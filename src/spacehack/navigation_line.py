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

THE WATCH (phase 2): the pickets rotate on the SensorColumn's
watchbill shifts (30 days as shipped) — everything derives from the day
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
from . import npc_movement
from . import solar_system as solar_system_module
from . import world
from .data.npc_ships import find_npc_ship as _find_picket_spec, map_speed
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
# not divisible by any sane shift length, so raw total_days would
# drift the boundaries off the ruled grid — tenure counts from HERE.
_EPOCH_DAY = total_days(day=1, month=1, year=2200)


def clock_total(ctx) -> int:
    """``total_days`` off a ctx (lightweight doubles stay valid)."""
    return total_days(
        getattr(ctx, "time_day", 1),
        getattr(ctx, "time_month", 1),
        getattr(ctx, "time_year", 2200),
    )


def tenure_of(total: int, shift_days: int) -> int:
    """Which shift owns ``total``: boundaries land every
    ``shift_days`` days (31/61/91… at the shipped 30; epoch-anchored
    — tenure 0 is the game's first shift)."""
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


def dock_spacing_cells(base, count):
    """Launch cells east of a base's dock, two apart (round 4):
    same-day reliefs from one base muster and leave pre-spaced — a
    convoy, not a brawl over one doorway. Deterministic by ordinal
    so the build stamp, the runtime launch, and the order gate all
    agree on the same cells."""
    _x, _y = station_dock_cell(base)
    return tuple((_x + 2 * _i, _y) for _i in range(count))


def _base_ordinals(roster):
    """Station y -> that station's ordinal within its base, in
    roster order. The ordinal picks the dock spacing cell."""
    _seen: dict = {}
    _out: dict = {}
    for _station in roster:
        _n = _seen.get(_station.base_id, 0)
        _out[_station.y] = _n
        _seen[_station.base_id] = _n + 1
    return _out


def _overdue_reliefs(system, column, total):
    """Future-tenure reliefs whose launch day has already passed:
    stamped at their bases, keyed for the tenure they fly toward."""
    _shift = column.shift_days
    _tenure = tenure_of(total, _shift)
    _rows_by_y = _watch_rows_by_y(system, column)
    _bases = _bases_by_id(system)
    out = []
    for _future in (_tenure + 1, _tenure + 2):
        _roster = roster_for(column, watch_kind(_future, column.watch_cycle))
        _ordinals = _base_ordinals(_roster)
        for _station in _roster:
            _row = _rows_by_y.get(_station.y)
            _base = _bases.get(_station.base_id)
            if (
                _row is None or _base is None
                or station_launch_day(_future, _station, _shift) > total
            ):
                continue
            _cell = dock_spacing_cells(
                _base, _ordinals[_station.y] + 1,
            )[-1]
            out.append((
                _row,
                tenure_key(solar_system_module.static_spawn_key(system, _row), _future),
                world.Position(*_cell),
            ))
    return out


# ---------------------------------------------------------------------------
# The watch pass (doc 41 phase 2) — one player step of watch traffic
# ---------------------------------------------------------------------------

def step_watch(ctx, day_pass: bool = False) -> None:
    """The per-step watch pass (call beside ``move_npcs`` in both
    movement passes): flights step every pass; launches and
    departures only on due days (pure day-arithmetic gate — O(1)
    idle steps). Wordless: nothing here logs. ``day_pass``: a
    wait's full day — each flight banks its whole hull speed."""
    system = solar_system_module.current_system()
    column = getattr(system, "sensor_column", None)
    if column is None or not watch_active(column):
        return
    total = clock_total(ctx)
    tenure = tenure_of(total, column.shift_days)
    _due, _boundary = _due_state(total, column, tenure)
    if _due:
        _run_due(ctx, system, column, total, tenure, _boundary)
    _step_flights(
        ctx, system, column, total, tenure,
        npc_movement.player_moves_per_day(ctx), day_pass,
    )


