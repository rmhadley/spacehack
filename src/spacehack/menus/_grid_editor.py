"""The fitting-grid editor (doc 56 phase 3): cursor + pick/place state
machine, letter-block presentation, and the read-only letter grid the
hangar and mechanic tabs reuse (SETTLED 19).

Two deliberate layers:

* The PURE layer (cursor, held part, ghost legality, power footer) is
  catalog-free plain ints exactly like :mod:`spacehack.fitting` — every
  geometry and power question reuses ``fitting``'s primitives
  (``in_bounds`` / ``footprint`` / ``net_power``), never a re-derived
  copy. Ghost legality composes the same three refusals the phase-2
  gate enforces: bounds, overlap, resting power.
* The PRESENTATION layer composes letter rows (SETTLED 15's letters)
  as ``(text, runs)`` pairs — tier colours via ``quality_color``,
  red/green legality for the held ghost (the legality colour overrides
  the tier colour), a bracketed cursor cell. Hosts wrap the pairs:
  the mechanic editor paints them as split rows, the hangar and
  mechanic tabs as screen body/rows.

The hand itself lives with the host (modal-runner session state, per
the phase-3 hand model); this module only ever sees the pure
:class:`HeldPart` mirror.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..fitting import footprint, in_bounds, net_power

Cell = tuple[int, int]


# ---------------------------------------------------------------------------
# Pure layer — plain ints, no catalogs, no ctx
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HeldPart:
    """The pure mirror of the editor's hand.

    ``origin`` is the vacated anchor when the part was PICKED UP from
    the grid (the entry stays installed at that anchor — held-as-fitted
    is free, doc 56 SETTLED 6); ``None`` for a HANDED-OVER part (buy or
    storage install, doc 56 SETTLED 17) which is not installed until
    dropped.
    """

    w: int
    h: int
    upkeep: int = 0
    origin: Cell | None = None


@dataclass(frozen=True)
class EditorState:
    """Cursor position and the hand's pure mirror."""

    grid_w: int
    grid_h: int
    cursor: Cell = (0, 0)
    held: HeldPart | None = None


def initial_state(grid_w: int, grid_h: int) -> EditorState:
    """A fresh editor over a grid, cursor at the top-left corner."""
    return EditorState(grid_w=grid_w, grid_h=grid_h)


def move_cursor(state: EditorState, dx: int, dy: int) -> EditorState:
    """Move the cursor by ``(dx, dy)`` clamped inside the grid."""
    x = max(0, min(state.grid_w - 1, state.cursor[0] + dx))
    y = max(0, min(state.grid_h - 1, state.cursor[1] + dy))
    return EditorState(state.grid_w, state.grid_h, (x, y), state.held)


def hold_part(state: EditorState, part: HeldPart) -> EditorState:
    """Take a part into the hand; a picked-up part's cursor snaps to its
    origin anchor so the ghost starts exactly where it was."""
    cursor = state.cursor if part.origin is None else part.origin
    return EditorState(state.grid_w, state.grid_h, cursor, part)


def release(state: EditorState) -> EditorState:
    """Empty the hand."""
    return EditorState(state.grid_w, state.grid_h, state.cursor, None)


def piece_at(pieces, cell: Cell):
    """The piece whose footprint covers ``cell``, or None.

    Pure over any records carrying ``x``/``y``/``w``/``h`` — the host's
    placed-piece views or a test's fakes alike.
    """
    x, y = cell
    for piece in pieces:
        if piece.x <= x < piece.x + piece.w and piece.y <= y < piece.y + piece.h:
            return piece
    return None


