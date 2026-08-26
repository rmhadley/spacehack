"""Core game-world module: tiles, entities, maps, and movement.

This module owns the shared tile catalog, the :class:`Entity` /
:class:`GameMap` runtime model, the movement helpers, and transit-stop data
(:class:`TransitStation`). Cohesive siblings hold the city building/layout
pass (:mod:`spacehack.world_layout`), the renderer-neutral draw commands
(:mod:`spacehack.world_render`), and A* pathfinding (:mod:`spacehack.world_path`);
this module re-exports their public helpers so existing ``world.<name>``
call sites keep working unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass


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
    bg_override: bool = False  # layout-authored background, not a theme default
    blocked_message: str = "A wall blocks your path."


WALL = Tile(kind="wall", char="▓", walkable=False, fg=(155, 185, 215), bg=(50, 62, 78))     # dark shade — paneled bulkhead (perimeter)

# Box-drawing wall tiles for building exteriors.  These use
# single-line box-drawing glyphs that render cleanly in any
# monospace CP437 bitmap font and connect into continuous
# architectural frames with proper corners.
WALL_TL = Tile(kind="wall", char="┌", walkable=False, fg=(155, 185, 215), bg=(50, 62, 78))  # top-left corner
WALL_TR = Tile(kind="wall", char="┐", walkable=False, fg=(155, 185, 215), bg=(50, 62, 78))  # top-right corner
WALL_BL = Tile(kind="wall", char="└", walkable=False, fg=(155, 185, 215), bg=(50, 62, 78))  # bottom-left corner
WALL_BR = Tile(kind="wall", char="┘", walkable=False, fg=(155, 185, 215), bg=(50, 62, 78))  # bottom-right corner
WALL_H  = Tile(kind="wall", char="─", walkable=False, fg=(155, 185, 215), bg=(50, 62, 78))  # horizontal
WALL_V  = Tile(kind="wall", char="│", walkable=False, fg=(155, 185, 215), bg=(50, 62, 78))  # vertical
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

# Open paved plaza — light shade reads as a paved square
PLAZA = Tile(kind="plaza", char="░", walkable=True, fg=(240, 230, 215), bg=(190, 180, 165))  # light shade on cream base

# Sidewalk edge strips (medium shade)
SIDEWALK = Tile(kind="sidewalk", char="▒", walkable=True, fg=(140, 145, 170), bg=(75, 80, 100))

# Grass / green space — full block reads as solid green fields. The fg
# IS the field colour: █ paints the whole cell, so fg carries the dark
# ground tone players expect (fg used to be a bright tint that only
# worked while █ drew background-only).
GRASS = Tile(kind="grass", char="█", walkable=True, fg=(40, 80, 35), bg=(40, 80, 35))

# Grass accent — comma adds a little texture without overwhelming.
# Keep the same dark field background as GRASS; the comma gets its own
# darker green accent so it reads as texture without inverting the tile.
GRASS_ACCENT = Tile(kind="grass", char=",", walkable=True, fg=(57, 100, 47), bg=(40, 80, 35))

# Landing pad — tarmac with a cool sci-fi blue glow (replaces generic
# sidewalk south of the spaceport with a dedicated ship-parking area).
LANDING_PAD = Tile(kind="landing_pad", char="▓", walkable=True, fg=(100, 210, 255), bg=(25, 45, 70))

# Neon accent — decorative glowing marker outside the spaceport
# entrance and at plaza edges. Using `*` char (classic sparkle / star)
# with bright gold-white fg so it pops against the dark asphalt
# without needing a unicode star glyph that may not exist in the
# terminal font.
NEON = Tile(kind="neon", char="*", walkable=True, fg=(255, 220, 100), bg=(40, 25, 12))

# Decorative tree — club suit reads as foliage.
TREE = Tile(kind="tree", char="♣", walkable=True, fg=(90, 180, 85), bg=(30, 65, 25))

# Decorative plaza feature — diamond reads as a jewel / fountain.
DECOR = Tile(kind="plaza", char="♦", walkable=True, fg=(255, 160, 120), bg=(190, 180, 165))

# Public landmark monument — bright beacon on dark stone base.
# High-contrast cyan diamond so the monument is immediately visible
# from across the city.
MONUMENT = Tile(kind="monument", char="♦", walkable=True, fg=(100, 240, 255), bg=(28, 48, 60))

# Interior building floor — warmer, brighter variant so it reads as a
# clean indoor surface distinct from the outdoor GRASS tiles.
#
# The char is a BLANK: a flat, smooth floor with no dot texture so
# ships, NPCs and furniture glyphs stay easy to read. (A middot like
# FLOOR's was tried first — the dotted pattern visually drowned out
# entities standing on it.) The warm bg still marks the indoor look.
INTERIOR = Tile(kind="floor", char=" ", walkable=True, fg=(245, 225, 175), bg=(130, 108, 70))

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
# Act 0's revealed Mars stairs are deliberately distinct from EXIT: they
# are a persistent story marker that enters the Act 1 alien-prison extension,
# rather than returning the player to space.
STAIRS_DOWN = Tile(kind="stairs_down", char=">", walkable=True,
                   fg=(130, 255, 180), bg=(20, 55, 35))
STAIRS_UP = Tile(kind="stairs_up", char="<", walkable=True,
                 fg=(150, 220, 255), bg=(20, 45, 65))
# Procedural extension feature tiles. They are walkable visual markers rather
# than entities, so cell doors, posts, and barriers never block pathfinding.
PRISON_CELL_DOOR = Tile(kind="prison_cell_door", char="|", walkable=True,
                        fg=(170, 230, 255), bg=(35, 55, 75))
SECURITY_POST = Tile(kind="security_post", char="+", walkable=True,
                     fg=(120, 255, 220), bg=(25, 65, 65))
DEFENSE_BARRIER = Tile(kind="defense_barrier", char="=", walkable=True,
                       fg=(255, 180, 100), bg=(75, 45, 30))
SECURITY_NODE = Tile(kind="security_node", char="*", walkable=True,
                     fg=(255, 100, 100), bg=(70, 25, 30))
HIGH_RISK_CELL_DOOR = Tile(kind="high_risk_cell_door", char="|", walkable=True,
                           fg=(220, 245, 255), bg=(45, 65, 90))
ALIEN_ELEVATOR = Tile(kind="alien_elevator", char="E", walkable=True,
                      fg=(160, 240, 255), bg=(35, 70, 95))
ENGINEERING_FLOOR = Tile(kind="engineering_floor", char="=", walkable=True,
                         fg=(180, 220, 240), bg=(45, 60, 75))
# Deep-cell (Floor 5) set dressing. Walkable visual markers so they
# never block pathfinding or movement, matching the other extension
# feature tiles.
DEEP_CELL_FLOOR = Tile(kind="deep_cell_floor", char=".", walkable=True,
                       fg=(190, 200, 215), bg=(35, 45, 60))
TORN_DOOR = Tile(kind="torn_door", char="#", walkable=False,
                 fg=(200, 130, 90), bg=(60, 35, 30))
CLAW_SCAR = Tile(kind="claw_scar", char="^", walkable=True,
                 fg=(220, 145, 100), bg=(55, 40, 45))
BRIDGE = Tile(kind="bridge", char="=", walkable=True,
              fg=(100, 180, 220), bg=(18, 28, 48))
TERMINAL_LANDING = Tile(kind="terminal_landing", char=".", walkable=True,
                        fg=(175, 195, 215), bg=(38, 48, 65))
LANDMARK_ENTRANCE = Tile(kind="landmark_entrance", char="X", walkable=True,
                         fg=(255, 150, 90), bg=(70, 35, 25))
# Alien landmark tiles.  The landmark parser resolves these names from
# ``TILE:`` directives; the console itself is an entity so bumping it can
# run the Act 0 interaction without conflating it with a generic computer.
DOOR_CONSOLE = Tile(kind="door_console", char="C", walkable=True,
                     fg=(255, 200, 80), bg=(50, 35, 20))
UNDULATING_DOOR_A = Tile(kind="alien_door", char="=", walkable=False,
                         fg=(120, 130, 150), bg=(30, 35, 45))
UNDULATING_DOOR_B = Tile(kind="alien_door", char="~", walkable=False,
                         fg=(120, 130, 150), bg=(30, 35, 45))

# Hull wall — blocks movement like DUNGEON_WALL but does NOT block
# FOV raycasting, so structural groups ({##}) on the ship exterior
# can be seen through. The layout parser replaces # tiles within
# {…} groups with this tile.
HULL_WALL = Tile(kind="hull_wall", char="#", walkable=False,
                 fg=(120, 130, 150), bg=(30, 35, 45))

# --- Building-interior furniture tiles ---
# Bar counter top (warm golden wood).
BAR_COUNTER = Tile(kind="floor", char="░", walkable=True, fg=(210, 165, 90), bg=(120, 100, 65))
# Bar counter body / front (darker wood grain).
BAR_BODY = Tile(kind="floor", char="▒", walkable=True, fg=(160, 120, 70), bg=(90, 75, 50))
# Table surface (≈ reads as a wavy table surface).
TABLE = Tile(kind="floor", char="~", walkable=True, fg=(255, 200, 80), bg=(130, 108, 70))
# Drink glass (♥ bright red for contrast against warm floor).
DRINK = Tile(kind="floor", char="♥", walkable=True, fg=(255, 60, 60), bg=(130, 108, 70))

# Mars colony interior fixtures. These are deliberately generic floor markers
# rather than blocking walls: room circulation stays clear while each room
# reads as engineered infrastructure instead of a recolored Earth interior.
MARS_CONSOLE = Tile(kind="floor", char="c", walkable=True, fg=(95, 245, 255), bg=(24, 62, 76))
MARS_HOLO = Tile(kind="floor", char="*", walkable=True, fg=(150, 245, 255), bg=(28, 68, 82))
MARS_PARTITION = Tile(kind="floor", char="=", walkable=True, fg=(195, 220, 225), bg=(48, 68, 76))
MARS_BENCH = Tile(kind="floor", char="_", walkable=True, fg=(230, 178, 92), bg=(72, 52, 36))
MARS_SIGNAL = Tile(kind="floor", char="!", walkable=True, fg=(255, 170, 72), bg=(76, 44, 26))


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
    main_quest_console: bool = False  # Act 0 alien-door console — interactable
    loot_data: dict | None = None  # {"good_id": str, "quantity": int} — set for cargo loot entities
    npc_char_id: str = ""  # references NpcCharSpec.id for ground-combat NPCs
    squad_id: str = ""  # groups spawned enemies into packs (movement/spawns only — combat uses LOS aggro, not squads)
    hp: int = 0  # ground-combat wound persistence: 0 = unengaged (full HP at first fight)
    main_quest_door: bool = False  # sealed alien door on Mars — main-quest bump target
    main_quest_step_id: str = ""  # quest cache / salvage loot — which main-quest step securing it completes
    transit_station_id: str = ""  # city transit stop — bump opens the station menu
    dungeon_interaction: str = ""  # reusable themed-extension interaction id
    interaction_flavor: str = ""  # bump text for non-interactive set-dressing (inactive terminals)
    last_seen_pos: Position | None = None  # ground hunter's remembered player cell
    last_seen_ticks: int = 0  # remaining dungeon ticks to pursue that cell
    city_npc_id: str = ""  # ambient city citizen — placed/moved by city_npcs
    city_spawn: Position | None = None  # ambient anchor; wander returns here
    city_wander_radius: int = 0  # district radius around city_spawn for destination picks
    city_move_chance: float = 0.0  # probability of a step per city tick
    city_rng: object | None = None  # per-NPC seeded RNG for deterministic wander
    city_dest: tuple | None = None  # current pavement destination (x, y); None = repick
    city_path: list | None = None  # cached A* path to city_dest (persisted across ticks)
    city_blocked_ticks: int = 0  # consecutive blocked steps; >= 4 drops the destination
    city_pause_ticks: int = 0  # ticks to wait after arriving at a destination
    blocked_message: str = "You bump into {name}."


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
    # Fog-of-war. ``seen`` is permanent memory (True = explored / revealed
    # at some point); ``visible`` is the CURRENT line-of-sight frame
    # (True = in LOS right now). Both are ``None`` on maps without fog
    # (city, space). ``visible`` is derived state — recomputed by
    # ``dungeon.reveal_around`` on every player move / entry / load, so
    # it is NOT serialized (see the save/load contract).
    seen: list[list[bool]] | None = None
    visible: list[list[bool]] | None = None
    sight_radius: int = 8  # dungeon fog sight radius; increased by power restore (20)
    # City public-transit topology: {station_id: {"name", "district",
    # "pos", "destinations"}}. Built by ``city_transit.place_transit_stations``
    # on city maps; consumed by the station bump flow. Not serialized —
    # city maps rebuild deterministically on load.
    city_transit: dict | None = None  # filled only on city maps (see city_transit.py)
    # Decorative-skyline building footprints ``[(x, y, w, h), ...]`` placed
    # by the city builder; used by tests to assert density/variety. City map
    # only — absent (None) elsewhere.
    skyline_placements: list | None = None
    # Authored city landmark metadata. City layouts populate these fields;
    # non-city maps leave them at their empty defaults.
    landmark_stamps: dict | None = None
    # Optional rotating-ring station geometry for non-rectangular city layouts.
    ring_geometry: dict | None = None
    ring_void_cells: set[tuple[int, int]] | None = None
    canyon_cells: set[tuple[int, int]] | None = None
    cave_cells: set[tuple[int, int]] | None = None
    bridge_crossings: tuple | None = None


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

    def blocking_entity_at(
        self,
        x: int,
        y: int,
        *,
        exclude: Entity | None = None,
    ) -> Entity | None:
        """Return the first solid entity at ``(x, y)``.

        Loot is an interactable floor object, not a physical obstacle.
        Movement and pathfinding use this lookup so cargo drops never
        seal a corridor or trap a combatant.
        """
        for _entity in self.entities:
            if _entity is exclude or _entity.loot_data is not None:
                continue
            if (
                _entity.pos.x <= x < _entity.pos.x + _entity.width
                and _entity.pos.y <= y < _entity.pos.y + _entity.height
            ):
                return _entity
        return None

    def loot_at(self, x: int, y: int) -> Entity | None:
        """Return the loot entity occupying ``(x, y)``, if any."""
        for _entity in self.entities:
            if _entity.loot_data is None:
                continue
            if (
                _entity.pos.x <= x < _entity.pos.x + _entity.width
                and _entity.pos.y <= y < _entity.pos.y + _entity.height
            ):
                return _entity
        return None

    def replace_tile(self, x: int, y: int, tile: Tile) -> None:
        self.tiles[y][x] = tile

    def is_revealed(self, x: int, y: int) -> bool:
        """Whether a cell is revealed by fog of war (remembered).

        Returns ``True`` if there's no fog (city/space maps) or the
        cell has been explored at some point.
        """
        if self.seen is None:
            return True
        if not self.in_bounds(x, y):
            return False
        return self.seen[y][x]

    def is_visible(self, x: int, y: int) -> bool:
        """Whether a cell is in the CURRENT line of sight.

        Returns ``True`` if there's no fog, or when the LOS grid is
        missing (a freshly deserialized dungeon before its first
        ``reveal_around``) — in both cases every revealed cell counts
        as visible, matching the no-fog fallback.
        """
        if self.visible is not None:
            if not self.in_bounds(x, y):
                return False
            return self.visible[y][x]
        return self.is_revealed(x, y)




# A city transit stop. Pure data so a planet can author its own network.
@dataclass(frozen=True)
class TransitStation:
    """One public transit stop in a planetary city.

    ``id`` is a stable catalog key; ``pos`` is the map cell the station
    occupies (walkable, bump to travel); ``destinations`` lists the
    station ids reachable from here.
    """

    id: str
    name: str
    district: str
    pos: Position
    destinations: tuple[str, ...] = ()
    glyph: str = "\u25c9"                      # high-visibility transit-stop marker
    fg: tuple[int, int, int] = (255, 215, 100)  # warm gold - distinct from terminals


# ---------------------------------------------------------------------------
# Movement actions
# ---------------------------------------------------------------------------


# Vim-style movement: lowercase letter -> (dx, dy) in city-space, where
# y increases downward.
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

ARROW_DELTAS: dict[str, tuple[int, int]] = {
    "up":    ( 0, -1),  # north
    "down":  ( 0,  1),  # south
    "left":  (-1,  0),  # west
    "right": ( 1,  0),  # east
}

NUMPAD_DELTAS: dict[str, tuple[int, int]] = {
    "kp_7": (-1, -1),  # north-west
    "kp_8": ( 0, -1),  # north
    "kp_9": ( 1, -1),  # north-east
    "kp_4": (-1,  0),  # west
    "kp_6": ( 1,  0),  # east
    "kp_1": (-1,  1),  # south-west
    "kp_2": ( 0,  1),  # south
    "kp_3": ( 1,  1),  # south-east
}

MOVE_KEYS: dict[str, tuple[int, int]] = {
    **VIM_DELTAS,
    **ARROW_DELTAS,
    **NUMPAD_DELTAS,
}


def find_loot_near(
    game_map: GameMap,
    position: Position,
) -> Entity | None:
    """Find loot on the current cell or any adjacent cell (cardinals first)."""
    _positions = (
        position,
        Position(position.x, position.y - 1),
        Position(position.x + 1, position.y),
        Position(position.x, position.y + 1),
        Position(position.x - 1, position.y),
        Position(position.x - 1, position.y - 1),
        Position(position.x + 1, position.y - 1),
        Position(position.x - 1, position.y + 1),
        Position(position.x + 1, position.y + 1),
    )
    for _position in _positions:
        _loot = game_map.loot_at(_position.x, _position.y)
        if _loot is not None:
            return _loot
    return None


def try_move(
    entity: Entity,
    game_map: GameMap,
    dx: int,
    dy: int,
) -> tuple[str, Tile | Entity | None]:
    """Attempt to move ``entity`` by ``(dx, dy)`` on ``game_map``.

    Returns a ``(code, blocker)`` pair: ``"moved"`` on success (blocker
    ``None``), ``"wall"`` on an out-of-bounds/unwalkable target (blocker the
    :class:`Tile` when in bounds), or ``"occupied"`` when another entity's
    footprint blocks the target (blocker that entity).
    """
    target_x = entity.pos.x + dx
    target_y = entity.pos.y + dy
    if not game_map.in_bounds(target_x, target_y):
        return ("wall", None)
    target_tile = game_map.tiles[target_y][target_x]
    if not target_tile.walkable:
        return ("wall", target_tile)
    blocker = game_map.blocking_entity_at(target_x, target_y, exclude=entity)
    if blocker is not None:
        return ("occupied", blocker)
    entity.pos = Position(target_x, target_y)
    return ("moved", None)


def blocked_message_for(blocker: Tile | Entity | None) -> str:
    """Return the player-facing message owned by a movement blocker."""
    if blocker is None:
        return "A wall blocks your path."
    if isinstance(blocker, Entity):
        return blocker.blocked_message.replace("{name}", blocker.name)
    return blocker.blocked_message


def try_vim_move(
    entity: Entity,
    game_map: GameMap,
    letter: str,
) -> tuple[str, Tile | Entity | None] | None:
    """Dispatch ``letter`` through :func:`try_move`, or ``None`` if not a vim key."""
    delta = VIM_DELTAS.get(letter)
    if delta is None:
        return None
    return try_move(entity, game_map, delta[0], delta[1])


def _step_cell(entity: Entity, game_map: GameMap, mx: int, my: int) -> bool:
    """Move ``entity`` onto ``(mx, my)`` if walkable and unoccupied."""
    x, y = entity.pos.x + mx, entity.pos.y + my
    if (game_map.is_walkable(x, y)
            and game_map.blocking_entity_at(x, y, exclude=entity) is None):
        entity.pos = Position(x, y)
        return True
    return False


def _perp_slips(dx: int, dy: int) -> tuple[tuple[int, int], ...]:
    """Return the perpendicular slip offsets for a blocked ``(dx, dy)`` step."""
    if dx != 0 and dy != 0:
        return ((dx, 0), (0, dy))
    if dx != 0:
        return ((dx, 1), (dx, -1), (0, 1), (0, -1))
    if dy != 0:
        return ((1, dy), (-1, dy), (1, 0), (-1, 0))
    return ()


def try_step_with_slip(
    entity: Entity,
    game_map: GameMap,
    dx: int,
    dy: int,
) -> bool:
    """Step one cell; on a blocked cell fall back to one perpendicular slip.

    Returns ``True`` only when the DIRECT step succeeded — a successful slip
    returns ``False`` so path-following callers keep their next cell.
    """
    if _step_cell(entity, game_map, dx, dy):
        return True
    for slip in _perp_slips(dx, dy):
        if _step_cell(entity, game_map, slip[0], slip[1]):
            return False
    return False


# ---------------------------------------------------------------------------
# Back-compat re-exports (cohesive siblings hold the implementations)
# ---------------------------------------------------------------------------
from .world_layout import (  # noqa: E402  (imported after definitions)
    SPACEPORT_LABEL, SPACEPORT_LABEL_FG, BUILDING_LABEL_COLORS,
    CityBuilding, CITY_BUILDINGS,
    make_building, make_space_port, _decorate_interiors, _decorate_bar,
    _layout_outside, make_city,
)
from .world_path import find_path  # noqa: E402
from .world_render import (  # noqa: E402
    WorldDrawCommand, world_draw_commands,
    render_world, render_world_view, camera_for_view,
    _dim_color, _is_static_entity, _tile_render_colors, _entity_render_fg,
    _append_tile_commands, _append_entity_commands,
)

# Public API of this module (including the re-exported sibling helpers).
__all__ = [
    "Tile", "Position", "Entity", "GameMap", "TransitStation",
    "CityBuilding", "CITY_BUILDINGS",
    "SPACEPORT_LABEL", "SPACEPORT_LABEL_FG", "BUILDING_LABEL_COLORS",
    "make_building", "make_space_port", "_decorate_interiors",
    "_decorate_bar", "_layout_outside", "make_city",
    "find_path",
    "WorldDrawCommand", "world_draw_commands", "render_world",
    "render_world_view", "camera_for_view",
    "_dim_color", "_is_static_entity", "_tile_render_colors",
    "_entity_render_fg", "_append_tile_commands", "_append_entity_commands",
    "VIM_DELTAS", "ARROW_DELTAS", "NUMPAD_DELTAS", "MOVE_KEYS",
    "find_loot_near", "try_move", "blocked_message_for",
    "try_vim_move", "try_step_with_slip",
]
