# DESIGN: Ship Equipment Storage and Loadout Transfer

> **Status:** In progress. This document is the contract for the first
> inventory/storage pass and is intentionally UI-iterative.

## Overview

Rare ship equipment should remain valuable after a ship upgrade. If the player
finds a Shield Mk. 4 and installs it on a Scout, buying a Cruiser must not
silently destroy that shield. The player should be able to unequip equipment,
place it in persistent storage, and attach it to a later ship.

The first version adds a global ship-equipment locker. It stores weapons and
modules independently from the currently active ship. The locker is deliberately
unlimited at first so the system solves the loss/retention problem before we add
capacity pressure or a more elaborate inventory economy.

The UI/UX is expected to evolve through playtesting. The initial presentation
should make the ownership distinction obvious:

- **Store:** catalog equipment available at the current mechanic.
- **Storage:** equipment the player owns but is not currently using.
- **My Ship:** equipment installed on the active ship; Enter opens Store/Sell.

The first implementation does not add rarity, random prefixes, item modifiers,
or a separate generated-item economy. "Finding a rare Shield Mk. 4" is the
motivating case; the equipment remains a normal catalog item identified by its
stable module or weapon ID.

## Design decisions (locked)

| Decision | Choice |
|----------|--------|
| **Storage scope** | One global locker accessible from every mechanic/ship terminal. |
| **Capacity** | Unlimited in the first version. Capacity may be designed later after playtesting. |
| **Equipment identity** | Catalog ID plus any state needed by the equipment, initially missile ammo. No rarity/modifier system yet. |
| **Equipment types** | Weapons and ship modules. Trade goods remain in the ship cargo inventory and are not mixed into this locker. |
| **Ship upgrade behavior** | Old installed equipment moves into storage when the player buys a new ship; it is not sold or destroyed as part of the trade-in. |
| **Starting loadout** | The purchased ship keeps its catalog-defined starting loadout. The old ship's equipment is added to storage, even when the new ship starts with similar parts. |
| **Selling** | Selling is always an explicit action. Storing and selling are separate actions and must not share an accidental fallback. |
| **Ammo** | A stored missile launcher retains its current magazine. Reinstalling it restores the saved rounds to its new weapon slot. |
| **Backward compatibility** | Existing saves load with an empty storage locker. Existing installed equipment remains installed exactly as before. |

## Philosophy alignment

| Principle | Application |
|----------|-------------|
| **Data-first** | Stored entries reference the existing weapon/module catalogs by stable ID; no duplicated static equipment specs live in runtime code. |
| **ctx-first** | The locker is one `GameContext` field, not a module-level inventory global. |
| **Pure computation** | Slot compatibility, storage-entry display, ammo transfer, and equipment re-indexing remain pure or narrowly testable mutation helpers. |
| **Explicit mutation** | Store, install, sell, and ship-upgrade transfer are named actions with no implicit destruction path. |
| **Save/load safety** | The locker, installed equipment, and missile ammo survive Continue without duplication or loss. |
| **UI iteration** | Presentation is separated from storage mutation so tabs, split panels, confirmations, and labels can change after playtesting without rewriting the equipment model. |
| **Reuse** | Existing `OwnedShip`, mechanic loadout, ship hangar, catalog lookup, and save/load paths are extended rather than duplicated. |

## Pre-implementation audit

### Existing classes/modules to extend or reuse

- `src/spacehack/ship.py`: `OwnedShip` is the existing mutable owner of
  installed weapons, modules, and slot-indexed missile ammo. Reuse
  `_install_weapon`, `_remove_weapon`, `_install_module`, `_remove_module`,
  `_find_weapon_slots`, `_find_module_slots`, and `total_ammo_cargo` rather
  than creating a second loadout implementation.
- `src/spacehack/game_context.py`: `GameContext` is the correct home for one
  persistent `ship_storage` field. The field should contain storage entries,
  not catalog specs or UI state.
- `src/spacehack/saveload.py`: `_ctx_to_dict`, `load_game`, and the existing
  `OwnedShip` serialization are the save/load seam. New storage fields need
  both serialization and deserialization with an empty default for old saves.
- `src/spacehack/menus/_loadout.py`: `_pygame_loadout_frame`,
  `_apply_pygame_loadout_action`, and `_run_loadout_menu` already render and
  mutate mechanic equipment. The first storage UI should extend this flow.
