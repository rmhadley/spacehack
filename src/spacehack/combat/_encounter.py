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
from .. import message_log as _ml
from ._loop import run_combat
from . import _rules_space


def _resolve_combat_inputs(ctx, encounter):
    """Validate encounter data + player readiness; returns ``(outcome, inputs)``.

    ``outcome`` is ``"DEFEAT"`` (player already dead) or ``"ABORTED"``
    (combat cannot start) — each failure path logs why. Otherwise
    ``inputs`` is ``(specs, positions, ship_cat, pilot_skills)``.
    Pilot skills come from ``ctx.stats``, the source of truth that
    folds in species/class base and XP skill-point growth; module
    bonuses are layered on inside ``init_combat_state`` — not here.
    """
    if getattr(ctx, 'player_dead', False):
        return "DEFEAT", None
    if not encounter:
        ctx.log.add("Encounter data missing.")
        return "ABORTED", None
    try:
        _specs, _positions = encounter
    except (ValueError, TypeError):
        ctx.log.add("Corrupted encounter data.")
        return "ABORTED", None
    if ctx.player_owned_ship is None:
        ctx.log.add("No ship - cannot start combat.")
        return "ABORTED", None
    from ..data.pilot_skills import PilotSkills
    _pilot_skills = PilotSkills(
        gunnery=ctx.stats.gunnery,
        piloting=ctx.stats.piloting,
        engineering=ctx.stats.engineering,
    )
    from ..data.ships import find_ship as _find_ship_catalog
    try:
        _ship_cat = _find_ship_catalog(ctx.player_owned_ship.ship_id)
    except (KeyError, AttributeError):
        ctx.log.add("Ship catalog mismatch - cannot start combat.")
        return "ABORTED", None
    return None, (_specs, _positions, _ship_cat, _pilot_skills)


def _mount_breach_charge(ctx) -> tuple[bool, str]:
    """Mount the militia live-fire prototype for this combat, if due.

    Returns ``(mounted, weapon_id)``; the caller dismounts after
    combat (win/flee/defeat) so it never persists.
    """
    _wid = "breach_charge_test"
    if (_wid in (ctx.player_owned_ship.weapons or ())
            or ctx.main_quest_chain != "militia"):
        return False, _wid
    from .. import main_quest as _mq_check
    if _mq_check.step_status(ctx, "mil_q5_livefire") not in (
        _mq_check.STATUS_AVAILABLE, _mq_check.STATUS_ACTIVE,
    ):
        return False, _wid
    from .. import solar_system as _ss
    if _ss.current_solar_system_id != "cygni":
        return False, _wid
    ctx.player_owned_ship.weapons = ctx.player_owned_ship.weapons + (_wid,)
    ctx.log.add_colored(
        "BREACH CHARGE ARMED - prototype mounted for live-fire test.",
        _ml.COLOR_IMPORTANT_EVENT,
    )
    return True, _wid


def _dismount_breach_charge(ctx, mounted: bool, weapon_id: str) -> None:
    """Remove the militia live-fire prototype after combat."""
    if not mounted or weapon_id not in (ctx.player_owned_ship.weapons or ()):
        return
    ctx.player_owned_ship.weapons = tuple(
        w for w in ctx.player_owned_ship.weapons if w != weapon_id
    )
    ctx.log.add_colored(
        "BREACH CHARGE DISARMED - prototype test complete.",
        _ml.COLOR_IMPORTANT_EVENT,
    )


def _apply_kill_reputation(ctx, _cr, _specs) -> None:
    """Apply per-kill playstyle counters and faction rep for a victory.

    Kill XP and the ``total_kills`` counter are granted at kill time by
    ``_rules_space._finalize_kill``; this pass only records the
    merchant-kill counter and reputation. Squad bonus (+1 to positive
    deltas) folds in when the entire original group is wiped (2+).
    """
    from ..faction import modify_rep, _COMBAT_KILL_DELTAS
    from ..data.npc_ships import find_npc_ship as _fns
    _all_killed = len(_cr.defeated_spec_ids) == len(_specs)
    _squad_bonus = _all_killed and len(_cr.defeated_spec_ids) >= 2
    for _dsid in _cr.defeated_spec_ids:
        try:
            _es = _fns(_dsid)
            if hasattr(ctx, 'player_counters'):
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


