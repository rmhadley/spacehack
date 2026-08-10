"""Main quest Act 1: the first post-prison orbit scene."""

from __future__ import annotations

from enum import Enum, auto

import tcod.event

from .. import message_log
from .. import ui
from ..data.main_quest.act1_post_prison import (
    ARCHIVE_DISCLOSURES,
    find_archive_disclosure,
)
from ..engine import SCREEN_HEIGHT, SCREEN_WIDTH, make_console
from ._core import STATUS_AVAILABLE, _schedule_next_step


class OrbitDisclosure(Enum):
    """The player's first decision about sharing the recovered archive."""

    DIAGNOSTIC_FRAGMENT = "diagnostic_fragment"
    ARCHIVE_SEALED = "archive_sealed"
    SAFE_DESTINATION = "safe_destination"


class OrbitSceneOutcome(Enum):
    """Result of one event in the orbit disclosure modal."""

    IGNORE = auto()
    CONFIRM = auto()
    QUIT = auto()


_DISCLOSURE_OPTIONS = tuple(
    (OrbitDisclosure(spec.key), spec)
    for spec in ARCHIVE_DISCLOSURES
)

_FACTION_READINGS = {
    "militia": "The Militia calls it a containment record and warns you not to transmit it.",
    "merchants": "The Guild sees infrastructure: routes, stations, and technology someone will try to own.",
    "bar": "The Bar hears a route to a score - and recognizes the shape of an old warning underneath it.",
    "lab": "The Lab calls it layered structure, not language, and refuses to separate the warning from the route.",
}


def _selected_disclosure(selected: int) -> OrbitDisclosure:
    """Return the disclosure key for a wrapped menu index."""
    return _DISCLOSURE_OPTIONS[selected % len(_DISCLOSURE_OPTIONS)][0]


def _update_orbit_scene(
    event: tcod.event.Event,
    selected: int,
) -> tuple[OrbitSceneOutcome, int]:
    """Update the disclosure modal while preserving its current selection."""
    if not isinstance(event, tcod.event.KeyDown):
        if isinstance(event, tcod.event.Quit):
            return (OrbitSceneOutcome.QUIT, selected)
        return (OrbitSceneOutcome.IGNORE, selected)
    _sym = event.sym
    _name = getattr(_sym, "name", "").lower()
    if _sym in ui._UP_SYMS or _name == "k":
        return (OrbitSceneOutcome.IGNORE, (selected - 1) % len(_DISCLOSURE_OPTIONS))
    if _sym in ui._DOWN_SYMS or _name == "j":
        return (OrbitSceneOutcome.IGNORE, (selected + 1) % len(_DISCLOSURE_OPTIONS))
    if _sym in ui._ENTER_SYMS:
        return (OrbitSceneOutcome.CONFIRM, selected)
    if _sym in ui._ESCAPE_SYMS:
        # Leaving the archive untouched is the safe default. It is still
        # an explicit disclosure outcome so the scene cannot trap the
        # player or recur on every later Mars launch.
        return (OrbitSceneOutcome.CONFIRM, 1)
    return (OrbitSceneOutcome.IGNORE, selected)


def _faction_reading(ctx) -> str:
    """Return the chosen faction's first, deliberately incomplete reading."""
    return _FACTION_READINGS.get(
        ctx.main_quest_chain,
        "The recovered archive has no trusted interpreter yet; its layers resist a clean reading.",
    )


def _render_disclosure_options(console, *, option_y: int, selected: int) -> None:
    """Render the archive disclosure choices and their descriptions."""
    for _idx, (_key, _spec) in enumerate(_DISCLOSURE_OPTIONS):
        _is_selected = _idx == selected
        _marker = "> " if _is_selected else "  "
        console.print(
            x=2,
            y=option_y + _idx * 3,
            string=f"{_marker}{_spec.label}",
            fg=ui.COLOR_OPTION_HIGHLIGHT if _is_selected else ui.COLOR_OPTION,
        )
        _wrapped = ui.wrap_text(_spec.menu_description, 66)
        for _line_idx, _line in enumerate(_wrapped):
            console.print(
                x=6,
                y=option_y + _idx * 3 + 1 + _line_idx,
                string=_line,
                fg=ui.COLOR_VALUE_DIM,
            )


