"""Pygame presentation worker for the turn-based combat loop.

The game process remains authoritative for combat state and mutations. It sends
renderer-neutral cell commands and receives only opaque input actions. A
persistent worker keeps one readable Pygame window open across turns and
animations instead of spawning a window for every keypress.
"""
from __future__ import annotations

from dataclasses import asdict
import json
import os
import queue
import subprocess
import sys
import threading
from typing import Any

from . import pygame_engine, pygame_overlay, pygame_ui, pygame_world
from .engine import HUD_WIDTH, MSG_LOG_HEIGHT, SCREEN_HEIGHT, SCREEN_WIDTH


class PygameCombatUnavailable(RuntimeError):
    """Raised when the combat worker cannot present or return input."""


class PygameCombatQuit(RuntimeError):
    """Raised when the combat window is closed."""


def enabled() -> bool:
    """Return whether the Pygame combat presentation is active."""
    return pygame_ui.presentation_enabled()


def _console_commands(console: Any) -> tuple[pygame_world.world.WorldDrawCommand, ...]:
    """Extract renderer-neutral cells from a capture or native tcod console."""
    commands = getattr(console, "commands", None)
    if commands is not None:
        try:
            return tuple(
                pygame_world.world.WorldDrawCommand(
                    x=int(command.x),
                    y=int(command.y),
                    char=str(command.char),
                    fg=tuple(int(value) for value in command.fg),
                    bg=None if command.bg is None else tuple(int(value) for value in command.bg),
                )
                for command in commands
            )
        except (AttributeError, IndexError, TypeError, ValueError) as exc:
            raise PygameCombatUnavailable("Combat console cell data is invalid") from exc

    chars = getattr(console, "ch", None)
    foreground = getattr(console, "fg", None)
    background = getattr(console, "bg", None)
    if chars is None or foreground is None or background is None:
        raise PygameCombatUnavailable("Combat console has no readable cell data")

    height, width = chars.shape
    if foreground.shape != (height, width, 3) or background.shape != (height, width, 3):
        raise PygameCombatUnavailable("Combat console color planes have invalid shapes")
    try:
        return tuple(
            pygame_world.world.WorldDrawCommand(
                x=x,
                y=y,
                char=chr(int(chars[y, x])),
                fg=tuple(int(value) for value in foreground[y, x]),
                bg=tuple(int(value) for value in background[y, x]),
            )
            for y in range(height)
            for x in range(width)
        )
    except (AttributeError, IndexError, TypeError, ValueError) as exc:
        raise PygameCombatUnavailable("Combat console cell data is invalid") from exc


