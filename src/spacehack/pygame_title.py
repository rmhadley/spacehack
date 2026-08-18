"""Pygame presentation for the title splash and Start/Continue menu."""
from __future__ import annotations

import random
from dataclasses import replace
from typing import Any

from . import pygame_menu, pygame_story, pygame_ui, ui
from .display_config import DisplayConfig
from .pygame_runtime import PygameContext


_TITLE_ART: tuple[str, ...] = tuple(getattr(ui, "_TITLE_ART", ()))
_SHIP_ART: tuple[str, ...] = tuple(getattr(ui, "_SHIP_ART", ()))
_SPLASH_BODY: tuple[str, ...] = (
    "The year is 2200. Humankind has spread across many star systems,",
    "linked by jump gates. You are a freelance pilot",
    "making a living on the frontier: trading, bounty hunting, and",
    "surviving.",
)
_PLANET_ART: tuple[str, ...] = (
    "  ┌────┐",
    " ─│    │─",
    "──│    │──",
    " ─│    │─",
    "  └────┘",
)
_SHIP_COLORS: tuple[tuple[int, int, int], ...] = (
    (180, 180, 210),
    (200, 200, 230),
    (220, 220, 245),
    (210, 210, 235),
    (210, 210, 235),
    (210, 210, 235),
    (200, 200, 225),
    (180, 170, 190),
    (190, 180, 200),
    (190, 180, 200),
    (170, 155, 180),
    (255, 120, 60),
    (255, 180, 50),
    (255, 210, 100),
    (220, 200, 150),
)


def enabled() -> bool:
    """Return whether the shared Pygame title presentation is active."""
    return pygame_ui.presentation_enabled()


_TITLE_ACTIONS = {
    "NEW_GAME": ui.TitleMenuOutcome.NEW_GAME,
    "CONTINUE": ui.TitleMenuOutcome.CONTINUE,
    "TUTORIAL": ui.TitleMenuOutcome.TUTORIAL,
    "EXIT": ui.TitleMenuOutcome.EXIT,
}


def _items(save_available: bool) -> tuple[pygame_menu.MenuItem, ...]:
    """Return the selectable title actions, omitting unavailable Continue."""
    items = [
        pygame_menu.MenuItem(
            "START NEW GAME", "Create a new pilot and choose your identity.", "NEW_GAME",
        ),
    ]
    if save_available:
        items.append(
            pygame_menu.MenuItem(
                "CONTINUE", "Resume the autosaved run from its exact last state.", "CONTINUE",
            )
        )
    items.append(
        pygame_menu.MenuItem(
            "OPTIONS", "Change fullscreen and window preferences.", "OPTIONS",
        )
    )
    items.extend((
        pygame_menu.MenuItem(
            "TUTORIAL", "Learn the frontier systems in a guided run.", "TUTORIAL",
        ),
        pygame_menu.MenuItem(
            "EXIT", "Close spacehack.", "EXIT",
        ),
    ))
    return tuple(items)


_WINDOW_PRESETS: tuple[tuple[int, int], ...] = (
    (1280, 768),
    (1600, 960),
    (1920, 1152),
)


def _options_items(config: DisplayConfig) -> tuple[pygame_menu.MenuItem, ...]:
    """Build display preference rows for the title Options menu."""
    mode = "On" if config.fullscreen else "Off"
    return (
        pygame_menu.MenuItem(
            f"FULLSCREEN: {mode}",
            "Toggle fullscreen presentation.",
            "TOGGLE_FULLSCREEN",
        ),
        pygame_menu.MenuItem(
            f"WINDOW SIZE: {config.window_width} x {config.window_height}",
            "Cycle the supported window sizes.",
            "CYCLE_WINDOW_SIZE",
        ),
        pygame_menu.MenuItem(
            "APPLY",
            "Apply and save these display preferences.",
            "APPLY_OPTIONS",
        ),
        pygame_menu.MenuItem(
            "BACK",
            "Discard changes and return to the title menu.",
            "BACK_OPTIONS",
        ),
    )


