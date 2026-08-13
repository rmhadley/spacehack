"""Mission queries, board lookup, and display helpers.

This module owns read-oriented mission predicates plus the shared
planet/system lookup cache used by procedural mission consumers.
"""
from __future__ import annotations

import dataclasses

from ..data.missions import MissionSpec, find_mission
from ._models import ActiveMission, MissionBoard


_PLANET_SYSTEM_CACHE: dict[str, str] | None = None


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

    # Main-quest smuggle crates are handled through the quest
    # dialogue overlay ("Hand over the crate"), not the standard
    # Deliver flow — showing both is confusing.
    if getattr(active, 'main_quest_step_id', ''):
        return False
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


def board_key(npc_id: str, planet_id: str = "") -> str:
    """Return the composite key for a mission board: NPC + planet.

    Boards are per-city, not per-NPC: the same NPC id (e.g.
    ``"guild_master"``) is re-skinned on many planets, and each city
    must keep its own mission list (that's what per-planet
    ``mission_tier`` scales). Keying by NPC id alone would make every
    city share the first board that was created for that NPC.
    """
    if planet_id:
        return f"{npc_id}@{planet_id}"
    return npc_id


def find_board_for_mission(
    ctx,
    mission_id: str,
) -> MissionBoard | None:
    """Return the board that offered ``mission_id``, or ``None``.

    Used by abandon / smuggle-fail paths to return a static mission to
    the exact board (NPC + city) that offered it — the board key is no
    longer derivable from the NPC id alone.

    Two-step lookup:
      1. Scan board slots first (covers missions still sitting on a
         board, e.g. planet-agnostic statics).
      2. Fall back to deriving the key from the static spec's
         ``giver_npc_id`` + ``origin_planet_id`` — accepted missions
         are removed from slots on accept, so they're only reachable
         through their spec. Returns ``None`` if unresolvable.
    """
    for _board in ctx.mission_boards.values():
        if mission_id in _board.slots:
            return _board
    try:
        _spec = find_mission(mission_id)
        return ctx.mission_boards.get(
            board_key(_spec.giver_npc_id, _spec.origin_planet_id or ""),
        )
    except KeyError:
        return None


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


def _planet_to_system() -> dict[str, str]:
    """Return ``{planet_id: system_id}`` for every planet (and station
    city_planet_id) across all registered solar systems.

    Lazy-built and cached so procedural generation doesn't re-scan the
    system registry on every call.
    """
    global _PLANET_SYSTEM_CACHE
    if _PLANET_SYSTEM_CACHE is not None:
        return _PLANET_SYSTEM_CACHE

    from ..data import solar_systems as _sys_mod
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


def system_display_name(system_id: str | None) -> str:
    """Resolve a solar-system id to its display name, with fallback.

    Falls back to a title-cased version of the raw id when the
    catalog lookup fails. ``None`` resolves to ``"unknown"``.
    """
    if not system_id:
        return "unknown"
    try:
        from ..data.solar_systems import find_solar_system as _fss
        return _fss(system_id).name
    except (KeyError, ImportError):
        return system_id.replace('_', ' ').title()


def system_name_for_planet(planet_id: str | None) -> str | None:
    """Resolve a planet id to its solar system's display name.

    Uses the cached planet-to-system mapping from
    :func:`_planet_to_system`, so callers always agree with the
    procedural generators. Returns ``None`` for unknown planets.
    """
    if not planet_id:
        return None
    _sys_id = _planet_to_system().get(planet_id)
    if _sys_id is None:
        return None
    return system_display_name(_sys_id)


def destination_system_name(mission) -> str | None:
    """Resolve a mission's destination solar system's display name.

    Uses ``target_system_id`` when set (bounties, intercepts,
    salvage); otherwise falls back to the delivery target planet's
    system (deliveries, smuggling). Returns ``None`` when neither
    is resolvable.
    """
    _sys_id = getattr(mission, 'target_system_id', None)
    if not _sys_id:
        _sys_id = system_name_for_planet(
            getattr(mission, 'delivery_target_planet_id', None),
        )
        return _sys_id
    return system_display_name(_sys_id)

