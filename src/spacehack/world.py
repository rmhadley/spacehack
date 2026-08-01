"""Game world: tile-based map + entities + a small procedural city.

For now the world is a single rectangular "city" room (walls around
the perimeter, floor inside, doors for exits) plus:

  * a wandering Merchant NPC near the city center,
  * the space-port building in the upper-left quadrant with one door
    in its south wall + three starships inside (sold via the
    ship-buy modal),
  * four guild buildings (Bar, Merchant Guild, Militia Center,
    Bounty Hunter Guild), each with a labeled top wall, a south
    door, and a guild NPC standing inside.

Scrolling / multiple rooms / outdoor terrain come later.
"""
from __future__ import annotations

import random

from dataclasses import dataclass

import tcod.console


# ---------------------------------------------------------------------------
# Tile kinds
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Tile:
    """A single tile on the map."""
    kind: str            # "wall" / "floor" / "door" / "label"
    char: str            # the glyph drawn at this tile
    walkable: bool       # can an entity stand on this tile?
    fg: tuple[int, int, int]
    bg: tuple[int, int, int]   # background painted under the glyph (darker than fg so the glyph reads on top)


WALL = Tile(kind="wall", char="▓", walkable=False, fg=(155, 185, 215), bg=(50, 62, 78))     # dark shade — paneled bulkhead texture
FLOOR = Tile(kind="floor", char="\u00b7", walkable=True, fg=(225, 205, 155), bg=(100, 86, 58)) # middot - reads as polished indoor flooring
DOOR = Tile(kind="door", char="+", walkable=True, fg=(100, 220, 255), bg=(25, 55, 80))        # glowing cyan glyph on dark port-blue base

# City exterior - walks like FLOOR for collision, but with a glyph and
# color that reads as a road, plaza, sidewalk, or grass patch. Used by
# ``make_city`` via :func:`_layout_outside` to dress up the open
# spaces between buildings so the city feels a bit lived-in.
#
# Each kind uses a distinct ascii / unicode glyph so a player can't
# confuse a plaza with a sidewalk at a glance; the smoke test asserts
# this explicitly to keep a future refactor from silently merging two
# tile kinds (e.g. by collapsing them to '.').

# Road centre lane marking (direction-specific glyphs)
ROAD_NS = Tile(kind="road", char=":", walkable=True, fg=(110, 115, 140), bg=(40, 42, 55))    # dark slate glyph on dark asphalt base
ROAD_EW = Tile(kind="road", char="-", walkable=True, fg=(110, 115, 140), bg=(40, 42, 55))    # same palette; direction glyph differs

# Road surface (fine asphalt grain between lane markings). 3-wide roads
# use ROAD_SURFACE on the two edge lanes and ROAD_NS/ROAD_EW on the
# centre lane, so the road reads as a defined corridor.
ROAD_SURFACE = Tile(kind="road", char=".", walkable=True, fg=(135, 140, 160), bg=(48, 50, 63))

# Open paved plaza — period reads as a fine paved square
PLAZA = Tile(kind="plaza", char=".", walkable=True, fg=(240, 230, 215), bg=(190, 180, 165))  # fine dot on cream base

# Sidewalk edge strips (equals sign reads as manufactured strip)
SIDEWALK = Tile(kind="sidewalk", char="=", walkable=True, fg=(140, 145, 170), bg=(75, 80, 100))

# Grass / green space — tilde reads as vegetation / field.
GRASS = Tile(kind="grass", char="~", walkable=True, fg=(115, 200, 95), bg=(40, 80, 35))

# Grass accent — comma adds a little texture without overwhelming.
GRASS_ACCENT = Tile(kind="grass", char=",", walkable=True, fg=(90, 175, 75), bg=(40, 80, 35))

# Landing pad — tarmac with a cool sci-fi blue glow (replaces generic
# sidewalk south of the spaceport with a dedicated ship-parking area).
LANDING_PAD = Tile(kind="landing_pad", char="=", walkable=True, fg=(100, 210, 255), bg=(25, 45, 70))

# Neon accent — decorative glowing marker outside the spaceport
# entrance and at plaza edges. Using `*` char (classic sparkle / star)
# with bright gold-white fg so it pops against the dark asphalt
# without needing a unicode star glyph that may not exist in the
# terminal font.
NEON = Tile(kind="neon", char="*", walkable=True, fg=(255, 220, 100), bg=(40, 25, 12))

# Decorative tree — T reads as a tree top.
TREE = Tile(kind="tree", char="T", walkable=True, fg=(90, 180, 85), bg=(30, 65, 25))

# Decorative plaza feature — o reads as a fountain / jewel.
DECOR = Tile(kind="plaza", char="o", walkable=True, fg=(255, 160, 120), bg=(190, 180, 165))

# Interior building floor — warmer, brighter variant so it reads as a
# clean indoor surface distinct from the outdoor GRASS tiles.
INTERIOR = Tile(kind="floor", char="\u00b7", walkable=True, fg=(245, 225, 175), bg=(130, 108, 70))

# --- Dungeon tiles (ship interiors) ---
DUNGEON_WALL = Tile(kind="dungeon_wall", char="#", walkable=False,
                     fg=(120, 130, 150), bg=(30, 35, 45))
DUNGEON_FLOOR = Tile(kind="dungeon_floor", char=".", walkable=True,
                      fg=(200, 200, 210), bg=(50, 55, 65))
DUNGEON_DOOR = Tile(kind="dungeon_door", char="+", walkable=True,
                     fg=(100, 220, 255), bg=(20, 45, 70))
VOID = Tile(kind="void", char=" ", walkable=False,
            fg=(0, 0, 0), bg=(0, 0, 0))
AIRLOCK = Tile(kind="airlock", char="=", walkable=True,
               fg=(100, 200, 255), bg=(30, 60, 80))
