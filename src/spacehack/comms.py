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
    IDENTIFY = auto()    # dark-hull challenge: answer with a broadcast
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

# The dark-hull challenge: TWO options only, no run (doc 40 ruling).
_CHALLENGE_DISPATCH = {
    "Identify": _InteractionOutcome.IDENTIFY,
    "Attack": _InteractionOutcome.ATTACK,
}

def _contact_broadcast_line(contact_entity):
    """One line naming what the contact broadcasts (doc 40: NPCs
    broadcast; the hail shows who claims to be on the other end)."""
    from . import identity
    _identity = identity.npc_identity(contact_entity)
    if _identity is None:
        return ""
    _faction = _identity.get("faction") or "independent"
    return f"Broadcast: {_identity['id']} - {_faction}"
def _hail_frames(
    ctx, contact_name, contact_spec, options, contact_entity,
    *, title="Hailing", esc_label="ESC back", lines=None,
):
    """One MenuFrame per selectable index for a contact hail."""
    from . import pygame_menu, pygame_ui

    items = tuple(
        pygame_menu.MenuItem(option, "Select this transmission action.", option)
        for option in options
    )
    _broadcast = _contact_broadcast_line(contact_entity)
    if lines is None:
        lines = getattr(contact_spec, "comms_lines", ()) or ("...",)
    _body = "\n".join(lines)
    if _broadcast:
        _body = f"{_broadcast}\n{_body}"
    return tuple(
        pygame_menu.MenuFrame(
            title=f"{contact_name} - {title}",
            body=_body,
            items=items,
            hints=(pygame_ui.modal_hint(
                pygame_ui.NAV_HINT, "ENTER select", esc_label,
                pygame_ui.GUIDE_HINT,
            ),),
            selected=index,
        )
        for index in range(max(1, len(items)))
    )


def _pygame_interaction_outcome(
    ctx, contact_name, contact_spec, options, contact_entity=None,
    *, dispatch=None, title="Hailing", esc_label="ESC back", lines=None,
):
    """Return a Pygame-selected interaction enum, or None for fallback."""
    from . import pygame_menu
    if dispatch is None:
        dispatch = _INTERACTION_DISPATCH

    _frames = _hail_frames(
        ctx, contact_name, contact_spec, options, contact_entity,
        title=title, esc_label=esc_label, lines=lines,
    )
    outcome, action, _selected = pygame_menu.run_for_context(
        ctx.context,
        _frames,
        caption=f"spacehack - {contact_name}",
    )
    if outcome == "GUIDE":
        from .help import _open_context_guide
        _open_context_guide(ctx, "NPCs & Factions")
        return _pygame_interaction_outcome(
            ctx, contact_name, contact_spec, options, contact_entity,
            dispatch=dispatch, title=title, esc_label=esc_label, lines=lines,
        )
    if outcome == "QUIT":
        return _InteractionOutcome.QUIT
    if outcome != "SELECT" or not action:
        return _InteractionOutcome.BACK
    return dispatch.get(action)



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
            contact_entity=contact_entity,
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
# Dark-hull challenge (doc 40 3b): a militia ship spotted a dark hull
# ---------------------------------------------------------------------------


def _judge_identification(ctx, face):
    """Pure: what a militia reader resolves from the identify answer.

    ``face`` None = the true registration (ID 1's sheet); an offered
    ID is judged by its OWN sheet's militia value (doc 40: the ID is
    the record). Returns ``(passed, line)``: every pass reads the
    same — the patrol checks the registration and waves the hull
    through. A hostile sheet draws fire, whatever hull it rides.
    """
    _PASS_LINE = "The patrol checks your registration and waves you through."
    sheet = ctx.faction_reputation if face is None else (face.get("rep") or {})
    if _get_attitude((sheet or {}).get("militia", 0)) in ("enemy", "disliked"):
        return (False, "The registration reads hostile: the patrol opens fire!")
    return (True, _PASS_LINE)


def resolve_identification(ctx, face):
    """Apply the identify answer: the transponder comes up broadcasting
    it (dark ends — you fly what you answered as) and the patrol judges
    exactly that. Returns True when the hull is waved through."""
    ctx.broadcast_dark = False
    ctx.broadcast_identity = dict(face) if face is not None else None
    _passed, _line = _judge_identification(ctx, face)
    ctx.log.add_colored(_line, _ml.COLOR_IMPORTANT_EVENT)
    return _passed


