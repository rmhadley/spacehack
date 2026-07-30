# DESIGN: Bar Missions — Shady Pirate Contracts

## Overview

Give the Barkeep NPC (guild `bar`) an active mission board with shady pirate-style contracts. Unlike clean merchant deliveries or guild-sanctioned bounty hunting, bar missions are criminal work on the fringe of the law. Four mission types provide variety:

1. **Intercept** (merchant hunting) — track down a merchant vessel, destroy it, loot a specific good, return to the bar.
2. **Smuggling** — move contraband goods through militia-patrolled systems to a destination. Risk of cargo scans.
3. **Extortion** — "collect what they owe us." Fly to a system, find a target via comms, demand tribute.
4. **Salvage rights** — a pirate crew lost a wreck in hostile space. Destroy the patrol guarding it, loot the mission component, return.

All bar missions share: high pay, risk of militia attention, and a clear criminal alignment path for players who want it.

### Player flow — Intercept (reference)

1. Talk to the Bartender → "View available work"
2. Accept an intercept mission
3. Travel to target system
4. Find and destroy the merchant ship in combat
5. Loot the mission-specific good from the wreckage
6. Return to the bar and deliver the stolen cargo

## Philosophy alignment

| Principle | How it applies |
|-----------|---------------|
| **Data-first** | Hand-crafted intercept missions go in `data/missions/bar.py`; procedural generation shares patterns with delivery/bounty generators |
| **ctx-first** | Mission-specific loot tracking goes through `ActiveMission.heist_target_good_id` and `OwnedShip.inventory` |
| **Domain owns flow** | Intercept mission logic lives in `mission.py` alongside delivery/bounty; faction reputation updates live in the completion path |
| **Board-driven** | Same `MissionBoard` / `fill_empty_slots` / `refresh_all_boards` infrastructure — just add `"bar"` to the guild gate |
| **Tiered** | Tiers 1-4, same rarity curve (min-of-two-rolls), planet `mission_tier` gating |
| **Seeded RNG** | All procedural generation uses `engine.RNG` |

## Data model

### New fields on `MissionSpec`

- **`heist_target_good_id: str | None = None`** — trade good ID the player must loot and return (e.g. `"electronics"`)
- **`heist_target_enemy_id: str | None = None`** — NPC ship spec to spawn as the target merchant vessel (e.g. `"merchant_scout"`)
- **`heist_target_system_id: str | None = None`** — system where the merchant patrols

(These mirror the existing bounty fields but for the intercept flow.)

### New fields on `ActiveMission`

- **`heist_target_good_id: str | None = None`** — snapshot for quest log + completion check
- **`heist_target_enemy_id: str | None = None`** — for merchant ship spawn
- **`heist_target_system_id: str | None = None`** — for spawn + quest log

### Existing infrastructure to reuse

| System | How bar missions use it |
|--------|------------------------|
| `OwnedShip.inventory` | Looted goods go here; mission checks inventory on deliver |
| `ctx.bounty_spawns` | Pattern reused — spawn a merchant ship as a dynamic target |
| `_add_bounty_spawns_to_map` / `_remove_bounty_spawn` | Reused for merchant ship spawn/despawn |
| `faction_reputation` | Completing a heist reduces `"merchant"` rep (e.g. -10) |
| `faction.get_attitude` | Merchant rep decay may eventually turn merchants hostile |
| `mission_module.board_remove` / `board_return_static` | Same board management |
| `find_deliverable_missions` | Reused — bar missions are "delivered" to the barkeep |
| `complete_mission` | Reused for reward payout + cargo removal |
| `_run_cargo_scan` | Militia scans can catch stolen goods (contraband) |

### HeistSpawn helper

Analogous to `BountySpawn`, a lightweight frozen dataclass placed on `ctx.bounty_spawns` (same dict, keyed by system). Reuses the same spawn infrastructure since the lifecycle (create on accept, place on map on jump/launch, remove on complete/abandon) is identical.

The merchant ship entity gets an attribute `heist_spawn_id` linking back to the mission, so combat knows when the merchant is destroyed.

## Mission type details