- `src/spacehack/menus/_mechanic.py`: the mechanic terminal owns the current
  mechanic tabs and routes into the loadout modal. Reuse its terminal entry
  pattern and current planet inventory lookup.
- `src/spacehack/menus/_ship_menu.py`: the hangar's SHIP/CARGO/LOADOUT tabs
  already show installed equipment and are a likely later place to expose a
  read-only or management shortcut to storage.
- `src/spacehack/menus/_ship_buy.py` and `src/spacehack/__main__.py`: the ship
  purchase/trade-in flow currently creates a replacement `OwnedShip` from
  `start_weapons` and `start_modules`. The upgrade handoff must move old
  equipment into storage before replacing the owned ship.
- `src/spacehack/data/weapons/` and `src/spacehack/data/modules/`: existing
  `find_weapon`, `find_module`, and catalog specs provide stable IDs, names,
  prices, slot types, descriptions, and missile capacity.
- `src/spacehack/combat/_actions.py`: `_sync_back_ammo` defines the existing
  slot-indexed ammo persistence contract that storage must preserve when a
  launcher leaves or re-enters a ship.
- `tests/test_ship_mutation.py`: existing weapon removal/install tests are the
  regression anchor for slot re-indexing and ammo behavior.
- `tests/test_saveload.py`: existing `OwnedShip` round-trip coverage should be
  extended to prove storage survives save/Continue.
- `tests/test_pygame_ui.py` and `tests/test_mechanic.py`: existing Pygame
  mechanic/loadout frame tests are the UI regression anchors.

### Three potential duplication hotspots

1. **A second equipment mutation system** could be created for storage instead
   of using the current installed-slot helpers.
   - **DRY strategy:** define small storage-aware orchestration helpers around
     the existing `_install_*` and `_remove_*` primitives. Keep slot mutation in
     `ship.py` and make storage actions call those helpers rather than editing
     tuples independently in the UI.

2. **Ship upgrade transfer** could duplicate weapon/module/ammo migration logic
   separately from the manual Store action.
   - **DRY strategy:** extract one `move_installed_equipment_to_storage` helper
     that converts the current ship's installed slots into storage entries and
     clears the loadout safely. The ship-buy path and a future "store all"
     action both call that helper.

3. **Storage rendering** could duplicate catalog lookup, slot compatibility,
   and item-description formatting across the mechanic and hangar screens.
   - **DRY strategy:** provide shared storage-row/view-model helpers that return
     immutable presentation data. Each modal chooses its layout while using the
     same labels, compatibility checks, and ammo display.

4. **Save/load migration** could serialize storage differently from the active
   ship and accidentally lose missile ammo or duplicate entries.
   - **DRY strategy:** serialize a storage-entry dataclass through the existing
     recursive `_d` helper and add one focused round-trip test covering duplicate
     IDs plus a partially spent missile launcher.

## Data model

### Stored equipment entry

The first implementation should use a runtime dataclass representing one owned
stored part:

```python
@dataclass
class StoredEquipment:
    item_type: str       # "weapon" or "module"
    item_id: str         # catalog ID, e.g. "shield_mk4"
    ammo: int | None = None
```

`ammo` is meaningful only for missile weapons. Energy weapons and modules use
`None`. A list of entries is preferable to a count dictionary even though most
items are currently stateless: it preserves duplicate equipment as distinct
owned parts and leaves room for future per-item state without forcing a second
migration.

The first version does **not** add a rarity or modifier field. If a later design
introduces a genuinely unique item, the entry can grow to include explicit
state rather than changing the meaning of the catalog ID.

### GameContext ownership

Add one field conceptually equivalent to:

```python
ship_storage: list[StoredEquipment] = field(default_factory=list)
```

The exact class name and field naming may be refined during Phase 1, but the
ownership contract is fixed: storage belongs to the player, not to a planet,
ship entity, mechanic terminal, or module-level session state.

### Equipment movement rules

#### Store an installed part

1. Read the installed weapon/module at the selected slot.
2. Capture its catalog ID.
3. For missile weapons, capture the current slot-indexed ammo.
4. Append one storage entry.
5. Remove the installed item through the existing removal helper so weapon
   slots and ammo indices above it re-index correctly.
6. Log the resulting action.

The operation must be atomic from the player's perspective: if the storage
append or slot mutation cannot complete, neither side should silently lose the
part.

#### Install from storage

1. Validate that the active ship has a compatible empty slot.
2. Remove the selected storage entry.
3. Install the catalog ID through the existing installation helper.
4. Restore stored missile ammo to the newly assigned weapon slot.
5. Log the result.

