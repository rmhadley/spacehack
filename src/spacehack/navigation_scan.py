"""Militia cargo-scan exposure, confiscation, and smuggling-mission failure.

Extracted from ``navigation.py`` to keep that module under the 1,000-line
architecture limit. Every function here stays under 40 lines.
"""

from __future__ import annotations

from . import main_quest as main_quest_module
from . import message_log
from . import mission as mission_module
from . import ship as ship_module


def _compute_scan_exposure(owned, active_missions) -> tuple[list, list]:
    """Pure: compute what a militia scan would confiscate.

    Returns ``(failed_missions, confiscated)`` where ``failed_missions``
    are active ``is_smuggle`` missions whose cargo overflows the
    smuggler's hold, and ``confiscated`` is ``(good_id, qty, fine)``
    triples for exposed inventory contraband. Mutates nothing — the
    caller applies the outcome only after the scan roll succeeds.
    """
    from .data.trade_goods import find_trade_good as _ftg
    _hold_cap = ship_module.smuggler_hold_capacity(owned)
    _failed_missions: list = []
    for _am in list(active_missions):
        if not getattr(_am, 'is_smuggle', False):
            continue
        _vol = _am.required_cargo_size
        if _vol <= _hold_cap:
            _hold_cap -= _vol
        else:
            _failed_missions.append(_am)
            _hold_cap = 0
    _confiscated: list[tuple[str, int, int]] = []
    for gid, qty in list(owned.inventory.items()):
        try:
            good = _ftg(gid)
        except KeyError:
            continue
        if good.category != "contraband":
            continue
        # The hold conceals crates up to its remaining volume capacity.
        _protected_crates = 0
        if _hold_cap > 0 and good.volume > 0:
            _protected_crates = min(qty, _hold_cap // good.volume)
            _hold_cap -= _protected_crates * good.volume
        _lose = qty - _protected_crates
        if _lose <= 0:
            continue
        _fine = good.base_price * _lose // 2
        _confiscated.append((gid, _lose, _fine))
    return _failed_missions, _confiscated


def _apply_scan_confiscation(ctx, owned, confiscated) -> None:
    """Mutate: remove confiscated inventory contraband and levy the fine.

    ``confiscated`` is the ``(good_id, qty, fine)`` triple list from
    :func:`_compute_scan_exposure`. Logs each confiscation, deletes or
    decrements the goods, and deducts the total fine from credits.
    """
    from .data.trade_goods import find_trade_good as _ftg
    _total_fine = 0
    for gid, qty, fine in confiscated:
        good = _ftg(gid)
        ctx.log.add_colored(
            f"Contraband {good.name} x{qty} confiscated by militia!",
            message_log.COLOR_IMPORTANT_EVENT,
        )
        _total_fine += fine
        remaining = owned.inventory.get(gid, 0) - qty
        if remaining <= 0:
            if gid in owned.inventory:
                del owned.inventory[gid]
        else:
            owned.inventory[gid] = remaining
    ctx.stats.credits = max(0, ctx.stats.credits - _total_fine)
    ctx.log.add_colored(
        f"Militia levies a fine of {_total_fine}$ for contraband.",
        message_log.COLOR_IMPORTANT_EVENT,
    )


def _militia_scan_target(ctx, planet_id: str):
    """Guard + resolve the militia checkpoint for a landing scan.

    Returns ``(owned, spec)`` when a scan is possible — the player
    owns a ship AND the planet is known AND has a militia building.
    Returns ``None`` otherwise (no scan). Pure lookup, no mutation.
    """
    owned = ctx.player_owned_ship
    if owned is None:
        return None
    from .data.planets import find_planet_spec, has_militia_presence
    try:
        spec = find_planet_spec(planet_id)
    except KeyError:
        return None
    if not has_militia_presence(planet_id):
        return None
    return owned, spec


def _fail_smuggle_mission(ctx, owned, active) -> None:
    """Auto-fail a smuggling mission whose cargo was confiscated.

    Releases the mission's reserved cargo volume, marks the mission
    FAILED, removes it from the active list, and returns a static
    mission to its giver's board so it can be re-accepted.
    """
    mission_module.release_mission_cargo(active, owned)
    active.status = mission_module.MissionStatus.FAILED
    ctx.log.add_colored(
        f"Mission FAILED \u2014 militia confiscates the smuggled cargo of "
        f"'{active.title}'!",
        message_log.COLOR_IMPORTANT_EVENT,
    )
    try:
        ctx.player_active_missions.remove(active)
    except ValueError:
        pass
    if not getattr(active, 'is_procedural', False):
        # Per-city boards: find by mission id, not NPC id (the same NPC
        # id exists on many planets, each with its own board).
        _board = mission_module.find_board_for_mission(ctx, active.mission_id)
        if _board is not None:
            mission_module.board_return_static(_board, active.mission_id)
    # Main-quest smuggle crate (Act 0 bar chain): a confiscation fails
    # the quest step — reset it so the Barkeep can re-offer his last
    # crate (the crate's ActiveMission is already removed above).
    if getattr(active, 'main_quest_step_id', ''):
        main_quest_module.fail_smuggle_step(ctx, active)


def _apply_scan_outcome(ctx, owned, failed_missions, confiscated) -> None:
    """Apply a fired scan's consequences: fail missions, confiscate goods."""
    for _am in failed_missions:
        _fail_smuggle_mission(ctx, owned, _am)
    if confiscated:
        _apply_scan_confiscation(ctx, owned, confiscated)


def _run_cargo_scan(ctx, planet_id: str) -> None:
    """Landing militia scan: warn at risk, roll 40%, then confiscate/fail.

    Smuggler's hold protects mission cargo FIRST (each ``is_smuggle``
    mission claims its ``required_cargo_size``), then inventory
    contraband. A mission whose cargo overflows the hold is
    confiscated and auto-fails (design decision 3). Exposure is
    computed up front so the player is warned BEFORE the roll.
    """
    from . import engine as _engine

    _target = _militia_scan_target(ctx, planet_id)
    if _target is None:
        return
    owned, spec = _target
    _failed_missions, _confiscated = _compute_scan_exposure(
        owned, ctx.player_active_missions,
    )
    if _confiscated or _failed_missions:
        ctx.log.add_colored(
            f"You're carrying goods a militia scan could confiscate on "
            f"{spec.name}!",
            message_log.COLOR_IMPORTANT_EVENT,
        )
    if _engine.RNG.random() >= 0.4:
        return
    ctx.log.add_colored(
        "A militia patrol hails you for a routine cargo scan...",
        message_log.COLOR_COMBAT_EVENT,
    )
    if not _confiscated and not _failed_missions:
        ctx.log.add("Militia scans your cargo \u2014 clean.")
        return
    _apply_scan_outcome(ctx, owned, _failed_missions, _confiscated)


def _run_space_cargo_scan(ctx) -> None:
    """Run a cargo scan triggered by militia auto-hail in space.

    Reuses the same exposure/confiscation logic as the planet-landing
    scan but skips the planet check and the 40% roll (the auto-hail
    already rolled). Always fires when called.
    """
    owned = ctx.player_owned_ship
    if owned is None:
        ctx.log.add("The militia patrol can't scan an empty hold?")
        return

    _failed_missions, _confiscated = _compute_scan_exposure(
        owned, ctx.player_active_missions,
    )

    ctx.log.add_colored(
        "A militia patrol scans your cargo...",
        message_log.COLOR_COMBAT_EVENT,
    )

    if not _confiscated and not _failed_missions:
        ctx.log.add("Militia scans your cargo - clean.")
        from .faction import modify_rep
        modify_rep(ctx, "militia", +1)
        return

    for _am in _failed_missions:
        _fail_smuggle_mission(ctx, owned, _am)
    if _confiscated:
        _apply_scan_confiscation(ctx, owned, _confiscated)
    from .faction import modify_rep
    modify_rep(ctx, "militia", -5)