def _frame_payload(console: Any, *, interactive: bool) -> dict[str, Any]:
    """Serialize a map-only combat console plus its native HUD/log overlay."""
    all_commands = _console_commands(console)
    commands = tuple(
        command for command in all_commands
        if command.x < SCREEN_WIDTH - HUD_WIDTH
        and command.y < SCREEN_HEIGHT - MSG_LOG_HEIGHT
    )
    overlay = pygame_overlay._frame_from_commands(
        all_commands,
        screen_width=1600 // pygame_world.TILE_WIDTH,
        screen_height=960 // pygame_world.TILE_HEIGHT,
        hud_view_height=(960 // pygame_world.TILE_HEIGHT) - pygame_world.MSG_LOG_HEIGHT,
    )
    return {
        "logical_size": (1600, 960),
        "commands": [asdict(command) for command in commands],
        "overlay": pygame_overlay.payload(overlay),
        "interactive": interactive,
    }


def _action_for_key(pygame: Any, event: Any) -> str:
    """Map one Pygame key event to an opaque combat action."""
    if event.type == pygame.QUIT:
        return "QUIT"
    if event.type != pygame.KEYDOWN:
        return ""
    if event.key == pygame.K_ESCAPE:
        return "FLEE"
    if event.key == pygame.K_TAB:
        return "TARGET"
    directional_keys = {
        pygame.K_UP: "up",
        pygame.K_DOWN: "down",
        pygame.K_LEFT: "left",
        pygame.K_RIGHT: "right",
    }
    if event.key in directional_keys:
        return f"MOVE:{directional_keys[event.key]}"
    key_name = pygame.key.name(event.key).lower()
    if key_name in {"h", "j", "k", "l", "y", "u", "b", "n"}:
        return f"MOVE:{key_name}"
    if key_name in {".", "period"}:
        return "WAIT"
    direct_actions = {"s": "DEFENSE", "w": "WAIT", "f": "FIRE"}
    if key_name in direct_actions:
        return direct_actions[key_name]
    if key_name in {str(index) for index in range(1, 10)}:
        return f"WEAPON:{int(key_name) - 1}"
    if pygame_ui.is_guide_key(pygame, event):
        return "GUIDE"
    return ""


def _command_from_payload(data: dict[str, Any]):
    """Deserialize one world draw command."""
    return pygame_world.world.WorldDrawCommand(
        x=int(data["x"]),
        y=int(data["y"]),
        char=str(data["char"]),
        fg=tuple(data["fg"]),
        bg=None if data.get("bg") is None else tuple(data["bg"]),
    )


def _frame_from_payload(data: dict[str, Any]) -> tuple[pygame_world.WorldFrame, pygame_overlay.OverlayFrame, bool]:
    """Deserialize a combat frame, native overlay, and input flag."""
    frame = pygame_world.WorldFrame(
        logical_size=tuple(data["logical_size"]),
        commands=tuple(_command_from_payload(command) for command in data["commands"]),
    )
    overlay = pygame_overlay.frame_from_payload(data["overlay"])
    return frame, overlay, bool(data.get("interactive", False))


def present(ctx: Any, console: Any) -> None:
    """Present a combat frame through the shared Pygame runtime."""
    presenter = getattr(ctx, "_pygame_combat_presenter", None)
    if presenter is not None:
        try:
            presenter.show(console, interactive=False)
            return
        except PygameCombatUnavailable:
            presenter.close()
            ctx._pygame_combat_presenter = None
    from . import pygame_runtime

    if pygame_runtime.is_shared_context(ctx.context):
        all_commands = _console_commands(console)
        overlay = pygame_overlay._frame_from_commands(
            all_commands,
            screen_width=SCREEN_WIDTH,
            screen_height=SCREEN_HEIGHT,
            hud_view_height=SCREEN_HEIGHT - MSG_LOG_HEIGHT,
        )
        map_console = pygame_world.CaptureConsole(SCREEN_WIDTH, SCREEN_HEIGHT)
        map_console.commands.extend(
            command for command in all_commands
            if command.x < SCREEN_WIDTH - HUD_WIDTH
            and command.y < SCREEN_HEIGHT - MSG_LOG_HEIGHT
        )
        ctx.context.present(map_console, overlay=overlay)
        return
    raise PygameCombatUnavailable("Shared Pygame combat presentation is not open")


def _worker_main() -> int:
    """Run the persistent Pygame combat worker."""
    first_line = sys.stdin.readline()
    if not first_line:
        return 0
    try:
        first_frame, first_overlay, first_interactive = _frame_from_payload(json.loads(first_line))
        pygame = pygame_engine._load_pygame()
    except (ValueError, KeyError, TypeError, RuntimeError):
        return 2

    logical_width, logical_height = first_frame.logical_size
    config = pygame_engine.PygameEngineConfig(
        logical_width=logical_width,
        logical_height=logical_height,
        window_width=logical_width,
        window_height=logical_height,
        title="spacehack - combat",
    )
    engine = pygame_engine.PygameEngine(pygame, config).open()
    frames: queue.Queue[tuple[pygame_world.WorldFrame, pygame_overlay.OverlayFrame, bool] | None] = queue.Queue(maxsize=2)
    stop = threading.Event()

    def _read_frames() -> None:
        """Read parent frames while the worker continues pumping events."""
        try:
            for line in sys.stdin:
                if stop.is_set():
                    break
                frame = _frame_from_payload(json.loads(line))
                while True:
                    try:
                        frames.get_nowait()
                    except queue.Empty:
                        break
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
    current = first_frame
    overlay = first_overlay
    interactive = first_interactive
    clock = pygame.time.Clock()
    try:
        while not stop.is_set():
            try:
                incoming = frames.get_nowait()
            except queue.Empty:
                incoming = None
            if incoming is not None:
                current, overlay, interactive = incoming
            pygame_world._draw_frame(pygame, engine, current)
            pygame_overlay.draw(
                pygame,
                engine.logical_surface,
                overlay,
                logical_width=logical_width,
                logical_height=logical_height,
            )
            engine.present()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    print(json.dumps({"action": "QUIT"}), flush=True)
                    stop.set()
                    break
                if not interactive:
                    continue
                action = _action_for_key(pygame, event)
                if not action:
                    continue
                print(json.dumps({"action": action}), flush=True)
                interactive = False
                if action == "QUIT":
                    stop.set()
                    break
            clock.tick(60)
    finally:
        stop.set()
        reader.join(timeout=1)
        engine.close()
    return 0


class PygameCombatPresenter:
    """Parent-side handle for a persistent combat presentation worker."""

    def __init__(self, process: subprocess.Popen[str]):
        self._process = process
        self._closed = False

    @classmethod
    def start(cls) -> "PygameCombatPresenter":
        """Start the worker or raise ``PygameCombatUnavailable``."""
        environment = {**os.environ, "PYGAME_HIDE_SUPPORT_PROMPT": "1"}
        try:
            process = subprocess.Popen(
                pygame_ui.worker_command(f"{__package__}.pygame_combat"),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                env=environment,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise PygameCombatUnavailable("Pygame combat worker could not start") from exc
        return cls(process)

    @property
    def alive(self) -> bool:
        """Whether the worker process is still available."""
        return not self._closed and self._process.poll() is None

    def show(self, console: Any, *, interactive: bool) -> None:
        """Send a captured console frame without waiting for input."""
        if not self.alive or self._process.stdin is None:
            raise PygameCombatUnavailable("Pygame combat worker stopped")
        try:
            self._process.stdin.write(
                json.dumps(_frame_payload(console, interactive=interactive)) + "\n"
            )
            self._process.stdin.flush()
        except (BrokenPipeError, OSError, ValueError) as exc:
            self.close()
            raise PygameCombatUnavailable("Pygame combat worker stopped") from exc

    def wait_action(self) -> str:
        """Wait for one opaque input action from the worker."""
        if not self.alive or self._process.stdout is None:
            raise PygameCombatUnavailable("Pygame combat worker stopped")
        line = self._process.stdout.readline()
        if not line:
            raise PygameCombatUnavailable("Pygame combat worker returned no action")
        try:
            action = str(json.loads(line)["action"])
        except (ValueError, KeyError, TypeError) as exc:
            raise PygameCombatUnavailable("Pygame combat worker returned bad input") from exc
        if action == "QUIT":
            raise PygameCombatQuit()
        return action

    def close(self) -> None:
        """Close the worker process and its pipes."""
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


if __name__ == "__main__":
    raise SystemExit(_worker_main() if "--worker" in sys.argv else 2)
