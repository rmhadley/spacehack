"""Player-initiated comms with NPC ships in space.

Press ``T`` in space mode to open the comms panel, which scans for
NPC ships within ``comms_range`` (default 15 cells) and lets the
player hail them for interaction (trade, cargo scan, attack, or
end transmission).

Faction-aware: pirates show ``(hostile)`` tags and an "Attack"
option instead of "Open Trade". Merchants and other neutrals get
"Open Trade" and "Scan Cargo" options.
"""

from __future__ import annotations

import math
from enum import Enum, auto

import tcod.console
import tcod.event

from . import ui
from .data.npc_ships import find_npc_ship as _find_npc_ship
from .engine import SCREEN_HEIGHT, SCREEN_WIDTH, make_console
from .game_context import GameContext
from . import message_log as _ml


class _CommsListOutcome(Enum):
    """Outcome for the contact-list modal."""
    IGNORE = auto()
    BACK = auto()
    QUIT = auto()
    HAIL = auto()   # ENTER on a contact → open interaction modal


class _InteractionOutcome(Enum):
    """Outcome for the per-contact interaction sub-modal."""
    IGNORE = auto()
    TRADE = auto()
    ATTACK = auto()
    SCAN = auto()
    BACK = auto()    # "End Transmission" or ESC
    QUIT = auto()


# ---------------------------------------------------------------------------
# Contact scanning
# ---------------------------------------------------------------------------

