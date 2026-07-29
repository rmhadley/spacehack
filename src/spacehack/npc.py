"""NPC runtime layer: dialog helpers and data facade.

NPCs live in two layers:

  * :mod:`spacehack.data.npcs` — the static catalog (the :class:`NPC`
    dataclass + per-guild tuples + :func:`find_npc` / :func:`list_npcs`
    lookup helpers). Adding a new NPC is a one-file edit there.
  * Here — the runtime dialog helpers (render/update/run NPC talk)
    that were extracted from :mod:`spacehack.__main__`, plus the
    :class:`TalkOutcome` enum they depend on, plus re-exports of
    the data-layer symbols so consumers (e.g. ``spacehack.__main__``)
    can keep using ``npc_module.NPC`` / ``npc_module.find_npc``
    without a second import line.

Mirrors the pattern established by :mod:`spacehack.mission`, which
re-exports its data module's symbols and defines its own runtime
functions identically.
"""
from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

import tcod.console
import tcod.event

from . import message_log
from . import ui
from .data.npcs import NPC, find_npc, list_npcs
from .engine import HUD_WIDTH, MSG_LOG_HEIGHT, SCREEN_WIDTH, SCREEN_HEIGHT, make_console
from .game_context import GameContext
from .input_helpers import _try_open_guide

if TYPE_CHECKING:
    from .mission import Mission


class TalkOutcome(Enum):
    """What happened during a single NPC-talk dialog iteration.

    ESC walks away (BACK); Enter opens the NPC's mission offerings
    (WORK); when the player has an active delivery mission that
    this NPC can fulfil (:data:`Mission.required_cargo_size` > 0
    and giver matches), Enter drives :attr:`DELIVER` instead and
    the dialog paints an extra ``> Deliver <title> <`` row. Quit
    closes the window; anything else is IGNORE. Mirrors
    :class:`spacehack.__main__.ShipBuyOutcome` so a future
    iteration can grow the dialog with more branches (e.g.
    ``WORK`` -> goods for sale, ``REST``) without churning the
    call site.
    """
    IGNORE = auto()
    BACK = auto()
    WORK = auto()
    DELIVER = auto()
    QUIT = auto()


def render_npc_talk(
    console: tcod.console.Console,
    ctx: GameContext,
    npc: NPC,
    *,
    screen_width: int,
    screen_height: int,
    deliver_missions: list | None = None,
    selected: int = 0,
) -> None:
    """Paint the centered NPC-talk dialog into ``console``.

    The menu shows one "Deliver: <title>" row per deliverable
    mission, then "View available work" at the bottom. When no
    missions are deliverable, only "View available work" appears.
    """
    console.clear()
    title = f"{npc.name} ({npc.guild})"
    body = f'"{npc.flavor_text}"'
    max_w = screen_width - HUD_WIDTH - 2

    def fit(line: str) -> str:
        return line if len(line) <= max_w else line[:max_w - 1] + "…"

    def paint(row: int, text: str, *, fg: tuple[int, int, int]) -> None:
        console.print(x=ui.centered_x(text, screen_width), y=row, string=text, fg=fg)

    center_y = (screen_height - MSG_LOG_HEIGHT) // 2
    paint(center_y - 2, fit(title), fg=ui.COLOR_TITLE)
    paint(center_y + 1, fit(body), fg=ui.COLOR_DESCRIPTION)

    _missions = deliver_missions or []
    options: list[tuple[str, bool]] = []
    for m in _missions:
        options.append(("Deliver: " + m.title, True))
    options.append(("View available work", False))
    n = len(options)
    sel = selected % n
    list_top = center_y + 3
    for i, (label, is_deliver) in enumerate(options):
        row = list_top + i * 2
        is_selected = i == sel
        marker_open = "> " if is_selected else "  "
        marker_close = " <" if is_selected else "  "
        text = f"{marker_open}{fit(label)}{marker_close}"
        if is_selected:
            fg = ui.COLOR_OPTION_HIGHLIGHT2 if is_deliver else ui.COLOR_OPTION_HIGHLIGHT
        else:
            fg = ui.COLOR_OPTION
        console.print(x=ui.centered_x(text, screen_width), y=row, string=text, fg=fg)
    hint = "ARROW KEYS / j,k navigate - ENTER select - ESC walk away."
    hint_row = list_top + n * 2
    if hint_row + 1 <= screen_height - MSG_LOG_HEIGHT:
        paint(hint_row, fit(hint), fg=ui.COLOR_INSTRUCTION)
    message_log.render_message_log(console, ctx.log, screen_width=screen_width, screen_height=screen_height)