If the ship has no compatible slot, the entry remains in storage unchanged.

#### Ship upgrade transfer

When a ship purchase succeeds and an owned ship exists:

1. Move every currently installed weapon and module from the old ship to
   storage, including missile ammo.
2. Preserve mission-reserved cargo according to the existing trade-in rules.
3. Create the purchased ship with its normal `start_weapons` and
   `start_modules`.
4. Leave the stored old equipment available for later installation.
5. Do not include installed equipment in the current hull trade-in calculation;
   the parts remain owned rather than being sold.

The transfer must happen only after the purchase is affordable and confirmed.
Backing out or failing affordability must not mutate either ship or storage.

## Domain changes

### Ship domain

- Add the stored-equipment dataclass and storage mutation helpers.
- Add compatibility checks for weapon/module slot types and available slots.
- Add a shared installed-to-storage transfer helper for ship upgrades.
- Preserve the existing slot-indexed missile-ammo contract.
- Keep computation and mutation separate where practical so edge cases are
  directly testable.

### Game context

- Add one `ship_storage` field with an empty default.
- Update the field ownership documentation in `GameContext`.
- Do not add module-level storage state.

### Save/load

- Serialize `ship_storage` in `_ctx_to_dict`.
- Restore it in `load_game` with `[]` for old saves.
- Preserve duplicate entries and partial missile ammo exactly.
- Add migration-tolerant defaults for malformed/legacy entries where practical;
  invalid catalog IDs should not crash Continue, but should be visible to tests
  and not silently become a different item.

### Mechanic and hangar UI

First UI pass should extend the existing mechanic loadout rather than introduce
an entirely new terminal:

- Add a `STORAGE` view/tab alongside `STORE` and `MY SHIP`, or use the
  closest equivalent supported by the current split-screen component.
- Show item name, type, and useful details; show remaining ammo for missile
  launchers.
- Make actions explicit: `STORE`, `INSTALL`, and `SELL`.
- Keep unavailable install actions readable rather than silently ignoring an
  incompatible selection.
- Preserve existing buy and sell behavior while making storage clearly
  separate from selling.

The first layout is provisional. After playtesting, the storage view may move
to the hangar tab set, become a full-screen inventory, or gain filters/grouping
without changing the storage domain contract.

### Ship upgrade flow

- Replace the current implicit loss of old installed equipment with the shared
  storage-transfer helper.
- Add a purchase/upgrade log message that tells the player equipment was moved
  to storage.
- Ensure the new ship's entity, `OwnedShip`, cargo reservations, and HUD all
  continue to reference the replacement ship.

### Guide/UI documentation

Add a guide section for:

- Storage is global and unlimited in the first version.
- Store equipment instead of selling it when upgrading ships.
- Stored parts can be installed later if the new ship has a compatible slot.
- Missile launchers retain their remaining ammunition in storage.
- Ship trade-ins do not destroy installed equipment.

## Phased implementation plan

### Phase 1 - Storage model, mutation, and save/load

- [x] Add the stored-equipment data model.
- [x] Add `GameContext.ship_storage` with an empty default.
- [x] Add pure compatibility/display helpers and tested storage mutation
  wrappers for weapons, modules, and missile ammo.
- [x] Add save/load serialization with old-save defaults.
- [x] Add unit tests for duplicate parts, partial missile ammo, incompatible
  slots, empty storage, invalid indexes, and round-trip persistence.

**PLAYTEST:** No major UI yet. Start a new game, save, Continue, and confirm the
new empty storage state does not change existing ship behavior. If a developer
fixture or temporary test setup populates storage, verify it survives save/load
without changing installed equipment.

**Implementation checkpoint:** Phase 1 backend storage is implemented. `StoredEquipment`
keeps duplicate parts distinct and preserves partial missile ammo; `GameContext`
owns a global locker; malformed or unknown storage records are ignored during
load; old saves default to an empty locker. Focused mutation and save/load tests
cover storage, and the existing UI remains unchanged. Automated validation:
`python3 tools/smoke.py` passes and `python3 tools/test.py` passes with 678 tests.
Manual playtest of the empty-locker Continue path remains before Phase 2.

### Phase 2 - First storage UI