def _due_state(total, column, tenure) -> tuple[bool, bool]:
    """(due today, boundary today) — O(1) pure day arithmetic: today
    is a boundary day, or any horizon station's exact launch day."""
    if (total - _EPOCH_DAY) % column.shift_days == 0:
        return (True, True)
    for _future in (tenure, tenure + 1, tenure + 2):
        _roster = roster_for(column, watch_kind(_future, column.watch_cycle))
        for _station in _roster:
            if station_launch_day(_future, _station, column.shift_days) == total:
                return (True, False)
    return (False, False)


def _run_due(ctx, system, column, total, tenure, boundary: bool) -> None:
    """Launch-day/boundary work. Overdue-INCLUSIVE (``<=``) so day
    skips (dev clock jumps) self-heal at the next due day."""
    _ensure_relief_wave(ctx, system, column, total, tenure)
    if boundary:
        _depart_ended_shifts(ctx, system, column, tenure)


def _live_watch_keys(ctx) -> set:
    """Spawn keys of every keyed, non-owned entity on the map."""
    return {
        _e.static_spawn_key
        for _e in ctx.game_map.entities
        if not getattr(_e, "owned", False)
        and getattr(_e, "static_spawn_key", "")
    }


def _stations_by_y(column) -> dict:
    """Every watchbill station keyed by its row y."""
    return {
        _station.y: _station
        for _station in (*column.full_watch, *column.thin_watch)
    }


def _bases_by_id(system) -> dict:
    """The system's stations by id (relief bases and landings)."""
    return {
        _spec.id: _spec for _spec in getattr(system, "stations", ()) or ()
    }


def _ensure_relief_wave(ctx, system, column, total, tenure) -> None:
    """Every horizon station-tenure whose launch day has passed gets
    its relief airborne from the base — unless the key is tombstoned
    (a murdered relief stays dead for its tenure) or already flying.
    The CURRENT tenure reads as overdue-inclusive: a keeper absent
    without a tombstone was never launched this session (the map
    predates its boundary) — it flies in late."""
    _shift = column.shift_days
    _ledger = getattr(ctx, "defeated_static_spawns", set())
    _live = _live_watch_keys(ctx)
    _rows_by_y = _watch_rows_by_y(system, column)
    _bases = _bases_by_id(system)
    for _future in (tenure, tenure + 1, tenure + 2):
        _roster = roster_for(column, watch_kind(_future, column.watch_cycle))
        _ordinals = _base_ordinals(_roster)
        for _station in _roster:
            _row = _rows_by_y.get(_station.y)
            _base = _bases.get(_station.base_id)
            _key_row = (
                tenure_key(solar_system_module.static_spawn_key(system, _row), _future)
                if _row is not None else ""
            )
            if (
                _row is None or _base is None
                or station_launch_day(_future, _station, _shift) > total
                or _key_row in _ledger or _key_row in _live
            ):
                continue
            _launch_relief(
                ctx, _row, _key_row, _station, _base, column.x,
                _ordinals[_station.y],
            )


def _launch_relief(ctx, row, key, station, base, column_x, ordinal) -> None:
    """One relief leaves its base for its station from its spacing
    cell (round 4: pre-spaced convoy, never a shared doorway),
    target cached in the existing path dicts. SILENT (the merchant
    paths log their pings — the watch's schedule is observable by
    watching only)."""
    from .data.npc_ships import find_npc_ship
    try:
        _spec = find_npc_ship(row.enemy_id)
    except KeyError:
        return
    _entity = make_static_entity(
        _spec, world.Position(*dock_spacing_cells(base, ordinal + 1)[-1]), key,
    )
    ctx.game_map.entities.append(_entity)
    _assign_flight(ctx, key, _entity, (column_x, station.y))


