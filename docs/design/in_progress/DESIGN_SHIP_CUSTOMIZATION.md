# Ship Customization — Manage Loadout at the Mechanic Terminal

## Overview

The Mechanic Terminal currently offers Refuel and Repair. This feature adds **Manage Loadout** — a sub-modal where the player can view installed weapons/modules, sell/remove them, and buy/install new ones from the mechanic's catalog.

This is a 4-phase feature that touches `menus.py` (the mechanic terminal), `ship.py` (OwnedShip validation), `data/weapons/` (add price field), and `__main__.py` (starting loadout).

## Philosophy alignment

| Principle | Adherence |
|-----------|-----------|
| **ctx-first** | All state accessed via `ctx.player_owned_ship`, `ctx.stats.credits`, etc. |
| **Data-first** | Mechanic's catalog built from `data/weapons/*.py` + `data/modules/*.py` — no hardcoded part lists |
| **Live-by-side-effect** | `_install_weapon()`, `_remove_weapon()`, etc. mutate OwnedShip and log; callers apply state |
| **Modal pattern** | Sub-modal uses `ui.Modal` for loadout management, nested inside the mechanic's `while True` loop |
| **Simplicity** | Parts are bought/sold directly — no intermediate inventory. Buy = install + pay. Sell = remove + receive credits. |

## Data model changes

### Phase 1: Add `price` to `WeaponSpec`

Currently `ModuleSpec` has a `price` field but `WeaponSpec` does not. Add:

```python
@dataclass(frozen=True)
class WeaponSpec:
    ...
    price: int = 0    # NEW — credits cost to buy
```

Update all weapon definitions in `data/weapons/lasers.py` and `data/weapons/missiles.py` with prices:

| Weapon | Price |
|--------|-------|
| Light Laser | 30$ |
| Heavy Laser | 60$ |
| Plasma Cannon | 100$ |
| Light Missile | 25$ |
| Heavy Missile | 50$ |
| EMP Missile | 75$ |

### No new catalog needed

The mechanic sells from the existing weapon and module catalogs. No new data files required. The "mechanic's catalog" is simply `list_weapons() + list_modules()` filtered by slot compatibility.

## Domain changes

### OwnedShip mutation helpers (ship.py)

Module-level helpers for UI to call directly — no Outcome enum indirection needed:

```python
def _install_weapon(owned: OwnedShip, weapon_id: str, ship_spec: Ship) -> bool:
    """Install weapon into first empty slot. Return True on success.
    Recalculates cargo_ammo if the weapon is a missile type."""

def _remove_weapon(owned: OwnedShip, index: int, ship_spec: Ship) -> tuple[str, ...]:
    """Remove weapon at index. Returns updated weapon tuple.
    Recalculates cargo_ammo."""

def _install_module(owned: OwnedShip, module_id: str, ship_spec: Ship) -> bool:
    """Install module into first empty slot. Return True on success."""

def _remove_module(owned: OwnedShip, index: int) -> tuple[str, ...]:
    """Remove module at index. Returns updated module tuple."""

def _sell_price(item_type: str, item_id: str) -> int:
    """Sell-back value: 50% of buy price, rounded down."""

def _find_weapon_slots(owned, ship_spec) -> list[tuple[str | None, int]]:
    """Return [(weapon_id or None, slot_index), ...] for all weapon slots."""

def _find_module_slots(owned, ship_spec) -> list[tuple[str | None, int]]:
    """Return [(module_id or None, slot_index), ...] for all module slots."""
```

**Invariant:** `len(owned.weapons) <= ship_spec.weapon_slots` and `len(owned.modules) <= ship_spec.module_slots` must hold after every operation.

### Ammo recalculation

When a missile weapon is removed or installed, `owned.cargo_ammo` must be recalculated via `ship_module.total_ammo_cargo(owned.weapons)`. This is already handled by `OwnedShip.__post_init__`, but since `weapons` is a tuple (immutable), we need to recreate it. The `install_weapon` / `remove_weapon` helpers handle this.

## Mechanic Terminal changes (menus.py)

The mechanic terminal's option list expands from 2 to 3:

```python
_MECH_OPTIONS = ["Refuel", "Repair", "Manage Loadout"]
```

Selecting "Manage Loadout" opens a sub-modal (`_run_loadout_menu(ctx)`) with the **same split-screen UX as the trade terminal**:

### Screen layout