BREACH = Tile(kind="breach", char="X", walkable=True,
              fg=(255, 120, 50), bg=(80, 30, 10))
COCKPIT = Tile(kind="cockpit", char="C", walkable=True,
               fg=(255, 200, 80), bg=(60, 45, 20))
ENGINE_TILE = Tile(kind="engine", char="E", walkable=True,
                    fg=(180, 200, 220), bg=(40, 45, 55))
DEBRIS = Tile(kind="debris", char="%", walkable=True,
              fg=(140, 130, 100), bg=(60, 55, 40))
EXIT = Tile(kind="exit", char=">", walkable=True,
            fg=(100, 255, 120), bg=(20, 60, 25))

# Hull wall — blocks movement like DUNGEON_WALL but does NOT block
# FOV raycasting, so structural groups ({##}) on the ship exterior
# can be seen through. The layout parser replaces # tiles within
# {…} groups with this tile.
HULL_WALL = Tile(kind="hull_wall", char="#", walkable=False,
                 fg=(120, 130, 150), bg=(30, 35, 45))

# --- Building-interior furniture tiles ---
# Bar counter top (warm golden wood).
BAR_COUNTER = Tile(kind="floor", char=".", walkable=True, fg=(210, 165, 90), bg=(120, 100, 65))
# Bar counter body / front (darker wood grain).
BAR_BODY = Tile(kind="floor", char="=", walkable=True, fg=(160, 120, 70), bg=(90, 75, 50))
# Table surface (= reads as a surface bar).
TABLE = Tile(kind="floor", char="=", walkable=True, fg=(255, 200, 80), bg=(130, 108, 70))
# Drink glass (! bright red for contrast against warm floor).
DRINK = Tile(kind="floor", char="!", walkable=True, fg=(255, 60, 60), bg=(130, 108, 70))


# ---------------------------------------------------------------------------
# Planet theme — per-planet colour / tile palette
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlanetTheme:
    """Colour-palette overrides for outdoor tiles.

    Each field is a :class:`Tile` that's used by :func:`_layout_outside`
    instead of the Earth-default module-level constant. A theme stores
    **only** the tiles that can vary — WALL, DOOR and the furniture
    tiles (BAR_*) stay at their module-level values everywhere so
    building exteriors and fixtures read consistently.

    ``floor`` is used by :func:`spacehack.data.planets.load_planet` as
    the base tile when initialising the tile grid (the "air" that fills
    every cell before buildings are carved). On Earth / Mars this is
    the warm brown indoor-outdoor floor; on a station it becomes a
    sterile metal deck plate.

    To add a new planet with a custom look, create a
    :class:`PlanetTheme` instance in the planet's data module and
    assign it to the ``theme`` field of its :class:`PlanetSpec`.
    """
    floor: Tile = FLOOR
    grass: Tile = GRASS
    grass_accent: Tile = GRASS_ACCENT
    plaza: Tile = PLAZA
    sidewalk: Tile = SIDEWALK
    road_surface: Tile = ROAD_SURFACE
    road_ns: Tile = ROAD_NS
    road_ew: Tile = ROAD_EW
    landing_pad: Tile = LANDING_PAD
    neon: Tile = NEON
    tree: Tile = TREE
    decor: Tile = DECOR


# Canonical Earth-default theme (matches the module-level constants above).
# Use this when no explicit theme is provided.
EARTH_THEME = PlanetTheme()


# ---------------------------------------------------------------------------
# Positions and entities
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Position:
    """An (x, y) coordinate on the map (city-space, not screen-space)."""
    x: int
    y: int


# Entity is NOT frozen: gameplay code reassigns ``pos`` in place when
# the entity moves. ``width`` and ``height`` are footprint metadata for
# collision; rendering paints the char at every cell of the footprint.
# An entity is either a ship (positive ``ship_id``), an NPC (positive
# ``npc_id``), or neither (e.g. the player, the wandering merchant).
#
# ``owned`` differentiates showroom ships (``owned=False``) from
# the player's hangar ship (``owned=True``). The occupied dispatch
# in :mod:`spacehack.__main__` reads it to decide whether bumping
# into a ship opens the buy dialog or the hangar menu.
@dataclass
class Entity:
    """A thing on the map that has its own glyph."""
    char: str
    fg: tuple[int, int, int]
    pos: Position
    name: str = ""
    ship_id: str = ""
    npc_id: str = ""
    width: int = 1
    height: int = 1
    owned: bool = False
    npc_ship_id: str = ""           # references NpcShipSpec.id for NPC ships
    procedural_squad_id: str = ""
    trade_terminal: bool = False
    mech_terminal: bool = False
    armory_terminal: bool = False
    computer_terminal: bool = False  # dungeon ship computer — interactable
    loot_data: dict | None = None  # {"good_id": str, "quantity": int} — set for cargo loot entities
    npc_char_id: str = ""  # references NpcCharSpec.id for ground-combat NPCs
    squad_id: str = ""  # groups ground enemies into squads (shared across scatter-spawned entities)


# Anchor where the player's bought ship is parked outside the
# space port. Lives in the SIDEWALK strip just south of the port's
# south door (which itself is at (port.x_lo + 9, port.y_hi) = (13,
# 12)) and is pointed exactly at the column where the door opens,
# so a player exiting the port door walks straight onto their
# ship. ``14`` is one row below the SIDEWALK border at y=13, which
# keeps the parked ship south of the strip's „you just walked
# out" edge and away from the eastern road at y=20.
HANGAR_ANCHOR: Position = Position(13, 17)


# ---------------------------------------------------------------------------
# GameMap
# ---------------------------------------------------------------------------


