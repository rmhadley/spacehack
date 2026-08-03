"""Main quest Act 0: signal trigger, Mars door, full-screen overlays, gate popups."""

from __future__ import annotations

from collections import deque
from enum import Enum, auto

import tcod.event

from .. import message_log
from .. import ui
from .. import world
from ..engine import SCREEN_HEIGHT, SCREEN_WIDTH, make_console
from ..data.main_quest import find_main_quest_step, main_quest_step_after
from ._core import (
    STATUS_ACTIVE,
    STATUS_AVAILABLE,
    STATUS_COMPLETED,
    step_status,
    start_step,
    complete_step,
    _active_objective_step,
    _complete_bump_objective,
)

_SIGNAL_SYSTEM_ID = "sol"


# ---------------------------------------------------------------------------
# Signal trigger
# ---------------------------------------------------------------------------


def maybe_trigger_signal(ctx, system_id: str) -> bool:
    """Fire the prologue signal on the first jump out of Sol."""
    if system_id != _SIGNAL_SYSTEM_ID:
        return False
    if step_status(ctx, "prologue_signal") in (STATUS_ACTIVE, STATUS_COMPLETED):
        return False
    ctx.main_quest_progress["prologue_signal"] = STATUS_AVAILABLE
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
# Farthest-walkable BFS (shared by Mars door + delve sites)
# ---------------------------------------------------------------------------


def _farthest_walkable(game_map: world.GameMap, spawn: world.Position) -> world.Position:
    """Walkable cell farthest from ``spawn`` (BFS over walkable tiles)."""
    _start = (spawn.x, spawn.y)
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
    return world.Position(_far[0], _far[1])


# ---------------------------------------------------------------------------
# Mars surface + sealed door
# ---------------------------------------------------------------------------


def place_mars_door(game_map: world.GameMap, spawn: world.Position) -> world.Entity:
    """Place the sealed alien door at the farthest walkable cell from spawn."""
    _door = world.Entity(
        char="=",
        fg=(140, 80, 255),
        pos=_farthest_walkable(game_map, spawn),
        name="Sealed Entrance",
        main_quest_door=True,
    )
    game_map.entities.append(_door)
    return _door


def prepare_mars_surface(ctx, game_map: world.GameMap, spawn: world.Position) -> None:
    """Hook after FIRST generating the Mars surface dungeon."""
    if step_status(ctx, "prologue_mars_unlocked") == STATUS_AVAILABLE:
        complete_step(ctx, "prologue_mars_unlocked")
    if step_status(ctx, "prologue_mars_entrance") == STATUS_AVAILABLE:
        start_step(ctx, "prologue_mars_entrance")
    if step_status(ctx, "prologue_open") != STATUS_COMPLETED:
        place_mars_door(game_map, spawn)


def bump_mars_door(ctx) -> None:
    """Handle bumping the sealed alien door on Mars."""
    if _complete_bump_objective(ctx):
        return
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


# ---------------------------------------------------------------------------
# Delve site preparation
# ---------------------------------------------------------------------------


def prepare_delve_site(
    ctx,
    game_map: world.GameMap,
    spawn: world.Position,
    planet_id: str,
) -> bool:
    """Place the quest cache for planet_id's active delve step."""
    _step_id = _active_objective_step(ctx, "delve", planet_id=planet_id)
    if _step_id is None:
        return False
    _step = find_main_quest_step(_step_id)
    _cache = world.Entity(
        char="%",
        fg=(255, 215, 0),
        pos=_farthest_walkable(game_map, spawn),
        name="Quest Cache",
        width=1, height=1,
        loot_data={"goods": list(_step.delve_good_ids)},
    )
    _cache.main_quest_step_id = _step_id
    game_map.entities.append(_cache)
    return True


# ---------------------------------------------------------------------------
# Exploration gates
# ---------------------------------------------------------------------------


def mars_exploration_unlocked(ctx) -> bool:
    """True once the signal has been received (Mars gate open)."""
    return step_status(ctx, "prologue_signal") in (STATUS_ACTIVE, STATUS_COMPLETED)


def delve_site_unlocked(ctx, planet_id: str) -> bool:
    """True while a delve step targeting planet_id is live."""
    return _active_objective_step(ctx, "delve", planet_id=planet_id) is not None


def surface_exploration_unlocked(ctx, planet_id: str) -> bool:
    """True when planet_id's surface explore option may be shown."""
    if planet_id == "mars":
        return mars_exploration_unlocked(ctx)
    return delve_site_unlocked(ctx, planet_id)


