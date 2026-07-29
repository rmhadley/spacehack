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


def board_offerings(board: MissionBoard) -> tuple[MissionSpec, ...]:
    """Return :class:`MissionSpec` objects for non-empty slots on
    ``board``. Skips slots whose mission ID is no longer in the
    catalog (e.g. procedural missions from a previous session).
    """
    result: list[MissionSpec] = []
    for slot_id in board.slots:
        if slot_id is not None:
            try:
                result.append(find_mission(slot_id))
            except KeyError:
                pass
    return tuple(result)


def fill_empty_slots(
    board: MissionBoard,
    planet_tier: int,
    completed_ids: frozenset[str],
    active_ids: frozenset[str],
    planet_id: str,
) -> None:
    """Fill empty (None) slots on ``board`` with available missions.

    First evicts any slot whose ID is in ``completed_ids`` or
    ``active_ids`` (stale slots from completed/accepted missions).
    Then fills the resulting empties with static missions first,
    using :func:`missions_offered_by` for the pool.
    """
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
        )
        board.last_refresh_month = ctx.time_month


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
]
