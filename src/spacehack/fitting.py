"""Pure fitting-grid geometry and power arithmetic (doc 56).

Geometry and watts only: occupancy, placement legality, deterministic
first-fit packing, and the resting net-power sum. No ctx, no
``OwnedShip`` mutation, no catalog imports — callers pass plain ints
and item ids, so the same primitives serve the phase-1 lints and
fixture renderer, the phase-2 install paths and power gate, and the
phase-5 NPC-spec packing.

``first_fit`` is the single placement primitive; ``auto_fit`` is a fold
over it. Placements are ``(item_id, x, y, w, h)`` records; sizes are
never quality-scaled (doc 56 SETTLED 5) and never rotated (SETTLED 2).
Power takes an explicit bonus list so phase 3's held-items-count-as-
fitted (SETTLED 12) passes the hand's items with no redesign.
"""

from __future__ import annotations

from dataclasses import dataclass

Cell = tuple[int, int]


@dataclass(frozen=True)
class Placement:
    """One item's footprint on a hull grid."""

    item_id: str
    x: int
    y: int
    w: int
    h: int

    def cells(self) -> set[Cell]:
        """The grid coordinates this footprint covers."""
        return footprint(self.x, self.y, self.w, self.h)


def footprint(x: int, y: int, w: int, h: int) -> set[Cell]:
    """The cells a w x h item placed at (x, y) covers."""
    return {
        (cx, cy)
        for cx in range(x, x + w)
        for cy in range(y, y + h)
    }


def in_bounds(grid_w: int, grid_h: int, x: int, y: int, w: int, h: int) -> bool:
    """A w x h item at (x, y) lies entirely inside the grid.

    Non-positive sizes are illegal — catalog footprints are ints >= 1
    (linted), and a degenerate item must never silently "fit".
    """
    return w >= 1 and h >= 1 and x >= 0 and y >= 0 and x + w <= grid_w and y + h <= grid_h


def placement_legal(
    grid_w: int, grid_h: int, occupied: set[Cell], x: int, y: int, w: int, h: int
) -> bool:
    """Legality = in bounds and touching no occupied cell."""
    return in_bounds(grid_w, grid_h, x, y, w, h) and not (footprint(x, y, w, h) & occupied)


def first_fit(
    grid_w: int, grid_h: int, occupied: set[Cell], w: int, h: int
) -> Cell | None:
    """First legal anchor for one w x h item, scanning row-major from (0, 0).

    Deterministic — same inputs, same result. This is the primitive
    behind both the batch packer and the one-item installs (a buy or
    storage install places into a partially occupied grid).
    """
    for y in range(grid_h):
        for x in range(grid_w):
            if placement_legal(grid_w, grid_h, occupied, x, y, w, h):
                return (x, y)
    return None


def auto_fit(
    grid_w: int, grid_h: int, items: list[tuple[str, int, int]]
) -> list[Placement] | None:
    """Fold ``first_fit`` over ``items`` — ``(item_id, w, h)`` in order.

    Returns a placement for every item, or ``None`` as soon as one finds
    no legal cell: batch packing either fits everything or reports
    failure. Tuple order is preserved, so callers keying magazines by
    entry index (``weapon_ammo``) are unaffected.
    """
    occupied: set[Cell] = set()
    placements: list[Placement] = []
    for item_id, w, h in items:
        anchor = first_fit(grid_w, grid_h, occupied, w, h)
        if anchor is None:
            return None
        placed = Placement(item_id, anchor[0], anchor[1], w, h)
        placements.append(placed)
        occupied |= placed.cells()
    return placements


def occupancy(placements: list[Placement]) -> set[Cell]:
    """Every cell covered by the placements — rebuild state from a save."""
    covered: set[Cell] = set()
    for placed in placements:
        covered |= placed.cells()
    return covered


def net_power(base_gen: int, bonuses) -> int:
    """The signed resting net: hull base plus every watt contribution.

    ``bonuses`` is the per-item list of effective ``power_gen_bonus``
    values (upkeep negative). The gate reads THIS signed number — the
    combat pool (``combat._stats._calc_power_gen``) clamps at zero,
    and the resting gate must see the debt to refuse it (doc 56).
    """
    return base_gen + sum(bonuses)


def power_legal(base_gen: int, bonuses) -> bool:
    """The resting power gate: the signed net must be non-negative."""
    return net_power(base_gen, bonuses) >= 0
