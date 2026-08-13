# Ground Equipment Expansion — weapons, armor, cybernetics, plasma, tier gating

> Status: in progress — reviewed and fully resolved; ready to implement.

## Overview

Ground combat gear currently tops out at tech level 2 for weapons and level 3
for armor, with only 9 armor pieces across 5 slots and no T4 anywhere. The
armory sells **everything everywhere** (no planet tech-level gating), and
enemy equipment drops are hand-authored per NPC with no tier awareness.

This pass expands the catalogs to a full T1–T4 curve, adds plasma weapons and
cybernetic armor pieces, gives enemies armor DR (so plasma and armor have real
counterplay), and makes armory stock + enemy drops respect planet tier exactly
like ship weapons/modules do via the mechanic.

Non-goals (owned by other docs): ammo + field consumables (doc 19), crew
combat, and any *new* equipment slots (cybernetics deliberately reuse the
existing five armor slots — see below).

## Philosophy alignment

| Guardrail | How this design honors it |
|-----------|---------------------------|
| Data-first | New gear = entries in existing `WARES` / `NPC_CHARS` tuples. No runtime logic per item. |
| State tables over conditionals | Damage-type → armor interaction table; tier → drop pool filtering. |
| ctx-first | Combat effects read equipped armor via `ctx.equipped_ground_armor`; no bare globals. |
| Pure functions | `sum_armor_bonus`, plasma damage, tier filtering, and `resolve_armory_inventory` are pure/testable. |
| Save/load contract | **No schema change** — cybernetics are armor; new items and enemy `tier`/`armor` are catalog data. |
| Game guide contract | Update `data/guide/` ground-gear section for plasma + cybernetics + tier availability. |
| SRP / file size | Keep `_rules_ground.py` < 1000 lines; extract helpers rather than growing functions. |

## Current state (audit snapshot)

- **Weapons** (`data/ground_weapons/`): pistols T1 (laser/kinetic), rifles T1–T2
  (shotgun T1, laser/kinetic rifle T2), melee T1–T2, monster weapons T1–T2
  (`shop_available=False`). Damage types `melee/kinetic/energy/explosive` —
  **explosive is defined but unused**; no plasma.
- **Armor** (`data/ground_armor/vests.py`): 9 pieces, T1–T3. Slots `head/body/
  hands/legs/feet`. Hands/feet have one T1 item each; no T4 anywhere.
- **Armory** (`menus/_armory.py`): `_buy_rows()` lists every `shop_available`
  weapon and **all** armor, ignoring planet `tech_level`.
- **Mechanic** (`data/planets/__init__.py::resolve_mech_inventory`): the model —
  fixed per-planet overrides (`mech_weapons`/`mech_modules`) or an RNG subset
  of `tech_level <= planet.tech_level`.
- **Enemy drops** (`combat/_rules_ground.py` on-kill → `_shared_equipment_loot`):
  uses `NpcCharSpec.equipment_loot_pool` verbatim; no tier field, no filter.
- **Enemy armor** (`_rules_ground.py::damage`): player attacks apply
  `max(1, damage + str_bonus)` with **no** enemy armor; only the enemy→player
  path (`_ground_damage_raw` in `_ai_ground.py`) subtracts armor DR.
- **Ground AP** (`_rules_ground.py::init`): `4 + ace_pilot_bonus`. Max HP:
  `20 + stamina // 3`.
- **Plasma animation**: `_shot_animations._shot_family` already maps ship
  `plasma → plasma` and ground `energy → laser`; the ship plasma bolt exists
  and can be reused.

## Data model

### `GroundWeaponSpec` (unchanged schema, new values)

Add the `"plasma"` damage type to the documented set. No new fields.

### `GroundArmorSpec` (schema extension)

Add four optional effect fields (default `0`) so cybernetics are just armor:

```python
ap_bonus: int = 0        # +1 AP per ground-combat turn (cybernetic legs)
hit_bonus: int = 0       # +% hit chance (cybernetic eyes)
melee_bonus: int = 0     # +flat melee damage (cybernetic arms)
hp_bonus: int = 0        # +flat max ground HP (cybernetic torso)
```

Cybernetics are armor pieces that fill a normal slot with low/zero `defense`
and a non-zero effect field. This reuses the entire armory/expedition/
save-load/equip pipeline unchanged.

### `NpcCharSpec` (schema extension)

