"""Main quest runtime: step lifecycle + quest-aware NPC dialogue.

Data (frozen :class:`~spacehack.data.main_quest.MainQuestStep` +
:class:`QuestDialogue` entries) lives in :mod:`spacehack.data.main_quest`.
This module owns the runtime:

* **Step lifecycle** — :func:`start_step` / :func:`complete_step`
  (with rewards + auto-advance to the next step).
* **Quest-aware NPC talk** — :func:`resolve_npc_dialogue` and
  :func:`quest_option_for` feed :func:`spacehack.npc.render_npc_talk`;
  :func:`trigger_dialogue` advances the step when the player picks the
  quest option.
* **Quest-log breadcrumb** — :func:`current_main_quest_objective` for
  the minimal "MAIN QUEST" section (Phase 4 builds the full UI).
* **Act 0 hooks** — :func:`maybe_trigger_signal`,
  :func:`prepare_mars_surface`, :func:`bump_mars_door`.

Design doc: ``docs/design/in_progress/07_DESIGN_MAIN_QUEST.md``.
"""

from __future__ import annotations

from collections import deque
from enum import Enum, auto

import tcod.event

from . import message_log
from . import ui
from . import world
from .engine import SCREEN_HEIGHT, SCREEN_WIDTH, make_console
from .data.main_quest import (
    MainQuestStep,
    QuestDialogue,
    find_main_quest_step,
    main_quest_step_after,
)

# Step statuses stored in ``ctx.main_quest_progress[step_id]``.
STATUS_AVAILABLE = "available"
STATUS_ACTIVE = "active"
STATUS_COMPLETED = "completed"

# The signal only fires on the first jump OUT of Sol (the game
# starts on Earth, so the first jump away from Sol IS the first
# departure — launching into Sol space alone doesn't trigger it).
_SIGNAL_SYSTEM_ID = "sol"


# ---------------------------------------------------------------------------
# Step lifecycle
# ---------------------------------------------------------------------------


def step_status(ctx, step_id: str) -> str:
    """Return the status of ``step_id`` (``\"\"`` if unknown)."""
    return ctx.main_quest_progress.get(step_id, "")


def start_step(ctx, step_id: str) -> bool:
    """Move an ``available`` step to ``active``. Returns True if started.

    Does NOT advance completed steps or re-start active ones. This is
    the "the player has begun this objective" transition; completing
    the objective uses :func:`complete_step`.
    """
    if step_status(ctx, step_id) != STATUS_AVAILABLE:
        return False
    ctx.main_quest_progress[step_id] = STATUS_ACTIVE
    return True


def complete_step(ctx, step_id: str) -> bool:
    """Complete a step: apply rewards, then auto-advance the next step.

    Works from ``available`` OR ``active`` (an available step can be
    completed directly when talking to the giver completes it — e.g.
    ``prologue_seek_help``). Applies ``rewards_credits`` /
    ``rewards_xp`` / ``rewards_rep`` / ``rewards_item``, then marks
    the first step that ``requires_step == step_id`` as ``available``.

    Returns True if the step was just completed.
    """
    _status = step_status(ctx, step_id)
    if _status not in (STATUS_AVAILABLE, STATUS_ACTIVE):
        return False
    _step = find_main_quest_step(step_id)
    ctx.main_quest_progress[step_id] = STATUS_COMPLETED
    ctx.log.add(f"[MAIN QUEST] {_step.title} — complete.")
    if _step.rewards_credits:
        ctx.stats.credits += _step.rewards_credits
        ctx.log.add(f"+{_step.rewards_credits}$ reward.")
    if _step.rewards_xp:
        from .xp import add_xp as _add_xp
        _add_xp(ctx, _step.rewards_xp)
    if _step.rewards_rep:
        from .faction import modify_rep as _modify_rep
        for _fac, _delta in _step.rewards_rep.items():
            _modify_rep(ctx, _fac, _delta)
    if _step.rewards_item:
        ctx.main_quest_unlocked_items.add(_step.rewards_item)
    # Auto-advance: the step that requires this one becomes available.
    _next = main_quest_step_after(step_id)
    if _next is not None and step_status(ctx, _next.id) == "":
        ctx.main_quest_progress[_next.id] = STATUS_AVAILABLE
    return True


