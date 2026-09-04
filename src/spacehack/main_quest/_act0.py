"""Main quest Act 0: signal trigger, Mars door, full-screen overlays, gate popups."""

from __future__ import annotations

from collections import deque
from enum import Enum, auto

from .. import message_log
from .. import animation_timing
from .. import ui
from .. import dungeon
from .. import landmark
from .. import world
from ..engine import (
    HUD_WIDTH,
    MSG_LOG_HEIGHT,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    make_console,
)
from ..text import get as t_get
from ..data.main_quest import find_main_quest_step, main_quest_step_after
from ._scenes import play_scene
from ._core import (
    STATUS_ACTIVE,
    STATUS_AVAILABLE,
    STATUS_COMPLETED,
    step_status,
    start_step,
    complete_step,
    _iter_known_steps,
    _active_objective_step,
    _complete_bump_objective,
)

_SIGNAL_SYSTEM_ID = "sol"

_SIGNAL_DOOR_WAVE_FRAMES: tuple[str, ...] = (
    "~=~=~=~",
    "=~=~=~=",
    "~=~=~=~",
    "=~=~=~=",
    "~=~=~=~",
)

def _signal_door_frames(width: int) -> tuple[str, ...]:
    """Build wave and center-split frames for an alien door barrier."""
    if width < 1:
        return ()
    if width == len(_SIGNAL_DOOR_WAVE_FRAMES[0]):
        _wave = _SIGNAL_DOOR_WAVE_FRAMES
        _base = _wave[0]
    else:
        _base = "".join("=" if _i % 2 else "~" for _i in range(width))
        _wave = tuple(
            _base if _i % 2 == 0 else _base.translate(str.maketrans("=~", "~="))
            for _i in range(len(_SIGNAL_DOOR_WAVE_FRAMES))
        )
    _centre = width // 2
    _split = tuple(
        "".join(
            " " if abs(_i - _centre) < _radius else _base[_i]
            for _i in range(width)
        )
        for _radius in range(1, _centre + 2)
    )
    return _wave + _split

# ---------------------------------------------------------------------------
# Signal trigger
# ---------------------------------------------------------------------------

def maybe_trigger_signal(ctx, system_id: str) -> bool:
    """Fire the prologue signal on the first jump out of Sol."""
    if system_id != _SIGNAL_SYSTEM_ID:
        return False
    if step_status(ctx, "prologue_signal") in (STATUS_ACTIVE, STATUS_COMPLETED):
        return False
    ctx.main_quest_progress["prologue_signal"] = STATUS_AVAILABLE
    ctx.log.add_colored(
        t_get("runtime.signal_log_static"),
        message_log.COLOR_IMPORTANT_EVENT,
    )
    ctx.log.add(t_get("runtime.signal_log_coordinates"))
    complete_step(ctx, "prologue_signal")
    return True

# ---------------------------------------------------------------------------
# Farthest-walkable BFS (shared by Mars door + delve sites)
# ---------------------------------------------------------------------------

def _farthest_walkable(game_map: world.GameMap, spawn: world.Position) -> world.Position:
    """Walkable cell farthest from ``spawn`` (BFS over walkable tiles)."""
    _start = (spawn.x, spawn.y)
    if not game_map.tiles[_start[1]][_start[0]].walkable:
        for _yy in range(game_map.height):
            for _xx in range(game_map.width):
                if game_map.tiles[_yy][_xx].walkable:
                    _start = (_xx, _yy)
                    break
            if game_map.tiles[_start[1]][_start[0]].walkable:
                break
    _dist: dict[tuple[int, int], int] = {_start: 0}
    _queue: deque[tuple[int, int]] = deque([_start])
    _far = _start
    while _queue:
        _x, _y = _queue.popleft()
        _d = _dist[(_x, _y)]
        if _d > _dist[_far]:
            _far = (_x, _y)
        for _nx, _ny in ((_x + 1, _y), (_x - 1, _y), (_x, _y + 1), (_x, _y - 1)):
            if not (0 <= _nx < game_map.width and 0 <= _ny < game_map.height):
                continue
            if (_nx, _ny) in _dist:
                continue
            if game_map.tiles[_ny][_nx].walkable:
                _dist[(_nx, _ny)] = _d + 1
                _queue.append((_nx, _ny))
    return world.Position(_far[0], _far[1])

# ---------------------------------------------------------------------------
# Mars surface + sealed door
# ---------------------------------------------------------------------------

