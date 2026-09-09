"""The Line (doc 41): Luyten's blockade as a sweep + checkpoint.

The BROADCAST SWEEP is a virtual sensor column: any hull crossing it
with a live or spoofed transponder is swept — identity reads at
range. Dark hulls are invisible to the sweep; only a Line picket
physically spotting them opens the checkpoint. One hail shape
everywhere: Comply (turn back) / Defy (the Line converges — phase 3
owns the full response; phase 1 sets a LINE-scoped interdiction flag
the spawn gate reads like charged-cell aggro: local, stance-
independent, no rep writes).

Crossing resolution reads IDENTITY only: the manifest trait waves, a
worn face at blockade rank waves as that ID, the service-run trait
waves and is consumed, everything else is hailed — allied standing
included (the doc-40 statics stand-down is superseded inside the
column only). The crossing edge is prev-x vs new-x inside the
movement pass; the tracker self-stamps from the position when
unknown, so every entry path (jump, load, materialization) stamps
naturally. Both session globals are deliberately NOT serialized:
the tripwire is edge-derived, and the flag resets on leaving the
system.
"""

from __future__ import annotations

from enum import Enum, auto

from . import identity
from . import message_log as _ml
from . import solar_system as solar_system_module
from .xp import has_trait

MANIFEST_TRAIT = "blockade_manifest"
SERVICE_TRAIT = "blockade_service_run"


class SweepVerdict(Enum):
    """One row of the sweep's rules table (doc 41)."""
    BLIND = auto()      # dark: the sweep cannot see the hull
    PAPERS = auto()     # manifest trait: waved through, logged
    RANK = auto()       # worn face at blockade rank: waved as that ID
    SERVICE = auto()    # service-run trait: waved through, consumed
    CHALLENGE = auto()  # unpapered: the checkpoint hail


class _Checkpoint(Enum):
    """The checkpoint modal's answers: Comply/Defy on the challenge
    (ruling 3 — binary), Acknowledge on the waves."""
    COMPLY = auto()
    DEFY = auto()
    ACK = auto()


_CHECKPOINT_DISPATCH = {
    "Comply": _Checkpoint.COMPLY,
    "Defy": _Checkpoint.DEFY,
}

_ACK_DISPATCH = {
    "Acknowledge": _Checkpoint.ACK,
}


def resolve_sweep(
    *, dark: bool, manifest: bool, face_militia_rep: int | None,
    service: bool, rank_rep: int,
) -> SweepVerdict:
    """Pure sweep table (doc 41): one crossing resolution.

    ``face_militia_rep`` is the worn false face's militia value, or
    None when no face is worn — the true hull's own standing is
    never rank (ruling 8: allied without papers turns back).
    """
    if dark:
        return SweepVerdict.BLIND
    _rows = (
        (manifest, SweepVerdict.PAPERS),
        (
            face_militia_rep is not None and face_militia_rep >= rank_rep,
            SweepVerdict.RANK,
        ),
        (service, SweepVerdict.SERVICE),
    )
    for _holds, _verdict in _rows:
        if _holds:
            return _verdict
    return SweepVerdict.CHALLENGE


# ---------------------------------------------------------------------------
# Session state (see module docstring — deliberately unsaved)
# ---------------------------------------------------------------------------

_prev_x: int | None = None
_interdiction_system: str | None = None


def reset_session() -> None:
    """New Game: clear the crossing tracker and any interdiction."""
    global _prev_x, _interdiction_system
    _prev_x = None
    _interdiction_system = None


def reset_interdiction() -> None:
    """Leaving the system: the Line's defiance does not follow."""
    global _interdiction_system
    _interdiction_system = None


def interdiction_system() -> str | None:
    """The system id where the Line was defied, or None."""
    return _interdiction_system


# ---------------------------------------------------------------------------
# The movement-pass check
# ---------------------------------------------------------------------------

def check_crossing(ctx, pos):
    """The movement pass's Line check (runs before the auto-comms
    warning; a hailed step skips that pass).

    None: nothing happened this step (no crossing, or a dark hull
    the sweep cannot see). ``(False, None)``: a wave — the all-clear
    comms ran, the player is through (GO TO continues).
    ``(True, payload | None)``: the challenge hail opened — the
    payload carries the converged squad on Defy.
    """
    global _prev_x
    system = solar_system_module.current_system()
    column = getattr(system, "sensor_column", None)
    if column is None:
        _prev_x = None
        return None
    crossed = _prev_x is not None and (_prev_x < column.x) != (pos.x < column.x)
    _prev_x = pos.x
    if not crossed:
        return None
    verdict = resolve_sweep(
        dark=identity.broadcast_mode(ctx) == identity.DARK,
        manifest=has_trait(ctx, MANIFEST_TRAIT),
        face_militia_rep=_worn_face_militia_rep(ctx),
        service=has_trait(ctx, SERVICE_TRAIT),
        rank_rep=column.rank_rep,
    )
    return _apply_verdict(ctx, column, system, verdict)