# ---------------------------------------------------------------------------
# Quest NPC spawning
# ---------------------------------------------------------------------------


def _wall_adjacent_tile(
    game_map: world.GameMap,
    near: world.Position,
) -> world.Position:
    """Return a non-walkable tile adjacent to a walkable tile near near."""
    for _r in range(1, 10):
        for _dy in range(-_r, _r + 1):
            for _dx in range(-_r, _r + 1):
                if max(abs(_dx), abs(_dy)) != _r:
                    continue
                _x, _y = near.x + _dx, near.y + _dy
                if not (0 <= _x < game_map.width and 0 <= _y < game_map.height):
                    continue
                if game_map.tiles[_y][_x].walkable:
                    continue
                for _nx, _ny in ((_x + 1, _y), (_x - 1, _y),
                                 (_x, _y + 1), (_x, _y - 1)):
                    if (0 <= _nx < game_map.width
                            and 0 <= _ny < game_map.height
                            and game_map.tiles[_ny][_nx].walkable):
                        return world.Position(_x, _y)
    return near


def spawn_quest_npcs(
    ctx,
    game_map: world.GameMap,
    planet_id: str,
    *,
    spawn_pos: world.Position | None = None,
) -> None:
    """Add quest-conditional NPCs to game_map after loading a city or dungeon."""
    _need_npc: str | None = None
    if planet_id == "barnards_b" and ctx.main_quest_chain == "bar":
        _need = any(
            step_status(ctx, _sid) in (STATUS_AVAILABLE, STATUS_ACTIVE)
            for _sid in ("bar_q2_proof", "bar_q3_rigparts")
        ) or (
            step_status(ctx, "bar_q2_proof") == STATUS_COMPLETED
            and step_status(ctx, "bar_q3_rigparts") not in (STATUS_COMPLETED,)
        )
        if _need:
            _need_npc = "old_smuggler"
    elif planet_id == "tc_b" and ctx.main_quest_chain == "merchants":
        _need = (
            step_status(ctx, "mer_q3_transport") in (STATUS_AVAILABLE, STATUS_ACTIVE)
            or (
                step_status(ctx, "mer_q3_transport") == STATUS_COMPLETED
                and step_status(ctx, "mer_q4_calibrate") in (STATUS_AVAILABLE, STATUS_ACTIVE)
            )
        )
        if _need:
            _need_npc = "salvage_specialist"
    if _need_npc is None:
        return
    if any(getattr(_e, 'npc_id', '') == _need_npc for _e in game_map.entities):
        return
    from ..data.npcs import find_npc as _find_npc
    _npc = _find_npc(_need_npc)
    if spawn_pos is not None:
        _pos = _wall_adjacent_tile(game_map, spawn_pos)
    else:
        _pos = world.Position(x=38, y=10)
    game_map.entities.append(world.Entity(
        char=_npc.char,
        fg=_npc.fg,
        pos=_pos,
        name=_npc.name,
        npc_id=_npc.id,
        width=1, height=1,
    ))


# ---------------------------------------------------------------------------
# Full-screen overlay plumbing
# ---------------------------------------------------------------------------


class _ModalOutcome(Enum):
    IGNORE = auto()
    CLOSE = auto()
    QUIT = auto()


class OfferOutcome(Enum):
    IGNORE = auto()
    ACCEPT = auto()
    DECLINE = auto()
    QUIT = auto()


