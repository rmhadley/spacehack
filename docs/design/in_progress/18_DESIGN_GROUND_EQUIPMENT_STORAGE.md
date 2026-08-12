# DESIGN: Ground Equipment Storage and Loadout Transfer

> **Status:** In progress. This document is the contract for the first
> persistent ground-equipment inventory pass and is intentionally UI-iterative.

## Overview

Ground equipment should remain valuable after a loadout change. If the player
buys a laser rifle, helmet, or heavy vest, they should be able to remove it
without selling or destroying it, keep it in storage, and equip it later when a
mission or character build calls for it. The system should also make it safe to
buy replacement armor or weapons without silently losing the previous item.

The first version has two distinct ownership layers:

- **Armory storage:** an unlimited global warehouse accessible from armory
  terminals. It can hold every owned ground weapon and armor item.
- **Expedition inventory:** a limited personal pack prepared at the armory and
  carried into a dungeon. It holds extra weapons and armor that can be swapped
  into the active loadout while exploring. Equipped items do not consume pack
  slots; the four initial slots represent reserve items only.

This separation preserves the convenience of unlimited ownership while making
expedition preparation and in-dungeon loadout decisions meaningful. Dungeon
loot also enters the limited expedition inventory, so the player must make room
or leave it behind.

The UI/UX should build on the existing Pygame armory, character equipment, and
combat screens. The first presentation should make the ownership distinction
obvious:

**Current implementation gap:** the existing armory directly appends a bought
weapon when fewer than two weapon IDs are equipped and directly overwrites no
armor slot; it does not yet enforce `hands=2`, preserve displaced equipment, or
offer Buy/Store destinations. The rules in this document are the Phase 1+
target contract, not claims about behavior already present. Phase 1 must add the
transactional domain helpers before the armory UI adopts them.

- **Buy:** ground equipment available at the current armory.
- **Armory Storage:** unlimited equipment ownership that stays at the armory.
- **Expedition Pack:** limited reserve equipment brought into a dungeon.
- **My Loadout:** weapons and armor currently equipped for ground combat.

This design covers ground weapons and armor only. Ship equipment remains
covered by `docs/design/complete/17_DESIGN_SHIP_EQUIPMENT_STORAGE.md`.

## Design decisions (locked for the first pass)

| Decision | Choice |
|----------|--------|
| **Armory storage scope** | One global, unlimited warehouse accessible from every armory terminal. |
| **Expedition inventory scope** | One limited personal pack prepared at an armory and carried into dungeons; it is not accessible from the armory warehouse while underground. |
| **Expedition capacity** | Four reserve-item slots initially, plus `max(0, (Strength - 10) // 10)` bonus slots. Strength 10 therefore starts with four slots; equipped items do not consume these slots. |
| **Equipment identity** | Catalog ID plus explicit per-item state if the ground combat model gains such state later. Duplicate items remain separate entries. |
| **Equipment types** | Ground weapons and ground armor. Trade goods, ship equipment, and loot remain separate systems. Both spare weapons and spare armor use expedition slots. |
| **Weapon slots** | The active loadout remains two weapon slots. The current armory only limits the list to two IDs; Phase 1 will make a two-handed weapon occupy both slots and prevent pairing it with another weapon. |
| **Armor slots** | One item per fixed slot: `head`, `body`, `hands`, `legs`, and `feet`. The current armory rejects a purchase when its slot is occupied; Phase 1 will preserve the displaced item through storage-aware replacement. |
| **Replacement behavior** | Phase 1 target: equipping an item into an occupied compatible slot stores the displaced item; it is never silently sold or destroyed. |
| **Buying** | Buying creates one owned item, then the player chooses whether to equip it, place it in the expedition pack, or leave it in armory storage. Payment is not lost if the destination choice is canceled or impossible. |
| **Dungeon swapping** | During exploration and active combat, the player may exchange active gear with an expedition item. Each successful swap costs 1 AP; armory storage is unavailable until the player returns to an armory. |
| **Dungeon loot** | Ground weapons and armor found in a dungeon require an available expedition slot. If the pack is full, the player must swap/drop an item or leave the loot. |
| **Selling** | Selling is always explicit and separate from storing. Selling from armory storage or the expedition pack is supported; selling active gear uses the existing armory-only action. |
| **Ammo** | The current ground-combat model does not persist weapon ammo; this first storage pass must not invent a partial ammo system. If ground ammo becomes persistent later, both storage layers must gain explicit ammo state in a follow-up migration. |
| **Backward compatibility** | Existing saves load with empty ground storage. Existing equipped weapons and armor remain equipped exactly as before. |

