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

import dataclasses
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

    # Bounty fields
    bounty_spawn_id: str | None = None
    target_enemy_id: str | None = None
    target_system_id: str | None = None
    bounty_target_name: str | None = None
    bounty_target_squad_size: int = 1
    bounty_target_loadout_pct: int = 0
    bounty_wingmate_enemy_id: str | None = None  # mixed squad: wingmate ship type (e.g. pirate escort)
    tier: int = 1

    # Intercept fields
    heist_target_good_id: str | None = None
    heist_good_secured: bool = False  # True once the mission's loot is secured in the hold

    # Salvage fields
    salvage_wreck_enemy_id: str | None = None  # derelict spec for the boarded wreck
    salvage_layout_id: str | None = None       # interior layout id for the wreck
    salvage_wreck_spawn_id: str | None = None  # BountySpawn id of the wreck (interior cache key + lifecycle)

    # Smuggling fields
    is_smuggle: bool = False       # cargo is hot — militia scans can confiscate it
    smuggle_good_id: str | None = None  # flavor good id for quest log display

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
    *,
    owned_ship: object | None = None,
) -> bool:
    """Check if an :class:`ActiveMission` is deliverable at the given
    NPC+planet. Works for both static and procedural missions.

    For static missions, looks up the :class:`MissionSpec` for field values.
    For procedural missions, uses the fields stored on ``active`` directly.

    Intercept missions (``heist_target_good_id`` set) are deliverable
    when the NPC/planet match AND the player has the looted good in
    their ship inventory.
    """
    _heist_good = getattr(active, 'heist_target_good_id', None)

    # Intercept path: requires the mission's loot to be SECURED.
    # The flag is set only by securing the mission-specific loot
    # entity — buying the same good at a trade terminal does NOT
    # count (design doc open question #6).
    if _heist_good is not None:
        target_npc = active.delivery_target_npc_id
        target_planet = active.delivery_target_planet_id
        if target_npc != npc_id or target_planet != planet_id:
            return False
        return getattr(active, 'heist_good_secured', False)

    # Standard delivery path: must have reserved cargo.
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
    *,
    owned_ship: object | None = None,
) -> ActiveMission | None:
    """Return the first deliverable mission in ``active_missions``
    for the given NPC+planet, or ``None``.
    """
    for am in active_missions:
        if active_is_deliverable_at(am, npc_id, planet_id, owned_ship=owned_ship):
            return am
    return None


def find_deliverable_missions(
    active_missions: list[ActiveMission],
    npc_id: str,
    planet_id: str,
    *,
    owned_ship: object | None = None,
) -> list[ActiveMission]:
    """Return ALL deliverable missions for the given NPC+planet."""
    return [
        am for am in active_missions
        if active_is_deliverable_at(am, npc_id, planet_id, owned_ship=owned_ship)
    ]


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
        from .data.trade_goods import find_trade_good as _ftg
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

    # --- XP gain ---
    if ctx is not None and xp > 0:
        from .xp import add_xp
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
    from .faction import modify_rep, _MISSION_REP_DELTAS

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