def options_frames(
    config: DisplayConfig,
    selected: int = 0,
) -> tuple[pygame_menu.MenuFrame, ...]:
    """Build the title Options menu for a pending display configuration."""
    items = _options_items(config)
    return tuple(
        pygame_menu.MenuFrame(
            title="OPTIONS",
            body="Display preferences are saved separately from game saves.",
            items=items,
            hints=(pygame_ui.modal_hint(
                pygame_ui.NAV_HINT, "ENTER select", "ESC back",
            ),),
            selected=index,
            initial_selected=selected,
            draw_log=False,
        )
        for index in range(len(items))
    )


def _next_window_size(config: DisplayConfig) -> tuple[int, int]:
    """Return the next supported window preset after the current size."""
    try:
        index = _WINDOW_PRESETS.index((config.window_width, config.window_height))
    except ValueError:
        index = -1
    return _WINDOW_PRESETS[(index + 1) % len(_WINDOW_PRESETS)]


def run_options_for_context(context: PygameContext) -> bool:
    """Run title display options; return True only after a successful Apply."""
    pending = context.display_config
    selected = 0
    while True:
        outcome, action, selected = pygame_menu.run_for_context(
            context,
            options_frames(pending, selected),
            caption="spacehack - options",
        )
        if outcome in {"QUIT", "BACK"} or action == "BACK_OPTIONS":
            return False
        if outcome != "SELECT":
            raise RuntimeError("Pygame Options menu returned no outcome")
        if action == "TOGGLE_FULLSCREEN":
            pending = replace(pending, fullscreen=not pending.fullscreen)
        elif action == "CYCLE_WINDOW_SIZE":
            width, height = _next_window_size(pending)
            pending = replace(pending, window_width=width, window_height=height)
        elif action == "APPLY_OPTIONS":
            try:
                context.apply_display_config(pending)
                context.save_display_config()
            except (OSError, RuntimeError, ValueError) as exc:
                pygame_story.dismiss(
                    context,
                    title="DISPLAY ERROR",
                    body=f"Could not apply display preferences: {exc}",
                    caption="spacehack - display error",
                )
                pending = context.display_config
            else:
                return True


def frames(save_available: bool) -> tuple[pygame_menu.MenuFrame, ...]:
    """Build every selection state for the shared title menu."""
    items = _items(save_available)
    art = _TITLE_ART
    return tuple(
        pygame_menu.MenuFrame(
            title="SPACEHACK",
            body="The frontier is waiting.",
            items=items,
            hints=(pygame_ui.modal_hint(
                pygame_ui.NAV_HINT, "ENTER select", "ESC exit",
            ),),
            selected=selected,
            initial_selected=1 if save_available else 0,
            art=art,
            art_color=pygame_ui.DEFAULT_PALETTE.title,
            draw_log=False,
        )
        for selected in range(len(items))
    )


def _splash_widths(font: Any) -> dict[str, int]:
    """Measure the fixed-width art groups used by the splash."""
    measure = lambda line: pygame_ui.measure_font(font, line)
    return {
        "ship_width": max((measure(line) for line in _SHIP_ART), default=0),
        "planet_width": max((measure(line) for line in _PLANET_ART), default=0),
        "title_width": max((measure(line) for line in _TITLE_ART), default=0),
        "body_width": max((measure(line) for line in _SPLASH_BODY), default=0),
    }


def _splash_layout_positions(
    line_height: int, width: int, height: int, widths: dict[str, int],
) -> dict[str, int]:
    """Calculate splash art and prompt positions."""
    title_y = max(55, int(height * 0.12))
    prompt_y = height - 78
    flavor_y = title_y + len(_TITLE_ART) * line_height + 34
    ship_y = flavor_y + len(_SPLASH_BODY) * line_height + 14
    ship_x = max(24, width - widths["ship_width"] - 34)
    planet_y = min(
        height - 188,
        prompt_y - len(_PLANET_ART) * line_height - line_height - 10,
    )
    return {
        "title_y": title_y,
        "flavor_y": flavor_y,
        "ship_x": ship_x,
        "ship_y": ship_y,
        "ship_bottom": ship_y + len(_SHIP_ART) * line_height,
        "planet_x": 52,
        "planet_y": planet_y,
        "planet_bottom": planet_y + len(_PLANET_ART) * line_height,
        "prompt_y": prompt_y,
    }