@dataclass
class GameMap:
    """Tile grid + entities, all in city-space coordinates."""
    width: int
    height: int
    tiles: list[list[Tile]]
    entities: list[Entity]
    seen: list[list[bool]] | None = None  # fog-of-war: True = revealed; None = no fog
    sight_radius: int = 4  # dungeon fog sight radius; increased by power restore

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def is_walkable(self, x: int, y: int) -> bool:
        return self.in_bounds(x, y) and self.tiles[y][x].walkable

    def entity_at(self, x: int, y: int, *, exclude: Entity | None = None) -> Entity | None:
        """First entity whose footprint contains ``(x, y)`` (excluding
        ``exclude`` if provided).

        Honoring footprint means a multi-cell ship correctly blocks
        the player on every covered tile, not just the anchor.
        """
        for e in self.entities:
            if e is exclude:
                continue
            if (
                e.pos.x <= x < e.pos.x + e.width
                and e.pos.y <= y < e.pos.y + e.height
            ):
                return e
        return None

    def replace_tile(self, x: int, y: int, tile: Tile) -> None:
        self.tiles[y][x] = tile

    def is_revealed(self, x: int, y: int) -> bool:
        """Whether a cell is revealed by fog of war.

        Returns ``True`` if there's no fog (city/space maps) or the
        cell has been explored.
        """
        if self.seen is None:
            return True
        if not self.in_bounds(x, y):
            return False
        return self.seen[y][x]


# ---------------------------------------------------------------------------
# Labeled buildings (one factory, used by space port AND guild halls)
# ---------------------------------------------------------------------------


# ``spaceport`` is the default building label; guild halls pass their
# own label string (``bar``, ``merchants``, ``militia``, ``bounties``).
SPACEPORT_LABEL: str = "spaceport"
SPACEPORT_LABEL_FG: tuple[int, int, int] = (220, 220, 220)

# Per-building label colors so each guild reads as distinct at a
# glance. Looked up by :func:`make_building`; unknown labels fall
# back to ``SPACEPORT_LABEL_FG``.
BUILDING_LABEL_COLORS: dict[str, tuple[int, int, int]] = {
    "spaceport": (100, 220, 255),       # bright cyan - space commerce
    "bar":       (255, 200, 80),         # warm gold - tavern / nightlife
    "bounties":  (255, 130, 200),        # vivid magenta - danger / reward
    "merchants": (140, 240, 140),        # soft green - wealth / trade
    "militia":   (130, 230, 220),        # teal - order / defence
    "depot":     (200, 200, 160),        # warm grey - utility / refueling
    "lab":       (150, 220, 200),        # teal-cyan - research / science
}


def make_building(
    label: str,
    x_lo: int, x_hi: int, y_lo: int, y_hi: int,
    *,
    door_x: int | None = None,
    occupant: Entity | None = None,
    door_north: bool = False,
) -> tuple[list[tuple[Position, Tile]], list[Entity]]:
    """Build a labeled rectangular building with one door and
    (optionally) a single NPC standing inside.

    By default the door is on the south wall (``y_hi``) and the
    label text is carved into the north wall (``y_lo``). Pass
    ``door_north=True`` to flip: the door moves to the north wall
    and the label moves to the south wall.

    This is a pure factory - it returns the tile-overwrites and the
    occupant entities (possibly empty) for the caller to splice into
    a :class:`GameMap`.

    Args:
      label:      text carved into the top wall (or south wall if
                  ``door_north=True``).
      x_lo, x_hi: inclusive tile x-range of the outer walls.
      y_lo, y_hi: inclusive tile y-range of the outer walls.
      door_x:     x-coordinate of the door tile. Defaults to the
                  midpoint. If ``door_north`` is False this is on
                  the south wall; if True, on the north wall.
      occupant:   optional :class:`Entity` to stand inside the
                  building. If provided, its ``pos`` is REASSIGNED
                  to the interior center.
      door_north: if True, the door is placed on the north wall
                  (``y_lo``) and the label is carved into the
                  south wall (``y_hi``). Default False matches
                  the original behaviour.

    Returns:
      ``(tile_changes, entities)``:
        * ``tile_changes`` is a list of ``(Position, Tile)`` pairs.
        * ``entities`` is the list of occupants.

    Raises:
      ValueError: if the rectangle is too small or ``label`` is
        wider than the wall.
    """
    if x_hi - x_lo < 4 or y_hi - y_lo < 4:
        raise ValueError("building must be at least 5x5 to fit walls + interior")
    if len(label) > x_hi - x_lo + 1:
        raise ValueError(
            f"building label {label!r} ({len(label)} chars) "
            f"is wider than the wall ({x_hi - x_lo + 1} cells)"
        )
    if door_x is None:
        door_x = (x_lo + x_hi) // 2

    # Centre the label horizontally on whichever wall it's on.
    label_pad = (x_hi - x_lo + 1 - len(label)) // 2
    label_x_start = x_lo + label_pad

    label_fg: tuple[int, int, int] = BUILDING_LABEL_COLORS.get(
        label, SPACEPORT_LABEL_FG,
    )

    tile_changes: list[tuple[Position, Tile]] = []

    if door_north:
        # --- Flipped layout: door on north wall, label on south wall ---

        # North wall (y = y_lo): door at door_x, WALL elsewhere.
        for x in range(x_lo, x_hi + 1):
            tile_changes.append((Position(x, y_lo), DOOR if x == door_x else WALL))

        # South wall (y = y_hi): label carved in, WALL elsewhere.
        for x in range(x_lo, x_hi + 1):
            if not (label_x_start <= x < label_x_start + len(label)):
                tile_changes.append((Position(x, y_hi), WALL))
        for i, ch in enumerate(label):
            tile_changes.append((
                Position(label_x_start + i, y_hi),
                Tile(kind="label", char=ch, walkable=False, fg=label_fg, bg=WALL.bg),
            ))
    else:
        # --- Default layout: label on north wall, door on south wall ---

        # North wall (y = y_lo): WALL except for the carved label.
        for x in range(x_lo, x_hi + 1):
            if not (label_x_start <= x < label_x_start + len(label)):
                tile_changes.append((Position(x, y_lo), WALL))
        for i, ch in enumerate(label):
            tile_changes.append((
                Position(label_x_start + i, y_lo),
                Tile(kind="label", char=ch, walkable=False, fg=label_fg, bg=WALL.bg),
            ))

        # South wall (y = y_hi): door at door_x, WALL elsewhere.
        for x in range(x_lo, x_hi + 1):
            tile_changes.append((Position(x, y_hi), DOOR if x == door_x else WALL))

    # East and west walls, excluding the top and bottom rows we
    # already wrote above.
    for y in range(y_lo + 1, y_hi):
        tile_changes.append((Position(x_lo, y), WALL))
        tile_changes.append((Position(x_hi, y), WALL))

    entities: list[Entity] = []
    if occupant is not None:
        occupant.pos = Position(
            (x_lo + x_hi) // 2,
            (y_lo + y_hi) // 2,
        )
        entities.append(occupant)

    return tile_changes, entities