def _render_orbit_scene(console, *, selected: int, faction_reading: str) -> None:
    """Render the archive response and disclosure options."""
    console.clear()
    _content_y = ui.screen_header(console, SCREEN_WIDTH, "THE FIRST READING")
    _lines = (
        "MARS ORBIT - ARCHIVE CARRIER: ACTIVE",
        "OUTBOUND SIGNAL: NONE DETECTED",
        "INBOUND RESPONSE: UNRESOLVED",
        "",
        "The recovered archive has begun interacting with your communications array.",
        "Not a translation. Not a message. A response.",
        "",
        faction_reading,
        "One layer may be a route beyond the Luyten blockade. The others remain unread.",
    )
    for _offset, _line in enumerate(_lines):
        console.print(
            x=2,
            y=_content_y + _offset,
            string=_line,
            fg=ui.COLOR_OPTION_HIGHLIGHT if _offset in (5, 7) else ui.COLOR_DESCRIPTION,
        )
    _option_y = _content_y + len(_lines) + 2
    _render_disclosure_options(console, option_y=_option_y, selected=selected)
    console.print(
        x=2,
        y=SCREEN_HEIGHT - 3,
        string="UP/DOWN or j/k choose - ENTER confirm - ESC leave sealed",
        fg=ui.COLOR_INSTRUCTION,
    )


def _unlock_research_immediately(ctx) -> None:
    """Make the intact-archive delivery available without a wait."""
    ctx.main_quest_gate.pop("research_alpha", None)
    ctx.main_quest_pending_message = ""
    ctx.main_quest_pending_objective = ""
    ctx.main_quest_progress["research_alpha"] = STATUS_AVAILABLE


def _apply_disclosure(ctx, choice: OrbitDisclosure) -> None:
    """Persist disclosure and schedule the context-appropriate handoff."""
    ctx.main_quest_disclosure = choice.value
    ctx.post_prison_orbit_seen = True
    if choice is OrbitDisclosure.ARCHIVE_SEALED:
        _unlock_research_immediately(ctx)
    else:
        _schedule_next_step(ctx, "act1_prison", next_step_id="research_alpha")
    _disclosure = find_archive_disclosure(choice.value)
    ctx.log.add_colored(
        _disclosure.log_message,
        message_log.COLOR_IMPORTANT_EVENT,
    )
    ctx.log.add(_disclosure.followup_message)


def _orbit_scene_is_ready(ctx, *, from_mars_prison: bool = False) -> bool:
    """Return whether the one-time Mars-orbit scene should fire."""
    return (
        (from_mars_prison or ctx.current_city_id == "mars")
        and not getattr(ctx, "post_prison_orbit_seen", False)
        and ctx.main_quest_progress.get("act1_prison") == "completed"
    )


def _pygame_orbit_choice(ctx) -> str | None:
    """Run the archive disclosure in the shared Pygame window."""
    from ..pygame_story import choose

    options = tuple(
        (spec.label, disclosure.value)
        for disclosure, spec in _DISCLOSURE_OPTIONS
    )
    body = (
        "The recovered archive has begun interacting with your communications array.\n\n"
        f"{_faction_reading(ctx)}\n\n"
        "One layer may be a route beyond the Luyten blockade. The others remain unread."
    )
    return choose(
        ctx,
        title="THE FIRST READING",
        body=body,
        options=options,
        caption="spacehack - the first reading",
    )


def maybe_show_post_prison_orbit(
    ctx,
    *,
    from_mars_prison: bool = False,
) -> bool:
    """Show the first-reading disclosure scene after a confirmed departure."""
    if not _orbit_scene_is_ready(ctx, from_mars_prison=from_mars_prison):
        return False
    choice = _pygame_orbit_choice(ctx)
    while choice == "__GUIDE__":
        choice = _pygame_orbit_choice(ctx)
    if choice == "__QUIT__":
        return False
    if choice in {"__BACK__", "__DISMISS__"}:
        _apply_disclosure(ctx, OrbitDisclosure.ARCHIVE_SEALED)
    else:
        _apply_disclosure(ctx, OrbitDisclosure(choice))
    return True


__all__ = [
    "OrbitDisclosure",
    "OrbitSceneOutcome",
    "maybe_show_post_prison_orbit",
]