def update_npc_talk(event: tcod.event.Event) -> TalkOutcome:
    """Map a single event for the NPC-talk dialog.

    Returns a NAV-AGNOSTIC outcome: ESC -> BACK, Enter -> WORK,
    window-close -> QUIT, anything else -> IGNORE. UP/DOWN /
    j/k nav is handled by :func:`_npc_talk_navigate` (a sibling
    helper used by :func:`_run_npc_talk`) so this function's
    job is purely the dialog-level outcomes.

    Note that ``TalkOutcome.WORK`` is the Enter default here; the
    caller (:func:`_run_npc_talk`) re-maps WORK to
    :attr:`TalkOutcome.DELIVER` when the highlighted option
    happens to be the "Deliver <title>" row. Keeping Enter here
    as a generic "confirm" marker lets the caller own the index-
    to-outcome mapping without the dispatcher hardcoding which
    option is deliverable.
    """
    if isinstance(event, tcod.event.Quit):
        return TalkOutcome.QUIT
    if not isinstance(event, tcod.event.KeyDown):
        return TalkOutcome.IGNORE
    if event.sym in ui._ENTER_SYMS:
        return TalkOutcome.WORK
    if event.sym in ui._ESCAPE_SYMS:
        return TalkOutcome.BACK
    return TalkOutcome.IGNORE


def _npc_talk_navigate(event: tcod.event.Event, selected: int, n: int) -> int | None:
    """If ``event`` drives NPC-talk menu nav, return the new
    ``selected`` index (modulo ``n`` options); otherwise ``None``.

    Recognises both the standard arrow keys (UP / DOWN; also KP_8
    / KP_2 via :data:`ui._UP_SYMS` / :data:`ui._DOWN_SYMS`) and
    the vertical vim keys (``j`` down, ``k`` up). Mirrors
    :func:`spacehack.__main__._mission_navigate` and
    :func:`spacehack.__main__._ship_menu_navigate` so all three
    NPC-facing modals share the same nav idiom — one shape the
    smoke harness can regression-guard.
    """
    if n <= 0:
        return None
    if not isinstance(event, tcod.event.KeyDown):
        return None
    sym = event.sym
    sym_name: str = getattr(sym, "name", "").lower()
    if sym in ui._UP_SYMS or sym_name == "k":
        return (selected - 1) % n
    if sym in ui._DOWN_SYMS or sym_name == "j":
        return (selected + 1) % n
    return None


def _run_npc_talk(
    ctx: GameContext,
    npc: NPC,
    *,
    deliver_missions: list | None = None,
) -> tuple[TalkOutcome, Mission | None]:
    """Show the talk modal for ``npc`` and return the chosen outcome.

    Menu has one "Deliver: <title>" row per deliverable mission
    (highlighted gold), then "View available work" at the bottom.
    ENTER on a deliver row returns DELIVER with that mission;
    ENTER on the work row returns WORK.

    Returns ``(outcome, deliver_mission)``: the specific mission
    when DELIVER, ``None`` otherwise.
    """
    ctx.log.add(f"You chat briefly with {npc.name}.")
    console = make_console()
    selected = 0
    _missions = deliver_missions or []
    n_deliver = len(_missions)
    n_options = n_deliver + 1  # deliver rows + "View available work"

    def _render() -> None:
        render_npc_talk(
            console,
            ctx,
            npc,
            screen_width=SCREEN_WIDTH,
            screen_height=SCREEN_HEIGHT,
            deliver_missions=_missions,
            selected=selected,
        )

    def _update(event: tcod.event.Event) -> TalkOutcome:
        nonlocal selected
        if _try_open_guide(event, ctx):
            return TalkOutcome.IGNORE
        new = _npc_talk_navigate(event, selected, n_options)
        if new is not None:
            selected = new
            return TalkOutcome.IGNORE
        result = update_npc_talk(event)
        if result is TalkOutcome.IGNORE:
            return TalkOutcome.IGNORE
        if result is TalkOutcome.QUIT:
            return TalkOutcome.QUIT
        if result is TalkOutcome.BACK:
            return TalkOutcome.BACK
        if selected < n_deliver:
            return TalkOutcome.DELIVER
        return TalkOutcome.WORK

    outcome = ui.Modal(ctx.context, console).run(_render, _update)
    if outcome is TalkOutcome.DELIVER and 0 <= selected < n_deliver:
        return (outcome, _missions[selected])
    return (outcome, None)


# IDENTITY GUARANTEE: ``npc_module.NPC is NPC`` (and ditto for
# find_npc / list_npcs). Smoke-verified at the registry build site
# so a future refactor that accidentally drops the re-exports (or
# wraps the symbol in a proxy) breaks the identity check rather
# than silently changing consumer semantics.
__all__ = [
    "NPC",
    "TalkOutcome",
    "find_npc",
    "list_npcs",
    "render_npc_talk",
    "update_npc_talk",
    "_npc_talk_navigate",
    "_run_npc_talk",
]