### Intercept — Merchant hunting

Player flow: accept → travel to target system → find merchant → destroy → loot good → return.

Tier progression (the merchant ship gets tougher + gains escorts):

| Tier | Merchant ship | Weapons | Escorts | Threat profile |
|------|--------------|---------|---------|---------------|
| 1 | `merchant_hauler` (Hauler hull) | 0-1 light laser | None | Easy — free loot, barely fights back |
| 2 | `merchant_hauler` (Hauler hull) | 1 light laser | 1 pirate_scout | Moderate — some resistance |
| 3 | `merchant_freighter` (Freighter hull) | 1-2 light lasers | 2 pirate_scouts | Tough — merchant has teeth, escorts flank |
| 4 | `merchant_caravan` (Freighter hull) | 2 light lasers + 1 heavy | 2 pirate_raiders | Deadly — merchant armed to the teeth with fighter-class escorts |

Merchants are **non-hostile** — they don't attack on sight. The player engages them (or uses comms to demand cargo). Heist completes when the **merchant** is destroyed.

### Smuggling — Contraband transport

Player flow: accept at bar → receive contraband cargo → travel to destination planet → deliver to a specific NPC → get paid.

Mechanically similar to delivery missions, but the cargo is **flagged as contraband**. Militia cargo scans (`_run_cargo_scan`) can catch it. The **smuggler's hold ship module** hides up to X cargo from scans.

Tier progression:

| Tier | Cargo size | Scan risk | Route type | Reward premium over delivery |
|------|-----------|-----------|------------|------------------------------|
| 1 | 5-10 | Low (few militia planets) | 1 hop | +25% |
| 2 | 10-20 | Medium (1-2 militia planets) | 1-2 hops | +40% |
| 3 | 20-40 | High (must pass through militia) | 2-4 hops | +60% |
| 4 | 40-60 | Extreme (militia home system) | 3-6 hops | +100% |

Deadlines are generous to allow circuitous routes that avoid heavily-patroled systems.

### Extortion — Debt collection

Player flow: accept at bar → travel to target system → find the target via comms or sensor ping → hail them → demand tribute → pay up or fight.

Reuses the existing comms hail system. The hail dialog presents options:
- Demand payment (credits transferred instantly)
- Demand cargo (goods added to inventory)
- Threaten (target may flee or fight)
- Let them go (mission fails)

Tier progression:

| Tier | Target type | Default response | Combat response | Payout range |
|------|------------|-----------------|----------------|-------------|
| 1 | Solo civilian hauler | Pays up (50%) | Fights back weakly, no militia | 150-250$ |
| 2 | Merchant runner | Pays up (40%) | Fights back + 30% chance militia arrives | 300-500$ |
| 3 | Trade convoy (2 ships) | Pays up (30%) | Both fight back + 50% chance militia arrives | 700-1100$ |
| 4 | Outpost supply (3 ships, 1 armed) | Pays up (20%) | Heavy fight + militia guaranteed on combat | 1500-2500$ |

Reward is immediate on payment — no return trip required. But higher tiers mean combat is more likely and militia response is nearly guaranteed.

### Salvage rights — Wreck recovery

Player flow: accept at bar → travel to target system → find a wreck marked on the map → destroy the patrol guarding it → loot the component → return to bar.

The wreck is a static map feature. A patrol squad spawns nearby. Once the patrol is cleared, the player can interact with the wreck to extract the specific mission component.

Tier progression:

| Tier | Patrol composition | Wreck location | Component value |
|------|-------------------|---------------|----------------|
| 1 | 1 pirate_scout | Near landmark, safe-ish space | 180$ |
| 2 | 2 pirate_scouts | Open space, moderate distance from gate | 400$ |
| 3 | 1 pirate_raider + 1 pirate_scout | Behind a planet, near enemy territory | 850$ |
| 4 | 2 pirate_raiders + 1 pirate_captain | Deep in hostile space, 5+ hops out | 2000$ |

No random loot — just the mission component. Patrols don't despawn until cleared (you can leave and come back).

## New ship module: Smuggler's Hold

A module that hides up to X cargo units from militia scans. Higher-tier versions hide more:

| Module | Cargo hidden | Slots | Tech level | Price |
|--------|-------------|-------|-----------|-------|
| `smuggler_hold_mk1` | 10 | 1 | 1 | 200$ |
| `smuggler_hold_mk2` | 25 | 1 | 2 | 500$ |
| `smuggler_hold_mk3` | 50 | 1 | 3 | 1200$ |

Works by marking cargo as "hidden" when the scan runs. Only affects cargo scan outcome — doesn't change actual cargo capacity or storage. Only affects *smuggling* mission cargo, not regular trade goods (unless the player is carrying contraband they acquired independently).

## Faction reputation impact

*(To be designed — see `docs/design/in_progress/DESIGN_FACTION_REPUTATION.md`)*

## Hand-crafted missions (Phase 1)

### Intercept

| ID | Title | Tier | Target Good | Target Ship | System | Rewards |
|----|-------|------|-------------|-------------|--------|---------|
| `bar_intercept_earth_ac` | The AC Run | 1 | `electronics` | `merchant_hauler` | Alpha Centauri | 200$ / 40xp |
| `bar_intercept_vega_components` | Vega Components | 2 | `machine_parts` | `merchant_hauler` | Vega | 400$ / 70xp |
| `bar_intercept_sirius_luxury` | Sirius Luxury | 3 | `luxury_goods` | `merchant_freighter` | Sirius | 800$ / 140xp |
| `bar_intercept_frontier_tech` | Frontier Tech | 4 | `electronics` | `merchant_caravan` | Luyten's Star | 1800$ / 300xp |

### Smuggling

| ID | Title | Tier | Contraband | Destination | System | Rewards |
|----|-------|------|------------|-------------|--------|---------|
| `bar_smuggle_mars_weapons` | Mars Weapons Run | 1 | `weapons` | Mars Barkeep | Sol | 150$ / 25xp |
| `bar_smuggle_sirius_tech` | Sirius Black-Tech | 2 | `electronics` | Sirius Station | Sirius | 350$ / 60xp |
| `bar_smuggle_vega_drugs` | Vega Narcotics | 3 | `luxury_goods` | Vega Barkeep | Vega | 700$ / 120xp |
| `bar_smuggle_frontier_fuel` | Frontier Fuel Heist | 4 | `fuel_cells` | Blockade Station | Luyten's Star | 1500$ / 250xp |

### Extortion

| ID | Title | Tier | Target | System | Rewards |
|----|-------|------|--------|--------|---------|
| `bar_extort_mars_debt` | Mars Debt | 1 | Civilian hauler | Sol | 200$ / 30xp |
| `bar_extort_sirius_protection` | Sirius Protection | 2 | Merchant runner | Sirius | 400$ / 65xp |
| `bar_extort_vega_interest` | Vega Interest | 3 | Trade convoy | Vega | 900$ / 150xp |
| `bar_extort_frontier_tribute` | Frontier Tribute | 4 | Outpost supply | Luyten's Star | 2000$ / 350xp |

### Salvage rights

| ID | Title | Tier | Component | System | Rewards |
|----|-------|------|-----------|--------|---------|
| `bar_salvage_tau_parts` | Tau Ceti Wreck | 1 | `machine_parts` | Tau Ceti | 180$ / 35xp |
| `bar_salvage_epsilon_drive` | Epsilon Drive | 2 | `electronics` | Epsilon Eridani | 400$ / 70xp |
| `bar_salvage_procyon_core` | Procyon Core | 3 | `fuel_cells` | Procyon | 850$ / 140xp |
| `bar_salvage_luyten_blackbox` | Luyten Black Box | 4 | `luxury_goods` | Luyten's Star | 2000$ / 320xp |

## Domain changes

### Phase 1: Data model — Intercept (the foundation)

