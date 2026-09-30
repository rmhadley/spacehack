"""Owned-ship save parsing — the loadout migration seam.

Split from ``saveload`` (the architecture ratchet, doc 49 phase 2):
the owned-ship rebuild and its equipment migration parsers live here;
``saveload`` re-imports them under their original private names so
every call site is unchanged.
"""

from __future__ import annotations


def _parse_loadout_entries(raws, parse_one) -> tuple:
    """Installed equipment through one migration parser: legacy bare-id
    strings seed as base entries, unknown records drop (the shared
    weapons/modules seam — doc 47.3 modules, doc 48.7 player weapons)."""
    return tuple(
        entry for raw in (raws or ()) if (entry := parse_one(raw)) is not None
    )


def _parse_owned_ship(data: dict):
    """Rebuild the player's :class:`ship.OwnedShip`, or None."""
    from . import ship as ship_module
    osh = data.get("player_owned_ship")
    if osh is None or not osh.get("ship_id"):
        return None
    # weapon_ammo migration: new saves key ammo by weapon SLOT index
    # (ints serialized as strings by _d). Pre-fix saves keyed it by
    # weapon id (shared magazine bug) — those entries are dropped so
    # __post_init__ seeds each installed launcher a fresh full mag.
    ammo_raw = osh.get("weapon_ammo", {}) or {}
    ammo: dict[int, int] = {}
    for k, v in ammo_raw.items():
        try:
            ammo[int(k)] = int(v)
        except (TypeError, ValueError):
            continue  # legacy weapon-id key — discard
    owned = ship_module.OwnedShip(
        ship_id=osh["ship_id"],
        display_name=osh.get("display_name"),
        fuel=osh.get("fuel", 0),
        hull_damage_pct=osh.get("hull_damage_pct", 0),
        weapons=_parse_loadout_entries(
            osh.get("weapons", ()), ship_module.parse_weapon_entry,
        ),
        modules=_parse_loadout_entries(
            osh.get("modules", ()), ship_module.parse_module_entry,
        ),
        inventory=osh.get("inventory", {}) or {},
        mission_reserved=osh.get("mission_reserved", 0),
        weapon_ammo=ammo,
    )
    # The saved ammo booking is authoritative (doc 49 phase 2): it
    # carries the Bounty Hunter's doubled reserve, which the ctx-free
    # __post_init__ recompute cannot know.
    _saved_cargo_ammo = osh.get("cargo_ammo")
    if _saved_cargo_ammo is not None:
        owned.cargo_ammo = int(_saved_cargo_ammo)
    return owned


def normalize_loaded_grid(ctx) -> None:
    """Run the doc-56 grid normalization once the owned ship AND its
    storage both exist (SETTLED 11/14): placement-less entries strip
    (old-shape saves), illegal geometry repairs, power-invalid grids
    shed their highest-upkeep offenders. The notice line lands here —
    post-ctx, so it reaches the message log the player actually sees."""
    from .data.ships import find_ship
    from . import ship_fitting

    owned = getattr(ctx, "player_owned_ship", None)
    if owned is None:
        return
    try:
        spec = find_ship(owned.ship_id)
    except KeyError:
        return
    stripped = ship_fitting.normalize_fitted_grid(
        owned, ctx.ship_storage, spec,
    )
    if stripped:
        ctx.log.add(f"Fitted gear moved to storage: {', '.join(stripped)}.")
