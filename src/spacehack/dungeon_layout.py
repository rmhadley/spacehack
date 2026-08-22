"""Authored ship and landmark layout loading."""

from __future__ import annotations

import pathlib
import sys
from dataclasses import dataclass

from . import layout_format, world
from .dungeon_population import _room_cells, _scatter_squad


if getattr(sys, "frozen", False):
    _LAYOUT_DIR = pathlib.Path(sys._MEIPASS) / "spacehack" / "data" / "layouts"
else:
    _LAYOUT_DIR = pathlib.Path(__file__).parent / "data" / "layouts"


_LOOT_MAX_PASSES: int = 4
_LOOT_POOLS: dict[str, list[tuple[str, int, int]]] = {
    "engine_room": [("machine_parts", 1, 2), ("fuel_cells", 1, 2), ("ship_components", 1, 1)],
    "mess_hall": [("food_rations", 1, 3), ("medical_supplies", 1, 2), ("luxury_goods", 1, 1)],
    "personal_storage": [("luxury_goods", 1, 1), ("electronics", 1, 2), ("research_data", 1, 1)],
    "cargo_bay": [("ore_processed", 2, 5), ("machine_parts", 1, 3), ("textiles", 1, 3)],
}


@dataclass
class _LayoutBuild:
    """Mutable intermediate representation while an authored map is built."""

    tiles: list[list[world.Tile]]
    entities: list[world.Entity]
    spawn_pos: world.Position | None
    loot_markers: list[tuple[str, int, int]]
    enemy_markers: list[tuple[str, int, int]]


def _console_entity(
    position: world.Position,
    tile_map: dict[str, world.Tile],
    colour: layout_format.ColourOverride | None,
) -> world.Entity:
    """Build a ship computer or alien door console entity."""
    quest_console = tile_map.get("C") is world.DOOR_CONSOLE
    return world.Entity(
        char="C",
        fg=colour.fg if colour else (255, 200, 80),
        pos=position,
        name="Alien Door Console" if quest_console else "Ship Computer",
        width=1,
        height=1,
        computer_terminal=not quest_console,
        main_quest_console=quest_console,
    )


def _engine_entity(
    position: world.Position,
    _tile_map: dict[str, world.Tile],
    colour: layout_format.ColourOverride | None,
) -> world.Entity:
    """Build an engine terminal entity."""
    return world.Entity(
        char="E",
        fg=colour.fg if colour else (180, 200, 220),
        pos=position,
        name="Engine Terminal",
        width=1,
        height=1,
    )


def _terminal_entity(
    position: world.Position,
    _tile_map: dict[str, world.Tile],
    colour: layout_format.ColourOverride | None,
) -> world.Entity:
    """Build a landmark terminal entity."""
    return world.Entity(
        char="T",
        fg=colour.fg if colour else (150, 230, 255),
        pos=position,
        name="Landmark Terminal",
        width=1,
        height=1,
        interaction_flavor="The terminal is dark. Its screen shows nothing.",
    )


_MARKER_BUILDERS = {
    "C": _console_entity,
    "E": _engine_entity,
    "T": _terminal_entity,
}


def _marker_entity(
    glyph: str,
    position: world.Position,
    tile_map: dict[str, world.Tile],
    colours: dict[str, layout_format.ColourOverride],
) -> world.Entity | None:
    """Build the runtime entity represented by one authored marker."""
    builder = _MARKER_BUILDERS.get(glyph)
    return builder(position, tile_map, colours.get(glyph)) if builder else None


def _parse_cell(
    glyph: str,
    x: int,
    y: int,
    first: int,
    last: int,
    parsed: layout_format.ParsedLayout,
) -> tuple[world.Tile, world.Entity | None, bool, tuple[str, int, int] | None, bool]:
    """Translate one raw glyph into a tile and optional marker information."""
    if x < first or x > last:
        return world.VOID, None, False, None, False
    floor = parsed.tile_map.get(".", world.DUNGEON_FLOOR)
    if glyph == " ":
        return floor, None, False, None, False
    if glyph in {"P", "C", "E", "T", "r", "R", "S"} or glyph in parsed.enemy_spawn_specs:
        underlay = parsed.tile_map.get(
            glyph if glyph == "T" else ".",
            floor,
        )
        position = world.Position(x, y)
        return underlay, _marker_entity(glyph, position, parsed.tile_map, parsed.colour_overrides), glyph == "P", None, glyph in parsed.enemy_spawn_specs
    if glyph in parsed.loot_zones:
        return floor, None, False, (parsed.loot_zones[glyph], x, y), False
    return parsed.tile_map.get(glyph, world.VOID), None, False, None, False