def _assign_flight(ctx, key, entity, target_cell) -> None:
    """Target + cached A* path for one flight (the existing path
    dicts, keyed by spawn key — dropped at save by the procedural
    sync, so flights are session-scoped)."""
    _target = tuple(target_cell)
    ctx.npc_targets[key] = _target
    ctx.npc_paths[key] = world.find_path(
        (entity.pos.x, entity.pos.y), {_target}, ctx.game_map,
        exclude_entity=entity,
    ) or []


def _depart_ended_shifts(ctx, system, column, tenure) -> None:
    """Boundary: every picket of an ENDED tenure standing AT ITS OWN
    STATION (the x:y in its key, within a cell — a slip aside still
    counts as on post) is ordered home to its base. Displaced or
    lured pickets are never given a target; in-flight ones keep
    theirs."""
    _bases = _bases_by_id(system)
    _by_y = _stations_by_y(column)
    for _entity in list(ctx.game_map.entities):
        _parsed = _watch_entity_key(_entity)
        if _parsed is None:
            continue
        ((_key_x, _key_y), _key_tenure) = _parsed
        _station = _by_y.get(_key_y)
        _base = _bases.get(_station.base_id) if _station is not None else None
        if (
            _key_tenure >= tenure
            or _base is None
            or ctx.npc_targets.get(_entity.static_spawn_key) is not None
            or max(abs(_entity.pos.x - _key_x), abs(_entity.pos.y - _key_y)) > 1
        ):
            continue
        _assign_flight(ctx, _entity.static_spawn_key, _entity, station_dock_cell(_base))


def _watch_entity_key(entity):
    """``((x, y), tenure)`` for a live watch picket, else None."""
    if getattr(entity, "owned", False):
        return None
    _key = getattr(entity, "static_spawn_key", "")
    return parse_tenure_key(_key) if _key else None


def _step_flights(ctx, system, column, total, tenure, player_speed,
                  day_pass=False) -> None:
    """Step every targeted flight at the picket's OWN hull speed
    (doc 44 credit, deterministic; ``combat_locked`` skipped). A
    targetless relief on a base SPACING cell takes station orders
    (the build's spaced stamps are awaiting them); any other
    targetless picket adjacent to its own post re-centers onto it
    (round 4)."""
    _base_cells = {
        _cell
        for _spec in _bases_by_id(system).values()
        for _cell in dock_spacing_cells(
            _spec, len(column.full_watch) + len(column.thin_watch),
        )
    }
    _by_y = _stations_by_y(column)
    for _entity in list(ctx.game_map.entities):
        _parsed = _watch_entity_key(_entity)
        if _parsed is None or getattr(_entity, "combat_locked", False):
            continue
        ((_key_x, _key_y), _key_tenure) = _parsed
        _station = _by_y.get(_key_y)
        if _station is None:
            continue
        _key = _entity.static_spawn_key
        _target = ctx.npc_targets.get(_key)
        if _target is None:
            if not _order_base_relief(ctx, column, _entity, _key, _key_tenure,
                                      _station, total, tenure, _base_cells):
                _recenter_on_station(
                    ctx, _entity, (_key_x, _key_y), _key_tenure, tenure,
                )
        else:
            _advance_flight(
                ctx, _entity, _key, _target, (_key_x, _key_y),
                player_speed, day_pass,
            )


def _order_base_relief(ctx, column, entity, key, key_tenure, station,
                       total, tenure, base_cells) -> bool:
    """Orders for a relief stamped at its base by a mid-tenure build:
    current-or-future tenure, standing on a base SPACING cell,
    launch day passed. Everything else (parked on post, lured
    aside, displaced across a boundary) stays exactly where it is.
    True when orders were given."""
    if (
        key_tenure < tenure
        or (entity.pos.x, entity.pos.y) not in base_cells
        or station_launch_day(key_tenure, station, column.shift_days) > total
    ):
        return False
    _assign_flight(ctx, key, entity, (column.x, station.y))
    return True


