"""Combat encounter dispatcher and death screen.

_handle_combat_encounter is the wrapper called from __main__.py
to start combat and handle victory/defeat outcomes (bounty
completion, death screen).

_render_death_screen presents a full-screen "ship destroyed" frame
(no HUD, no console log) when the player loses; any key returns to
the main menu immediately and no save is written.
"""

from __future__ import annotations

from .. import pygame_engine
from .. import world
from .. import message_log as _ml
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

    # Resolve the player's live pilot skills from ctx.stats — the
    # source of truth that already folds in species/class base and
    # XP skill-point growth.  (ctx.pilot_skills was never set on
    # GameContext, so the old code silently fell back to a hard-
    # coded 30/30/30 and AP never grew past 4 no matter how high
    # the player raised piloting.)  Module bonuses are layered on
    # inside init_combat_state, so don't add them here.
    from ..data.pilot_skills import PilotSkills
    _pilot_skills = PilotSkills(
        gunnery=ctx.stats.gunnery,
        piloting=ctx.stats.piloting,
        engineering=ctx.stats.engineering,
    )

    # Sanity: player must have a ship catalog and owned ship.
    if ctx.player_owned_ship is None:
        ctx.log.add("No ship - cannot start combat.")
        return "FLEE"

    _ship_cat = None
    from ..data.ships import find_ship as _find_ship_catalog
    try:
        _ship_cat = _find_ship_catalog(ctx.player_owned_ship.ship_id)
    except (KeyError, AttributeError):
        ctx.log.add("Ship catalog mismatch - cannot start combat.")
        return "FLEE"

    # Militia live-fire test (mil_q5_livefire): temporarily mount the
    # breach charge prototype as a ship weapon for this combat only.
    # Dismounted after combat (win/flee/defeat) so it never persists.
    _breach_mounted = False
    _breach_wid = "breach_charge_test"
    if (_breach_wid not in (ctx.player_owned_ship.weapons or ())
            and ctx.main_quest_chain == "militia"):
        from .. import main_quest as _mq_check
        if _mq_check.step_status(ctx, "mil_q5_livefire") in (
            _mq_check.STATUS_AVAILABLE, _mq_check.STATUS_ACTIVE,
        ):
            from .. import solar_system as _ss
            if _ss.current_solar_system_id == "cygni":
                ctx.player_owned_ship.weapons = (
                    ctx.player_owned_ship.weapons + (_breach_wid,)
                )
                _breach_mounted = True
                ctx.log.add_colored(
                    "BREACH CHARGE ARMED - prototype mounted for live-fire test.",
                    _ml.COLOR_IMPORTANT_EVENT,
                )

    from ._rules_space import init as _rs_init
    # Tutorial: explain space combat before the combat UI takes over
    # (fires once, only in tutorial runs).
    from ..tutorial import maybe_space_combat_intro as _tut_space_intro
    _tut_space_intro(ctx)
    _rs_init(
        ctx, console,
        _ship_cat, ctx.player_owned_ship,
        ctx.player.pos, _pilot_skills,
        _specs, _positions,
        ctx.game_map, ctx.log,
    )
    _cr = run_combat(console, ctx, ctx.game_map, _rules_space)

    # Dismount the breach charge prototype if it was temporarily
    # mounted for the militia live-fire test (mil_q5_livefire).
    if _breach_mounted and _breach_wid in (ctx.player_owned_ship.weapons or ()):
        ctx.player_owned_ship.weapons = tuple(
            w for w in ctx.player_owned_ship.weapons
            if w != _breach_wid
        )
        ctx.log.add_colored(
            "BREACH CHARGE DISARMED - prototype test complete.",
            _ml.COLOR_IMPORTANT_EVENT,
        )

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
        _render_death_screen(ctx)
    elif _cr.outcome == "FLEE":
        # Apply cowardice rep penalty for fleeing combat.
        from ..faction import modify_rep, _COMBAT_FLEE_DELTAS
        for _fac, _delta in _COMBAT_FLEE_DELTAS.items():
            modify_rep(ctx, _fac, _delta)

    return _cr.outcome


