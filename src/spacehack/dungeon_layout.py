"""Authored ship and landmark layout loading."""

from __future__ import annotations

import pathlib
import sys
from dataclasses import dataclass

from . import layout_format, world
from .data.quality import WRECK_QUALITY_RATES, roll_quality
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
LOOT_ROOM_TYPES = frozenset(_LOOT_POOLS)

# Room-typed gear presence (doc 47.2): workgear in the engine room,
# personal effects in storage — what a wreck's crew actually left
# behind. Presence is a 1-in-N roll per loot marker; quality rolls
# through the WRECK ladder. Opening guesses, tuned at playtest.
_ROOM_EQUIPMENT_POOLS: dict[str, tuple[tuple[str, str], ...]] = {
    "engine_room": (
        ("weapon", "survival_axe"), ("armor", "reinforced_gauntlets"),
    ),
    "personal_storage": (
        ("weapon", "kinetic_pistol"), ("weapon", "combat_knife"),
        ("armor", "light_vest"), ("armor", "tactical_gloves"),
    ),
}
WRECK_EQUIPMENT_RATE: int = 3

# Room-typed module presence (doc 47.3 SETTLED 15): spare reactors in
# the engine room, crate-packed system modules in the cargo bay — no
# layout has a "systems" room. Opening guesses, tuned at playtest;
# pool contents are authoring guesses, never mechanism bans (SETTLED 17).
_ROOM_MODULE_POOLS: dict[str, tuple[tuple[str, str], ...]] = {
    "engine_room": (
        ("module", "compact_reactor"), ("module", "reactor_mk2"),
    ),
    "cargo_bay": (
        ("module", "shield_mk1"), ("module", "shield_capacitor"),
        ("module", "targeting_computer"), ("module", "expanded_cargo"),
    ),
}
WRECK_MODULE_RATE: int = 4

# The wreck credit-chip pass (doc 47.4 SETTLED 6/22): small-value
# immediate-reward scatter. Opening guesses, tuned at playtest.
WRECK_CHIP_COUNT: tuple[int, int] = (2, 4)
WRECK_CHIP_VALUE: tuple[int, int] = (40, 120)


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
    if glyph in {"P", "C", "E", "T", "r", "R"} or glyph in parsed.enemy_spawn_specs:
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
    band: int = 0,
) -> None:
    """Scatter authored ENEMY markers; ``band`` (the site's, doc 48
    SETTLED 35) sizes stats/gear — markers fix specs, not stats."""
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
            mx, my,
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
            band=band,
            bold=_spec.elite,
        )


def _find_enemy(enemy_id: str):
    """Resolve one authored enemy catalog entry."""
    from .data.npc_chars import find_npc_char

    return find_npc_char(enemy_id)


def _append_container(
    build: _LayoutBuild, x: int, y: int, fg, payload: dict,
) -> None:
    """Append one salvage container entity."""
    build.entities.append(world.Entity(
        char="%",
        fg=fg,
        pos=world.Position(x, y),
        name="Salvage Container",
        width=1,
        height=1,
        loot_data=payload,
    ))


def _append_loot(
    build: _LayoutBuild,
    x: int,
    y: int,
    good_id: str,
    quantity: int,
    colours: dict[str, layout_format.ColourOverride],
) -> None:
    """Append one trade-good container; authored ``%`` overrides win."""
    from .loot_common import loot_fg

    colour = colours.get("%")
    _append_container(
        build, x, y,
        colour.fg if colour else loot_fg({"good_id": good_id, "quantity": quantity}),
        {"good_id": good_id, "quantity": quantity},
    )


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


def _append_equipment_loot(
    build: _LayoutBuild,
    x: int,
    y: int,
    item_type: str,
    item_id: str,
    quality: int,
    randart_seed: int | None = None,
) -> None:
    """Append one quality-variant ground-equipment container entity."""
    from .loot_common import equipment_payload, loot_fg

    payload = equipment_payload(item_type, item_id, quality, randart_seed)
    _append_container(build, x, y, loot_fg(payload), payload)


def _scatter_pool_presence(
    build: _LayoutBuild,
    pools: dict[str, tuple[tuple[str, str], ...]],
    rate: int,
) -> None:
    """Roll one 1-in-N presence per pool-bearing loot marker; a hit
    drops one pooled item at WRECK-ladder quality."""
    from .engine import RNG

    for marker in build.loot_markers:
        room_type = marker[0]
        pool = pools.get(room_type)
        if not pool or RNG.randint(1, rate) != 1:
            continue
        cells = _room_cells_for_marker(build, marker)
        if not cells:
            continue
        x, y = cells[RNG.randint(0, len(cells) - 1)]
        item_type, item_id = RNG.choice(pool)
        quality = roll_quality(WRECK_QUALITY_RATES, RNG)
        _append_equipment_loot(build, x, y, item_type, item_id, quality)