def drop_refusal(
    state: EditorState, occupied: set, base_gen: int, bonuses,
) -> str | None:
    """Why the held part may not drop at the cursor: ``"room"`` (out of
    bounds or overlapping another piece), ``"power"`` (the resting grid
    would go negative), or None when the drop is legal.

    ``occupied`` is the LIVE cell set including the held part's own
    origin footprint (the picked-up entry stays installed) — the vacated
    origin is excluded here, the one place that rule lives.
    ``bonuses`` is the as-if-fitted effective power list: every
    installed module's contribution plus the hand's exactly once
    (picked-up parts are already in the tuple).
    """
    part = state.held
    if part is None:
        return "room"
    x, y = state.cursor
    if not in_bounds(state.grid_w, state.grid_h, x, y, part.w, part.h):
        return "room"
    blockers = set(occupied)
    if part.origin is not None:
        blockers -= footprint(part.origin[0], part.origin[1], part.w, part.h)
    if footprint(x, y, part.w, part.h) & blockers:
        return "room"
    if net_power(base_gen, bonuses) < 0:
        return "power"
    return None


def drop_legal(
    state: EditorState, occupied: set, base_gen: int, bonuses,
) -> bool:
    """The ghost's colour predicate (SETTLED 16: green here, red not)."""
    return drop_refusal(state, occupied, base_gen, bonuses) is None


def power_parts(base_gen: int, bonuses) -> tuple[int, int, int]:
    """The POWER footer's ``(gen, upkeep, net)`` components.

    ``gen`` is the hull base plus every positive contribution (reactor
    modules are generators); ``upkeep`` is the negative sum, carried as
    a negative number; ``net`` is their signed total — the same number
    :func:`fitting.net_power` gates on.
    """
    gen = base_gen + sum(bonus for bonus in bonuses if bonus > 0)
    upkeep = sum(bonus for bonus in bonuses if bonus < 0)
    return gen, upkeep, gen + upkeep


def _signed(value: int) -> str:
    """Sign-conditional component: ``+9``, ``0`` (never ``-0``), ``-3``."""
    return f"+{value}" if value > 0 else str(value)


def power_footer(base_gen: int, bonuses) -> str:
    """The fitting screen's POWER line (ASCII hyphen; zero renders bare).

    ``POWER: +9 gen / -2 upkeep / +7 net`` — the doc's ruled format.
    """
    gen, upkeep, net = power_parts(base_gen, bonuses)
    return f"POWER: {_signed(gen)} gen / {upkeep} upkeep / {_signed(net)} net"


# ---------------------------------------------------------------------------
# Presentation layer — SETTLED 15 letters, tier colours, cursor + ghost
# ---------------------------------------------------------------------------

# SETTLED 15's ruling, now the game-side single source (the fixture
# renderer imports this table). Shield capacitor/recharger fold into
# the shield family letter; EMP gets its own E beside the missile M. A
# new catalog id without a letter fails loudly so the decision is
# made, not defaulted.
LETTERS: dict[str, str] = {
    # weapons
    "light_laser": "L", "medium_laser": "L", "heavy_laser": "L",
    "light_missile": "M", "heavy_missile": "M",
    "emp_missile": "E",
    "plasma_cannon": "P",
    "breach_charge_test": "B",
    # modules
    "shield_mk1": "S", "shield_mk2": "S", "shield_mk3": "S", "shield_mk4": "S",
    "shield_capacitor": "S", "shield_recharger": "S",
    "targeting_computer": "T", "targeting_mk2": "T", "targeting_mk3": "T", "targeting_mk4": "T",
    "gyro_stabilizer": "G", "gyro_mk2": "G", "gyro_mk3": "G", "gyro_mk4": "G",
    "expanded_cargo": "C", "cargo_mk2": "C", "cargo_mk3": "C", "cargo_mk4": "C",
    "armor_plating": "A", "armor_mk2": "A", "armor_mk3": "A", "armor_mk4": "A",
    "compact_reactor": "R", "reactor_mk2": "R", "reactor_mk3": "R", "reactor_mk4": "R",
    "heavy_reactor": "R",
    "smuggler_hold_mk1": "H", "smuggler_hold_mk2": "H",
    "smuggler_hold_mk3": "H", "smuggler_hold_mk4": "H",
}


