"""Main quest Act 1: the first post-prison orbit scene."""

from __future__ import annotations

from enum import Enum

from .. import message_log
from ..text import get as t_get
from ..data.main_quest.act1_post_prison import (
    ARCHIVE_DISCLOSURES,
    find_archive_disclosure,
)
from ._core import STATUS_AVAILABLE, _schedule_next_step

class OrbitDisclosure(Enum):
    """The player's first decision about sharing the recovered archive."""

    DIAGNOSTIC_FRAGMENT = "diagnostic_fragment"
    ARCHIVE_SEALED = "archive_sealed"
    SAFE_DESTINATION = "safe_destination"

_DISCLOSURE_OPTIONS = tuple(
    (OrbitDisclosure(spec.key), spec)
    for spec in ARCHIVE_DISCLOSURES
)

def _faction_reading(ctx) -> str:
    """Return the chosen faction's first, deliberately incomplete reading."""
    return t_get(
        f"runtime.orbit_faction_{ctx.main_quest_chain}",
        default=t_get("runtime.orbit_faction_unknown"),
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
        f"{t_get('runtime.orbit_body_intro')}\n\n"
        f"{_faction_reading(ctx)}\n\n"
        f"{t_get('runtime.orbit_body_route')}"
    )
    return choose(
        ctx,
        title=t_get("runtime.orbit_title"),
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
    "maybe_show_post_prison_orbit",
]