```
╔═══════════════════════════════════════════════════╗
║          MECHANIC — SHIP LOADOUT                 ║
╠══════════════════════╤═══════════════════════════╣
║  FOR SALE            │  MY SHIP                  ║
║                      │                           ║
║  ─ WEAPONS ─         │  ─ WEAPON SLOTS (2/4) ─  ║
║  Light Laser    30$  │  Light Laser     (sell 15$)║
║  Heavy Laser    60$  │  Heavy Laser     (sell 30$)║
║  Plasma Cannon 100$  │  [empty]                  ║
║  Light Missile  25$  │  [empty]                  ║
║  Heavy Missile  50$  │                           ║
║  EMP Missile    75$  │  ─ MODULE SLOTS (1/4) ─   ║
║                      │  Compact Reactor (sell 25$)║
║  ─ MODULES ─         │  [empty]                  ║
║  Compact Reactor 50$ │  [empty]                  ║
║  Heavy Reactor  120$ │  [empty]                  ║
║  Shield Mk.1     60$ │                           ║
║  Shield Cap.     80$ │                           ║
║  Shield Rech.   100$ │                           ║
║  Targeting Comp. 70$ │                           ║
║  Gyro Stabil.    70$ │                           ║
║  Expanded Cargo  40$ │                           ║
║  Armor Plating   90$ │                           ║
╠══════════════════════╧═══════════════════════════╣
║  Credits: 1200$                                   ║
║  UP/DOWN navigate  TAB switch panel  ENTER buy/sell  ESC back ║
╚═══════════════════════════════════════════════════╝
```

### Interaction model

| Action | Left panel (For Sale) | Right panel (My Ship) |
|--------|----------------------|----------------------|
| **ENTER** | Buy + install selected part | Sell selected installed part |
| **TAB** | Switch to right panel | Switch to left panel |
| **UP/DOWN** | Navigate items | Navigate slots |
| **ESC** | Back to mechanic menu | Back to mechanic menu |

### Buying flow (ENTER on left panel)

1. Player navigates to a part in the For Sale list
2. Presses ENTER
3. Validation checks: enough credits? empty slot of correct type?
4. If passes: deduct credits, install part into first empty slot
5. Log: `"Installed Light Laser for 30$."`
6. Re-render both panels (left shows still-available parts, right shows new slot state)

If validation fails (no credits, no free slot): log the reason and stay in the menu.

### Selling flow (ENTER on right panel)

1. Player navigates to an installed part in My Ship
2. Presses ENTER
3. Validation checks: is this slot occupied?
4. If passes: remove part, add 50% sell-back credits
5. Log: `"Sold Light Laser for 15$."`
6. Re-render both panels (right shows now-empty slot, left shows part again)

Pressing ENTER on an empty slot is a no-op (logged).

### Price display

- **For Sale:** Shows buy price (full price from spec)
- **My Ship:** Shows sell-back value in dim text: `(sell 15$)`

## Slot compatibility rules

### Weapons

- Any weapon fits in any empty weapon slot.
- No slot-type restriction per slot (all slots accept energy OR missile).
- Exception: if `len(owned.weapons) >= ship_spec.weapon_slots`, no more can be installed.

### Modules

Modules have `slot_type: "engine" | "system"`. The mechanic panel currently groups them on the right side together (simplified view). Module slots are not typed — any module fits in any empty module slot. Future enhancement could add typed slots.

- If `len(owned.modules) >= ship_spec.module_slots`, no more can be installed.

## Sell pricing

- Weapons and modules sell back at **50% of buy price**, rounded down.
- `sell_price = max(1, buy_price // 2)`
- Selling opens cargo space (for modules that affect cargo) and reduces stat bonuses.

## Phased implementation plan + playtest checklists

---

### Phase 1 — Data model prep

- [x] Add `price` field to `WeaponSpec` (default 0)
- [x] Set prices on all 6 weapons in `lasers.py` and `missiles.py`
- [x] Verify `ModuleSpec.price` is already present (it is)

**▸ PLAYTEST Phase 1:**

Run the smoke gate. Then verify no visual change to the game — prices are data-only and not yet shown in any UI. Start a new game, walk around, open the trade terminal, launch to space, bump a planet. Everything should work exactly as before.

Passed: [x]   Issues: none — data-only, smoke test passed, no visual change.

---

### Phase 2 — Ship mutation helpers

- [ ] Add `_install_weapon()`, `_remove_weapon()` to `ship.py`
- [ ] Add `_install_module()`, `_remove_module()` to `ship.py`
- [ ] Add `_sell_price()` helper to `ship.py`
- [ ] Add `_find_weapon_slots()`, `_find_module_slots()` to `ship.py`
- [ ] Ensure `total_ammo_cargo()` is called after weapon changes
- [ ] Ensure `len(owned.weapons) <= ship_spec.weapon_slots` invariant
- [ ] Ensure `len(owned.modules) <= ship_spec.module_slots` invariant

**▸ PLAYTEST Phase 2:**

Run the smoke gate. Then verify no visual change — these are pure helpers with no UI yet. Same as Phase 1: start a game, walk around, everything works as before.

The smoke gate is the real test here (it checks imports resolve and signatures are correct).

Passed: [ ]   Issues: _______________

---

### Phase 3 — DRY refactor (extract shared split-screen primitives)

Before the loadout UI, extract shared code from `trade.py` so we don't duplicate the split-screen pattern:

| Candidate | Current home | Where it should go |
|-----------|-------------|-------------------|
| `_render_trade_frame()` | `trade.py` | Shared module (e.g. `ui.py`) — two-panel layout, separator, headers, footer |
| `_format_trade_line()` | `trade.py` | Shared module — row formatting |
| `_paint_text()` / `_paint_centered()` | `trade.py` | Shared module — low-level render |
| `focus`/`sel` nav pattern | `trade.py` | Shared module — UP/DOWN/TAB switching |