## Philosophy alignment

| Principle | Application |
|----------|-------------|
| **Data-first** | Stored entries reference the existing frozen ground weapon and armor catalogs by stable ID. |
| **ctx-first** | Armory storage, expedition inventory, and active loadout belong to `GameContext`; none is module-level state or UI state. |
| **Pure computation** | Slot compatibility, two-handed fit checks, sell prices, and display rows remain pure or narrowly testable helpers. |
| **Explicit mutation** | Buy, store, install, replace, and sell are named actions with no implicit destruction path. |
| **Save/load safety** | Storage and the equipped loadout survive Continue without duplication or loss. |
| **UI iteration** | Ground storage mutation is separated from the armory presentation so the split view can evolve without rewriting ownership logic. |
| **Reuse** | Extend `GroundWeaponSpec`, `GroundArmorSpec`, `GameContext`, the armory, combat initialization, and existing save/load paths rather than creating parallel catalogs. |

## Pre-implementation audit

### Existing modules and helpers to extend or reuse

- `src/spacehack/game_context.py`: `GameContext.equipped_ground_weapons`
  and `GameContext.equipped_ground_armor` are the current active-loadout
  fields; add separate persistent armory-storage and expedition-inventory
  fields beside them.
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
  only active equipment; a successful expedition swap must update that loadout
  before the next action and charge 1 AP.
- `src/spacehack/__main__.py` and `src/spacehack/input_helpers.py`: the dungeon
  input dispatch and existing modal-opening conventions are the integration
  seam for an expedition equipment modal. The modal must pause the current
  frame and must not advance NPCs or combat until it returns.
- `src/spacehack/dungeon.py` and `src/spacehack/trade.py`: dungeon loot pickup
  and entity removal are the likely seams for routing discovered ground gear
  into the expedition pack instead of armory storage.
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
same entry shape can be used by both armory storage and expedition inventory;
the container determines the item's access and capacity rules.

The first implementation should not add `ammo` because the current ground
combat rules do not consume or persist player weapon ammunition. If that
 gameplay changes, add a deliberate migration and tests rather than inferring
state from an item ID.

### GameContext ownership

Add two fields conceptually equivalent to:

```python
ground_armory_storage: list[StoredGroundEquipment] = field(
    default_factory=list,
)
ground_expedition_inventory: list[StoredGroundEquipment] = field(
    default_factory=list,
)
```

The exact class and field names may be refined during Phase 1, but the
ownership contract is fixed: armory storage is the unlimited warehouse and
expedition inventory is the limited carried reserve. Both are independent of
the current map; only expedition inventory is available underground.

The existing fields remain the active loadout:

```python
equipped_ground_weapons: list[str]       # normalized active weapon IDs
equipped_ground_armor: dict[str, str]    # armor slot -> catalog ID
```

The persisted weapon list stays compact: one-handed loadouts contain one or
two IDs, while a two-handed weapon is represented by one ID occupying both
logical weapon slots. No empty placeholder ID is stored for the second hand;
the shared fit helper derives the logical occupancy from `GroundWeaponSpec.hands`.
A transition from two one-handed weapons to a two-handed weapon must first
move both displaced IDs atomically to the selected destination. In a dungeon,
the expedition pack must have room for both displaced items after the selected
weapon is removed; at an armory they may go to Armory Storage or the pack only
through an explicit destination choice. A canceled or under-capacity transition
leaves the source container and active loadout unchanged.

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

1. Validate that the item exists in the selected container (armory storage at
   an armory, expedition inventory in a dungeon).