# ---------------------------------------------------------------------------
# Quest-aware NPC dialogue
# ---------------------------------------------------------------------------


def _live_dialogue(ctx, npc_id: str) -> tuple[MainQuestStep, "QuestDialogue"] | None:
    """Return ``(step, dialogue)`` for the highest-priority live entry.

    Priority (per design doc): active > available > completed. Only
    entries whose variant text is non-empty for the current status
    count; completed steps only match if they define a ``complete``
    variant.
    """
    for _status in (STATUS_ACTIVE, STATUS_AVAILABLE, STATUS_COMPLETED):
        for _step_id, _st in ctx.main_quest_progress.items():
            if _st != _status:
                continue
            try:
                _step = find_main_quest_step(_step_id)
            except KeyError:
                continue
            _dialogue = _step.dialogues.get(npc_id)
            if _dialogue is None:
                continue
            if _status == STATUS_ACTIVE and _dialogue.active:
                return (_step, _dialogue)
            if _status == STATUS_AVAILABLE and _dialogue.intro:
                return (_step, _dialogue)
            if _status == STATUS_COMPLETED and _dialogue.complete:
                return (_step, _dialogue)
    return None


def resolve_npc_dialogue(ctx, npc_id: str) -> tuple[str, str | None]:
    """Return ``(dialogue_text, trigger_step_id or None)`` for this NPC.

    Scans quest progress for a live :class:`QuestDialogue` entry;
    falls back to the NPC's default ``flavor_text`` with no trigger.

    For a triggerable step (``trigger_on_talk`` + available/active), the
    body returned is the NPC's normal ``flavor_text`` — the offer detail
    lives in the help-offer modal (:func:`show_help_offer`) that the
    quest option row kicks off, so the talk modal stays short. For a
    completed step, the ``complete`` variant is shown as the body with
    no trigger.

    ``trigger_step_id`` is non-None when the live entry has
    ``trigger_on_talk`` — the NPC-talk modal should show its
    ``option_label`` row so the player can advance the step.
    """
    _live = _live_dialogue(ctx, npc_id)
    if _live is not None:
        _step, _dialogue = _live
        _status = ctx.main_quest_progress[_step.id]
        _trigger = (
            _step.id
            if _dialogue.trigger_on_talk and _status in (STATUS_AVAILABLE, STATUS_ACTIVE)
            else None
        )
        if _trigger is not None:
            # Triggerable: talk modal keeps the NPC's normal flavor;
            # the offer itself lives in the help-offer modal.
            from .data.npcs import find_npc as _find_npc
            return (_find_npc(npc_id).flavor_text, _trigger)
        _text = (
            _dialogue.active if _status == STATUS_ACTIVE
            else _dialogue.intro if _status == STATUS_AVAILABLE
            else _dialogue.complete
        )
        return (_text, None)
    from .data.npcs import find_npc as _find_npc
    return (_find_npc(npc_id).flavor_text, None)


def quest_option_for(ctx, npc_id: str) -> tuple[str, str] | None:
    """Return ``(option_label, step_id)`` when this NPC offers a live
    quest option row, else ``None``.

    A row appears when the NPC's live dialogue defines a non-empty
    ``option_label`` AND the step is in a triggerable state
    (available or active).
    """
    _live = _live_dialogue(ctx, npc_id)
    if _live is None:
        return None
    _step, _dialogue = _live
    if not _dialogue.option_label:
        return None
    if step_status(ctx, _step.id) == STATUS_COMPLETED:
        return None
    return (_dialogue.option_label, _step.id)


def trigger_dialogue(ctx, npc_id: str, step_id: str) -> bool:
    """Advance ``step_id`` from an NPC-talk quest option selection.

    Applies the dialogue entry's ``backing_faction`` (claim planted)
    and ``unlock_item`` (tool / data unlocked), then completes the
    step. Returns True if the step was advanced.
    """
    _step = find_main_quest_step(step_id)
    _dialogue = _step.dialogues.get(npc_id)
    if _dialogue is None:
        return False
    if _dialogue.backing_faction:
        ctx.main_quest_backing.add(_dialogue.backing_faction)
    if _dialogue.unlock_item:
        ctx.main_quest_unlocked_items.add(_dialogue.unlock_item)
    return complete_step(ctx, step_id)