```python
tier: int = 1            # drop tier: equipment drops filter to tech_level <= tier
armor: int = 0           # flat DR subtracted from player hits (plasma halves it)
```

### `PlanetSpec` (schema extension — mirrors `mech_weapons`/`mech_modules`)

```python
armory_weapons: tuple[str, ...] = ()
armory_armor: tuple[str, ...] = ()
```

Empty tuples → `resolve_armory_inventory` uses seeded RNG (see below).

## Gear draft (values are tunable — flag in review)

### Weapons (new entries)

| id | type | dmg | acc | AP | hands | range | ammo | price | TL |
|----|------|-----|-----|----|-------|-------|------|-------|----|
| smg | kinetic | 5 | 70 | 1 | 1 | 1-4 | 30 | 120 | 2 |
| battle_rifle | kinetic | 14 | 68 | 2 | 2 | 2-8 | 24 | 260 | 3 |
| railgun | kinetic | 22 | 72 | 3 | 2 | 3-9 | 12 | 650 | 4 |
| laser_carbine | energy | 11 | 76 | 1 | 1 | 1-6 | 100 | 240 | 3 |
| ion_blaster | energy | 18 | 72 | 2 | 2 | 1-8 | 120 | 620 | 4 |
| plasma_pistol | plasma | 9 | 74 | 1 | 1 | 1-5 | -1 | 220 | 2 |
| plasma_rifle | plasma | 16 | 70 | 2 | 2 | 1-8 | -1 | 520 | 3 |
| plasma_caster | plasma | 24 | 66 | 3 | 2 | 1-7 | -1 | 980 | 4 |
| vibroblade | melee | 8 | 80 | 1 | 1 | 1 | -1 | 180 | 3 |
| mono_blade | melee | 13 | 78 | 1 | 2 | 1 | -1 | 420 | 4 |
| power_fist | melee | 16 | 74 | 2 | 1 | 1 | -1 | 560 | 4 |
| grenade_launcher | explosive | 15 | 62 | 2 | 2 | 3-7 | 6 | 480 | 3 |
| rocket_launcher | explosive | 30 | 58 | 3 | 2 | 2-9 | 4 | 1100 | 4 |

Plasma: infinite ammo (like ship plasma), high damage, `ap_cost` scales with
output, and it **halves the target's armor DR**. Explosive: heavy burst
damage, low accuracy, finite `ammo_capacity` (like kinetic). No new reload
mechanics — real ammo for all weapon types lands in doc 19.

### Armor + cybernetics (new entries)

| id | slot | defense | effect | price | TL |
|----|------|---------|--------|-------|----|
| visor_helmet | head | 3 | — | 140 | 3 |
| assault_helmet | head | 4 | — | 340 | 4 |
| cybernetic_eyes | head | 0 | hit_bonus +8 | 260 | 2 |
| powered_vest | body | 7 | — | 620 | 4 |
| cybernetic_torso | body | 1 | hp_bonus +3 | 520 | 3 |
| reinforced_gauntlets | hands | 2 | — | 55 | 2 |
| powered_gloves | hands | 3 | — | 130 | 3 |
| cybernetic_arms | hands | 0 | melee_bonus +2 | 340 | 2 |
| reinforced_greaves | legs | 3 | — | 140 | 3 |
| assault_greaves | legs | 4 | — | 340 | 4 |
| cybernetic_legs | legs | 0 | ap_bonus +1 | 520 | 3 |
| assault_boots | feet | 2 | — | 55 | 2 |
| powered_boots | feet | 3 | — | 130 | 3 |
| mag_boots | feet | 4 | — | 340 | 4 |

Cybernetics trade defense for a utility effect; they are the "not armored
pants, cybernetic legs" option the user described.

### Enemy armor (new DR values)

| NPC | armor | rationale |
|-----|-------|-----------|
| sentry_drone | 1 | light security frame |
| assault_drone | 3 | "armored bruiser" — plasma's best target |

Fauna (rock_scavenger, ice_worm, dust_prowler, hull_parasite, frost_spitter)
and pirates keep `armor=0`.

## Domain changes

1. **`data/ground_weapons/*.py`** — add the new weapons across `pistols.py`,
   `rifles.py`, `melee.py`, plus new `plasma.py` and `explosive.py` modules
   (auto-discovered via `WARES`). Document `"plasma"` in `__init__.py`.
