# DESIGN: Ground Equipment Storage and Loadout Transfer

> **Status:** In progress. This document is the contract for the first
> persistent ground-equipment inventory pass and is intentionally UI-iterative.

## Overview

Ground equipment should remain valuable after a loadout change. If the player
buys a laser rifle, helmet, or heavy vest, they should be able to remove it
without selling or destroying it, keep it in storage, and equip it later when a
mission or character build calls for it. The system should also make it safe to
buy replacement armor or weapons without silently losing the previous item.

The first version adds a global ground-equipment locker. It stores personal
weapons and armor independently from the currently equipped ground loadout.
The locker is deliberately unlimited at first so the system solves ownership
and retention before adding capacity pressure or a more elaborate inventory
economy.

The UI/UX should build on the existing Pygame armory and character equipment
screens. The first presentation should make the ownership distinction obvious:

**Current implementation gap:** the existing armory directly appends a bought
weapon when fewer than two weapon IDs are equipped and directly overwrites no
armor slot; it does not yet enforce `hands=2`, preserve displaced equipment, or
offer Buy/Store destinations. The rules in this document are the Phase 1+
target contract, not claims about behavior already present. Phase 1 must add the
transactional domain helpers before the armory UI adopts them.

- **Buy:** ground equipment available at the current armory.
- **Storage:** equipment the player owns but is not currently using.
- **My Loadout:** weapons and armor currently equipped for ground combat.

This design covers ground weapons and armor only. Ship equipment remains
covered by `docs/design/complete/17_DESIGN_SHIP_EQUIPMENT_STORAGE.md`.

## Design decisions (locked for the first pass)

| Decision | Choice |
|----------|--------|
| **Storage scope** | One global locker accessible from every armory. |
| **Capacity** | Unlimited in the first version. |
| **Equipment identity** | Catalog ID plus explicit per-item state if the ground combat model gains such state later. Duplicate items remain separate entries. |
| **Equipment types** | Ground weapons and ground armor. Trade goods, ship equipment, and loot remain separate systems. |
| **Weapon slots** | The active loadout remains two weapon slots. The current armory only limits the list to two IDs; Phase 1 will make a two-handed weapon occupy both slots and prevent pairing it with another weapon. |
| **Armor slots** | One item per fixed slot: `head`, `body`, `hands`, `legs`, and `feet`. The current armory rejects a purchase when its slot is occupied; Phase 1 will preserve the displaced item through storage-aware replacement. |
| **Replacement behavior** | Phase 1 target: equipping an item into an occupied compatible slot stores the displaced item; it is never silently sold or destroyed. |
| **Buying** | Buying creates one owned item, then the player chooses whether to equip it or store it. Payment is not lost if the destination choice is canceled or impossible. |
| **Selling** | Selling is always explicit and separate from storing. Selling a stored item is supported. |
| **Ammo** | The current ground-combat model does not persist weapon ammo; this first storage pass must not invent a partial ammo system. If ground ammo becomes persistent later, stored entries must gain explicit ammo state in a follow-up migration. |
| **Backward compatibility** | Existing saves load with empty ground storage. Existing equipped weapons and armor remain equipped exactly as before. |

## Philosophy alignment

| Principle | Application |
|----------|-------------|
| **Data-first** | Stored entries reference the existing frozen ground weapon and armor catalogs by stable ID. |
| **ctx-first** | The locker belongs to `GameContext`; it is not module-level state or UI state. |
| **Pure computation** | Slot compatibility, two-handed fit checks, sell prices, and display rows remain pure or narrowly testable helpers. |
| **Explicit mutation** | Buy, store, install, replace, and sell are named actions with no implicit destruction path. |
| **Save/load safety** | Storage and the equipped loadout survive Continue without duplication or loss. |
| **UI iteration** | Ground storage mutation is separated from the armory presentation so the split view can evolve without rewriting ownership logic. |
| **Reuse** | Extend `GroundWeaponSpec`, `GroundArmorSpec`, `GameContext`, the armory, combat initialization, and existing save/load paths rather than creating parallel catalogs. |

## Pre-implementation audit

### Existing modules and helpers to extend or reuse

- `src/spacehack/game_context.py`: `GameContext.equipped_ground_weapons`
  and `GameContext.equipped_ground_armor` are the current ownership fields;
  add one persistent ground-storage field beside them.
- `src/spacehack/data/ground_weapons/__init__.py`: `GroundWeaponSpec`,
  `find_ground_weapon`, and `list_ground_weapons` define the stable catalog and
  expose the `hands` constraint needed for two-handed loadouts.
