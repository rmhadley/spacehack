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

def _sol_viewport(system, player_pos):
    """The on-screen rectangle (x, y, w, h) centred on the player."""
    from . import solar_system as _ss
    _w, _h = _ss.SOL_VIEW_W, _ss.SOL_VIEW_H
    return (
        max(0, min(player_pos.x - _w // 2, system.width - _w)),
        max(0, min(player_pos.y - _h // 2, system.height - _h)),
        _w, _h,
    )


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
    _cam_x, _cam_y, _view_w, _view_h = _sol_viewport(_system, player_pos)

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

def _contact_options(ctx, contact_spec) -> list[str]:
    """The action rows for one contact, by faction and attitude."""
    _contact_rep = ctx.faction_reputation.get(
        getattr(contact_spec, 'faction', ''), 0,
    )
    _attitude = _get_attitude(_contact_rep)
    if getattr(contact_spec, 'is_boardable', False):
        return ["End Transmission"]  # derelicts: nothing to say
    if getattr(contact_spec, 'id', '') == 'militia_blockade':
        return ["End Transmission"]  # restricted-space warning only
    if getattr(contact_spec, 'faction', '') == 'militia':
        return ["Allow Scan", "Flee", "Attack"]
    _options = ["Attack", "Scan Cargo"]
    if _attitude in ('neutral', 'liked', 'allied'):
        _options.insert(1, "Open Trade")
    _options.append("End Transmission")
    return _options


def _unprovoked_attack_rep(ctx, contact_spec) -> None:
    """Rep deltas for opening fire. Pirates only gain respect when the
    target is not pirate-aligned; lawful penalties always apply."""
    from .faction import modify_rep, _COMBAT_UNPROVOKED_DELTAS
    _target_faction = getattr(contact_spec, 'faction', '')
    for _fac, _delta in _COMBAT_UNPROVOKED_DELTAS.items():
        if _fac == 'pirate' and _delta > 0 and _target_faction == 'pirate':
            continue
        modify_rep(ctx, _fac, _delta)


def _squad_payload(ctx, contact_spec, contact_entity):
    """(specs, positions) for every ship that joins the fight.

    Pulls the contact's procedural squad AND its bounty/escort squad:
    every member carries bounty_squad_id (the leader's spawn id), so
    hailing ANY member and attacking draws the whole squad in.
    """
    specs, positions = _procedural_squadmates(ctx, contact_entity)
    _wing_specs, _wing_positions = _bounty_squadmates(ctx, contact_entity)
    return (
        [contact_spec] + specs + _wing_specs,
        [contact_entity.pos] + positions + _wing_positions,
    )


def _procedural_squadmates(ctx, contact_entity):
    """(specs, positions) for the contact's procedural squadmates."""
    _squad_id = getattr(contact_entity, 'procedural_squad_id', '')
    if not _squad_id:
        return [], []
    specs: list = []
    positions: list = []
    for _e in ctx.game_map.entities:
        if _e is contact_entity:
            continue
        if getattr(_e, 'procedural_squad_id', '') != _squad_id:
            continue
        _pid = getattr(_e, 'npc_ship_id', '')
        if not _pid:
            continue
        try:
            specs.append(_find_npc_ship(_pid))
        except (KeyError, ImportError):
            continue
        positions.append(_e.pos)
    return specs, positions


def _bounty_squadmates(ctx, contact_entity):
    """(specs, positions) for the contact's bounty/escort squad."""
    _squad_ref = (
        getattr(contact_entity, 'bounty_squad_id', None)
        or getattr(contact_entity, 'bounty_spawn_id', None)
    )
    if not _squad_ref:
        return [], []
    from . import solar_system as _ss
    _sys_id = getattr(_ss.current_system(), 'id', '')
    if not _sys_id:
        return [], []
    specs: list = []
    positions: list = []
    for _bs in ctx.bounty_spawns.get(_sys_id, []):
        if _bs.spawn_id != _squad_ref and _bs.squad_group_id != _squad_ref:
            continue
        if (_bs.pos.x == contact_entity.pos.x
                and _bs.pos.y == contact_entity.pos.y):
            continue  # already in payload as the contact
        try:
            specs.append(_find_npc_ship(_bs.enemy_id))
        except (KeyError, ImportError):
            continue
        positions.append(_bs.pos)
    return specs, positions


def _attempt_flee(ctx, contact_name, contact_spec, contact_entity):
    """Militia flee attempt: evade, or forced combat as an Attack."""
    from .navigation import _calc_flee_chance as _cfc
    from . import engine as _engine
    if _engine.RNG.random() < _cfc(ctx):
        ctx.log.add("You break line of sight and evade the patrol.")
        return None
    ctx.log.add_colored(
        "The militia patrol blocks your escape!",
        _ml.COLOR_IMPORTANT_EVENT,
    )
    _unprovoked_attack_rep(ctx, contact_spec)
    _combat_open_log(ctx, contact_name, contact_spec)
    return _squad_payload(ctx, contact_spec, contact_entity)


def _combat_open_log(ctx, contact_name, contact_spec) -> None:
    """Warning, the contact's reply, and the opening-fire lines."""
    ctx.log.add_colored(
        f"You transmit a warning to the {contact_name}.",
        _ml.COLOR_IMPORTANT_EVENT,
    )
    if getattr(contact_spec, 'comms_lines', None):
        ctx.log.add_colored(
            f"{contact_name}: \"{contact_spec.comms_lines[-1]}\"",
            _ml.COLOR_ENEMY_ACTION,
        )
    ctx.log.add_colored(
        f"You open fire on the {contact_name}!",
        _ml.COLOR_IMPORTANT_EVENT,
    )


def _run_interaction_modal(
    ctx: GameContext,
    console: FrameBuffer,
    contact_name: str,
    contact_spec: object,
    contact_entity: object,
) -> tuple[list, list] | None:
    """Run one contact's action modal. ``(specs, positions)`` for
    combat, ``None`` otherwise."""
    interaction_outcome = (
        _pygame_interaction_outcome(
            ctx, contact_name, contact_spec, _contact_options(ctx, contact_spec),
        )
        or _InteractionOutcome.BACK
    )
    return _handle_interaction(
        ctx, interaction_outcome, contact_name, contact_spec, contact_entity,
    )


def _handle_interaction(ctx, outcome, contact_name, contact_spec, contact_entity):
    """Resolve one chosen comms action (combat payload, or None)."""
    if outcome is _InteractionOutcome.ATTACK:
        _unprovoked_attack_rep(ctx, contact_spec)
        _combat_open_log(ctx, contact_name, contact_spec)
        return _squad_payload(ctx, contact_spec, contact_entity)

    if outcome is _InteractionOutcome.ALLOW_SCAN:
        from .navigation import _run_space_cargo_scan as _rscs
        _rscs(ctx)  # militia: player submits to the scan
        return None

    if outcome is _InteractionOutcome.FLEE:
        return _attempt_flee(ctx, contact_name, contact_spec, contact_entity)

    if outcome is _InteractionOutcome.SCAN:
        _goods = getattr(contact_spec, 'cargo_goods', ())
        _held = ", ".join(str(g) for g in _goods) if _goods else "empty hold"
        ctx.log.add(f"Cargo scan of {contact_name}: {_held}.")
        return None

    if outcome is _InteractionOutcome.TRADE:
        from .trade import open_npc_trade as _open_npc_trade
        _open_npc_trade(ctx, contact_spec)
        return None

    return None  # BACK / QUIT / anything else

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
