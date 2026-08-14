# DESIGN: Ground Ammo, Reloads, and Field Items

> **Status:** Complete. Phases 0-6 are implemented, covered by the current
> regression suite, and the full manual lifecycle playtest passed on 2026-08-14.
>
> **Related:**
> `docs/design/complete/18_DESIGN_GROUND_EQUIPMENT_STORAGE.md`
>
> **Scope:** persistent ground-weapon ammunition, reload actions, extra ammo
> carried in the Expedition Pack, and future non-combat field items such as
> med packs and stims.

## Overview

Ground weapons now consume and persist ammunition through per-instance
magazines and typed reserve stacks. The next inventory step is to add
consumables without creating a second inventory system for every new item type.

The proposed direction is:

- Active weapons have mutable per-instance state, including current loaded
  ammunition where applicable.
- The Expedition Pack becomes a general carried-item container rather than a
  weapons/armor-only list.
- Spare ammunition is represented as explicit pack items and can be used by a
  reload action.
- Reloading is a deliberate combat action with an AP cost and clear failure
  states; it is not an automatic infinite refill.
- Future consumables (med packs, stims, repair tools, quest items) use the same
  pack framework but explicit item effects and action rules.
- Armory Storage remains unlimited terminal-only ownership. The Expedition Pack
  is the only field inventory available underground.

Phases 0-5 have now landed: ground weapons use independent per-instance
magazines, firing consumes loaded rounds, `R` performs a transactional reload
of an eligible active weapon, Ground Armory ammo purchases plus coded field-item
loot are wired through the typed stack domain, and consumables now have
data-driven use effects. When multiple active weapons can reload, `R` opens a
compact weapon chooser; a single eligible weapon reloads directly.

## Current-state audit

### Existing data and behavior

- `src/spacehack/data/ground_weapons/__init__.py` defines
  `GroundWeaponSpec.ammo_capacity` and `ammo_per_shot`.
- Finite capacities are already present on several ground weapons, including
  kinetic pistols, kinetic rifles, shotguns, and laser weapons. Melee weapons
  use the infinite-ammo convention.
- `src/spacehack/combat/_rules_ground.py` owns the ground combat state and
  exposes `can_fire()` and `consume_shot()`. `can_fire()` rejects empty or
  insufficient magazines, and `consume_shot()` decrements the selected weapon
  instance after an accepted shot.
- `src/spacehack/combat/_loop.py` calls `can_fire()` before resolving a shot
  and `consume_shot()` after a shot. The same loop dispatches `R` to the reload
  action without duplicating fire orchestration; ground rules open a compact
  chooser when multiple active weapons have matching reserve ammo.
- Ground combat reads per-instance state from
  `GameContext.equipped_ground_weapons`; duplicate catalog IDs have independent
  magazines.
- `src/spacehack/ground_equipment.py` stores owned ground weapons and armor as
  frozen `StoredGroundEquipment(item_type, item_id)` entries. That shape is
  sufficient for catalog ownership, but cannot represent magazine state.
- `src/spacehack/character_screen.py` now exposes selectable Expedition Pack
  rows. Enter opens `Equip` / `Discard`; compatible equipped slots still open
  swap choices. In active ground combat, a successful gear swap closes the
  screen so AP loss and the enemy turn are visible immediately.
- `src/spacehack/trade.py` and dungeon combat loot provide the separate
  ground-equipment loot path; its reachability and full lifecycle passed the
  Phase 6 manual playtest.
- `src/spacehack/saveload.py` validates and round-trips active weapon
  instances, Armory/Expedition field-item stacks, and legacy string-ID
  migrations.
- `src/spacehack/help.py` documents the shipped magazine, reserve-ammo, and
  `R` reload behavior. It must be updated together with every new
  ammo/consumable behavior change.

### Existing patterns to reuse

- `GameContext.ground_expedition_inventory` is the correct ownership seam for
  all field-carried reserve items.
- `ground_equipment.expedition_capacity()` is the correct capacity seam. The
  first item implementation should decide whether ammo/items consume one
  slot, a stack slot, or weighted capacity, then keep that rule in one pure
  helper.
- `StoredGroundEquipment` and the catalog lookup pattern provide safe legacy
  validation, but should not be stretched indefinitely into an ambiguous
  catch-all record. A deliberate `StoredFieldItem`/`GroundItemStack` model is
  preferable when ammo is implemented.
