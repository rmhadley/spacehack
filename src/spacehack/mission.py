"""Mission runtime layer: lifecycle state + accept/deliver/complete/abort.

Missions live in two layers:

  * :mod:`spacehack.data.missions` - the static catalog (the
    :class:`Mission` dataclass + per-faction ``MISSIONS`` tuples
    + :func:`find_mission` / :func:`missions_offered_by` lookup
    helpers). Adding a new mission is a one-file edit there.
  * Here (:class:`ActiveMission` + the four runtime functions
    below) - the BUSINESS LOGIC that operates on a :class:`Mission`
    instance the player has accepted. Splits the "data shape"
    concern (in data/) from the "what happens when the player
    accepts / delivers / aborts / completes" concern (here).

This module re-exports :class:`Mission`, :func:`find_mission`,
and :func:`missions_offered_by` from :mod:`spacehack.data.missions`
so the dispatcher's ``mission_module.Mission`` / ``mission_module.
find_mission`` / ``mission_module.missions_offered_by`` references
keep working without forcing a second import line on every caller.
The runtime functions take a :class:`Mission` as their first arg
so the data dependency is explicit at the call boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from . import ship
from .data.missions import Mission, find_mission, missions_offered_by


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

    ``bounty_spawn_id`` is set on accept for bounty missions with
    a ``target_enemy_id`` — it links the active mission to the
    dynamically spawned :class:`GameContext.BountySpawn` so combat
    can verify the correct target was killed.
    """

    mission_id: str
    status: MissionStatus = MissionStatus.IN_PROGRESS
    bounty_spawn_id: str | None = None


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


# Re-exports so consumers (e.g. ``spacehack.__main__``) can keep
# using ``mission_module.Mission`` / ``mission_module.find_mission`` /
# ``mission_module.missions_offered_by`` without a second import
# line. The data lives in :mod:`spacehack.data.missions`; this
# module is the runtime layer that operates on it.
#
# Two import paths are equivalent and both supported:
#   from spacehack import mission as mission_module        # runtime + data facade
#   from spacehack.data.missions import Mission, ...        # data-only
# The facade keeps ``mission_module.X`` working so existing call
# sites in ``__main__`` (~16 references) don't churn. New code can
# import directly from data.missions for clarity; old code keeps
# working.
#
# IDENTITY GUARANTEE: ``mission_module.Mission is Mission`` (and
# ditto for the helpers). Smoke-verified at the registry build site
# so a future refactor that accidentally drops the re-exports (or
# wraps the symbol in a proxy) breaks the identity check rather
# than silently changing consumer semantics.
__all__ = [
    "ActiveMission",
    "Mission",
    "MissionStatus",
    "abort_mission",
    "complete_mission",
    "find_mission",
    "is_deliverable_at",
    "missions_offered_by",
    "try_accept_mission",
]