def _validate_splash_layout(
    width: int, height: int, line_height: int,
    widths: dict[str, int], positions: dict[str, int],
) -> None:
    """Reject a splash surface where its art would overlap or overflow."""
    if (
        widths["title_width"] > width - 100
        or widths["body_width"] > width - 100
        or positions["ship_x"] + widths["ship_width"] > width - 24
        or positions["ship_bottom"] > positions["prompt_y"] - line_height - 24
        or positions["planet_x"] + widths["planet_width"] > width - 24
        or positions["planet_bottom"] > positions["prompt_y"] - line_height - 10
        or positions["planet_y"] < 24
    ):
        raise ValueError("title splash artwork does not fit the shared surface")


def _splash_layout(font: Any, width: int, height: int) -> dict[str, int]:
    """Return pixel positions for a splash whose artwork cannot overlap."""
    line_height = font.get_linesize()
    widths = _splash_widths(font)
    positions = _splash_layout_positions(line_height, width, height, widths)
    _validate_splash_layout(width, height, line_height, widths, positions)
    return {"line_height": line_height, **widths, **positions}


def _splash_font(pygame: Any, width: int, height: int) -> Any:
    """Choose the largest crisp font that fits every splash element."""
    path = pygame_menu._font_path(pygame)
    for size in range(28, 11, -1):
        font = pygame.font.Font(path, size)
        try:
            _splash_layout(font, width, height)
        except ValueError:
            continue
        return font
    raise pygame_menu.PygameMenuUnavailable(
        "Shared Pygame surface is too small for the title splash"
    )


def _draw_splash_border(pygame: Any, screen: Any, width: int, height: int) -> None:
    """Paint the double-line frame around the illustrated splash."""
    color = ui.COLOR_SPLASH_BORDER
    outer = pygame.Rect(14, 14, width - 28, height - 28)
    inner = pygame.Rect(19, 19, width - 38, height - 38)
    pygame.draw.rect(screen, color, outer, width=2)
    pygame.draw.rect(screen, color, inner, width=1)


def _splash_star_positions(font: Any, width: int, height: int) -> tuple[tuple[int, int], ...]:
    """Return stable star positions outside every major splash element."""
    layout = _splash_layout(font, width, height)
    line_height = layout["line_height"]
    exclusions = (
        (0, layout["title_y"] - line_height, width, layout["title_y"] + len(_TITLE_ART) * line_height),
        (0, layout["flavor_y"] - 4, width, layout["flavor_y"] + len(_SPLASH_BODY) * line_height),
        (layout["ship_x"] - 8, layout["ship_y"] - 4, width, layout["ship_bottom"] + 4),
        (
            layout["planet_x"] - 12,
            layout["planet_y"] - 4,
            layout["planet_x"] + layout["planet_width"] + 12,
            layout["planet_bottom"] + 4,
        ),
        (0, layout["prompt_y"] - line_height - 8, width, height),
    )
    rng = random.Random(2200)
    positions: list[tuple[int, int]] = []
    attempts = 0
    while len(positions) < 80 and attempts < 800:
        attempts += 1
        x = rng.randint(32, max(32, width - 48))
        y = rng.randint(32, max(32, height - 150))
        if any(left <= x < right and top <= y < bottom for left, top, right, bottom in exclusions):
            continue
        positions.append((x, y))
    return tuple(positions)


def _draw_splash_stars(
    pygame: Any,
    screen: Any,
    font: Any,
    width: int,
    height: int,
) -> None:
    """Paint a stable starfield behind the title illustrations."""
    rng = random.Random(2200)
    for x, y in _splash_star_positions(font, width, height):
        brightness = rng.randint(100, 200)
        pygame_ui.draw_text(
            pygame, screen, font, rng.choice((".", ".", "*", ".")),
            x, y, color=(brightness, brightness, brightness),
        )


def _draw_splash_title(
    pygame: Any, screen: Any, font: Any, content: pygame_ui.Rect,
    layout: dict[str, int],
) -> None:
    """Paint the title and flavor text on the splash."""
    line_height = layout["line_height"]
    for index, line in enumerate(_TITLE_ART):
        pygame_ui.draw_centered_text(
            pygame, screen, font, line, content,
            layout["title_y"] + index * line_height,
            color=ui.COLOR_SPLASH_ART,
        )
    for index, line in enumerate(_SPLASH_BODY):
        pygame_ui.draw_centered_text(
            pygame, screen, font, line, content,
            layout["flavor_y"] + index * line_height,
            color=ui.COLOR_SPLASH_FLAVOR,
        )