# ---------------------------------------------------------------------------
# Quest-log breadcrumb (minimal — Phase 4 builds the full UI)
# ---------------------------------------------------------------------------


def current_main_quest_objective(ctx) -> tuple[str, str] | None:
    """Return ``(title, description)`` of the current breadcrumb step.

    The first step in ``main_quest_progress`` that is available or
    active. Returns ``None`` when no main quest is in progress.
    """
    for _step_id, _status in ctx.main_quest_progress.items():
        if _status not in (STATUS_AVAILABLE, STATUS_ACTIVE):
            continue
        try:
            _step = find_main_quest_step(_step_id)
        except KeyError:
            continue
        return (_step.title, _step.description)
    return None


# ---------------------------------------------------------------------------
# Act 0 hooks: signal trigger, Mars gate, sealed door
# ---------------------------------------------------------------------------


def maybe_trigger_signal(ctx, system_id: str) -> bool:
    """Fire the prologue signal on the first jump out of Sol.

    Called from :func:`spacehack.navigation._jump_to_system` with the
    OUTGOING system id, right after the player emerges in the
    destination system. Only fires once: completes ``prologue_signal``
    (via :func:`complete_step`, which auto-advances
    ``prologue_mars_unlocked`` to available — the Mars exploration
    gate). Returns True if the signal just fired.
    """
    if system_id != _SIGNAL_SYSTEM_ID:
        return False
    if step_status(ctx, "prologue_signal") in (STATUS_ACTIVE, STATUS_COMPLETED):
        return False
    ctx.main_quest_progress["prologue_signal"] = STATUS_AVAILABLE
    # Describe the transmission first, then mark the step complete so
    # the player reads the event before the quest-log marker.
    ctx.log.add_colored(
        "STATIC... a garbled transmission cuts through the noise.",
        message_log.COLOR_IMPORTANT_EVENT,
    )
    ctx.log.add(
        "A burst of coordinates — then silence. They resolve to somewhere on Mars."
    )
    complete_step(ctx, "prologue_signal")
    return True


# ---------------------------------------------------------------------------
# Full-screen quest overlays (the ui.Modal interruption pattern)
#
# Both the incoming transmission and the sealed Mars door surface as a
# centered full-screen modal — the same interruption pattern as militia
# auto-hails. Shared plumbing (outcome enum, dismiss handler, box +
# centered-print helpers) lives here; each overlay picks its own content.
# All characters are CP437-safe (dots, dashes, #, =, + only — no Unicode
# block chars that can garble on the tilesheet fallback).
# ---------------------------------------------------------------------------

class _ModalOutcome(Enum):
    """Outcome for a full-screen quest overlay modal."""
    IGNORE = auto()
    CLOSE = auto()
    QUIT = auto()


