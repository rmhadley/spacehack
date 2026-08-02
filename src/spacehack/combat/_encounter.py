"""Combat encounter dispatcher and death screen.

_handle_combat_encounter is the wrapper called from __main__.py
to start combat and handle victory/defeat outcomes (bounty
completion, death screen).

_render_death_screen displays the dramatic "ship destroyed" overlay
when the player loses.
"""

from __future__ import annotations

import tcod.event

from .. import world
from .. import message_log as _ml
from ..engine import SCREEN_WIDTH, SCREEN_HEIGHT
from ._loop import run_combat
from . import _rules_space


def _handle_combat_encounter(ctx, console, encounter) -> str:
    """Resolve a combat encounter triggered by the dispatcher.

    Was inlined in __main__._handle_combat_encounter pre-N1; promoted
    to combat.py so the dispatcher stays combat-unaware. The
    encounter param is normally a tuple ``(specs, positions)``
    produced by ``navigation._detect_combat_encounter``.

    Returns ``"VICTORY"``, ``"DEFEAT"``, or ``"FLEE"``.
    """
    from .. import ui as _ui_module

    # Already dead from a previous defeat — no-op.
    if getattr(ctx, 'player_dead', False):
        return "DEFEAT"

    if not encounter:
        ctx.log.add("Encounter data missing.")
        return "FLEE"

    try:
        _specs, _positions = encounter
    except (ValueError, TypeError):
        ctx.log.add("Corrupted encounter data.")
        return "FLEE"

    # Resolve pilot skills — use ctx defaults if available, else
    # hard-coded 30/30/30 as a fallback for test/legacy callers.
    _pilot_skills = getattr(ctx, 'pilot_skills', None)
    if _pilot_skills is None:
        from ..data.pilot_skills import PilotSkills
        _pilot_skills = PilotSkills(gunnery=30, piloting=30, engineering=30)

    # Sanity: player must have a ship catalog and owned ship.
    if ctx.player_owned_ship is None:
        ctx.log.add("No ship — cannot start combat.")
        return "FLEE"

    _ship_cat = None
    from ..data.ships import find_ship as _find_ship_catalog
    try:
        _ship_cat = _find_ship_catalog(ctx.player_owned_ship.ship_id)
    except (KeyError, AttributeError):
        ctx.log.add("Ship catalog mismatch — cannot start combat.")
        return "FLEE"

    from ._rules_space import init as _rs_init
    _rs_init(
        ctx, console,
        _ship_cat, ctx.player_owned_ship,
        ctx.player.pos, _pilot_skills,
        _specs, _positions,
        ctx.game_map, ctx.log,
    )
    _cr = run_combat(console, ctx, ctx.game_map, _rules_space)

    if _cr.outcome == "VICTORY":
        if len(_cr.defeated_names) == 1:
            ctx.log.add(f"Victory! {_cr.defeated_names[0]} destroyed.")
        else:
            ctx.log.add(f"Victory! {len(_cr.defeated_names)} enemies destroyed.")

        # Apply combat kill reputation changes + XP per defeated enemy.
        # Squad bonus (+1 to positive deltas) folds in when the
        # entire original group is wiped (2+ enemies).
        from ..faction import modify_rep, _COMBAT_KILL_DELTAS
        from ..data.npc_ships import find_npc_ship as _fns
        from ..data.ships import find_ship as _find_ship_cat
        from ..xp import add_xp as _add_xp
        _all_killed = len(_cr.defeated_spec_ids) == len(_specs)
        _squad_bonus = _all_killed and len(_cr.defeated_spec_ids) >= 2
        for _dsid in _cr.defeated_spec_ids:
            try:
                _es = _fns(_dsid)
                # Combat XP: enemy base hull * 2 per kill.
                try:
                    _sc = _find_ship_cat(_es.ship_id)
                    _add_xp(ctx, _sc.base_hull * 2)
                except (KeyError, ImportError):
                    pass
                # Playstyle kill counters.
                if hasattr(ctx, 'player_counters'):
                    ctx.player_counters.total_kills += 1
                    if getattr(_es, 'faction', '') == 'merchant':
                        ctx.player_counters.merchant_kills += 1
                # Faction reputation deltas.
                _deltas = _COMBAT_KILL_DELTAS.get(_es.faction, {})
                for _fac, _delta in _deltas.items():
                    if _squad_bonus and _delta > 0:
                        _delta += 1
                    modify_rep(ctx, _fac, _delta)
            except (KeyError, ImportError):
                pass

        # Check bounty completion: match defeated bounty_spawn_ids
        # collected during combat against active missions. Only the
        # specific bounty target entity triggers completion.
        _missions = getattr(ctx, 'player_active_missions', [])
        for _m in _missions:
            _m_spawn = getattr(_m, 'bounty_spawn_id', None)
            if _m_spawn is not None and _m_spawn in _cr.defeated_bounty_ids:
                # Salvage missions: killing the guard patrol does NOT complete
                # the mission — the component is secured from the wreck's
                # interior and delivered to the barkeep. Still clean up the
                # dead patrol's BountySpawn so it doesn't linger.
                if getattr(_m, 'salvage_layout_id', None) is not None:
                    from ..navigation import _remove_bounty_spawn
                    _remove_bounty_spawn(ctx, _m_spawn, getattr(_m, 'target_system_id', None))
                    continue
                from ..mission import complete_mission as _complete
                _today = ctx.time_day + (ctx.time_month - 1) * 30
                _complete(_m, ctx.player_owned_ship, ctx.stats, ctx.log, current_day=_today, ctx=ctx)
                if not _m.is_procedural:
                    ctx.completed_mission_ids.add(_m.mission_id)
                try:
                    _missions.remove(_m)
                except ValueError:
                    pass
                ctx.player_active_missions = _missions
                ctx.log.add(f"Bounty complete! {_m.title}")
                # Clean up the BountySpawn so re-detect doesn't find it.
                from ..navigation import _remove_bounty_spawn
                _remove_bounty_spawn(ctx, _m_spawn, getattr(_m, 'target_system_id', None))

        # Main-quest bounty objective (Act 0 chains): a quest-tagged
        # spawn defeated completes the matching chain step. Runs AFTER
        # the mission-bounty loop so mission spawns don't double-trigger.
        from .. import main_quest as _mq_module
        _mq_module.maybe_complete_bounty(ctx, _cr.defeated_bounty_ids)

        # --- Intercept/heist cleanup: remove BountySpawn entries so re-detect doesn't find them.
        # (Loot entity is spawned in _rules_space.on_kill where the death position is available.)
        _hei_missions = [
            _m for _m in (_missions or [])
            if getattr(_m, 'bounty_spawn_id', None) is not None
            and getattr(_m, 'heist_target_good_id', None) is not None
            # Salvage missions reuse heist_target_good_id for the component
            # but their patrol carries no heist_spawn_id — exclude them.
            and getattr(_m, 'salvage_layout_id', None) is None
        ]
        for _hm in _hei_missions:
            _hm_spawn = getattr(_hm, 'bounty_spawn_id', None)
            if _hm_spawn is not None and _hm_spawn in _cr.defeated_heist_ids:
                from ..navigation import _remove_bounty_spawn
                _remove_bounty_spawn(ctx, _hm_spawn, getattr(_hm, 'target_system_id', None))

        # Dead enemies are already removed individually during combat
        # by rules.on_kill() (which calls _remove_dead_entity and cleans
        # up procedural spawns matched by squad_id + npc_id).
        # No post-combat sweep needed.

    elif _cr.outcome == "DEFEAT":
        ctx.player_dead = True
        _render_death_screen(console, ctx.context, ctx.log)
    elif _cr.outcome == "FLEE":
        # Apply cowardice rep penalty for fleeing combat.
        from ..faction import modify_rep, _COMBAT_FLEE_DELTAS
        for _fac, _delta in _COMBAT_FLEE_DELTAS.items():
            modify_rep(ctx, _fac, _delta)

    return _cr.outcome