def make_space_port(
    x_lo: int, x_hi: int, y_lo: int, y_hi: int,
    *,
    door_x: int | None = None,
    label: str = SPACEPORT_LABEL,
) -> tuple[list[tuple[Position, Tile]], list[Entity]]:
    """Build the space-port building: a labeled rectangular building
    (no NPC) plus the three ships on display inside.

    This is a thin composition over :func:`make_building` plus the
    fixed ship placements. Kept as a separate function so other
    callers can keep using the existing ``(tile_changes, ships)``
    return shape.
    """
    tile_changes, _npcs = make_building(
        label, x_lo, x_hi, y_lo, y_hi, door_x=door_x,
    )

    ships: list[Entity] = [
        Entity(
            char="s",
            fg=(130, 220, 255),                                      # bright sky-blue (greyscale-brightest of the 3)
            pos=Position(x=x_lo + 3, y=y_lo + 2),
            name="Ship: Scout",
            ship_id="scout",
            width=1, height=1,
        ),
        Entity(
            char="H",
            fg=(140, 210, 140),                                      # medium saturated green
            pos=Position(x=x_lo + 7, y=y_lo + 2),
            name="Ship: Hauler",
            ship_id="hauler",
            width=2, height=1,
        ),
        Entity(
            char="C",
            fg=(235, 130, 130),                                      # saturated red - mean-luma ~165, matches hauler for colorblind contrast
            pos=Position(x=x_lo + 11, y=y_lo + 4),
            name="Ship: Cruiser",
            ship_id="cruiser",
            width=2, height=2,
        ),
    ]



    return tile_changes, ships

# ---------------------------------------------------------------------------
# Building-interior decoration
# ---------------------------------------------------------------------------


def _decorate_interiors(
    tiles: list[list[Tile]],
    buildings: tuple[CityBuilding, ...],
) -> None:
    """Paint furniture + detail tiles into building interiors after
    step 7 has filled them with :data:`INTERIOR`.

    Each building label gets its own layout — a cosy bar counter,
    spaceport display pylons, guild-hall furnishings, etc. The NPC
    position (interior centre) is left alone so the occupant stays
    visible.
    """
    _decorate_bar(tiles, buildings)


def _decorate_bar(
    tiles: list[list[Tile]],
    buildings: tuple[CityBuilding, ...],
) -> None:
    """Paint a bar counter with stools and a drinks table.

    Bar is 8\u00d76 (x=34..41, y=8..13), interior is 6\u00d74
    (x=35..40, y=9..12). The barkeep NPC sits at the centre
    (x=37, y=10).

    Layout (key):

        y=9:  \u2591 \u2591 \u2591 \u2591 \u2591 \u2591   counter top
        y=10: \u2592 \u2592 b \u2592 \u2592 \u2592   counter body, barkeep at x=37
        y=11: \u2665 \u00d6 \u2665 \u00d6 \u00b7 \u00b7   drinks + table
        y=12: \u00b7 \u00b7 \u00b7 \u00b7 \u00b7 \u00b7   open walk to door
    """
    bar = next((b for b in buildings if b.label == "bar"), None)
    if bar is None:
        return

    npc_x = (bar.x_lo + bar.x_hi) // 2  # = 37
    npc_y = (bar.y_lo + bar.y_hi) // 2  # = 10

    # Row y=9: full-width counter top.
    for ix in range(bar.x_lo + 1, bar.x_hi):
        tiles[bar.y_lo + 1][ix] = BAR_COUNTER

    # Row y=10: counter body, except the NPC tile.
    for ix in range(bar.x_lo + 1, bar.x_hi):
        if ix != npc_x:
            tiles[npc_y][ix] = BAR_BODY

    # Row y=11: drinks + table pattern (left half of the interior).
    row_11_y = bar.y_lo + 3  # = 11
    drink_positions: list[tuple[int, Tile]] = [
        (bar.x_lo + 1, DRINK),   # x=35
        (bar.x_lo + 2, TABLE),   # x=36
        (bar.x_lo + 3, DRINK),   # x=37
        (bar.x_lo + 4, TABLE),   # x=38
        (bar.x_lo + 5, INTERIOR), # x=39
    ]
    for ix, tile in drink_positions:
        tiles[row_11_y][ix] = tile

    # Row y=12 stays as INTERIOR (set by step 7) — open walkway to door.