def _scatter_room_equipment(build: _LayoutBuild) -> None:
    """Roll gear + module presence per equipment-bearing loot marker.

    Runs strictly after the goods passes so pre-existing seeded
    layouts draw the same goods they always did; the equipment pool
    draws before the module pool so its sequence is unchanged too.
    """
    _scatter_pool_presence(build, _ROOM_EQUIPMENT_POOLS, WRECK_EQUIPMENT_RATE)
    _scatter_pool_presence(build, _ROOM_MODULE_POOLS, WRECK_MODULE_RATE)


def _scatter_wreck_chips(build: _LayoutBuild) -> None:
    """The wreck chip pass (doc 47.4): a handful of small-value credit
    containers at loot-marker cells. Gated to dead-ship interiors by
    the caller — cities, landmarks, and intact captures stay out."""
    from .engine import RNG
    from .loot_common import CREDIT_CHIP_KIND, credits_payload, loot_fg

    for _ in range(RNG.randint(*WRECK_CHIP_COUNT)):
        if not build.loot_markers:
            return
        marker = build.loot_markers[RNG.randint(0, len(build.loot_markers) - 1)]
        cells = _room_cells_for_marker(build, marker)
        if not cells:
            continue
        x, y = cells[RNG.randint(0, len(cells) - 1)]
        payload = credits_payload(
            RNG.randint(*WRECK_CHIP_VALUE), CREDIT_CHIP_KIND,
        )
        _append_container(build, x, y, loot_fg(payload), payload)


def _scatter_wreck_kits(build: _LayoutBuild) -> None:
    """The wreck tinker-kit roll (doc 47.5 SETTLED 34): one 1-in-N
    presence per dead-ship interior — very rare, never guaranteed, at
    a loot-marker cell like the chip pass. Draws after the chips so
    pre-existing wreck sequences stay unchanged."""
    from .data.quality import KIT_WRECK_RATE
    from .engine import RNG
    from .ground_consumables import kit_drop_payload
    from .loot_common import loot_fg

    if not build.loot_markers or RNG.randint(1, KIT_WRECK_RATE) != 1:
        return
    marker = build.loot_markers[RNG.randint(0, len(build.loot_markers) - 1)]
    cells = _room_cells_for_marker(build, marker)
    if not cells:
        return
    x, y = cells[RNG.randint(0, len(cells) - 1)]
    payload = kit_drop_payload()
    _append_container(build, x, y, loot_fg(payload), payload)


# The capture strip's room (doc 47.3 SETTLED 15's audit follow-on):
# engine rooms host the pulled hardware.
_CAPTURE_STRIP_ROOM = "engine_room"


def _walkable_cell(build: _LayoutBuild, x: int, y: int) -> bool:
    """True when (x, y) is an in-bounds walkable cell."""
    return (
        0 <= y < len(build.tiles)
        and 0 <= x < len(build.tiles[0])
        and build.tiles[y][x].walkable
    )


def _spawn_adjacent_positions(build: _LayoutBuild) -> list[tuple[int, int]]:
    """Walkable cells in the spawn's 8-neighborhood (strip fallback)."""
    spawn = build.spawn_pos
    if spawn is None:
        return []
    return [
        (spawn.x + dx, spawn.y + dy)
        for dy in (-1, 0, 1)
        for dx in (-1, 0, 1)
        if (dx or dy) and _walkable_cell(build, spawn.x + dx, spawn.y + dy)
    ]


def _capture_strip_cell(
    build: _LayoutBuild, markers, index: int, fallback, rng,
) -> tuple[int, int] | None:
    """Pick one cell for strip item ``index``: round-robin engine-room
    markers first, spawn-adjacent fallback, the spawn cell last."""
    if markers:
        cells = _room_cells_for_marker(build, markers[index % len(markers)])
        if cells:
            return cells[rng.randint(0, len(cells) - 1)]
    if fallback:
        return fallback[index % len(fallback)]
    spawn = build.spawn_pos
    return (spawn.x, spawn.y) if spawn is not None else None


