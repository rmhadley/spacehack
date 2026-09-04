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
            "serves": station.serves,
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
    """Pick a clear walkable arrival cell beside ``station_pos``.

    The player must never be dropped onto a blocker (another transit stop,
    a terminal, an NPC, a ship) or wedged into a building door, so we scan
    a small ring around the station and take the first cell that is walkable,
    free of every blocking entity, and not a door tile. Falls back to walking
    one cell away from the station to avoid landing on the stop itself.
    """
    if hasattr(station_pos, "x"):
        x, y = station_pos.x, station_pos.y
    else:
        x, y = station_pos[0], station_pos[1]
    for radius in range(1, 3):
        for dx, dy in (
            (0, -1), (1, 0), (0, 1), (-1, 0),
            (1, -1), (1, 1), (-1, 1), (-1, -1),
        ):  # cardinals first, then diagonals
            if abs(dx) > radius or abs(dy) > radius:
                continue
            nx, ny = x + dx, y + dy
            if not game_map.in_bounds(nx, ny):
                continue
            tile = game_map.tiles[ny][nx]
            if not tile.walkable or tile.kind == "door":
                continue
            if game_map.blocking_entity_at(nx, ny) is not None:
                continue
            return world.Position(nx, ny)
    # No free neighbour — step away from the station, or fail to the station.
    x2, y2 = x, y
    for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0)):
        nx, ny = x + dx, y + dy
        if game_map.in_bounds(nx, ny) and game_map.tiles[ny][nx].walkable \
                and game_map.tiles[ny][nx].kind != "door" \
                and game_map.blocking_entity_at(nx, ny) is None:
            x2, y2 = nx, ny
            break
    return world.Position(x2, y2)


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
    animate_transit_arrival(
        state, dest["name"],
        colour=_station_colour(state.game_map, destination_id),
    )
    return None


def _station_colour(game_map, station_id):
    """The station's own entity colour (the gold transit default if absent)."""
    _entity = next(
        (
            e for e in game_map.entities
            if getattr(e, "transit_station_id", "") == station_id
        ),
        None,
    )
    return getattr(_entity, "fg", (255, 215, 100))


def _arrival_pulse_sources(base, pos, colour, intensity) -> list:
    """Base map sources plus one decaying pulse at the arrival cell."""
    from .lighting import LightSource

    return list(base) + [LightSource(
        x=pos.x, y=pos.y, colour=tuple(colour),
        radius=3, intensity=intensity,
    )]


def _present_light_frame(state, game_map, sources, clock, location) -> None:
    """Assign a propagated light grid and present one city frame."""
    from .city_render import present_city_transition_frame
    from .lighting import propagate_light

    def _occludes(x: int, y: int) -> bool:
        return not game_map.tiles[y][x].walkable

    game_map.light_grid = propagate_light(
        game_map.width, game_map.height, sources,
        t=clock, occluder=_occludes,
    )
    present_city_transition_frame(
        state.ctx, state.console, game_map, state.player, location,
    )


def animate_transit_arrival(
    state, location: str, colour=(255, 215, 100),
) -> None:
    """Bloom the arrival stop's glow around the player, then settle.

    A busy city can hide where transit dropped you (playtest v15); a
    pulse of the stop's own colour at the player's cell eases out over
    ~0.6s while the city renders normally around it. The steady light
    grid is snapshotted and restored exactly, so flickering cities
    resume bit-identical. No-op on maps without a light grid.

    Frames go through the pure ``propagate_light`` (not
    ``recompute_light_grid``) because the cached recompute skips
    all-steady sources — and a decaying pulse is steady by profile.
    """
    from . import animation_timing
    from .navigation_travel import _responsive_sleep

    game_map = state.game_map
    if getattr(game_map, "light_grid", None) is None:
        return
    pos = state.player.pos
    base = list(getattr(game_map, "light_sources", None) or [])
    snapshot = [row[:] for row in game_map.light_grid]
    clock = getattr(getattr(state.ctx, "context", None), "frame_clock", 0)

    frames = 12
    for i in range(frames):
        _present_light_frame(
            state, game_map,
            _arrival_pulse_sources(base, pos, colour, (1.0 - i / frames) ** 1.6),
            clock, location,
        )
        _responsive_sleep(animation_timing.TRANSIT_ARRIVAL)
    game_map.light_grid = snapshot
    from .city_render import present_city_transition_frame
    present_city_transition_frame(
        state.ctx, state.console, game_map, state.player, location,
    )


__all__ = ["place_transit_stations", "resolve_transit_station"]
