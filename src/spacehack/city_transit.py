"""City public transit: station placement and the station-to-station travel flow.

Public transit lets a player move between a city's named districts without
walking across the whole map. Stations are pure data
(:class:`spacehack.world.TransitStation`, authored per :class:`PlanetSpec`).
This module owns the two runtime pieces:

* :func:`place_transit_stations` — stamp each station's hit-bump entity and a
  ``game_map.city_transit`` lookup onto a freshly built city map.
* :func:`resolve_transit_station` — the bump interaction: show a named
  destination menu, then move the player to the chosen station.

Transit is free in this first slice (no fuel, no credits) and advances the
normal one-action-per-tick contract; the full city-tick/NPC layer is a later
phase.
"""

from __future__ import annotations

from . import world


def place_transit_stations(game_map: world.GameMap, spec) -> None:
    """Append station entities + a ``city_transit`` metadata lookup to ``game_map``."""
    stations = spec.transit_stations or ()
    lookup: dict[str, dict] = {}
    for station in stations:
        game_map.entities.append(world.Entity(
            char=station.glyph,
            fg=station.fg,
            pos=station.pos,
            name=f"Transit: {station.name}",
            width=1, height=1,
            transit_station_id=station.id,
            blocked_message="You step up to the transit gate.",
        ))
        lookup[station.id] = {
            "name": station.name,
            "district": station.district,
            "pos": (station.pos.x, station.pos.y),
            "destinations": list(station.destinations),
        }
    game_map.city_transit = lookup


def _run_transit_menu(ctx, station_name: str, destinations) -> str | None:
    """Run the Pygame destination menu; return the chosen station id or ``None``."""
    from . import pygame_menu, pygame_ui

    frames = tuple(
        pygame_menu.MenuFrame(
            title=station_name,
            body="Choose a transit destination.",
            items=tuple(
                pygame_menu.MenuItem(
                    metadata.get("name"),
                    f"{metadata.get('district', '').title()} district",
                    dest_id,
                )
                for dest_id, metadata in destinations
            ),
            hints=(pygame_ui.modal_hint(
                pygame_ui.NAV_HINT, "ENTER ride", "ESC cancel",
                pygame_ui.GUIDE_HINT,
            ),),
            selected=selected,
        )
        for selected in range(max(1, len(destinations)))
    )
    outcome, action, _selected = pygame_menu.run_for_context(
        ctx.context,
        frames,
        caption=f"spacehack - {station_name}",
    )
    if outcome == "SELECT":
        return action
    if outcome == "GUIDE":
        from .help import _run_help_guide
        _run_help_guide(ctx)
        return None
    return None


def _arrival_cell(game_map, station_pos, station_id) -> world.Position:
    """Pick a walkable arrival cell beside ``station_pos``.

    Prefers a cell that isn't another transit/terminal blocker so the player
    doesn't immediately re-bump a stop. Falls back to the station's own tile.
    """
    x, y = station_pos
    for offset in ((0, 1), (1, 0), (0, -1), (-1, 0), (0, 0)):
        nx, ny = x + offset[0], y + offset[1]
        if not game_map.in_bounds(nx, ny):
            continue
        if not game_map.tiles[ny][nx].walkable:
            continue
        blocker = game_map.blocking_entity_at(nx, ny)
        if blocker is not None and blocker.transit_station_id:
            continue
        return world.Position(nx, ny)
    return world.Position(x, y)


def resolve_transit_station(state, blocker) -> str | None:
    """Handle bumping a transit stop: pick a destination and travel there.

    Returns a loop sentinel (``None``) or ``'QUIT'`` consistent with other
    blocker resolvers in :mod:`spacehack.game_interactions`.
    """
    station_id = blocker.transit_station_id
    lookup = state.game_map.city_transit or {}
    current = lookup.get(station_id)
    if not current:
        return None
    destinations = [
        (dest_id, lookup[dest_id])
        for dest_id in current.get("destinations", ())
        if dest_id in lookup
    ]
    if not destinations:
        state.log.add(f"There are no transit routes leaving {current['name']}.")
        return None
    destination_id = _run_transit_menu(
        state.ctx, current["name"], destinations,
    )
    if destination_id is None:
        return None
    dest = lookup[destination_id]
    state.player.pos = _arrival_cell(
        state.game_map, dest["pos"], destination_id,
    )
    state.log.add(
        f"You ride the transit to the {dest['name']} ({dest['district'].title()} district).",
    )
    return None


__all__ = ["place_transit_stations", "resolve_transit_station"]