def mission_spec_from_dict(raw: dict) -> MissionSpec:
    """Rebuild a :class:`MissionSpec` from a serialized dict.

    Save/load flattens procedural missions (stored in
    ``ctx.generated_missions``) into plain dicts via ``_d()``.
    This reconstructs the frozen dataclass so mission-board
    rendering (``_mission_type_tag`` reads fields like
    ``salvage_wreck_enemy_id``) and rep/XP resolution get real
    MissionSpec objects after a Continue. Unknown keys are
    ignored; missing keys fall back to the dataclass defaults.
    """
    _kwargs = {
        _f.name: raw[_f.name]
        for _f in dataclasses.fields(MissionSpec)
        if _f.name in raw
    }
    return MissionSpec(**_kwargs)


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
    ctx = None,
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
    rng.shuffle(available_ids)
    # Track which IDs are already on the board to avoid duplicates.
    existing = set(s for s in board.slots if s is not None)
    for i in range(len(board.slots)):
        if board.slots[i] is None and available_ids:
            for mid in available_ids:
                if mid not in existing:
                    board.slots[i] = mid
                    existing.add(mid)
                    break

    # Resolve guild for procedural generation dispatch.
    _guild = ""
    try:
        from .data.npcs import find_npc as _fnpc
        _guild = _fnpc(board.npc_id).guild
    except KeyError:
        pass

    # Table-driven dispatch: guild → procedural generator function.
    _PROCEDURAL_GENERATORS = {
        "merchants": generate_delivery_mission,
        "bhguild": generate_bounty_mission,
        "bar": generate_bar_mission,
    }
    _generator_fn = _PROCEDURAL_GENERATORS.get(_guild)
    if _generator_fn is None:
        return  # no procedural missions for this guild

    # --- Faction reputation: pay scaling only (never gates access) ---
    # Every guild offers missions at any reputation; standing only
    # adjusts pay (disliked -15%, liked +10%, allied +20%). The hard
    # gates (enemy refusal, tier cuts) were removed by design.
    _pay_pct = 0
    if ctx is not None:
        from .faction import guild_to_faction, adjust_reward_pct, get_attitude
        _board_faction = guild_to_faction(_guild)
        _board_rep = ctx.faction_reputation.get(_board_faction, 0)
        _board_attitude = get_attitude(_board_rep)
        _pay_pct = adjust_reward_pct(_board_attitude)

    # Fill remaining empty slots with procedural missions.
    _proc_counter = 0
    for i in range(len(board.slots)):
        if board.slots[i] is not None:
            continue
        _proc = _generator_fn(
            origin_planet_id=planet_id,
            max_tier=planet_tier,
            rng=rng,
            counter=_proc_counter,
            giver_npc_id=board.npc_id,
        )
        if _proc is not None:
            # Apply faction attitude pay scaling (never blocks the mission).
            if _pay_pct != 0:
                _proc = dataclasses.replace(
                    _proc,
                    reward_credits=max(1, _proc.reward_credits * (100 + _pay_pct) // 100),
                )
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
            ctx=ctx,
        )
        board.last_refresh_month = ctx.time_month


# ---------------------------------------------------------------------------
# Procedural delivery mission generator
# ---------------------------------------------------------------------------

# Cached planet_id → system_id mapping. Built lazily on first call to
# _planet_to_system() from the solar system registry.
_PLANET_SYSTEM_CACHE: dict[str, str] | None = None


def _roll_tier(max_tier: int, rng: random.Random) -> int:
    """Weighted tier roll: min-of-two gives a natural rarity curve.

    Shared by both delivery and bounty procedural generators.
    Returns 1..max_tier with lower tiers more common.
    """
    _max = max(1, max_tier)
    return min(rng.randint(1, _max), rng.randint(1, _max))


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

    # 1. Weighted tier roll.
    tier = _roll_tier(max_tier, rng)

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

    # 6. Deadline: ~30 days per hop for comfortable travel.
    #    All solar systems are 200x140 cells. Crossing one from gate to gate
    #    takes ~180 moves = 18 days at speed 10. A multi-hop journey also
    #    includes launch-area transit + local destination transit (~2 extra
    #    systems of travel). Formula: hops * 30 + random(10-20) gives roughly
    #    2-3x the actual travel time for slow ships.
    deadline = max(20, hops * 30 + rng.randint(10, 20))

    # 7. Reward: credits scale by cargo * 5 * (tier + 1) so tier ranges
    #    match the design doc: T1 50-100, T2 150-300, T3 400-800, T4 1000-1500.
    credits = cargo * 5 * (tier + 1)
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


# ---------------------------------------------------------------------------
# Procedural bounty mission generator
# ---------------------------------------------------------------------------

_BOUNTY_ADJECTIVES: tuple[str, ...] = (
    "Crimson", "Shadow", "Iron", "Silver", "Black", "Red",
    "Void", "Ghost", "Rust", "Bone", "Ash", "Frost",
    "Storm", "Venom", "Blade", "Fang", "Claw", "Wraith",
    "Dusk", "Blazing", "Rogue", "Savage", "Bleeding", "Obsidian",
    "Scorch", "Drift", "Hollow", "Broken", "Silent", "Grim",
    "Vile", "Pale", "Dead", "Cold", "Grave", "Midnight",
    "Scarred", "Jagged", "Shade", "Spectral", "Cursed", "Slate",
    "Thunder", "Onyx", "Deep", "Feral", "Plague", "Wild",
    "Bitter", "Bleak", "Blind", "Bloody", "Blunt", "Brass",
    "Brazen", "Burning", "Charred", "Chrome", "Copper", "Corroded",
    "Cracked", "Crude", "Dread", "Drowned", "Dusty", "Fallen",
    "Fiery", "Flaming", "Forged", "Fractured", "Frozen", "Fuming",
    "Gilded", "Glassy", "Gleaming", "Gloom", "Glowing", "Golden",
    "Granite", "Haunted", "Howling", "Hungry", "Hushed", "Icy",
    "Keen", "Lethal", "Livid", "Lonely", "Meridian", "Molten",
    "Mortal", "Nocturnal", "Quick", "Reckless", "Restless", "Rusted",
)