2. Validate that the active loadout can fit the weapon's `hands` requirement.
3. For an armory install, resolve any displaced equipment into armory storage
   or the expedition pack according to the player's explicit destination.
4. For an expedition swap, require 1 AP and resolve displaced equipment back
   into the expedition inventory.
5. Remove exactly that source entry.
6. Add the weapon to the active loadout in a normalized slot arrangement.
7. Log the result.

A two-handed weapon requires both logical weapon slots and is stored as one
weapon ID in the normalized active list. Equipping it from a container must
atomically move both currently equipped one-handed weapons to an explicit
destination; it must never silently discard either one. In the expedition pack,
the selected two-handed item is removed before capacity is checked for the two
displaced items, but the complete transaction must still pass before any state
is mutated. Replacing an active two-handed weapon with a one-handed weapon
moves the two-handed item into the source container and installs the selected
weapon. The first UI pass should use a compact replacement chooser when
displacement is required. If there is no valid destination or the player
cancels, the source container and active loadout remain unchanged.

### Install stored armor

1. Validate that the armor entry exists in the selected container.
2. Determine its fixed catalog slot.
3. If that slot is empty, remove the entry from the source container and equip
   it.
4. If the slot is occupied, atomically move the currently equipped item into
   the destination container, then equip the selected item. During dungeon
   swapping this means the displaced armor must fit in the expedition pack.
5. Charge 1 AP only for a successful in-dungeon swap; armory management is
   free.
6. Log the replacement.

Armor replacement must preserve the displaced item even when the player is
installing a stronger item from storage.

### Buy ground equipment

1. Validate credits and the current armory's catalog availability.
2. Open an Install / Expedition Pack / Armory Storage destination chooser
   before mutating credits.
3. For Install, use the same weapon/armor compatibility and replacement rules
   as armory loadout management.
4. For Expedition Pack, require one available reserve slot and append one new
   entry.
5. For Armory Storage, append one new entry without a capacity check.
6. Deduct credits only after the selected destination succeeds.
7. Log the purchase and destination.

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
weapon. Selling an item from armory storage or the expedition pack must not
change the active combat loadout. Dungeon selling is not available; the player
must return to an armory to sell expedition items.

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

- Add `ground_armory_storage` and `ground_expedition_inventory` fields with
  empty defaults.
- Document that equipped fields contain active combat gear, armory storage is
  unlimited terminal-only ownership, and expedition inventory is the limited
  carried reserve.
- Do not add module-level ground inventory state.

### Save/load

- Serialize `ground_armory_storage` and `ground_expedition_inventory` in
  `_ctx_to_dict`.
- Restore both in `load_game` with `[]` for old saves. A migration may accept
  the pre-expedition `ground_equipment_storage` name as armory storage if an
  intermediate development save ever contains it.
- Preserve duplicate weapon and armor entries exactly.
- Save the expedition pack even while the player is underground so Continue
  restores the same carried equipment and active loadout.
- Validate item types and catalog IDs during load; malformed records should be
  ignored rather than crashing Continue or becoming a different item.
- Preserve the current equipped loadout unchanged during migration.

### Armory and character UI

First UI pass should extend the existing armory split screen:

- Add explicit `[B]uy`, `[A]rmory`, and `[E]xpedition` destinations/views, or
  an equally clear layout that distinguishes the unlimited warehouse from the
  limited carried pack.
- Keep the right panel as **My Loadout**, showing weapon slots and all five
  armor slots.
- Show both storage containers with item counts such as `Pack 2/4` and
  `Armory unlimited`.
- Show stored weapons and armor with type, slot, hands, damage/defense, and
  price details where useful.
- Use compact Install/Store/Pack/Sell actions consistent with the ship
  mechanic UI. Selling is available at an armory, not underground.
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
- Do not let armory-stored or expedition-reserve items affect weapon
  selection, AP, or armor defense until an explicit swap succeeds.
- A successful in-combat swap costs 1 AP and refreshes the combat weapon/armor
  state before the next action; a failed or canceled swap costs nothing.
- Preserve the current no-persistent-ammo behavior in the first storage pass.
- If a future combat change adds ground ammo, update the stored-entry schema,
  combat sync, save/load, guide, and tests together in a separate phase.

