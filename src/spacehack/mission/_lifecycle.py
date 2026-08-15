"""Mission acceptance, cargo, reward, and reputation lifecycle logic."""
from __future__ import annotations

from .. import ship
from ..data.missions import MissionSpec, find_mission
from ._models import ActiveMission, MAX_ACTIVE_MISSIONS


def _cargo_accept_error(mission: MissionSpec, owned_ship: object, log: object) -> bool:
    """Return whether cargo prevents accepting ``mission``."""
    if mission.required_cargo_size <= 0:
        return False
    if owned_ship is None:
        log.add("You don't have a ship to carry cargo yet.")
        return True
    ship_obj = ship.find_ship(owned_ship.ship_id)
    _eff_cap = ship.effective_max_cargo(ship_obj, owned_ship)
    new_used = owned_ship.cargo_used + mission.required_cargo_size
    if new_used <= _eff_cap:
        return False
    short = new_used - _eff_cap
    log.add(
        f"Your {ship_obj.name} can't carry '{mission.title}' - "
        f"{short} cargo unit(s) over capacity ({owned_ship.cargo_used}/{_eff_cap})."
    )
    return True


def try_accept_mission(
    mission: MissionSpec,
    owned_ship: object,
    log: object,
    active_count: int = 0,
) -> bool:
    """Accept ``mission`` if the player has room and cargo capacity."""
    if active_count >= MAX_ACTIVE_MISSIONS:
        log.add(
            f"Your mission log is full ({MAX_ACTIVE_MISSIONS}/{MAX_ACTIVE_MISSIONS}). "
            "Abandon one first (Q)."
        )
        return False
    return not _cargo_accept_error(mission, owned_ship, log)


def commit_accept_mission(
    mission: MissionSpec,
    owned_ship: object | None,
    log: object,
) -> None:
    """Apply the side-effects of accepting ``mission``.

    Loads cargo onto ``owned_ship`` (if the mission has cargo) and
    logs the acceptance. Call this AFTER :func:`try_accept_mission`
    returns ``True`` and the :class:`ActiveMission` has been created.
    """
    if mission.required_cargo_size > 0 and owned_ship is not None:
        owned_ship.mission_reserved += mission.required_cargo_size
        ship_obj = ship.find_ship(owned_ship.ship_id)
        _eff_cap = ship.effective_max_cargo(ship_obj, owned_ship)
        log.add(
            f"You accept: {mission.title}. "
            f"Cargo now {owned_ship.cargo_used}/{_eff_cap}."
        )
    else:
        log.add(f"You accept: {mission.title}.")


def _reserved_heist_volume(active: ActiveMission) -> int:
    """Hold space reserved by a secured intercept mission (0 if none).

    Assumes the loot quantity is 1 (intercept loot entities are
    spawned with ``quantity: 1``). Keep in sync with the secure-side
    reservation in ``trade._secure_heist_cargo`` — the flag is set
    only AFTER this lookup on the release side, so the two can't
    share one helper without breaking that timing.
    """
    if not getattr(active, 'heist_good_secured', False):
        return 0
    _good_id = getattr(active, 'heist_target_good_id', None)
    if not _good_id:
        return 0
    try:
        from ..data.trade_goods import find_trade_good as _ftg
        return _ftg(_good_id).volume
    except KeyError:
        return 0


def release_mission_cargo(active: ActiveMission, owned_ship: object) -> int:
    """Release the mission's reserved hold volume; returns units freed.

    Frees both the delivery reservation (``required_cargo_size``) and
    any secured intercept cargo. Shared by abort / complete / auto-fail
    paths so the release math lives in exactly one place. Returns 0
    when there is no ship or nothing was reserved.
    """
    if owned_ship is None:
        return 0
    _release = active.required_cargo_size + _reserved_heist_volume(active)
    if _release <= 0:
        return 0
    owned_ship.mission_reserved = max(
        0, owned_ship.mission_reserved - _release,
    )
    return _release


def abort_mission(
    active: ActiveMission,
    owned_ship: object,
    log: object,
) -> None:
    """Drop the mission's cargo from ``owned_ship`` and log the release.

    Does NOT remove ``active`` from the mission list — the caller
    owns that bookkeeping.
    """
    if owned_ship is None:
        return
    if release_mission_cargo(active, owned_ship) <= 0:
        return
    ship_obj = ship.find_ship(owned_ship.ship_id)
    _eff_cap = ship.effective_max_cargo(ship_obj, owned_ship)
    log.add(
        f"Cargo released from abandoned '{active.title}' "
        f"({owned_ship.cargo_used}/{_eff_cap})."
    )