- `combat/_loop.py` already owns turn orchestration. Reload should be an opaque
  combat action dispatched there, while computation and mutation live in pure
  or narrowly testable helpers.
- `pygame_screen.ScreenRow` and the compact `pygame_story.choose()` chooser
  provide the existing UI patterns for backpack actions.
- Existing ship ammo in `ship.py` / `combat/_actions.py` demonstrates the
  save/load and per-slot state problems that ground ammo must avoid repeating.
  Ship ammo is keyed by weapon slot because duplicate launchers need separate
  magazines; ground ammo should use the same instance principle.

## Design decisions for review

| Decision | Proposed direction |
|---|---|
| Ammo state | Per equipped weapon instance, never per catalog ID. Two copies of the same weapon must not share a magazine. |
| Loaded vs reserve ammo | Keep a loaded magazine on the weapon instance and reserve ammunition in the Expedition Pack. Reload transfers reserve rounds into the weapon. |
| Magazine size | Use the weapon catalog's `ammo_capacity` as the loaded-magazine maximum. `ammo_capacity == -1` means no reloadable ammo (melee/infinite weapons). |
| Ammo identity | Give every reloadable weapon an `ammo_type` catalog field, such as `kinetic_pistol`, `rifle_round`, or `shotgun_shell`. Ammo items reference that type, not a weapon ID. |
| Ammo stacks | Reserve ammo should be stackable by `ammo_type`, with a quantity. A stack is one backpack row, not one slot per round. |
| Pack capacity | Keep the existing reserve-slot model: equipment and each ammo/consumable stack consume one slot. Add stack quantity limits separately so a single stack cannot become infinite. Revisit weighted capacity only after playtesting. **(locked — stack = 1 slot)** |
| Reload action | `R` opens a compact chooser of active reloadable weapons, showing loaded/capacity and matching reserve. The player selects one; reload is explicit, costs AP, and follows normal turn rules. It never happens automatically on fire. |
| Partial reload | Support partial reloads when a magazine is not empty, but make the first implementation deterministic: reload up to capacity or available reserve, whichever is smaller. |
| Tactical reload | Retain rounds already loaded. Reload transfers only the missing rounds, with no detachable-magazine loss in the first pass. A later design can model magazines as items if that depth proves valuable. |
| Empty fire | A weapon with insufficient loaded ammo cannot fire; `can_fire()` returns a player-facing reason. The burst still allows other active weapons to fire if they are valid. |
| Ammo pickup | Ground loot may contain typed ammo stacks. Pickup first fills matching partial stacks, then creates new stacks while slots remain; any remainder stays on the floor as a typed ammo stack. No rounds are silently discarded. Full-pack behavior uses the same deliberate drop/leave choice as other field items. |
| Armory ownership | Armory Storage may own spare ammo without capacity. Moving ammo into the pack checks pack slots and stack limits. |
| Armory purchasing | Buy ground ammo and consumables at the Ground Armory only. Every purchase explicitly chooses Armory Storage or Expedition Pack; credits are deducted only after destination and capacity validation succeed. The ship mechanic's missile-ammo UI remains separate. |
| Consumables | Med packs, stims, and similar items are stackable field items with explicit effects and action costs. Med Packs fully heal outside combat; in combat they restore 5 HP immediately plus 2 HP at the start of the next 3 turns, refreshing rather than stacking. Combat Stims grant +1 AP on each of the next 3 turns. Values remain data-driven per catalog entry. |
| Use location | Field consumables are available underground subject to their explicit action rules. Med packs are free to use during exploration and cost their catalog `use_ap_cost` in combat. Stims are combat-only; their effect exists only during the active ground combat and expires when that combat ends. Armory-only items remain unavailable underground. |
| Discard | Discard removes the selected pack item/quantity explicitly and logs the result. It is never an implicit fallback for a failed equip or reload. |
| Save/load | Serialize active weapon instance state, reserve stacks, and consumable stacks. Old saves load with deterministic full magazines and no new reserve items unless a migration source exists. |
| Enemies | Enemy ammunition remains encounter-local initially. Persistent enemy magazines add complexity without improving the player's inventory loop. |
| No ammo for melee | Melee and fists remain infinite; they never need reserve ammo or reload actions. |