- `src/spacehack/data/ground_armor/__init__.py`: `GroundArmorSpec`,
  `find_ground_armor`, and `list_ground_armor` define armor identity, fixed
  slot, defense, and price.
- `src/spacehack/menus/_armory.py`: `_pygame_armory_frame`,
  `_apply_pygame_armory_action`, and `_run_armory_menu` are the current Pygame
  armory entry points. The storage UI should reuse the split-frame and chooser
  patterns established by the ship mechanic terminal.
- `src/spacehack/character_screen.py`: `_equipment_rows` is the current
  read-only equipment presentation and should remain the shared source for
  character equipment details where possible.
- `src/spacehack/combat/_rules_ground.py`: `init`, `player_weapons`, and armor
  defense calculation consume the equipped loadout. They must continue to see
  only the active equipment after storage is introduced.
- `src/spacehack/saveload.py`: `_ctx_to_dict`, `load_game`, and the existing
  equipped-ground fields are the save/load seam. New storage needs matching
  serialization, deserialization, and old-save defaults.
- `src/spacehack/__main__.py`: armory terminal routing already opens the shared
  armory menu; no new game mode is required for the first UI pass.
- `tests/test_pygame_ui.py`: existing armory frame/action tests are the UI
  regression anchor.
- `tests/test_saveload.py`: existing context round-trip tests should cover
  duplicate stored weapons, stored armor, and equipped-loadout preservation.
- `tests/combat/test_rules_ground.py` and `tests/test_ship_mutation.py`: use
  the ground combat tests for loadout behavior and the ship mutation tests as a
  model for focused storage mutation coverage.

### Three potential duplication hotspots

1. **A second loadout rules engine** could be created inside the armory UI,
   duplicating combat's weapon and armor assumptions.
   - **DRY strategy:** keep storage actions in a ground-equipment domain helper;
     have both armory actions and future character-screen actions call it.
     Combat continues to consume the resulting equipped fields only.

2. **Two-handed validation** could be implemented differently for buying,
   storing, and installing.
   - **DRY strategy:** define one compatibility/fit calculation for a proposed
     weapon loadout. It must be used by equip, replacement, and buy-destination
     flows, with tests for one-handed pairs, two-handed weapons, and full slots.

3. **Armor replacement and sell pricing** could diverge between equipped and
   stored items.
   - **DRY strategy:** use one stored-entry lookup and one catalog-based sell
     price helper for both locations. A replacement action should be a single
     atomic operation that moves the old item to storage before installing the
     new one.

4. **Save/load migration** could serialize equipped and stored items using
   incompatible shapes or silently discard duplicates.
   - **DRY strategy:** use a small stored-entry representation and shared
     catalog validation during load. Add round-trip tests with duplicate IDs,
     mixed weapon/armor entries, and malformed legacy records.

## Data model

### Stored ground-equipment entry

The first implementation should use a runtime dataclass representing one owned
item:

```python
@dataclass
class StoredGroundEquipment:
    item_type: str       # "weapon" or "armor"
    item_id: str         # ground catalog ID
```

A list is preferable to a count dictionary. It preserves duplicate items as
distinct owned parts and leaves room for explicit per-item state later. The
first implementation should not add `ammo` because the current ground combat
rules do not consume or persist player weapon ammunition. If that gameplay
changes, add a deliberate migration and tests rather than inferring state from
an item ID.

### GameContext ownership

Add one field conceptually equivalent to:

```python
ground_equipment_storage: list[StoredGroundEquipment] = field(
    default_factory=list,
)
```

The exact class and field names may be refined during Phase 1, but the
ownership contract is fixed: storage belongs to the player and is independent
of the current armory, dungeon, or map.

The existing fields remain the active loadout:

```python
equipped_ground_weapons: list[str]       # zero to two effective slots

equipped_ground_armor: dict[str, str]    # armor slot -> catalog ID
```

## Equipment movement rules

### Store an equipped weapon

1. Read the selected weapon slot.
2. Create one stored weapon entry with its catalog ID.
3. Remove it from the active loadout through the shared ground-equipment
   mutation helper.
4. Re-normalize the weapon slots so combat does not see a phantom gap.
5. Log the action.

If removing the weapon would leave an invalid two-handed arrangement, the
operation must fail without changing either loadout or storage.

### Store equipped armor

1. Read the selected armor slot.
2. Create one stored armor entry.
3. Remove the armor from `equipped_ground_armor`.
4. Log the action.

### Install a stored weapon