def letter(item_id: str) -> str:
    """The item's grid letter (SETTLED 15); unknown ids fail loudly."""
    return LETTERS[item_id]


@dataclass(frozen=True)
class GridPiece:
    """One placed entry's presentation view (host builds these from the
    owned tuples; the held picked-up piece is omitted — its cells are
    vacated while the ghost paints it at the cursor)."""

    key: str
    item_id: str
    x: int
    y: int
    w: int
    h: int
    color: tuple[int, int, int] | None = None
    detail: str = ""


def _tier_color(quality: int, randart_seed) -> tuple[int, int, int] | None:
    """The tier's letter colour; randarts read legendary (the module
    label seam's rule, applied to grid letters)."""
    from ..data.quality import LEGENDARY_QUALITY, quality_color

    return quality_color(
        LEGENDARY_QUALITY if randart_seed is not None else quality,
    )


def _entry_detail(entry) -> str:
    """The hovered-entry readout: the shipped detail lines."""
    if entry.item_type == "weapon":
        from ..data.weapons import find_weapon
        from ..ship import weapon_display_name

        return " - ".join(
            (weapon_display_name(entry.item_id, entry.quality),
             _weapon_detail(find_weapon(entry.item_id), quality=entry.quality)),
        )
    from ..ship import module_display_name

    return " - ".join((
        module_display_name(entry.item_id, entry.quality, entry.randart_seed),
        _entry_module_detail(entry),
    ))


def _entry_module_detail(entry) -> str:
    from ..ship import module_detail

    try:
        return module_detail(entry.item_id, entry.quality, entry.randart_seed)
    except KeyError:
        return ""


def _weapon_detail(spec, *, ammo: int | None = None, ctx=None, quality: int = 0) -> str:
    """Format weapon details for a market, storage, or ship row.

    (Lives here — the editor's hover readout and the loadout market
    rows share one formatter.) ``ctx`` switches the missile capacity
    shown to the effective rack (the Bounty Hunter's double, doc 49
    SETTLED 7); rows without ctx read the catalog spec. ``quality``
    scales damage AND accuracy to the flown instance's tier (doc 47
    SETTLED 2).
    """
    from ..data.quality import effective_ship_weapon_spec
    from ..ship import effective_missile_capacity

    spec = effective_ship_weapon_spec(spec.id, quality)
    detail = (
        f"Damage: {spec.damage}  Accuracy: {spec.accuracy}%  "
        f"Range: {spec.min_range}-{spec.max_range}"
    )
    if spec.slot_type == "missile":
        capacity = effective_missile_capacity(spec, ctx)
        current = capacity if ammo is None else max(0, min(ammo, capacity))
        detail += f"  Ammo: {current}/{capacity}"
    return detail


def pieces_for(owned, *, omit_key=None) -> tuple[GridPiece, ...]:
    """Presentation views for every PLACED entry (doc 56 phase 3).

    ``omit_key`` is the rich hand's installed key (``"weapon:2"``) when
    a picked-up part is held: that entry is omitted — its cells vacate
    for the ghost. Unplaced entries are skipped (none exist mid-play
    after load normalization).
    """
    from ..ship_fitting import _entry_spec

    pieces = []
    for kind, entries in (
        ("weapon", getattr(owned, "weapons", ()) or ()),
        ("module", getattr(owned, "modules", ()) or ()),
    ):
        for index, entry in enumerate(entries):
            key = f"{kind}:{index}"
            if key == omit_key:
                continue
            spec = _entry_spec(entry)
            if spec is None or entry.grid_x is None or entry.grid_y is None:
                continue
            pieces.append(GridPiece(
                key=key, item_id=entry.item_id,
                x=entry.grid_x, y=entry.grid_y,
                w=spec.grid_w, h=spec.grid_h,
                color=_tier_color(entry.quality, entry.randart_seed),
                detail=_entry_detail(entry),
            ))
    return tuple(pieces)