def prepare_mars_surface(ctx, game_map: world.GameMap, spawn: world.Position) -> None:
    """Stamp the Mars signal landmark into the fresh surface dungeon."""
    if step_status(ctx, "prologue_mars_unlocked") == STATUS_AVAILABLE:
        complete_step(ctx, "prologue_mars_unlocked")
    if step_status(ctx, "prologue_mars_entrance") == STATUS_AVAILABLE:
        start_step(ctx, "prologue_mars_entrance")
    if step_status(ctx, "prologue_open") != STATUS_COMPLETED:
        _landmark = landmark.load_landmark("mars_signal_door")
        _stamp = landmark.stamp_landmark(game_map, _landmark, spawn)
        if _stamp.console is None or _stamp.stairs is None:
            raise ValueError(
                "Mars signal landmark must define a console and stairs"
            )
        game_map.mars_stairs_pos = _stamp.stairs
        _conceal_mars_stairs(game_map, _stamp.stairs)
        # The landmark's console replaces the old abstract one-tile door.
        # Guardians are placed after the stamp so they stay near the actual
        # console/entrance and the finished map can be cached unchanged.
        _spawn_cache_guardian(game_map, _stamp.console, "mars")

def _conceal_mars_stairs(
    game_map: world.GameMap,
    stairs: world.Position,
) -> None:
    """Hide the Mars stairs behind a themed wall until the seal opens."""
    if not game_map.in_bounds(stairs.x, stairs.y):
        return
    _wall = next(
        (
            _tile
            for _row in game_map.tiles
            for _tile in _row
            if _tile.kind == "dungeon_wall"
        ),
        world.DUNGEON_WALL,
    )
    game_map.tiles[stairs.y][stairs.x] = _wall

def _signal_door_barrier(game_map: world.GameMap) -> list[world.Position]:
    """Return one contiguous authored alien barrier, ordered left-to-right."""
    _positions = sorted(
        (
            world.Position(x, y)
            for y, row in enumerate(game_map.tiles)
            for x, tile in enumerate(row)
            if tile.kind == "alien_door"
        ),
        key=lambda _pos: (_pos.y, _pos.x),
    )
    if not _positions:
        return []
    _row = _positions[0].y
    if any(_position.y != _row for _position in _positions):
        return []
    if any(
        _left.x + 1 != _right.x
        for _left, _right in zip(_positions, _positions[1:])
    ):
        return []
    return _positions

def _signal_door_screen_pos(
    position: world.Position,
    camera_x: int,
    camera_y: int,
    region_x: int,
    region_y: int,
) -> tuple[int, int]:
    """Translate a map position into the current dungeon viewport."""
    return (
        region_x + position.x - camera_x,
        region_y + position.y - camera_y,
    )

def _draw_door_frame_glyph(
    console,
    game_map: world.GameMap,
    position: world.Position,
    glyph: str,
    camera_x: int,
    camera_y: int,
    region_x: int,
    region_y: int,
    map_w: int,
    map_h: int,
) -> None:
    """Print one animation glyph over its tile if it is on screen."""
    _screen_x, _screen_y = _signal_door_screen_pos(
        position, camera_x, camera_y, region_x, region_y,
    )
    if 0 <= _screen_x < map_w and 0 <= _screen_y < map_h:
        _tile = game_map.tiles[position.y][position.x]
        console.print(
            x=_screen_x, y=_screen_y, string=glyph,
            fg=_tile.fg, bg=_tile.bg,
        )


def _render_signal_door_frame(
    ctx,
    console,
    game_map: world.GameMap,
    player_pos: world.Position,
    barrier: list[world.Position],
    frame: str,
) -> None:
    """Render one signal-door animation frame and present it."""
    _map_w = SCREEN_WIDTH - HUD_WIDTH
    _map_h = SCREEN_HEIGHT - MSG_LOG_HEIGHT
    _camera_x, _camera_y, _region_x, _region_y = world.camera_for_view(
        game_map,
        player_pos,
        region_w=_map_w,
        region_h=_map_h,
    )
    console.clear()
    world.render_world_view(
        console,
        game_map,
        region_x=_region_x,
        region_y=_region_y,
        region_w=_map_w,
        region_h=_map_h,
        camera_x=_camera_x,
        camera_y=_camera_y,
    )
    for _position, _glyph in zip(barrier, frame):
        _draw_door_frame_glyph(
            console, game_map, _position, _glyph,
            _camera_x, _camera_y, _region_x, _region_y,
            _map_w, _map_h,
        )
    ctx.context.present(console)