## Proposed data model

### Weapon instance state

The current active weapon list is `list[str]`. Before persistent ammo lands,
introduce a backward-compatible owned instance representation rather than
putting a mutable dictionary in the frozen catalog spec:

```python
@dataclass
class GroundWeaponInstance:
    weapon_id: str
    loaded_ammo: int | None  # None for infinite/melee weapons
```

The exact class name may change, but the invariants are fixed:

- `weapon_id` resolves through `find_ground_weapon()`.
- `loaded_ammo` is clamped to `[0, ammo_capacity]` for reloadable weapons.
- Duplicate weapon IDs are separate instances with separate ammo.
- Two-handed occupancy remains a loadout rule, not a duplicate instance.
- The active loadout and storage entries must not accidentally alias the same
  mutable object.

A migration may temporarily accept legacy `list[str]` values and seed each
reloadable weapon at full capacity. The migration must be explicit and tested;
it must not infer a partially spent magazine from an ID.

### Field-item model

Do not expand `StoredGroundEquipment.item_type` to accept arbitrary strings
without a schema. Use a separate, explicit item model when consumables arrive:

```python
@dataclass
class GroundItemStack:
    item_type: str       # "ammo" or "consumable" initially
    item_id: str         # catalog ID, e.g. "rifle_round" or "med_pack"
    quantity: int
```

Possible future extension:

```python
@dataclass
class GroundFieldInventory:
    equipment: list[StoredGroundEquipment]
    items: list[GroundItemStack]
```

This keeps existing equipment mutation helpers strict while allowing ammo and
consumables to be stackable. A unified display adapter can render both models
as backpack rows without forcing armor/weapon slot logic to understand items.

### Ammo catalog

Add a data-first `src/spacehack/data/ground_items/` catalog, or equivalent
existing data package, with frozen specs:

```python
@dataclass(frozen=True)
class GroundAmmoSpec:
    id: str
    name: str
    ammo_type: str
    rounds_per_stack: int
    price_per_round: int
```

Weapon specs should gain:

```python
ammo_type: str | None = None
reload_ap_cost: int = 1
```

`ammo_capacity` and `ammo_per_shot` remain weapon properties. The ammo catalog
must not contain combat effects; it only defines identity, stack limits, and
purchase/display data.

### Consumable catalog

Add a separate frozen catalog for field effects:

```python
@dataclass(frozen=True)
class GroundConsumableSpec:
    id: str
    name: str
    effect_id: str
    quantity_per_stack: int
    use_ap_cost: int
    price: int
```

Effects must be table-driven and validated, for example:

- `med_pack`: restore a bounded amount of ground HP.
- `stim`: temporary combat modifier with an explicit data-defined duration in
  ground-combat turns; the initial catalog entry starts at 3 turns.
- `adrenaline`: future example; not part of the first implementation.

The consumable spec should gain an optional `duration_turns: int = 0` field so
higher- or lower-quality stims can vary without runtime conditionals. Duration
is combat-local and is not persisted outside an active combat session.

Do not encode item behavior as a long `if/elif` chain in the UI. Dispatch
validated `effect_id` values through a domain handler table, and keep pure
healing/stat calculations separate from `ctx` mutation.

## Combat rules

### Fire validation

`_rules_ground.can_fire(slot, ctx)` should remain the single fire gate. It
should validate, in order:

1. Valid active slot and weapon instance.
2. Living target and line of sight.
3. Range and AP.
4. Loaded ammo is at least `ammo_per_shot`, unless the weapon is infinite.

The return reason should identify the actionable fix, e.g. `"Empty magazine -
reload (R)."` or `"Not enough rounds loaded."`, without mutating state.

### Shot consumption

`consume_shot(slot, ctx)` should decrement only the selected weapon instance's
loaded ammo after the shot is accepted. It must be called exactly once per
weapon that fires, including burst fire and duplicate weapons.

### Reload

Add an opaque combat action such as `RELOAD` (key choice remains open; `R` is
the leading candidate). A reload should:

