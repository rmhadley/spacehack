"""The gated fitting model (doc 56 phase 2) — placements, power, and
the boundary normalization that keeps every resting grid legal.

Split from :mod:`spacehack.ship` as a cohesive sibling (the 1000-line
ratchet fired when the phase-2 model landed): ``ship`` keeps the entry
dataclass and the UNGATED mechanical primitives (``_install_*``,
``_remove_*``, ``store_*``, the strip-all transfer); this module owns
everything that reads the grid or the power budget —

* resting power (the gate's input; combat's pool is its clamp),
* dual interim install legality (slots AND grid AND power),
* gated install/removal seams the loadout modal routes through,
* the shared start-loadout resolver, and
* ``normalize_fitted_grid`` — SETTLED 11/14's load-time repair.

``ship`` re-exports the public names, so existing import sites are
unchanged. Imports of ``ship`` are function-level throughout (the
package's standing pattern) — no import cycle.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from .fitting import auto_fit, first_fit, footprint, in_bounds, net_power

if TYPE_CHECKING:
    from .data.ships import Ship
    from .ship import OwnedShip

# Refusal reasons for the gated install seam. The modal maps them to
# its player-facing strings. Doc 56 phase 3 retired 'slots' with the
# slot summaries: a grid-legal install lands on the grid regardless
# of the legacy slot counts.
INSTALL_REFUSAL_INVALID = "invalid"
INSTALL_REFUSAL_ROOM = "room"
INSTALL_REFUSAL_POWER = "power"


def _entry_spec(entry):
    """Catalog spec for one equipment entry, or None when unknown."""
    from .data.modules import find_module as _fm
    from .data.weapons import find_weapon as _fw

    finders = {"weapon": _fw, "module": _fm}
    finder = finders.get(entry.item_type)
    if finder is None:
        return None
    try:
        return finder(entry.item_id)
    except KeyError:
        return None


def _entry_cells(entry, spec, grid_w: int, grid_h: int) -> set | None:
    """The entry's placed footprint, or None when it claims no legal
    cells (unplaced, unknown, or out of bounds — hand-edited saves)."""
    if spec is None or entry.grid_x is None or entry.grid_y is None:
        return None
    if not in_bounds(
        grid_w, grid_h, entry.grid_x, entry.grid_y, spec.grid_w, spec.grid_h,
    ):
        return None
    return footprint(entry.grid_x, entry.grid_y, spec.grid_w, spec.grid_h)


def occupied_cells(owned: "OwnedShip", grid_w: int, grid_h: int) -> set:
    """Every grid cell covered by installed entries — live occupancy
    for ``first_fit`` installs. Unplaced entries cover nothing; after
    the load-time normalization none exist mid-play."""
    cells: set = set()
    entries = (*getattr(owned, "weapons", ()), *getattr(owned, "modules", ()))
    for entry in entries:
        covered = _entry_cells(entry, _entry_spec(entry), grid_w, grid_h)
        if covered:
            cells |= covered
    return cells


def modules_resting_power(ship_spec: "Ship", modules, ctx=None) -> int:
    """The signed resting net over a module tuple.

    Computed by the SAME quality/randart-scaled sum combat uses
    (``_module_bonus_sum``, function-level — one implementation, no
    drift). Weapons never draw upkeep (doctrine: guns cost power when
    fired, modules cost power to exist). ``_calc_power_gen`` clamps at
    zero for the combat pool; the gate reads this signed value so it
    can see the debt and refuse it.
    """
    from .combat._stats import _module_bonus_sum

    return net_power(
        getattr(ship_spec, "base_power_gen", 3),
        [_module_bonus_sum(modules, "power_gen_bonus")],
    )


def resting_power(owned: "OwnedShip", ship_spec: "Ship", ctx=None) -> int:
    """The ship's signed resting power balance — the gate's input."""
    return modules_resting_power(
        ship_spec, getattr(owned, "modules", ()) or (), ctx,
    )


def install_refusal(owned: "OwnedShip", stored, ship_spec: "Ship", ctx=None) -> str | None:
    """Legality for installing one entry: None when the install is
    legal, else why it is refused — grid room first, then the resting
    power gate. Weapons draw no upkeep, so a weapon install can refuse
    on room but never on power. (Doc 56 phase 3: the slot-count check
    retired with the slot summaries — beyond-slots installs land on
    the grid.)
    """
    spec = _entry_spec(stored)
    if spec is None:
        return INSTALL_REFUSAL_INVALID
    anchor = first_fit(
        ship_spec.grid_w, ship_spec.grid_h,
        occupied_cells(owned, ship_spec.grid_w, ship_spec.grid_h),
        spec.grid_w, spec.grid_h,
    )
    if anchor is None:
        return INSTALL_REFUSAL_ROOM
    if stored.item_type == "module" and modules_resting_power(
        ship_spec, (*getattr(owned, "modules", ()), stored), ctx,
    ) < 0:
        return INSTALL_REFUSAL_POWER
    return None


def gated_install_entry(owned: "OwnedShip", entry, ship_spec: "Ship", ctx=None) -> str | None:
    """Install one entry through the full gate, placement stamped.

    THE commit seam for buy-installs and storage-installs: the refusal
    reason comes back as a string (see ``install_refusal``); success
    stamps the entry's grid anchor via ``first_fit`` over live
    occupancy, so every installed entry is placed.
    """
    reason = install_refusal(owned, entry, ship_spec, ctx)
    if reason is not None:
        return reason
    spec = _entry_spec(entry)
    anchor = first_fit(
        ship_spec.grid_w, ship_spec.grid_h,
        occupied_cells(owned, ship_spec.grid_w, ship_spec.grid_h),
        spec.grid_w, spec.grid_h,
    )
    if anchor is None:
        # Unreachable — install_refusal just passed the same pure
        # state — but fail loudly rather than install an unplaced
        # entry: it would silently strip to storage at the next load.
        raise RuntimeError("fitting gate desynchronized during install")
    placed = dataclasses.replace(entry, grid_x=anchor[0], grid_y=anchor[1])
    if entry.item_type == "weapon":
        from .ship import _install_weapon
        _install_weapon(owned, placed, ctx)
    else:
        from .ship import _install_module
        _install_module(owned, placed)
    return None


def clamp_installed_magazine(owned: "OwnedShip", stored, ctx=None) -> None:
    """Clamp a just-installed missile's STORED ammo onto its new slot.

    ``_install_weapon`` seeds a fresh full magazine; a part installed
    from storage restores the rounds it left with (capped at the
    effective rack). One helper for the storage-install seam and the
    editor's hand-off drop.
    """
    from .data.weapons import find_weapon as _fw
    from .ship import effective_missile_capacity

    if stored.item_type != "weapon" or stored.ammo is None:
        return
    capacity = effective_missile_capacity(_fw(stored.item_id), ctx)
    owned.weapon_ammo[len(owned.weapons) - 1] = max(
        0, min(stored.ammo, capacity),
    )


def install_stored_equipment(
    owned: "OwnedShip",
    storage: list,
    storage_index: int,
    ship_spec: "Ship",
    ctx=None,
) -> bool:
    """Install one stored part through the fitting gate and remove it
    from storage on success (geometry + power gated — AC1's
    fresh-Skiff shield_mk4 refusal lands here).

    Doc 56 phase 3: the modal's live install path is the editor's
    hand-off; THIS seam remains the programmatic install (the balance
    harness refits ships through it, and the phase-2 lint pins ride
    it)."""
    if not 0 <= storage_index < len(storage):
        return False
    stored = storage[storage_index]
    if gated_install_entry(owned, stored, ship_spec, ctx) is not None:
        return False
    clamp_installed_magazine(owned, stored, ctx)
    storage.pop(storage_index)
    return True


def removal_trips_power(
    owned: "OwnedShip",
    ship_spec: "Ship",
    item_type: str,
    slot_index: int,
    ctx=None,
) -> bool:
    """True when removing that installed entry would send the resting
    grid negative (SETTLED 3 — the gate is symmetric on removal).

    Only modules draw upkeep, and only removing a funding generator
    can trip this: storing a shield strictly improves the net.
    """
    if item_type != "module":
        return False
    entries = getattr(owned, "modules", ()) or ()
    if not 0 <= slot_index < len(entries):
        return False
    reduced = entries[:slot_index] + entries[slot_index + 1:]
    return modules_resting_power(ship_spec, reduced, ctx) < 0


def fitted_entries(ship_spec: "Ship", weapon_ids, module_ids):
    """Auto-fitted base-quality entries for an explicit loadout.

    The start-loadout resolver's primitive: ``auto_fit`` stamps every
    anchor in tuple order, so ``weapon_ammo``'s index coupling rides
    for free. A loadout that cannot pack returns UNSTAMPED entries —
    the catalog starts and the dev grant are linted to pack, so live
    callers never see that path (and the load-time normalization
    would strip such entries anyway).
    """
    from .ship import base_module_entries, base_weapon_entries

    weapons = base_weapon_entries(weapon_ids)
    modules = base_module_entries(module_ids)
    sizes = [
        (entry.item_id, spec.grid_w, spec.grid_h)
        for entry, spec in (
            (entry, _entry_spec(entry)) for entry in (*weapons, *modules)
        )
    ]
    stamps = auto_fit(ship_spec.grid_w, ship_spec.grid_h, sizes)
    if stamps is None:
        return weapons, modules
    split = len(weapons)
    return (
        tuple(
            dataclasses.replace(e, grid_x=s.x, grid_y=s.y)
            for e, s in zip(weapons, stamps[:split])
        ),
        tuple(
            dataclasses.replace(e, grid_x=s.x, grid_y=s.y)
            for e, s in zip(modules, stamps[split:])
        ),
    )


def start_fitted_entries(ship_spec: "Ship", ctx=None):
    """THE shared start-loadout resolver: every fresh-ship stamping
    site resolves through here — new game, purchase, the render tool,
    and the lints. One resolver, one placement order."""
    return fitted_entries(ship_spec, ship_spec.start_weapons, ship_spec.start_modules)


def effective_upkeep(entry) -> int:
    """The entry's quality/randart-scaled power contribution (weapons
    read 0 through the callers that build hands — only modules draw
    upkeep). Public since doc 56 phase 3: the loadout editor's as-if
    bonus list is built from per-entry upkeeps."""
    from .data.quality import effective_module_spec

    try:
        return effective_module_spec(
            entry.item_id, entry.quality, entry.randart_seed,
        ).power_gen_bonus
    except KeyError:
        return 0


def _strip_label(kind: str, entry) -> str:
    """The notice-line label for one stripped entry."""
    if kind == "weapon":
        from .ship import weapon_display_name

        return weapon_display_name(entry.item_id, entry.quality)
    from .ship import module_display_name

    return module_display_name(entry.item_id, entry.quality, entry.randart_seed)


def _strip_entries(owned: "OwnedShip", storage: list, drops, ctx=None) -> list[str]:
    """Strip the dropped ``(kind, index)`` entries to storage — highest
    index first so earlier indices stay valid — and return their
    labels in the caller's drop order."""
    from .ship import store_module, store_weapon

    entries_of = {"weapon": owned.weapons, "module": owned.modules}
    labels = []
    for kind, index in drops:
        entries = entries_of[kind]
        if index < len(entries):
            labels.append(_strip_label(kind, entries[index]))
    for kind, index in sorted(drops, key=lambda drop: drop[1], reverse=True):
        if kind == "weapon":
            store_weapon(owned, storage, index, ctx)
        else:
            store_module(owned, storage, index)
    return labels