def _landmark_floor_near_barrier(
    game_map: world.GameMap,
    barrier: list[world.Position],
) -> world.Tile:
    """Find the floor style immediately adjacent to the alien barrier."""
    for _position in barrier:
        for _dx, _dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            _x = _position.x + _dx
            _y = _position.y + _dy
            if not game_map.in_bounds(_x, _y):
                continue
            _tile = game_map.tiles[_y][_x]
            if _tile.kind == "dungeon_floor" and _tile.walkable:
                return _tile
    return world.DUNGEON_FLOOR

def _open_signal_door_tiles(
    game_map: world.GameMap,
    barrier: list[world.Position],
    stairs: world.Position,
) -> None:
    """Commit the opened barrier and reveal its walkable stairs marker."""
    _floor = _landmark_floor_near_barrier(game_map, barrier)
    for _position in barrier:
        game_map.tiles[_position.y][_position.x] = _floor
    if game_map.in_bounds(stairs.x, stairs.y):
        game_map.tiles[stairs.y][stairs.x] = world.STAIRS_DOWN
        game_map.extension_entry_id = "mars_alien_prison"

def animate_signal_door_opening(
    ctx,
    console,
    game_map: world.GameMap,
    player_pos: world.Position,
) -> bool:
    """Undulate the Mars barrier, split it from the middle, and reveal stairs."""
    _stairs = getattr(game_map, "mars_stairs_pos", None)
    _barrier = _signal_door_barrier(game_map)
    if not isinstance(_stairs, world.Position) or not _barrier:
        return False
    from ..navigation import _responsive_sleep
    for _frame in _signal_door_frames(len(_barrier)):
        _render_signal_door_frame(ctx, console, game_map, player_pos, _barrier, _frame)
        _responsive_sleep(animation_timing.SIGNAL_WAVE)
    _open_signal_door_tiles(game_map, _barrier, _stairs)
    _render_signal_door_frame(
        ctx,
        console,
        game_map,
        player_pos,
        _barrier,
        " " * len(_barrier),
    )
    _responsive_sleep(animation_timing.SIGNAL_SETTLE)
    return True

def _door_room_cells(game_map: world.GameMap, door_pos: world.Position, *, cap: int = 40) -> list[world.Position]:
    """BFS through walkable cells from the door — the door's room.

    Walls and doors stop expansion; cells are returned nearest-first,
    so the first entries surround the door itself.
    """
    _queue: deque[tuple[int, int]] = deque([(door_pos.x, door_pos.y)])
    _seen: set[tuple[int, int]] = {(door_pos.x, door_pos.y)}
    _cells: list[world.Position] = []
    while _queue and len(_cells) < cap:
        _x, _y = _queue.popleft()
        _cells.append(world.Position(_x, _y))
        for _nx, _ny in ((_x + 1, _y), (_x - 1, _y), (_x, _y + 1), (_x, _y - 1)):
            if not (0 <= _nx < game_map.width and 0 <= _ny < game_map.height):
                continue
            if (_nx, _ny) in _seen:
                continue
            _tile = game_map.tiles[_ny][_nx]
            if not _tile.walkable or _tile.kind in ("dungeon_door", "breach"):
                continue
            _seen.add((_nx, _ny))
            _queue.append((_nx, _ny))
    return _cells

def _spawn_squad_near(
    game_map: world.GameMap,
    near_pos: world.Position,
    *,
    enemy_id: str,
    count: int,
    label: str,
    room_cap: int = 40,
) -> int:
    """Scatter ``count`` copies of ``enemy_id`` in the room around ``near_pos``.

    Shared by the Mars door ambush and the quest-cache guardians: a
    nearest-first BFS from ``near_pos`` (``room_cap`` cells), occupied
    cells excluded, all members sharing one ``squad_id`` so the group
    joins a single ground-combat encounter. Spawns on the given map —
    cached interiors keep the squad across save/load and re-entry.
    Returns how many were placed.
    """
    from ..data.npc_chars import find_npc_char as _fnc
    try:
        _spec = _fnc(enemy_id)
    except KeyError:
        return 0
    _room = _door_room_cells(game_map, near_pos, cap=room_cap)
    if not _room:
        return 0
    from ..engine import RNG as _RNG
    _occupied = {(e.pos.x, e.pos.y) for e in game_map.entities}
    _squad_id = f"{label}_{_RNG.randint(10000, 99999)}"
    return dungeon._scatter_squad(
        game_map.entities,
        _occupied,
        enemy_id=enemy_id,
        cells=[(_cell.x, _cell.y) for _cell in _room],
        count=count,
        squad_id=_squad_id,
        char=_spec.char,
        fg=_spec.fg,
    )

