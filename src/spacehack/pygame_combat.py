"""Pygame presentation for the turn-based combat loop.

The game process remains authoritative for combat state and mutations. Combat
frames render through the shared Pygame runtime: the map/HUD cells blit as
bitmap glyphs and the native overlay paints the HUD, message band, shields,
floaters, and the target card.
"""
from __future__ import annotations

from typing import Any

from . import pygame_overlay, pygame_ui, pygame_world
from .engine import HUD_WIDTH, MSG_LOG_HEIGHT, SCREEN_HEIGHT, SCREEN_WIDTH
from .framebuffer import FrameBuffer
from .game_context import GameContext


class PygameCombatUnavailable(RuntimeError):
    """Raised when the shared Pygame combat presentation is not available."""


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


def _combat_floaters(ctx: GameContext | None) -> tuple:
    """Return + consume the current frame's native floating combat text.

    Consume-on-read: each presented frame draws whatever floaters the
    shot animation queued, and a frame with no active shot draws none.
    """
    if ctx is None:
        return ()
    from .combat import _animations
    return _animations.active_floaters()


def _combat_target_card(ctx: GameContext | None):
    """Return the native info card for the targeted combatant, if any.

    Both rules modules own a ``presentation_target_card``; space is
    checked first because its session carries an ``active`` flag, so a
    stale ground card from an earlier fight can't leak into a space fight
    (and vice versa).
    """
    if ctx is None:
        return None
    from .combat import _rules_ground, _rules_space
    _space = _rules_space.presentation_target_card(ctx=ctx)
    if _space is not None:
        return _space
    return _rules_ground.presentation_target_card(ctx=ctx)


_DEATH_LINES: tuple[str, ...] = (
    "SHIP DESTROYED",
    "Your ship has been destroyed.",
    "All crew lost. All cargo lost.",
)


def _draw_death_lines(pygame: Any, screen: Any, lines: tuple[str, ...], font_path: str) -> None:
    """Paint the death frame's centered title, body, and prompt lines."""
    width, height = screen.get_size()
    title_font = pygame.font.Font(font_path, max(24, height // 15))
    body_font = pygame.font.Font(font_path, max(14, height // 40))
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
    pygame_ui.draw_centered_text(
        pygame, screen, body_font,
        "Press any key to return to the main menu",
        content, height - 130, color=(255, 240, 175),
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
    screen = engine.logical_surface
    screen.fill((40, 0, 0))  # dark red
    _draw_death_lines(engine.pygame, screen, lines, pygame_menu._font_path(engine.pygame))
    engine.present()


def _map_console(console: FrameBuffer, all_commands: tuple) -> pygame_world.CaptureConsole:
    """Copy map-region cells into a capture console for shared presentation."""
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
    return map_console


def present(ctx: GameContext, console: FrameBuffer) -> None:
    """Present a combat frame through the shared Pygame runtime."""
    from . import pygame_runtime

    if not pygame_runtime.is_shared_context(ctx.context):
        raise PygameCombatUnavailable("Shared Pygame combat presentation is not open")
    all_commands = _console_commands(console)
    overlay = pygame_overlay._frame_from_commands(
        all_commands,
        screen_width=SCREEN_WIDTH,
        screen_height=SCREEN_HEIGHT,
        hud_view_height=SCREEN_HEIGHT - MSG_LOG_HEIGHT,
        # The combat console is one HUD-width wider than the window so
        # HUD lines can use the panel's full ~40 half-width characters.
        hud_x_max=SCREEN_WIDTH + HUD_WIDTH,
        messages=pygame_overlay._message_segments(
            ctx, SCREEN_WIDTH, SCREEN_HEIGHT,
        ),
        shields=_combat_shield_bubbles(ctx),
        floaters=_combat_floaters(ctx),
        target=_combat_target_card(ctx),
    )
    ctx.context.present(_map_console(console, all_commands), overlay=overlay)