def noise_hostiles(
    ctx,
    game_map,
    player_pos,
    radius: int,
) -> list:
    """Hostiles drawn by gunfire/sound — the future noise seam (stub).

    v1 is pure LOS (design doc 12, decision #3): noise is deferred, so
    this stub returns an empty list. It exists to prove the seam:
    ``visible_hostiles`` ORs this in, and because the combat trigger,
    the mid-fight join scan, and the end-of-combat check all call
    ``visible_hostiles``, a real noise scan can be added here later
    with ZERO changes to those consumers — the single OR-in point.

    The args are the seam contract — deliberately unused today, but
    already wired: the player's position is the shot origin and
    ``radius`` is the hearing range. When noise lands, only this
    function's body (and optionally the call in
    ``visible_hostiles``) changes; nothing else in combat reads it.
    """
    return []


def visible_hostiles(
    ctx,
    game_map,
    player_pos,
    radius: int,
) -> list:
    """Hostiles the player can currently see: within ``radius`` + clear LOS.

    The single player-LOS aggro predicate (design doc 12) shared by the
    combat trigger, the mid-fight join scan, and the end-of-combat
    check. Side-effect free: no squad linkage, no assist radius, no
    auto-reveal — the fight is exactly what the player sees. The noise
    seam (decision #3) ORs in here; ``noise_hostiles`` is the only
    additional source of hostiles, so future gunfire-drawn mobs need
    no consumer changes.
    """
    from ..data.npc_chars import find_npc_char as _fnc
    from .. import faction as _faction
    from ._animations import _has_los

    _result: list = []
    for _e in game_map.entities:
        if (_e.pos.x, _e.pos.y) == (player_pos.x, player_pos.y):
            continue
        if max(abs(_e.pos.x - player_pos.x), abs(_e.pos.y - player_pos.y)) > radius:
            continue
        _eid = getattr(_e, 'npc_char_id', '')
        if not _eid:
            continue
        try:
            _spec = _fnc(_eid)
        except KeyError:
            continue
        if not _faction.spec_is_hostile(ctx, _spec):
            continue
        if not _has_los(game_map, player_pos.x, player_pos.y, _e.pos.x, _e.pos.y):
            continue
        _result.append(_e)
    # Noise seam: mobs drawn by gunfire OR into the visible set here.
    # Empty stub in v1 — the single OR-in point for the future system.
    _result.extend(noise_hostiles(ctx, game_map, player_pos, radius))
    return _result


def detect_ground_combat(
    ctx, game_map, player_pos,
) -> list:
    """Hostiles currently visible to the player — LOS-based aggro.

    Returns the full visible set (no squad linkage, no assist radius,
    no auto-reveal). The player fights exactly what they see; mobs
    that wander into view mid-fight join via
    ``_rules_ground.check_reinforcements``.
    """
    _radius = getattr(game_map, 'sight_radius', 8)
    return visible_hostiles(ctx, game_map, player_pos, _radius)


def _wait_for_death_input(ctx, lines: tuple[str, ...] = ()) -> None:
    """Wait for dismissal through the shared Pygame presentation.

    Presents the full-screen death frame (no HUD, no console log) and
    returns on any key, or exits on window close.
    """
    from .. import pygame_combat

    pygame_combat.present_death(ctx, lines=lines)
    for event in ctx.context.wait_events():
        if pygame_engine.is_quit(event):
            raise SystemExit()
        if pygame_engine.is_keydown(event):
            return


def _render_death_screen(ctx, *, lines: tuple[str, ...] = ()) -> None:
    """Display a dramatic full-screen death overlay and wait for input.

    The entire shared surface is painted dark red with a centered
    final message - no HUD column, no console-log band. Any key
    returns to the main menu immediately; the death path never
    writes a save.
    """
    _wait_for_death_input(ctx, lines=lines)
