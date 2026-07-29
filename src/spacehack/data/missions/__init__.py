"""Missions catalog: contract-style jobs the player picks up from city NPCs.

Each :class:`MissionSpec` is a frozen dataclass. Adding a new mission is
one entry in a per-faction tuple (e.g. ``merchants.py``)
- no if/else chains, no dispatcher rewrites. The runtime layer
(``ActiveMission``, ``try_accept_mission``, ``complete_mission``,
etc.) lives in :mod:`spacehack.mission` so this package stays
focused on static data.

Delivery-only this iteration. Bounty, patrol, and flavor mission
types are follow-up work — the data model supports them (fields present)
but no entries exist yet.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MissionSpec:
    """A static contract entry in the city's mission catalog.

    Two tiers of complexity:

    **Hand-crafted** — a content author writes a :class:`MissionSpec`
    literal in a faction file (e.g. ``merchants.py``). These are
    tracked by ``completed_mission_ids`` so they don't repeat.

    **Procedural** — generated at runtime by
    :func:`generate_delivery_mission`. These are ephemeral: abandon
    = gone, new one generates in the freed board slot.

    Attributes:
        id: registry key, e.g. ``"merchants_delivery_earth_mars"``.
        title: display title shown in the offering modal + log lines.
        description: 1-3 sentence blurb shown in the offering modal.
        giver_npc_id: NPC id who offers this work in their talk modal.
        faction: guild/faction tag — ``"merchants"``, ``"bounty"``, etc.
        mission_type: ``"delivery"`` (this iteration), or ``"bounty"``,
            ``"patrol"`` in future passes.
        tier: 1-4, controls where the mission appears (planet
            ``mission_tier`` gates) and reward scaling.
        reward_credits: base payout on completion.
        reward_xp: base XP on completion.
        deadline_days: days until deadline (0 = no deadline).
        early_bonus_pct: % bonus if completed in < 50% of deadline
            (e.g. 25 = +25% credits). 0 = no early bonus.

        # --- Delivery-specific ---
        required_cargo_size: cargo units loaded on accept,
            released on deliver/abandon. 0 for non-delivery types.
        delivery_target_npc_id: NPC to hand cargo to.
        delivery_target_planet_id: planet where delivery happens.
        origin_planet_id: source planet, used for tier gating
            (only offered on planets where this matches).

        # --- Bounty-specific ---
        target_enemy_id: enemy spec to kill.
        target_system_id: system to find them in.
        bounty_target_name: custom display name for the target
            (e.g. "Vex Korr"). When set, overrides the base
            NpcShipSpec name for the spawned enemy entity.
            Procedural missions generate names from tier-gated
            word pools. None == use the base spec name.
        bounty_target_squad_size: number of enemies in the target
            group (leader + wingmates). 1 = solo target.
        bounty_target_loadout_pct: 0-100 representing how upgraded
            the target's weapons/modules are vs the base spec.
            0 = base spec, 50 = +1 weapon, 100 = fully kitted.

        # --- Recommendations (soft hints) ---
        recommended_class_id: optional class hint for offering modal.
        recommended_ship_min_cargo: optional hull-capacity hint.
    """

    id: str
    title: str
    description: str
    giver_npc_id: str
    faction: str = "merchants"
    mission_type: str = "delivery"
    tier: int = 1
    reward_credits: int = 0
    reward_xp: int = 0
    deadline_days: int = 0
    early_bonus_pct: int = 0

    # --- Delivery-specific ---
    required_cargo_size: int = 0
    delivery_target_npc_id: str | None = None
    delivery_target_planet_id: str | None = None
    origin_planet_id: str | None = None

    # --- Bounty-specific ---
    target_enemy_id: str | None = None
    target_system_id: str | None = None
    bounty_target_name: str | None = None
    bounty_target_squad_size: int = 1
    bounty_target_loadout_pct: int = 0

    # --- Recommendations ---
    recommended_class_id: str | None = None
    recommended_ship_min_cargo: int = 0


# Per-faction mission tuples. Empty this iteration — all existing missions
# are replaced. Phase 2 adds hand-crafted delivery missions here.
#
# Adding a new faction:
#   1. Create a new <faction>.py exporting MISSIONS: tuple[MissionSpec, ...]
#   2. Add an import + loop in _build_registry below.
#   3. Missions are auto-discovered — no dispatcher changes needed.


def _build_registry() -> dict[str, "MissionSpec"]:
    from . import bar as bar_module
    from . import merchants as merchants_module
    from . import militia as militia_module
    from . import bounty as bounty_module
    combined: dict[str, MissionSpec] = {}
    for m in bar_module.MISSIONS:
        combined[m.id] = m
    for m in merchants_module.MISSIONS:
        combined[m.id] = m
    for m in militia_module.MISSIONS:
        combined[m.id] = m
    for m in bounty_module.MISSIONS:
        combined[m.id] = m
    return combined


_BY_ID: dict[str, MissionSpec] | None = None


def _registry() -> dict[str, MissionSpec]:
    global _BY_ID
    if _BY_ID is None:
        _BY_ID = _build_registry()
    return _BY_ID


def find_mission(mission_id: str) -> MissionSpec:
    """Look up a :class:`MissionSpec` catalog entry by id.

    Raises :class:`KeyError` on an unknown id.
    """
    try:
        return _registry()[mission_id]
    except KeyError:
        raise KeyError(f"unknown mission id: {mission_id!r}") from None


def list_missions() -> tuple[MissionSpec, ...]:
    """All registered missions, in registry order."""
    return tuple(_registry().values())


def missions_offered_by(
    npc_id: str,
    planet_tier: int = 1,
    completed_ids: frozenset[str] | None = None,
    active_ids: frozenset[str] | None = None,
    planet_id: str | None = None,
) -> tuple[MissionSpec, ...]:
    """All :class:`MissionSpec` entries whose ``giver_npc_id``
    matches ``npc_id``, filtered by planet tier, completion status,
    active missions, and origin planet.

    Only returns missions where:
      * ``m.tier <= planet_tier`` (planet can support this level)
      * ``m.id`` NOT in ``completed_ids`` (don't repeat finished missions)
      * ``m.id`` NOT in ``active_ids`` (don't re-offer accepted missions)
      * ``m.origin_planet_id`` matches ``planet_id`` (or is None, or
        ``planet_id`` is None — origin-gating is opt-in)

    Returns an empty tuple on a no-match so the offering modal
    just shows "no work available".
    """
    if completed_ids is None:
        completed_ids = frozenset()
    if active_ids is None:
        active_ids = frozenset()
    return tuple(
        m for m in list_missions()
        if m.giver_npc_id == npc_id
        and m.tier <= planet_tier
        and m.id not in completed_ids
        and m.id not in active_ids
        and (planet_id is None or m.origin_planet_id is None or m.origin_planet_id == planet_id)
    )


__all__ = [
    "MissionSpec",
    "find_mission",
    "list_missions",
    "missions_offered_by",
]