def _build_tiles(parsed: layout_format.ParsedLayout, require_spawn: bool) -> _LayoutBuild:
    """Build tiles and defer scatter markers from a parsed layout."""
    tiles: list[list[world.Tile]] = []
    entities: list[world.Entity] = []
    spawn_pos: world.Position | None = None
    loot_markers: list[tuple[str, int, int]] = []
    enemy_markers: list[tuple[str, int, int]] = []
    for y, line in enumerate(parsed.map_lines):
        nonspace = [index for index, char in enumerate(line) if char != " "]
        first = min(nonspace, default=0)
        last = max(nonspace, default=0)
        row: list[world.Tile] = []
        for x, glyph in enumerate(line):
            tile, entity, is_spawn, loot_marker, is_enemy = _parse_cell(
                glyph, x, y, first, last, parsed,
            )
            row.append(tile)
            if entity is not None:
                entities.append(entity)
            if is_spawn:
                if spawn_pos is not None:
                    raise ValueError(
                        f"Multiple spawn points in layout (found at ({x},{y}) "
                        f"and ({spawn_pos.x},{spawn_pos.y}))"
                    )
                spawn_pos = world.Position(x, y)
            if loot_marker is not None:
                loot_markers.append(loot_marker)
            if is_enemy:
                enemy_markers.append((glyph, x, y))
        tiles.append(row)
    if require_spawn and spawn_pos is None:
        raise ValueError("Layout has no player spawn marker (P)")
    return _LayoutBuild(tiles, entities, spawn_pos, loot_markers, enemy_markers)


def _apply_hull_groups(build: _LayoutBuild, map_lines: tuple[str, ...]) -> None:
    """Convert bracketed wall runs into transparent hull-wall tiles."""
    for y, line in enumerate(map_lines):
        in_group = False
        for x, glyph in enumerate(line):
            tile = build.tiles[y][x]
            if tile.kind == "hull_wall" and glyph in ("{", "}"):
                in_group = not in_group
            elif in_group and tile.kind == "dungeon_wall":
                build.tiles[y][x] = world.HULL_WALL


def _apply_colours(
    build: _LayoutBuild,
    map_lines: tuple[str, ...],
    colours: dict[str, layout_format.ColourOverride],
) -> None:
    """Apply authored foreground/background colors to built tiles."""
    for y, line in enumerate(map_lines):
        for x, glyph in enumerate(line):
            override = colours.get(glyph)
            if override is None:
                continue
            tile = build.tiles[y][x]
            build.tiles[y][x] = world.Tile(
                kind=tile.kind,
                char=tile.char,
                walkable=tile.walkable,
                fg=override.fg,
                bg=override.bg if override.bg is not None else tile.bg,
                bg_override=override.bg is not None,
                blocked_message=tile.blocked_message,
            )


def _scatter_layout_enemies(
    build: _LayoutBuild,
    parsed: layout_format.ParsedLayout,
    layout_id: str,
) -> None:
    """Scatter authored enemy markers through their connected rooms."""
    from .engine import RNG

    squad_counter = 0
    for glyph, mx, my in build.enemy_markers:
        enemy_id, chance, squad_min, squad_max = parsed.enemy_spawn_specs[glyph]
        if RNG.random() >= chance:
            continue
        cells = _room_cells(
            build.tiles,
            len(build.tiles[0]),
            len(build.tiles),
            mx,
            my,
            {(entity.pos.x, entity.pos.y) for entity in build.entities},
        )
        if not cells:
            cells = [(mx, my)]
        squad_id = f"{layout_id}_{glyph}_{squad_counter}"
        squad_counter += 1
        _spec = _find_enemy(enemy_id)
        _scatter_squad(
            build.entities,
            {(entity.pos.x, entity.pos.y) for entity in build.entities},
            enemy_id=enemy_id,
            cells=cells,
            count=RNG.randint(squad_min, squad_max),
            squad_id=squad_id,
            char=_spec.char,
            fg=parsed.colour_overrides.get(glyph, layout_format.ColourOverride((255, 100, 100))).fg,
        )


def _find_enemy(enemy_id: str):
    """Resolve one authored enemy catalog entry."""
    from .data.npc_chars import find_npc_char

    return find_npc_char(enemy_id)


def _append_loot(
    build: _LayoutBuild,
    x: int,
    y: int,
    good_id: str,
    quantity: int,
    colours: dict[str, layout_format.ColourOverride],
) -> None:
    """Append one salvage container entity."""
    colour = colours.get("%")
    build.entities.append(world.Entity(
        char="%",
        fg=colour.fg if colour else (180, 220, 140),
        pos=world.Position(x, y),
        name="Salvage Container",
        width=1,
        height=1,
        loot_data={"good_id": good_id, "quantity": quantity},
    ))


