"""Pure validation rules for authored layout documents."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from src.spacehack import layout_format, world
from src.spacehack.dungeon_layout import LOOT_ROOM_TYPES
from src.spacehack.data.npc_chars import find_npc_char

from .model import AssetMode, EditorDocument


_FIXED_MARKERS = frozenset({"P", "C", "E", "T", "r", "R", "S"})


@dataclass(frozen=True)
class ValidationIssue:
    """One actionable document validation message."""

    severity: str
    message: str
    cell: tuple[int, int] | None = None
    directive: str | None = None


def _issue(
    message: str,
    *,
    cell: tuple[int, int] | None = None,
    directive: str | None = None,
    severity: str = "error",
) -> ValidationIssue:
    """Construct one validation issue with optional source location."""
    return ValidationIssue(severity, message, cell, directive)


def _validate_directives(document: EditorDocument) -> list[ValidationIssue]:
    """Validate directive glyphs, tile names, catalog references, and ranges."""
    issues: list[ValidationIssue] = []
    for glyph, directive in document.tile_directives.items():
        if len(glyph) != 1:
            issues.append(_issue("Tile glyphs must contain one character", directive="TILE"))
        try:
            layout_format.tile_for_name(directive.tile_name)
        except KeyError:
            issues.append(_issue(
                f"Unknown tile name {directive.tile_name!r}", directive="TILE",
            ))
    for glyph, directive in document.colour_directives.items():
        if len(glyph) != 1:
            issues.append(_issue("Color glyphs must contain one character", directive="COLOUR"))
        if any(not 0 <= value <= 255 for value in (*directive.fg, *(directive.bg or ()) )):
            issues.append(_issue("Colors must use RGB values from 0 to 255", directive="COLOUR"))
    for glyph, directive in document.loot_directives.items():
        if len(glyph) != 1:
            issues.append(_issue("Loot glyphs must contain one character", directive="LOOT"))
        if directive.room_type not in LOOT_ROOM_TYPES:
            issues.append(_issue(
                f"Unknown loot room type {directive.room_type!r}", directive="LOOT",
            ))
    for glyph, directive in document.enemy_directives.items():
        if len(glyph) != 1:
            issues.append(_issue("Enemy glyphs must contain one character", directive="ENEMY"))
        try:
            find_npc_char(directive.enemy_id)
        except KeyError:
            issues.append(_issue(
                f"Unknown enemy id {directive.enemy_id!r}", directive="ENEMY",
            ))
        if not 0 <= directive.chance <= 1:
            issues.append(_issue("Enemy chance must be between 0 and 1", directive="ENEMY"))
        if directive.squad_min < 1 or directive.squad_min > directive.squad_max:
            issues.append(_issue("Enemy squad bounds are invalid", directive="ENEMY"))
    return issues


def _known_glyphs(document: EditorDocument) -> set[str]:
    """Return glyphs interpreted by the runtime loader for this document."""
    return (
        set(document.tile_directives)
        | set(document.colour_directives)
        | set(document.loot_directives)
        | set(document.enemy_directives)
        | set(_FIXED_MARKERS)
    )


def _validate_grid(document: EditorDocument) -> list[ValidationIssue]:
    """Validate grid shape and every non-space authored glyph."""
    issues: list[ValidationIssue] = []
    known = _known_glyphs(document)
    width = document.grid.width
    for y, row in enumerate(document.grid.rows):
        if len(row) != width:
            issues.append(_issue("Grid rows must all have the same width", cell=(0, y)))
        for x, glyph in enumerate(row):
            if glyph != " " and glyph not in known:
                issues.append(_issue(f"Unknown glyph {glyph!r}", cell=(x, y)))
    if width < 1 or document.grid.height < 1:
        issues.append(_issue("The map must contain at least one cell"))
    return issues


def _tile_map(document: EditorDocument) -> dict[str, world.Tile]:
    """Resolve valid tile directives, omitting invalid entries."""
    resolved: dict[str, world.Tile] = {}
    for glyph, directive in document.tile_directives.items():
        try:
            resolved[glyph] = layout_format.tile_for_name(directive.tile_name)
        except KeyError:
            continue
    return resolved


def _effective_walkable(document: EditorDocument) -> list[list[bool]]:
    """Build the runtime-equivalent walkability grid for reachability checks."""
    tiles = _tile_map(document)
    floor = tiles.get(".", world.DUNGEON_FLOOR)
    dynamic = set(document.enemy_directives) | set(document.loot_directives)
    rows: list[list[bool]] = []
    for line in document.grid.lines():
        nonspace = [x for x, glyph in enumerate(line) if glyph != " "]
        first, last = min(nonspace, default=0), max(nonspace, default=0)
        row: list[bool] = []
        for x, glyph in enumerate(line):
            if x < first or x > last:
                row.append(False)
                continue
            if glyph == " " or glyph in _FIXED_MARKERS or glyph in dynamic:
                row.append(floor.walkable)
                continue
            row.append(tiles.get(glyph, world.VOID).walkable)
        rows.append(row)
    return rows


def _reachable(walkable: list[list[bool]], start: tuple[int, int]) -> set[tuple[int, int]]:
    """Return walkable cells reachable from ``start``."""
    height = len(walkable)
    width = len(walkable[0]) if height else 0
    if not (0 <= start[0] < width and 0 <= start[1] < height) or not walkable[start[1]][start[0]]:
        return set()
    seen = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            neighbor = (x + dx, y + dy)
            if neighbor in seen:
                continue
            nx, ny = neighbor
            if 0 <= nx < width and 0 <= ny < height and walkable[ny][nx]:
                seen.add(neighbor)
                queue.append(neighbor)
    return seen


def _marker_positions(document: EditorDocument, glyph: str) -> list[tuple[int, int]]:
    """Return all grid coordinates containing one marker glyph."""
    return [
        (x, y)
        for y, row in enumerate(document.grid.rows)
        for x, value in enumerate(row)
        if value == glyph
    ]


def _tile_kind_positions(
    document: EditorDocument,
    kind: str,
) -> list[tuple[int, int]]:
    """Return cells whose configured tile directive has ``kind``."""
    tiles = _tile_map(document)
    return [
        (x, y)
        for y, row in enumerate(document.grid.rows)
        for x, glyph in enumerate(row)
        if tiles.get(glyph, world.VOID).kind == kind
    ]


def _validate_markers(document: EditorDocument) -> list[ValidationIssue]:
    """Validate ship and landmark marker contracts and basic reachability."""
    issues: list[ValidationIssue] = []
    spawns = _marker_positions(document, "P")
    if document.mode is AssetMode.SHIP and len(spawns) != 1:
        issues.append(_issue("Ship layouts require exactly one P spawn marker"))
    entrances = _tile_kind_positions(document, "dungeon_door") + _tile_kind_positions(document, "landmark_entrance")
    if document.mode is AssetMode.LANDMARK:
        if len(entrances) != 1:
            issues.append(_issue("Landmarks require exactly one entrance door"))
        for kind in ("stairs_up", "stairs_down"):
            if len(_tile_kind_positions(document, kind)) > 1:
                issues.append(_issue(f"Landmarks allow at most one {kind} marker"))
    if document.mode is AssetMode.CITY:
        if len(entrances) > 1:
            issues.append(_issue("City landmarks allow at most one entrance door"))
        console_tiles = [
            position for position in _marker_positions(document, "C")
            if document.tile_directives.get("C", None)
            and document.tile_directives["C"].tile_name == "DOOR_CONSOLE"
        ]
        if len(console_tiles) > 1:
            issues.append(_issue("Landmarks allow at most one door console"))
    walkable = _effective_walkable(document)
    start = spawns[0] if spawns else None
    if start is None and document.mode is AssetMode.LANDMARK:
        start = next(
            (
                (x, y)
                for y, row in enumerate(walkable)
                for x, is_walkable in enumerate(row)
                if is_walkable
            ),
            None,
        )
    if start is None:
        return issues
    reachable = _reachable(walkable, start)
    targets = _tile_kind_positions(document, "exit")
    if document.mode is AssetMode.LANDMARK:
        targets = _tile_kind_positions(document, "stairs_down")
    for target in targets:
        if target not in reachable:
            neighbors = {
                (target[0] + dx, target[1] + dy)
                for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0))
            }
            if not neighbors & reachable:
                issues.append(_issue("Required destination is unreachable", cell=target))
    return issues


def validate_document(document: EditorDocument) -> tuple[ValidationIssue, ...]:
    """Return all known validation issues without modifying the document."""
    return tuple(
        _validate_directives(document)
        + _validate_grid(document)
        + _validate_markers(document)
    )