def _scan_contacts(
    ctx: GameContext,
    player_pos,
) -> list[tuple[str, object, object]]:
    """Return a list of ``(name, spec, entity)`` for NPCs visible on screen.

    Computes the current camera viewport (80x54 centred on the player)
    and returns any unowned entity with an ``npc_ship_id`` tag whose
    world position falls within that viewport rectangle.
    """
    from . import solar_system as _ss
    _system = _ss.current_system()
    if _system is None:
        return []
    _view_w = _ss.SOL_VIEW_W
    _view_h = _ss.SOL_VIEW_H
    _cam_x = max(0, min(player_pos.x - _view_w // 2, _system.width - _view_w))
    _cam_y = max(0, min(player_pos.y - _view_h // 2, _system.height - _view_h))

    contacts: list[tuple[str, object, object]] = []
    for _e in ctx.game_map.entities:
        if getattr(_e, 'owned', False):
            continue
        _pid = getattr(_e, 'npc_ship_id', '')
        if not _pid:
            continue
        try:
            _spec = _find_npc_ship(_pid)
        except (KeyError, ImportError):
            continue
        # Filter by viewport visibility (world-coord rectangle check).
        if not (_cam_x <= _e.pos.x < _cam_x + _view_w
                and _cam_y <= _e.pos.y < _cam_y + _view_h):
            continue
        contacts.append((_spec.name, _spec, _e))
    # Sort by distance (nearest first) for consistent ordering.
    contacts.sort(
        key=lambda c: math.hypot(
            player_pos.x - c[2].pos.x,
            player_pos.y - c[2].pos.y,
        ),
    )
    return contacts


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

_CONTACTS_TITLE_COLOR: tuple[int, int, int] = (130, 220, 255)      # cyan
_CONTACTS_HOSTILE_TAG: tuple[int, int, int] = (255, 80, 80)        # red hostile tag
_CONTACTS_SELECTED: tuple[int, int, int] = (255, 255, 255)         # white selected
_CONTACTS_NORMAL: tuple[int, int, int] = (200, 200, 220)           # pale lavender
_CONTACTS_DIM: tuple[int, int, int] = (150, 150, 150)              # silver dim
_CONTACTS_FLAVOR: tuple[int, int, int] = (175, 170, 210)           # muted lavender

_INTERACTION_TITLE: tuple[int, int, int] = (130, 220, 255)         # cyan title
_INTERACTION_FLAVOR: tuple[int, int, int] = (175, 170, 210)        # flavor text
_INTERACTION_OPTION: tuple[int, int, int] = (200, 200, 220)        # normal option
_INTERACTION_HIGHLIGHT: tuple[int, int, int] = (255, 255, 255)     # selected option
_INTERACTION_INSTRUCTION: tuple[int, int, int] = (110, 130, 175)   # instruction


def _render_comms_panel(
    console: tcod.console.Console,
    contacts: list[tuple[str, object, object]],
    selected: int,
) -> None:
    """Paint the comms contact-list panel.

    Uses a fixed left-aligned column (rather than per-line centering)
    so scrolling never shifts the text horizontally. Selection markers
    have consistent width so all contact lines occupy the same space.
    """
    console.clear()
    n = len(contacts)
    title = f"COMMS — {n} contact{('' if n == 1 else 's')} in range"
    console.print(
        x=ui.centered_x(title, SCREEN_WIDTH),
        y=SCREEN_HEIGHT // 4,
        string=title,
        fg=_CONTACTS_TITLE_COLOR,
    )

    # Fixed left column for all contact rows — left of centre so there's
    # room for long names + the (hostile) tag without wrapping.
    _COL_X = SCREEN_WIDTH // 4
    _INDENT = 2
    list_top = SCREEN_HEIGHT // 4 + 2
    for i, (name, spec, entity) in enumerate(contacts):
        row = list_top + i * 3
        is_selected = i == selected
        is_hostile = spec.faction == 'pirate'

        # Consistent-width markers: both selected and unselected markers
        # are 4 chars total (2 open + 2 close) so the name never shifts.
        marker_open = '> ' if is_selected else '  '
        marker_close = ' <' if is_selected else '  '
        hostile_tag = ' (hostile)' if is_hostile else ''
        name_fg = _CONTACTS_SELECTED if is_selected else (
            _CONTACTS_HOSTILE_TAG if is_hostile else _CONTACTS_NORMAL
        )
        text = f"{marker_open}{name}{hostile_tag}{marker_close}"
        console.print(x=_COL_X, y=row, string=text, fg=name_fg)

        # Flavor text, indented from the column.
        flavor = spec.comms_lines[0] if spec.comms_lines else "..."
        console.print(
            x=_COL_X + _INDENT, y=row + 1,
            string=f'"{flavor}"',
            fg=_CONTACTS_FLAVOR if is_selected else _CONTACTS_DIM,
        )

    hint = "UP/DOWN / j,k navigate - ENTER hail - ESC close"
    console.print(
        x=ui.centered_x(hint, SCREEN_WIDTH),
        y=list_top + n * 3 + 1,
        string=hint,
        fg=_INTERACTION_INSTRUCTION,
    )


def _render_interaction_modal(
    console: tcod.console.Console,
    contact_name: str,
    spec: object,
    options: list[str],
    selected: int,
) -> None:
    """Paint the per-contact interaction sub-modal.

    Flavor text rendered directly; options delegated to
    :func:`ui.render_selectable_list` for consistent markers.
    """
    console.clear()
    title = f"{contact_name} — Hailing"
    title_y = SCREEN_HEIGHT // 4
    console.print(
        x=ui.centered_x(title, SCREEN_WIDTH),
        y=title_y,
        string=title,
        fg=_INTERACTION_TITLE,
    )

    # Flavor text — left-aligned from a fixed column.
    _COL_X = SCREEN_WIDTH // 4
    flavor_y = title_y + 2
    for line in spec.comms_lines:
        wrapped = ui.wrap_text(line, max_width=SCREEN_WIDTH - _COL_X * 2)
        for wl in wrapped:
            console.print(
                x=_COL_X, y=flavor_y,
                string=wl,
                fg=_INTERACTION_FLAVOR,
            )
            flavor_y += 1

    # Options via reusable list renderer.
    _opt_items = [(opt, "") for opt in options]
    _list_title_y = flavor_y + 1
    ui.render_selectable_list(
        console, SCREEN_WIDTH, SCREEN_HEIGHT,
        title="",
        items=_opt_items,
        selected=selected,
        col_x=_COL_X,
        title_y=_list_title_y,
        title_fg=_INTERACTION_TITLE,
        row_spacing=2,
        item_fg_selected=_INTERACTION_HIGHLIGHT,
        item_fg_normal=_INTERACTION_OPTION,
        hint="UP/DOWN navigate - ENTER select - ESC back",
        hint_fg=_INTERACTION_INSTRUCTION,
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def open_comms(
    ctx: GameContext,
    player_pos,
) -> tuple[list, list] | None:
    """Open the comms panel.

    Scans for NPC ships in comms range. If none found, logs a message
    and returns ``None``.

    If the player selects **Attack** from the interaction sub-modal,
    returns ``(specs, positions)`` suitable for direct hand-off to
    ``combat._handle_combat_encounter()``. Otherwise returns ``None``
    (player chose End Transmission, Open Trade, Scan Cargo, or ESC).

    Scan Cargo logs the cargo manifest to the message log.
    Open Trade opens the NPC trade modal via ``trade.open_npc_trade()``.
    """
    contacts = _scan_contacts(ctx, player_pos)
    if not contacts:
        ctx.log.add("No ships in comms range.")
        return None

    console = make_console()
    selected = 0

    # ---- Modal 1: contact list ----
    def _render_list() -> None:
        _render_comms_panel(console, contacts, selected)

    def _update_list(event) -> _CommsListOutcome:
        nonlocal selected
        if isinstance(event, tcod.event.Quit):
            return _CommsListOutcome.QUIT
        if not isinstance(event, tcod.event.KeyDown):
            return _CommsListOutcome.IGNORE
        sym_name: str = getattr(event.sym, 'name', '').lower()
        if event.sym in ui._ESCAPE_SYMS:
            return _CommsListOutcome.BACK
        if event.sym in ui._UP_SYMS or sym_name == 'k':
            selected = (selected - 1) % len(contacts)
            return _CommsListOutcome.IGNORE
        if event.sym in ui._DOWN_SYMS or sym_name == 'j':
            selected = (selected + 1) % len(contacts)
            return _CommsListOutcome.IGNORE
        if event.sym in ui._ENTER_SYMS:
            return _CommsListOutcome.HAIL
        return _CommsListOutcome.IGNORE

    list_outcome = ui.Modal(ctx.context, console).run(
        _render_list, _update_list,
    )
    if list_outcome is not _CommsListOutcome.HAIL:
        return None

    # ---- Modal 2: interaction with selected contact ----
    _contact_name, _contact_spec, _contact_entity = contacts[selected]
    _is_hostile = getattr(_contact_spec, 'faction', '') == 'pirate'

    _options: list[str] = ["End Transmission"]
    if _is_hostile:
        _options.insert(0, "Attack")
    else:
        _options.insert(0, "Open Trade")
        _options.insert(1, "Scan Cargo")

    _interaction_selected = 0

    def _render_interaction() -> None:
        _render_interaction_modal(
            console, _contact_name, _contact_spec,
            _options, _interaction_selected,
        )

    def _update_interaction(event) -> _InteractionOutcome:
        nonlocal _interaction_selected
        if isinstance(event, tcod.event.Quit):
            return _InteractionOutcome.QUIT
        if not isinstance(event, tcod.event.KeyDown):
            return _InteractionOutcome.IGNORE
        sym_name: str = getattr(event.sym, 'name', '').lower()
        if event.sym in ui._ESCAPE_SYMS:
            return _InteractionOutcome.BACK
        if event.sym in ui._UP_SYMS or sym_name == 'k':
            _interaction_selected = (_interaction_selected - 1) % len(_options)
            return _InteractionOutcome.IGNORE
        if event.sym in ui._DOWN_SYMS or sym_name == 'j':
            _interaction_selected = (_interaction_selected + 1) % len(_options)
            return _InteractionOutcome.IGNORE
        if event.sym in ui._ENTER_SYMS:
            chosen = _options[_interaction_selected]
            if chosen == "Open Trade":
                return _InteractionOutcome.TRADE
            elif chosen == "Attack":
                return _InteractionOutcome.ATTACK
            elif chosen == "Scan Cargo":
                return _InteractionOutcome.SCAN
            else:  # "End Transmission"
                return _InteractionOutcome.BACK
        return _InteractionOutcome.IGNORE

    interaction_outcome = ui.Modal(ctx.context, console).run(
        _render_interaction, _update_interaction,
    )

    # ---- Handle interaction outcome ----
    if interaction_outcome is _InteractionOutcome.ATTACK:
        ctx.log.add_colored(
            f"You open fire on the {_contact_name}!",
            _ml.COLOR_IMPORTANT_EVENT,
        )
        return ([_contact_spec], [_contact_entity.pos])

    elif interaction_outcome is _InteractionOutcome.SCAN:
        _goods = getattr(_contact_spec, 'cargo_goods', ())
        if _goods:
            _goods_str = ", ".join(
                str(g) for g in _goods
            )
            ctx.log.add(
                f"Cargo scan of {_contact_name}: {_goods_str}.",
            )
        else:
            ctx.log.add(
                f"Cargo scan of {_contact_name}: empty hold.",
            )
        return None

    elif interaction_outcome is _InteractionOutcome.TRADE:
        from .trade import open_npc_trade as _open_npc_trade
        _open_npc_trade(ctx, _contact_spec)
        return None

    else:  # BACK / QUIT / anything else
        return None