def _spawn_cache_guardian(
    game_map: world.GameMap,
    near_pos: world.Position,
    planet_id: str,
) -> int:
    """Spawn the planet's quest-cache guardian squad near ``near_pos``.

    Reads the guardian pool + count from the planet's ``dungeon_params``
    (empty pool = no guardian). Called at generation time, so the
    guardian persists via the interior cache (save/load safe).
    """
    from ..data.planets import find_planet_spec as _fps
    try:
        _pspec = _fps(planet_id)
    except KeyError:
        return 0
    _params = getattr(_pspec, "dungeon_params", None)
    _pool = tuple(getattr(_params, "cache_guardian_pool", ()) or ())
    if not _pool:
        return 0
    from ..engine import RNG as _RNG
    _eid = _RNG.choice(_pool)
    _count = getattr(_params, "cache_guardian_count", 1)
    # The 10 cells nearest the cache keep the squad in the cache room
    # (a wide BFS can leak it far down a corridor, away from what it
    # is guarding).
    return _spawn_squad_near(
        game_map, near_pos,
        enemy_id=_eid, count=_count, label="cache_guardian",
        room_cap=10,
    )

def start_prison_objective(ctx) -> None:
    """Start the Act 1 prison step when the player enters the extension.

    Called on the first descent into the alien prison each run. The step
    is made available when ``prologue_open`` completes (Act 0's end); this
    flips it to active on entry and completes on the Floor 5 extraction.
    """
    if step_status(ctx, "act1_prison") == STATUS_AVAILABLE:
        start_step(ctx, "act1_prison")
        ctx.log.add_colored(
            t_get("runtime.quest_prison_start_log"),
            message_log.COLOR_IMPORTANT_EVENT,
        )

def _spawn_door_ambush(ctx, *, count: int = 3) -> bool:
    """Spawn pirate raiders in the room around the Mars door.

    Returns True if raiders were placed.  The squad shares one
    ``squad_id`` so the whole group joins a single ground-combat
    encounter.  Spawns on the current map (the cached Mars surface),
    so the raiders persist across save/load and re-entry.
    """
    _anchor = next(
        (
            _e.pos for _e in ctx.game_map.entities
            if getattr(_e, "main_quest_console", False)
        ),
        None,
    )
    if _anchor is None:
        _anchor = next(
            (
                _e.pos for _e in ctx.game_map.entities
                if getattr(_e, "main_quest_door", False)
            ),
            None,
        )
    if _anchor is None:
        return False
    return _spawn_squad_near(
        ctx.game_map, _anchor,
        enemy_id="pirate_raider", count=count, label="door_ambush",
    ) > 0

def _chip_bump_objective(ctx, bumped_step: str) -> None:
    """Show the quest readout modal for a chipped bump objective."""
    from ._objectives import show_step_readout as _ssr
    _ssr(ctx, find_main_quest_step(bumped_step))
    # The lab sample draws attention: pirates watching the dig
    # spring an ambush in the door's room the moment it's chipped.
    if bumped_step == "lab_q1_sample" and _spawn_door_ambush(ctx):
        show_gate_popup(
            ctx, t_get("runtime.door_ambush_faction"),
            t_get("runtime.door_ambush_body"),
            title=t_get("runtime.door_ambush_title"),
        )


def _play_sealed_door_open(ctx) -> None:
    """Play the door-opening scene: animate the doors, then the overlay."""
    animate_signal_door_opening(ctx, make_console(), ctx.game_map, ctx.player.pos)
    show_sealed_door_overlay(ctx, "open")


