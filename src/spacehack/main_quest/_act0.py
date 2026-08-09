"""Main quest Act 0: signal trigger, Mars door, full-screen overlays, gate popups."""

from __future__ import annotations

from collections import deque
from enum import Enum, auto

import tcod.event

from .. import message_log
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
        "A burst of coordinates cuts through the static, followed by a second pattern folded inside the first. They resolve to somewhere on Mars."
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
        _screen_x, _screen_y = _signal_door_screen_pos(
            _position, _camera_x, _camera_y, _region_x, _region_y,
        )
        if 0 <= _screen_x < _map_w and 0 <= _screen_y < _map_h:
            _tile = game_map.tiles[_position.y][_position.x]
            console.print(
                x=_screen_x,
                y=_screen_y,
                string=_glyph,
                fg=_tile.fg,
                bg=_tile.bg,
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
        _responsive_sleep(0.10)
    _open_signal_door_tiles(game_map, _barrier, _stairs)
    _render_signal_door_frame(
        ctx,
        console,
        game_map,
        player_pos,
        _barrier,
        " " * len(_barrier),
    )
    _responsive_sleep(0.18)
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
            "[MAIN QUEST] Act 1: The Prison Below — descend the facility.",
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


def bump_mars_door(ctx) -> None:
    """Handle bumping the sealed alien door on Mars."""
    _bumped_step = _complete_bump_objective(ctx)
    if _bumped_step:
        # A quest bump objective was chipped (e.g. lab_q1_sample):
        # show the quest readout modal (completion flavor + next step)
        # instead of a bare console-log line.
        from ._objectives import show_step_readout as _ssr
        _step = find_main_quest_step(_bumped_step)
        _ssr(ctx, _step)
        # The lab sample draws attention: pirates watching the dig
        # spring an ambush in the door's room the moment it's chipped.
        if _bumped_step == "lab_q1_sample" and _spawn_door_ambush(ctx):
            show_gate_popup(
                ctx, "Pirate Raiders",
                "Raiders pour out of the shadows around the sealed "
                "door — they were watching the dig site, waiting for "
                "someone to come back for the sample. They want it.",
                title="AMBUSH!",
            )
        return
    _open_status = step_status(ctx, "prologue_open")
    if _open_status in (STATUS_AVAILABLE, STATUS_ACTIVE):
        complete_step(ctx, "prologue_open")
        ctx.main_quest_unlocked_items.add("prison_data")
        ctx.log.add_colored(
            "The seal gives way. Inside: an empty cell built for something enormous — "
            "and a cache of data that refuses to become a language.",
            message_log.COLOR_IMPORTANT_EVENT,
        )
        ctx.log.add(
            "The data is recovered: routes, warnings, and an absence where a "
            "prisoner should be."
        )
        animate_signal_door_opening(ctx, make_console(), ctx.game_map, ctx.player.pos)
        show_sealed_door_overlay(ctx, "open")
        return
    _entrance_status = step_status(ctx, "prologue_mars_entrance")
    if _entrance_status in (STATUS_AVAILABLE, STATUS_ACTIVE):
        complete_step(ctx, "prologue_mars_entrance")
        ctx.log.add_colored(
            "A door of alien make, set into the red dust. No visible "
            "mechanism — older than the colony. It will not open.",
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


def spawn_quest_npcs(
    ctx,
    game_map: world.GameMap,
    planet_id: str,
    *,
    spawn_pos: world.Position | None = None,
) -> None:
    """Add quest-conditional NPCs to game_map after loading a city or dungeon."""
    _need_npc: str | None = None
    if planet_id == "barnards_b" and ctx.main_quest_chain == "bar":
        # The old smuggler is on the map from the proof run (q2)
        # through the power-cell handover (q4) — he draws the cave
        # and re-issues a lost cell — and leaves once the cell is on
        # its way to Wolf 359 (q4 complete).
        _need = (
            step_status(ctx, "bar_q2_proof") != ""
            and step_status(ctx, "bar_q4_blackmarket") != STATUS_COMPLETED
        )
        if _need:
            _need_npc = "old_smuggler"
    elif planet_id == "tc_b" and ctx.main_quest_chain == "merchants":
        _need = (
            step_status(ctx, "mer_q3_transport") in (STATUS_AVAILABLE, STATUS_ACTIVE)
            or (
                step_status(ctx, "mer_q3_transport") == STATUS_COMPLETED
                and step_status(ctx, "mer_q4_calibrate") in (STATUS_AVAILABLE, STATUS_ACTIVE)
            )
        )
        if _need:
            _need_npc = "salvage_specialist"
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


class _ModalOutcome(Enum):
    IGNORE = auto()
    CLOSE = auto()
    QUIT = auto()


class OfferOutcome(Enum):
    IGNORE = auto()
    ACCEPT = auto()
    DECLINE = auto()
    QUIT = auto()


def _overlay_box(console, *, screen_width, screen_height, box_w, box_h) -> int:
    console.clear()
    y0 = max(0, (screen_height - box_h) // 2 - 2)
    ui.paint_rect_border(
        console,
        (max(0, (screen_width - box_w) // 2), y0, box_w, box_h),
        fg=ui.COLOR_VALUE_DIM,
    )
    return y0


def _centered_print(console, *, screen_width, y, text, fg) -> None:
    console.print(x=ui.centered_x(text, screen_width), y=y, string=text, fg=fg)


def _modal_dismiss_update(event: tcod.event.Event) -> _ModalOutcome:
    if isinstance(event, tcod.event.Quit):
        return _ModalOutcome.QUIT
    if not isinstance(event, tcod.event.KeyDown):
        return _ModalOutcome.IGNORE
    if event.sym in ui._ENTER_SYMS or event.sym in ui._ESCAPE_SYMS:
        return _ModalOutcome.CLOSE
    return _ModalOutcome.IGNORE


# ---------------------------------------------------------------------------
# Incoming transmission overlay
# ---------------------------------------------------------------------------

_SIGNAL_STATIC: tuple[str, ...] = (
    "...--.-.-..--...-..-.-.--.....-.-..--.-..",
    "-.--..-.-..--.-..-...--..-.-..--...--...-",
    "..-.-.--.....-.-..--.-..--...--.-..---.-.",
)
_SIGNAL_TRACE_FG: tuple[int, int, int] = (90, 150, 90)


def render_incoming_transmission(console, *, screen_width, screen_height) -> None:
    _y0 = _overlay_box(console, screen_width=screen_width, screen_height=screen_height, box_w=64, box_h=18)
    _centered_print(console, screen_width=screen_width, y=_y0 + 1, text="INCOMING TRANSMISSION", fg=ui.COLOR_TITLE)
    _centered_print(console, screen_width=screen_width, y=_y0 + 3,
                    text="FREQUENCY: UNKNOWN    SOURCE: UNKNOWN    ENCRYPTION: NONE", fg=ui.COLOR_VALUE_DIM)
    for _i, _line in enumerate(_SIGNAL_STATIC):
        _centered_print(console, screen_width=screen_width, y=_y0 + 5 + _i, text=_line, fg=_SIGNAL_TRACE_FG)
    _centered_print(console, screen_width=screen_width, y=_y0 + 9,
                    text="A burst of coordinates cuts through the static -", fg=ui.COLOR_DESCRIPTION)
    _centered_print(console, screen_width=screen_width, y=_y0 + 10, text="then silence.", fg=ui.COLOR_DESCRIPTION)
    _centered_print(console, screen_width=screen_width, y=_y0 + 12,
                    text="They resolve to somewhere on Mars.", fg=ui.COLOR_OPTION_HIGHLIGHT)
    _centered_print(console, screen_width=screen_width, y=_y0 + 14,
                    text="Press ENTER to acknowledge", fg=ui.COLOR_INSTRUCTION)


def show_prologue_transmission(ctx) -> None:
    console = make_console()
    def _render(): render_incoming_transmission(console, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)
    def _update(event): return _modal_dismiss_update(event)
    ui.Modal(ctx.context, console).run(_render, _update)


# ---------------------------------------------------------------------------
# Quest summon overlay
# ---------------------------------------------------------------------------


def render_quest_summon(console, *, screen_width, screen_height, message, objective="") -> None:
    _lines = ui.wrap_text(message, 60)
    _obj_lines = ui.wrap_text(objective, 60) if objective else []
    _box_h = 14 + len(_lines) + len(_obj_lines) + (1 if _obj_lines else 0)
    _y0 = _overlay_box(console, screen_width=screen_width, screen_height=screen_height, box_w=70, box_h=_box_h)
    _centered_print(console, screen_width=screen_width, y=_y0 + 1, text="INCOMING MESSAGE", fg=ui.COLOR_TITLE)
    _centered_print(console, screen_width=screen_width, y=_y0 + 3,
                    text="SOURCE: CHAIN CONTACT    ENCRYPTION: NONE    REPLY: NOT REQUIRED", fg=ui.COLOR_VALUE_DIM)
    _body_y = _y0 + 5
    for _i, _line in enumerate(_lines):
        _centered_print(console, screen_width=screen_width, y=_body_y + _i, text=_line, fg=ui.COLOR_DESCRIPTION)
    _hint_y = _body_y + len(_lines) + 2
    if _obj_lines:
        for _i, _line in enumerate(_obj_lines):
            _centered_print(console, screen_width=screen_width, y=_hint_y + _i, text=_line, fg=ui.COLOR_OPTION_HIGHLIGHT)
        _hint_y += len(_obj_lines) + 1
    _centered_print(console, screen_width=screen_width, y=_hint_y,
                    text="Press ENTER to acknowledge", fg=ui.COLOR_INSTRUCTION)


def show_quest_summon(ctx, message: str, *, objective: str = "") -> None:
    console = make_console()
    def _render(): render_quest_summon(console, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT, message=message, objective=objective)
    def _update(event): return _modal_dismiss_update(event)
    ui.Modal(ctx.context, console).run(_render, _update)


# ---------------------------------------------------------------------------
# Gate popup (time-gate explanation)
# ---------------------------------------------------------------------------

_OFFER_BODY_WIDTH = 62


def render_gate_popup(console, *, screen_width, screen_height, faction, body_text, title="THE WORK BEGINS") -> None:
    """Paint a dismiss-only modal (time-gate explanation, ambush, etc.)."""
    _lines = ui.wrap_text(body_text, _OFFER_BODY_WIDTH)
    _box_h = 10 + len(_lines)
    _y0 = _overlay_box(console, screen_width=screen_width, screen_height=screen_height, box_w=70, box_h=_box_h)
    _centered_print(console, screen_width=screen_width, y=_y0 + 1, text=title, fg=ui.COLOR_TITLE)
    _centered_print(console, screen_width=screen_width, y=_y0 + 3,
                    text=f"FACTION: {faction.upper()}", fg=ui.COLOR_VALUE_DIM)
    _body_y = _y0 + 5
    for _i, _line in enumerate(_lines):
        _centered_print(console, screen_width=screen_width, y=_body_y + _i, text=_line, fg=ui.COLOR_DESCRIPTION)
    _centered_print(console, screen_width=screen_width, y=_body_y + len(_lines) + 2,
                    text="Press ENTER to continue", fg=ui.COLOR_INSTRUCTION)


def show_gate_popup(ctx, faction: str, body_text: str, *, title: str = "THE WORK BEGINS") -> None:
    """Show a dismiss-only modal popup (time-gate explanation, ambush, etc.)."""
    console = make_console()
    def _render(): render_gate_popup(console, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT, faction=faction, body_text=body_text, title=title)
    def _update(event): return _modal_dismiss_update(event)
    ui.Modal(ctx.context, console).run(_render, _update)


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
            "A door of alien make, set into the red dust.",
            "No visible mechanism - older than the colony.",
        ),
        "highlight": "It will not open with any human tool.",
        "instruction": "Press ENTER to acknowledge",
    },
    "open": {
        "title": "THE SEAL GIVES WAY",
        "meta": "SEAL: BROKEN    CHAMBER: EMPTY    DATA: RECOVERED",
        "art": _DOOR_ART_OPEN,
        "body": (
            "The seal gives way - cleanly, as if it were waiting.",
            "Inside: an empty cell built for something enormous -",
            "and a cache of data that refuses to become a language.",
        ),
        "highlight": "The data is recovered, but it is not a message yet. Routes, warnings, and fragments of a vanished prison record are tangled together inside it.",
        "instruction": "Press ENTER to continue",
    },
}


def render_sealed_door_overlay(console, *, screen_width, screen_height, beat) -> None:
    _content = _DOOR_OVERLAYS[beat]
    _art = _content["art"]
    _body = _content["body"]
    _box_h = 15 + len(_art) + len(_body)
    _y0 = _overlay_box(console, screen_width=screen_width, screen_height=screen_height, box_w=66, box_h=_box_h)
    _centered_print(console, screen_width=screen_width, y=_y0 + 1, text=_content["title"], fg=ui.COLOR_TITLE)
    _centered_print(console, screen_width=screen_width, y=_y0 + 3, text=_content["meta"], fg=ui.COLOR_VALUE_DIM)
    for _i, _line in enumerate(_DOOR_RUNES):
        _centered_print(console, screen_width=screen_width, y=_y0 + 5 + _i, text=_line, fg=_DOOR_RUNE_FG)
    _art_y = _y0 + 9
    for _i, _line in enumerate(_art):
        _centered_print(console, screen_width=screen_width, y=_art_y + _i, text=_line, fg=_DOOR_ART_FG)
    _body_y = _art_y + len(_art) + 1
    for _i, _line in enumerate(_body):
        _centered_print(console, screen_width=screen_width, y=_body_y + _i, text=_line, fg=ui.COLOR_DESCRIPTION)
    _centered_print(console, screen_width=screen_width, y=_body_y + len(_body) + 1,
                    text=_content["highlight"], fg=ui.COLOR_OPTION_HIGHLIGHT)
    _centered_print(console, screen_width=screen_width, y=_body_y + len(_body) + 3,
                    text=_content["instruction"], fg=ui.COLOR_INSTRUCTION)


def show_sealed_door_overlay(ctx, beat: str) -> None:
    console = make_console()
    def _render(): render_sealed_door_overlay(console, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT, beat=beat)
    def _update(event): return _modal_dismiss_update(event)
    ui.Modal(ctx.context, console).run(_render, _update)


# ---------------------------------------------------------------------------
# Help-offer modal
# ---------------------------------------------------------------------------


def render_help_offer(console, *, screen_width, screen_height, npc_name, offer_text, selected) -> None:
    _title = "AN OFFER OF HELP"
    _lines = ui.wrap_text(offer_text, _OFFER_BODY_WIDTH)
    _box_h = 14 + len(_lines)
    _y0 = _overlay_box(console, screen_width=screen_width, screen_height=screen_height, box_w=70, box_h=_box_h)
    _centered_print(console, screen_width=screen_width, y=_y0 + 1, text=_title, fg=ui.COLOR_TITLE)
    _centered_print(console, screen_width=screen_width, y=_y0 + 3,
                    text=f"OFFERED BY: {npc_name.upper()}", fg=ui.COLOR_VALUE_DIM)
    _body_y = _y0 + 5
    for _i, _line in enumerate(_lines):
        _centered_print(console, screen_width=screen_width, y=_body_y + _i, text=_line, fg=ui.COLOR_DESCRIPTION)
    _opt_y = _body_y + len(_lines) + 1
    for _i, _label in enumerate(("Accept", "I need more time")):
        _is_sel = _i == selected
        _marker_open = "> " if _is_sel else "  "
        _marker_close = " <" if _is_sel else "  "
        _centered_print(console, screen_width=screen_width, y=_opt_y + _i,
                        text=f"{_marker_open}{_label}{_marker_close}",
                        fg=ui.COLOR_OPTION_HIGHLIGHT if _is_sel else ui.COLOR_OPTION)
    _centered_print(console, screen_width=screen_width, y=_opt_y + 3,
                    text="ARROW KEYS / j,k navigate - ENTER select - ESC go back", fg=ui.COLOR_INSTRUCTION)


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
    _selected = 0
    console = make_console()

    def _render():
        render_help_offer(console, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT,
                          npc_name=_npc_name, offer_text=_offer_text, selected=_selected)

    def _update(event) -> OfferOutcome:
        nonlocal _selected
        if isinstance(event, tcod.event.Quit):
            return OfferOutcome.QUIT
        if not isinstance(event, tcod.event.KeyDown):
            return OfferOutcome.IGNORE
        sym = event.sym
        sym_name: str = getattr(sym, "name", "").lower()
        if sym in ui._UP_SYMS or sym_name == "k":
            _selected = 0
            return OfferOutcome.IGNORE
        if sym in ui._DOWN_SYMS or sym_name == "j":
            _selected = 1
            return OfferOutcome.IGNORE
        if sym in ui._ENTER_SYMS:
            return OfferOutcome.ACCEPT if _selected == 0 else OfferOutcome.DECLINE
        if sym in ui._ESCAPE_SYMS:
            return OfferOutcome.DECLINE
        return OfferOutcome.IGNORE

    return ui.Modal(ctx.context, console).run(_render, _update)


# ---------------------------------------------------------------------------
# Quest readout overlay
# ---------------------------------------------------------------------------


def render_quest_readout(console, *, screen_width, screen_height, npc_name, body_text) -> None:
    _lines = ui.wrap_text(body_text, _OFFER_BODY_WIDTH)
    _box_h = 10 + len(_lines)
    _y0 = _overlay_box(console, screen_width=screen_width, screen_height=screen_height, box_w=70, box_h=_box_h)
    _centered_print(console, screen_width=screen_width, y=_y0 + 1, text=npc_name.upper(), fg=ui.COLOR_TITLE)
    _body_y = _y0 + 3
    for _i, _line in enumerate(_lines):
        _centered_print(console, screen_width=screen_width, y=_body_y + _i, text=_line, fg=ui.COLOR_DESCRIPTION)
    _centered_print(console, screen_width=screen_width, y=_body_y + len(_lines) + 2,
                    text="Press ENTER to continue", fg=ui.COLOR_INSTRUCTION)


def show_quest_readout(ctx, npc, body_text: str) -> None:
    console = make_console()
    def _render(): render_quest_readout(console, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT, npc_name=npc.name, body_text=body_text)
    def _update(event): return _modal_dismiss_update(event)
    ui.Modal(ctx.context, console).run(_render, _update)