def _complete_bounty_missions(ctx, _cr) -> None:
    """Complete missions whose bounty target died this fight.

    Only the specific bounty target entity triggers completion;
    salvage-mission patrols are cleaned up without completing.
    """
    _missions = getattr(ctx, 'player_active_missions', [])
    for _m in _missions:
        _m_spawn = getattr(_m, 'bounty_spawn_id', None)
        if _m_spawn is None or _m_spawn not in _cr.defeated_bounty_ids:
            continue
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


def _cleanup_heist_spawns(ctx, _cr) -> None:
    """Remove intercept BountySpawn entries so re-detect can't refind them.

    The loot entity is spawned in ``_rules_space.on_kill`` where the
    death position is available.
    """
    _missions = getattr(ctx, 'player_active_missions', [])
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


def _handle_victory(ctx, _cr, _specs) -> None:
    """Apply victory bookkeeping: log, per-kill rewards, missions."""
    if len(_cr.defeated_names) == 1:
        ctx.log.add(f"Victory! {_cr.defeated_names[0]} destroyed.")
    else:
        ctx.log.add(f"Victory! {len(_cr.defeated_names)} enemies destroyed.")
    _apply_kill_reputation(ctx, _cr, _specs)
    _complete_bounty_missions(ctx, _cr)
    # Main-quest bounty objective (Act 0 chains): a quest-tagged
    # spawn defeated completes the matching chain step. Runs AFTER
    # the mission-bounty loop so mission spawns don't double-trigger.
    from .. import main_quest as _mq_module
    _mq_module.maybe_complete_bounty(ctx, _cr.defeated_bounty_ids)
    _cleanup_heist_spawns(ctx, _cr)
    # Dead enemies are already removed individually during combat by
    # rules.on_kill() (which calls _remove_dead_entity and cleans up
    # procedural spawns matched by squad_id + npc_id). No post-combat
    # sweep needed.


def _handle_combat_encounter(ctx, console, encounter) -> str:
    """Resolve a combat encounter triggered by the dispatcher.

    The encounter param is normally ``(specs, positions)`` from
    ``navigation._detect_combat_encounter``. Returns ``"VICTORY"``,
    ``"DEFEAT"``, or ``"ABORTED"`` when no combat occurred.
    """
    _blocked, _inputs = _resolve_combat_inputs(ctx, encounter)
    if _blocked is not None:
        return _blocked
    _specs, _positions, _ship_cat, _pilot_skills = _inputs

    _breach_mounted, _breach_wid = _mount_breach_charge(ctx)
    from ._rules_space import init as _rs_init
    from ..tutorial import maybe_space_combat_intro as _tut_space_intro
    _tut_space_intro(ctx)  # one-time tutorial intro, tutorial runs only
    _rs_init(ctx, console, _ship_cat, ctx.player_owned_ship,
             ctx.player.pos, _pilot_skills, _specs, _positions,
             ctx.game_map, ctx.log)
    _cr = run_combat(console, ctx, ctx.game_map, _rules_space)
    _dismount_breach_charge(ctx, _breach_mounted, _breach_wid)

    if _cr.outcome == "VICTORY":
        _handle_victory(ctx, _cr, _specs)
    elif _cr.outcome == "DEFEAT":
        ctx.player_dead = True
        _render_death_screen(ctx)

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


def _visible_hostile_entities(ctx, game_map, player_pos, radius) -> list:
    """Hostile map entities within ``radius`` with clear LOS to the player."""
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
    return _result


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
    _result = _visible_hostile_entities(ctx, game_map, player_pos, radius)
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
