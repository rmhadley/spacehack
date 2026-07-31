"""Player-initiated comms with NPC ships in space.

Press ``T`` in space mode to open the comms panel, which scans for
NPC ships within ``comms_range`` (default 15 cells) and lets the
player hail them for interaction (trade, cargo scan, attack, or
end transmission).

Faction-aware: enemy and disliked factions show ``(hostile)`` tags.
Trade is only available for neutral+ attitudes.  "Scan Cargo" is
always available.  "Attack" is always available.
"""

from __future__ import annotations

import math
from enum import Enum, auto

import tcod.console
import tcod.event

from . import ui
from .faction import get_attitude as _get_attitude
from .data.npc_ships import find_npc_ship as _find_npc_ship
from .engine import SCREEN_HEIGHT, SCREEN_WIDTH, make_console
from .game_context import GameContext
from . import message_log as _ml
from .input_helpers import _try_open_guide


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
        contacts.append((getattr(_e, 'name', '') or _spec.name, _spec, _e))
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

# Colour constants — all imported from ui.py to avoid duplication.
_CONTACTS_TITLE_COLOR = ui.COLOR_TITLE
_CONTACTS_FLAVOR = ui.COLOR_DESCRIPTION
_CONTACTS_DIM = ui.COLOR_VALUE_DIM

_INTERACTION_TITLE = ui.COLOR_TITLE
_INTERACTION_FLAVOR = ui.COLOR_DESCRIPTION
_INTERACTION_OPTION = ui.COLOR_OPTION
_INTERACTION_HIGHLIGHT = ui.COLOR_OPTION_HIGHLIGHT
_INTERACTION_INSTRUCTION = ui.COLOR_INSTRUCTION