1. Select the current weapon or an explicit weapon slot.
2. Confirm the weapon is reloadable and not already full.
3. Find a matching ammo stack in the Expedition Pack.
4. Move the minimum of available reserve and missing magazine capacity.
5. Charge the weapon's reload AP cost only after validation.
6. Remove empty stacks and preserve remaining quantities.
7. End the player's turn if AP reaches zero, allowing the normal enemy-turn
   path to run.

Reload computation should be pure:

```python
def reload_amount(loaded: int, capacity: int, reserve: int) -> int:
    ...
```

The mutation wrapper must be transactional: insufficient ammo, invalid item
identity, or unavailable AP leaves both magazine and reserve unchanged.

The first UI should offer `R reload` for the selected weapon and display the
weapon name, `loaded/capacity`, and matching reserve count. A later chooser can
select among multiple reloadable weapons.

### Consumable use

A field-item action should follow the same pattern as backpack Equip/Discard:
select a stack, press Enter, then choose `Use` or `Discard`. `Use` calls a
catalog effect handler, decrements one quantity only after successful effect
validation, and charges the item's AP cost in combat. Med packs are free to use
in exploration; combat uses their catalog `use_ap_cost`. Combat-only stims are
unavailable outside an active ground fight. Ground combat displays player HP
as `current/max`; an active Med Pack regeneration amount appears as a `+N`
suffix, and the combat log reports both the immediate heal and each regeneration
tick. An active Combat Stim adds a blue `+N` indicator beside the base AP
readout until its duration expires.

## Backpack UX

The Equipment tab should become a general **Expedition Pack** view:

- Header: `EXPEDITION PACK (current/max)`.
- Active loadout rows remain at the top.
- Backpack rows are selectable.
- The weapon row offers `Reload` alongside compatible pack weapons for swapping.
- Weapon/armor row chooser: `Equip` / `Discard` for pack equipment.
- Ammo row chooser: `Reload` / `Discard` when a matching active weapon exists;
  if multiple weapons use that ammo, `Reload` opens a weapon chooser; otherwise
  `Discard` plus an explanation.
- Consumable row chooser: `Use` / `Discard`.
- Details show type, quantity, and useful state (`loaded/capacity`, reserve
  quantity, HP effect, or duration).
- In combat, a successful Equip/Reload/Use action closes the menu so the player
  immediately sees AP drain and the enemy turn if AP reaches zero.
- Outside combat, Reload is free and the menu may remain open after a successful
  item action so the player can prepare every active weapon before a fight. The
  normal ground-exploration HUD provides the direct `R` reload control.
- Discard is always explicit and never silently removes a displaced item.
- Full-pack messages must identify the item and the capacity boundary, and
  offer a deliberate leave/discard decision rather than silently destroying
  anything.

## Save/load and migration

Every new mutable field must be included in both `_ctx_to_dict()` and
`load_game()`:

- active ground weapon instances and their loaded ammo;
- Armory Storage ammo stacks;
- Expedition Pack ammo and consumable stacks;
- temporary consumable effects and remaining durations, if implemented;
- any reload/usable-item session state that can survive a save boundary.

Migration rules:

1. Legacy equipped string IDs become instances seeded at full magazine.
2. Legacy `StoredGroundEquipment` weapon/armor entries remain unchanged.
3. Legacy expedition packs contain no ammo/consumable entries.
4. Malformed item IDs, unknown types, negative quantities, and over-capacity
   stacks are ignored or clamped according to one shared parser policy.
5. A failed parse must never prevent Continue from loading the rest of the run.
6. Duplicate weapon instances remain duplicate instances with independent ammo.
7. Save/load round-trip tests must cover active magazines, duplicate weapons,
   reserve stacks, consumables, partial reloads, full packs, and legacy saves.

## Loot, shops, and ownership

- Ground combat drops can produce equipment, ammo, or consumables through
  explicit typed loot payloads. Existing trade-good/quest loot stays untouched.
- Pressing `P` opens a compact chooser listing every reachable loot stack,
  including when there is only one; pressing ENTER immediately attempts to
  pick up the selected stack. Unselected loot remains in place, and capacity
  failures use the existing explicit overflow/drop behavior.
- Picking up ammo fills matching partial pack stacks first, then uses additional
  pack slots for new stacks. If the pack cannot accept the full quantity, the
  accepted portion is packed and the remainder remains on the floor as a typed
  loot stack. No quantity is silently lost.
- Picking up a consumable follows the same quantity/stack rules, including
  explicit overflow preservation.