def bump_mars_door(ctx) -> None:
    """Handle bumping the sealed alien door on Mars."""
    _bumped_step = _complete_bump_objective(ctx)
    if _bumped_step:
        _chip_bump_objective(ctx, _bumped_step)
        return
    _open_status = step_status(ctx, "prologue_open")
    if _open_status in (STATUS_AVAILABLE, STATUS_ACTIVE):
        complete_step(ctx, "prologue_open")
        ctx.log.add_colored(
            t_get("runtime.door_open_log"),
            message_log.COLOR_IMPORTANT_EVENT,
        )
        ctx.log.add(t_get("runtime.door_open_log2"))
        play_scene(ctx, "prologue_open")
        return
    _entrance_status = step_status(ctx, "prologue_mars_entrance")
    if _entrance_status in (STATUS_AVAILABLE, STATUS_ACTIVE):
        complete_step(ctx, "prologue_mars_entrance")
        ctx.log.add_colored(
            t_get("runtime.door_discover_log"),
            message_log.COLOR_IMPORTANT_EVENT,
        )
        play_scene(ctx, "prologue_mars_entrance")
        return
    if step_status(ctx, "prologue_open") == STATUS_COMPLETED:
        ctx.log.add(t_get("runtime.door_gapes_log"))
        return
    ctx.log.add(t_get("runtime.door_holds_log"))

# ---------------------------------------------------------------------------
# Delve site preparation
# ---------------------------------------------------------------------------

# Authored camp layouts per delve planet: the quest cache lands inside
# the camp instead of a random far room (wolf_b: frozen prospectors'
# bunkhouse, doc 32; mercury: sealed requisition vault, doc 35).
_DELVE_CAMPS: dict[str, str] = {
    "wolf_b": "wolf_camp",
    "mercury": "mercury_vault",
}


def _camp_or_far_cache(
    game_map: world.GameMap, spawn: world.Position, planet_id: str,
) -> world.Position:
    """The cache position: inside the planet's authored camp if one
    stamped cleanly, else the farthest walkable cell.

    The camp's deepest interior cell (farthest from its door) holds
    the cache, so the guardians end up holding the room around it. A
    camp that cannot route on this map falls back — the delve must
    never fail to build.
    """
    _layout_id = _DELVE_CAMPS.get(planet_id)
    if _layout_id is not None:
        try:
            _asset = landmark.load_landmark(_layout_id)
            _stamp = landmark.stamp_landmark(game_map, _asset, spawn)
        except ValueError:
            _stamp = None
        if _stamp is not None:
            game_map.landmark_footprint = (
                set(getattr(game_map, "landmark_footprint", ()) or ())
                | set(_stamp.footprint)
            )
            _door = (_stamp.entrance.x, _stamp.entrance.y)
            _interior = [
                (x, y)
                for x, y in _stamp.footprint
                if game_map.in_bounds(x, y)
                and game_map.tiles[y][x].walkable
            ]
            if _interior:
                _cx, _cy = max(
                    _interior,
                    key=lambda c: (abs(c[0] - _door[0]) + abs(c[1] - _door[1]), c[1], c[0]),
                )
                return world.Position(_cx, _cy)
    return _farthest_walkable(game_map, spawn)


def prepare_delve_site(
    ctx,
    game_map: world.GameMap,
    spawn: world.Position,
    planet_id: str,
) -> bool:
    """Place the quest cache for planet_id's active delve step."""
    _step_id = _active_objective_step(ctx, "delve", planet_id=planet_id)
    if _step_id is None:
        return False
    _step = find_main_quest_step(_step_id)
    _cache_pos = _camp_or_far_cache(game_map, spawn, planet_id)
    _cache = world.Entity(
        char="%",
        fg=(255, 215, 0),
        pos=_cache_pos,
        name="Quest Cache",
        width=1, height=1,
        loot_data={"goods": list(_step.delve_good_ids)},
    )
    _cache.main_quest_step_id = _step_id
    game_map.entities.append(_cache)
    # The planet's guardian holds the cache room — one squad, placed at
    # generation time so it persists via the interior cache.
    _spawn_cache_guardian(game_map, _cache_pos, planet_id)
    return True

# ---------------------------------------------------------------------------
# Exploration gates
# ---------------------------------------------------------------------------

def mars_exploration_unlocked(ctx) -> bool:
    """True once the signal has been received (Mars gate open)."""
    return step_status(ctx, "prologue_signal") in (STATUS_ACTIVE, STATUS_COMPLETED)

def delve_site_unlocked(ctx, planet_id: str) -> bool:
    """True while a delve step targeting planet_id is live."""
    return _active_objective_step(ctx, "delve", planet_id=planet_id) is not None

def surface_exploration_unlocked(ctx, planet_id: str) -> bool:
    """True when planet_id's surface explore option may be shown."""
    if planet_id == "mars":
        return mars_exploration_unlocked(ctx)
    return delve_site_unlocked(ctx, planet_id)