def _seed_capture_modules(build: _LayoutBuild, capture_modules) -> None:
    """The capture strip (doc 47.3 SETTLED 14/16): an intact capture
    drops its whole flown module list — the instances that fought, at
    the quality they flew, no re-roll. Dead-ship interiors (wrecks,
    derelicts, mission salvage) never pass modules: their hardware
    died with the hull, so they feed from room scatter only."""
    from .engine import RNG

    engine_markers = [
        marker for marker in build.loot_markers
        if marker[0] == _CAPTURE_STRIP_ROOM
    ]
    fallback = _spawn_adjacent_positions(build)
    for index, entry in enumerate(capture_modules):
        pos = _capture_strip_cell(build, engine_markers, index, fallback, RNG)
        if pos is not None:
            _append_equipment_loot(
                build, pos[0], pos[1], "module", entry.item_id, entry.quality,
                entry.randart_seed,
            )


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
    from .loot_common import loot_fg
    component = world.Entity(
        char="%",
        fg=loot_fg({"good_id": good_id, "quantity": 1}, mission=True),
        pos=world.Position(x, y),
        name=f"Mission Component: {good_id.replace('_', ' ').title()}",
        width=1,
        height=1,
        loot_data={"good_id": good_id, "quantity": 1},
    )
    component.heist_mission = True
    component.heist_mission_id = mission_id
    build.entities.append(component)


def _populate_build(
    build: _LayoutBuild,
    parsed: layout_format.ParsedLayout,
    layout_id: str,
    *,
    loot_budget,
    component_good_id: str | None,
    component_mission_id: str | None,
    capture_modules: tuple,
    wreck_scatter: bool = False,
    spawn_band: int = 0,
) -> None:
    """Run the full scatter/populate pipeline over a built layout.

    Order is load-bearing: enemies → goods → mission component →
    gear presence → capture strip → wreck scatter (chips, then
    tinker kits), so pre-existing seeded layouts keep drawing the
    goods they always did before any new consumer.
    """
    _scatter_layout_enemies(build, parsed, layout_id, spawn_band)
    _scatter_loot(build, parsed, loot_budget)
    if component_good_id is not None and component_mission_id is not None:
        _place_component(build, parsed, component_good_id, component_mission_id)
    _scatter_room_equipment(build)
    if capture_modules:
        _seed_capture_modules(build, capture_modules)
    if wreck_scatter:
        _scatter_wreck_chips(build)
        _scatter_wreck_kits(build)


def _parse_layout_file(
    layout_id: str, layout_dir: pathlib.Path | None,
) -> layout_format.ParsedLayout:
    """Read and parse one authored layout file from disk."""
    path = (layout_dir or _LAYOUT_DIR) / f"{layout_id}.layout"
    if not path.exists():
        raise FileNotFoundError(f"Layout not found: {path}")
    return layout_format.parse_layout(
        path.read_text(encoding="utf-8").splitlines(), layout_id,
    )


def load_layout(
    layout_id: str,
    *,
    loot_budget: tuple[int, int] | None = None,
    component_good_id: str | None = None,
    component_mission_id: str | None = None,
    capture_modules: tuple = (),
    layout_dir: pathlib.Path | None = None,
    require_spawn: bool = True,
    wreck_scatter: bool = False,
    spawn_band: int = 0,
) -> tuple[world.GameMap, world.Position | None]:
    """Parse an authored layout and return its runtime map and spawn.

    ``capture_modules`` (flown ``StoredEquipment`` instances) seeds the
    intact-capture strip — only the combat boarding path passes it.
    ``wreck_scatter`` gates the dead-ship-only scatter passes (credit
    chips, tinker kits) to wreck/derelict/salvage interiors.
    ``spawn_band`` stamps the site's band on ENEMY markers (doc 48).
    """
    parsed = _parse_layout_file(layout_id, layout_dir)
    build = _build_tiles(parsed, require_spawn)
    _apply_hull_groups(build, parsed.map_lines)
    _apply_colours(build, parsed.map_lines, parsed.colour_overrides)
    _populate_build(
        build, parsed, layout_id,
        loot_budget=loot_budget,
        component_good_id=component_good_id,
        component_mission_id=component_mission_id,
        capture_modules=capture_modules,
        wreck_scatter=wreck_scatter,
        spawn_band=spawn_band,
    )
    game_map = world.GameMap(
        width=parsed.width,
        height=parsed.height,
        tiles=build.tiles,
        entities=build.entities,
    )
    return game_map, build.spawn_pos
