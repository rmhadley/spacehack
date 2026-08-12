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

from .framebuffer import FrameBuffer
from .faction import get_attitude as _get_attitude
from .data.npc_ships import find_npc_ship as _find_npc_ship
from .engine import make_console
from .game_context import GameContext
from . import message_log as _ml

class _InteractionOutcome(Enum):
    """Outcome for the per-contact interaction sub-modal."""
    IGNORE = auto()
    TRADE = auto()
    ATTACK = auto()
    SCAN = auto()
    ALLOW_SCAN = auto()  # militia: submit to cargo scan
    FLEE = auto()        # militia: attempt to flee the patrol
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

_INTERACTION_DISPATCH = {
    "Open Trade": _InteractionOutcome.TRADE,
    "Attack": _InteractionOutcome.ATTACK,
    "Scan Cargo": _InteractionOutcome.SCAN,
    "Allow Scan": _InteractionOutcome.ALLOW_SCAN,
    "Flee": _InteractionOutcome.FLEE,
    "End Transmission": _InteractionOutcome.BACK,
}

def _pygame_interaction_outcome(ctx, contact_name, contact_spec, options):
    """Return a Pygame-selected interaction enum, or None for fallback."""
    from . import pygame_menu, pygame_ui

    items = tuple(
        pygame_menu.MenuItem(option, "Select this transmission action.", option)
        for option in options
    )
    frames = tuple(
        pygame_menu.MenuFrame(
            title=f"{contact_name} - Hailing",
            body="\n".join(getattr(contact_spec, "comms_lines", ()) or ("...",)),
            items=items,
            hints=(pygame_ui.modal_hint(
                pygame_ui.NAV_HINT, "ENTER select", "ESC back",
                pygame_ui.GUIDE_HINT,
            ),),
            selected=index,
        )
        for index in range(max(1, len(items)))
    )
    outcome, action, _selected = pygame_menu.run_for_context(
        ctx.context,
        frames,
        caption=f"spacehack - {contact_name}",
    )
    if outcome == "GUIDE":
        from .help import _open_context_guide
        _open_context_guide(ctx, "NPCs & Factions")
        return _pygame_interaction_outcome(ctx, contact_name, contact_spec, options)
    if outcome == "QUIT":
        return _InteractionOutcome.QUIT
    if outcome != "SELECT":
        return _InteractionOutcome.BACK
    return _INTERACTION_DISPATCH.get(action)

# ---------------------------------------------------------------------------
# Interaction sub-modal (shared between open_comms and open_comms_direct)
# ---------------------------------------------------------------------------