2. **`data/ground_armor/vests.py`** — add armor + cybernetics; add the four
   effect fields to `GroundArmorSpec`.
3. **`data/npc_chars/__init__.py`** — add `tier` and `armor` fields; assign
   values (monsters: scavenger/dust_prowler/ice_worm/hull_parasite T1,
   sentry_drone/frost_spitter T2, assault_drone T3; pirates: raider T1,
   rifleman T2; drones get armor per the table).
4. **`combat/_shot_animations.py`** — extend the ground `_shot_family` mapping
   with `"plasma": "plasma"` (reuse the ship plasma bolt).
5. **`combat/_rules_ground.py`**
   - `_ground_damage_raw`: plasma halves `armor_defense` (`armor_defense // 2`).
   - `damage()`: refactor to call `_ground_damage_raw(weapon_id, strength,
     enemy.spec.armor)` so enemy armor DR is applied (DRY — removes the
     duplicated formula).
   - `init`: `_player_ap_total = 4 + ace_pilot_bonus + sum_armor_bonus(..., "ap_bonus")`;
     `_player_max_hp = 20 + stamina//3 + sum_armor_bonus(..., "hp_bonus")`.
   - `hit_chance`: add `hit_bonus`; melee damage adds `melee_bonus`.
6. **`ground_equipment.py`** — add pure `sum_armor_bonus(armor_ids, attr) -> int`
   summing a bonus field across equipped armor (skip `None`/unknown ids).
7. **`data/planets/__init__.py`** — add `armory_weapons`/`armory_armor` to
   `PlanetSpec` and a `resolve_armory_inventory(planet_id)` mirroring
   `resolve_mech_inventory`: verbatim override, else `shop_available and
   tech_level <= planet.tech_level`, sorted by price, `RNG.sample` of
   min(4 weapons / 6 armor).
8. **`menus/_armory.py`** — `_buy_rows()` lists `resolve_armory_inventory`
   results instead of the whole catalog; show cybernetic effects in the
   armor detail line (e.g. `Legs  Defense: 0  +1 AP`). Bare-title frame
   (`planet_id=""`) falls back to the full `shop_available` catalog.
9. **`tutorial.py`** — update the `earth_armory` text to reference a T1 weapon
   guaranteed in Earth's fixed stock (e.g. the Shotgun), since `kinetic_rifle`
   (T2) is no longer stocked at Earth.
10. **`data/planets/earth.py` + `mars.py`** — add fixed `armory_weapons`/
    `armory_armor` starter sets (mirroring their `mech_*` overrides); Earth T1
    (incl. shotgun), Mars T1–T2.
11. **`combat/_rules_ground.py` on-kill** — filter `equipment_loot_pool` to
    entries whose item `tech_level <= npc.tier` before passing to
    `_shared_equipment_loot`; expand each pool with tier-appropriate gear.
12. **`data/guide/`** — update the ground-gear section: plasma damage type,
    cybernetic effects, enemy armor, and that stock + drops scale with tier.

## Pre-implementation audit

### Reuse / extend

- `data/ground_weapons/__init__.py` registry auto-discovers `WARES` — new
  weapons need no registry edits (same for armor via `GroundArmorSpec`).
- `resolve_mech_inventory` (planets/__init__.py) is the template for
  `resolve_armory_inventory` (fixed overrides + seeded RNG subset).
- `_spawn_equipment_loot_at_position` + `_append_loot_entity` (combat/_actions.py)
  already drop `(item_type, item_id)` ground gear; only the call site adds a
  tier filter.
- `_ground_damage_raw` already exists and is the single armor-mitigation point;
  `damage()` should call it instead of duplicating the formula.
- `_shot_animations._animate_plasma_bolt` already exists for ships — reuse.
- `sum_armor_bonus` mirrors the existing `armor_defense` summation in
  `_rules_ground.init`.

### Duplication hotspots

1. Copy-pasting the mechanic's tier-filter + RNG-subset instead of extracting a
   shared helper — keep the two resolvers sibling functions with a shared
   `_filter_by_tech_level(items)` helper.
2. Re-implementing armor effect summation per stat — one `sum_armor_bonus`
   helper, called with the field name.
3. Duplicating the damage formula in `damage()` vs `_ground_damage_raw` — the
   `damage()` refactor collapses this into one path.

### DRY strategy

- `_filter_by_tech_level(items, level)` is the shared tier gate for both
  mechanic and armory resolvers.