_BOUNTY_FIRST_NAMES: tuple[str, ...] = (
    "Jack", "Kai", "Nova", "Rex", "Vex", "Zara",
    "Finn", "Mira", "Cole", "Sera", "Jax", "Vega",
    "Lyra", "Kira", "Zane", "Rook", "Tessa", "Orin",
    "Cora", "Dax", "Luna", "Rhea", "Thane", "Arya",
    "Kael", "Nyla", "Talon", "Sasha", "Remy", "Jett",
    "Quinn", "Phoenix", "River", "Sky", "Echo", "Sparrow",
    "Raven", "Storm", "Blaze", "Jinx", "Sol", "Wren",
    "Vesper", "Flint", "Ridge", "Vale", "Mara", "Toren",
    "Shae", "Elyse", "Doran", "Kestrel", "Nyx", "Korra",
    "Alden", "Astra", "Bex", "Briar", "Calyx", "Cass",
    "Cinder", "Cypher", "Dash", "Dove", "Draven", "Dune",
    "Elara", "Ember", "Faye", "Gage", "Galen", "Garnet",
    "Harlow", "Haven", "Iris", "Ivory", "Jade", "Jorah",
    "Kaida", "Lark", "Lira", "Lorn", "Mace", "Maren",
    "Maven", "Nash", "Niam", "Oren", "Orion",
    "Palen", "Pax", "Rayne", "Reed", "Riven", "Rowan",
    "Ryan", "Salem", "Soren", "Sylvan", "Torin", "Vance",
)



def _generate_bounty_name(rng: random.Random) -> str:
    """Generate a bounty target name like "Crimson Jack".

    Picks a random adjective + first name from large flat pools
    (96 adjectives × 107 first names = 10,272 possible combos).
    """
    _adj = rng.choice(_BOUNTY_ADJECTIVES)
    _fn = rng.choice(_BOUNTY_FIRST_NAMES)
    return f"{_adj} {_fn}"


def _bounty_enemy_pool(tier: int) -> list[str]:
    """Return eligible NpcShipSpec IDs for a bounty of the given tier."""
    _pools: dict[int, list[str]] = {
        1: ["pirate_scout"],
        2: ["pirate_scout", "pirate_raider"],
        3: ["pirate_raider"],
        4: ["pirate_raider", "pirate_captain"],
    }
    return _pools.get(max(1, min(4, tier)), ["pirate_scout"])


def _bounty_loadout_range(tier: int) -> tuple[int, int]:
    """Return (min_pct, max_pct) for loadout scaling by tier."""
    return {
        1: (0, 25),
        2: (25, 50),
        3: (50, 75),
        4: (75, 100),
    }.get(max(1, min(4, tier)), (0, 25))


def _bounty_squad_range(tier: int) -> tuple[int, int]:
    """Return (min_squad, max_squad) by tier."""
    return {
        1: (1, 1),
        2: (1, 1),
        3: (1, 2),
        4: (2, 3),
    }.get(max(1, min(4, tier)), (1, 1))


def _bounty_danger_text(tier: int, squad_size: int) -> str:
    """Return a danger-level label for mission descriptions.

    Based purely on tier so the label always matches the mission's
    reward tier (which already scales with squad size internally).
    """
    if tier >= 4:
        return "Extreme"
    if tier >= 3:
        return "High"
    if tier >= 2:
        return "Moderate"
    return "Low"


