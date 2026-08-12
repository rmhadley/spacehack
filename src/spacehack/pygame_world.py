"""Pygame preview for the live exploration frame.

The game process creates renderer-neutral draw commands from ``world.py`` and
projects the existing HUD/message log into the same command stream. The
normal game runtime owns the shared window and event pump; the isolated worker
protocol remains available for renderer tests. The preview is presentation-only:
it never receives or mutates gameplay state.
"""
from __future__ import annotations

import atexit
import json
import os
import queue
import subprocess
import sys
import threading
from dataclasses import asdict, dataclass, replace
from typing import Any

from . import pygame_engine
from . import pygame_ui
from . import world
from .framebuffer import FrameBuffer
from .engine import MSG_LOG_HEIGHT, TILE_HEIGHT, TILE_WIDTH


Color = tuple[int, int, int]


@dataclass(frozen=True)
class WorldFrame:
    """Renderer-neutral logical frame for the exploration screen."""

    logical_size: tuple[int, int]
    commands: tuple[world.WorldDrawCommand, ...]
    default_bg: Color | None = None

    def payload(self) -> dict[str, Any]:
        """Serialize this frame for the isolated worker process."""
        return {
            "logical_size": self.logical_size,
            "commands": [asdict(command) for command in self.commands],
            "default_bg": self.default_bg,
        }


class CaptureConsole(FrameBuffer):
    """FrameBuffer compatibility name for existing capture callers."""


def make_frame(
    game_map: world.GameMap,
    *,
    region_x: int,
    region_y: int,
    region_w: int,
    region_h: int,
    camera_x: int = 0,
    camera_y: int = 0,
    centered: bool = False,
    logical_size: tuple[int, int] = (1600, 960),
) -> WorldFrame:
    """Build a Pygame-ready frame from the current world state."""
    commands = tuple(
        world.world_draw_commands(
            game_map,
            region_x=region_x,
            region_y=region_y,
            region_w=region_w,
            region_h=region_h,
            camera_x=camera_x,
            camera_y=camera_y,
            centered=centered,
        )
    )
    return WorldFrame(logical_size=logical_size, commands=commands)


def _ui_commands(
    ctx: Any,
    *,
    mode: str,
    location: str,
    screen_width: int,
    screen_height: int,
    hud_view_height: int,
    has_trade_terminal: bool = False,
    has_mech_terminal: bool = False,
    has_armory_terminal: bool = False,
) -> tuple[world.WorldDrawCommand, ...]:
    """Capture the existing HUD and message-log renderers as cell commands."""
    from . import hud, message_log

    capture = CaptureConsole(screen_width, screen_height)
    hud.render_hud(
        capture,
        ctx,
        screen_width=screen_width,
        hud_view_height=hud_view_height,
        location=location,
        mode=mode,
        has_trade_terminal=has_trade_terminal,
        has_mech_terminal=has_mech_terminal,
        has_armory_terminal=has_armory_terminal,
    )
    message_log.render_message_log(
        capture,
        ctx.log,
        screen_width=screen_width,
        screen_height=screen_height,
    )
    return tuple(capture.commands)


def make_exploration_frame(
    ctx: Any,
    game_map: world.GameMap,
    *,
    mode: str,
    location: str,
    region_x: int,
    region_y: int,
    region_w: int,
    region_h: int,
    camera_x: int = 0,
    camera_y: int = 0,
    centered: bool = False,
    has_trade_terminal: bool = False,
    has_mech_terminal: bool = False,
    has_armory_terminal: bool = False,
    logical_size: tuple[int, int] = (1600, 960),
) -> WorldFrame:
    """Build map, HUD, and message-log commands for one exploration frame."""
    map_frame = make_frame(
        game_map,
        region_x=region_x,
        region_y=region_y,
        region_w=region_w,
        region_h=region_h,
        camera_x=camera_x,
        camera_y=camera_y,
        centered=centered,
        logical_size=logical_size,
    )
    screen_width = logical_size[0] // TILE_WIDTH
    screen_height = logical_size[1] // TILE_HEIGHT
    ui_commands = _ui_commands(
        ctx,
        mode=mode,
        location=location,
        screen_width=screen_width,
        screen_height=screen_height,
        hud_view_height=screen_height - MSG_LOG_HEIGHT,
        has_trade_terminal=has_trade_terminal,
        has_mech_terminal=has_mech_terminal,
        has_armory_terminal=has_armory_terminal,
    )
    return WorldFrame(
        logical_size=logical_size,
        commands=map_frame.commands + ui_commands,
    )


def make_mode_exploration_frame(
    ctx: Any,
    game_map: world.GameMap,
    *,
    mode: str,
    location: str,
    map_width: int,
    map_height: int,
    camera_x: int = 0,
    camera_y: int = 0,
    region_x: int = 0,
    region_y: int = 0,
    region_width: int | None = None,
    region_height: int | None = None,
    centered: bool = False,
    has_trade_terminal: bool = False,
    has_mech_terminal: bool = False,
    has_armory_terminal: bool = False,
) -> WorldFrame:
    """Build one exploration frame from mode-independent layout inputs."""
    if region_width is None:
        region_width = map_width
    if region_height is None:
        region_height = map_height
    return make_exploration_frame(
        ctx,
        game_map,
        mode=mode,
        location=location,
        region_x=region_x,
        region_y=region_y,
        region_w=region_width,
        region_h=region_height,
        camera_x=camera_x,
        camera_y=camera_y,
        centered=centered,
        has_trade_terminal=has_trade_terminal,
        has_mech_terminal=has_mech_terminal,
        has_armory_terminal=has_armory_terminal,
    )