def _overlay_box(
    console,
    *,
    screen_width: int,
    screen_height: int,
    box_w: int,
    box_h: int,
) -> int:
    """Clear the console, draw a centered bordered box, return ``y0``.

    Callers render every line via :func:`_centered_print`, which
    centers on the full screen width, so ``x0`` is never needed.
    """
    console.clear()
    y0 = max(0, (screen_height - box_h) // 2 - 2)
    ui.paint_rect_border(
        console,
        (max(0, (screen_width - box_w) // 2), y0, box_w, box_h),
        fg=ui.COLOR_VALUE_DIM,
    )
    return y0


def _centered_print(console, *, screen_width: int, y: int, text: str, fg) -> None:
    """Print ``text`` centered on row ``y`` with foreground ``fg``."""
    console.print(
        x=ui.centered_x(text, screen_width),
        y=y,
        string=text,
        fg=fg,
    )


def _modal_dismiss_update(event: tcod.event.Event) -> _ModalOutcome:
    """Map a single event for any quest overlay.

    ENTER / ESC closes (:attr:`CLOSE`), window-close quits
    (:attr:`QUIT`), everything else is :attr:`IGNORE`.
    """
    if isinstance(event, tcod.event.Quit):
        return _ModalOutcome.QUIT
    if not isinstance(event, tcod.event.KeyDown):
        return _ModalOutcome.IGNORE
    if event.sym in ui._ENTER_SYMS or event.sym in ui._ESCAPE_SYMS:
        return _ModalOutcome.CLOSE
    return _ModalOutcome.IGNORE


# Garbled signal noise — CP437-safe (dots + dashes only).
_SIGNAL_STATIC: tuple[str, ...] = (
    "...--.-.-..--...-..-.-.--.....-.-..--.-..",
    "-.--..-.-..--.-..-...--..-.-..--...--...-",
    "..-.-.--.....-.-..--.-..--...--.-..---.-.",
)

# Dim green — reads as a weak signal trace, distinct from the
# palette's bright player-action green.
_SIGNAL_TRACE_FG: tuple[int, int, int] = (90, 150, 90)


def render_incoming_transmission(
    console,
    *,
    screen_width: int,
    screen_height: int,
) -> None:
    """Paint the garbled-signal overlay: a centered box with the
    transmission title, unknown-source metadata, signal static, and
    the coordinate reveal.

    Idempotent (clears first). All characters are CP437-safe.
    """
    _y0 = _overlay_box(
        console,
        screen_width=screen_width,
        screen_height=screen_height,
        box_w=64,
        box_h=18,
    )
    _centered_print(
        console, screen_width=screen_width, y=_y0 + 1,
        text="INCOMING TRANSMISSION", fg=ui.COLOR_TITLE,
    )
    _centered_print(
        console, screen_width=screen_width, y=_y0 + 3,
        text="FREQUENCY: UNKNOWN    SOURCE: UNKNOWN    ENCRYPTION: NONE",
        fg=ui.COLOR_VALUE_DIM,
    )
    for _i, _line in enumerate(_SIGNAL_STATIC):
        _centered_print(
            console, screen_width=screen_width, y=_y0 + 5 + _i,
            text=_line, fg=_SIGNAL_TRACE_FG,
        )
    _centered_print(
        console, screen_width=screen_width, y=_y0 + 9,
        text="A burst of coordinates cuts through the static -",
        fg=ui.COLOR_DESCRIPTION,
    )
    _centered_print(
        console, screen_width=screen_width, y=_y0 + 10,
        text="then silence.", fg=ui.COLOR_DESCRIPTION,
    )
    _centered_print(
        console, screen_width=screen_width, y=_y0 + 12,
        text="They resolve to somewhere on Mars.", fg=ui.COLOR_OPTION_HIGHLIGHT,
    )
    _centered_print(
        console, screen_width=screen_width, y=_y0 + 14,
        text="Press ENTER to acknowledge", fg=ui.COLOR_INSTRUCTION,
    )


def show_prologue_transmission(ctx) -> None:
    """Show the garbled prologue signal as an incoming-comms overlay.

    Called from :func:`spacehack.navigation._jump_to_system` right
    after :func:`maybe_trigger_signal` fires, so the signal arrives
    as a full-screen transmission readout as the player emerges in
    the destination system — not just log lines. Blocks until the
    player acknowledges (ENTER / ESC).
    """
    console = make_console()

    def _render() -> None:
        render_incoming_transmission(
            console,
            screen_width=SCREEN_WIDTH,
            screen_height=SCREEN_HEIGHT,
        )

    def _update(event) -> _ModalOutcome:
        return _modal_dismiss_update(event)

    ui.Modal(ctx.context, console).run(_render, _update)


# ---------------------------------------------------------------------------
# Sealed-door overlay (the door bump surfaces as a full-screen modal)
# ---------------------------------------------------------------------------

# Alien rune noise — the door's answer to the signal static: carved
# glyphs of # / = / + (CP437-safe). All rows are 30 wide.
_DOOR_RUNES: tuple[str, ...] = (
    "##=+==#=+==#=+==#=+==##=+==#=+",
    "=+==#=+==#=+==#=+==#=+==#=+==#",
    "+==#=+==#=+==#=+==#=+==#=+==#=",
)

# Alien violet — matches the door entity's fg on the Mars surface.
_DOOR_RUNE_FG: tuple[int, int, int] = (150, 95, 255)
_DOOR_ART_FG: tuple[int, int, int] = (140, 80, 255)

# ASCII door art for the two beats (equal-width rows, CP437-safe).
# Every row is 32 wide: two-space margin, pipe/equal frame, 26-char
# interior. The middle block is the door itself; #-marks are rune
# carvings, === is the seal seam (open beat shows the broken seam
# with a dark gap of dots).
_DOOR_ART_SEALED: tuple[str, ...] = (
    "  .==========================.  ",
    "  |  #    #   #   #   #   #  |  ",
    "  |   #   #   #   #   #   #  |  ",
    "  |  #    #   #   #   #   #  |  ",
    "  |   #   #   #   #   #   #  |  ",
    "  |                          |  ",
    "  |      ==============      |  ",
    "  |      |            |      |  ",
    "  |      |     ===    |      |  ",
    "  |      |            |      |  ",
    "  |      ==============      |  ",
    "  |                          |  ",
    "  '=========================='  ",
)

_DOOR_ART_OPEN: tuple[str, ...] = (
    "  .==========================.  ",
    "  |  #    #   #   #   #   #  |  ",
    "  |   #   #   #   #   #   #  |  ",
    "  |  #    #   #   #   #   #  |  ",
    "  |   #   #   #   #   #   #  |  ",
    "  |                          |  ",
    "  |      ==============      |  ",
    "  |      |    ...     |      |  ",
    "  |      |   .....    |      |  ",
    "  |      |    ...     |      |  ",
    "  |      ==============      |  ",
    "  |                          |  ",
    "  '=========================='  ",
)

# Table-driven content per beat (state-table guardrail: no chained
# if/elif over the two beats — a dict lookup instead).
_DOOR_OVERLAYS: dict[str, dict[str, object]] = {
    "discover": {
        "title": "SEALED ENTRANCE",
        "meta": "MAKE: ALIEN    MECHANISM: NONE VISIBLE    AGE: UNKNOWN",
        "art": _DOOR_ART_SEALED,
        "body": (
            "A door of alien make, set into the red dust.",
            "No visible mechanism - older than the colony.",
        ),
        "highlight": "It will not open with any human tool.",
        "instruction": "Press ENTER to acknowledge",
    },
    "open": {
        "title": "THE SEAL GIVES WAY",
        "meta": "SEAL: BROKEN    CHAMBER: EMPTY    DATA: RECOVERED",
        "art": _DOOR_ART_OPEN,
        "body": (
            "The seal gives way - cleanly, as if it were waiting.",
            "Inside: an empty cell of alien make -",
            "and a cache of data beyond any human technology.",
        ),
        "highlight": "The prison data is recovered. Someone will want to study this.",
        "instruction": "Press ENTER to continue",
    },
}


def render_sealed_door_overlay(
    console,
    *,
    screen_width: int,
    screen_height: int,
    beat: str,
) -> None:
    """Paint the sealed-door overlay for a quest beat.

    ``beat`` selects the content table: ``"discover"`` (first bump —
    the door refuses to open) or ``"open"`` (the seal gives way and
    the empty prison is revealed). Mirrors the transmission overlay:
    title, metadata, alien rune static, ASCII door art, description,
    highlight, and a dismiss hint.
    """
    _content = _DOOR_OVERLAYS[beat]
    _art = _content["art"]
    _body = _content["body"]
    _box_h = 15 + len(_art) + len(_body)
    _y0 = _overlay_box(
        console,
        screen_width=screen_width,
        screen_height=screen_height,
        box_w=66,
        box_h=_box_h,
    )
    _centered_print(
        console, screen_width=screen_width, y=_y0 + 1,
        text=_content["title"], fg=ui.COLOR_TITLE,
    )
    _centered_print(
        console, screen_width=screen_width, y=_y0 + 3,
        text=_content["meta"], fg=ui.COLOR_VALUE_DIM,
    )
    for _i, _line in enumerate(_DOOR_RUNES):
        _centered_print(
            console, screen_width=screen_width, y=_y0 + 5 + _i,
            text=_line, fg=_DOOR_RUNE_FG,
        )
    _art_y = _y0 + 9
    for _i, _line in enumerate(_art):
        _centered_print(
            console, screen_width=screen_width, y=_art_y + _i,
            text=_line, fg=_DOOR_ART_FG,
        )
    _body_y = _art_y + len(_art) + 1
    for _i, _line in enumerate(_body):
        _centered_print(
            console, screen_width=screen_width, y=_body_y + _i,
            text=_line, fg=ui.COLOR_DESCRIPTION,
        )
    _centered_print(
        console, screen_width=screen_width,
        y=_body_y + len(_body) + 1,
        text=_content["highlight"], fg=ui.COLOR_OPTION_HIGHLIGHT,
    )
    _centered_print(
        console, screen_width=screen_width,
        y=_body_y + len(_body) + 3,
        text=_content["instruction"], fg=ui.COLOR_INSTRUCTION,
    )


def show_sealed_door_overlay(ctx, beat: str) -> None:
    """Show the sealed-door overlay as a full-screen modal.

    Called from :func:`bump_mars_door` on the two quest-beat bumps
    (first contact + opening with a faction tool). Blocks until the
    player dismisses (ENTER / ESC).
    """
    console = make_console()

    def _render() -> None:
        render_sealed_door_overlay(
            console,
            screen_width=SCREEN_WIDTH,
            screen_height=SCREEN_HEIGHT,
            beat=beat,
        )

    def _update(event) -> _ModalOutcome:
        return _modal_dismiss_update(event)

    ui.Modal(ctx.context, console).run(_render, _update)


# ---------------------------------------------------------------------------
# Faction help-offer modal (the seek-help fork surfaces here)
# ---------------------------------------------------------------------------

class OfferOutcome(Enum):
    """Outcome for the faction help-offer modal."""
    IGNORE = auto()
    ACCEPT = auto()
    DECLINE = auto()
    QUIT = auto()


# Offer body wraps at 62 chars so even the longest lead (the militia's
# "There is no door..." ~200 chars) fits in ~4 lines inside the box.
_OFFER_BODY_WIDTH = 62


def render_help_offer(
    console,
    *,
    screen_width: int,
    screen_height: int,
    npc_name: str,
    offer_text: str,
    selected: int,
) -> None:
    """Paint the faction help-offer overlay: who's speaking, the
    detailed offer message (word-wrapped), and Accept help / Keep
    looking options.

    ``npc_name`` heads the meta line; ``offer_text`` is the dialogue's
    ``intro``/``active`` variant (full, wrapped — never truncated).
    ``selected`` is 0 = Accept help, 1 = Keep looking. Reuses the
    shared overlay plumbing from the transmission/door overlays.
    """
    _title = "AN OFFER OF HELP"
    _lines = ui.wrap_text(offer_text, _OFFER_BODY_WIDTH)
    # Title + meta + wrap-gap + body + options + hint, with margins.
    _box_h = 14 + len(_lines)
    _y0 = _overlay_box(
        console,
        screen_width=screen_width,
        screen_height=screen_height,
        box_w=70,
        box_h=_box_h,
    )
    _centered_print(
        console, screen_width=screen_width, y=_y0 + 1,
        text=_title, fg=ui.COLOR_TITLE,
    )
    _centered_print(
        console, screen_width=screen_width, y=_y0 + 3,
        text=f"OFFERED BY: {npc_name.upper()}", fg=ui.COLOR_VALUE_DIM,
    )
    _body_y = _y0 + 5
    for _i, _line in enumerate(_lines):
        _centered_print(
            console, screen_width=screen_width, y=_body_y + _i,
            text=_line, fg=ui.COLOR_DESCRIPTION,
        )
    _opt_y = _body_y + len(_lines) + 1
    for _i, _label in enumerate(("Accept help", "Keep looking")):
        _is_sel = _i == selected
        _marker_open = "> " if _is_sel else "  "
        _marker_close = " <" if _is_sel else "  "
        _centered_print(
            console, screen_width=screen_width, y=_opt_y + _i,
            text=f"{_marker_open}{_label}{_marker_close}",
            fg=ui.COLOR_OPTION_HIGHLIGHT if _is_sel else ui.COLOR_OPTION,
        )
    _centered_print(
        console, screen_width=screen_width, y=_opt_y + 3,
        text="ARROW KEYS / j,k navigate - ENTER select - ESC keep looking",
        fg=ui.COLOR_INSTRUCTION,
    )


def show_help_offer(ctx, npc_id: str, step_id: str) -> OfferOutcome:
    """Show the faction's help-offer modal; return the player's choice.

    Pulls the live dialogue for ``npc_id`` on ``step_id`` and shows its
    full ``intro``/``active`` offer text in a modal with two options:
    **Accept help** (returns :attr:`OfferOutcome.ACCEPT` — the caller
    then runs :func:`trigger_dialogue`) and **Keep looking** (returns
    :attr:`OfferOutcome.DECLINE` — back to the talk modal). Window
    close returns :attr:`OfferOutcome.QUIT`.

    Falls back to :attr:`OfferOutcome.DECLINE` when the dialogue is
    missing or has no offer text (shouldn't happen — callers gate on
    ``quest_option_for`` first).
    """
    _step = find_main_quest_step(step_id)
    _dialogue = _step.dialogues.get(npc_id)
    if _dialogue is None:
        return OfferOutcome.DECLINE
    _status = ctx.main_quest_progress.get(step_id, "")
    _offer_text = _dialogue.active if _status == STATUS_ACTIVE else _dialogue.intro
    if not _offer_text:
        return OfferOutcome.DECLINE
    from .data.npcs import find_npc as _find_npc
    _npc_name = _find_npc(npc_id).name
    _selected = 0
    console = make_console()

    def _render() -> None:
        render_help_offer(
            console,
            screen_width=SCREEN_WIDTH,
            screen_height=SCREEN_HEIGHT,
            npc_name=_npc_name,
            offer_text=_offer_text,
            selected=_selected,
        )

    def _update(event) -> OfferOutcome:
        nonlocal _selected
        if isinstance(event, tcod.event.Quit):
            return OfferOutcome.QUIT
        if not isinstance(event, tcod.event.KeyDown):
            return OfferOutcome.IGNORE
        sym = event.sym
        sym_name: str = getattr(sym, "name", "").lower()
        if sym in ui._UP_SYMS or sym_name == "k":
            _selected = 0
            return OfferOutcome.IGNORE
        if sym in ui._DOWN_SYMS or sym_name == "j":
            _selected = 1
            return OfferOutcome.IGNORE
        if sym in ui._ENTER_SYMS:
            return OfferOutcome.ACCEPT if _selected == 0 else OfferOutcome.DECLINE
        if sym in ui._ESCAPE_SYMS:
            return OfferOutcome.DECLINE
        return OfferOutcome.IGNORE

    return ui.Modal(ctx.context, console).run(_render, _update)


def mars_exploration_unlocked(ctx) -> bool:
    """True once the signal has been received (Mars gate open).

    Gates the planet-menu "Explore signal" option for Mars (see
    :func:`spacehack.menus._planet._run_planet_menu`).
    """
    return step_status(ctx, "prologue_signal") in (STATUS_ACTIVE, STATUS_COMPLETED)


def place_mars_door(game_map: world.GameMap, spawn: world.Position) -> world.Entity:
    """Place the sealed alien door at the walkable cell farthest from spawn.

    The Mars surface is generated once and cached in ``ctx.interiors``
    (same persistence as salvage wreck interiors), so the door is
    placed deterministically AFTER the FIRST generation only. A BFS
    from the spawn over walkable tiles lands on the farthest reachable
    cell — guaranteed findable on any run, no special room tagging.
    """
    _start = (spawn.x, spawn.y)
    # Guard: the spawn must be walkable (BSP centers always are, but a
    # non-walkable spawn would otherwise place the door under the player).
    if not game_map.tiles[_start[1]][_start[0]].walkable:
        for _yy in range(game_map.height):
            for _xx in range(game_map.width):
                if game_map.tiles[_yy][_xx].walkable:
                    _start = (_xx, _yy)
                    break
            if game_map.tiles[_start[1]][_start[0]].walkable:
                break
    _dist: dict[tuple[int, int], int] = {_start: 0}
    _queue: deque[tuple[int, int]] = deque([_start])
    _far = _start
    while _queue:
        _x, _y = _queue.popleft()
        _d = _dist[(_x, _y)]
        if _d > _dist[_far]:
            _far = (_x, _y)
        for _nx, _ny in ((_x + 1, _y), (_x - 1, _y), (_x, _y + 1), (_x, _y - 1)):
            if not (0 <= _nx < game_map.width and 0 <= _ny < game_map.height):
                continue
            if (_nx, _ny) in _dist:
                continue
            if game_map.tiles[_ny][_nx].walkable:
                _dist[(_nx, _ny)] = _d + 1
                _queue.append((_nx, _ny))
    _door = world.Entity(
        char="=",
        fg=(140, 80, 255),  # alien violet — distinct from any Mars tile
        pos=world.Position(_far[0], _far[1]),
        name="Sealed Entrance",
        main_quest_door=True,
    )
    game_map.entities.append(_door)
    return _door


def prepare_mars_surface(ctx, game_map: world.GameMap, spawn: world.Position) -> None:
    """Hook after FIRST generating the Mars surface dungeon.

    Called only on the first visit (the EXPLORE handler caches the
    surface in ``ctx.interiors`` afterward, so re-entry reuses the
    same map — door stays where it was found, fog stays revealed).
    Advances the checkpoint step (``prologue_mars_unlocked`` ->
    ``prologue_mars_entrance``) and places the sealed door while it
    is still closed.
    """
    if step_status(ctx, "prologue_mars_unlocked") == STATUS_AVAILABLE:
        complete_step(ctx, "prologue_mars_unlocked")  # auto-advances entrance -> available
    if step_status(ctx, "prologue_mars_entrance") == STATUS_AVAILABLE:
        start_step(ctx, "prologue_mars_entrance")  # objective: find the door
    if step_status(ctx, "prologue_open") != STATUS_COMPLETED:
        place_mars_door(game_map, spawn)


def bump_mars_door(ctx) -> None:
    """Handle bumping the sealed alien door on Mars.

    * Before the door is found (entrance step active): discover it —
      completes ``prologue_mars_entrance``, making ``prologue_seek_help``
      available. Logs the "won't open with any human tool" flavor and
      shows the SEALED ENTRANCE overlay (the two quest-beat bumps
      surface as full-screen modals, mirroring the incoming signal).
    * After ``prologue_open`` is available (player holds a faction
      tool): open it — completes ``prologue_open``, plants the claim,
      recovers the prison data (fuels Act 1), shows the opening overlay.
    * Otherwise (repeat bumps): log line only — no modal nag.
    """
    _open_status = step_status(ctx, "prologue_open")
    if _open_status in (STATUS_AVAILABLE, STATUS_ACTIVE):
        complete_step(ctx, "prologue_open")
        ctx.main_quest_unlocked_items.add("prison_data")
        ctx.log.add_colored(
            "The seal gives way. Inside: an empty cell of alien make — "
            "and a cache of data beyond any human technology.",
            message_log.COLOR_IMPORTANT_EVENT,
        )
        ctx.log.add("The prison data is recovered. Someone will want to study this.")
        show_sealed_door_overlay(ctx, "open")
        return
    _entrance_status = step_status(ctx, "prologue_mars_entrance")
    if _entrance_status in (STATUS_AVAILABLE, STATUS_ACTIVE):
        complete_step(ctx, "prologue_mars_entrance")
        ctx.log.add_colored(
            "A door of alien make, set into the red dust. No visible "
            "mechanism — older than the colony. It will not open.",
            message_log.COLOR_IMPORTANT_EVENT,
        )
        show_sealed_door_overlay(ctx, "discover")
        return
    if step_status(ctx, "prologue_open") == STATUS_COMPLETED:
        ctx.log.add("The opened entrance gapes dark and empty.")
        return
    ctx.log.add("The sealed door holds fast. It needs a tool you don't have.")


__all__ = [
    "STATUS_AVAILABLE",
    "STATUS_ACTIVE",
    "STATUS_COMPLETED",
    "step_status",
    "start_step",
    "complete_step",
    "resolve_npc_dialogue",
    "quest_option_for",
    "trigger_dialogue",
    "current_main_quest_objective",
    "maybe_trigger_signal",
    "show_prologue_transmission",
    "show_sealed_door_overlay",
    "OfferOutcome",
    "show_help_offer",
    "mars_exploration_unlocked",
    "place_mars_door",
    "prepare_mars_surface",
    "bump_mars_door",
]