def _recenter_on_station(ctx, entity, station_cell, key_tenure, tenure) -> None:
    """One DIRECT step onto the exact station cell (round 4): a
    targetless picket of a current-or-future tenure standing
    Chebyshev-1 from its OWN post, with the cell free, re-centers.
    Never a flight target — the within-a-cell arrival check would
    self-cancel it. Flown-in pickets otherwise park one cell off
    for their whole tenure, invisible to the row-position trigger
    pass. Displaced (ended-tenure) pickets stay put — that ruling
    holds."""
    if key_tenure < tenure:
        return
    _dx = station_cell[0] - entity.pos.x
    _dy = station_cell[1] - entity.pos.y
    if max(abs(_dx), abs(_dy)) != 1:
        return
    if ctx.game_map.blocking_entity_at(
            station_cell[0], station_cell[1], exclude=entity,
    ) is not None:
        return
    world.try_step_with_slip(entity, ctx.game_map, _dx, _dy)


def _advance_flight(ctx, entity, key, target, station_cell,
                    player_speed, day_pass=False) -> None:
    """One pass of credited flight along the cached path (doc 44:
    the picket flies at its OWN hull speed — deterministic, the
    kernel's clamp parks it on a cell that would trigger an
    encounter). Pathless flights compute their A* once; unreachable
    targets drop the flight (stands fast)."""
    _tx, _ty = target
    if _within_a_cell(entity, _tx, _ty):
        _arrive(ctx, entity, key, target, station_cell)
        return
    if not ctx.npc_paths.get(key):
        # falsy, not None: an empty stored path (assign-time A*
        # failure) recomputes too — a ghost target must never pin
        # a picket outside every other lifecycle check.
        ctx.npc_paths[key] = world.find_path(
            (entity.pos.x, entity.pos.y), {(_tx, _ty)}, ctx.game_map,
            exclude_entity=entity,
        ) or []
        if not ctx.npc_paths[key]:
            _drop_flight(ctx, key)  # unreachable: stands fast
            return
    try:
        _spec = _find_picket_spec(entity.npc_ship_id)
        _speed, _radius = map_speed(_spec), _spec.detect_radius
    except KeyError:
        _speed, _radius = 1, 0
    _credit, _outcome = npc_movement.spend_credit(
        ctx, ctx.game_map, entity=entity, key=key,
        credit=ctx.npc_credit.get(key, 0.0)
        + npc_movement.rate_for(_speed, player_speed, day_pass),
        player_pos=ctx.player.pos, radius=_radius,
    )
    if _outcome == "blocked" and _blocked_by_parked(ctx, entity, key):
        _reroute_flight(ctx, entity, key, (_tx, _ty))
    _settle_flight_outcome(
        ctx, entity, key, target, station_cell, _credit, _outcome,
    )


def _settle_flight_outcome(ctx, entity, key, target, station_cell,
                           credit, outcome) -> None:
    """Post-``spend_credit`` bookkeeping: settle the retained
    fraction, or run the arrival (park / land) on exhaustion."""
    if outcome in ("moving", "blocked", "clamped"):
        npc_movement.settle(ctx, key, credit)
    elif _within_a_cell(entity, target[0], target[1]):
        _arrive(ctx, entity, key, target, station_cell)
    else:
        npc_movement.settle(ctx, key, credit)


def _blocked_by_parked(ctx, entity, key) -> bool:
    """The path-head cell's occupant is effectively stationary: a
    combat-locked hull, or a watch picket with no live target.
    Head-on MOVERS pass under the kept-path idiom (verified: 23
    passes, zero recomputes) — re-routing past them would churn
    ~16ms of A* per pass for nothing."""
    _path = ctx.npc_paths.get(key) or []
    if not _path:
        return False
    _blocker = ctx.game_map.blocking_entity_at(
        _path[0][0], _path[0][1], exclude=entity,
    )
    if _blocker is None:
        return False
    if getattr(_blocker, "combat_locked", False):
        return True
    _bkey = getattr(_blocker, "static_spawn_key", "")
    if parse_tenure_key(_bkey) is None:
        return False  # a procedural mover — slips carry us past
    return ctx.npc_targets.get(_bkey) is None