def _command_from_data(data: Any) -> world.WorldDrawCommand:
    """Normalize one renderer-neutral command from an object or mapping."""
    if isinstance(data, dict):
        return world.WorldDrawCommand(
            x=int(data["x"]),
            y=int(data["y"]),
            char=str(data["char"]),
            fg=tuple(data["fg"]),
            bg=None if data.get("bg") is None else tuple(data["bg"]),
        )
    return world.WorldDrawCommand(
        x=int(data.x),
        y=int(data.y),
        char=str(data.char),
        fg=tuple(int(value) for value in data.fg),
        bg=None if data.bg is None else tuple(int(value) for value in data.bg),
    )


def _frame_from_payload(data: dict[str, Any]) -> WorldFrame:
    """Deserialize one complete frame from worker input."""
    return WorldFrame(
        logical_size=tuple(data["logical_size"]),
        commands=tuple(_command_from_data(command) for command in data["commands"]),
        default_bg=None if data.get("default_bg") is None else tuple(data["default_bg"]),
    )


def _draw_frame(
    pygame: Any,
    engine: pygame_engine.PygameEngine,
    frame: WorldFrame,
) -> None:
    """Paint one exploration frame onto the worker's logical surface."""
    if engine.logical_surface is None or engine.glyphs is None:
        raise RuntimeError("Pygame world engine is not open")
    clear_color = frame.default_bg or (0, 0, 0)
    engine.logical_surface.fill((*clear_color, 255))
    for command in frame.commands:
        engine.glyphs.blit(
            engine.logical_surface,
            command.char,
            command.x * engine.glyphs.tile_width,
            command.y * engine.glyphs.tile_height,
            fg=command.fg,
            bg=command.bg,
        )


def _worker_main() -> int:
    """Run the Pygame worker until the parent closes its input pipe."""
    first_line = sys.stdin.readline()
    if not first_line:
        return 0
    first_frame = _frame_from_payload(json.loads(first_line))
    pygame = pygame_engine._load_pygame()
    logical_width, logical_height = first_frame.logical_size
    config = replace(
        pygame_engine.PygameEngineConfig(),
        logical_width=logical_width,
        logical_height=logical_height,
        window_width=logical_width,
        window_height=logical_height,
    )
    engine = pygame_engine.PygameEngine(pygame, config).open()
    frames: queue.Queue[WorldFrame | None] = queue.Queue(maxsize=2)
    stop = threading.Event()

    def _read_frames() -> None:
        """Read parent frames without blocking the Pygame event loop."""
        try:
            for line in sys.stdin:
                if stop.is_set():
                    break
                frame = _frame_from_payload(json.loads(line))
                try:
                    frames.get_nowait()
                except queue.Empty:
                    pass
                frames.put(frame)
        except (EOFError, OSError, ValueError, KeyError, TypeError):
            pass
        finally:
            stop.set()
            try:
                frames.put_nowait(None)
            except queue.Full:
                pass

    reader = threading.Thread(target=_read_frames, daemon=True)
    reader.start()
    current: WorldFrame | None = first_frame
    clock = pygame.time.Clock()
    try:
        while not stop.is_set():
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    stop.set()
                    break
            try:
                incoming = frames.get_nowait()
            except queue.Empty:
                incoming = current
            if incoming is None:
                clock.tick(60)
                continue
            current = incoming
            _draw_frame(pygame, engine, current)
            engine.present()
            clock.tick(60)
    finally:
        stop.set()
        reader.join(timeout=1)
        engine.close()
    return 0


class PygameWorldPreview:
    """Parent-side handle for the isolated live world preview."""

    def __init__(self, process: subprocess.Popen[str]):
        self._process = process
        self._closed = False
        atexit.register(self.close)

    @classmethod
    def start(cls) -> "PygameWorldPreview":
        """Start the worker or raise ``PygameWorldUnavailable``."""
        environment = {**os.environ, "PYGAME_HIDE_SUPPORT_PROMPT": "1"}
        try:
            process = subprocess.Popen(
                [sys.executable, "-m", f"{__package__}.pygame_world", "--worker"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                env=environment,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise PygameWorldUnavailable(
                "Pygame world preview could not start."
            ) from exc
        return cls(process)

    @property
    def alive(self) -> bool:
        """Whether the worker is still available for new frames."""
        return not self._closed and self._process.poll() is None

    def send(self, frame: WorldFrame) -> bool:
        """Send the latest frame, returning False after worker failure."""
        if not self.alive or self._process.stdin is None:
            return False
        try:
            self._process.stdin.write(json.dumps(frame.payload()) + "\n")
            self._process.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            self.close()
            return False
        return True

    def close(self) -> None:
        """Close the worker process and its input pipe."""
        if self._closed:
            return
        self._closed = True
        if self._process.stdin is not None:
            try:
                self._process.stdin.close()
            except OSError:
                pass
        try:
            self._process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            self._process.terminate()
            try:
                self._process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self._process.kill()


class PygameWorldUnavailable(RuntimeError):
    """Raised when the world preview cannot start."""


def start_if_enabled() -> PygameWorldPreview:
    """Start the world preview for the mandatory Pygame presentation."""
    return PygameWorldPreview.start()


if __name__ == "__main__":
    raise SystemExit(_worker_main() if "--worker" in sys.argv else 2)