# ---------------------------------------------------------------------------
# Quest NPC spawning
# ---------------------------------------------------------------------------

def _quest_npcs_for_planet(ctx, planet_id: str) -> tuple[str, ...]:
    """Quest NPC ids that should appear on ``planet_id`` right now.

    Data-driven over each step's ``npc_presence`` tags: an NPC
    appears while ANY live step (status available/active) of the
    locked chain tags it, and vanishes once its steps complete. The
    standing spot comes from the planet's own ``quest_npc_spots`` —
    the step's objective location (e.g. a space salvage) and the
    NPC's guild building may differ. No per-step hard-coded ids.
    """
    from ..data.planets import find_planet_spec as _find_planet_spec
    try:
        _spotted = {
            _nid for _nid, _label in _find_planet_spec(planet_id).quest_npc_spots
        }
    except KeyError:
        return ()
    if not _spotted:
        return ()
    _needed: set[str] = set()
    for _step_id, _status, _step in _iter_known_steps(ctx):
        if _status not in (STATUS_AVAILABLE, STATUS_ACTIVE):
            continue
        if _step.chain and _step.chain != ctx.main_quest_chain:
            continue
        _needed.update(_nid for _nid in _step.npc_presence if _nid in _spotted)
    return tuple(sorted(_needed))


def _quest_npc_building_label(planet_id: str, npc_id: str) -> str | None:
    """The guild-building label whose interior hosts ``npc_id``.

    Since the cities rework, buildings are enterable landmarks: the
    quest NPC stands INSIDE the building's authored interior next to
    the resident — never on the city map's roof rectangle (playtest
    v12: the salvage specialist spawned mid-roof, unreachable).
    """
    from ..data.planets import find_planet_spec as _find_planet_spec
    try:
        _spec = _find_planet_spec(planet_id)
    except KeyError:
        return None
    for _npc_id, _label in _spec.quest_npc_spots:
        if _npc_id == npc_id:
            return _label
    return None


def seat_quest_npcs_in_interior(
    ctx,
    game_map: world.GameMap,
    record: dict,
) -> None:
    """Seat live quest NPCs inside a building's authored interior.

    Called from ``city_interiors`` when an interior loads (fresh or
    cached): every live quest NPC whose ``quest_npc_spots`` points at
    this building's label stands beside the resident, on the next
    clear interior cell. Idempotent; additive NPCs ride the interior
    cache, and because interiors are deterministic-authored (rebuilt,
    not saved), a completed step simply stops seating them.
    """
    planet_id = getattr(ctx, "current_city_id", "")
    label = record.get("label", "")
    if not planet_id or not label:
        return
    from ..data.npcs import find_npc as _find_npc
    for _npc_id in _quest_npcs_for_planet(ctx, planet_id):
        if _quest_npc_building_label(planet_id, _npc_id) != label:
            continue
        if any(getattr(_e, 'npc_id', '') == _npc_id for _e in game_map.entities):
            continue
        _npc = _find_npc(_npc_id)
        _spawn = getattr(game_map, "entry_spawn", None)
        _pos = _interior_seat_for_quest_npc(game_map, _spawn)
        if _pos is None:
            ctx.log.add(
                f"[MAIN QUEST] {_npc_id} has no clear cell in {label}."
            )
            continue
        game_map.entities.append(world.Entity(
            char=_npc.char,
            fg=_npc.fg,
            pos=_pos,
            name=_npc.name,
            npc_id=_npc.id,
            width=1, height=1,
        ))


def _interior_seat_for_quest_npc(game_map, spawn):
    """Next clear interior cell near the center (resident already seated)."""
    from ..city_interiors import _first_interior_npc
    return _first_interior_npc(game_map, spawn) if spawn is not None else None


# ---------------------------------------------------------------------------
# Full-screen overlay plumbing
# ---------------------------------------------------------------------------

class OfferOutcome(Enum):
    IGNORE = auto()
    ACCEPT = auto()
    DECLINE = auto()
    QUIT = auto()

# ---------------------------------------------------------------------------
# Incoming transmission overlay
# ---------------------------------------------------------------------------

