"""The Line (doc 41): Luyten's blockade as a sweep + checkpoint +
a manned watch.

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

THE WATCH (phase 2): the pickets rotate on 7-day shifts driven by
the SensorColumn's watchbill — everything derives from the day
clock (total_days → tenure → kind → roster), so there is NO
schedule state anywhere. Rotation spawns stamp their keys with a
monotonic ``:t<tenure>`` suffix so the phase-1 tombstones hold per
tenure. Reliefs launch early at their base, fly in (riding the
existing path dicts keyed by spawn key — dropped at save by the
procedural-sync, so flights are session-scoped by construction),
park for the shift, then fly home at the boundary and land.
Displaced pickets are never given a target — they serve until
destroyed. All line traffic is SILENT (no log lines) and carries
no squad id (never enters the patrol machinery).
"""

from __future__ import annotations

from enum import Enum, auto

from . import identity
from . import message_log as _ml
from . import solar_system as solar_system_module
from . import world
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
# The watchbill (doc 41 phase 2) — pure derivations from the clock
# ---------------------------------------------------------------------------

def total_days(day: int, month: int, year: int) -> int:
    """The wrapping clock triple as one monotonic day number.

    ``year*360 + (month-1)*30 + day`` — months are 30 days, years
    12 months, so the derivation is dense (no gaps at wraps).
    Every watch schedule decision reads this, never the triple.
    """
    return year * 360 + (month - 1) * 30 + day


# The watchbill's epoch: the game's first day. A 360-day year is
# not divisible by 7, so raw total_days would drift the shift
# boundaries off the doc's days 8/15/22 — tenure counts from HERE.
_EPOCH_DAY = total_days(day=1, month=1, year=2200)


def clock_total(ctx) -> int:
    """``total_days`` off a ctx (lightweight doubles stay valid)."""
    return total_days(
        getattr(ctx, "time_day", 1),
        getattr(ctx, "time_month", 1),
        getattr(ctx, "time_year", 2200),
    )


def tenure_of(total: int, shift_days: int) -> int:
    """Which shift owns ``total``: boundaries land on days 8, 15, 22…
    (epoch-anchored — tenure 0 is the game's first week)."""
    return (total - _EPOCH_DAY) // shift_days


def tenure_start(tenure: int, shift_days: int) -> int:
    """The first day of ``tenure`` (the boundary it launches toward)."""
    return _EPOCH_DAY + tenure * shift_days


def watch_kind(tenure: int, watch_cycle: tuple[str, ...]) -> str:
    """The watch kind serving ``tenure`` (cycling data)."""
    return watch_cycle[tenure % len(watch_cycle)]


def station_launch_day(tenure: int, station, shift_days: int) -> int:
    """The day ``tenure``'s relief for ``station`` leaves its base —
    its lead before the boundary, so it arrives ≈ shift end."""
    return tenure_start(tenure, shift_days) - station.lead_days


def tenure_key(base_key: str, tenure: int) -> str:
    """The rotation-stamped spawn key: ``…:x:y:t<tenure>``. Monotonic
    per station, so a tombstone holds for its tenure and the post
    re-mans at the next boundary."""
    return f"{base_key}:t{tenure}"


def parse_tenure_key(key: str) -> tuple[tuple[int, int], int] | None:
    """``((x, y), tenure)`` from a tenure-stamped key, else None.

    The station is embedded in the key itself — a picket's own
    post is readable from wherever it currently stands.
    """
    _stem, _sep, _last = key.rpartition(":")
    if not _sep or not _last.startswith("t") or not _last[1:].isdigit():
        return None
    _enemy_x, _sep_y, _y = _stem.rpartition(":")
    _sys_enemy, _sep_x, _x = _enemy_x.rpartition(":")
    if not (_sep_y and _sep_x and _x.isdigit() and _y.isdigit()):
        return None
    return ((int(_x), int(_y)), int(_last[1:]))


def watch_active(column) -> bool:
    """True when the column carries a watchbill (either roster)."""
    return bool(column.full_watch or column.thin_watch)


def roster_for(column, kind: str):
    """The stations of ``kind``'s watch ("full" / "thin")."""
    return column.full_watch if kind == "full" else column.thin_watch


