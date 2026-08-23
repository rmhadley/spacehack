"""Shared parser for authored ``.layout`` source files.

This module owns only the text-to-directives transformation. Runtime map
construction remains in :mod:`spacehack.dungeon`, while tools can consume the
same parsed source without reimplementing the layout syntax.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from . import world


@dataclass(frozen=True)
class ColourOverride:
    """Optional foreground/background override from a layout directive."""

    fg: tuple[int, int, int]
    bg: tuple[int, int, int] | None = None


@dataclass(frozen=True)
class ParsedLayout:
    """The source sections and directives found in one layout file."""

    map_lines: tuple[str, ...]
    tile_map: dict[str, world.Tile]
    colour_overrides: dict[str, ColourOverride]
    loot_zones: dict[str, str]
    enemy_spawn_specs: dict[str, tuple[str, float, int, int]]

    @property
    def width(self) -> int:
        """Return the padded map width in cells."""
        return max((len(line) for line in self.map_lines), default=0)

    @property
    def height(self) -> int:
        """Return the number of authored map rows."""
        return len(self.map_lines)


_TILE_BY_NAME: dict[str, world.Tile] = {
    name: getattr(world, name)
    for name in dir(world)
    if isinstance(getattr(world, name), world.Tile)
}
from . import city_tiles as _city_tiles

_TILE_BY_NAME.update({
    name: getattr(_city_tiles, name)
    for name in dir(_city_tiles)
    if name.startswith("CITY_") and isinstance(getattr(_city_tiles, name), world.Tile)
})


def tile_names() -> tuple[str, ...]:
    """Return available world tile constant names in stable order."""
    return tuple(sorted(_TILE_BY_NAME))


def tile_for_name(name: str) -> world.Tile:
    """Return the authoritative tile for a constant name."""
    return _TILE_BY_NAME[name]


def tile_name_for(tile: world.Tile) -> str:
    """Return the first constant name that refers to ``tile``."""
    for name in tile_names():
        if _TILE_BY_NAME[name] is tile:
            return name
    raise KeyError(f"Unknown world tile: {tile!r}")


def _split_directive(rest: str) -> tuple[str, str] | None:
    """Split a ``glyph = value`` directive, including ``=`` as a glyph."""
    if " = " in rest:
        return rest.split(" = ", 1)
    if "=" in rest:
        return rest.split("=", 1)
    return None


def _parse_rgb(value: str) -> tuple[int, int, int] | None:
    """Parse one ``(R, G, B)`` tuple."""
    parts = [part.strip() for part in value.strip().strip("()").split(",")]
    if len(parts) != 3:
        return None
    try:
        return tuple(int(part) for part in parts)  # type: ignore[return-value]
    except ValueError:
        return None


def _parse_colour(rest: str) -> tuple[str, ColourOverride] | None:
    """Parse a foreground-only or foreground/background color directive."""
    parts = _split_directive(rest)
    if parts is None:
        return None
    glyph_part, rgb_part = parts
    if "#" in rgb_part:
        rgb_part = rgb_part.split("#", 1)[0].strip()
    fg_text, _, bg_text = rgb_part.partition("/")
    fg = _parse_rgb(fg_text)
    if fg is None:
        return None
    bg = _parse_rgb(bg_text) if bg_text else None
    if bg_text and bg is None:
        return None
    return glyph_part.strip(), ColourOverride(fg=fg, bg=bg)


def _parse_loot(rest: str, loot_zones: dict[str, str]) -> None:
    """Add one LOOT directive to ``loot_zones`` when it is well formed."""
    parts = _split_directive(rest)
    if parts is None:
        return
    glyph, room_type = parts
    loot_zones[glyph.strip()] = room_type.strip()


def _parse_enemy(rest: str, enemy_specs: dict[str, tuple[str, float, int, int]]) -> None:
    """Add one ENEMY directive to ``enemy_specs``."""
    parts = _split_directive(rest)
    if parts is None:
        return
    glyph_part, spec_part = parts
    spec = spec_part.strip()
    squad_min, squad_max = 1, 1
    if "#" in spec:
        spec, squad_text = spec.rsplit("#", 1)
        try:
            if "-" in squad_text:
                min_text, max_text = squad_text.split("-", 1)
                squad_min, squad_max = int(min_text), int(max_text)
            else:
                squad_min = squad_max = int(squad_text)
        except ValueError:
            pass
    if "@" in spec:
        enemy_id, chance_text = spec.rsplit("@", 1)
        try:
            chance = float(chance_text)
        except ValueError:
            chance = 1.0
    else:
        enemy_id, chance = spec, 1.0
    enemy_specs[glyph_part.strip()] = (
        enemy_id.strip(), chance, squad_min, squad_max,
    )


def _parse_tile(
    layout_id: str,
    rest: str,
    tile_map: dict[str, world.Tile],
) -> None:
    """Add one TILE directive or raise for an unknown tile constant."""
    parts = _split_directive(rest)
    if parts is None:
        return
    glyph_part, tile_name = parts
    glyph = glyph_part.strip()
    tile_name = tile_name.strip()
    if tile_name not in _TILE_BY_NAME:
        raise ValueError(
            f"Unknown tile name {tile_name!r} in TILE directive "
            f"of layout {layout_id!r}"
        )
    tile_map[glyph] = _TILE_BY_NAME[tile_name]


def _collect_sections(lines: Iterable[str]) -> tuple[list[str], list[str]]:
    """Collect MAP rows and post-map directive lines."""
    map_lines: list[str] = []
    directives: list[str] = []
    in_map = False
    after_map = False
    for line in lines:
        stripped = line.strip()
        if stripped == "MAP":
            in_map = True
            continue
        if stripped == "ENDMAP":
            in_map = False
            after_map = True
            continue
        if in_map:
            map_lines.append(line)
            continue
        if stripped.startswith("#") or not stripped:
            continue
        if after_map:
            directives.append(line)
    return map_lines, directives


def _apply_directive(
    layout_id: str,
    line: str,
    tile_map: dict[str, world.Tile],
    colour_overrides: dict[str, ColourOverride],
    loot_zones: dict[str, str],
    enemy_specs: dict[str, tuple[str, float, int, int]],
) -> None:
    """Apply one supported post-map directive to the output collections."""
    stripped = line.strip()
    if stripped.startswith("LOOT:"):
        _parse_loot(stripped[5:].strip(), loot_zones)
        return
    if stripped.startswith("ENEMY:"):
        _parse_enemy(stripped[6:].strip(), enemy_specs)
        return
    if stripped.startswith("TILE:"):
        _parse_tile(layout_id, stripped[5:].strip(), tile_map)
        return
    if stripped.startswith("COLOUR:"):
        parsed = _parse_colour(stripped[7:].strip())
        if parsed is not None:
            glyph, override = parsed
            colour_overrides[glyph] = override


def parse_layout(lines: Iterable[str], layout_id: str = "<layout>") -> ParsedLayout:
    """Parse layout source lines into a shared, padded representation."""
    map_lines, directives = _collect_sections(lines)
    if not map_lines:
        raise ValueError(f"Layout {layout_id!r} has no MAP section")
    tile_map: dict[str, world.Tile] = {}
    colour_overrides: dict[str, ColourOverride] = {}
    loot_zones: dict[str, str] = {}
    enemy_specs: dict[str, tuple[str, float, int, int]] = {}
    for line in directives:
        _apply_directive(
            layout_id, line, tile_map, colour_overrides,
            loot_zones, enemy_specs,
        )
    width = max(len(line) for line in map_lines)
    padded = tuple(line.ljust(width) for line in map_lines)
    return ParsedLayout(
        map_lines=padded,
        tile_map=tile_map,
        colour_overrides=colour_overrides,
        loot_zones=loot_zones,
        enemy_spawn_specs=enemy_specs,
    )


def parse_layout_file(path: str | Path, layout_id: str | None = None) -> ParsedLayout:
    """Read and parse one UTF-8 layout file."""
    path = Path(path)
    return parse_layout(
        path.read_text(encoding="utf-8").splitlines(),
        layout_id or path.stem,
    )