def _identify_face_frames(ctx):
    """MenuFrames for the identify face-choice: true registration plus
    every collected ID."""
    from . import pygame_menu, pygame_ui

    rows = [("TRUE", "Your true registration")]
    for _i, _entry in enumerate(ctx.collected_ids or ()):
        rows.append(
            (f"FACE:{_i}", f"{_entry.get('label', 'ID')} {_entry.get('id', '??')}")
        )
    items = tuple(
        pygame_menu.MenuItem(label, "Pick what the transponder broadcasts.", action)
        for action, label in rows
    )
    return tuple(
        pygame_menu.MenuFrame(
            title="Identify yourself",
            body="The transponder comes up.",
            items=items,
            hints=(pygame_ui.modal_hint(
                pygame_ui.NAV_HINT, "ENTER select", "ESC refuse",
                pygame_ui.GUIDE_HINT,
            ),),
            selected=index,
        )
        for index in range(len(items))
    )


def _identify_face_result(ctx):
    """Run the identify face-choice modal. Returns ``('true', None)``,
    ``('face', entry)``, or ``('silent', None)`` when the player
    refuses to answer."""
    from . import pygame_menu

    outcome, action, _selected = pygame_menu.run_for_context(
        ctx.context, _identify_face_frames(ctx), caption="spacehack - identify",
    )
    if outcome == "GUIDE":
        from .help import _open_context_guide
        _open_context_guide(ctx, "Identity & Transponder")
        return _identify_face_result(ctx)
    if outcome != "SELECT" or not action:
        return ("silent", None)
    if action == "TRUE":
        return ("true", None)
    try:
        return ("face", (ctx.collected_ids or ())[int(action.split(":", 1)[1])])
    except (ValueError, IndexError):
        return ("silent", None)


def _identify_choice(ctx):
    """The identify answer: ``('true', None)``, ``('face', entry)``, or
    ``('silent', None)``. No library means only yourself to offer."""
    if not getattr(ctx, "collected_ids", None):
        return ("true", None)
    return _identify_face_result(ctx)


def _handle_challenge(ctx, outcome, contact_name, contact_spec, contact_entity):
    """Resolve one challenge answer. ``(specs, positions)`` for combat
    (the patrol opens fire), ``None`` when the hull is waved through."""
    if outcome is _InteractionOutcome.ATTACK:
        return _handle_interaction(
            ctx, outcome, contact_name, contact_spec, contact_entity,
        )
    _passed = False
    _answered = _identify_choice(ctx) if outcome is _InteractionOutcome.IDENTIFY else ("silent", None)
    if _answered[0] == "silent":
        # BACK / QUIT / silence: refusing the conversation is an answer
        # too — there is no run (doc 40 ruling).
        ctx.log.add_colored(
            "No answer comes from the dark hull.",
            _ml.COLOR_IMPORTANT_EVENT,
        )
    else:
        _passed = resolve_identification(ctx, _answered[1])
    if not _passed:
        ctx.log.add_colored(
            f"The {contact_name} opens fire!",
            _ml.COLOR_COMBAT_EVENT,
        )
        return _squad_payload(ctx, contact_spec, contact_entity)
    return None

# ---------------------------------------------------------------------------
# Direct comms (skip contact list, hail a specific entity)
# ---------------------------------------------------------------------------

def _resolve_contact(entity):
    """``(name, spec)`` for an NPC entity, or None when not resolvable."""
    _pid = getattr(entity, 'npc_ship_id', '')
    if not _pid:
        return None
    try:
        _spec = _find_npc_ship(_pid)
    except (KeyError, ImportError):
        return None
    return getattr(entity, 'name', '') or _spec.name, _spec


def open_comms_direct(
    ctx: GameContext,
    entity: object,
) -> tuple[list, list] | None:
    """Open comms directly with a specific entity, skipping the contact
    list. Used by auto-hail so the player sees the hailing ship's
    message immediately without selecting from a list.
    """
    _resolved = _resolve_contact(entity)
    if _resolved is None:
        return None
    _name, _spec = _resolved
    console = make_console()
    return _run_interaction_modal(ctx, console, _name, _spec, entity)


def _challenge_body_lines(spec):
    """Pure: the challenge modal body — the ship's authored
    ``challenge_lines``, else the generic dark-hull demand. Never the
    cargo-inspection ``comms_lines``."""
    return (
        getattr(spec, "challenge_lines", ())
        or ("Contact: your transponder is dark. Identify yourself or we open fire.",)
    )


def open_challenge_direct(ctx, entity) -> tuple[list, list] | None:
    """The dark-hull challenge (doc 40 3b): NPC-initiated comms with
    TWO options — Identify / Attack; no run. Backing out is refusing
    to answer, and the patrol opens fire on silence.
    """
    _resolved = _resolve_contact(entity)
    if _resolved is None:
        return None
    _name, _spec = _resolved
    _outcome = _pygame_interaction_outcome(
        ctx, _name, _spec, ("Identify", "Attack"),
        contact_entity=entity,
        dispatch=_CHALLENGE_DISPATCH,
        title="Challenge", esc_label="ESC refuse",
        lines=_challenge_body_lines(_spec),
    )
    return _handle_challenge(
        ctx, _outcome or _InteractionOutcome.BACK, _name, _spec, entity,
    )

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
