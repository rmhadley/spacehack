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
from ..data.main_quest import find_main_quest_step, main_quest_step_after
from ._core import (
    STATUS_ACTIVE,
    STATUS_AVAILABLE,
    STATUS_COMPLETED,
    step_status,
    start_step,
    complete_step,
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
        "STATIC... a garbled transmission cuts through the noise.",
        message_log.COLOR_IMPORTANT_EVENT,
    )
    ctx.log.add(
        "Your ship crunches the data and outputs coordinates on mars."
    )
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
            "[MAIN QUEST] Act 1: The Prison Below - descend the facility.",
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
            ctx, "Pirate Raiders",
            "Raiders pour out of the shadows around the sealed "
            "door - they were watching the dig site, waiting for "
            "someone to come back for the sample. They want it.",
            title="AMBUSH!",
        )


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
            "The seal gives way. Inside: an empty cell built for something enormous - "
            "and a dark terminal interface waiting to be accessed.",
            message_log.COLOR_IMPORTANT_EVENT,
        )
        ctx.log.add(
            "The entrance is open. Beyond it, the facility descends into darkness."
        )
        animate_signal_door_opening(ctx, make_console(), ctx.game_map, ctx.player.pos)
        show_sealed_door_overlay(ctx, "open")
        return
    _entrance_status = step_status(ctx, "prologue_mars_entrance")
    if _entrance_status in (STATUS_AVAILABLE, STATUS_ACTIVE):
        complete_step(ctx, "prologue_mars_entrance")
        ctx.log.add_colored(
            "An undulating wall of alien make, set into the red dust.",
            message_log.COLOR_IMPORTANT_EVENT,
        )
        show_sealed_door_overlay(ctx, "discover")
        return
    if step_status(ctx, "prologue_open") == STATUS_COMPLETED:
        ctx.log.add("The opened entrance gapes dark and empty.")
        return
    ctx.log.add("The sealed door holds fast. It needs a tool you don't have.")

# ---------------------------------------------------------------------------
# Delve site preparation
# ---------------------------------------------------------------------------

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
    _cache_pos = _farthest_walkable(game_map, spawn)
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

def _wall_adjacent_tile(
    game_map: world.GameMap,
    near: world.Position,
) -> world.Position:
    """Return a non-walkable tile adjacent to a walkable tile near near."""
    for _r in range(1, 10):
        for _dy in range(-_r, _r + 1):
            for _dx in range(-_r, _r + 1):
                if max(abs(_dx), abs(_dy)) != _r:
                    continue
                _x, _y = near.x + _dx, near.y + _dy
                if not (0 <= _x < game_map.width and 0 <= _y < game_map.height):
                    continue
                if game_map.tiles[_y][_x].walkable:
                    continue
                for _nx, _ny in ((_x + 1, _y), (_x - 1, _y),
                                 (_x, _y + 1), (_x, _y - 1)):
                    if (0 <= _nx < game_map.width
                            and 0 <= _ny < game_map.height
                            and game_map.tiles[_ny][_nx].walkable):
                        return world.Position(_x, _y)
    return near

def _quest_npc_for_planet(ctx, planet_id: str) -> str | None:
    """Return the quest NPC id that should appear on this planet, if any."""
    if planet_id == "barnards_b" and ctx.main_quest_chain == "bar":
        # The old smuggler is on the map from the proof run (q2)
        # through the power-cell handover (q4) — he draws the cave
        # and re-issues a lost cell — and leaves once the cell is on
        # its way to Wolf 359 (q4 complete).
        _needs_smuggler = (
            step_status(ctx, "bar_q2_proof") != ""
            and step_status(ctx, "bar_q4_blackmarket") != STATUS_COMPLETED
        )
        return "old_smuggler" if _needs_smuggler else None
    if planet_id == "tc_b" and ctx.main_quest_chain == "merchants":
        _mid_transport = (
            step_status(ctx, "mer_q3_transport") in (STATUS_AVAILABLE, STATUS_ACTIVE)
        )
        _awaiting_calibrate = (
            step_status(ctx, "mer_q3_transport") == STATUS_COMPLETED
            and step_status(ctx, "mer_q4_calibrate") in (STATUS_AVAILABLE, STATUS_ACTIVE)
        )
        return "salvage_specialist" if (_mid_transport or _awaiting_calibrate) else None
    return None