def _run_interaction_modal(
    ctx: GameContext,
    console: FrameBuffer,
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
    _is_militia = getattr(contact_spec, 'faction', '') == 'militia'
    _is_blockade = getattr(contact_spec, 'id', '') == 'militia_blockade'

    # Derelict/boardable ships: only "End Transmission" makes sense.
    if getattr(contact_spec, 'is_boardable', False):
        _options: list[str] = ["End Transmission"]
    # Militia blockade: warning only — you are approaching restricted space.
    elif _is_blockade:
        _options: list[str] = ["End Transmission"]
    elif _is_militia:
        # Militia patrol: Allow Scan / Flee / Attack (no End Transmission).
        _options: list[str] = ["Allow Scan", "Flee", "Attack"]
    else:
        _options: list[str] = ["Attack", "Scan Cargo"]
        # Trade only available for neutral+ attitudes.
        if _contact_attitude in ('neutral', 'liked', 'allied'):
            _options.insert(1, "Open Trade")
        # End Transmission always last.
        _options.append("End Transmission")

    interaction_outcome = (
        _pygame_interaction_outcome(ctx, contact_name, contact_spec, _options)
        or _InteractionOutcome.BACK
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
        # Also include the contacted ship's bounty/escort squad. Every
        # squad member carries bounty_squad_id (the leader's spawn id),
        # so hailing ANY member — merchant leader OR pirate escort —
        # and attacking pulls the whole squad into combat.
        _squad_ref = (
            getattr(contact_entity, 'bounty_squad_id', None)
            or getattr(contact_entity, 'bounty_spawn_id', None)
        )
        if _squad_ref:
            from . import solar_system as _ss
            _sys_id = getattr(_ss.current_system(), 'id', '')
            if _sys_id:
                for _bs in ctx.bounty_spawns.get(_sys_id, []):
                    if _bs.spawn_id != _squad_ref and _bs.squad_group_id != _squad_ref:
                        continue
                    if (_bs.pos.x == contact_entity.pos.x
                            and _bs.pos.y == contact_entity.pos.y):
                        continue  # already in payload as the contact
                    try:
                        _wing_spec = _find_npc_ship(_bs.enemy_id)
                    except (KeyError, ImportError):
                        continue
                    _attack_specs.append(_wing_spec)
                    _attack_positions.append(_bs.pos)
        return (_attack_specs, _attack_positions)

    elif interaction_outcome is _InteractionOutcome.ALLOW_SCAN:
        # Militia: player submits to a cargo scan.
        from .navigation import _run_space_cargo_scan as _rscs
        _rscs(ctx)
        return None

    elif interaction_outcome is _InteractionOutcome.FLEE:
        # Militia: player attempts to flee the patrol.
        from .navigation import _calc_flee_chance as _cfc
        from . import engine as _engine
        _chance = _cfc(ctx)
        if _engine.RNG.random() < _chance:
            ctx.log.add("You break line of sight and evade the patrol.")
            return None
        # Failed flee → forced combat (same squad resolution as Attack).
        ctx.log.add_colored(
            "The militia patrol blocks your escape!",
            _ml.COLOR_IMPORTANT_EVENT,
        )
        from .faction import modify_rep, _COMBAT_UNPROVOKED_DELTAS
        _target_faction = getattr(contact_spec, 'faction', '')
        for _fac, _delta in _COMBAT_UNPROVOKED_DELTAS.items():
            if _fac == 'pirate' and _delta > 0 and _target_faction == 'pirate':
                continue
            modify_rep(ctx, _fac, _delta)
        ctx.log.add_colored(
            f"You open fire on the {contact_name}!",
            _ml.COLOR_IMPORTANT_EVENT,
        )
        # Resolve full squad (same logic as Attack handler).
        _squad_id = getattr(contact_entity, 'procedural_squad_id', '')
        _attack_specs: list = [contact_spec]
        _attack_positions: list = [contact_entity.pos]
        if _squad_id:
            for _e in ctx.game_map.entities:
                if _e is contact_entity:
                    continue
                if getattr(_e, 'procedural_squad_id', '') != _squad_id:
                    continue
                _epid = getattr(_e, 'npc_ship_id', '')
                if not _epid:
                    continue
                try:
                    _espec = _find_npc_ship(_epid)
                except (KeyError, ImportError):
                    continue
                _attack_specs.append(_espec)
                _attack_positions.append(_e.pos)
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

def _pygame_contact_result(ctx, contacts):
    """Run the contact list through Pygame and return selected contact."""
    from . import pygame_menu, pygame_ui

    items = tuple(
        pygame_menu.MenuItem(
            f"{name} (hostile)" if _get_attitude(ctx.faction_reputation.get(spec.faction, 0)) in ("enemy", "disliked") else name,
            spec.comms_lines[0] if spec.comms_lines else "...",
            f"CONTACT:{index}",
        )
        for index, (name, spec, _entity) in enumerate(contacts)
    )
    frames = tuple(
        pygame_menu.MenuFrame(
            f"COMMS - {len(contacts)} contacts in range",
            "Select a ship to hail.", items,
            (pygame_ui.modal_hint(
                pygame_ui.NAV_HINT, "ENTER hail", "ESC close",
                pygame_ui.GUIDE_HINT,
            ),), selected,
        )
        for selected in range(max(1, len(items)))
    )
    outcome, action, selected = pygame_menu.run_for_context(
        ctx.context,
        frames,
        caption="spacehack - comms",
    )
    if outcome == "GUIDE":
        from .help import _open_context_guide
        _open_context_guide(ctx, "NPCs & Factions")
        return _pygame_contact_result(ctx, contacts)
    if outcome == "QUIT":
        return "QUIT"
    if outcome != "SELECT" or not action.startswith("CONTACT:"):
        return "BACK"
    try:
        return contacts[int(action.split(":", 1)[1])]
    except (ValueError, IndexError):
        return None

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

    _pygame_contact = _pygame_contact_result(ctx, contacts)
    # Tuple membership (== comparison, no hashing): a selected contact is
    # a ``(name, spec, entity)`` tuple whose ``entity`` is an unhashable
    # ``world.Entity`` — a set lookup would raise ``TypeError``.
    if _pygame_contact in ("QUIT", "BACK", None):
        return None
    _contact_name, _contact_spec, _contact_entity = _pygame_contact
    return _run_interaction_modal(
        ctx, make_console(), _contact_name, _contact_spec, _contact_entity,
    )
