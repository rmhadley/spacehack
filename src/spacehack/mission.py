"""Missions: contract-style jobs the player picks up from city NPCs.

Missions live in two places:

  * Here (``Mission`` + ``MISSIONS``) - static catalog entries describing
    the work. Each entry binds a :class:`spacehack.npc.NPC` via
    ``giver_npc_id``; the NPC's flavor text mentions the work and the
    offering modal lists it.
  * :mod:`spacehack.__main__` - an :class:`ActiveMission` instance
    tracks the player's currently accepted mission (single slot,
    matches the single-ship-slot design from :mod:`spacehack.ship`).

Categories and class hints are SOFT - we never hard-block a class from
any mission, but a ``recommended_class_id`` lets the UI print a "best
suited for {class}" hint without locking the player out. The reward
numbers are placeholder values; once mission outcomes are wired in
they'll move from ``None`` to ``(gold, xp)`` deltas in
:mod:`spacehack.__main__`.

Mission contents are deliberately placeholder-grade titles / blurbs
because the user explicitly said "we don't have to worry about the
mission details yet" - what matters this iteration is the SHAPE of
the data and the FLOW through the dispatcher.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from . import ship


@dataclass(frozen=True)
class Mission:
    """A static contract entry in the city's mission catalog.

    ``title`` and ``description`` are placeholder strings for this
    iteration. ``giver_npc_id`` matches a :class:`spacehack.npc.NPC`
    id - the dispatch in :mod:`spacehack.__main__` uses it to know
    which NPC offers the work. ``reward_gold`` + ``reward_xp`` are
    placeholders (positive ints; gameplay wiring lands in a later
    iteration). ``recommended_class_id`` is optional and is shown
    as a flavor hint rather than a hard gate.
    """

    id: str
    title: str
    description: str
    giver_npc_id: str
    reward_gold: int
    reward_xp: int
    recommended_class_id: str | None = None
    recommended_ship_min_cargo: int = 0
    # How much cargo this mission loads onto the player's hull when
    # accepted (subtracted again at delivery). Zero for missions
    # that don't actually move goods around — combat / diplomacy /
    # scouting jobs. The dispatcher in :mod:`spacehack.__main__`
    # uses this for the cargo-cap check on ACCEPT and the
    # cargo-drop on COMPLETE/DELIVER. Kept distinct from
    # :attr:`recommended_ship_min_cargo` which is only a soft hint
    # about the recommended hull capacity.
    required_cargo_size: int = 0
    # Where this mission's cargo must be hand-delivered to finish
    # it. Both ids are optional — a mission that has no delivery
    # target simply never raises the "Deliver <title>" NPC-talk
    # option anywhere, even if the player tries to complete it
    # early. A delivery mission sets BOTH to a matching pair
    # (e.g. research_officer on ac_station) so the deliver
    # predicate in :func:`is_deliverable_at` can verify the
    # current NPC AND the current planet together, preventing
    # the bug where the cargo-release fires when the player
    # bumps the wrong NPC on the wrong planet.
    delivery_target_npc_id: str | None = None
    delivery_target_planet_id: str | None = None


# Eight placeholder missions (two per quest-giver NPC). The titles
# are deliberately generic so future iterations can swap in real
# prose without touching the data model or dispatcher. Class hints
# are informational only - a soft "best suited for X" line in the
# UI, never a hard filter.
#
# NPC bindings:
#   barkeep         (bar / city rumours)        - any class
#   guild_master    (merchants guild / trade)     - best for merchant
#   militia_captain (militia / law-and-order)     - best for bounty_hunter
#   bounty_master   (bhguild / chases)            - best for bounty_hunter
MISSIONS: tuple[Mission, ...] = (
    # ----- barkeep (bar) ----------------------------------------------
    Mission(
        id="bar_routine_delivery",
        title="A routine delivery",
        description=(
            "A small but time-sensitive cargo drop across the next "
            "system. No escort, no danger - just don't be late."
        ),
        giver_npc_id="barkeep",
        reward_gold=60,
        reward_xp=10,
        recommended_class_id=None,
        recommended_ship_min_cargo=20,
    ),
    Mission(
        id="bar_back_alley_dispute",
        title="A back-alley dispute",
        description=(
            "Two regulars are arguing over a debt. Talk to both, "
            "settle it quietly, keep it out of the militia's ears."
        ),
        giver_npc_id="barkeep",
        reward_gold=40,
        reward_xp=15,
        recommended_class_id=None,
    ),
    # ----- guild_master (merchants) ----------------------------------
    Mission(
        id="merchants_supply_run_alpha_centauri",
        title="Supply run to Alpha Centauri",
        description=(
            "The research station orbiting Proxima Centauri is low "
            "on resealable research supplies. Ten units of cargo - "
            "calibration gear, biologics, the boring essentials. "
            "Hand them to the Research Officer on arrival."
        ),
        giver_npc_id="guild_master",
        reward_gold=150,
        reward_xp=30,
        recommended_class_id="merchant",
        recommended_ship_min_cargo=10,
        required_cargo_size=10,
        delivery_target_npc_id="research_officer",
        delivery_target_planet_id="ac_station",
    ),
    Mission(
        id="merchants_bulk_trade",
        title="Bulk trade run",
        description=(
            "A convoy-style trade route with room for high-margin "
            "cargo. Bring a ship with capacity to spare."
        ),
        giver_npc_id="guild_master",
        reward_gold=140,
        reward_xp=20,
        recommended_class_id="merchant",
        recommended_ship_min_cargo=80,
    ),
    Mission(
        id="merchants_tariff_dispute",
        title="Tariff dispute mediation",
        description=(
            "Two guild branches disagree on who owes what. Talk it "
            "through, broker the deal, take a small cut."
        ),
        giver_npc_id="guild_master",
        reward_gold=80,
        reward_xp=25,
        recommended_class_id="merchant",
    ),
    # ----- militia_captain (militia) ----------------------------------
    Mission(
        id="militia_beat_patrol",
        title="Beat patrol",
        description=(
            "Walk a route through the lower wards, log anything "
            "unusual, report back. Pays quietly and on time."
        ),
        giver_npc_id="militia_captain",
        reward_gold=50,
        reward_xp=15,
        recommended_class_id="bounty_hunter",
    ),
    Mission(
        id="militia_lost_property",
        title="Lost property retrieval",
        description=(
            "A crate of supplies vanished en route to a militia "
            "outpost. Find it. Return it. No questions asked."
        ),
        giver_npc_id="militia_captain",
        reward_gold=70,
        reward_xp=20,
        recommended_class_id="bounty_hunter",
    ),
    # ----- bounty_master (bounties) -----------------------------------
    Mission(
        id="bounty_smuggler_at_large",
        title="Bounty: a smuggler at large",
        description=(
            "A repeat offender is using the outer belt to dodge "
            "duties. Bring them in. Alive preferred, not required."
        ),
        giver_npc_id="bounty_master",
        reward_gold=180,
        reward_xp=30,
        recommended_class_id="bounty_hunter",
    ),
    Mission(
        id="bounty_deserter",
        title="Bounty: locate the deserter",
        description=(
            "A former crewmember skipped on a debt. Find them. "
            "Recover the mark or the money - whichever is cleaner."
        ),
        giver_npc_id="bounty_master",
        reward_gold=120,
        reward_xp=35,
        recommended_class_id="bounty_hunter",
    ),
)


_BY_ID: dict[str, Mission] = {m.id: m for m in MISSIONS}


def find_mission(mission_id: str) -> Mission:
    """Look up a :class:`Mission` catalog entry by id.

    Raises :class:`KeyError` on an unknown id so callers in
    :mod:`spacehack.__main__` get the same
    look-up-by-id contract used by every other catalog module.
    """
    try:
        return _BY_ID[mission_id]
    except KeyError:
        raise KeyError(f"unknown mission id: {mission_id!r}") from None


def missions_offered_by(npc_id: str) -> tuple[Mission, ...]:
    """All :class:`Mission` catalog entries whose ``giver_npc_id``
    matches ``npc_id``.

    Returns an empty tuple on a no-match (an NPC that hasn't been
    wired with missions yet) so callers don't have to special-case
    KeyError - the offering modal just shows "no work available".
    """
    return tuple(m for m in MISSIONS if m.giver_npc_id == npc_id)


class MissionStatus(Enum):
    """Lifecycle state of an :class:`ActiveMission`.

    Single member this iteration (\"in_progress\") - the user's
    explicit \"we don't have to wire up mission completion yet\"
    note. Future iterations add ``COMPLETED`` and ``FAILED`` here;
    callers dispatch on the enum value rather than a free-form
    string so a typo can't quietly land an invalid state.

    Defined ABOVE :class:`ActiveMission` so the field default
    ``MissionStatus.IN_PROGRESS`` is visible when :class:`ActiveMission`
    is evaluated (Python resolves default expressions at class-body
    time, not lazily). A string forward reference would have worked
    for the *annotation* but not for the *default expression*.
    """

    IN_PROGRESS = auto()


@dataclass
class ActiveMission:
    """Mutable state of the player's currently accepted mission.

    Single slot - matches :class:`spacehack.ship.OwnedShip` and the
    overall one-of-everything scaffold design. ``status`` is a
    :class:`MissionStatus` enum (auto()-numbered to mirror
    :class:`spacehack.ui.MenuAction` / :class:`spacehack.character`
    -- free-form strings would let typos sneak in once completion
    lands). Only ``IN_PROGRESS`` is wired this iteration; future
    states (``COMPLETED``, ``FAILED``) can be added here without
    churning call sites because no caller outside the dispatcher
    reads ``status`` yet.
    """

    mission_id: str
    status: MissionStatus = MissionStatus.IN_PROGRESS


def try_accept_mission(
    mission: Mission,
    owned_ship: object,
    log: object,
) -> bool:
    """Accept ``mission`` if the player's owned ship has the cargo
    capacity for it. Mutates :attr:`OwnedShip.cargo_used` on
    success. Returns ``True`` if the mission was accepted,
    ``False`` if the cargo cap was exceeded.

    ``owned_ship`` is duck-typed (``cargo_used`` / ``ship_id``)
    rather than imported as :class:`spacehack.ship.OwnedShip` so
    this module stays free of cross-imports - the dispatcher
    passes the player's actual instance and we drive the
    mutation off ``ship_id``. ``log`` is duck-typed the same way
    (must expose :func:`add`).

    A ``mission`` with :attr:`Mission.required_cargo_size` of 0
    has no cargo to load -- it always accepts regardless of the
    ship (and never mutates ``cargo_used``). When
    ``owned_ship`` is ``None`` (the player hasn't bought a ship
    yet), zero-cargo missions still accept; non-zero ones refuse
    with the standard "you need a hull" log line.
    """
    if mission.required_cargo_size <= 0:
        return True
    if owned_ship is None:
        log.add("You don't have a ship to carry cargo yet.")
        return False
    ship_obj = ship.find_ship(owned_ship.ship_id)
    new_used = owned_ship.cargo_used + mission.required_cargo_size
    if new_used > ship_obj.max_cargo:
        short = new_used - ship_obj.max_cargo
        log.add(
            f"Your {ship_obj.name} can't carry '{mission.title}' - "
            f"{short} cargo unit(s) over capacity ({owned_ship.cargo_used}"
            f"/{ship_obj.max_cargo})."
        )
        return False
    owned_ship.cargo_used = new_used
    log.add(
        f"You accept: {mission.title}. "
        f"Cargo now {owned_ship.cargo_used}/{ship_obj.max_cargo}."
    )
    return True


def is_deliverable_at(mission: Mission, npc_id: str, planet_id: str) -> bool:
    """True iff ``mission`` can be handed over to NPC ``npc_id``
    while the player is on ``planet_id``.

    A mission is deliverable at a given (NPC, planet) pair only
    when ALL of the following hold:

      * the mission actually moves cargo (:attr:`required_cargo_size`
        > 0) — combat / diplomacy jobs never raise a Deliver
        option so they cannot be "mis-delivered" by accident,
      * the NPC id matches :attr:`Mission.delivery_target_npc_id`,
      * the planet id matches :attr:`Mission.delivery_target_planet_id`.

    The predicate is intentionally strict — a partial match
    (right NPC, wrong planet, or vice versa) returns ``False`` so
    the dispatcher shows the regular NPC flavor dialog instead
    of a Deliver option. Without the strict check, a future
    cross-system delivery could fire ``complete_mission`` on the
    wrong body the player happened to bump while flying past.
    The smoke @checks lock this contract in.
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


def abort_mission(
    mission: Mission,
    owned_ship: object,
    log: object,
) -> None:
    """Drop the mission's cargo from ``owned_ship`` and log the
    release. Symmetric to the ACCEPT-side cargo load — the only
    side-effect on the player's hull is undone without granting
    any gold/xp (abandoning is not the same as completing).

    Used when the player abandons a mission through the quest
    log. Pure side-effects; the dispatcher is responsible for
    clearing :class:`ActiveMission` afterwards so this helper
    stays out of the mission-slot bookkeeping.

    A zero-cargo mission is a no-op (nothing to release). A
    ``None`` owned_ship is a no-op too — the player cannot have
    cargo loaded without a hull, so there's nothing to give back.
    The cargo drop is clamped at zero so a future regression
    that mis-pairs the accept/abort math cannot land the
    cargo_used below the floor.
    """
    if mission.required_cargo_size <= 0 or owned_ship is None:
        return
    owned_ship.cargo_used = max(
        0, owned_ship.cargo_used - mission.required_cargo_size,
    )
    ship_obj = ship.find_ship(owned_ship.ship_id)
    log.add(
        f"Cargo released from abandoned '{mission.title}' "
        f"({owned_ship.cargo_used}/{ship_obj.max_cargo})."
    )


def complete_mission(
    mission: Mission,
    owned_ship: object,
    stats: object,
    log: object,
) -> None:
    """Complete ``mission``: drop its cargo from the owned ship,
    grant gold to ``stats``, and log the payout.

    Symmetric with :func:`try_accept_mission` -- the cargo delta
    is exactly :attr:`Mission.required_cargo_size` either way (so
    cargo_used returns to zero if no other missions are active).
    Duck-types ``owned_ship`` / ``stats`` / ``log`` for the same
    reason as :func:`try_accept_mission` - the dispatcher is the
    one place that knows the concrete types and is responsible for
    clearing :class:`ActiveMission` after this returns.

    The mission's :attr:`Mission.reward_xp` is logged but not
    applied to a stat yet (future iteration: add an xp field to
    :class:`spacehack.hud.HudStats`). The reward_xp flow is
    accounted for so the player sees the full payout in the
    message log even though we don't persist xp.
    """
    if mission.required_cargo_size > 0 and owned_ship is not None:
        owned_ship.cargo_used = max(
            0, owned_ship.cargo_used - mission.required_cargo_size,
        )
    if hasattr(stats, "gold"):
        stats.gold = stats.gold + mission.reward_gold
    ship_obj = (
        ship.find_ship(owned_ship.ship_id)
        if owned_ship is not None
        else None
    )
    cargo_after = (
        f"{owned_ship.cargo_used}/{ship_obj.max_cargo}"
        if ship_obj is not None
        else "no ship"
    )
    log.add(
        f"Delivered: {mission.title}. +{mission.reward_gold}g "
        f"+{mission.reward_xp}xp. ({cargo_after} cargo.)"
    )