def _reroute_flight(ctx, entity, key, target) -> None:
    """Recompute the path around a parked blocker (A* avoids
    occupied intermediates). On failure KEEP the old path — a
    sealed corridor is momentary, and dropping the flight would
    strand a home-bound hull forever (round 4's ADVISE round)."""
    _fresh = world.find_path(
        (entity.pos.x, entity.pos.y), {tuple(target)}, ctx.game_map,
        exclude_entity=entity,
    )
    if _fresh:
        ctx.npc_paths[key] = _fresh


def _within_a_cell(entity, x: int, y: int) -> bool:
    """Arrival proximity: within a cell of the target (a slip aside
    off an occupied station still counts as on post)."""
    return max(abs(entity.pos.x - x), abs(entity.pos.y - y)) <= 1


def _drop_flight(ctx, key) -> None:
    """Forget one flight entirely — target, path, and credit."""
    ctx.npc_targets.pop(key, None)
    ctx.npc_paths.pop(key, None)
    ctx.npc_credit.pop(key, None)


def _arrive(ctx, entity, key, target, station_cell) -> None:
    """Arrival (path exhausted / within a cell of the target): a
    station target parks the picket — early arrivals HOLD their post
    (a slip aside off an occupied station counts); a base target
    lands it, despawned SILENTLY."""
    _drop_flight(ctx, key)
    if tuple(target) != tuple(station_cell):
        try:
            ctx.game_map.entities.remove(entity)
        except ValueError:
            pass


# ---------------------------------------------------------------------------
# The legacy tombstone migration (doc 41 phase 2) — one-time, at load
# ---------------------------------------------------------------------------

def migrate_legacy_tombstones(keys, *, day: int, month: int, year: int) -> list:
    """Re-stamp pre-phase-2 UNQUALIFIED picket tombstones with the
    current tenure's key: a phase-1 kill stays dead through the
    current tenure and its post re-mans at the next boundary — no
    silent resurrection, no eternal death.

    Scoped to column systems' ``picket_enemy_id`` prefixes only
    (ross_154 / lalande_21185 ship unqualified static kill keys and
    are never touched). Idempotent: already-tenured keys pass
    through, so this runs safely at every load.
    """
    from .data import solar_systems as _systems
    _total = total_days(day, month, year)
    _columns = [
        (_sys.id, _sys.sensor_column)
        for _sys in _systems.list_solar_systems()
        if getattr(_sys, "sensor_column", None) is not None
    ]
    out = []
    for _key in keys:
        if parse_tenure_key(_key) is not None:
            out.append(_key)
            continue
        for _sys_id, _column in _columns:
            if _key.startswith(f"{_sys_id}:{_column.picket_enemy_id}:"):
                out.append(tenure_key(_key, tenure_of(_total, _column.shift_days)))
                break
        else:
            out.append(_key)
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
    if not crossed or not _picket_payload(ctx, column)[0]:
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
    return (True, _picket_payload(ctx, column))


def _picket_payload(ctx, column):
    """(specs, positions) for every alive picket on the Line —
    parked, in flight, displaced: the sweep counts them all (doc 41
    phase 2; a relief wave keeps the column swept from launch).

    Read by ID: the picket id is unique to the column system, and
    identity-by-key would need the watchbill to interpret tenures.
    Positions are LIVE — combat moves hulls, and a lured-but-alive
    picket fights from where it actually is."""
    from .data.npc_ships import find_npc_ship
    positions = [
        _e.pos for _e in ctx.game_map.entities
        if not getattr(_e, "owned", False)
        and getattr(_e, "npc_ship_id", "") == column.picket_enemy_id
    ]
    if not positions:
        return ([], [])
    try:
        _spec = find_npc_ship(column.picket_enemy_id)
    except KeyError:
        return ([], [])
    return ([_spec] * len(positions), positions)


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