# Buildings the city spawns at make_city time. Coords are picked so
# that no two building rectangles overlap, the player can walk
# between them on the new roads, and the south-door of every
# building faces open city floor (no overlap with perimeter walls,
# perimeter city-exit doors, the wandering merchant NPC, or any
# other building).
@dataclass(frozen=True)
class CityBuilding:
    label: str
    x_lo: int
    x_hi: int
    y_lo: int
    y_hi: int
    door_x: int
    npc_id: str
    door_north: bool = False  # True: door on north wall, label on south wall


CITY_BUILDINGS: tuple[CityBuilding, ...] = (
    # Space port (commerce-heavy, NW): 20x10, door at midpoint.
    CityBuilding(label="spaceport", x_lo=4,  x_hi=23, y_lo=3,  y_hi=12, door_x=13, npc_id=""),
    # Bar (small tavern, NE): 8x6, north of the BH guild.
    CityBuilding(label="bar",       x_lo=34, x_hi=41, y_lo=8,  y_hi=13, door_x=37, npc_id="barkeep"),
    # Bounty hunter guild (medium, NE under the bar): 15x11.
    CityBuilding(label="bounties",  x_lo=43, x_hi=57, y_lo=5,  y_hi=15, door_x=50, npc_id="bounty_master"),
    # Merchant guild (big emporium, SW): 21x12.
    CityBuilding(label="merchants", x_lo=4,  x_hi=24, y_lo=25, y_hi=36, door_x=14, npc_id="guild_master"),
    # Militia center (medium barracks, SE): 16x10.
    CityBuilding(label="militia",   x_lo=40, x_hi=55, y_lo=26, y_hi=35, door_x=47, npc_id="militia_captain"),
)