def _render_comms_panel(
    console: tcod.console.Console,
    contacts: list[tuple[str, object, object]],
    selected: int,
    ctx,
) -> None:
    """Paint the comms contact-list panel via :func:`ui.render_selectable_list`.

    Attitude suffix (``(hostile)``) is baked into the contact name so
    the standard list renderer works without per-row color overrides.
    ``ctx`` is needed for faction reputation lookups.
    """
    console.clear()
    n = len(contacts)
    title = f"COMMS — {n} contact{('' if n == 1 else 's')} in range"

    # Build items with suffix baked in, flavor text as description.
    _items: list[tuple[str, str]] = []
    for name, spec, _entity in contacts:
        _rep = ctx.faction_reputation.get(spec.faction, 0)
        _attitude = _get_attitude(_rep)
        _display_name = f"{name} (hostile)" if _attitude in ('enemy', 'disliked') else name
        _flavor = spec.comms_lines[0] if spec.comms_lines else "..."
        _items.append((_display_name, _flavor))

    ui.render_selectable_list(
        console, SCREEN_WIDTH, SCREEN_HEIGHT,
        title=title,
        items=_items,
        selected=selected,
        col_x=SCREEN_WIDTH // 4,
        title_y=SCREEN_HEIGHT // 4,
        title_fg=_CONTACTS_TITLE_COLOR,
        row_spacing=3,
        item_fg_selected=ui.COLOR_OPTION_HIGHLIGHT,
        item_fg_normal=ui.COLOR_OPTION,
        desc_fg_selected=_CONTACTS_FLAVOR,
        desc_fg_normal=_CONTACTS_DIM,
        hint="UP/DOWN / j,k navigate - ENTER hail - ESC close",
        hint_fg=_INTERACTION_INSTRUCTION,
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
# Interaction sub-modal (shared between open_comms and open_comms_direct)
# ---------------------------------------------------------------------------

def _run_interaction_modal(
    ctx: GameContext,
    console: tcod.console.Console,
    contact_name: str,
    contact_spec: object,
    contact_entity: object,
) -> tuple[list, list] | None:
    """Run the interaction sub-modal for a single contact and return
    the outcome.

    Skips the contact-list modal and goes straight to displaying
    the contact's comms lines (flavor text) with action options.

    Returns ``(specs, positions)`` if the player chose **Attack**,
    or ``None`` if they chose End Transmission, Open Trade, Scan
    Cargo, or ESC.
    """
    _contact_rep = ctx.faction_reputation.get(
        getattr(contact_spec, 'faction', ''), 0,
    )
    _contact_attitude = _get_attitude(_contact_rep)

    # Derelict/boardable ships: only "End Transmission" makes sense.
    # No crew to trade with, no cargo to scan, no point attacking a wreck.
    if getattr(contact_spec, 'is_boardable', False):
        _options: list[str] = ["End Transmission"]
    else:
        _options: list[str] = ["Attack", "Scan Cargo"]
        # Trade only available for neutral+ attitudes.
        if _contact_attitude in ('neutral', 'liked', 'allied'):
            _options.insert(1, "Open Trade")
        # End Transmission always last.
        _options.append("End Transmission")

    _interaction_selected = 0

    def _render_interaction() -> None:
        _render_interaction_modal(
            console, contact_name, contact_spec,
            _options, _interaction_selected,
        )

    def _update_interaction(event) -> _InteractionOutcome:
        nonlocal _interaction_selected
        if _try_open_guide(event, ctx):
            return _InteractionOutcome.IGNORE
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
        # Apply unprovoked attack rep penalty before combat starts.
        # Pirates only get +2 if the target is NOT pirate-aligned
        # (attacking their enemies earns respect; attacking their
        # own does not). Lawful faction penalties always apply.
        from .faction import modify_rep, _COMBAT_UNPROVOKED_DELTAS
        _target_faction = getattr(contact_spec, 'faction', '')
        for _fac, _delta in _COMBAT_UNPROVOKED_DELTAS.items():
            if _fac == 'pirate' and _delta > 0 and _target_faction == 'pirate':
                continue
            modify_rep(ctx, _fac, _delta)

        ctx.log.add_colored(
            f"You transmit a warning to the {contact_name}.",
            _ml.COLOR_IMPORTANT_EVENT,
        )
        if getattr(contact_spec, 'comms_lines', None):
            _reply = contact_spec.comms_lines[-1]
            ctx.log.add_colored(
                f"{contact_name}: \"{_reply}\"",
                _ml.COLOR_ENEMY_ACTION,
            )
        ctx.log.add_colored(
            f"You open fire on the {contact_name}!",
            _ml.COLOR_IMPORTANT_EVENT,
        )
        # Look up the contacted ship's squad and include ALL members.
        _squad_id = getattr(contact_entity, 'procedural_squad_id', '')
        _attack_specs: list = [contact_spec]
        _attack_positions: list = [contact_entity.pos]
        if _squad_id:
            for _e in ctx.game_map.entities:
                if _e is contact_entity:
                    continue
                if getattr(_e, 'procedural_squad_id', '') != _squad_id:
                    continue
                _pid = getattr(_e, 'npc_ship_id', '')
                if not _pid:
                    continue
                try:
                    _spec = _find_npc_ship(_pid)
                except (KeyError, ImportError):
                    continue
                _attack_specs.append(_spec)
                _attack_positions.append(_e.pos)
        # Also include bounty squad wingmates (tagged via BountySpawn).
        _bounty_id = getattr(contact_entity, 'bounty_spawn_id', None)
        if _bounty_id:
            from . import solar_system as _ss
            _sys_id = getattr(_ss.current_system(), 'id', '')
            if _sys_id:
                for _bs in ctx.bounty_spawns.get(_sys_id, []):
                    if _bs.squad_group_id == _bounty_id:
                        try:
                            _wing_spec = _find_npc_ship(_bs.enemy_id)
                        except (KeyError, ImportError):
                            continue
                        _attack_specs.append(_wing_spec)
                        _attack_positions.append(_bs.pos)
        return (_attack_specs, _attack_positions)

    elif interaction_outcome is _InteractionOutcome.SCAN:
        _goods = getattr(contact_spec, 'cargo_goods', ())
        if _goods:
            _goods_str = ", ".join(str(g) for g in _goods)
            ctx.log.add(f"Cargo scan of {contact_name}: {_goods_str}.")
        else:
            ctx.log.add(f"Cargo scan of {contact_name}: empty hold.")
        return None

    elif interaction_outcome is _InteractionOutcome.TRADE:
        from .trade import open_npc_trade as _open_npc_trade
        _open_npc_trade(ctx, contact_spec)
        return None

    else:  # BACK / QUIT / anything else
        return None


# ---------------------------------------------------------------------------
# Direct comms (skip contact list, hail a specific entity)
# ---------------------------------------------------------------------------

def open_comms_direct(
    ctx: GameContext,
    entity: object,
) -> tuple[list, list] | None:
    """Open comms directly with a specific entity, skipping the contact
    list. Used by auto-hail so the player sees the hailing ship's
    message immediately without selecting from a list.
    """
    _pid = getattr(entity, 'npc_ship_id', '')
    if not _pid:
        return None
    try:
        _spec = _find_npc_ship(_pid)
    except (KeyError, ImportError):
        return None
    _name = getattr(entity, 'name', '') or _spec.name
    console = make_console()
    return _run_interaction_modal(ctx, console, _name, _spec, entity)


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
        _render_comms_panel(console, contacts, selected, ctx)

    def _update_list(event) -> _CommsListOutcome:
        nonlocal selected
        if _try_open_guide(event, ctx):
            return _CommsListOutcome.IGNORE
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
    return _run_interaction_modal(
        ctx, console, _contact_name, _contact_spec, _contact_entity,
    )