1. Validate that the item exists in storage.
2. Validate that the active loadout can fit the weapon's `hands` requirement.
3. Remove exactly that storage entry.
4. Add the weapon to the active loadout in a normalized slot arrangement.
5. Log the action.

A two-handed weapon requires both weapon slots. Equipping it must either store
the displaced one-handed weapons as part of the same atomic action or offer a
clear replacement choice; it must never silently discard them. The first UI
pass should use a compact replacement chooser when displacement is required.
If there is no valid destination and the player cancels, storage and the active
loadout remain unchanged.

### Install stored armor

1. Validate that the armor entry exists in storage.
2. Determine its fixed catalog slot.
3. If that slot is empty, remove the entry from storage and equip it.
4. If the slot is occupied, atomically move the currently equipped item into
   storage, then equip the selected item.
5. Log the replacement.

Armor replacement must preserve the displaced item even when the player is
installing a stronger item from storage.

### Buy ground equipment

1. Validate credits and the current armory's catalog availability.
2. Open an Install/Store destination chooser before mutating credits.
3. For Install, use the same weapon/armor compatibility and replacement rules
   as storage installation.
4. For Store, append one new entry without requiring an available active slot.
5. Deduct credits only after the selected destination succeeds.
6. Log the purchase and destination.

A canceled, unaffordable, incompatible, or otherwise failed destination leaves
credits, storage, and the active loadout unchanged.

### Sell ground equipment

Selling is an explicit action from either the active loadout or storage:

1. Resolve the selected catalog item.
2. Open the compact confirmation/action chooser if the UI uses one.
3. Remove exactly one owned item.
4. Add the catalog sell value (initially half the buy price).
5. Log the sale.

Selling an equipped item must not shift an unrelated armor slot or duplicate a
weapon. Selling an item from storage must not change the active combat loadout.

## Domain changes

### Ground-equipment domain

- Add the stored-entry dataclass and storage mutation helpers.
- Add pure weapon-fit checks covering one-handed and two-handed weapons.
- Add armor-slot compatibility and replacement helpers.
- Normalize the active weapon list after store/install actions.
- Keep catalog lookup and sell-price calculation shared by equipped and stored
  actions.
- Keep mutation transactional: validate first, then apply the complete move.

### Game context

- Add one `ground_equipment_storage` field with an empty default.
- Document that equipped fields contain only active combat gear and storage
  contains unequipped owned gear.
- Do not add module-level ground inventory state.

### Save/load

- Serialize `ground_equipment_storage` in `_ctx_to_dict`.
- Restore it in `load_game` with `[]` for old saves.
- Preserve duplicate weapon and armor entries exactly.
- Validate item types and catalog IDs during load; malformed records should be
  ignored rather than crashing Continue or becoming a different item.
- Preserve the current equipped loadout unchanged during migration.

### Armory and character UI

First UI pass should extend the existing armory split screen:

- Add explicit `[B]uy` and `[S]torage` header tabs, following the ship-storage
  interaction pattern.
- Keep the right panel as **My Loadout**, showing weapon slots and all five
  armor slots.
- Show stored weapons and armor with type, slot, hands, damage/defense, and
  price details where useful.
- Use compact Install/Store and Sell actions consistent with the mechanic UI.
- Display a clear replacement prompt when a two-handed weapon would displace
  one-handed weapons or when armor occupies the same slot.
- Keep empty slots visible and explain that Fists are the combat fallback when
  no weapon is equipped.
- Reuse shared Pygame split-screen primitives rather than creating a second
  terminal rendering system.

The character Equipment tab remains read-only in the first pass unless a later
phase demonstrates a compelling need for direct management outside an armory.

### Ground combat integration

- Continue reading only `equipped_ground_weapons` and
  `equipped_ground_armor` during combat initialization.
- Do not let stored items affect weapon selection, AP, or armor defense.
- Preserve the current no-persistent-ammo behavior in the first storage pass.
- If a future combat change adds ground ammo, update the stored-entry schema,
  combat sync, save/load, guide, and tests together in a separate phase.

### Guide/UI documentation

Add or update a guide section explaining:

- Ground Storage is global and unlimited in the first version.
- Buy equipment into Storage when the active loadout is full.
- Install and store actions preserve owned equipment; they are not sales.
- Two-handed weapons require both weapon slots.
- Replacing armor stores the previous piece instead of destroying it.
- Selling from Storage is explicit and returns the normal sell value.
- Ground weapons do not currently track persistent ammunition.

## Phased implementation plan

### Phase 1 - Storage model, loadout mutation, and save/load