def _piece_cells(pieces) -> dict[Cell, tuple[str, tuple[int, int, int] | None]]:
    """The placed letters: cell -> (letter, tier colour)."""
    return {
        (x, y): (letter(piece.item_id), piece.color)
        for piece in pieces
        for x in range(piece.x, piece.x + piece.w)
        for y in range(piece.y, piece.y + piece.h)
    }


def read_only_rows(ship_spec, owned) -> tuple[tuple[str, tuple | None], ...]:
    """The read-only letter grid (SETTLED 19): one ``(text, runs)`` pair
    per grid row, tier-coloured letters, ``.`` empties, no cursor —
    the hangar LOADOUT tab and the mechanic tab render this."""
    cells = _piece_cells(pieces_for(owned))
    rows = []
    for y in range(ship_spec.grid_h):
        segments = []
        for x in range(ship_spec.grid_w):
            glyph, color = cells.get((x, y), (".", None))
            segments.append((f"{glyph} ", color))
        rows.append(_trim_row(segments))
    return tuple(rows)


def _trim_row(segments):
    """Trim the row's trailing whitespace keeping runs == text."""
    segments = list(segments)
    while segments and not segments[-1][0].strip():
        segments.pop()
    if not segments:
        return "", None
    text, color = segments[-1]
    segments[-1] = (text.rstrip(), color)
    trimmed = tuple(segments)
    return "".join(part for part, _color in trimmed), trimmed


def _cell_paint(state, cells, ghost, hover_cells, cell, palette):
    """One cell's ``(glyph, colour)``: the held ghost's legality colour
    first, then the hovered piece's accent highlight, else the placed
    letter at its tier colour."""
    x, y = cell
    if ghost is not None and (
        state.cursor[0] <= x < state.cursor[0] + state.held.w
        and state.cursor[1] <= y < state.cursor[1] + state.held.h
    ):
        return ghost[0], (
            palette.positive if ghost[1] else palette.negative
        )
    if cell in hover_cells:
        return cells[cell][0], palette.accent
    return cells.get(cell, (".", None))


def _overlays(state, pieces, occupied, base_gen, bonuses, held_letter):
    """The two whole-piece overlays: the held ghost as
    ``(letter, legality)``, and — empty-handed — the hovered piece's
    cells (hover reads the piece, not the cell)."""
    ghost = (
        (held_letter, drop_legal(state, occupied, base_gen, bonuses))
        if state.held is not None and held_letter
        else None
    )
    hovered = piece_at(pieces, state.cursor) if state.held is None else None
    hover_cells = (
        footprint(hovered.x, hovered.y, hovered.w, hovered.h)
        if hovered is not None else set()
    )
    return ghost, hover_cells


def pane_rows(
    state: EditorState,
    pieces: tuple[GridPiece, ...],
    occupied: set,
    base_gen: int,
    bonuses,
    held_letter: str = "",
) -> tuple[tuple[str, tuple | None], ...]:
    """The editor's letter rows: cursor bracketed, held ghost painted at
    the cursor in its legality colour (green legal / red not — the
    legality colour overrides the tier colour), and the whole hovered
    piece highlighted in the accent colour (playtest 2026-09-30)."""
    from .. import pygame_ui

    palette = pygame_ui.DEFAULT_PALETTE
    ghost, hover_cells = _overlays(
        state, pieces, occupied, base_gen, bonuses, held_letter,
    )
    cells = _piece_cells(pieces)
    rows = []
    for y in range(state.grid_h):
        segments = []
        for x in range(state.grid_w):
            cell = (x, y)
            glyph, color = _cell_paint(
                state, cells, ghost, hover_cells, cell, palette,
            )
            # Every glyph centers in its 3-char cell: " S " / "[S]" —
            # the cursor brackets wrap the glyph without shifting its
            # column (playtest 2026-09-30).
            if cell == state.cursor:
                segments.append((f"[{glyph}]", color or palette.accent))
            else:
                segments.append((f" {glyph} ", color))
        rows.append(_trim_row(segments))
    return tuple(rows)