def generate_bounty_mission(
    origin_planet_id: str,
    max_tier: int,
    rng: random.Random,
    counter: int = 0,
    giver_npc_id: str = "",
) -> MissionSpec | None:
    """Generate one procedural bounty mission originating from
    ``origin_planet_id``.

    Algorithm:
      1. Roll tier: weighted 1..max_tier using min-of-two-rolls.
      2. Find origin system and reachable systems (reuses hop-range
         pattern from delivery generation).
      3. Pick a target system via hop-range gating tuned for bounty
         distances (longer ranges than delivery).
      4. Pick enemy from tier-appropriate pool.
      5. Roll loadout_pct and squad_size within tier ranges.
      6. Generate name via tier-gated prefix/title pools.
      7. Compute reward: base = hull_strength × tier × 40, adjusted
         by squad size.
      8. Compute deadline: max(20, hops × 35 + randint(10, 25)) — accounts for
         200×140 system size (~18 days per crossing at speed 10).
      9. Build MissionSpec with mission_type="bounty", faction="bhguild".

    Returns ``None`` if no suitable target system can be found.
    """
    from .data.solar_systems import reachable_system_ids
    from .data.npc_ships import find_npc_ship
    from .data.ships import find_ship as _find_ship_cat

    # 1. Tier roll (shared two-roll pattern for rarity curve).
    tier = _roll_tier(max_tier, rng)

    # 2. Resolve origin system and reachable systems.
    p2s = _planet_to_system()
    origin_system_id = p2s.get(origin_planet_id)
    if origin_system_id is None:
        return None

    reachable = reachable_system_ids(origin_system_id, max_hops=10)

    # Bounty hop ranges: slightly longer than delivery.
    _hop_ranges = {
        1: (1, 2),
        2: (1, 3),
        3: (2, 5),
        4: (3, 7),
    }
    min_hops, max_hops = _hop_ranges.get(tier, (1, 10))

    # Build candidate system list.
    _candidates: list[tuple[str, int]] = []
    for sys_id, hops in reachable.items():
        if min_hops <= hops <= max_hops and sys_id != origin_system_id:
            _candidates.append((sys_id, hops))

    if not _candidates:
        return None

    # 3. Pick a target system.
    target_system_id, hops = rng.choice(_candidates)

    # 4. Pick enemy from tier-appropriate pool.
    _pool = _bounty_enemy_pool(tier)
    enemy_id = rng.choice(_pool)
    try:
        _espec = find_npc_ship(enemy_id)
        _ship_cat = _find_ship_cat(_espec.ship_id)
        _hull_strength = _ship_cat.base_hull
    except (KeyError, ImportError):
        _hull_strength = 50

    # 5. Roll loadout and squad.
    _lo_lo, _lo_hi = _bounty_loadout_range(tier)
    loadout_pct = rng.randint(_lo_lo, _lo_hi)
    _sq_lo, _sq_hi = _bounty_squad_range(tier)
    squad_size = rng.randint(_sq_lo, _sq_hi)

    # 6. Generate name.
    target_name = _generate_bounty_name(rng)

    # 7. Reward: base = hull_strength × tier × 40, × squad multiplier.
    _sq_mult = {1: 1.0, 2: 1.5, 3: 2.0}.get(squad_size, 1.0)
    credits = int(_hull_strength * tier * 40 * _sq_mult)
    xp = int(_hull_strength * tier * 2 * _sq_mult)

    # 8. Deadline: ~35 days per hop so travel + hunting fits comfortably.
    #    All solar systems are 200x140 cells. Crossing one from gate to gate
    #    takes ~180 moves = 18 days at speed 10. Bounties get a slightly
    #    more generous multiplier than deliveries to account for local
    #    searching and combat (even though combat is "free", the hunt
    #    before engagement can add crossing time).
    deadline = max(20, hops * 35 + rng.randint(10, 25))

    # 9. Danger text + description.
    _danger = _bounty_danger_text(tier, squad_size)
    try:
        from .data.planets import find_planet_spec as _fps_origin
        origin_name = _fps_origin(origin_planet_id).name
    except KeyError:
        origin_name = origin_planet_id

    title = f"Wanted: {target_name}"
    _squad_note = f" + {squad_size - 1} wingmates" if squad_size > 1 else ""
    _loadout_note = " (heavy loadout)" if loadout_pct >= 75 else ""
    description = (
        f"The Bounty Guild on {origin_name} seeks {target_name}, "
        f"last seen {hops} jump(s) away. "
        f"Danger: {_danger}.{_squad_note}{_loadout_note}"
    )

    # 10. Generated ID.
    gen_id = f"proc_bounty_{origin_planet_id}_{target_system_id}_{enemy_id}_{counter}_{tier}"

    return MissionSpec(
        id=gen_id,
        title=title,
        description=description,
        giver_npc_id=giver_npc_id,
        faction="bhguild",
        mission_type="bounty",
        tier=tier,
        reward_credits=credits,
        reward_xp=xp,
        deadline_days=deadline,
        early_bonus_pct=30,
        target_enemy_id=enemy_id,
        target_system_id=target_system_id,
        bounty_target_name=target_name,
        bounty_target_squad_size=squad_size,
        bounty_target_loadout_pct=loadout_pct,
        origin_planet_id=origin_planet_id,
    )