### Guide/UI documentation

Add or update a guide section explaining:

- Armory Storage is global, terminal-only, and unlimited in the first version.
- The Expedition Pack is a limited carried reserve with four base slots plus
  the Strength bonus; equipped items do not consume reserve slots.
- Pack weapons and armor can be swapped into the active loadout during
  exploration or combat for 1 AP; Armory Storage is unavailable underground.
- Buy equipment into Armory Storage or the Expedition Pack when active slots
  are full, subject to pack capacity.
- Install, pack, and store actions preserve owned equipment; they are not
  sales.
- Two-handed weapons occupy both logical weapon slots and atomically displace
  both one-handed weapons.
- Replacing armor stores the previous piece instead of destroying it.
- Selling from Armory Storage or the Expedition Pack is explicit and returns
  the normal sell value at an armory; selling is unavailable underground.
- Ground-equipment loot consumes Expedition Pack capacity.
- Ground weapons do not currently track persistent ammunition.

## Phased implementation plan

### Phase 1 - Two-tier inventory model, mutation, and save/load

- [x] Add the stored-ground-equipment data model.
- [x] Add `GameContext.ground_armory_storage` and
  `GameContext.ground_expedition_inventory` with empty defaults.
- [x] Add the Strength-based expedition capacity helper.
- [x] Add transactional store/install/sell/pack-transfer helpers for weapons
  and armor.
- [x] Add one shared two-handed weapon fit calculation.
- [x] Add old-save defaults and malformed-entry filtering.
- [x] Add tests for duplicates, empty containers, capacity boundaries, invalid
  indexes, two-handed conflicts, armor replacement, sell isolation, and
  round-trip persistence.

**PLAYTEST:** No major UI yet. Start a new game, save, Continue, and confirm
existing ground combat behaves exactly as before. Populate both containers in
a developer fixture, including a full four-slot pack and a Strength bonus, then
verify save/load preserves both containers, the active loadout, and combat
stats unchanged.

**Implementation checkpoint:** Phase 1 establishes the backend split between
unlimited `ground_armory_storage` and Strength-scaled
`ground_expedition_inventory`. `ground_equipment.py` owns catalog validation,
capacity, normalized two-handed fit checks, atomic storage/installation,
armor replacement, duplicate-safe transfers, and explicit sale removal.
Existing saves default both containers empty; an intermediate
`ground_equipment_storage` field migrates into Armory Storage. Focused mutation
and save/load tests pass, while the armory and dungeon UI remain unchanged for
Phase 2 and Phase 3.

### Phase 2 - Armory warehouse and expedition-pack UI

- [x] Add clear Buy, Armory Storage, and Expedition Pack views or destinations.
- [x] Add pack capacity/count display and Strength bonus feedback.
- [x] Add stored weapon and armor rows with useful details.
- [x] Add compact Install/Pack/Armory/Sell action choosers.
- [x] Keep the current armory buy/sell behavior working while making ownership
  and destination explicit.
- [x] Add replacement prompts for occupied armor slots and two-handed weapons.

**PLAYTEST:** At an armory, use `[B]uy`, `[A]rmory`, and `[E]xpedition` to
switch views. Buy a weapon and choose Install; buy another item and choose
Expedition Pack; fill all four pack slots and verify a fifth item can still be
bought into unlimited Armory Storage. Move a reserve item back to Armory
Storage, then add another pack item. Replace equipped armor and verify the old
piece reaches the selected container. Sell one stored item and verify only that
item and the credits change.

### Phase 3 - Dungeon expedition swapping and loot

- [ ] Add a dungeon equipment modal that manages expedition inventory and the
  active loadout without opening armory storage.
- [ ] Allow weapon and armor swaps during exploration and active combat at a
  cost of 1 AP per successful swap.
- [ ] Route discovered ground-equipment loot into the expedition inventory,
  with clear full-pack behavior.
- [ ] Ensure every ground loadout change uses the same storage-aware mutation
  helpers, including future scripted or developer loadout paths.