def _layout_outside(
    tiles: list[list[Tile]],
    width: int,
    height: int,
    buildings: tuple[CityBuilding, ...],
    theme: PlanetTheme = EARTH_THEME,
) -> None:
    """Carve roads + plaza + purposeful green spaces into the city.

    The function is sized for the canonical 60x40 planetary city
    template. Smaller planets (e.g. ac_station 40x24) early-return
    so they stay as a bare interior.

    ``theme`` provides per-planet tile colours (grass, roads, plaza,
    landing pad, neon, etc.). Earth uses :data:`EARTH_THEME`; Mars
    passes its own red-dust theme from the planet's data module.

    Overhauls the original full-width-sidewalk + corner-grass-patch
    approach into a more deliberate city layout:

      * 3-tile-wide roads with centre-lane markings (unchanged)
      * 9\u00d79 central plaza with jewel-like fountain diamonds \u2666
      * Narrow (3-tile) walkways from each building door to the road
        instead of blocky full-width sidewalk slabs.
      * Landing pad directly south of the spaceport (unchanged).
      * Two park belts between the E/W road and the bottom-row
        buildings (merchant guild, militia center).
      * Every bare FLOOR cell is converted to GRASS so the city
        doesn't have the "brown with no purpose" look.
      * Tree (\u2663) accents along the N/S road edge, inside parks,
        and at key building gaps.
      * Neon signs still flank the spaceport door and mark plaza
        cardinal points (painted last so they survive overwrites).
    """
    if width != 60 or height != 40:
        return

    # Deterministic seeding so the same planet always looks the same.

    # Unpack the per-planet theme into local aliases used below.
    _grass = theme.grass
    _grass_accent = theme.grass_accent
    _plaza = theme.plaza
    _sidewalk = theme.sidewalk
    _road_surface = theme.road_surface
    _road_ns = theme.road_ns
    _road_ew = theme.road_ew
    _landing_pad = theme.landing_pad
    _neon = theme.neon
    _tree = theme.tree
    _decor = theme.decor

    spaceport = next((b for b in buildings if b.label == "spaceport"), None)

    # ------------------------------------------------------------------
    # 1. 3-tile-wide main roads with centre-lane markings
    # ------------------------------------------------------------------
    # N/S corridor: x = 29, 30, 31  (centre lane at x=30).
    for y in range(1, 17):
        tiles[y][29] = _road_surface
        tiles[y][30] = _road_ns
        tiles[y][31] = _road_surface
    for y in range(24, height - 1):
        tiles[y][29] = _road_surface
        tiles[y][30] = _road_ns
        tiles[y][31] = _road_surface

    # E/W corridor: y = 19, 20, 21  (centre lane at y=20).
    for x in range(1, 27):
        tiles[19][x] = _road_surface
        tiles[20][x] = _road_ew
        tiles[21][x] = _road_surface
    for x in range(34, width - 1):
        tiles[19][x] = _road_surface
        tiles[20][x] = _road_ew
        tiles[21][x] = _road_surface

    # ------------------------------------------------------------------
    # 2. Central plaza (9\u00d79, bridges the 3-wide road gap)
    # ------------------------------------------------------------------
    for y in range(16, 25):
        for x in range(26, 35):
            tiles[y][x] = _plaza

    # ---- 2b. Plaza jewel decorations (diamond \u2666 fountain accents) ----
    # Four tiles at the inner corners of the plaza read as fountain
    # features radiating from the plaza / road crossing.
    for dx, dy in [(28, 18), (32, 18), (28, 22), (32, 22)]:
        if 0 <= dx < width and 0 <= dy < height:
            tiles[dy][dx] = _decor

    # ------------------------------------------------------------------
    # 3. Narrow walkways from each building door to the nearest road
    # ------------------------------------------------------------------
    # Instead of painting _sidewalk across the building's full width,
    # we paint a focused 3-tile-wide path centred on the door. The
    # path extends south until it hits the perimeter wall or a tile
    # that isn't walkable-exterior (e.g. a road tile, which stops
    # the walk so the path doesn't paint over the road itself).
    for spec in buildings:
        door_x = spec.door_x
        path_x_lo = max(door_x - 1, spec.x_lo)
        path_x_hi = min(door_x + 1, spec.x_hi)

        if spec.door_north:
            # Walk NORTH from the north wall towards the road.
            sy = spec.y_lo - 1
            while sy > 0:
                if any(
                    tiles[sy][sx].kind == "road"
                    for sx in range(path_x_lo, path_x_hi + 1)
                ):
                    break
                blocked = any(
                    tiles[sy][sx].kind not in ("floor", "sidewalk", "plaza")
                    for sx in range(path_x_lo, path_x_hi + 1)
                )
                if blocked:
                    break
                for sx in range(path_x_lo, path_x_hi + 1):
                    tiles[sy][sx] = _sidewalk
                sy -= 1
        else:
            # Walk SOUTH from the south wall towards the road (original behaviour).
            sy = spec.y_hi + 1
            while sy < height - 1:
                if any(
                    tiles[sy][sx].kind == "road"
                    for sx in range(path_x_lo, path_x_hi + 1)
                ):
                    break
                blocked = any(
                    tiles[sy][sx].kind not in ("floor", "sidewalk", "plaza")
                    for sx in range(path_x_lo, path_x_hi + 1)
                )
                if blocked:
                    break
                for sx in range(path_x_lo, path_x_hi + 1):
                    tiles[sy][sx] = _sidewalk
                sy += 1

    # ------------------------------------------------------------------
    # 4. Landing pad (south of spaceport) — painted AFTER walkways so
    #    the pad overwrites any _sidewalk the spaceport's path placed
    #    in the tarmac zone.
    # ------------------------------------------------------------------
    if spaceport is not None:
        pad_centre = (spaceport.x_lo + spaceport.x_hi) // 2  # = 14
        pad_x_lo = pad_centre - 5
        pad_x_hi = pad_centre + 5
        for py in range(spaceport.y_hi + 1, 18):
            for px in range(pad_x_lo, pad_x_hi + 1):
                if 0 <= px < width and 0 <= py < height:
                    tiles[py][px] = _landing_pad

    # ------------------------------------------------------------------
    # 5. Neon glowing signs (painted LAST so they survive overwrites)
    # ------------------------------------------------------------------
    # Flanking the spaceport door – one tile each side.
    if spaceport is not None:
        door_col = spaceport.door_x
        neon_y = spaceport.y_hi + 1
        if 0 <= door_col - 1 < width:
            tiles[neon_y][door_col - 1] = _neon
        if 0 <= door_col + 1 < width:
            tiles[neon_y][door_col + 1] = _neon

    # Plaza cardinal-edge neon markers.
    plaza_cx, plaza_cy = 30, 20
    for n_x, n_y in [
        (plaza_cx,    16),   # north edge
        (plaza_cx,    24),   # south edge
        (26, plaza_cy),       # west edge
        (34, plaza_cy),       # east edge
    ]:
        if 0 <= n_x < width and 0 <= n_y < height:
            tiles[n_y][n_x] = _neon

    # ------------------------------------------------------------------
    # 6. Convert ALL remaining bare FLOOR tiles to GRASS
    # ------------------------------------------------------------------
    # This replaces every "brown with no purpose" cell with green
    # space, giving the city a much more intentional look. Everything
    # that came before (roads, plaza, walkways, landing pad, neon) is
    # already carved out, so only truly empty floor is caught here.
    for fy in range(1, height - 1):
        for fx in range(1, width - 1):
            if tiles[fy][fx].kind == "floor":
                # ~15% comma accent, rest solid block.
                tiles[fy][fx] = _grass_accent if random.random() < 0.15 else _grass

    # ------------------------------------------------------------------
    # 7. Repaint building interiors from GRASS back to INTERIOR floor
    # ------------------------------------------------------------------
    # Step 6 converted every FLOOR cell to GRASS, including the inside
    # of every building.  This step restores building interiors to a
    # warm, clean floor tile so the player sees a clear visual contrast
    # when stepping through a door from the grassy outside into a
    # building interior.
    for spec in buildings:
        for iy in range(spec.y_lo + 1, spec.y_hi):
            for ix in range(spec.x_lo + 1, spec.x_hi):
                tiles[iy][ix] = INTERIOR

    # ------------------------------------------------------------------
    # 8. Decorate building interiors with furniture and detail tiles
    # ------------------------------------------------------------------
    _decorate_interiors(tiles, buildings)

    # ------------------------------------------------------------------
    # 9. Tree (\u2663) accents at deliberate fixed positions
    # ------------------------------------------------------------------
    # West edge of the N/S road corridor (x=28).
    for ry in range(1, height - 1):
        if tiles[ry][28].kind in ("grass", "road", "sidewalk"):
            if ry % 4 == 0:
                tiles[ry][28] = _tree

    # East edge (x=32).
    for ry in range(1, height - 1):
        if tiles[ry][32].kind in ("grass", "road", "sidewalk"):
            if ry % 4 == 2:
                tiles[ry][32] = _tree

    # Park south of the E/W road, north of the merchant guild.
    # (14, 24) is omitted because it sits on the merchant's north-facing path.)
    for tx, ty in [(6, 22), (10, 23), (18, 23), (22, 22)]:
        if tiles[ty][tx].kind == "grass":
            tiles[ty][tx] = _tree

    # Park south of the E/W road, north of the militia center.
    # (48, 22) is omitted because it sits on the militia's north-facing path.)
    for tx, ty in [(42, 23), (45, 25), (52, 24)]:
        if tiles[ty][tx].kind == "grass":
            tiles[ty][tx] = _tree