# ---------------------------------------------------------------------------
# Procedural bar mission generator
# ---------------------------------------------------------------------------

# Heist goods pool — trade good IDs used as intercept loot / salvage components.
_HEIST_GOODS: tuple[str, ...] = (
    "electronics", "machine_parts", "luxury_goods", "fuel_cells",
)

# Merchant ship pool by tier (intercept targets).
_MERCHANT_POOLS: dict[int, list[str]] = {
    1: ["merchant_hauler"],
    2: ["merchant_hauler"],
    3: ["merchant_freighter"],
    4: ["merchant_caravan"],
}

# Pirate patrol pool by tier (salvage guards).
_PATROL_POOLS: dict[int, list[str]] = {
    1: ["pirate_scout"],
    2: ["pirate_scout"],
    3: ["pirate_raider"],
    4: ["pirate_raider", "pirate_captain"],
}

# Wreck + layout by tier (salvage boarding).
_WRECK_LAYOUTS: dict[int, tuple[str, str]] = {
    1: ("derelict_scout", "scout_a"),
    2: ("derelict_scout", "scout_a"),
    3: ("derelict_freighter", "freightliner_a"),
    4: ("derelict_freighter", "freightliner_a"),
}

# Hop-range tables for bar mission types.
_INTERCEPT_HOP_RANGES: dict[int, tuple[int, int]] = {
    1: (1, 2), 2: (1, 3), 3: (2, 5), 4: (3, 7),
}
_SMUGGLE_HOP_RANGES: dict[int, tuple[int, int]] = {
    1: (0, 1), 2: (1, 2), 3: (2, 4), 4: (3, 6),
}
_SALVAGE_HOP_RANGES: dict[int, tuple[int, int]] = {
    1: (1, 2), 2: (1, 3), 3: (2, 5), 4: (3, 7),
}


def _generate_bar_intercept(
    origin_planet_id: str,
    tier: int,
    rng: random.Random,
    counter: int,
    giver_npc_id: str,
) -> MissionSpec | None:
    """Generate a procedural intercept (merchant hunting) bar mission."""
    from .data.solar_systems import reachable_system_ids

    p2s = _planet_to_system()
    origin_system_id = p2s.get(origin_planet_id)
    if origin_system_id is None:
        return None

    reachable = reachable_system_ids(origin_system_id, max_hops=10)
    min_hops, max_hops = _INTERCEPT_HOP_RANGES.get(tier, (1, 10))

    _candidates = [
        (sid, h) for sid, h in reachable.items()
        if min_hops <= h <= max_hops and sid != origin_system_id
    ]
    if not _candidates:
        return None

    target_system_id, hops = rng.choice(_candidates)

    # Pick merchant ship + heist good.
    _pool = _MERCHANT_POOLS.get(tier, ["merchant_hauler"])
    enemy_id = rng.choice(_pool)
    heist_good = rng.choice(_HEIST_GOODS)

    # Squad: escorts at T2+.
    squad_size = 1
    wingmate_id = None
    if tier >= 2:
        squad_size = rng.randint(1, min(tier, 3))
        if squad_size > 1:
            wingmate_id = "pirate_scout" if tier <= 3 else "pirate_raider"

    # Round-trip deadline (travel both ways).
    deadline = max(30, hops * 60 + rng.randint(10, 30))

    # Reward.
    credits = tier * 200 + hops * 50
    xp = tier * 40 + hops * 10

    try:
        from .data.npc_ships import find_npc_ship
        enemy_name = find_npc_ship(enemy_id).name
    except KeyError:
        enemy_name = enemy_id

    gen_id = f"proc_intercept_{origin_planet_id}_{target_system_id}_{counter}_{tier}"
    title = f"Intercept: {enemy_name}"
    _escort_note = f" ({squad_size - 1} escorts)" if squad_size > 1 else ""
    description = (
        f"Ambush a {enemy_name}{_escort_note} hauling {heist_good} "
        f"{hops} jump(s) away. Return the cargo to the bar."
    )

    return MissionSpec(
        id=gen_id,
        title=title,
        description=description,
        giver_npc_id=giver_npc_id,
        faction="bar",
        mission_type="intercept",
        tier=tier,
        reward_credits=credits,
        reward_xp=xp,
        deadline_days=deadline,
        early_bonus_pct=25,
        target_enemy_id=enemy_id,
        target_system_id=target_system_id,
        bounty_target_squad_size=squad_size,
        bounty_wingmate_enemy_id=wingmate_id,
        heist_target_good_id=heist_good,
        origin_planet_id=origin_planet_id,
    )