- Armory Storage can receive purchased or displaced ammo/items without a
  capacity check. The Expedition Pack is capacity-checked.
- Underground selling remains unavailable. Discarding is not selling and gives
  no credits.
- Loot generation should be authored in the data catalog or NPC loot pools,
  not hard-coded in combat/UI modules.

## Phased implementation plan

### Phase 0 - UX fixes and design approval

- [x] Close the Character Equipment menu after a successful combat swap.
- [x] Make Expedition Pack rows selectable.
- [x] Add compact `Equip` / `Discard` backpack actions for equipment rows.
- [x] Preserve existing two-handed and armor-slot validation.
- [x] Review and approve the ammo/field-item architecture in this document.

### Phase 1 - General field-item container

- [x] Add explicit `GroundItemStack` / field-inventory data model without
  weakening `StoredGroundEquipment` validation.
- [x] Add ammo and consumable catalogs with stable IDs and frozen specs.
- [x] Add pack capacity/stack helpers and malformed-entry filtering.
- [x] Render generalized rows in the Character Equipment tab.
- [x] Add save/load migration tests while ammo remains inactive.

### Phase 2 - Ground weapon instances and magazine state

- [x] Add per-instance active weapon state and legacy string-ID migration.
- [x] Seed legacy reloadable weapons deterministically at full magazines.
- [x] Serialize duplicate weapon instances independently.
- [x] Update armory purchase/store/install paths transactionally.
- [x] Preserve two-handed transitions and displaced gear.

### Phase 3 - Fire consumption and reload action

- [x] Gate `can_fire()` on loaded ammo.
- [x] Implement transactional `consume_shot()`.
- [x] Add reload computation, reserve transfer, AP cost, and combat action.
- [x] Close combat Equipment after successful reload.
- [x] Add HUD `loaded/capacity` and reserve counts.

### Phase 4 - Ammo sourcing and loot

- [x] Add Ground Armory ammo purchasing with explicit Armory Storage or
  Expedition Pack destination handling; ship missile-ammo purchasing remains
  separate.
- [x] Add authored typed ammo loot and pickup/stack merging.
- [x] Add partial pickup/full-pack overflow behavior and save/load coverage;
  any uncollected quantity remains on the floor.
- [x] Add focused regression coverage for ammo scarcity boundaries, duplicate
  weapon reserve behavior, reload timing, and pack pressure. A full manual
  lifecycle playtest remains part of Phase 6 hardening.

### Phase 5 - Consumables ✅

- [x] Add med packs and one stim with explicit, data-driven effect handlers.
- [x] Add `Use` / `Discard` chooser and combat AP semantics.
- [x] Add combat-local temporary effects and expiry rules; effects are not
      persisted outside an active combat session.
- [x] Add authored consumable loot and Ground Armory purchasing.
- [x] Update guide and add automated coverage for the field-item lifecycle.

### Phase 6 - Hardening and cleanup

- [x] Audit every mutable field for save/load coverage.
- [x] Add legacy-save, malformed-item, duplicate-instance, and full-pack tests.
- [x] Update guide, smoke gate, and acceptance criteria.
- [x] Run `python3 tools/smoke.py` and `python3 tools/test.py`.
- [x] Move this design doc to `docs/design/complete/` after all phases and
  playtests are complete.

#### Phase 6 PLAYTEST

- [x] Save and Continue from city, space, and a Scout Derelict with ammo,
  Med Packs, Stims, duplicate weapons, and mixed ground equipment.
- [x] Verify malformed or legacy ground records do not prevent Continue and
  that valid equipment, field items, and magazines remain available.
- [x] Fill the Expedition Pack, then test ammo and consumable pickup, transfer,
  purchase, and overflow paths; verify no item is lost or duplicated.
- [x] Complete a full ground-combat lifecycle with firing, reload, Med Pack,
  Combat Stim, loot pickup, and persistence.

**PLAYTEST RESULT — COMPLETE (2026-08-14):** The full ground-equipment
lifecycle was manually confirmed good across city, space, Scout Derelict,
Expedition Pack capacity/overflow, duplicate-weapon reloads, consumable use,
loot pickup, combat feedback, and save/Continue boundaries. The compact loot
chooser and its scrollbar were also verified for long option lists.