def station_dock_cell(station_spec) -> tuple[int, int]:
    """The cell ships launch from / land at beside a station — the
    same east-of-body +1, mid-height convention as the merchant
    body goals (``npc_ships._build_body_goals``; keep in sync)."""
    return (
        station_spec.pos.x + station_spec.width + 1,
        station_spec.pos.y + station_spec.height // 2,
    )


def next_boundary_gap(day: int, month: int, year: int, shift_days: int) -> int:
    """Days from the given date to the NEXT boundary (strictly
    future — a boundary day advances a full shift)."""
    _total = total_days(day, month, year)
    return shift_days - ((_total - _EPOCH_DAY) % shift_days)


# ---------------------------------------------------------------------------
# The watch build (doc 41 phase 2) — who stands where at a map build
# ---------------------------------------------------------------------------

def make_static_entity(espec, pos, spawn_key):
    """The one construction site for static-system ship entities —
    the map build and the watch's runtime launches share it (no
    copy-pasted Entity blocks; see the phase-2 audit's DRY list)."""
    return world.Entity(
        char=espec.char, fg=espec.fg, pos=pos,
        name=espec.name, width=1, height=1,
        npc_ship_id=espec.id, static_spawn_key=spawn_key,
    )


def _watch_rows_by_y(system, column):
    """The picket rows standing at the column's x, keyed by station y."""
    return {
        _row.pos.y: _row
        for _row in getattr(system, "enemies", ()) or ()
        if _row.pos.x == column.x
        and _row.enemy_id == column.picket_enemy_id
    }


def static_build_placements(system, total):
    """(row, spawn key, position) for every static spawning at a map
    built on day ``total`` (doc 41 phase 2).

    The current watch spawns PARKED on its stations, tenure-keyed;
    off-duty stations place nothing; every non-watch row places
    itself (phase-1 semantics). Overdue future reliefs — their
    launch day passed before this build — stamp AT THEIR BASES and
    fly in once stepped (flight state is session-scoped: the map
    rebuild dropped it; build-side reconciliation). ``total`` None
    on a watch-active system raises: an unwatched build would
    silently dark the column.
    """
    column = getattr(system, "sensor_column", None)
    rows = tuple(getattr(system, "enemies", ()) or ())
    if column is None or not watch_active(column):
        return tuple(
            (_row, solar_system_module.static_spawn_key(system, _row), _row.pos)
            for _row in rows
        )
    if total is None:
        raise ValueError(
            f"{getattr(system, 'id', '?')!r} carries a watchbill: its "
            "map build needs watch_day (a build without one would "
            "silently dark the column)"
        )
    placements = _row_placements(
        system, rows, column, tenure_of(total, column.shift_days),
    )
    placements.extend(_overdue_reliefs(system, column, total))
    return tuple(placements)


def _row_placements(system, rows, column, tenure):
    """Per static row: plain rows place themselves (phase-1 keys),
    on-duty watch rows park on station with tenure keys, off-duty
    rows place nothing. Watch-row membership is
    :func:`_watch_rows_by_y` — the one definition (x + id + y)."""
    _watch_rows = _watch_rows_by_y(system, column)
    _on_duty_ys = {
        _station.y
        for _station in roster_for(
            column, watch_kind(tenure, column.watch_cycle),
        )
    }
    out = []
    for _row in rows:
        if _row.pos.y not in _watch_rows:
            out.append((
                _row, solar_system_module.static_spawn_key(system, _row), _row.pos,
            ))
        elif _row.pos.y in _on_duty_ys:
            out.append((
                _row,
                tenure_key(solar_system_module.static_spawn_key(system, _row), tenure),
                _row.pos,
            ))
    return out