- [ ] Extract `_render_trade_frame()` (or a more generic version) into `ui.py`
- [ ] Extract `_format_trade_line()` into `ui.py`
- [ ] Extract `_paint_text()` / `_paint_centered()` into `ui.py`
- [ ] Extract split-screen nav handling into `ui.py`
- [ ] Refactor `trade.py` to call the shared versions
- [ ] Run smoke gate

**▸ PLAYTEST Phase 3 (DRY refactor):**

Start a new game, buy a ship, launch to space. Find a planet with a trade terminal (Earth), dock, bump the terminal. The trade UI should look and behave identically to before — buy/sell goods, TAB to switch panels, UP/DOWN to navigate, ESC to exit. No visual or functional regression.

- [ ] Trade terminal opens and shows two-panel layout
- [ ] Tab switches between panels
- [ ] Up/down navigates within a panel
- [ ] Buy a good (ENTER on left panel) — credits deducted, cargo added
- [ ] Sell a good (ENTER on right panel) — credits added, cargo removed
- [ ] ESC back to city view

Passed: [ ]   Issues: _______________

---

### Phase 3b — "Manage Loadout" UI

- [ ] Add "Manage Loadout" to `_MECH_OPTIONS`
- [ ] Implement split-screen loadout modal (`_run_loadout_menu`)
- [ ] Left panel: weapons list, `───` divider, modules list (all "For Sale" with prices)
- [ ] Right panel: weapon slots with installed/`[empty]`, `───` divider, module slots with installed/`[empty]`
- [ ] Each slot shows sell-back val in dim: `(sell 15$)`
- [ ] Navigation: UP/DOWN within panel, TAB switches panels
- [ ] Buy flow: ENTER on left panel -> validate credits + empty slot -> deduct + install
- [ ] Sell flow: ENTER on right panel -> validate occupied -> remove + refund 50%
- [ ] Log messages for all buy/sell/error/no-op events
- [ ] Missile weapon changes recalculate `cargo_ammo`
- [ ] ESC back to mechanic menu (Refuel / Repair still work)

**▸ PLAYTEST Phase 3b:**

New game, Earth hangar, buy a ship (any ship). Walk to the mechanic terminal, bump it.

- [ ] "Manage Loadout" appears as 3rd option after Refuel and Repair
- [ ] Select it — left panel shows weapons (fast) then `───` then modules (mech catalog)
- [ ] Right panel shows your ship's weapon slots (installed items listed, empty slots show `[empty]`)
- [ ] Right panel shows `───` then module slots (same pattern)
- [ ] Navigate ENTIRE left list with DOWN arrow — scrolls past weapons into modules
- [ ] Navigate ENTIRE right list — scrolls past weapons into modules
- [ ] TAB to right panel, navigate to an installed weapon, press ENTER
      → credits added (50% of buy price), slot now shows `[empty]`
      → log says "Sold Light Laser for 15$."
- [ ] TAB to left panel, buy a different weapon
      → credits deducted, weapon installed in the now-empty slot
      → log says "Installed Heavy Laser for 60$."
- [ ] Buy until weapon slots full → verify error message
- [ ] Sell a module, buy a different module → same pattern works
- [ ] Buy a module when module slots full → verify error
- [ ] ESC back → Refuel and Repair still work
- [ ] ESC back to city, launch to space, enter combat → new loadout is used

Passed: [ ]   Issues: _______________

---

### Phase 4 — Integration + starting loadout

- [ ] Update starting loadout in `__main__.py` to a balanced subset (e.g. 2 energy + 2 missile, not all 6)
- [ ] Starting credits should be enough to buy modules/weapons at the mechanic (optional)
- [ ] Final smoke test
- [ ] Final playtest: full buy/sell cycle + combat with modified loadout
- [ ] Update design doc status — move to `docs/design/complete/` if all checkboxes checked

**▸ PLAYTEST Phase 4:**

Exit any current game. Start a COMPLETELY NEW GAME (so the new starting loadout applies).

- [ ] New game ship has fewer weapons (e.g. 4 instead of 6)
- [ ] Walk to mechanic, buy a weapon → installs correctly
- [ ] Sell a starter weapon → frees a slot, get credits back
- [ ] Launch to space, enter combat → only installed weapons appear in combat HUD
- [ ] Combat works end-to-end (fire, kill enemy, return)
- [ ] ESC to quit, no crashes

Passed: [ ]   Issues: _______________

---

## Acceptance criteria (final sign-off)

1. [ ] Player can see all weapons and modules available from the mechanic
2. [ ] Player can buy and install parts (credits deducted, slot consumed)
3. [ ] Player can sell installed parts (credits added, slot freed)
4. [ ] Slot limits enforced (can't install more than `weapon_slots` / `module_slots`)
5. [ ] Cargo ammo recalculated when missile weapons change
6. [ ] Combat reads the updated loadout correctly
7. [ ] Starting loadout is a reasonable subset (not all 6 weapons)
8. [ ] All existing mechanics (Refuel, Repair) still work
9. [ ] DRY: no duplicated split-screen code between trade and loadout