def normalize_fitted_grid(
    owned: "OwnedShip",
    storage: list,
    ship_spec: "Ship",
    ctx=None,
) -> list[str]:
    """Boundary normalization (SETTLED 11/14): make a loaded grid
    legal, deterministically.

    Unplaced entries strip (14 — old-shape saves); out-of-bounds or
    overlapping placements strip with weapons claiming cells first, so
    a cross-tuple overlap strips the MODULE (one grid, two tuples, one
    rule) and a within-tuple overlap strips the later entry; a
    power-invalid grid then strips highest-upkeep-first, ties by later
    tuple position, until the net is non-negative (11). Returns the
    stripped labels in decision order for the caller's notice line.
    """
    drops: list[tuple[str, int]] = []
    occupied: set = set()
    scanned = [
        *(("weapon", i, e) for i, e in enumerate(owned.weapons)),
        *(("module", i, e) for i, e in enumerate(owned.modules)),
    ]
    for kind, index, entry in scanned:
        covered = _entry_cells(entry, _entry_spec(entry), ship_spec.grid_w, ship_spec.grid_h)
        if covered is None or covered & occupied:
            drops.append((kind, index))
            continue
        occupied |= covered
    labels = _strip_entries(owned, storage, drops, ctx)
    while resting_power(owned, ship_spec, ctx) < 0 and owned.modules:
        worst = min(
            enumerate(owned.modules),
            key=lambda pair: (effective_upkeep(pair[1]), -pair[0]),
        )[0]
        labels.extend(_strip_entries(owned, storage, [("module", worst)], ctx))
    return labels
