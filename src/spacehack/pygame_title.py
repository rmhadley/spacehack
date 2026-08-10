"""Pygame presentation for the title splash and Start/Continue menu."""
from __future__ import annotations

import random
from typing import Any

from . import pygame_menu, pygame_ui, ui


_TITLE_ART: tuple[str, ...] = tuple(getattr(ui, "_TITLE_ART", ()))
_SHIP_ART: tuple[str, ...] = tuple(getattr(ui, "_SHIP_ART", ()))
_SPLASH_BODY: tuple[str, ...] = (
    "The year is 2200. Humankind has spread across a dozen star systems,",
    "linked by jump gates of unknown origin. You are a freelance pilot",
    "making a living on the frontier - trading, bounty hunting, and",
    "surviving where the law is what you make of it.",
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
    items.extend((
        pygame_menu.MenuItem(
            "TUTORIAL", "Learn the frontier systems in a guided run.", "TUTORIAL",
        ),
        pygame_menu.MenuItem(
            "EXIT", "Close spacehack.", "EXIT",
        ),
    ))
    return tuple(items)


def frames(save_available: bool) -> tuple[pygame_menu.MenuFrame, ...]:
    """Build every selection state for the shared title menu."""
    items = _items(save_available)
    art = _TITLE_ART
    return tuple(
        pygame_menu.MenuFrame(
            title="SPACEHACK",
            body="The frontier is waiting.",
            items=items,
            hints=("ARROW KEYS / j,k navigate   ENTER select   ESC exit",),
            selected=selected,
            art=art,
            art_color=pygame_ui.DEFAULT_PALETTE.title,
        )
        for selected in range(len(items))
    )


def _splash_layout(font: Any, width: int, height: int) -> dict[str, int]:
    """Return pixel positions for a splash whose artwork cannot overlap."""
    line_height = font.get_linesize()
    title_y = max(55, int(height * 0.12))
    prompt_y = height - 78
    flavor_y = title_y + len(_TITLE_ART) * line_height + 34
    ship_y = flavor_y + len(_SPLASH_BODY) * line_height + 14
    ship_width = max(
        (pygame_ui.measure_font(font, line) for line in _SHIP_ART),
        default=0,
    )
    ship_x = max(24, width - ship_width - 34)
    ship_bottom = ship_y + len(_SHIP_ART) * line_height
    planet_y = min(
        height - 188,
        prompt_y - len(_PLANET_ART) * line_height - line_height - 10,
    )
    planet_x = 52
    planet_width = max(
        (pygame_ui.measure_font(font, line) for line in _PLANET_ART),
        default=0,
    )
    planet_bottom = planet_y + len(_PLANET_ART) * line_height
    title_width = max(
        (pygame_ui.measure_font(font, line) for line in _TITLE_ART),
        default=0,
    )
    body_width = max(
        (pygame_ui.measure_font(font, line) for line in _SPLASH_BODY),
        default=0,
    )
    if (
        title_width > width - 100
        or body_width > width - 100
        or ship_x + ship_width > width - 24
        or ship_bottom > prompt_y - line_height - 24
        or planet_x + planet_width > width - 24
        or planet_bottom > prompt_y - line_height - 10
        or planet_y < 24
    ):
        raise ValueError("title splash artwork does not fit the shared surface")
    return {
        "line_height": line_height,
        "title_y": title_y,
        "flavor_y": flavor_y,
        "ship_x": ship_x,
        "ship_y": ship_y,
        "ship_width": ship_width,
        "ship_bottom": ship_bottom,
        "planet_x": planet_x,
        "planet_y": planet_y,
        "planet_width": planet_width,
        "planet_bottom": planet_bottom,
        "prompt_y": prompt_y,
    }


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


def _draw_splash(
    pygame: Any,
    screen: Any,
    font: Any,
) -> None:
    """Paint the complete illustrated splash frame."""
    width, height = screen.get_size()
    screen.fill(pygame_ui.DEFAULT_PALETTE.background)
    _draw_splash_border(pygame, screen, width, height)
    _draw_splash_stars(pygame, screen, font, width, height)

    layout = _splash_layout(font, width, height)
    line_height = layout["line_height"]
    content = pygame_ui.Rect(0, 0, width, height)
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

    for index, line in enumerate(_SHIP_ART):
        pygame_ui.draw_text(
            pygame, screen, font, line,
            layout["ship_x"], layout["ship_y"] + index * line_height,
            color=_SHIP_COLORS[index % len(_SHIP_COLORS)],
        )

    for index, line in enumerate(_PLANET_ART):
        pygame_ui.draw_text(
            pygame, screen, font, line, layout["planet_x"],
            layout["planet_y"] + index * line_height,
            color=ui.COLOR_SPLASH_BORDER,
        )
    pygame_ui.draw_text(
        pygame, screen, font, "◄", layout["planet_x"] + font.get_linesize(),
        layout["planet_y"] + 2 * line_height,
        color=ui.COLOR_SPLASH_ART,
    )

    pygame_ui.draw_centered_text(
        pygame, screen, font, "-------", content,
        layout["prompt_y"] - line_height,
        color=ui.COLOR_SPLASH_BORDER,
    )
    pygame_ui.draw_centered_text(
        pygame, screen, font, "Press any key to begin", content,
        layout["prompt_y"], color=ui.COLOR_SPLASH_PROMPT,
    )


def run_splash_for_context(context: Any) -> None:
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


def run_for_context(context: Any, save_available: bool) -> tuple[ui.TitleMenuOutcome, int]:
    """Run the title menu in the existing shared Pygame window."""
    outcome, action, selected = pygame_menu.run_for_context(
        context,
        frames(save_available),
        caption="spacehack",
    )
    if outcome in {"QUIT", "BACK"}:
        return ui.TitleMenuOutcome.EXIT, selected
    if outcome != "SELECT":
        raise RuntimeError("Pygame title menu returned no outcome")
    title_outcome = _TITLE_ACTIONS.get(action)
    if title_outcome is None:
        raise RuntimeError("Pygame title menu returned an unknown action")
    return title_outcome, selected