## Pre-implementation audit

### Existing modules/classes to reuse

- `GameContext.ground_expedition_inventory` and
  `ground_equipment.expedition_capacity()` for carried capacity.
- `StoredGroundEquipment` and its strict catalog validation for legacy weapon
  and armor ownership.
- `character_screen._equipment_rows`, `_swap_from_pack`,
  `pygame_screen.ScreenRow`, and `pygame_story.choose()` for backpack actions.
- `combat/_loop._handle_character_action`, `can_fire()`, and `consume_shot()`
  for combat menu/AP/action integration.
- `saveload._ctx_to_dict`, `_ground_equipment_from_dict`, and `load_game()` for
  migration and malformed-entry filtering.
- Ground weapon frozen specs and the data-catalog discovery pattern for ammo
  and consumable catalogs.
- Existing ship ammo state and slot-indexed ship combat ammo synchronization as
  a cautionary implementation model, not a type to copy blindly.

### Duplication hotspots and DRY strategy

1. **Weapon state could fork between armory, character screen, and combat.**
   Keep active-instance mutation and reload computation in a domain module;
   UI actions call it and combat reads the same state.
2. **Ammo validation could be repeated in fire, reload, loot, and shops.**
   Centralize `ammo_type`, capacity, stack limits, and reload calculations in
   pure helpers; use one parser for save/load and loot payloads.
3. **Consumable effects could become UI conditionals.** Use a validated effect
   registry/table with pure effect calculation and thin mutation wrappers.
4. **Pack capacity could diverge for equipment, ammo, and consumables.** Use
   one inventory-capacity policy that receives an item/stack proposal and
   returns the resulting slot/stack usage.
5. **Per-ID ammo could accidentally merge duplicate weapons.** Treat active
   weapons as instances with stable slot/instance identity; add duplicate
   tests before changing combat.

## Acceptance criteria

- Successful combat equipment swaps close the menu before the next combat
  frame; AP loss and any enemy turn are visible.
- Backpack equipment rows are selectable and Enter presents Equip/Discard.
- Persistent ammo is enabled for ground weapons: each active instance has an
  independent magazine, reserve ammo is typed and stackable, and reloads are
  transactional.
- Reloadable weapons have independent loaded magazines after implementation.
- Firing consumes ammo exactly once per weapon shot and blocks empty weapons
  without blocking valid weapons in the same burst.
- Reload moves matching reserve ammo into the magazine transactionally and costs
  the documented AP.
- Ammo stacks and consumables use Expedition Pack capacity and survive save/load.
- Med packs/stims use explicit effects and do not mutate state when canceled or
  invalid.
- Ground loot, armory purchases, swaps, discards, reloads, and consumable use
  never silently lose or duplicate items.
- Legacy saves without magazine fields migrate to deterministic full
  magazines; malformed field-item records are ignored without breaking load.
- Malformed active ground stats, armor slots, and HP values are normalized
  without breaking load or creating invalid runtime state.
- The guide documents every shipped action and keybinding.
- Smoke and the full test suite pass for every implementation phase.

## Open questions

1. Is one pack slot per ammo stack the right first capacity rule, or should
   ammo consume weighted capacity from the beginning? **(Resolved: one stack =
   one slot, matching equipment; `rounds_per_stack` is the efficiency knob.
   Weighted capacity deferred until the Phase 4 playtest.)**
2. **Resolved:** `R` opens a weapon chooser when multiple active weapons can
   reload; the action validates the selected weapon before charging AP.
3. **Resolved:** tactical reloads retain loaded rounds and transfer only the
   missing amount.
4. **Resolved:** med packs are free to use during exploration and consume their
   catalog `use_ap_cost` during combat. Combat-only stims cannot be used outside
   an active ground fight.
5. **Resolved:** stims use a combat-local, data-defined duration measured in
   ground-combat turns. The initial stim starts at 3 turns; effects end when
   combat ends and are not persisted outside combat.
6. **Resolved:** ground ammo and consumables are purchased at the Ground Armory
   only; each purchase chooses Armory Storage or Expedition Pack before payment.
7. **Resolved:** pickup auto-fills matching partial stacks, creates new stacks
   while capacity remains, and leaves any overflow on the floor. No stack
   destination chooser is needed in the first pass.