def _generate_bar_smuggling(
    origin_planet_id: str,
    tier: int,
    rng: random.Random,
    counter: int,
    giver_npc_id: str,
) -> MissionSpec | None:
    """Generate a procedural smuggling (contraband delivery) bar mission."""
    from .data.solar_systems import reachable_system_ids

    p2s = _planet_to_system()
    origin_system_id = p2s.get(origin_planet_id)
    if origin_system_id is None:
        return None

    reachable = reachable_system_ids(origin_system_id, max_hops=10)
    min_hops, max_hops = _SMUGGLE_HOP_RANGES.get(tier, (0, 10))

    # Collect destination candidates (same pattern as delivery).
    _dest_candidates: list[tuple[str, str, int]] = []
    if min_hops == 0:
        _dest_candidates.extend(
            _dest_candidates_in_system(origin_system_id, origin_planet_id, 0),
        )
    for sys_id, hops in reachable.items():
        if min_hops <= hops <= max_hops:
            _dest_candidates.extend(
                _dest_candidates_in_system(sys_id, origin_planet_id, hops),
            )

    if not _dest_candidates:
        return None

    dest_planet_id, _dest_sys_id, hops = rng.choice(_dest_candidates)
    npc_ids = _planet_npc_ids(dest_planet_id)
    target_npc_id = rng.choice(npc_ids) if npc_ids else None

    # Cargo and rewards.
    _cargo_ranges = {1: (5, 10), 2: (10, 20), 3: (20, 40), 4: (40, 60)}
    cargo_lo, cargo_hi = _cargo_ranges.get(tier, (5, 10))
    cargo = rng.randint(cargo_lo, cargo_hi)

    credits = cargo * 4 * (tier + 1)
    xp = cargo * tier
    deadline = max(20, hops * 30 + rng.randint(10, 20))

    smuggle_good = rng.choice(_HEIST_GOODS)

    try:
        from .data.planets import find_planet_spec
        dest_name = find_planet_spec(dest_planet_id).name
    except KeyError:
        dest_name = dest_planet_id

    gen_id = f"proc_smuggle_{origin_planet_id}_{dest_planet_id}_{counter}_{tier}"
    title = f"Smuggle: {dest_name}"
    description = (
        f"Move {cargo} units of contraband to {dest_name} "
        f"({hops} jump(s)). Militia scans are a risk."
    )

    return MissionSpec(
        id=gen_id,
        title=title,
        description=description,
        giver_npc_id=giver_npc_id,
        faction="bar",
        mission_type="smuggling",
        tier=tier,
        reward_credits=credits,
        reward_xp=xp,
        deadline_days=deadline,
        early_bonus_pct=25,
        required_cargo_size=cargo,
        delivery_target_npc_id=target_npc_id,
        delivery_target_planet_id=dest_planet_id,
        origin_planet_id=origin_planet_id,
        is_smuggle=True,
        smuggle_good_id=smuggle_good,
    )


