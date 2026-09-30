#!/usr/bin/env python3
"""Doc 56 fixture renderer: each hull's fitting grid with its start
loadout placed as letter blocks — or, with ``--save PATH``, the LIVE
grid of a saved ship (the phase-2 stand-in for the phase-3 editor
pane: the modal auto-places invisibly, this shows where everything
landed, plus the resting net power).

The glyph letters (doc 56 SETTLED 15): S/R/T/G/C/A/H module
families, L/M/P/E weapons, '.' empty. Still deliberately NOT pinned
by any test — phase 3's editor owns the in-game letter+colour
treatment; this tool just renders fixtures.

Placement comes from ``ship.start_fitted_entries`` (start fixtures)
or the save's serialized ``grid_x``/``grid_y`` (live ships) — never
this tool's own placement loop (doc 56 audit hotspot 2).

Usage:
    python3 tools/fitting_render.py [hull_id ...]     # default: every hull
    python3 tools/fitting_render.py --save PATH       # a saved ship's grid
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.spacehack.data.ships import find_ship, list_ships  # noqa: E402
from src.spacehack.ship import resting_power, start_fitted_entries  # noqa: E402

# SETTLED 15's ruling. Shield capacitor/recharger fold into the
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


def _spec_of(entry):
    from src.spacehack.data.modules import find_module
    from src.spacehack.data.weapons import find_weapon

    finder = find_weapon if entry.item_type == "weapon" else find_module
    return finder(entry.item_id)


def _render_grid(ship, entries, extra_header: str = "") -> str:
    """One grid fixture: header, rows, legend — over placed entries."""
    paint = {}
    unplaced = []
    for entry in entries:
        spec = _spec_of(entry)
        if entry.grid_x is None or entry.grid_y is None:
            unplaced.append(entry)
            continue
        for cx in range(entry.grid_x, entry.grid_x + spec.grid_w):
            for cy in range(entry.grid_y, entry.grid_y + spec.grid_h):
                paint[(cx, cy)] = LETTERS[entry.item_id]
    total = ship.grid_w * ship.grid_h
    lines = [
        f"=== {ship.name} ({ship.id}) - grid {ship.grid_w}x{ship.grid_h}, "
        f"{len(paint)}/{total} cells used ==={extra_header}"
    ]
    for y in range(ship.grid_h):
        lines.append(" ".join(paint.get((x, y), ".") for x in range(ship.grid_w)))
    for entry in entries:
        spec = _spec_of(entry)
        anchor = (
            f"({entry.grid_x},{entry.grid_y})"
            if entry.grid_x is not None else "UNPLACED"
        )
        lines.append(
            f"  {LETTERS[entry.item_id]}  {spec.name:26s} "
            f"{anchor} {spec.grid_w}x{spec.grid_h}"
        )
    if unplaced:
        lines.append("  (!) unplaced entries strip to storage at next load")
    return "\n".join(lines)


def render_ship(ship) -> str:
    """One hull's fixture: its start loadout through the resolver."""
    weapons, modules = start_fitted_entries(ship)
    entries = (*weapons, *modules)
    if any(e.grid_x is None or e.grid_y is None for e in entries):
        return f"=== {ship.name} ({ship.id}) - START LOADOUT DOES NOT PACK ==="
    return _render_grid(ship, entries)


def render_saved_ship(path: str) -> str:
    """A saved ship's live grid: the serialized anchors, verbatim."""
    from src.spacehack.saveload_ship import _parse_owned_ship

    owned = _parse_owned_ship(json.loads(Path(path).read_text()))
    if owned is None:
        return f"=== {path}: no owned ship in save ==="
    ship = find_ship(owned.ship_id)
    net = resting_power(owned, ship)
    return _render_grid(
        ship, (*owned.weapons, *owned.modules),
        extra_header=f"  net power {net:+d}",
    )


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "--save":
        print(render_saved_ship(argv[1]))
        return 0
    hulls = [find_ship(hull_id) for hull_id in argv] or list_ships()
    blocks = [render_ship(ship) for ship in hulls]
    print("\n\n".join(blocks))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