- [ ] Add `heist_target_good_id`, `heist_target_enemy_id`, `heist_target_system_id` to `MissionSpec` (defaulting to None)
- [ ] Add same fields to `ActiveMission`
- [ ] Add merchant NpcShipSpec entries (`merchant_hauler`, `merchant_freighter`, `merchant_caravan`)
- [ ] Add HeistSpawn helper dataclass (mirrors BountySpawn)
- [ ] Populate `data/missions/bar.py` with 4 hand-crafted intercept missions
- [ ] Wire `fill_empty_slots` guild gate to include `"bar"` guild
- [ ] Wire `heist_target_*` fields into ActiveMission during accept flow (intercept variant)
- [ ] Wire intercept combat completion (destroy merchant → loot drops specific good)
- [ ] Wire intercept delivery to barkeep (complete on cargo hand-in)

### Phase 1.5: Playtest — Intercept

**Checklist:**
- [ ] Visit Earth bar → missions visible
- [ ] Accept intercept → merchant spawns in target system
- [ ] Destroy merchant → specific good appears in inventory
- [ ] Return to bar → deliver → reward granted, good removed

### Phase 2: Smuggling

- [ ] Add `generate_smuggle_mission` to `mission.py` — like delivery, but contraband cargo + scan risk
- [ ] Add smuggler's hold module entries to `data/modules/`
- [ ] Wire cargo scan to check smuggler's hold (hidden cargo passes scan)
- [ ] Add 4 hand-crafted smuggling missions to `bar.py`
- [ ] Quest log: show contraband type, route, scan risk warning

### Phase 3: Extortion

- [ ] Add extortion comms dialog (demand payment, demand cargo, threaten, let go)
- [ ] Add civilian NPC ship spec (non-hostile, carries credits + cargo)
- [ ] Wire extortion outcome: pay (instant reward) or fight (combat + possible militia)
- [ ] Add 4 hand-crafted extortion missions to `bar.py`
- [ ] Quest log: show target name, system, "collect what they owe"

### Phase 4: Salvage rights

- [ ] Add wreck/interactable entity type (static loot point on map)
- [ ] Add patrol spawn around wreck (combat encounter)
- [ ] Wire wreck interaction: "Extract component" after patrol cleared
- [ ] Add 4 hand-crafted salvage missions to `bar.py`
- [ ] Quest log: show component, system, patrol threat level

### Phase 5: Procedural generation + polish

- [ ] Add `generate_bar_mission` that dispatches to sub-generators by type
- [ ] Wire into `fill_empty_slots` for `guild == "bar"` (already done in Phase 1)
- [ ] Help guide section for all bar mission types
- [ ] Barkeep flavor text variations per mission type
- [ ] DRY scan across all four bar mission code paths
- [ ] RNG audit

## Contracts compliance (MANDATORY — see knowledge.md)

- [ ] **Save/load:** New ActiveMission fields (`heist_target_*`) → added to both `_ctx_to_dict()` AND `load_game()`
- [ ] **Save/load:** Smuggler's hold `hidden_cargo` → computed from modules (no new field needed, but verify module bonuses survive save/load)
- [ ] **NPC spawns:** Merchant target ships, patrol guards → registered in `ctx.procedural_spawns` with matching `squad_id`
- [ ] **NPC cleanup:** Intercept target killed → spawn removed from `ctx.procedural_spawns` via per-kill handler
- [ ] **Game guide:** Bar missions → new `_GUIDE_BAR_MISSIONS` section or update `_GUIDE_MISSIONS`
- [ ] **Game guide:** Smuggler's hold module → update `_GUIDE_SHIPS` module table

## Open questions

1. **How does the player know WHERE in the system the target is?** Sensor ping on system entry (intercept/salvage), comms ping (extortion), landmark marker (salvage wreck).
2. **Should stolen goods be contraband for militia scans?** Yes — extends risk/reward tension to intercept missions too. Smuggler's hold module mitigates this.
3. **What happens if the player's ship is destroyed?** Mission auto-fails on death.
4. **Extortion: what if the target has nothing to give?** Always yields at least some credits. Higher tier = better payout.
5. **Salvage: can the player loot the wreck early and skip the patrol?** No — patrol must be cleared first (wreck is non-interactable until enemies are dead).
6. **What if the player already has the target good in their inventory (intercept/salvage)?** Mission completion checks for the specific mission-tagged item, not just a count.
