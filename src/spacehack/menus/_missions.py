"""Mission offerings screen — render, update, and modal runner.

Extracted from the old ``menus.py`` during the package refactor.
"""

from __future__ import annotations
from enum import Enum, auto

from .. import mission as mission_module
from .. import npc as npc_module

class MissionOutcome(Enum):
    """What the player chose in an NPC's mission offering modal.

    ``ACCEPT`` carries the picked :class:`spacehack.mission.MissionSpec`
    back to the caller so :func:`_run_game` can slot it into the
    ``player_active_missions`` list.
    """
    IGNORE = auto()
    ACCEPT = auto()
    BACK = auto()
    QUIT = auto()

def _mission_type_tag(m: mission_module.MissionSpec) -> str:
    """Return a short category tag for a mission based on its fields.

    Priority: Salvage > Heist > Smuggle > Bounty > Delivery.
    """
    if m.salvage_wreck_enemy_id:
        return "Salvage"
    if m.heist_target_good_id:
        return "Heist"
    if m.is_smuggle:
        return "Smuggle"
    if m.target_enemy_id:
        return "Bounty"
    return "Delivery"

def _mission_board_label(m: mission_module.MissionSpec) -> str:
    """One board row: ``[Tag] {title} ({reward}$)``.

    Appends the destination solar system (``@{system}``) unless the
    title already names it — e.g. "Deliver to Mars in Sol" carries
    the system, while "Wanted: Crimson Jack" gets "@ Sirius".
    """
    _tag = _mission_type_tag(m)
    _sys = mission_module.destination_system_name(m)
    _suffix = f" @ {_sys}" if _sys and _sys.lower() not in m.title.lower() else ""
    return f'[{_tag}] {m.title}{_suffix} ({m.reward_credits}$)'

def _run_pygame_menu(
    ctx,
    frames: tuple,
    *,
    caption: str,
) -> tuple[str, str, int]:
    """Run a selectable menu in the mandatory shared Pygame window."""
    from .. import pygame_menu, pygame_runtime

    if not pygame_runtime.is_shared_context(ctx.context):
        raise pygame_menu.PygameMenuUnavailable(
            "Shared Pygame runtime is not open"
        )
    return pygame_menu.run_shared(ctx.context, frames, caption=caption)

def _run_pygame_interactive_missions(
    ctx,
    npc: npc_module.NPC,
    offerings: tuple[mission_module.MissionSpec, ...],
) -> tuple[MissionOutcome, mission_module.MissionSpec | None] | None:
    """Run mission offerings through the generic selectable worker."""
    from .. import pygame_menu, pygame_ui

    items = tuple(
        pygame_menu.MenuItem(_mission_board_label(mission), mission.description, str(index))
        for index, mission in enumerate(offerings)
    )
    frames = tuple(
        pygame_menu.MenuFrame(
            title=f"{npc.name} - available work",
            body=(
                "Select a contract to review its details."
                if offerings else "No work is available right now."
            ),
            items=items,
            hints=(pygame_ui.modal_hint(
                pygame_ui.NAV_HINT, "ENTER accept", "ESC walk away",
                pygame_ui.GUIDE_HINT,
            ),),
            selected=index,
        )
        for index in range(max(1, len(offerings)))
    )
    outcome, action, selected = _run_pygame_menu(
        ctx,
        frames,
        caption="spacehack - available work",
    )
    if outcome == "GUIDE":
        from ..help import _open_context_guide
        _open_context_guide(ctx, "Missions")
        return MissionOutcome.BACK, None
    if outcome == "QUIT":
        return MissionOutcome.QUIT, None
    if outcome == "TAB":
        return MissionOutcome.BACK, None
    if outcome == "SELECT" and offerings:
        try:
            picked = offerings[int(action)]
        except (ValueError, IndexError):
            return None
        return MissionOutcome.ACCEPT, picked
    return MissionOutcome.BACK, None

def _run_mission_offerings(
    ctx,
    npc: npc_module.NPC,
    offerings: tuple[mission_module.MissionSpec, ...],
) -> tuple[MissionOutcome, mission_module.MissionSpec | None]:
    """Show the NPC's offerings modal and return the choice.

    Returns ``(MissionOutcome, picked_mission)``: ``picked`` is
    ``None`` whenever the outcome is not ACCEPT. The caller
    (:func:`_run_game`) is responsible for swapping
    ``player_active_missions`` once it sees an ACCEPT.
    """
    result = _run_pygame_interactive_missions(ctx, npc, offerings)
    if result is None:
        raise RuntimeError("Mission offerings returned no outcome")
    return result
