#!/usr/bin/env python3
"""Doc 56 phase-1 fixture: render each hull's fitting grid with its
start loadout placed as letter blocks.

The glyph proposal (doc 56 open question 1): S/R/T/G/C/A/H module
families, L/M/P/E weapons, '.' empty. Deliberately NOT pinned by any
test — the user's eyeball on this output is the ruling session.

Placement always comes from ``fitting.auto_fit`` / ``fitting.footprint``
— this tool never runs its own placement loop (doc 56 audit hotspot 2).

Usage:
    python3 tools/fitting_render.py [hull_id ...]   # default: every hull
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.spacehack.data.modules import find_module  # noqa: E402
from src.spacehack.data.ships import find_ship, list_ships  # noqa: E402
from src.spacehack.data.weapons import find_weapon  # noqa: E402
from src.spacehack.fitting import auto_fit  # noqa: E402

# Open question 1's proposal. Shield capacitor/recharger fold into the
# shield family letter; EMP gets its own E beside the missile M. A new
# catalog id without a letter fails loudly here so the decision is
# made, not defaulted.
LETTERS = {
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


def _start_items(ship):
    weapons = [(wid, find_weapon(wid)) for wid in ship.start_weapons]
    modules = [(mid, find_module(mid)) for mid in ship.start_modules]
    return [
        (item_id, spec.grid_w, spec.grid_h, spec.name)
        for item_id, spec in (*weapons, *modules)
    ]


def render_ship(ship) -> str:
    """One hull's fixture: header, grid rows, legend."""
    items = _start_items(ship)
    placements = auto_fit(
        ship.grid_w, ship.grid_h, [(i, w, h) for i, w, h, _ in items]
    )
    if placements is None:
        return f"=== {ship.name} ({ship.id}) - START LOADOUT DOES NOT PACK ==="
    names = {item_id: name for item_id, _, _, name in items}
    paint = {
        cell: LETTERS[placed.item_id]
        for placed in placements
        for cell in placed.cells()
    }
    used = len(paint)
    total = ship.grid_w * ship.grid_h
    lines = [
        f"=== {ship.name} ({ship.id}) - grid {ship.grid_w}x{ship.grid_h}, "
        f"{used}/{total} cells used ==="
    ]
    for y in range(ship.grid_h):
        lines.append(" ".join(paint.get((x, y), ".") for x in range(ship.grid_w)))
    for placed in placements:
        lines.append(
            f"  {LETTERS[placed.item_id]}  {names[placed.item_id]:26s} "
            f"({placed.x},{placed.y}) {placed.w}x{placed.h}"
        )
    return "\n".join(lines)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    hulls = [find_ship(hull_id) for hull_id in argv] or list_ships()
    blocks = [render_ship(ship) for ship in hulls]
    print("\n\n".join(blocks))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