def _draw_splash_ship_and_planet(
    pygame: Any, screen: Any, font: Any, layout: dict[str, int],
) -> None:
    """Paint the ship and planet illustrations."""
    line_height = layout["line_height"]
    for index, line in enumerate(_SHIP_ART):
        pygame_ui.draw_text(
            pygame, screen, font, line,
            layout["ship_x"], layout["ship_y"] + index * line_height,
            color=_SHIP_COLORS[index % len(_SHIP_COLORS)],
        )
    for line_index, line in enumerate(_PLANET_ART):
        pygame_ui.draw_text(
            pygame, screen, font, line, layout["planet_x"],
            layout["planet_y"] + line_index * line_height,
            color=ui.COLOR_SPLASH_BORDER,
        )
    pygame_ui.draw_text(
        pygame, screen, font, "◄", layout["planet_x"] + line_height,
        layout["planet_y"] + 2 * line_height,
        color=ui.COLOR_SPLASH_ART,
    )


def _draw_splash_prompt(
    pygame: Any, screen: Any, font: Any,
    content: pygame_ui.Rect, prompt_y: int,
) -> None:
    """Paint the splash separator and input prompt."""
    line_height = font.get_linesize()
    pygame_ui.draw_centered_text(
        pygame, screen, font, "-------", content,
        prompt_y - line_height, color=ui.COLOR_SPLASH_BORDER,
    )
    pygame_ui.draw_centered_text(
        pygame, screen, font, "Press any key to begin", content,
        prompt_y, color=ui.COLOR_SPLASH_PROMPT,
    )


def _draw_splash(
    pygame: Any, screen: Any, font: Any,
) -> None:
    """Paint the complete illustrated splash frame."""
    width, height = screen.get_size()
    screen.fill(pygame_ui.DEFAULT_PALETTE.background)
    _draw_splash_border(pygame, screen, width, height)
    _draw_splash_stars(pygame, screen, font, width, height)
    layout = _splash_layout(font, width, height)
    content = pygame_ui.Rect(0, 0, width, height)
    _draw_splash_title(pygame, screen, font, content, layout)
    _draw_splash_ship_and_planet(pygame, screen, font, layout)
    _draw_splash_prompt(pygame, screen, font, content, layout["prompt_y"])


def run_splash_for_context(context: PygameContext) -> None:
    """Show the illustrated title splash in the existing shared Pygame window."""
    runtime = getattr(context, "_runtime", None)
    engine = getattr(runtime, "engine", None)
    if engine is None or engine.logical_surface is None:
        raise pygame_menu.PygameMenuUnavailable("Shared Pygame runtime is not open")
    pygame = engine.pygame
    screen = engine.logical_surface
    width, height = screen.get_size()
    font = _splash_font(pygame, width, height)
    while True:
        _draw_splash(pygame, screen, font)
        engine.present()
        event = pygame.event.wait()
        if event.type == pygame.QUIT:
            return
        if event.type == pygame.KEYDOWN:
            return


def run_for_context(context: PygameContext, save_available: bool) -> tuple[ui.TitleMenuOutcome, int]:
    """Run the title menu in the existing shared Pygame window."""
    outcome, action, selected = pygame_menu.run_for_context(
        context,
        frames(save_available),
        caption="spacehack",
    )
    if outcome in {"QUIT", "BACK"}:
        return ui.TitleMenuOutcome.EXIT, selected
    if outcome == "GUIDE":
        # The title screen has no game context yet, so the guide cannot
        # open — treat ? as a no-op and keep the menu on screen.
        return ui.TitleMenuOutcome.IGNORE, selected
    if outcome != "SELECT":
        raise RuntimeError("Pygame title menu returned no outcome")
    if action == "OPTIONS":
        run_options_for_context(context)
        return ui.TitleMenuOutcome.IGNORE, selected
    title_outcome = _TITLE_ACTIONS.get(action)
    if title_outcome is None:
        raise RuntimeError("Pygame title menu returned an unknown action")
    return title_outcome, selected