def spawn_quest_npcs(
    ctx,
    game_map: world.GameMap,
    planet_id: str,
    *,
    spawn_pos: world.Position | None = None,
) -> None:
    """Add quest-conditional NPCs to game_map after loading a city or dungeon."""
    _need_npc = _quest_npc_for_planet(ctx, planet_id)
    if _need_npc is None:
        return
    if any(getattr(_e, 'npc_id', '') == _need_npc for _e in game_map.entities):
        return
    from ..data.npcs import find_npc as _find_npc
    _npc = _find_npc(_need_npc)
    if spawn_pos is not None:
        _pos = _wall_adjacent_tile(game_map, spawn_pos)
    else:
        _pos = world.Position(x=38, y=10)
    game_map.entities.append(world.Entity(
        char=_npc.char,
        fg=_npc.fg,
        pos=_pos,
        name=_npc.name,
        npc_id=_npc.id,
        width=1, height=1,
    ))

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
        title="INCOMING TRANSMISSION",
        body=(
            "Comms lights up with a strange signal. It's mostly noise and "
            "static. But through the incomprehensible chatter the systems "
            "detect a pattern. Coordinates that appear to pointing to a "
            "remote part of Mars in Sol."
        ),
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
        title="INCOMING MESSAGE",
        body=_body,
        caption="spacehack - incoming message",
    )

# ---------------------------------------------------------------------------
# Gate popup (time-gate explanation)
# ---------------------------------------------------------------------------

def show_gate_popup(ctx, faction: str, body_text: str, *, title: str = "THE WORK BEGINS") -> None:
    """Show a dismiss-only modal popup (time-gate explanation, ambush, etc.)."""
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
        if _q1 is not None \
                and step_status(ctx, _q1.id) == STATUS_AVAILABLE \
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

_DOOR_OVERLAYS: dict[str, dict[str, object]] = {
    "discover": {
        "title": "SEALED ENTRANCE",
        "meta": "MAKE: ALIEN    MECHANISM: NONE VISIBLE    AGE: UNKNOWN",
        "art": _DOOR_ART_SEALED,
        "body": (
            "The martian rock merges with high tech metal machinery.",
            "You see a wall that undulates before you as you examine it.",
            "An alien console stands before it, still with power.",
            "But a mystery you can't solve alone.",
        ),
        "highlight": "The console just hums and ignores your input.",
        "instruction": "Press ENTER to acknowledge",
    },
    "open": {
        "title": "THE SEAL GIVES WAY",
        "meta": "SEAL: BROKEN    CHAMBER: EMPTY    ACCESS: GRANTED",
        "art": _DOOR_ART_OPEN,
        "body": (
            "The seal gives way - cleanly, as if it were waiting.",
            "Inside: an empty cell built for something enormous -",
            "and a dark terminal interface waiting for input.",
        ),
        "highlight": "The entrance is open. The way forward leads deeper into the facility.",
        "instruction": "Press ENTER to continue",
    },
}

def show_sealed_door_overlay(ctx, beat: str) -> None:
    _content = _DOOR_OVERLAYS[beat]
    _show_pygame_dismiss(
        ctx,
        title=str(_content["title"]),
        body="\n".join((*_content["body"], str(_content["highlight"]))),
        caption=f"spacehack - {str(_content['title']).lower()}",
        art=tuple((str(_content["meta"]), "", *_DOOR_RUNES, *_content["art"])),
        art_color=_DOOR_ART_FG,
        art_colors=tuple((
            ui.COLOR_VALUE_DIM,
            ui.COLOR_VALUE_DIM,
            *(_DOOR_RUNE_FG for _ in _DOOR_RUNES),
            *(_DOOR_ART_FG for _ in _content["art"]),
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
