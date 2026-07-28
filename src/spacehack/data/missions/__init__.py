"""Missions catalog: contract-style jobs the player picks up from city NPCs.

Each :class:`Mission` is a frozen dataclass. Adding a new mission is
one entry in a per-faction tuple (e.g. ``merchants.py``, ``bar.py``)
- no if/else chains, no dispatcher rewrites. The runtime layer
(``ActiveMission``, ``try_accept_mission``, ``complete_mission``,
etc.) lives in :mod:`spacehack.mission` so this package stays
focused on static data.

The :mod:`spacehack.__main__` dispatcher uses
:func:`missions_offered_by` to populate the NPC-talk modal and
:func:`find_mission` to resolve the player's :class:`ActiveMission`
back to its full spec. Mission validation lives in
:func:`spacehack.mission.try_accept_mission` /
:func:`spacehack.mission.is_deliverable_at` so the catalog stays
free of business logic.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Mission:
    """A static contract entry in the city's mission catalog.

    Two flavors are wired in this iteration:

    **Delivery** (functional) - the player accepts cargo on one
    planet, flies it to another, hands it to the target NPC.
    ``merchants_supply_run_alpha_centauri`` is the canonical
    exemplar. A delivery mission sets ALL of:

      * ``required_cargo_size > 0`` (the cargo load)
      * ``delivery_target_npc_id`` (the receiving NPC)
      * ``delivery_target_planet_id`` (the receiving planet)

    The runtime layer (:func:`spacehack.mission.try_accept_mission`
    loads cargo, :func:`spacehack.mission.is_deliverable_at` gates
    the Deliver option, :func:`spacehack.mission.complete_mission`
    grants reward) wires the full lifecycle.

    **Flavor** (placeholder) - the player reads the blurb, gets
    the reward, no cargo moves. Eight of the nine current
    missions are flavor; they keep ``required_cargo_size=0`` and
    leave ``delivery_target_*`` unset so :func:`is_deliverable_at`
    never raises a Deliver option for them. Future flavor
    missions stay simple - just title/description/reward - and
    don't touch the cargo/delivery fields.

    Adding a future flavor like the delivery exemplar is a
    one-file edit in the matching ``<faction>.py`` + (if a new
    flavor is added) one line in :func:`_build_registry`. No
    dispatcher / engine / render code rewrites.

    Attributes:
        id: registry key, e.g. ``\"merchants_supply_run_alpha_centauri\"``.
        title: display title shown in the offering modal + log lines.
        description: 1-3 sentence blurb shown in the offering modal.
        giver_npc_id: NPC id (matches :class:`spacehack.data.npcs.NPC.id`)
            who offers this work in their talk modal.
        reward_credits: payout on completion (added to ``stats.credits``).
        reward_xp: payout on completion (logged only - xp stat not
            yet persisted on :class:`spacehack.hud.HudStats`).
        recommended_class_id: optional class id for the \"best suited
            for X\" hint in the offering modal. Soft hint only,
            never a hard filter.
        recommended_ship_min_cargo: optional hull-capacity hint
            shown in the offering modal. Soft hint only.
        required_cargo_size: cargo units the mission loads onto the
            player's hull on accept (subtracted on deliver/abandon).
            Zero for flavor missions. ``> 0`` + matching delivery
            target ids = a delivery mission.
        delivery_target_npc_id: NPC id the player must hand cargo
            to. Required for delivery missions; left ``None`` for
            flavor.
        delivery_target_planet_id: planet id the player must be on
            to deliver. Required for delivery missions; left ``None``
            for flavor.
    """

    id: str
    title: str
    description: str
    giver_npc_id: str
    reward_credits: int
    reward_xp: int
    recommended_class_id: str | None = None
    recommended_ship_min_cargo: int = 0
    required_cargo_size: int = 0
    delivery_target_npc_id: str | None = None
    delivery_target_planet_id: str | None = None
    target_enemy_id: str | None = None    # bounty: which enemy spec to kill
    target_system_id: str | None = None   # bounty: which system to find them in
    deadline_days: int = 0                # days until deadline (0 = no deadline)


# Per-faction mission tuples - append an import + line in
# ``_build_registry`` when adding a new faction (mirrors how
# ``data/weapons/__init__.py`` picks up new weapon modules).
# Order is preserved as offering-modal order (see ``list_missions``).
#
# Note on the per-faction split (vs a single ``missions.py`` like
# ``data/npcs/guilds.py`` has all 5 NPCs): missions have richer
# per-instance variation than NPCs (different field combinations:
# delivery vs flavor) AND each guild has distinct thematic coherence
# (bar=gossip+rumors, merchants=trade+cargo, militia=law+patrol,
# bounty=chases+retrieval) + a common ``giver_npc_id`` binding them
# to one NPC. Grouping by guild keeps a single author's edits
# localised - a future expansion of, say, merchants missions
# naturally edits ``merchants.py`` without growing a single-file
# catalog. If a guild ever needs to ship 10+ missions, splitting
# further (e.g. ``merchants/trade.py`` vs ``merchants/delivery.py``)
# is a natural follow-up rather than a forced refactor.


def _build_registry() -> dict[str, "Mission"]:
    from . import bar as bar_module
    from . import merchants as merchants_module
    from . import militia as militia_module
    from . import bounty as bounty_module
    combined: dict[str, Mission] = {}
    for m in bar_module.MISSIONS:
        combined[m.id] = m
    for m in merchants_module.MISSIONS:
        combined[m.id] = m
    for m in militia_module.MISSIONS:
        combined[m.id] = m
    for m in bounty_module.MISSIONS:
        combined[m.id] = m
    return combined


_BY_ID: dict[str, Mission] | None = None


def _registry() -> dict[str, Mission]:
    global _BY_ID
    if _BY_ID is None:
        _BY_ID = _build_registry()
    return _BY_ID


def find_mission(mission_id: str) -> Mission:
    """Look up a :class:`Mission` catalog entry by id.

    Raises :class:`KeyError` on an unknown id so callers in
    :mod:`spacehack.__main__` get the same
    look-up-by-id contract used by every other catalog module.
    """
    try:
        return _registry()[mission_id]
    except KeyError:
        raise KeyError(f"unknown mission id: {mission_id!r}") from None


def list_missions() -> tuple[Mission, ...]:
    """All registered missions, in registry (offering-modal) order."""
    return tuple(_registry().values())


def missions_offered_by(npc_id: str) -> tuple[Mission, ...]:
    """All :class:`Mission` catalog entries whose ``giver_npc_id``
    matches ``npc_id``.

    Returns an empty tuple on a no-match (an NPC that hasn't been
    wired with missions yet) so callers don't have to special-case
    KeyError - the offering modal just shows \"no work available\".
    """
    return tuple(m for m in list_missions() if m.giver_npc_id == npc_id)


__all__ = ["Mission", "find_mission", "list_missions", "missions_offered_by"]