def _mission_spec_for(active: ActiveMission, ctx):
    """Resolve a completed mission to its static or generated spec."""
    try:
        if active.is_procedural:
            return ctx.generated_missions.get(active.mission_id)
        return find_mission(active.mission_id)
    except (KeyError, AttributeError):
        return None


def _record_faction_mission(ctx, active: ActiveMission) -> None:
    """Increment explicit faction-career counters before awarding XP."""
    if not hasattr(ctx, "player_counters"):
        return
    _spec = _mission_spec_for(active, ctx)
    if _spec is None:
        return
    _faction = getattr(_spec, "faction", "")
    _counter = ctx.player_counters
    if _faction == "merchants":
        _counter.merchant_missions_completed += 1
        # Preserve the legacy delivery counter for existing saves/UI.
        if getattr(_spec, "mission_type", "") == "delivery":
            _counter.deliveries_completed += 1
    elif _faction == "bar":
        _counter.bar_missions_completed += 1
    elif _faction in {"bhguild", "bounty"}:
        _counter.bounty_missions_completed += 1
        # Preserve the legacy bounty counter for existing saves/UI.
        _counter.bounties_completed += 1


def _payout(active: ActiveMission, current_day: int) -> tuple[int, int, str]:
    """Return adjusted ``(credits, xp, bonus_message)`` for a completion."""
    credits = active.reward_credits
    xp = active.reward_xp
    if active.deadline_days <= 0 or active.accept_day <= 0 or current_day <= 0:
        return credits, xp, ""
    elapsed = current_day - active.accept_day
    if elapsed < active.deadline_days // 2 and active.early_bonus_pct > 0:
        bonus = credits * active.early_bonus_pct // 100
        return credits + bonus, xp, f" Early delivery bonus: +{bonus}$."
    if elapsed > active.deadline_days:
        return credits // 2, 0, " Late delivery - half pay."
    return credits, xp, ""


def _log_payout(active, owned_ship, stats, log, credits, xp, bonus_msg) -> None:
    """Apply credits and log the completion summary."""
    if hasattr(stats, "credits"):
        stats.credits += credits
    ship_obj = ship.find_ship(owned_ship.ship_id) if owned_ship is not None else None
    cargo_after = (
        f"{owned_ship.cargo_used}/{ship.effective_max_cargo(ship_obj, owned_ship)}"
        if ship_obj is not None else "no ship"
    )
    log.add(
        f"Delivered: {active.title}. +{credits}$ +{xp}xp. "
        f"({cargo_after} cargo.){bonus_msg}"
    )


def _is_early_completion(active: ActiveMission, current_day: int) -> bool:
    """Return whether a mission qualifies for its early-completion bonus."""
    return (
        active.deadline_days > 0 and active.accept_day > 0 and current_day > 0
        and current_day - active.accept_day < active.deadline_days // 2
    )


def complete_mission(
    active: ActiveMission,
    owned_ship: object,
    stats: object,
    log: object,
    current_day: int = 0,
    ctx = None,
) -> None:
    """Complete ``active`` and apply its reward, progress, and reputation."""
    release_mission_cargo(active, owned_ship)
    credits, xp, bonus_msg = _payout(active, current_day)
    _log_payout(active, owned_ship, stats, log, credits, xp, bonus_msg)
    if ctx is not None:
        _record_faction_mission(ctx, active)
        if xp > 0:
            from ..xp import add_xp
            add_xp(ctx, xp)
        _apply_mission_rep(
            active, ctx, is_early=_is_early_completion(active, current_day),
        )


def _mission_type_for(active: ActiveMission, ctx) -> str | None:
    """Resolve the static or generated mission type for reputation."""
    try:
        _spec = (
            ctx.generated_missions.get(active.mission_id)
            if active.is_procedural else find_mission(active.mission_id)
        )
        return getattr(_spec, "mission_type", None)
    except (KeyError, AttributeError):
        return None


def _apply_rep_delta(ctx, faction: str, delta: int, is_early: bool) -> None:
    """Apply one mission reputation delta, including the early bonus."""
    from ..faction import modify_rep
    if is_early and delta > 0:
        delta += (delta + 1) // 2
    modify_rep(ctx, faction, delta)


def _apply_mission_rep(
    active: ActiveMission,
    ctx,
    *,
    is_early: bool = False,
) -> None:
    """Apply the mission type's faction reputation changes."""
    from ..faction import _MISSION_REP_DELTAS
    mission_type = _mission_type_for(active, ctx)
    if mission_type is None:
        return
    deltas = _MISSION_REP_DELTAS.get(mission_type)
    if deltas is None:
        return
    for faction, delta in deltas.items():
        _apply_rep_delta(ctx, faction, delta, is_early)