def _generate_bar_salvage(
    origin_planet_id: str,
    tier: int,
    rng: random.Random,
    counter: int,
    giver_npc_id: str,
) -> MissionSpec | None:
    """Generate a procedural salvage (wreck boarding) bar mission."""
    from .data.solar_systems import reachable_system_ids

    p2s = _planet_to_system()
    origin_system_id = p2s.get(origin_planet_id)
    if origin_system_id is None:
        return None

    reachable = reachable_system_ids(origin_system_id, max_hops=10)
    min_hops, max_hops = _SALVAGE_HOP_RANGES.get(tier, (1, 10))

    _candidates = [
        (sid, h) for sid, h in reachable.items()
        if min_hops <= h <= max_hops and sid != origin_system_id
    ]
    if not _candidates:
        return None

    target_system_id, hops = rng.choice(_candidates)

    # Patrol.
    _pool = _PATROL_POOLS.get(tier, ["pirate_scout"])
    patrol_id = rng.choice(_pool)

    _sq_ranges = {1: (1, 1), 2: (1, 2), 3: (1, 2), 4: (2, 3)}
    _sq_lo, _sq_hi = _sq_ranges.get(tier, (1, 1))
    squad_size = rng.randint(_sq_lo, _sq_hi)

    wingmate_id = None
    if squad_size > 1 and tier >= 3:
        wingmate_id = "pirate_scout" if tier == 3 else "pirate_raider"

    # Wreck + layout.
    wreck_id, layout_id = _WRECK_LAYOUTS.get(tier, ("derelict_scout", "scout_a"))

    # Component.
    component = rng.choice(_HEIST_GOODS)

    # Round-trip deadline.
    deadline = max(30, hops * 60 + rng.randint(15, 35))

    credits = tier * 180 + hops * 40
    xp = tier * 35 + hops * 7

    try:
        from .data.npc_ships import find_npc_ship
        patrol_name = find_npc_ship(patrol_id).name
    except KeyError:
        patrol_name = patrol_id

    gen_id = f"proc_salvage_{origin_planet_id}_{target_system_id}_{counter}_{tier}"
    title = f"Salvage: {patrol_name} Wreck"
    description = (
        f"Recover {component} from a derelict wreck {hops} jump(s) away. "
        f"{squad_size} pirate(s) guard the site."
    )

    return MissionSpec(
        id=gen_id,
        title=title,
        description=description,
        giver_npc_id=giver_npc_id,
        faction="bar",
        mission_type="salvage",
        tier=tier,
        reward_credits=credits,
        reward_xp=xp,
        deadline_days=deadline,
        early_bonus_pct=25,
        target_enemy_id=patrol_id,
        target_system_id=target_system_id,
        bounty_target_squad_size=squad_size,
        bounty_wingmate_enemy_id=wingmate_id,
        heist_target_good_id=component,
        salvage_wreck_enemy_id=wreck_id,
        salvage_layout_id=layout_id,
        origin_planet_id=origin_planet_id,
    )


# Dispatch table for bar mission type -> sub-generator.
from typing import Callable as _Callable

_BarGenFn = _Callable[
    [str, int, random.Random, int, str], MissionSpec | None
]

_BAR_GENERATORS: dict[str, _BarGenFn] = {
    "intercept": _generate_bar_intercept,
    "smuggling": _generate_bar_smuggling,
    "salvage": _generate_bar_salvage,
}

_BAR_TYPE_WEIGHTS: dict[str, float] = {
    "intercept": 35.0,
    "smuggling": 35.0,
    "salvage": 30.0,
}


def generate_bar_mission(
    origin_planet_id: str,
    max_tier: int,
    rng: random.Random,
    counter: int = 0,
    giver_npc_id: str = "",
) -> MissionSpec | None:
    """Generate one procedural bar mission (intercept, smuggling, or salvage).

    Algorithm:
      1. Roll tier via shared :func:`_roll_tier`.
      2. Pick a mission type with weighted randomness.
      3. Dispatch to the sub-generator for that type.

    Returns ``None`` if the sub-generator can't find a suitable target
    system or destination.
    """
    tier = _roll_tier(max_tier, rng)

    _types = list(_BAR_TYPE_WEIGHTS.keys())
    _weights = list(_BAR_TYPE_WEIGHTS.values())
    mission_type = rng.choices(_types, weights=_weights, k=1)[0]

    generator = _BAR_GENERATORS[mission_type]
    return generator(origin_planet_id, tier, rng, counter, giver_npc_id)


# Re-exports so consumers can keep using ``mission_module.MissionSpec``
# etc. without a second import line.
__all__ = [
    "ActiveMission",
    "MissionSpec",
    "MissionStatus",
    "MAX_ACTIVE_MISSIONS",
    "release_mission_cargo",
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
    "generate_bounty_mission",
    "generate_bar_mission",
    "_planet_npc_ids",
    "_planet_to_system",
]
