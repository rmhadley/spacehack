"""Mission runtime layer: lifecycle state + accept/deliver/complete/abort.

Missions live in two layers:

  * :mod:`spacehack.data.missions` - the static catalog (the
    :class:`MissionSpec` dataclass + per-faction ``MISSIONS`` tuples
    + :func:`find_mission` / :func:`missions_offered_by` lookup
    helpers). Adding a new mission is a one-file edit there.
  * Here (:class:`ActiveMission` + the four runtime functions
    below) - the BUSINESS LOGIC that operates on a :class:`MissionSpec`
    instance the player has accepted.

This module re-exports :class:`MissionSpec`, :func:`find_mission`,
and :func:`missions_offered_by` from :mod:`spacehack.data.missions`
so the dispatcher's ``mission_module.MissionSpec`` references keep
working without a second import line.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum, auto

from . import ship
from .data.missions import MissionSpec, find_mission, list_missions, missions_offered_by

MAX_ACTIVE_MISSIONS: int = 5


@dataclass
class MissionBoard:
    """Per-NPC mission offering state.

    Stored on :attr:`GameContext.mission_boards`, keyed by NPC id.
    Lazy-initialized on first NPC talk. Slots refill on month rollover.

    Attributes:
        npc_id: which NPC giver this board belongs to.
        slots: mission spec IDs or generated keys. ``None`` = empty slot.
        max_slots: how many missions this NPC can offer at once.
        last_refresh_month: game month when the board was last populated
            (0 = never populated). Used to prevent double-fill within
            the same month.
    """
    npc_id: str
    slots: list[str | None] = field(default_factory=list)
    max_slots: int = 5
    last_refresh_month: int = 0
    planet_id: str = ""  # which planet this board belongs to (for refresh context)


class MissionStatus(Enum):
    """Lifecycle state of an :class:`ActiveMission`."""

    IN_PROGRESS = auto()
    COMPLETED = auto()
    FAILED = auto()


@dataclass
class ActiveMission:
    """Mutable state of one player-accepted mission.

    Up to :data:`MAX_ACTIVE_MISSIONS` are tracked in
    :attr:`GameContext.player_active_missions`. Each holds a snapshot
    of delivery/reward/deadline fields so procedural missions don't
    need a catalog lookup at runtime.
    """

    mission_id: str
    is_procedural: bool = False
    status: MissionStatus = MissionStatus.IN_PROGRESS
    title: str = ""  # display title (snapshot from spec or generated)

    # Delivery fields
    required_cargo_size: int = 0
    delivery_target_npc_id: str | None = None
    delivery_target_planet_id: str | None = None

    # Bounty fields (future)
    bounty_spawn_id: str | None = None
    target_enemy_id: str | None = None
    target_system_id: str | None = None

    # Deadline
    time_deadline: tuple[int, int, int] | None = None  # (day, month, year)
    deadline_days: int = 0
    accept_day: int = 0  # absolute game day when accepted (for early-bonus calc)

    # Reward
    reward_credits: int = 0
    reward_xp: int = 0
    early_bonus_pct: int = 0


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


def is_deliverable_at(
    mission: MissionSpec,
    npc_id: str,
    planet_id: str,
) -> bool:
    """True iff ``mission`` can be handed over to NPC ``npc_id``
    while the player is on ``planet_id``.

    Also works with an :class:`ActiveMission`'s stored delivery fields
    for procedural missions — pass those as named args by unpacking.
    """
    if mission.required_cargo_size <= 0:
        return False
    if mission.delivery_target_npc_id is None:
        return False
    if mission.delivery_target_planet_id is None:
        return False
    return (
        mission.delivery_target_npc_id == npc_id
        and mission.delivery_target_planet_id == planet_id
    )


def active_is_deliverable_at(
    active: ActiveMission,
    npc_id: str,
    planet_id: str,
) -> bool:
    """Check if an :class:`ActiveMission` is deliverable at the given
    NPC+planet. Works for both static and procedural missions.

    For static missions, looks up the :class:`MissionSpec` for field values.
    For procedural missions, uses the fields stored on ``active`` directly.
    """
    if active.required_cargo_size <= 0:
        return False
    target_npc = active.delivery_target_npc_id
    target_planet = active.delivery_target_planet_id
    if target_npc is None or target_planet is None:
        return False
    return target_npc == npc_id and target_planet == planet_id


def find_deliverable(
    active_missions: list[ActiveMission],
    npc_id: str,
    planet_id: str,
) -> ActiveMission | None:
    """Return the first deliverable mission in ``active_missions``
    for the given NPC+planet, or ``None``.
    """
    for am in active_missions:
        if active_is_deliverable_at(am, npc_id, planet_id):
            return am
    return None


def find_deliverable_missions(
    active_missions: list[ActiveMission],
    npc_id: str,
    planet_id: str,
) -> list[ActiveMission]:
    """Return ALL deliverable missions for the given NPC+planet."""
    return [
        am for am in active_missions
        if active_is_deliverable_at(am, npc_id, planet_id)
    ]


def abort_mission(
    active: ActiveMission,
    owned_ship: object,
    log: object,
) -> None:
    """Drop the mission's cargo from ``owned_ship`` and log the release.

    Does NOT remove ``active`` from the mission list — the caller
    owns that bookkeeping.
    """
    if active.required_cargo_size <= 0 or owned_ship is None:
        return
    owned_ship.mission_reserved = max(
        0, owned_ship.mission_reserved - active.required_cargo_size,
    )
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
) -> None:
    """Complete ``active``: drop cargo, grant reward (with early/late
    modifiers), and log the payout.

    Does NOT remove ``active`` from the mission list or add to
    ``completed_mission_ids`` — the caller owns that bookkeeping.
    """
    # Drop cargo.
    if active.required_cargo_size > 0 and owned_ship is not None:
        owned_ship.mission_reserved = max(
            0, owned_ship.mission_reserved - active.required_cargo_size,
        )

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
            bonus_msg = " Late delivery — half pay."

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


def ensure_board(
    ctx, npc_id: str, max_slots: int = 5, planet_id: str = "",
) -> MissionBoard:
    """Get or create a :class:`MissionBoard` for ``npc_id``.

    If no board exists, creates one with ``max_slots`` empty slots
    and stores it in ``ctx.mission_boards``. Returns the existing
    board if one already exists.
    """
    if npc_id not in ctx.mission_boards:
        board = MissionBoard(
            npc_id=npc_id,
            slots=[None] * max_slots,
            max_slots=max_slots,
            planet_id=planet_id,
        )
        ctx.mission_boards[npc_id] = board
    return ctx.mission_boards[npc_id]


def board_offerings(
    board: MissionBoard,
    generated: dict[str, MissionSpec] | None = None,
) -> tuple[MissionSpec, ...]:
    """Return :class:`MissionSpec` objects for non-empty slots on
    ``board``. Checks the static catalog first, then falls back to
    ``generated`` (procedural missions). Skips slots whose ID is
    unresolvable in both registries.
    """
    if generated is None:
        generated = {}
    result: list[MissionSpec] = []
    for slot_id in board.slots:
        if slot_id is not None:
            try:
                result.append(find_mission(slot_id))
            except KeyError:
                gen = generated.get(slot_id)
                if gen is not None:
                    result.append(gen)
    return tuple(result)


def fill_empty_slots(
    board: MissionBoard,
    planet_tier: int,
    completed_ids: frozenset[str],
    active_ids: frozenset[str],
    planet_id: str,
    *,
    generated: dict[str, MissionSpec] | None = None,
    rng: random.Random | None = None,
) -> None:
    """Fill empty (None) slots on ``board`` with available missions.

    First evicts any slot whose ID is in ``completed_ids`` or
    ``active_ids`` (stale slots from completed/accepted missions).
    Then fills the resulting empties with static missions first,
    using :func:`missions_offered_by` for the pool. Remaining empty
    slots are filled with procedurally-generated delivery missions.

    Generated missions are stored in ``generated`` (typically
    ``ctx.generated_missions``) so :func:`board_offerings` can
    resolve them later.
    """
    if generated is None:
        generated = {}
    if rng is None:
        from .engine import RNG
        rng = RNG

    # Evict completed/active missions from board slots.
    for i in range(len(board.slots)):
        _sid = board.slots[i]
        if _sid is not None and (_sid in completed_ids or _sid in active_ids):
            board.slots[i] = None

    available = missions_offered_by(
        board.npc_id,
        planet_tier=planet_tier,
        completed_ids=completed_ids,
        active_ids=active_ids,
        planet_id=planet_id,
    )
    available_ids = [m.id for m in available]
    # Track which IDs are already on the board to avoid duplicates.
    existing = set(s for s in board.slots if s is not None)
    for i in range(len(board.slots)):
        if board.slots[i] is None and available_ids:
            for mid in available_ids:
                if mid not in existing:
                    board.slots[i] = mid
                    existing.add(mid)
                    break

    # Fill remaining empty slots with procedural delivery missions.
    _proc_counter = 0
    for i in range(len(board.slots)):
        if board.slots[i] is not None:
            continue
        _proc = generate_delivery_mission(
            origin_planet_id=planet_id,
            max_tier=planet_tier,
            rng=rng,
            counter=_proc_counter,
            giver_npc_id=board.npc_id,
        )
        if _proc is not None:
            generated[_proc.id] = _proc
            board.slots[i] = _proc.id
            existing.add(_proc.id)
            _proc_counter += 1


def board_remove(board: MissionBoard, mission_id: str) -> None:
    """Remove ``mission_id`` from ``board.slots`` (set to None).
    No-op if the ID isn't on the board.
    """
    for i in range(len(board.slots)):
        if board.slots[i] == mission_id:
            board.slots[i] = None
            return


def board_return_static(board: MissionBoard, mission_id: str) -> None:
    """Return a static mission ID to the first empty slot on
    ``board``. If no empty slot exists, bumps the last slot to
    make room (the bumped mission goes back into the candidate pool
    for future fills).
    """
    for i in range(len(board.slots)):
        if board.slots[i] is None:
            board.slots[i] = mission_id
            return
    # Board is full — bump the last slot to make room.
    board.slots[-1] = mission_id


def refresh_all_boards(ctx) -> None:
    """Called on month rollover. Fills empty slots on all boards.

    Uses each board's stored ``planet_id`` to compute tier filtering.
    Skips boards whose ``last_refresh_month`` matches the current month
    (already refreshed this month).
    """
    from .engine import RNG
    active_ids = frozenset(m.mission_id for m in ctx.player_active_missions)
    completed_ids = frozenset(ctx.completed_mission_ids)

    for board in ctx.mission_boards.values():
        if board.last_refresh_month == ctx.time_month:
            continue
        # Resolve planet tier from stored planet_id.
        _tier = 1
        if board.planet_id:
            try:
                from .data.planets import find_planet_spec as _fps
                _tier = _fps(board.planet_id).mission_tier
            except KeyError:
                pass
        fill_empty_slots(
            board,
            planet_tier=_tier,
            completed_ids=completed_ids,
            active_ids=active_ids,
            planet_id=board.planet_id,
            generated=ctx.generated_missions,
            rng=RNG,
        )
        board.last_refresh_month = ctx.time_month


# ---------------------------------------------------------------------------
# Procedural delivery mission generator
# ---------------------------------------------------------------------------

# Cached planet_id → system_id mapping. Built lazily on first call to
# _planet_to_system() from the solar system registry.
_PLANET_SYSTEM_CACHE: dict[str, str] | None = None


def _planet_to_system() -> dict[str, str]:
    """Return ``{planet_id: system_id}`` for every planet (and station
    city_planet_id) across all registered solar systems.

    Lazy-built and cached so procedural generation doesn't re-scan the
    system registry on every call.
    """
    global _PLANET_SYSTEM_CACHE
    if _PLANET_SYSTEM_CACHE is not None:
        return _PLANET_SYSTEM_CACHE

    from .data import solar_systems as _sys_mod
    mapping: dict[str, str] = {}
    for _sys in _sys_mod.list_solar_systems():
        for _p in _sys.planets:
            if not getattr(_p, 'sun', False):
                mapping[_p.id] = _sys.id
        # Stations with city_planet_id share the same system.
        for _st in getattr(_sys, 'stations', ()) or ():
            if _st.city_planet_id:
                mapping[_st.city_planet_id] = _sys.id
    _PLANET_SYSTEM_CACHE = mapping
    return mapping


def _planet_npc_ids(planet_id: str) -> list[str]:
    """Return the NPC IDs present on ``planet_id`` (non-empty npc_ids
    from the planet's building specs).

    Used to pick a delivery target NPC for procedural missions.
    Returns empty list if the planet is unknown or has no NPC buildings.
    """
    try:
        from .data.planets import find_planet_spec as _fps
        spec = _fps(planet_id)
    except KeyError:
        return []
    return [b.npc_id for b in spec.buildings if b.npc_id]


def _dest_candidates_in_system(
    system_id: str,
    origin_planet_id: str,
    hops: int,
) -> list[tuple[str, str, int]]:
    """Return ``[(planet_id, system_id, hops), ...]`` for every
    landable planet (or station city_planet_id) in ``system_id``
    that is not ``origin_planet_id`` and has at least one NPC.

    Handles both same-system and remote-system destination lookup
    with a single code path.
    """
    from .data.planets import has_landable_port
    from .data import solar_systems as _sys_mod

    try:
        _sys = _sys_mod.find_solar_system(system_id)
    except KeyError:
        return []

    result: list[tuple[str, str, int]] = []
    # Planets.
    for _p in _sys.planets:
        if getattr(_p, 'sun', False):
            continue
        if _p.id == origin_planet_id:
            continue
        if not has_landable_port(_p.id):
            continue
        if not _planet_npc_ids(_p.id):
            continue
        result.append((_p.id, system_id, hops))
    # Stations (city_planet_id points to the planet spec).
    for _st in getattr(_sys, 'stations', ()) or ():
        if _st.city_planet_id == origin_planet_id:
            continue
        if not _st.city_planet_id:
            continue
        if not has_landable_port(_st.city_planet_id):
            continue
        if not _planet_npc_ids(_st.city_planet_id):
            continue
        result.append((_st.city_planet_id, system_id, hops))
    return result


def generate_delivery_mission(
    origin_planet_id: str,
    max_tier: int,
    rng: random.Random,
    counter: int = 0,
    giver_npc_id: str = "",
) -> MissionSpec | None:
    """Generate one procedural delivery mission originating from
    ``origin_planet_id``.

    Algorithm:
      1. Roll tier: weighted 1..max_tier using min-of-two-rolls.
      2. Find the origin system, then filter reachable systems by
         tier-appropriate jump range (via BFS hop count).
      3. Pick a destination planet in a different system with a
         landable port and at least one NPC.
      4. Generate cargo, deadline, and reward scaled by tier + distance.

    Returns ``None`` if no suitable destination planet can be found
    (e.g. isolated system with no jump gates, or no NPCs on any
    reachable planet).

    Args:
        origin_planet_id: planet registry key (e.g. ``"earth"``).
        max_tier: planet's ``mission_tier`` — caps the rolled tier.
        rng: shared :data:`engine.RNG` for deterministic generation.
        counter: unique per-fill counter appended to the generated ID.
    """
    from .data.solar_systems import reachable_system_ids

    # 1. Weighted tier roll: min-of-two gives a natural rarity curve.
    _max = max(1, max_tier)
    tier = min(rng.randint(1, _max), rng.randint(1, _max))

    # 2. Resolve origin system and reachable systems.
    p2s = _planet_to_system()
    origin_system_id = p2s.get(origin_planet_id)
    if origin_system_id is None:
        return None

    reachable = reachable_system_ids(origin_system_id, max_hops=10)

    # Tier → hop range: same-system deliveries are allowed for tier 1.
    _hop_ranges = {
        1: (0, 1),   # same system or neighbor
        2: (1, 2),   # regional
        3: (2, 4),   # sector
        4: (3, 6),   # frontier
    }
    min_hops, max_hops = _hop_ranges.get(tier, (0, 10))

    # Build candidate (system_id, hop_count) pairs.
    _candidates: list[tuple[str, int]] = []
    if min_hops == 0:
        # Include same-system destinations (hop count 0).
        _candidates.append((origin_system_id, 0))
    for sys_id, hops in reachable.items():
        if min_hops <= hops <= max_hops:
            _candidates.append((sys_id, hops))

    if not _candidates:
        return None

    # 3. Collect all landable planets (excl. origin) in candidate
    #    systems, with at least one NPC. Uses a shared helper so
    #    same-system and different-system enumeration share one path.
    _dest_candidates: list[tuple[str, str, int]] = []  # (planet_id, system_id, hops)
    for cand_sys_id, hops in _candidates:
        _dest_candidates.extend(
            _dest_candidates_in_system(cand_sys_id, origin_planet_id, hops),
        )

    if not _dest_candidates:
        return None

    dest_planet_id, dest_system_id, hops = rng.choice(_dest_candidates)

    # 4. Pick a delivery target NPC on the destination planet.
    npc_ids = _planet_npc_ids(dest_planet_id)
    target_npc_id = rng.choice(npc_ids) if npc_ids else None

    # 5. Cargo amount, scaled by tier.
    _cargo_ranges = {1: (5, 10), 2: (10, 20), 3: (20, 40), 4: (40, 60)}
    cargo_lo, cargo_hi = _cargo_ranges.get(tier, (5, 10))
    cargo = rng.randint(cargo_lo, cargo_hi)

    # 6. Deadline: 4 days per hop + random 2-6 days.
    deadline = max(3, hops * 4 + rng.randint(2, 6))

    # 7. Reward: credits = cargo * 10 * tier, xp = cargo * 2 * tier.
    credits = cargo * 10 * tier
    xp = cargo * 2 * tier

    # 8. Generated ID: unique per run, deterministic from RNG state.
    gen_id = f"proc_delivery_{origin_planet_id}_{dest_planet_id}_{counter}_{tier}"

    # 9. Construct display title and description.
    try:
        from .data.planets import find_planet_spec as _fps_dest
        dest_name = _fps_dest(dest_planet_id).name
    except KeyError:
        dest_name = dest_planet_id

    try:
        from .data.planets import find_planet_spec as _fps_origin
        origin_name = _fps_origin(origin_planet_id).name
    except KeyError:
        origin_name = origin_planet_id

    title = f"Delivery: {origin_name} \u2192 {dest_name}"
    # Build a simple description mentioning cargo and jumps.
    _hop_desc = "same system" if hops == 0 else f"{hops} jump(s)"
    description = (
        f"A {cargo}-unit cargo shipment from {origin_name} to "
        f"{dest_name}. ({_hop_desc}, tier {tier})."
    )

    # 10. Determine faction + giver NPC from the board.
    # For procedural missions, we use the board's NPC id as giver.
    # The faction defaults to "merchants" for delivery missions.
    # These fields are filled in by the caller based on the board.

    return MissionSpec(
        id=gen_id,
        title=title,
        description=description,
        giver_npc_id=giver_npc_id,
        faction="merchants",
        mission_type="delivery",
        tier=tier,
        reward_credits=credits,
        reward_xp=xp,
        deadline_days=deadline,
        early_bonus_pct=25,
        required_cargo_size=cargo,
        delivery_target_npc_id=target_npc_id,
        delivery_target_planet_id=dest_planet_id,
        origin_planet_id=origin_planet_id,
    )


# Re-exports so consumers can keep using ``mission_module.MissionSpec``
# etc. without a second import line.
__all__ = [
    "ActiveMission",
    "MissionSpec",
    "MissionStatus",
    "MAX_ACTIVE_MISSIONS",
    "abort_mission",
    "active_is_deliverable_at",
    "commit_accept_mission",
    "complete_mission",
    "find_mission",
    "find_deliverable",
    "find_deliverable_missions",
    "is_deliverable_at",
    "list_missions",
    "missions_offered_by",
    "try_accept_mission",
    "ensure_board",
    "board_offerings",
    "fill_empty_slots",
    "board_remove",
    "board_return_static",
    "refresh_all_boards",
    "generate_delivery_mission",
    "_planet_npc_ids",
    "_planet_to_system",
]
