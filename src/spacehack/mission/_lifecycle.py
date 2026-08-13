"""Mission acceptance, cargo, reward, and reputation lifecycle logic."""
from __future__ import annotations

from .. import ship
from ..data.missions import MissionSpec, find_mission
from ._models import ActiveMission, MAX_ACTIVE_MISSIONS


def try_accept_mission(
    mission: MissionSpec,
    owned_ship: object,
    log: object,
    active_count: int = 0,
) -> bool:
    """Accept ``mission`` if the player has room and cargo capacity.

    Checks:
      1. ``active_count < MAX_ACTIVE_MISSIONS`` (slots check).
      2. If the mission has cargo, the owned ship must exist and have
         enough free capacity.

    Returns ``True`` if the mission can be accepted. Does NOT mutate
    state — the caller is responsible for creating the
    :class:`ActiveMission` and adding it to the list.
    """
    if active_count >= MAX_ACTIVE_MISSIONS:
        log.add(
            f"Your mission log is full ({MAX_ACTIVE_MISSIONS}/{MAX_ACTIVE_MISSIONS}). "
            "Abandon one first (Q)."
        )
        return False

    if mission.required_cargo_size <= 0:
        return True

    if owned_ship is None:
        log.add("You don't have a ship to carry cargo yet.")
        return False

    ship_obj = ship.find_ship(owned_ship.ship_id)
    _eff_cap = ship.effective_max_cargo(ship_obj, owned_ship)
    new_used = owned_ship.cargo_used + mission.required_cargo_size
    if new_used > _eff_cap:
        short = new_used - _eff_cap
        log.add(
            f"Your {ship_obj.name} can't carry '{mission.title}' - "
            f"{short} cargo unit(s) over capacity ({owned_ship.cargo_used}"
            f"/{_eff_cap})."
        )
        return False
    return True


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


def complete_mission(
    active: ActiveMission,
    owned_ship: object,
    stats: object,
    log: object,
    current_day: int = 0,
    ctx = None,
) -> None:
    """Complete ``active``: drop cargo, grant reward (with early/late
    modifiers), apply faction rep changes, and log the payout.

    Does NOT remove ``active`` from the mission list or add to
    ``completed_mission_ids`` — the caller owns that bookkeeping.

    ``ctx`` is optional for backward compatibility — rep changes
    are skipped when ctx is None (legacy callers, tests).
    """
    # Drop cargo (delivery reservation + secured intercept cargo).
    release_mission_cargo(active, owned_ship)

    # Compute reward with early/late modifiers.
    credits = active.reward_credits
    xp = active.reward_xp
    bonus_msg = ""

    if active.deadline_days > 0 and active.accept_day > 0 and current_day > 0:
        elapsed = current_day - active.accept_day
        half_deadline = active.deadline_days // 2
        if elapsed < half_deadline:
            # Early bonus: +early_bonus_pct% credits.
            if active.early_bonus_pct > 0:
                bonus = credits * active.early_bonus_pct // 100
                credits += bonus
                bonus_msg = f" Early delivery bonus: +{bonus}$."
        elif elapsed > active.deadline_days:
            # Late penalty: half credits, no XP.
            credits = credits // 2
            xp = 0
            bonus_msg = " Late delivery - half pay."

    if hasattr(stats, "credits"):
        stats.credits = stats.credits + credits

    ship_obj = (
        ship.find_ship(owned_ship.ship_id)
        if owned_ship is not None
        else None
    )
    cargo_after = (
        f"{owned_ship.cargo_used}/{ship.effective_max_cargo(ship_obj, owned_ship)}"
        if ship_obj is not None
        else "no ship"
    )
    log.add(
        f"Delivered: {active.title}. +{credits}$ "
        f"+{xp}xp. ({cargo_after} cargo.){bonus_msg}"
    )

    # --- XP gain ---
    if ctx is not None and xp > 0:
        from ..xp import add_xp
        add_xp(ctx, xp)
        # Increment delivery/bounty counters.
        if hasattr(ctx, 'player_counters'):
            _mtype = getattr(active, 'mission_id', '')
            if 'delivery' in _mtype.lower() or 'proc_delivery' in _mtype.lower():
                ctx.player_counters.deliveries_completed += 1
            elif 'bounty' in _mtype.lower() or 'proc_bounty' in _mtype.lower():
                ctx.player_counters.bounties_completed += 1

    # --- Faction reputation changes ---
    if ctx is not None:
        _apply_mission_rep(active, ctx, is_early=bool(
            active.deadline_days > 0 and active.accept_day > 0
            and current_day > 0
            and (current_day - active.accept_day) < active.deadline_days // 2
        ))


def _apply_mission_rep(
    active: ActiveMission,
    ctx,
    *,
    is_early: bool = False,
) -> None:
    """Apply faction reputation changes for completing ``active``.

    Looks up the mission type from the static catalog or generated
    missions, then applies the per-faction deltas from
    :data:`faction._MISSION_REP_DELTAS`.  If ``is_early`` is True,
    positive deltas get a +50% bonus (rounded up). Negative deltas
    are never boosted.
    """
    from ..faction import modify_rep, _MISSION_REP_DELTAS

    # Resolve mission type from spec.
    mission_type: str | None = None
    try:
        if active.is_procedural:
            gen = ctx.generated_missions.get(active.mission_id)
            if gen is not None:
                mission_type = gen.mission_type
        else:
            spec = find_mission(active.mission_id)
            mission_type = spec.mission_type
    except (KeyError, AttributeError):
        pass

    if mission_type is None:
        return

    deltas = _MISSION_REP_DELTAS.get(mission_type)
    if deltas is None:
        return

    for faction, delta in deltas.items():
        if is_early and delta > 0:
            bonus = (delta + 1) // 2   # ceil division = 50% rounded up
            delta = delta + bonus
        modify_rep(ctx, faction, delta)