def detect_ground_combat(
    ctx, game_map, player_pos,
) -> list:
    """Check for hostile NPC chars within detect radius + LOS.

    If any hostile entity spots the player, all entities with the
    same ``squad_id`` within a 20-tile assist radius are pulled into
    combat.  Fog is revealed around all combatants.
    Returns a list of hostile :class:`world.Entity` (may be empty).
    """
    import math as _m
    from ..data.npc_chars import find_npc_char as _fnc
    from .. import faction as _faction
    from ..dungeon import reveal_around as _reveal_around

    _ASSIST_RADIUS = 20

    for _e in game_map.entities:
        if _e is ctx.player:
            continue
        _eid = getattr(_e, 'npc_char_id', '')
        if not _eid:
            continue
        try:
            _spec = _fnc(_eid)
        except KeyError:
            continue
        _rep = ctx.faction_reputation.get(_spec.faction, 0)
        _attitude = _faction.get_attitude(_rep)
        if _attitude not in ("enemy", "disliked"):
            continue
        _dist = _m.hypot(player_pos.x - _e.pos.x, player_pos.y - _e.pos.y)
        if _dist <= 0 or _dist > _spec.detect_radius:
            continue
        _steps = max(abs(_e.pos.x - player_pos.x), abs(_e.pos.y - player_pos.y))
        _los_blocked = False
        for _si in range(1, _steps):
            _t = _si / max(_steps, 1)
            _lx = round(player_pos.x + (_e.pos.x - player_pos.x) * _t)
            _ly = round(player_pos.y + (_e.pos.y - player_pos.y) * _t)
            if game_map.in_bounds(_lx, _ly):
                _tile = game_map.tiles[_ly][_lx]
                if not _tile.walkable:
                    _los_blocked = True
                    break
        if _los_blocked:
            continue

        _squad_id = getattr(_e, 'squad_id', '')
        _result = [_e]
        if _squad_id:
            for _oe in game_map.entities:
                if _oe is _e or _oe is ctx.player:
                    continue
                if getattr(_oe, 'squad_id', '') != _squad_id:
                    continue
                if not getattr(_oe, 'npc_char_id', ''):
                    continue
                _od = _m.hypot(
                    player_pos.x - _oe.pos.x, player_pos.y - _oe.pos.y,
                )
                if _od <= _ASSIST_RADIUS:
                    _result.append(_oe)

        for _ce in _result:
            _reveal_around(game_map, _ce.pos, radius=3)

        return _result

    return []