def make_city(width: int = 60, height: int = 40) -> GameMap:
    """Back-compat shim: build the Earth on-surface city from
    :func:`spacehack.data.planets.load_planet`.

    The full city layout (perimeter walls + doors + 5 buildings +
    showroom ships + wandering merchant + roads + plaza + sidewalks
    + grass patch) is now expressed as a :class:`PlanetSpec` literal
    in :mod:`spacehack.data.planets.earth`. This shim keeps every
    pre-refactor call site (``world.make_city()`` from the dispatcher
    and smoke tests) working without a code change.

    ``width``/``height`` are accepted for back-compat but ignored —
    the Earth's spec defines its own grid size (60x40 today).
    """
    from .data.planets import load_planet
    del width, height  # explicit: spec owns the dimensions
    return load_planet("earth")


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# A* pathfinding
# ---------------------------------------------------------------------------


def find_path(
    start: tuple[int, int],
    end_candidates: set[tuple[int, int]],
    game_map: GameMap,
    *,
    exclude_entity: Entity | None = None,
    max_steps: int = 50000,
) -> list[tuple[int, int]] | None:
    """A* shortest path from ``start`` to any cell in ``end_candidates``.

    Performs 8-directional Chebyshev-weighted A* exploration up to
    ``max_steps`` total visited cells. Returns the path as a list of
    ``(x, y)`` tuples (INCLUDING the start, EXCLUDING the end cell)
    so the caller can pop steps one at a time, or ``None`` if no path
    exists.

    ``exclude_entity`` is excluded from collision checks (e.g. the
    entity doing the pathfinding), so the path won't be blocked by
    itself. Other entities still block.

    The returned path is start-to-next-step so the caller can take
    ``path[0]`` as the immediate next cell to move into, and
    ``path[-1]`` is always an end candidate (the goal).

    ``end_candidates`` cells are always considered passable
    regardless of walkability or entity occupancy (the goal is to
    reach that cell).
    """
    import heapq
    dirs_8 = [(0, -1), (-1, 0), (1, 0), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)]

    def _heuristic(a, b):
        return max(abs(a[0] - b[0]), abs(a[1] - b[1]))

    # Pick the closest end candidate as A* target for heuristic guidance.
    best_target = min(end_candidates, key=lambda tc: _heuristic(start, tc))

    counter = 0
    open_set = [(0, counter, start)]
    came_from: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    g_score: dict[tuple[int, int], float] = {start: 0}
    visited: set[tuple[int, int]] = set()
    found = False
    target_reached = None

    while open_set and not found:
        _, _, curr = heapq.heappop(open_set)
        if curr in visited:
            continue
        visited.add(curr)
        if len(visited) > max_steps:
            break
        if curr in end_candidates:
            found = True
            target_reached = curr
            break
        cx, cy = curr
        for dx, dy in dirs_8:
            nx, ny = (cx + dx, cy + dy)
            npos = (nx, ny)
            if not game_map.in_bounds(nx, ny):
                continue
            if npos not in end_candidates:
                if not game_map.is_walkable(nx, ny):
                    continue
                blocker = game_map.entity_at(nx, ny, exclude=exclude_entity)
                if blocker is not None:
                    continue
            tentative_g = g_score.get(curr, 0) + 1
            if tentative_g < g_score.get(npos, 999999):
                came_from[npos] = curr
                g_score[npos] = tentative_g
                f = tentative_g + _heuristic(npos, best_target)
                counter += 1
                heapq.heappush(open_set, (f, counter, npos))

    if not found:
        return None

    path: list[tuple[int, int]] = []
    cur = target_reached
    while cur is not None:
        path.append(cur)
        cur = came_from.get(cur)
    path.reverse()
    # Exclude the start cell from the path (the caller is already there).
    return path[1:]


def render_world(
    console: tcod.console.Console,
    game_map: GameMap,
    *,
    region_x: int,
    region_y: int,
    region_w: int,
    region_h: int,
) -> None:
    """Paint ``game_map`` centred into a viewport region of ``console``.

    Tiles are drawn first (city background appears under each
    entity), then each entity's char is painted at every cell of its
    footprint. A 2x1 ship reads as two glyphs side-by-side; an NPC
    reads as a single glyph at its standing spot. The multi-cell
    collision check in :meth:`GameMap.entity_at` matches.

    Entities are iterated in insertion order; a later entity's paint
    overwrites an earlier one's overlapping cell.
    """
    if game_map.width > region_w or game_map.height > region_h:
        raise ValueError(
            f"city {game_map.width}x{game_map.height} is larger than "
            f"viewport region {region_w}x{region_h}"
        )

    off_x = (region_w - game_map.width) // 2
    off_y = (region_h - game_map.height) // 2

    for ty in range(game_map.height):
        for tx in range(game_map.width):
            # Fog of war: skip unseen tiles (renders as black)
            if not game_map.is_revealed(tx, ty):
                continue
            tile = game_map.tiles[ty][tx]
            console.print(
                x=region_x + off_x + tx,
                y=region_y + off_y + ty,
                string=tile.char,
                fg=tile.fg,
                bg=tile.bg,
            )
    for e in game_map.entities:
        # Skip entities on unseen tiles
        if not game_map.is_revealed(e.pos.x, e.pos.y):
            continue
        for dx in range(e.width):
            for dy in range(e.height):
                ex = e.pos.x + dx
                ey = e.pos.y + dy
                console.print(
                    x=region_x + off_x + ex,
                    y=region_y + off_y + ey,
                    string=e.char,
                    fg=e.fg,
                )


