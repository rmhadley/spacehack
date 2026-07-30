"""Combat encounter dispatcher and death screen.

_handle_combat_encounter is the wrapper called from __main__.py
to start combat and handle victory/defeat outcomes (bounty
completion, death screen).

_render_death_screen displays the dramatic "ship destroyed" overlay
when the player loses.
"""

from __future__ import annotations

import tcod.event

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

        # Dead enemies are already removed individually during combat
        # by _remove_dead_entity (called from _weapons.py on each kill),
        # and their procedural spawns are cleaned up per-kill in
        # _weapons.py (matched by squad_id + npc_id for 1:1 precision).
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