def _overlay_box(console, *, screen_width, screen_height, box_w, box_h) -> int:
    console.clear()
    y0 = max(0, (screen_height - box_h) // 2 - 2)
    ui.paint_rect_border(
        console,
        (max(0, (screen_width - box_w) // 2), y0, box_w, box_h),
        fg=ui.COLOR_VALUE_DIM,
    )
    return y0


def _centered_print(console, *, screen_width, y, text, fg) -> None:
    console.print(x=ui.centered_x(text, screen_width), y=y, string=text, fg=fg)


def _modal_dismiss_update(event: tcod.event.Event) -> _ModalOutcome:
    if isinstance(event, tcod.event.Quit):
        return _ModalOutcome.QUIT
    if not isinstance(event, tcod.event.KeyDown):
        return _ModalOutcome.IGNORE
    if event.sym in ui._ENTER_SYMS or event.sym in ui._ESCAPE_SYMS:
        return _ModalOutcome.CLOSE
    return _ModalOutcome.IGNORE


# ---------------------------------------------------------------------------
# Incoming transmission overlay
# ---------------------------------------------------------------------------

_SIGNAL_STATIC: tuple[str, ...] = (
    "...--.-.-..--...-..-.-.--.....-.-..--.-..",
    "-.--..-.-..--.-..-...--..-.-..--...--...-",
    "..-.-.--.....-.-..--.-..--...--.-..---.-.",
)
_SIGNAL_TRACE_FG: tuple[int, int, int] = (90, 150, 90)


def render_incoming_transmission(console, *, screen_width, screen_height) -> None:
    _y0 = _overlay_box(console, screen_width=screen_width, screen_height=screen_height, box_w=64, box_h=18)
    _centered_print(console, screen_width=screen_width, y=_y0 + 1, text="INCOMING TRANSMISSION", fg=ui.COLOR_TITLE)
    _centered_print(console, screen_width=screen_width, y=_y0 + 3,
                    text="FREQUENCY: UNKNOWN    SOURCE: UNKNOWN    ENCRYPTION: NONE", fg=ui.COLOR_VALUE_DIM)
    for _i, _line in enumerate(_SIGNAL_STATIC):
        _centered_print(console, screen_width=screen_width, y=_y0 + 5 + _i, text=_line, fg=_SIGNAL_TRACE_FG)
    _centered_print(console, screen_width=screen_width, y=_y0 + 9,
                    text="A burst of coordinates cuts through the static -", fg=ui.COLOR_DESCRIPTION)
    _centered_print(console, screen_width=screen_width, y=_y0 + 10, text="then silence.", fg=ui.COLOR_DESCRIPTION)
    _centered_print(console, screen_width=screen_width, y=_y0 + 12,
                    text="They resolve to somewhere on Mars.", fg=ui.COLOR_OPTION_HIGHLIGHT)
    _centered_print(console, screen_width=screen_width, y=_y0 + 14,
                    text="Press ENTER to acknowledge", fg=ui.COLOR_INSTRUCTION)


def show_prologue_transmission(ctx) -> None:
    console = make_console()
    def _render(): render_incoming_transmission(console, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)
    def _update(event): return _modal_dismiss_update(event)
    ui.Modal(ctx.context, console).run(_render, _update)


# ---------------------------------------------------------------------------
# Quest summon overlay
# ---------------------------------------------------------------------------


def render_quest_summon(console, *, screen_width, screen_height, message, objective="") -> None:
    _lines = ui.wrap_text(message, 60)
    _obj_lines = ui.wrap_text(objective, 60) if objective else []
    _box_h = 14 + len(_lines) + len(_obj_lines) + (1 if _obj_lines else 0)
    _y0 = _overlay_box(console, screen_width=screen_width, screen_height=screen_height, box_w=70, box_h=_box_h)
    _centered_print(console, screen_width=screen_width, y=_y0 + 1, text="INCOMING MESSAGE", fg=ui.COLOR_TITLE)
    _centered_print(console, screen_width=screen_width, y=_y0 + 3,
                    text="SOURCE: CHAIN CONTACT    ENCRYPTION: NONE    REPLY: NOT REQUIRED", fg=ui.COLOR_VALUE_DIM)
    _body_y = _y0 + 5
    for _i, _line in enumerate(_lines):
        _centered_print(console, screen_width=screen_width, y=_body_y + _i, text=_line, fg=ui.COLOR_DESCRIPTION)
    _hint_y = _body_y + len(_lines) + 2
    if _obj_lines:
        for _i, _line in enumerate(_obj_lines):
            _centered_print(console, screen_width=screen_width, y=_hint_y + _i, text=_line, fg=ui.COLOR_OPTION_HIGHLIGHT)
        _hint_y += len(_obj_lines) + 1
    _centered_print(console, screen_width=screen_width, y=_hint_y,
                    text="Press ENTER to acknowledge", fg=ui.COLOR_INSTRUCTION)


def show_quest_summon(ctx, message: str, *, objective: str = "") -> None:
    console = make_console()
    def _render(): render_quest_summon(console, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT, message=message, objective=objective)
    def _update(event): return _modal_dismiss_update(event)
    ui.Modal(ctx.context, console).run(_render, _update)


# ---------------------------------------------------------------------------
# Gate popup (time-gate explanation)
# ---------------------------------------------------------------------------

_OFFER_BODY_WIDTH = 62


def render_gate_popup(console, *, screen_width, screen_height, faction, body_text) -> None:
    """Paint a dismiss-only time-gate explanation popup."""
    _lines = ui.wrap_text(body_text, _OFFER_BODY_WIDTH)
    _box_h = 10 + len(_lines)
    _y0 = _overlay_box(console, screen_width=screen_width, screen_height=screen_height, box_w=70, box_h=_box_h)
    _centered_print(console, screen_width=screen_width, y=_y0 + 1, text="THE WORK BEGINS", fg=ui.COLOR_TITLE)
    _centered_print(console, screen_width=screen_width, y=_y0 + 3,
                    text=f"FACTION: {faction.upper()}", fg=ui.COLOR_VALUE_DIM)
    _body_y = _y0 + 5
    for _i, _line in enumerate(_lines):
        _centered_print(console, screen_width=screen_width, y=_body_y + _i, text=_line, fg=ui.COLOR_DESCRIPTION)
    _centered_print(console, screen_width=screen_width, y=_body_y + len(_lines) + 2,
                    text="Press ENTER to continue", fg=ui.COLOR_INSTRUCTION)


def show_gate_popup(ctx, faction: str, body_text: str) -> None:
    """Show a time-gate explanation popup and block until dismissed."""
    console = make_console()
    def _render(): render_gate_popup(console, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT, faction=faction, body_text=body_text)
    def _update(event): return _modal_dismiss_update(event)
    ui.Modal(ctx.context, console).run(_render, _update)


# ---------------------------------------------------------------------------
# Chain continuation (after dialogue trigger)
# ---------------------------------------------------------------------------


def maybe_continue_chain(ctx, npc_id: str, step_id: str) -> None:
    """After trigger_dialogue completes step_id, handle follow-up popups."""
    from ._dialogue import trigger_dialogue
    _step = find_main_quest_step(step_id)
    if step_id == "prologue_seek_help" and ctx.main_quest_chain:
        _q1 = main_quest_step_after("prologue_seek_help", chain=ctx.main_quest_chain)
        if _q1 is not None \
                and step_status(ctx, _q1.id) == STATUS_AVAILABLE \
                and npc_id in _q1.dialogues:
            _offer = show_help_offer(ctx, npc_id, _q1.id)
            if _offer is OfferOutcome.QUIT:
                return
            if _offer is OfferOutcome.ACCEPT:
                trigger_dialogue(ctx, npc_id, _q1.id)
                _step = find_main_quest_step(_q1.id)
            else:
                return
    if _step.wait_days > 0 and _step.completion_flavor:
        if _step.objective_type == "smuggle" and step_status(ctx, _step.id) == STATUS_ACTIVE:
            return
        _fac = (_step.chain or "faction").capitalize()
        show_gate_popup(ctx, _fac, _step.completion_flavor)


# ---------------------------------------------------------------------------
# Sealed door overlay
# ---------------------------------------------------------------------------

_DOOR_RUNES: tuple[str, ...] = (
    "##=+==#=+==#=+==#=+==##=+==#=+",
    "=+==#=+==#=+==#=+==#=+==#=+==#",
    "+==#=+==#=+==#=+==#=+==#=+==#=",
)
_DOOR_RUNE_FG: tuple[int, int, int] = (150, 95, 255)
_DOOR_ART_FG: tuple[int, int, int] = (140, 80, 255)

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


def render_sealed_door_overlay(console, *, screen_width, screen_height, beat) -> None:
    _content = _DOOR_OVERLAYS[beat]
    _art = _content["art"]
    _body = _content["body"]
    _box_h = 15 + len(_art) + len(_body)
    _y0 = _overlay_box(console, screen_width=screen_width, screen_height=screen_height, box_w=66, box_h=_box_h)
    _centered_print(console, screen_width=screen_width, y=_y0 + 1, text=_content["title"], fg=ui.COLOR_TITLE)
    _centered_print(console, screen_width=screen_width, y=_y0 + 3, text=_content["meta"], fg=ui.COLOR_VALUE_DIM)
    for _i, _line in enumerate(_DOOR_RUNES):
        _centered_print(console, screen_width=screen_width, y=_y0 + 5 + _i, text=_line, fg=_DOOR_RUNE_FG)
    _art_y = _y0 + 9
    for _i, _line in enumerate(_art):
        _centered_print(console, screen_width=screen_width, y=_art_y + _i, text=_line, fg=_DOOR_ART_FG)
    _body_y = _art_y + len(_art) + 1
    for _i, _line in enumerate(_body):
        _centered_print(console, screen_width=screen_width, y=_body_y + _i, text=_line, fg=ui.COLOR_DESCRIPTION)
    _centered_print(console, screen_width=screen_width, y=_body_y + len(_body) + 1,
                    text=_content["highlight"], fg=ui.COLOR_OPTION_HIGHLIGHT)
    _centered_print(console, screen_width=screen_width, y=_body_y + len(_body) + 3,
                    text=_content["instruction"], fg=ui.COLOR_INSTRUCTION)


def show_sealed_door_overlay(ctx, beat: str) -> None:
    console = make_console()
    def _render(): render_sealed_door_overlay(console, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT, beat=beat)
    def _update(event): return _modal_dismiss_update(event)
    ui.Modal(ctx.context, console).run(_render, _update)


# ---------------------------------------------------------------------------
# Help-offer modal
# ---------------------------------------------------------------------------


def render_help_offer(console, *, screen_width, screen_height, npc_name, offer_text, selected) -> None:
    _title = "AN OFFER OF HELP"
    _lines = ui.wrap_text(offer_text, _OFFER_BODY_WIDTH)
    _box_h = 14 + len(_lines)
    _y0 = _overlay_box(console, screen_width=screen_width, screen_height=screen_height, box_w=70, box_h=_box_h)
    _centered_print(console, screen_width=screen_width, y=_y0 + 1, text=_title, fg=ui.COLOR_TITLE)
    _centered_print(console, screen_width=screen_width, y=_y0 + 3,
                    text=f"OFFERED BY: {npc_name.upper()}", fg=ui.COLOR_VALUE_DIM)
    _body_y = _y0 + 5
    for _i, _line in enumerate(_lines):
        _centered_print(console, screen_width=screen_width, y=_body_y + _i, text=_line, fg=ui.COLOR_DESCRIPTION)
    _opt_y = _body_y + len(_lines) + 1
    for _i, _label in enumerate(("Accept", "I need more time")):
        _is_sel = _i == selected
        _marker_open = "> " if _is_sel else "  "
        _marker_close = " <" if _is_sel else "  "
        _centered_print(console, screen_width=screen_width, y=_opt_y + _i,
                        text=f"{_marker_open}{_label}{_marker_close}",
                        fg=ui.COLOR_OPTION_HIGHLIGHT if _is_sel else ui.COLOR_OPTION)
    _centered_print(console, screen_width=screen_width, y=_opt_y + 3,
                    text="ARROW KEYS / j,k navigate - ENTER select - ESC go back", fg=ui.COLOR_INSTRUCTION)


def show_help_offer(ctx, npc_id: str, step_id: str) -> OfferOutcome:
    _step = find_main_quest_step(step_id)
    _dialogue = _step.dialogues.get(npc_id)
    if _dialogue is None:
        return OfferOutcome.DECLINE
    _status = ctx.main_quest_progress.get(step_id, "")
    _offer_text = _dialogue.active if _status == STATUS_ACTIVE else _dialogue.intro
    if not _offer_text:
        return OfferOutcome.DECLINE
    from ..data.npcs import find_npc as _find_npc
    _npc_name = _find_npc(npc_id).name
    _selected = 0
    console = make_console()

    def _render():
        render_help_offer(console, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT,
                          npc_name=_npc_name, offer_text=_offer_text, selected=_selected)

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


# ---------------------------------------------------------------------------
# Quest readout overlay
# ---------------------------------------------------------------------------


def render_quest_readout(console, *, screen_width, screen_height, npc_name, body_text) -> None:
    _lines = ui.wrap_text(body_text, _OFFER_BODY_WIDTH)
    _box_h = 10 + len(_lines)
    _y0 = _overlay_box(console, screen_width=screen_width, screen_height=screen_height, box_w=70, box_h=_box_h)
    _centered_print(console, screen_width=screen_width, y=_y0 + 1, text=npc_name.upper(), fg=ui.COLOR_TITLE)
    _body_y = _y0 + 3
    for _i, _line in enumerate(_lines):
        _centered_print(console, screen_width=screen_width, y=_body_y + _i, text=_line, fg=ui.COLOR_DESCRIPTION)
    _centered_print(console, screen_width=screen_width, y=_body_y + len(_lines) + 2,
                    text="Press ENTER to continue", fg=ui.COLOR_INSTRUCTION)


def show_quest_readout(ctx, npc, body_text: str) -> None:
    console = make_console()
    def _render(): render_quest_readout(console, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT, npc_name=npc.name, body_text=body_text)
    def _update(event): return _modal_dismiss_update(event)
    ui.Modal(ctx.context, console).run(_render, _update)