def render_world_view(
    console: tcod.console.Console,
    game_map: GameMap,
    *,
    region_x: int,
    region_y: int,
    region_w: int,
    region_h: int,
    camera_x: int = 0,
    camera_y: int = 0,
) -> None:
    """Scrollable variant of :func:`render_world` that lets ``game_map``
    be larger than the visible region.

    :func:`render_world` raises :class:`ValueError` when ``game_map``
    exceeds the region (city mode is small and centered, so the city
    fits inside the viewport). In space mode the solar-system map is
    much larger than the 80x54 viewport, so the player has to scroll
    to explore - this function is the scrolling-aware primitive that
    consumes ``camera_x``/``camera_y`` from the caller.

    The function reads ``region_w`` x ``region_h`` cells from
    ``game_map`` starting at ``(camera_x, camera_y)`` and paints them
    into ``console`` at ``(region_x, region_y)``. The camera is
    clamped so it never reads past the map bounds, and a defensive
    inner ``if 0 <= map_x < ...`` guard protects against a
    partially-out-of-bounds camera at the map edge.

    Entities are drawn after tiles, footprint-aware (so a multi-cell
    planet renders the same glyph at every cell of its ``width`` x
    ``height``), and only the cells inside the camera viewport are
    emitted (the rest of the footprint is correctly skipped).
    """
    # The ONLY place camera-edge-clamping lives for in-game rendering;
    # the caller computes a ship-centered value and we clamp here
    # defensively so a partly-out-of-bounds camera is safe.
    cam_x = max(
        0, min(camera_x, max(0, game_map.width - region_w)),
    )
    cam_y = max(
        0, min(camera_y, max(0, game_map.height - region_h)),
    )

    for ty in range(region_h):
        for tx in range(region_w):
            map_x = cam_x + tx
            map_y = cam_y + ty
            if 0 <= map_x < game_map.width and 0 <= map_y < game_map.height:
                # Fog of war: skip unseen tiles (renders as black).
                if not game_map.is_revealed(map_x, map_y):
                    continue
                tile = game_map.tiles[map_y][map_x]
                console.print(
                    x=region_x + tx,
                    y=region_y + ty,
                    string=tile.char,
                    fg=tile.fg,
                    bg=tile.bg,
                )

    # Draw loot entities first (cargo debris), then ships/entities
    # on top. Loot has loot_data set; sorting with key=lambda e:
    # e.loot_data is None puts loot (False=0) before ships (True=1)
    # while preserving insertion order for same-key entities.
    #
    # Viewport cull: only sort + iterate entities touching the
    # visible camera region.  Avoids O(n log n) on hundreds of
    # off-screen loot entities accumulated from large battles.
    _visible = [
        _e for _e in game_map.entities
        if (_e.pos.x < cam_x + region_w and _e.pos.x + _e.width > cam_x
            and _e.pos.y < cam_y + region_h and _e.pos.y + _e.height > cam_y)
    ]
    for e in sorted(_visible, key=lambda _e: _e.loot_data is None):
        # Fog of war: skip entities on unrevealed cells.
        if not game_map.is_revealed(e.pos.x, e.pos.y):
            continue
        for dx in range(e.width):
            for dy in range(e.height):
                ex = e.pos.x + dx
                ey = e.pos.y + dy
                # Only paint cells whose footprint intersects the
                # visible camera viewport; the rest of the entity is
                # correctly skipped (no negative console coords).
                if (
                    cam_x <= ex < cam_x + region_w
                    and cam_y <= ey < cam_y + region_h
                ):
                    sx_screen = region_x + (ex - cam_x)
                    sy_screen = region_y + (ey - cam_y)
                    console.print(
                        x=sx_screen,
                        y=sy_screen,
                        string=e.char,
                        fg=e.fg,
                    )


# ---------------------------------------------------------------------------
# Movement actions
# ---------------------------------------------------------------------------


# Vim-style movement: lowercase letter -> (dx, dy) in city-space, where
# y increases downward (matching tcod's convention). The standard
# roguelike layout is h/j/k/l for cardinals and y/u/b/n for diagonals.
# tcod's KeySym reports physical letter key presses as UPPERCASE
# members (KeySym.H, KeySym.J, ...) which we lowercase for lookup, see
# ``spacehack.__main__._vim_action``.
VIM_DELTAS: dict[str, tuple[int, int]] = {
    "h": (-1,  0),  # west
    "j": ( 0,  1),  # south
    "k": ( 0, -1),  # north
    "l": ( 1,  0),  # east
    "y": (-1, -1),  # north-west
    "u": ( 1, -1),  # north-east
    "b": (-1,  1),  # south-west
    "n": ( 1,  1),  # south-east
}


def try_move(
    entity: Entity,
    game_map: GameMap,
    dx: int,
    dy: int,
) -> tuple[str, Entity | None]:
    """Attempt to move ``entity`` by ``(dx, dy)`` on ``game_map``.

    Returns a ``(code, blocker)`` pair:

      * ``code == "moved"``: success; ``entity.pos`` was updated and
        ``blocker`` is ``None``.
      * ``code == "wall"``: target tile was out-of-bounds or
        unwalkable; ``blocker`` is ``None``.
      * ``code == "occupied"``: target tile was walkable but inside
        some other entity's footprint (so multi-cell ships block on
        every covered cell); ``blocker`` is that entity.

    Returning the blocker with the code lets callers either log a
    player-facing message or open a ship-buy / npc-talk dialog
    without reverse-engineering the target tile.
    """
    target_x = entity.pos.x + dx
    target_y = entity.pos.y + dy
    if not game_map.is_walkable(target_x, target_y):
        return ("wall", None)
    blocker = game_map.entity_at(target_x, target_y, exclude=entity)
    if blocker is not None:
        return ("occupied", blocker)
    entity.pos = Position(target_x, target_y)
    return ("moved", None)


def try_vim_move(
    entity: Entity,
    game_map: GameMap,
    letter: str,
) -> tuple[str, Entity | None] | None:
    """If ``letter`` is a known vim movement key, dispatch to
    :func:`try_move` using that key's delta.

    Returns the same ``(code, blocker)`` shape as :func:`try_move`,
    or ``None`` if ``letter`` isn't a movement key.
    """
    delta = VIM_DELTAS.get(letter)
    if delta is None:
        return None
    return try_move(entity, game_map, delta[0], delta[1])
