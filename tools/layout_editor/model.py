"""Pygame-independent document model for authored layout files."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from src.spacehack import layout_format, world


class AssetMode(str, Enum):
    """The two supported authored layout asset families."""

    SHIP = "ship"
    LANDMARK = "landmark"
    CITY = "city"


@dataclass(frozen=True)
class TileDirective:
    """Map a single glyph to a world tile constant."""

    glyph: str
    tile_name: str


@dataclass(frozen=True)
class ColourDirective:
    """Override a glyph's foreground and optional background color."""

    glyph: str
    fg: tuple[int, int, int]
    bg: tuple[int, int, int] | None = None


@dataclass(frozen=True)
class LootDirective:
    """Map a glyph to a runtime loot room type."""

    glyph: str
    room_type: str


@dataclass(frozen=True)
class EnemyDirective:
    """Describe an authored enemy spawn marker."""

    glyph: str
    enemy_id: str
    chance: float = 1.0
    squad_min: int = 1
    squad_max: int = 1


@dataclass
class EditorGrid:
    """Mutable rectangular raw-glyph grid."""

    rows: list[list[str]]

    @classmethod
    def from_lines(cls, lines: tuple[str, ...] | list[str]) -> "EditorGrid":
        """Build a rectangular grid, padding short rows with spaces."""
        width = max((len(line) for line in lines), default=1)
        normalized = [list(line.ljust(width)) for line in lines] or [[" "]]
        return cls(normalized)

    @property
    def width(self) -> int:
        """Return the number of columns."""
        return len(self.rows[0]) if self.rows else 0

    @property
    def height(self) -> int:
        """Return the number of rows."""
        return len(self.rows)

    def lines(self) -> tuple[str, ...]:
        """Return rows as immutable strings for serialization."""
        return tuple("".join(row) for row in self.rows)

    def char_at(self, x: int, y: int) -> str:
        """Return the glyph at one coordinate."""
        return self.rows[y][x]

    def set_char(self, x: int, y: int, glyph: str) -> None:
        """Set one cell to exactly one character."""
        if len(glyph) != 1:
            raise ValueError("a grid cell requires exactly one character")
        self.rows[y][x] = glyph

    def resize(self, width: int, height: int, fill: str = " ") -> None:
        """Resize in place while preserving the top-left authored area."""
        if width < 1 or height < 1 or len(fill) != 1:
            raise ValueError("grid dimensions and fill must be positive single-cell values")
        self.rows = [
            [
                self.rows[y][x] if y < self.height and x < self.width else fill
                for x in range(width)
            ]
            for y in range(height)
        ]


@dataclass
class EditorDocument:
    """Editable layout source independent of runtime maps and Pygame."""

    mode: AssetMode
    grid: EditorGrid
    path: Path | None = None
    tile_directives: dict[str, TileDirective] = field(default_factory=dict)
    colour_directives: dict[str, ColourDirective] = field(default_factory=dict)
    loot_directives: dict[str, LootDirective] = field(default_factory=dict)
    enemy_directives: dict[str, EnemyDirective] = field(default_factory=dict)
    dirty: bool = False

    @classmethod
    def from_parsed(
        cls,
        parsed: layout_format.ParsedLayout,
        mode: AssetMode,
        path: Path | None = None,
    ) -> "EditorDocument":
        """Create an editor document from shared parser output."""
        tiles = {
            glyph: TileDirective(glyph, layout_format.tile_name_for(tile))
            for glyph, tile in parsed.tile_map.items()
        }
        colours = {
            glyph: ColourDirective(glyph, override.fg, override.bg)
            for glyph, override in parsed.colour_overrides.items()
        }
        loot = {
            glyph: LootDirective(glyph, room_type)
            for glyph, room_type in parsed.loot_zones.items()
        }
        enemies = {
            glyph: EnemyDirective(glyph, enemy_id, chance, squad_min, squad_max)
            for glyph, (enemy_id, chance, squad_min, squad_max)
            in parsed.enemy_spawn_specs.items()
        }
        return cls(
            mode=mode,
            grid=EditorGrid.from_lines(parsed.map_lines),
            path=path,
            tile_directives=tiles,
            colour_directives=colours,
            loot_directives=loot,
            enemy_directives=enemies,
        )


def infer_mode(path: Path) -> AssetMode:
    """Infer asset mode from the data directory + the tiles it declares.

    City assets (exteriors and interiors for any planet) declare
    ``CITY_*`` tiles; dungeon-style landmarks (e.g. Mars's signal
    door) don't. Anything outside the landmarks directory is a ship
    layout. This is data-driven, not planet-name-driven: Mercury's
    interiors validate the same way Earth's do.
    """
    if path.parent.name != "landmarks":
        return AssetMode.SHIP
    text = path.read_text(encoding="utf-8")
    if any(
        line.strip().startswith("TILE:") and "CITY_" in line
        # Dungeon landmarks borrow CITY_ORNAMENT for crates/bunks
        # (wolf_camp, mercury_vault); only real city fabric — floors,
        # walls, building doors — marks a city asset.
        and "CITY_ORNAMENT" not in line
        for line in text.splitlines()
    ):
        return AssetMode.CITY
    return AssetMode.LANDMARK


def load_document(path: str | Path, mode: AssetMode | None = None) -> EditorDocument:
    """Load a layout file through the shared source parser."""
    path = Path(path)
    parsed = layout_format.parse_layout_file(path)
    return EditorDocument.from_parsed(parsed, mode or infer_mode(path), path)


def new_document(mode: AssetMode, path: Path | None = None) -> EditorDocument:
    """Create a small starter document for the selected asset family."""
    if mode in {AssetMode.LANDMARK, AssetMode.CITY}:
        lines = ["#####", "#...#", "##d##"]
        tiles = {"#": "DUNGEON_WALL", ".": "DUNGEON_FLOOR", "d": "DUNGEON_DOOR"}
    else:
        lines = ["###", "#P#", "#>#"]
        tiles = {"#": "DUNGEON_WALL", ".": "DUNGEON_FLOOR", ">": "EXIT"}
    return EditorDocument(
        mode=mode,
        path=path,
        grid=EditorGrid.from_lines(lines),
        tile_directives={glyph: TileDirective(glyph, name) for glyph, name in tiles.items()},
    )


def tile_for_directive(directive: TileDirective) -> world.Tile:
    """Resolve one editor tile directive through the shared catalog."""
    return layout_format.tile_for_name(directive.tile_name)