def _overdue_reliefs(system, column, total):
    """Future-tenure reliefs whose launch day has already passed:
    stamped at their bases, keyed for the tenure they fly toward."""
    _shift = column.shift_days
    _tenure = tenure_of(total, _shift)
    _rows_by_y = _watch_rows_by_y(system, column)
    _bases = {_spec.id: _spec for _spec in getattr(system, "stations", ()) or ()}
    out = []
    for _future in (_tenure + 1, _tenure + 2):
        _roster = roster_for(column, watch_kind(_future, column.watch_cycle))
        for _station in _roster:
            _row = _rows_by_y.get(_station.y)
            _base = _bases.get(_station.base_id)
            if (
                _row is None or _base is None
                or station_launch_day(_future, _station, _shift) > total
            ):
                continue
            out.append((
                _row,
                tenure_key(solar_system_module.static_spawn_key(system, _row), _future),
                world.Position(*station_dock_cell(_base)),
            ))
    return out


# ---------------------------------------------------------------------------
# The movement-pass check
# ---------------------------------------------------------------------------

def _entered_column(prev_x: int | None, new_x: int, column_x: int) -> bool:
    """The sweep fires on ENTERING the column from either side;
    leaving is always free — a complying hull is never re-hailed on
    its retreat (user playtest ruling, 2026-09-09)."""
    return prev_x is not None and new_x == column_x and prev_x != column_x


def check_crossing(ctx, pos):
    """The movement pass's Line check (runs before the auto-comms
    warning; a hailed step skips that pass).

    The sweep fires once per entry onto the column, from either
    side; leaving is free (no re-hail on a complying retreat). The
    sweep is manned: with no picket alive the column is dark — no
    hail, no waves, no defiance (the fight method pays).

    None: nothing happened this step (no entry, or a dark hull the
    sweep cannot see). ``(False, None)``: a wave — the all-clear
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
    crossed = _entered_column(_prev_x, pos.x, column.x)
    _prev_x = pos.x
    if not crossed or not _picket_payload(ctx, column, system)[0]:
        return None  # no entry, or the sweep is unmanned: dark column
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


def _line_modal(ctx, column, lines, options, dispatch, esc_label):
    """One comms-shaped Line modal — the checkpoint's single
    presentation; returns the player's reply. The column's message
    templates carry an ``{id}`` placeholder for the address."""
    from . import comms
    return comms._pygame_interaction_outcome(
        ctx, column.label, None, options,
        contact_entity=None, dispatch=dispatch, title="Hailing",
        esc_label=esc_label,
        lines=tuple(
            line.format(id=_checkpoint_address(ctx)) for line in lines
        ),
    )


def _wave_through(ctx, column, lines) -> tuple[bool, None]:
    """A waved crossing: the blockade's all-clear comms (one
    Acknowledge option; ESC counts), then a terse log line.
    ``(False, None)`` — the player is through; GO TO continues."""
    _line_modal(
        ctx, column, lines, ("Acknowledge",), _ACK_DISPATCH,
        "ESC acknowledge",
    )
    ctx.log.add("The blockade waves you through.")
    return (False, None)


def _wave_papers(ctx, column, system):
    return _wave_through(ctx, column, column.manifest_lines or column.hail_lines)


def _wave_rank(ctx, column, system):
    return _wave_through(ctx, column, column.rank_lines or column.hail_lines)


def _wave_service(ctx, column, system):
    _wave_through(ctx, column, column.service_lines or column.hail_lines)
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
        _CHECKPOINT_DISPATCH, "ESC defy",
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
    return (True, _picket_payload(ctx, column, system))


def _picket_payload(ctx, column, system):
    """(specs, positions) for every alive picket on the Line.

    Identity is the stamped ``static_spawn_key``, not position —
    combat moves hulls, and a lured-but-alive picket fights from
    where it actually is."""
    from .data.npc_ships import find_npc_ship
    from .solar_system import static_spawn_key
    _live: dict = {
        getattr(_e, "static_spawn_key", ""): _e.pos
        for _e in ctx.game_map.entities
        if not getattr(_e, "owned", False)
        and getattr(_e, "static_spawn_key", "")
    }
    specs: list = []
    positions: list = []
    for _spawn in getattr(system, "enemies", ()) or ():
        if _spawn.squad_id != column.squad_id:
            continue
        _key = static_spawn_key(system, _spawn)
        if _key not in _live:
            continue
        try:
            specs.append(find_npc_ship(_spawn.enemy_id))
        except KeyError:
            continue
        positions.append(_live[_key])
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