def _render_death_screen(console, context, log) -> None:
    """Display a dramatic full-screen death overlay and wait for input.

    Renders a red-tinted screen with a final message and the message
    log so the player can review how they died.
    """
    from .. import message_log as _ml

    _lines = [
        "",
        "╔══════════════════════════════════════╗",
        "║          SHIP DESTROYED              ║",
        "╚══════════════════════════════════════╝",
        "",
        "Your ship has been destroyed.",
        "All crew lost. All cargo lost.",
        "",
        "Press any key to return to the main menu...",
    ]

    while True:
        console.clear()
        console_bg = (40, 0, 0)  # dark red background
        for y in range(SCREEN_HEIGHT):
            for x in range(SCREEN_WIDTH):
                console.print(x=x, y=y, string=" ", fg=(255, 255, 255), bg=console_bg)

        # Centre the death message
        _msg_y = SCREEN_HEIGHT // 2 - len(_lines) // 2
        for _i, _line in enumerate(_lines):
            _x = (SCREEN_WIDTH - len(_line)) // 2
            console.print(x=_x, y=_msg_y + _i, string=_line, fg=(255, 80, 80))

        # Show recent log entries at the bottom
        _ml.render_message_log(
            console, log,
            screen_width=SCREEN_WIDTH,
            screen_height=SCREEN_HEIGHT,
        )

        context.present(console)

        for event in tcod.event.wait():
            if isinstance(event, tcod.event.Quit):
                raise SystemExit()
            if isinstance(event, tcod.event.KeyDown):
                return