- [ ] Add the stored-ground-equipment data model.
- [ ] Add `GameContext.ground_equipment_storage` with an empty default.
- [ ] Add transactional store/install/sell helpers for weapons and armor.
- [ ] Add one shared two-handed weapon fit calculation.
- [ ] Add old-save defaults and malformed-entry filtering.
- [ ] Add tests for duplicates, empty storage, invalid indexes, two-handed
  conflicts, armor replacement, sell isolation, and round-trip persistence.

**PLAYTEST:** No major UI yet. Start a new game, save, Continue, and confirm
existing ground combat behaves exactly as before. If a developer fixture
populates storage, verify it survives save/load while the equipped loadout and
combat stats remain unchanged.

### Phase 2 - Armory storage UI

- [ ] Add Buy/Storage tabs and direct `B`/`S` shortcuts to the armory.
- [ ] Add stored weapon and armor rows with useful details.
- [ ] Add compact Install/Store/Sell action choosers.
- [ ] Keep the current armory buy/sell behavior working while making ownership
  explicit.
- [ ] Add replacement prompts for occupied armor slots and two-handed weapons.

**PLAYTEST:** At an armory, buy a weapon and choose Install; buy another item
and choose Store. Open Storage, install the stored item, then store it again.
Replace an equipped armor piece and verify the old piece appears in Storage.
Attempt to install a two-handed weapon with both weapon slots occupied and
confirm the replacement/cancel paths never destroy equipment. Sell one stored
item and verify only that item and the credits change.

### Phase 3 - Ground progression and loadout preservation

- [ ] Ensure every ground loadout change uses the same storage-aware mutation
  helpers, including future scripted or developer loadout paths.
- [ ] Verify dungeon entry, combat disengagement, death, and Continue preserve
  the active loadout and storage contents.
- [ ] Add regression coverage for repeated armor replacement, duplicate weapons,
  two-handed transitions, and save/load at each transition.
- [ ] Update ground equipment and armory guide text with exact current rules.

**PLAYTEST:** Build a varied loadout with a one-handed pair, a two-handed rifle,
and armor in multiple slots. Store and reinstall items across several armory
visits. Enter ground combat after each transition and verify weapon choices,
AP, and total armor defense match the active loadout only. Save/Continue after
replacement and confirm every owned item appears exactly once.

### Phase 4 - UX iteration and regression pass

- [ ] Playtest the complete ground-equipment lifecycle.
- [ ] Decide whether Storage belongs only in the armory, also in the Character
  Equipment tab, or in both.
- [ ] Refine labels, hints, replacement confirmation, and empty-state text.
- [ ] Add final UI/action-mapping regression tests.
- [ ] Run `python3 tools/smoke.py` and `python3 tools/test.py`.

**PLAYTEST:** Complete the full lifecycle: buy, install, store, replace, sell,
enter ground combat, spend turns with the resulting loadout, save/Continue,
and repeat with duplicate weapons and armor replacements. Confirm no item is
lost, duplicated, or silently sold, and that the UI makes active versus stored
ownership clear.

## Acceptance criteria

- A player can unequip a ground weapon or armor piece without selling or
  destroying it.
- Ground storage is global, persistent, and unlimited in the first version.
- A stored item can be installed later when its slot/hand requirements fit.
- Two-handed weapon transitions never silently destroy one-handed weapons.
- Replacing armor stores the previous item and preserves duplicates.
- Buying into Storage works when active slots are full.
- Selling is explicit and removes exactly one owned item.
- Stored items do not affect active ground combat until installed.
- Existing saves load successfully with empty ground storage by default.
- Storage survives save/load with exact contents.
- The current no-persistent-ammo ground rule remains unchanged in the first
  version.
- The UI clearly distinguishes buying, storing, installing, replacing, and
  selling.
- The guide explains ground storage and two-handed/armor-slot behavior.
- Smoke and the full test suite pass.

## Open questions for UI iteration

1. Should Storage remain armory-only, or should the Character Equipment tab
   eventually allow management away from a terminal?
2. When installing a two-handed weapon would displace two one-handed weapons,
   should the chooser offer `Store both`, `Store one`, or require manual setup?
3. Should the storage list show individual duplicate rows or grouped counts?
4. Should armor replacement be immediate after confirmation, or should the
   player choose the destination for the displaced armor explicitly?
5. Should ground weapons eventually gain persistent ammo, and if so should ammo
   be per weapon instance or per catalog type?

## Current status

The design is ready for Phase 1 implementation. The current armory already
provides a Pygame split-screen presentation and the current combat model has a
clear active-loadout contract, so the first implementation can focus on
persistent ownership, transactional mutation, and save/load without changing
ground combat rules.
