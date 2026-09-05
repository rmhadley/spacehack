"""Main quest Act 1: the post-escape disposition choice (doc 38).

The one-time Mars-orbit scene after the prison escape presents the
epilogue branch: return to the faction that helped you and share the
archive for your reward, or keep everything and go solo. The choice
sets the persistent disposition and unlocks the delivered branch's
chain-keyed reward step; the kept branch carries no step — Act 1
finds its own way past the Line.
"""

from __future__ import annotations

from .. import message_log
from ..text import get as t_get
from ._core import STATUS_AVAILABLE

DISPOSITION_DELIVERED = "delivered"
DISPOSITION_KEPT = "kept"


def _faction_reading(ctx) -> str:
    """Return the chosen faction's first, deliberately incomplete reading."""
    return t_get(
        f"runtime.orbit_faction_{ctx.main_quest_chain}",
        default=t_get("runtime.orbit_faction_unknown"),
    )


def _orbit_scene_is_ready(ctx, *, from_mars_prison: bool = False) -> bool:
    """Return whether the one-time Mars-orbit scene should fire."""
    return (
        (from_mars_prison or ctx.current_city_id == "mars")
        and not getattr(ctx, "post_prison_orbit_seen", False)
        and ctx.main_quest_progress.get("act1_prison") == "completed"
        and getattr(ctx, "main_quest_disposition", "") == ""
    )


def _pygame_disposition_choice(ctx) -> str | None:
    """Run the deliver-or-keep choice in the shared Pygame window."""
    from ..pygame_story import choose

    body = (
        f"{t_get('runtime.orbit_body_intro')}\n\n"
        f"{_faction_reading(ctx)}\n\n"
        f"{t_get('runtime.orbit_body_route')}"
    )
    return choose(
        ctx,
        title=t_get("runtime.orbit_title"),
        body=body,
        options=(
            (t_get("runtime.epilogue_option_deliver"), DISPOSITION_DELIVERED),
            (t_get("runtime.epilogue_option_keep"), DISPOSITION_KEPT),
        ),
        caption="spacehack - the archive is yours",
    )


def _apply_disposition(ctx, disposition: str) -> None:
    """Persist the disposition and unlock its branch.

    Delivered: the chain's epilogue reward step becomes available
    (return to the faction, share the archive, collect). Kept: no
    step — the data stays yours alone, and the summon teases the
    road ahead past the Line.
    """
    ctx.main_quest_disposition = disposition
    ctx.post_prison_orbit_seen = True
    if disposition == DISPOSITION_DELIVERED:
        ctx.main_quest_progress[
            f"epilogue_reward_{ctx.main_quest_chain}"
        ] = STATUS_AVAILABLE
        ctx.log.add_colored(
            t_get("runtime.epilogue_delivered_log"),
            message_log.COLOR_IMPORTANT_EVENT,
        )
    else:
        ctx.main_quest_pending_message = t_get("runtime.epilogue_kept_title")
        ctx.main_quest_pending_objective = t_get("runtime.epilogue_kept_body")
        ctx.log.add_colored(
            t_get("runtime.epilogue_kept_log"),
            message_log.COLOR_IMPORTANT_EVENT,
        )


def maybe_show_post_prison_orbit(
    ctx,
    *,
    from_mars_prison: bool = False,
) -> bool:
    """Show the deliver-or-keep scene after a confirmed departure."""
    if not _orbit_scene_is_ready(ctx, from_mars_prison=from_mars_prison):
        return False
    choice = _pygame_disposition_choice(ctx)
    while choice == "__GUIDE__":
        choice = _pygame_disposition_choice(ctx)
    if choice == "__QUIT__":
        return False
    if choice in {"__BACK__", "__DISMISS__"}:
        # No declining the decision — the default keeps the archive
        # (the player can always fly back and deliver later).
        choice = DISPOSITION_KEPT
    _apply_disposition(ctx, choice)
    return True


__all__ = [
    "DISPOSITION_DELIVERED",
    "DISPOSITION_KEPT",
    "maybe_show_post_prison_orbit",
]
