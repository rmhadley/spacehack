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
from .framebuffer import FrameBuffer
from .game_context import GameContext


class PygameCombatUnavailable(RuntimeError):
    """Raised when the combat worker cannot present or return input."""


class PygameCombatQuit(RuntimeError):
    """Raised when the combat window is closed."""


def enabled() -> bool:
    """Return whether the Pygame combat presentation is active."""
    return pygame_ui.presentation_enabled()


def _console_commands(console: FrameBuffer) -> tuple[pygame_world.world.WorldDrawCommand, ...]:
    """Extract cells from a framebuffer or renderer-neutral test fixture."""
    try:
        if hasattr(console, "to_commands"):
            return console.to_commands()
        commands = getattr(console, "commands")
        return tuple(pygame_world._command_from_data(command) for command in commands)
    except (AttributeError, IndexError, TypeError, ValueError) as exc:
        raise PygameCombatUnavailable("Combat frame cell data is invalid") from exc


def _default_background(console: Any) -> tuple[int, int, int] | None:
    """Return a framebuffer background when the object provides one."""
    getter = getattr(console, "default_background", None)
    return None if getter is None else getter()


def _combat_shield_bubbles(ctx: GameContext | None) -> tuple:
    """Return live space-combat bubbles without coupling the overlay to rules."""
    if ctx is None:
        return ()
    from .combat import _rules_space
    return _rules_space.presentation_shield_bubbles(ctx=ctx)


def _frame_payload(
    console: FrameBuffer,
    *,
    interactive: bool,
    ctx: GameContext | None = None,
) -> dict[str, Any]:
    """Serialize a map-only combat frame plus its native HUD/log overlay."""
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
        hud_view_height=(960 // pygame_world.TILE_HEIGHT) - MSG_LOG_HEIGHT,
        shields=_combat_shield_bubbles(ctx),
    )
    return {
        "logical_size": (1600, 960),
        "commands": [asdict(command) for command in commands],
        "default_bg": _default_background(console),
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
    direct_actions = {"s": "DEFENSE", "w": "WAIT", "f": "FIRE", "c": "CHARACTER"}
    if key_name in direct_actions:
        return direct_actions[key_name]
    if key_name in {str(index) for index in range(1, 10)}:
        return f"WEAPON:{int(key_name) - 1}"
    if pygame_ui.is_guide_key(pygame, event):
        return "GUIDE"
    return ""


def _frame_from_payload(data: dict[str, Any]) -> tuple[pygame_world.WorldFrame, pygame_overlay.OverlayFrame, bool]:
    """Deserialize a combat frame, native overlay, and input flag."""
    frame = pygame_world._frame_from_payload(data)
    overlay = pygame_overlay.frame_from_payload(data["overlay"])
    return frame, overlay, bool(data.get("interactive", False))


_DEATH_LINES: tuple[str, ...] = (
    "SHIP DESTROYED",
    "Your ship has been destroyed.",
    "All crew lost. All cargo lost.",
)


def present_death(ctx: GameContext, *, lines: tuple[str, ...] = ()) -> None:
    """Present a full-screen death frame: no HUD, no console log.

    Paints the entire shared surface dark red with a centered final
    message (``lines[0]`` is the title, the rest the body). The
    caller owns input waiting — this function only draws and flips.
    """
    from . import pygame_menu

    runtime = getattr(getattr(ctx, "context", None), "_runtime", None)
    engine = getattr(runtime, "engine", None)
    if engine is None or engine.logical_surface is None:
        raise PygameCombatUnavailable(
            "Shared Pygame death presentation is not open"
        )
    lines = lines or _DEATH_LINES
    if not lines:
        raise PygameCombatUnavailable("Death frame has no text")
    pygame = engine.pygame
    screen = engine.logical_surface
    width, height = screen.get_size()
    font_path = pygame_menu._font_path(pygame)
    title_font = pygame.font.Font(font_path, max(24, height // 15))
    body_font = pygame.font.Font(font_path, max(14, height // 40))
    screen.fill((40, 0, 0))  # dark red
    content = pygame_ui.Rect(0, 0, width, height)
    title, *body = lines
    title_y = int(height * 0.38)
    pygame_ui.draw_centered_text(
        pygame, screen, title_font, title, content, title_y,
        color=(255, 90, 90),
    )
    body_y = title_y + title_font.get_linesize() + 24
    for line in body:
        pygame_ui.draw_centered_text(
            pygame, screen, body_font, line, content, body_y,
            color=(235, 210, 210),
        )
        body_y += body_font.get_linesize() + 10
    prompt_y = height - 130
    pygame_ui.draw_centered_text(
        pygame, screen, body_font,
        "Press any key to return to the main menu",
        content, prompt_y, color=(255, 240, 175),
    )
    engine.present()


def present(ctx: GameContext, console: FrameBuffer) -> None:
    """Present a combat frame through the shared Pygame runtime."""
    presenter = getattr(ctx, "_pygame_combat_presenter", None)
    if presenter is not None:
        try:
            presenter.show(console, interactive=False, ctx=ctx)
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
            shields=_combat_shield_bubbles(ctx),
        )
        map_console = pygame_world.CaptureConsole(
            SCREEN_WIDTH,
            SCREEN_HEIGHT,
            background=_default_background(console),
        )
        for command in all_commands:
            if (
                command.x < SCREEN_WIDTH - HUD_WIDTH
                and command.y < SCREEN_HEIGHT - MSG_LOG_HEIGHT
            ):
                map_console.write_cell(
                    command.x,
                    command.y,
                    command.char,
                    fg=command.fg,
                    bg=command.bg,
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

    def show(self, console: Any, *, interactive: bool, ctx: GameContext | None = None) -> None:
        """Send a captured console frame without waiting for input."""
        if not self.alive or self._process.stdin is None:
            raise PygameCombatUnavailable("Pygame combat worker stopped")
        try:
            self._process.stdin.write(
                json.dumps(_frame_payload(console, interactive=interactive, ctx=ctx)) + "\n"
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