_SIGNAL_STATIC: tuple[str, ...] = (
    "...--.-.-..--...-..-.-.--.....-.-..--.-..",
    "-.--..-.-..--.-..-...--..-.-..--...--...-",
    "..-.-.--.....-.-..--.-..--...--.-..---.-.",
)
_SIGNAL_TRACE_FG: tuple[int, int, int] = (90, 150, 90)
_SIGNAL_ART: tuple[str, ...] = (
    "FREQUENCY: UNKNOWN    SOURCE: UNKNOWN    ENCRYPTION: NONE",
    "",
    *_SIGNAL_STATIC,
)
_SIGNAL_ART_COLORS: tuple[tuple[int, int, int], ...] = (
    ui.COLOR_VALUE_DIM,
    ui.COLOR_VALUE_DIM,
    *(_SIGNAL_TRACE_FG for _ in _SIGNAL_STATIC),
)

def show_prologue_transmission(ctx) -> None:
    _show_pygame_dismiss(
        ctx,
        title=t_get("runtime.transmission_title"),
        body=t_get("runtime.transmission_body"),
        caption="spacehack - incoming transmission",
        art=_SIGNAL_ART,
        art_color=_SIGNAL_TRACE_FG,
        art_colors=_SIGNAL_ART_COLORS,
    )

# ---------------------------------------------------------------------------
# Quest summon overlay
# ---------------------------------------------------------------------------

def show_quest_summon(ctx, message: str, *, objective: str = "") -> None:
    _body = message if not objective else f"{message}\n\n{objective}"
    _show_pygame_dismiss(
        ctx,
        title=t_get("runtime.summon_title"),
        body=_body,
        caption="spacehack - incoming message",
    )

# ---------------------------------------------------------------------------
# Gate popup (time-gate explanation)
# ---------------------------------------------------------------------------

def show_gate_popup(ctx, faction: str, body_text: str, *, title: str = "") -> None:
    """Show a dismiss-only modal popup (time-gate explanation, ambush, etc.)."""
    if not title:
        title = t_get("runtime.gate_popup_default_title")
    _show_pygame_dismiss(
        ctx,
        title=title,
        body=f"FACTION: {faction.upper()}\n\n{body_text}",
        caption=f"spacehack - {title.lower()}",
    )

# ---------------------------------------------------------------------------
# Chain continuation (after dialogue trigger)
# ---------------------------------------------------------------------------

def maybe_continue_chain(ctx, npc_id: str, step_id: str) -> None:
    """After trigger_dialogue completes step_id, handle follow-up popups."""
    from ._dialogue import trigger_dialogue
    _step = find_main_quest_step(step_id)
    if step_id == "prologue_seek_help" and ctx.main_quest_chain:
        _q1 = main_quest_step_after("prologue_seek_help", chain=ctx.main_quest_chain)
        # Only talk-commitment q1 steps get the accept offer. Bump q1
        # (the lab chain) completes by chipping the door, so an offer
        # whose "Accept" advances nothing would be a dead prompt.
        if _q1 is not None \
                and step_status(ctx, _q1.id) == STATUS_AVAILABLE \
                and _q1.objective_type == "talk" \
                and npc_id in _q1.dialogues:
            _offer = show_help_offer(ctx, npc_id, _q1.id)
            if _offer is OfferOutcome.QUIT:
                return
            if _offer is OfferOutcome.ACCEPT:
                trigger_dialogue(ctx, npc_id, _q1.id)
                _step = find_main_quest_step(_q1.id)
            else:
                return
    if (_step.wait_days > 0 and _step.completion_flavor
            and step_status(ctx, _step.id) == STATUS_COMPLETED):
        _fac = (_step.chain or "faction").capitalize()
        show_gate_popup(ctx, _fac, _step.completion_flavor)

# ---------------------------------------------------------------------------
# Sealed door overlay
# ---------------------------------------------------------------------------

_DOOR_RUNES: tuple[str, ...] = (
    "##=+==#=+==#=+==#=+==##=+==#=+",
    "=+==#=+==#=+==#=+==#=+==#=+==#",
    "+==#=+==#=+==#=+==#=+==#=+==#=",
)
_DOOR_RUNE_FG: tuple[int, int, int] = (150, 95, 255)
_DOOR_ART_FG: tuple[int, int, int] = (140, 80, 255)

