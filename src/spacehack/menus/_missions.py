"""Mission offerings screen — render, update, and modal runner.

Extracted from the old ``menus.py`` during the package refactor.
"""

from __future__ import annotations
from enum import Enum, auto

import tcod.console
import tcod.event

from .. import ui
from .. import mission as mission_module
from .. import npc as npc_module
from ..game_context import GameContext
from ..engine import HUD_WIDTH, MSG_LOG_HEIGHT, SCREEN_HEIGHT, SCREEN_WIDTH, make_console
from ..data.classes import find_class
from ..input_helpers import _try_open_guide


class MissionOutcome(Enum):
    """What the player chose in an NPC's mission offering modal.

    ``ACCEPT`` carries the picked :class:`spacehack.mission.MissionSpec`
    back to the caller so :func:`_run_game` can slot it into the
    ``player_active_missions`` list.
    """
    IGNORE = auto()
    ACCEPT = auto()
    BACK = auto()


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


def _offerings_to_menu(npc: npc_module.NPC, offerings: tuple[mission_module.MissionSpec, ...]) -> tuple[str, tuple[tuple[str, str], ...], dict[str, str]]:
    """Build an :class:`spacehack.ui.MenuScreen` payload from an
    NPC-mission-list so we can reuse the shared menu primitives.

    ``available_options`` is ``(id, label)`` where label is
    ``"[Tag] {title} @ {system} ({reward}$)"`` so the player sees
    the mission type tag, destination system, and reward in the
    listing.
    ``descriptions`` is the mission body blurb.
    """
    available_options = tuple(((str(i), _mission_board_label(m)) for i, m in enumerate(offerings)))
    descriptions = {str(i): m.description for i, m in enumerate(offerings)}
    return (f'{npc.name} - available work', available_options, descriptions)


def render_mission_offerings(console: tcod.console.Console, ctx: GameContext, npc: npc_module.NPC, offerings: tuple[mission_module.MissionSpec, ...], selected: int, *, screen_width: int, screen_height: int) -> None:
    """Paint the NPC's available missions as a character-screen style
    menu — centered title, left-anchored list at a fixed column.

    ``selected`` is the index of the highlighted option (clamped
    by caller-supplied modulo wrap, so any int is safe). The list
    of missions themselves lives in :mod:`spacehack.mission`.
    """
    console.clear()
    title, options, descriptions = _offerings_to_menu(npc, offerings)
    n = len(options)
    content_x, max_w = ui.content_metrics(screen_width, HUD_WIDTH)

    def fit(line: str) -> str:
        return line if len(line) <= max_w else line[:max_w - 1] + '…'

    def paint_title(row: int, text: str, *, fg: tuple[int, int, int]) -> None:
        console.print(x=ui.centered_x(text, screen_width), y=row, string=text, fg=fg)

    def paint(row: int, text: str, *, fg: tuple[int, int, int]) -> None:
        console.print(x=content_x, y=row, string=text, fg=fg)
    center_y = (screen_height - MSG_LOG_HEIGHT) // 2
    paint_title(center_y - 6, fit(title), fg=ui.COLOR_TITLE)
    sel = selected % n if n else 0
    list_top = center_y - 4
    for i, (_, label) in enumerate(options):
        row = list_top + i * 2
        is_selected = i == sel
        marker = '> ' if is_selected else '  '
        end_marker = ' <' if is_selected else '  '
        text = f'{marker}{fit(label)}{end_marker}'
        console.print(x=content_x, y=row, string=text, fg=ui.COLOR_OPTION_HIGHLIGHT if is_selected else ui.COLOR_OPTION)
    desc = descriptions.get(str(sel), '') if descriptions else ''
    desc_rows = ui.wrap_text(desc, max_w)
    desc_start_row = list_top + n * 2 + 1
    for j, line in enumerate(desc_rows):
        paint(desc_start_row + j, line, fg=ui.COLOR_DESCRIPTION)
    hint_lines: list[str] = ['ARROW KEYS / j,k navigate - ENTER accept - ESC walk away.']
    if offerings:
        picked = offerings[sel]
        hint_lines.append(f'Reward: {picked.reward_credits}$ + {picked.reward_xp}xp')
        if picked.recommended_class_id:
            klass = find_class(picked.recommended_class_id)
            hint_lines.append(f'Best suited for: {klass.name}')
        if picked.recommended_ship_min_cargo > 0:
            hint_lines.append(f'Ship cargo recommended: {picked.recommended_ship_min_cargo}+')
    for i, line in enumerate(hint_lines):
        paint(desc_start_row + max(len(desc_rows), 1) + 1 + i, fit(line), fg=ui.COLOR_INSTRUCTION)


def update_mission_offerings(event: tcod.event.Event) -> MissionOutcome:
    """Map a single event for the offerings modal.

    Pure dispatcher: UP/DOWN navigation is handled by the caller
    (it owns the ``selected`` int via :func:`_mission_navigate`,
    which mirrors :func:`_ship_menu_navigate` so the smoke test
    can verify both share the same input idiom). Enter -> ACCEPT,
    ESC -> BACK, anything else -> IGNORE.
    """
    if isinstance(event, tcod.event.Quit):
        return MissionOutcome.BACK
    if not isinstance(event, tcod.event.KeyDown):
        return MissionOutcome.IGNORE
    sym = event.sym
    if sym in ui._ESCAPE_SYMS:
        return MissionOutcome.BACK
    if sym in ui._ENTER_SYMS:
        return MissionOutcome.ACCEPT
    return MissionOutcome.IGNORE


def _mission_navigate(event: tcod.event.Event, selected: int, n: int) -> int | None:
    """If ``event`` drives offerings-menu nav, return the new
    ``selected`` index (modulo ``n`` options). Returns ``None``
    for non-nav events so the caller routes through
    :func:`update_mission_offerings`. Mirrors
    :func:`_ship_menu_navigate` so the keyboard idioms stay
    consistent across modals.
    """
    if n <= 0:
        return None
    if not isinstance(event, tcod.event.KeyDown):
        return None
    sym = event.sym
    sym_name: str = getattr(sym, 'name', '').lower()
    if sym in ui._UP_SYMS or sym_name == 'k':
        return (selected - 1) % n
    if sym in ui._DOWN_SYMS or sym_name == 'j':
        return (selected + 1) % n
    return None


def _run_mission_offerings(ctx, npc: npc_module.NPC, offerings: tuple[mission_module.MissionSpec, ...]) -> tuple[MissionOutcome, mission_module.MissionSpec | None]:
    """Show the NPC's offerings modal and return the choice.

    Returns ``(MissionOutcome, picked_mission)``: ``picked`` is
    ``None`` whenever the outcome is not ACCEPT. The caller
    (:func:`_run_game`) is responsible for swapping
    ``player_active_missions`` once it sees an ACCEPT.
    """
    console = make_console()
    selected = 0

    def _render() -> None:
        render_mission_offerings(console, ctx, npc, offerings, selected, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)

    def _update(event) -> MissionOutcome:
        nonlocal selected
        if _try_open_guide(event, ctx):
            return MissionOutcome.IGNORE
        new = _mission_navigate(event, selected, len(offerings))
        if new is not None:
            selected = new
            return MissionOutcome.IGNORE
        return update_mission_offerings(event)
    outcome = ui.Modal(ctx.context, console).run(_render, _update)
    if outcome is MissionOutcome.ACCEPT:
        return (outcome, offerings[selected % len(offerings)])
    return (outcome, None)