- `sum_armor_bonus(armor_ids, attr)` is the single summation point; combat
  reads the four fields from it.
- Plasma armor interaction is a single branch in `_ground_damage_raw`, shared
  by the player→enemy (`damage()`) and enemy→player (`_ai_ground`) paths.

## Phased implementation plan

### Phase 1 — Schema + catalogs

- [ ] Add `"plasma"` damage type docs + `plasma.py`/`explosive.py` weapon modules
- [ ] Add new weapons across pistols/rifles/melee + the draft table
- [ ] Add `ap_bonus`/`hit_bonus`/`melee_bonus`/`hp_bonus` to `GroundArmorSpec`
- [ ] Add armor + cybernetic entries to `vests.py`
- [ ] Add `tier` + `armor` fields to `NpcCharSpec`; assign existing values

**PLAYTEST:** `python -m pytest tests/` green; armory still lists the full
catalog (gating lands in Phase 3), so no visible regression yet.

### Phase 2 — Combat effects (plasma, enemy armor, cybernetics)

- [ ] Extend `_shot_family` ground mapping with `"plasma"`
- [ ] `_ground_damage_raw` plasma armor bypass (half DR); `damage()` refactor to
      apply enemy `spec.armor`
- [ ] `sum_armor_bonus` + wire `ap_bonus`/`hit_bonus`/`melee_bonus`/`hp_bonus`
      into `init`/`hit_chance`/`damage`
- [ ] Unit tests for each effect + plasma DR + enemy armor

**PLAYTEST:** equip cybernetic legs → AP shows 5 (4 + 1) in ground combat;
cybernetic eyes raise hit %; plasma pistol deals full damage to an assault
drone (armor halved) while a kinetic rifle is reduced by its 3 armor.

### Phase 3 — Availability gating (armory mirrors mechanic)

- [ ] Add `armory_weapons`/`armory_armor` to `PlanetSpec` + `resolve_armory_inventory`
- [ ] `_buy_rows()` lists `resolve_armory_inventory`; bare-title fallback
- [ ] Earth/Mars fixed armory starter sets
- [ ] Update `tutorial.py` `earth_armory` text → T1 weapon (Shotgun)
- [ ] Unit tests: Earth shows fixed T1 stock; a T4 planet samples T1–T4

**PLAYTEST:** Earth armory shows the curated starter set (incl. Shotgun, no
Kinetic Rifle); tutorial popup text matches; Sirius/blockade show T3/T4 gear.

### Phase 4 — Enemy drops respect tier

- [ ] Filter `equipment_loot_pool` by `tech_level <= npc.tier` at kill time
- [ ] Expand monster + pirate equipment pools with tier-appropriate gear
- [ ] Unit tests for the filter (T1 NPC never drops T4 gear)

**PLAYTEST:** clear a tier-1 cave — drops are T1 only; kill an assault drone
(T3) — drops T3 gear; armor values visible via plasma-vs-kinetic damage. T4
gear never drops (shop-only).

### Phase 5 — Guide + detail display + final gate

- [ ] Update `data/guide/` ground-gear section
- [ ] Armory/character detail lines show cybernetic effects + weapon damage type
- [ ] `make check` (smoke + architecture + lint + full pytest)

## Acceptance criteria

- [ ] Weapons span T1–T4 across melee/kinetic/energy/plasma/explosive.
- [ ] Armor spans T1–T4 across all five slots; cybernetics occupy normal slots.
- [ ] Armory mirrors the mechanic: fixed per-planet overrides + seeded RNG
      subset, gated by `tech_level`.
- [ ] Enemy equipment drops respect `npc.tier` (up to T3; T4 is shop-only).
- [ ] Enemies with `armor > 0` reduce incoming damage; plasma halves that DR.
- [ ] Cybernetic effects (AP/hit/melee/HP) apply in ground combat and survive
      save/load (no schema migration required).
- [ ] Tutorial `earth_armory` beat names a T1 weapon that Earth actually stocks.
- [ ] `make check` green; pure-function tests in the same commits.

## Resolved decisions

- **T4 drops**: shop-only — enemy drops stop at T3; no new T4 enemy this pass.
- **Explosive**: keep grenade/rocket launchers here with finite `ammo_capacity`;
  real reload/ammo mechanics for all weapons arrive in doc 19.
- **Cybernetic legs**: `cybernetic_legs` (+1 AP) at TL3, not TL2.