def _room_cells_for_marker(
    build: _LayoutBuild,
    marker: tuple[str, int, int],
) -> list[tuple[int, int]]:
    """Return currently unoccupied cells connected to one loot marker."""
    _, x, y = marker
    occupied = {(entity.pos.x, entity.pos.y) for entity in build.entities}
    return _room_cells(build.tiles, len(build.tiles[0]), len(build.tiles), x, y, occupied)


def _affordable_loot(
    pool: list[tuple[str, int, int]],
    remaining: int,
) -> tuple[str, int, int] | None:
    """Choose a shuffled affordable good and return its value."""
    from .data.trade_goods import find_trade_good
    from .engine import RNG

    indices = list(range(len(pool)))
    RNG.shuffle(indices)
    for index in indices:
        good_id, min_qty, max_qty = pool[index]
        try:
            good = find_trade_good(good_id)
        except KeyError:
            continue
        quantity = RNG.randint(min_qty, max_qty)
        value = good.base_price * quantity
        if value <= remaining:
            return good_id, quantity, value
    return None


def _scatter_loot_pass(
    build: _LayoutBuild,
    parsed: layout_format.ParsedLayout,
    remaining: int | None,
) -> tuple[int | None, bool]:
    """Place one pass of budgeted or guaranteed loot."""
    from .engine import RNG
    placed_any = False
    for marker in build.loot_markers:
        room_type = marker[0]
        pool = _LOOT_POOLS.get(room_type, [])
        cells = _room_cells_for_marker(build, marker)
        if not pool or not cells:
            continue
        x, y = cells[RNG.randint(0, len(cells) - 1)]
        if remaining is None:
            good_id, min_qty, max_qty = pool[RNG.randint(0, len(pool) - 1)]
            quantity = RNG.randint(min_qty, max_qty)
            _append_loot(build, x, y, good_id, quantity, parsed.colour_overrides)
            placed_any = True
            continue
        choice = _affordable_loot(pool, remaining)
        if choice is None:
            continue
        good_id, quantity, value = choice
        _append_loot(build, x, y, good_id, quantity, parsed.colour_overrides)
        remaining -= value
        placed_any = True
    return remaining, placed_any


def _scatter_loot(build: _LayoutBuild, parsed: layout_format.ParsedLayout, budget) -> None:
    """Scatter guaranteed or budget-constrained loot containers."""
    from .engine import RNG

    has_budget = budget is not None and budget[1] > 0
    remaining = RNG.randint(budget[0], budget[1]) if has_budget else None
    passes = _LOOT_MAX_PASSES if has_budget else 1
    for _ in range(passes):
        remaining, placed = _scatter_loot_pass(build, parsed, remaining)
        if has_budget and not placed:
            break


def _place_component(
    build: _LayoutBuild,
    parsed: layout_format.ParsedLayout,
    good_id: str,
    mission_id: str,
) -> None:
    """Place one mission-tagged component in a random loot room."""
    from .engine import RNG

    if not build.loot_markers:
        return
    marker = build.loot_markers[RNG.randint(0, len(build.loot_markers) - 1)]
    cells = _room_cells_for_marker(build, marker) or [(marker[1], marker[2])]
    x, y = cells[RNG.randint(0, len(cells) - 1)]
    component = world.Entity(
        char="%",
        fg=(255, 215, 0),
        pos=world.Position(x, y),
        name=f"Mission Component: {good_id.replace('_', ' ').title()}",
        width=1,
        height=1,
        loot_data={"good_id": good_id, "quantity": 1},
    )
    component.heist_mission = True
    component.heist_mission_id = mission_id
    build.entities.append(component)


def load_layout(
    layout_id: str,
    *,
    loot_budget: tuple[int, int] | None = None,
    component_good_id: str | None = None,
    component_mission_id: str | None = None,
    layout_dir: pathlib.Path | None = None,
    require_spawn: bool = True,
) -> tuple[world.GameMap, world.Position | None]:
    """Parse an authored layout and return its runtime map and spawn."""
    path = (layout_dir or _LAYOUT_DIR) / f"{layout_id}.layout"
    if not path.exists():
        raise FileNotFoundError(f"Layout not found: {path}")
    parsed = layout_format.parse_layout(
        path.read_text(encoding="utf-8").splitlines(), layout_id,
    )
    build = _build_tiles(parsed, require_spawn)
    _apply_hull_groups(build, parsed.map_lines)
    _apply_colours(build, parsed.map_lines, parsed.colour_overrides)
    _scatter_layout_enemies(build, parsed, layout_id)
    _scatter_loot(build, parsed, loot_budget)
    if component_good_id is not None and component_mission_id is not None:
        _place_component(build, parsed, component_good_id, component_mission_id)
    game_map = world.GameMap(
        width=parsed.width,
        height=parsed.height,
        tiles=build.tiles,
        entities=build.entities,
    )
    return game_map, build.spawn_pos