- [x] Add a first-pass Storage view to the mechanic loadout flow.
- [x] Add the My Ship Store/Sell chooser for installed weapons/modules.
- [x] Add the compact Install/Sell chooser for stored weapons/modules.
- [x] Add visible remaining-ammo text for stored missile launchers.
- [x] Keep Sell inside compact My Ship and Storage choosers and preserve current mechanic purchase behavior.
- [x] Replace the View toggle with Buy/Storage header tabs and B/S shortcuts.

**PLAYTEST:** At a mechanic, install a cheap weapon/module, open Storage, store
it, verify it disappears from My Ship and appears in Storage, then install it
again. Try an incompatible or full slot and verify the item remains stored with
a clear message. Store a missile launcher with spent ammo and verify its ammo
returns when reinstalled. Also switch to SELL explicitly and verify selling a
stored part does not affect installed equipment.

**Implementation checkpoint:**Phase 2 adds a first-pass two-view loadout modal: STORE and STORAGE. The left header uses [B]uy and [S]torage tabs; B and S switch modes directly. Installed My Ship rows are intentionally minimal; ENTER opens a small shared-Pygame chooser with Store and Sell for X$, and Escape leaves the part unchanged. Storage rows open a compact chooser with Install and Sell for X$.

Stored missile launchers display remaining ammo, and failed installs leave storage
unchanged with a log explanation. The guide now documents the storage workflow
and the Store/Sell chooser. Focused UI, mechanic, and ship mutation validation
passes; manual playtest of the complete chooser -> Store/Install lifecycle remains
before Phase 3.


### Phase 3 - Ship upgrade preservation

- [ ] Route successful ship purchases through the installed-equipment transfer
  helper.
- [ ] Move all old weapons/modules and missile ammo into storage before the new
  ship becomes active.
- [ ] Preserve mission cargo reservations and existing trade-in pricing rules.
- [ ] Add upgrade-flow regression tests for affordability failure, cancel/back,
  duplicate equipment, full storage semantics, and successful transfer.

**PLAYTEST:** Install a rare module such as Shield Mk. 4 on the current ship,
then buy a larger ship. Confirm the old shield is in Storage, the new ship has
its expected starting loadout, and the shield can be installed if a compatible
slot is available. Save/Continue between the purchase and reinstallation and
verify the shield is still present exactly once.

### Phase 4 - UX iteration, guide, and regression pass

- [ ] Playtest the first UI with the full equipment progression and revise the
  layout, labels, hints, and confirmation behavior.
- [ ] Decide whether storage belongs in the mechanic split view, the hangar tab
  set, or both.
- [ ] Add the guide section and update the ship/equipment help text.
- [ ] Add final tests for the selected UX action mapping and edge cases.
- [ ] Run `python3 tools/smoke.py` and `python3 tools/test.py`.

**PLAYTEST:** Run a full equipment lifecycle: find or buy equipment, install it,
spend missile ammo, store it, upgrade ships multiple times, reinstall it, sell a
different part, save/Continue at each stage, and verify no equipment duplicates,
disappears, or changes ammo unexpectedly. Record UI friction and revise this
doc before declaring the feature complete.

## Acceptance criteria

- A player can unequip a weapon or module without selling or destroying it.
- Stored equipment is global, persistent, and unlimited in the first version.
- A stored weapon/module can be installed on a compatible later ship.
- Duplicate equipment remains distinct and is not collapsed or lost.
- Stored missile launchers retain their current ammo.
- Buying a new ship never silently destroys installed old equipment.
- Cancelled or unaffordable upgrades do not mutate the old ship or storage.
- Existing saves load successfully with empty storage by default.
- Storage survives save/load with exact contents and ammo state.
- The UI clearly distinguishes buying, storing, installing, and selling.
- The guide explains the storage behavior and upgrade-preservation rule.
- Smoke and the full test suite pass.

## Open questions for UI iteration

These are intentionally deferred until the first playable UI exists:

1. Should Storage be a third split-screen column/tab, a hangar tab, or both?
2. Should Store/Install require confirmation, or should the action be reversible
   enough that immediate execution is clearer?
3. Should stored equipment be sorted by type, name, price, or slot compatibility?
4. Should the Storage view show a count for duplicates, or individual rows for
   every owned part?
5. Should a full incompatible loadout offer a quick "Store all" operation?
6. Should the player eventually pay a service fee to transfer or install stored
   equipment? No fee is planned for the first pass.

## Current status

Phase 2 implementation is complete pending manual playtest. Phase 1 established
the persistent storage backend; Phase 2 adds the first iterative mechanic UI.
UI details are expected to change after playtesting; the persistent ownership
and no-silent-destruction rules are the stable core.