_DOOR_ART_SEALED: tuple[str, ...] = (
    "  .==========================.  ",
    "  |  #    #   #   #   #   #  |  ",
    "  |   #   #   #   #   #   #  |  ",
    "  |  #    #   #   #   #   #  |  ",
    "  |   #   #   #   #   #   #  |  ",
    "  |                          |  ",
    "  |      ==============      |  ",
    "  |      |            |      |  ",
    "  |      |     ===    |      |  ",
    "  |      |            |      |  ",
    "  |      ==============      |  ",
    "  |                          |  ",
    "  '=========================='  ",
)

_DOOR_ART_OPEN: tuple[str, ...] = (
    "  .==========================.  ",
    "  |  #    #   #   #   #   #  |  ",
    "  |   #   #   #   #   #   #  |  ",
    "  |  #    #   #   #   #   #  |  ",
    "  |   #   #   #   #   #   #  |  ",
    "  |                          |  ",
    "  |      ==============      |  ",
    "  |      |    ...     |      |  ",
    "  |      |   .....    |      |  ",
    "  |      |    ...     |      |  ",
    "  |      ==============      |  ",
    "  |                          |  ",
    "  '=========================='  ",
)

_DOOR_ART: dict[str, tuple[str, ...]] = {
    "discover": _DOOR_ART_SEALED,
    "open": _DOOR_ART_OPEN,
}

def show_sealed_door_overlay(ctx, beat: str) -> None:
    _title = t_get(f"runtime.door_{beat}_title")
    _art = _DOOR_ART[beat]
    _show_pygame_dismiss(
        ctx,
        title=_title,
        body=t_get(f"runtime.door_{beat}_body")
        + "\n" + t_get(f"runtime.door_{beat}_highlight"),
        caption=f"spacehack - {_title.lower()}",
        art=tuple((t_get(f"runtime.door_{beat}_meta"), "", *_DOOR_RUNES, *_art)),
        art_color=_DOOR_ART_FG,
        art_colors=tuple((
            ui.COLOR_VALUE_DIM,
            ui.COLOR_VALUE_DIM,
            *(_DOOR_RUNE_FG for _ in _DOOR_RUNES),
            *(_DOOR_ART_FG for _ in _art),
        )),
    )

# ---------------------------------------------------------------------------
# Help-offer modal
# ---------------------------------------------------------------------------

def _show_pygame_dismiss(
    ctx,
    *,
    title: str,
    body: str,
    caption: str,
    art: tuple[str, ...] = (),
    art_color: tuple[int, int, int] | None = None,
    art_colors: tuple[tuple[int, int, int], ...] = (),
) -> bool:
    """Show a story popup in the shared Pygame window."""
    from ..pygame_story import dismiss

    while True:
        outcome = dismiss(
            ctx,
            title=title,
            body=body,
            caption=caption,
            art=art,
            art_color=art_color,
            art_colors=art_colors,
        )
        if outcome == "__GUIDE__":
            continue
        if outcome == "QUIT":
            raise SystemExit
        return True

def _run_pygame_help_offer(ctx, npc_name: str, offer_text: str) -> OfferOutcome:
    """Map the Pygame help offer back to quest outcomes."""
    from ..pygame_story import choose

    _action = choose(
        ctx,
        title="AN OFFER OF HELP",
        body=f"OFFERED BY: {npc_name.upper()}\n\n{offer_text}",
        options=(("Accept", "ACCEPT"), ("I need more time", "DECLINE")),
        caption="spacehack - an offer of help",
    )
    if _action == "ACCEPT":
        return OfferOutcome.ACCEPT
    if _action == "__QUIT__":
        return OfferOutcome.QUIT
    return OfferOutcome.DECLINE

def show_help_offer(ctx, npc_id: str, step_id: str) -> OfferOutcome:
    _step = find_main_quest_step(step_id)
    _dialogue = _step.dialogues.get(npc_id)
    if _dialogue is None:
        return OfferOutcome.DECLINE
    _status = ctx.main_quest_progress.get(step_id, "")
    _offer_text = _dialogue.active if _status == STATUS_ACTIVE else _dialogue.intro
    if not _offer_text:
        return OfferOutcome.DECLINE
    from ..data.npcs import find_npc as _find_npc
    _npc_name = _find_npc(npc_id).name
    return _run_pygame_help_offer(ctx, _npc_name, _offer_text)

# ---------------------------------------------------------------------------
# Quest readout overlay
# ---------------------------------------------------------------------------

def show_quest_readout(ctx, npc, body_text: str) -> None:
    _show_pygame_dismiss(
        ctx,
        title=npc.name.upper(),
        body=body_text,
        caption=f"spacehack - {npc.name}",
    )