def _worn_face_militia_rep(ctx) -> int | None:
    """The worn false face's militia value, or None (live / no face).

    The true registration is not a face: its standing is exactly
    what ruling 8 turns back — only an impersonation reads for rank.
    """
    face = identity.resolved_identity(ctx)
    if face is None or face.get("kind", "true") == "true":
        return None
    return (face.get("rep") or {}).get("militia", 0)


def _checkpoint_address(ctx) -> str:
    """What the blockade calls the hull: the broadcast registration,
    or "Unidentified hull" when nothing resolves (dark)."""
    face = identity.resolved_identity(ctx)
    _id = (face or {}).get("id", "")
    return _id if _id else "Unidentified hull"


def _line_modal(ctx, column, lines, options, dispatch):
    """One comms-shaped Line modal — the checkpoint's single
    presentation; returns the player's reply. The column's message
    templates carry an ``{id}`` placeholder for the address."""
    from . import comms
    return comms._pygame_interaction_outcome(
        ctx, column.label, None, options,
        contact_entity=None, dispatch=dispatch, title="Hailing",
        lines=tuple(
            line.format(id=_checkpoint_address(ctx)) for line in lines
        ),
    )


def _current_column():
    """The active system's sensor column, or None."""
    system = solar_system_module.current_system()
    return getattr(system, "sensor_column", None)


def _wave_through(ctx, lines) -> tuple[bool, None]:
    """A waved crossing: the blockade's all-clear comms (one
    Acknowledge option; ESC counts), then a terse log line.
    ``(False, None)`` — the player is through; GO TO continues."""
    _line_modal(ctx, _current_column(), lines, ("Acknowledge",), _ACK_DISPATCH)
    ctx.log.add("The blockade waves you through.")
    return (False, None)


def _wave_papers(ctx, column, system):
    return _wave_through(ctx, column.manifest_lines or column.hail_lines)


def _wave_rank(ctx, column, system):
    return _wave_through(ctx, column.rank_lines or column.hail_lines)


def _wave_service(ctx, column, system):
    _wave_through(ctx, column.service_lines or column.hail_lines)
    if has_trait(ctx, SERVICE_TRAIT):
        ctx.player_traits.remove(SERVICE_TRAIT)
    ctx.log.add("The service-run contract is spent.")
    return (False, None)


# ---------------------------------------------------------------------------
# The checkpoint (one hail shape everywhere — ruling 3)
# ---------------------------------------------------------------------------

def _run_checkpoint(ctx, column, system):
    """The hail: Comply = turn back, Defy = converge. ESC/window-
    close is Defy — refusing the conversation is an answer too
    (doc-40 precedent)."""
    outcome = _line_modal(
        ctx, column, column.hail_lines, ("Comply", "Defy"),
        _CHECKPOINT_DISPATCH,
    )
    if outcome is _Checkpoint.COMPLY:
        ctx.log.add_colored(
            "You turn back from the blockade.",
            _ml.COLOR_IMPORTANT_EVENT,
        )
        return (True, None)
    global _interdiction_system
    _interdiction_system = getattr(system, "id", "")
    ctx.log.add_colored(
        "The blockade's targeting lasers focus on you!",
        _ml.COLOR_COMBAT_EVENT,
    )
    payload = _picket_payload(ctx, column, system)
    if not payload[0]:
        return (True, None)  # squad dead: the flag's patrols carry it
    return (True, payload)


def _picket_payload(ctx, column, system):
    """(specs, positions) for every alive picket on the Line."""
    from .data.npc_ships import find_npc_ship
    from .navigation_combat import _alive_entity_at
    specs: list = []
    positions: list = []
    for _spawn in getattr(system, "enemies", ()) or ():
        if _spawn.squad_id != column.squad_id:
            continue
        if not _alive_entity_at(ctx, _spawn.pos):
            continue
        try:
            specs.append(find_npc_ship(_spawn.enemy_id))
        except KeyError:
            continue
        positions.append(_spawn.pos)
    return (specs, positions)


_HANDLERS = {
    SweepVerdict.PAPERS: _wave_papers,
    SweepVerdict.RANK: _wave_rank,
    SweepVerdict.SERVICE: _wave_service,
    SweepVerdict.CHALLENGE: _run_checkpoint,
}


def _apply_verdict(ctx, column, system, verdict):
    """Dispatch one sweep verdict in ``check_crossing``'s shape."""
    if verdict is SweepVerdict.BLIND:
        return None
    return _HANDLERS[verdict](ctx, column, system)


def line_dark_hail(ctx, entity):
    """The in-column dark-spot hail, or None when the spotter is not
    a Line picket (the doc-40 challenge stands there). The Line's
    cruisers are the only hulls of their id, so the spotter names
    the column."""
    system = solar_system_module.current_system()
    column = getattr(system, "sensor_column", None)
    if (
        column is None
        or getattr(entity, "npc_ship_id", "") != column.picket_enemy_id
    ):
        return None
    return _run_checkpoint(ctx, column, system)


def column_supersedes_warning() -> bool:
    """True in a column system: the checkpoint is the only hail the
    Line gives — the doc-39 warning-only comms are superseded at the
    column (waved hulls included; ruling 3's one hail shape)."""
    system = solar_system_module.current_system()
    return getattr(system, "sensor_column", None) is not None