- [ ] Verify dungeon entry, combat disengagement, death, and Continue preserve
  the active loadout and both storage containers.
- [ ] Add regression coverage for repeated armor replacement, duplicate weapons,
  two-handed transitions, swap AP cost, canceled swaps, full-pack loot, and
  save/load at each transition.

**PLAYTEST:** Build a varied loadout with a one-handed pair, a two-handed rifle,
and armor in multiple slots. Prepare four reserve items at the armory, enter a
dungeon, and swap a gun and armor during exploration. In combat, verify a
successful swap costs 1 AP and a canceled/insufficient-AP swap costs nothing.
Collect ground-equipment loot with a free slot, then test the full-pack choice.
Save/Continue underground and confirm the pack, active loadout, and armory
warehouse are all preserved.

### Phase 4 - UX iteration and regression pass

- [ ] Playtest the complete ground-equipment lifecycle.
- [ ] Decide whether expedition management belongs only in the dungeon modal,
  also in the Character Equipment tab, or in both.
- [ ] Refine labels, hints, replacement confirmation, pack-full behavior, and
  empty-state text.
- [ ] Add final UI/action-mapping regression tests.
- [ ] Run `python3 tools/smoke.py` and `python3 tools/test.py`.

**PLAYTEST:** Complete the full lifecycle: buy, install, pack, store, replace,
swap during exploration, swap during combat, collect loot, sell at an armory,
and save/Continue both above and underground. Repeat with duplicate weapons,
armor replacements, a full pack, and a Strength capacity bonus. Confirm no item
is lost, duplicated, or silently sold, and that the UI makes armory ownership,
carried reserve gear, and active loadout clear.

## Acceptance criteria

- A player can unequip a ground weapon or armor piece without selling or
  destroying it.
- Armory storage is global, persistent, and unlimited in the first version.
- Expedition inventory is persistent, carried into dungeons, and limited to
  `4 + max(0, (Strength - 10) // 10)` reserve-item slots.
- A reserve item can be installed later when its slot/hand requirements fit.
- Two-handed weapon transitions never silently destroy one-handed weapons.
- Replacing armor stores the previous item and preserves duplicates.
- Buying into Armory Storage or the Expedition Pack works when active slots are
  full, subject to pack capacity.
- Swapping active gear with an expedition item costs 1 AP and is available
  during exploration and active combat.
- Dungeon loot uses expedition capacity and has a clear full-pack outcome.
- Selling is explicit and removes exactly one owned item; underground selling
  is unavailable.
- Stored/reserve items do not affect active ground combat until installed.
- Existing saves load successfully with empty Armory Storage and an empty
  Expedition Pack by default; any legacy `ground_equipment_storage` records
  migrate to Armory Storage.
- Armory Storage and the Expedition Pack survive save/load with exact contents.
- The current no-persistent-ammo ground rule remains unchanged in the first
  version.
- The UI clearly distinguishes buying, storing, installing, replacing, and
  selling.
- The guide explains ground storage and two-handed/armor-slot behavior.
- Smoke and the full test suite pass.

## Open questions for UI iteration

1. Should expedition management eventually be available from the Character
   Equipment tab as well as the dungeon modal?
2. When a two-handed weapon would displace two one-handed weapons, should the
   chooser label the transaction `Pack both`, `Armory both`, or another phrase?
   The atomic displacement rule itself is locked.
3. Should each armory show only the unlimited warehouse, or also a compact view
   of the currently prepared expedition pack?
4. Should the player be able to drop reserve gear directly onto the dungeon map
   to make room for loot, or only leave loot behind?
5. Should ground weapons eventually gain persistent ammo, and if so should ammo
   be per weapon instance or per catalog type?

## Current status

Phase 2 is complete. The armory terminal now exposes `[B]uy`, `[A]rmory`, and
`[E]xpedition` views, shows pack capacity and unlimited warehouse ownership,
provides stored weapon/armor details, and routes purchase, install, transfer,
store, and sale actions through the ground-equipment domain. Phase 3 adds
in-dungeon 1-AP swaps and loot capacity behavior; Phase 4 remains the UX and
regression pass.
