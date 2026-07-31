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
- **`bounty_wingmate_enemy_id: str | None = None`** — ship type for the squad's wingmates when it's a MIXED squad. None (default) = wingmates are the same ship as the leader (bounty default). Intercepts use this to spawn pirate fighter escorts alongside the merchant — e.g. `bounty_target_squad_size=2` + `bounty_wingmate_enemy_id="pirate_scout"` puts one Pirate Scout in the merchant's squad.

(These mirror the existing bounty fields but for the intercept flow.)

**Mixed-squad escort (playtest feature):** The squad system was already type-agnostic at the plumbing level — every `BountySpawn` carries its own `enemy_id`, and `_detect_combat_encounter` / comms Attack / `_add_bounty_spawns_to_map` / `_remove_bounty_spawn` all resolve specs per-spawn. Adding `bounty_wingmate_enemy_id` to `MissionSpec` (and mirroring it on `ActiveMission` for save/load + quest log) lets a hand-crafted mission declare a different wingmate ship. The AC Run (T1) now spawns `merchant_hauler` + 1 `pirate_scout` escort; escorts fight as one squad with the merchant (auto-hail pulls the whole group), and only the merchant leader counts for heist completion.

### New fields on `ActiveMission`

- **`heist_target_good_id: str | None = None`** — snapshot for quest log + completion check
- **`heist_target_enemy_id: str | None = None`** — for merchant ship spawn
- **`heist_target_system_id: str | None = None`** — for spawn + quest log
- **`heist_good_secured: bool = False`** — True once the mission's loot entity is secured. Delivery checks THIS flag, never the trade inventory — buying the target good at a terminal does NOT complete the mission.

### Mission-tagged cargo (design decision — from open question #6)

Intercept loot is mission-tagged, not a generic inventory count:

- The loot entity (`%`) carries `heist_mission_id` linking it to the exact `ActiveMission` (two intercept missions can target the same good — e.g. `electronics` at T1 and T4 — so a good-id match is not enough).
- Securing the loot sets `ActiveMission.heist_good_secured = True` and reserves the good's volume in `OwnedShip.mission_reserved` — the existing MISSION CARGO hold concept (shown in the cargo screen, consumed by `cargo_used`).
- The good never enters `OwnedShip.inventory`, so it cannot be sold at a trade terminal and does not stack with bought/traded goods.
- Delivery (`active_is_deliverable_at`) checks `heist_good_secured`, not `inventory[good] > 0`.
- `complete_mission` / `abort_mission` release the reserved volume (shared `_reserved_heist_volume` helper).

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
| `bar_intercept_earth_ac` | The AC Run | 1 | `electronics` | `merchant_hauler` + 1 `pirate_scout` escort | Alpha Centauri | 200$ / 40xp |
| `bar_intercept_vega_components` | Vega Components | 2 | `machine_parts` | `merchant_hauler` | Vega | 400$ / 70xp |
| `bar_intercept_sirius_luxury` | Sirius Luxury | 3 | `luxury_goods` | `merchant_freighter` | Sirius | 800$ / 140xp |
| `bar_intercept_frontier_tech` | Frontier Tech | 4 | `electronics` | `merchant_caravan` | Luyten's Star | 1800$ / 300xp |

**Escort rule:** T1+ intercepts may include pirate fighter escorts via `bounty_wingmate_enemy_id`. Escorts spawn with the merchant, share its squad id, and trigger like bounty wingmen (auto-hail / combat start). Only the merchant leader completes the mission; escorts are bonus kills + bonus rep/loot.

**Deadline rule (playtest fix):** Intercepts are ROUND TRIPS — fly out, kill, fly back — so deadlines are scaled to real travel distance at starter-ship speed (10 moves/day), with ~2.1-2.2x headroom so BOTH on-time completion AND the early bonus (< half the deadline) are achievable at starter speed (faster ships get slack). Measured round trips: AC ~41d (deadline 90), Vega ~32d (70), Sirius ~69d (150), Luyten ~169d (360). The old 30/40/50/60 ladder was impossible (T1 needed 41d on a 30d clock; T4 is a 10-jump/100-fuel run on an 80-fuel tank).

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

## Pre-implementation audit (MANDATORY — knowledge.md)

### Existing infrastructure to reuse

| What | Where | How intercept reuses it |
|------|-------|-------------------------|
| `MissionSpec` | `data/missions/__init__.py:21` | Add `heist_target_good_id`. Auto-discovery picks up new `bar.py`. |
| `ActiveMission` | `mission.py:63` | Add `heist_target_good_id`. Reuse `delivery_target_npc_id="barkeep"` + `delivery_target_planet_id` for return tracking. |
| `BountySpawn` | `game_context.py:107` | Spawn merchant ships via same `ctx.bounty_spawns` dict. No new spawn dataclass needed. |
| `_add_bounty_spawns_to_map` | `navigation.py` | Places merchant entity on space map on jump/launch. Same code path as bounty targets. |
| `_detect_combat_encounter` | `navigation.py:421` | Already scans entities by faction proximity. If player has enemy merchant rep, merchant triggers combat on approach. |
| `_handle_combat_encounter` | `combat/_encounter.py:20` | Post-victory: add parallel `defeated_heist_ids` check to spawn mission loot. |
| `on_kill` | `combat/_rules_space.py:474` | Already calls `_spawn_loot_drops`. Add check: if entity has `heist_spawn_id`, append to `defeated_heist_ids`. |
| `_spawn_loot_drops` | `combat/_actions.py` | Existing helper for random cargo loot. Intercept adds mission-specific `%` entity at same position. |
| `open_loot_pickup` | `trade.py` | Already works for `loot_data` entities in space mode. Player flies over `%` to collect. |
| `fill_empty_slots` | `mission.py:430` | Static missions from `missions_offered_by("barkeep")` fill before the procedural early-return. No change needed. |
| `find_deliverable_missions` | `mission.py:226` | Checks `delivery_target_npc_id` + `delivery_target_planet_id`. Intercept sets both to barkeep + accept planet. |
| `complete_mission` | `mission.py:241` | Drops cargo (looted good), grants credits/XP, applies rep changes. Works as-is. |
| `merchant_hauler` | `data/npc_ships/core.py:165` | Already exists with `faction="merchant"`, unarmed. Tier 1 ready. |
| `_COMBAT_KILL_DELTAS` | `faction.py:185` | Already has `"merchant"` deltas. Killing merchants has rep consequences today. |
| Comms Attack flow | `comms.py:408` | Returns `_attack_data` → `_handle_combat_encounter`. Player hails merchant → Attack → combat. |

### Three duplication hotspots + DRY strategies

#### Hotspot 1: Merchant spawn accept flow duplicates bounty accept

**Risk:** The 40-line bounty accept block in `__main__.py` would be copy-pasted for intercept.

**DRY strategy:** `BountySpawn` already supports any `enemy_id`. Add `heist_spawn_id` field to `BountySpawn` (defaults `None`). The intercept accept flow creates a `BountySpawn` with `heist_spawn_id` set. The entity-placement code in `navigation.py` sets `bounty_spawn_id` on the entity for bounty spawns, or `heist_spawn_id` for intercept spawns. Single code path, attribute-driven.

#### Hotspot 2: Post-kill heist loot spawn duplicates cargo loot spawn

**Risk:** `_rules_space.py::on_kill` already calls `_spawn_loot_drops()`. Adding a second spawn call duplicates entity construction.

**DRY strategy:** In `on_kill`, if the dead entity has `heist_spawn_id`, append it to `cr.defeated_heist_ids` (same pattern as `defeated_bounty_ids`). In `_encounter.py`'s post-victory handler, iterate `defeated_heist_ids` against active missions and spawn one `%` loot entity per match. The loot entity construction reuses the existing `world.Entity(loot_data=...)` pattern.

#### Hotspot 3: Missions catalog module duplicates existing faction modules

**Risk:** Creating `data/missions/bar.py` by copy-pasting `merchants.py`.

**DRY strategy:** `bar.py` only needs a `MISSIONS` tuple of `MissionSpec` entries with `giver_npc_id="barkeep"`. Auto-discovery picks it up. Follow the existing pattern from `data/missions/bounty.py`.

### Files to create / modify

| File | Change |
|------|--------|
| `data/missions/bar.py` | **New** — 4 hand-crafted intercept missions |
| `data/npc_ships/core.py` | Add `merchant_freighter`, `merchant_caravan` |
| `data/missions/__init__.py` | Add `heist_target_good_id` to `MissionSpec` |
| `mission.py` | Add `heist_target_good_id` to `ActiveMission` |
| `game_context.py` | Add `heist_spawn_id` to `BountySpawn` |
| `combat/_types.py` | Add `defeated_heist_ids` to `CombatResult` |
| `combat/_rules_space.py` | `on_kill`: if entity has `heist_spawn_id`, append to `cr.defeated_heist_ids` |
| `combat/_encounter.py` | Post-victory: spawn `%` loot entity for each defeated heist |
| `__main__.py` | Intercept accept flow: create `BountySpawn` with `heist_spawn_id`, store delivery fields on `ActiveMission` |
| `saveload.py` | Serialize/deserialize `heist_target_good_id` on `ActiveMission` |
| `help.py` | Bar missions guide section |
| `faction.py` | `_MISSION_REP_DELTAS` entry for `"bar_intercept"` |

## Domain changes

### Phase 1: Data model — Intercept (the foundation)

- [x] Add `heist_target_good_id` to `MissionSpec` — `data/missions/__init__.py:103`. `target_enemy_id` / `target_system_id` reuse the existing bounty fields (no new `heist_target_enemy/system` fields — DRY per audit Hotspot 1)
- [x] Add `heist_target_good_id` to `ActiveMission` — `mission.py:92` (delivery + bounty fields reused for return tracking)
- [x] Add merchant NpcShipSpec entries (`merchant_hauler`, `merchant_freighter`, `merchant_caravan`) — `data/npc_ships/core.py`
- [x] Heist spawn support — `BountySpawn.heist_spawn_id` (`game_context.py:128`) instead of a separate HeistSpawn class (audit Hotspot 1 DRY strategy)
- [x] Populate `data/missions/bar.py` with 4 hand-crafted intercept missions
- [x] Wire barkeep board — auto-discovery via `_build_registry` + static fill in `fill_empty_slots` (`missions_offered_by("barkeep")`). Procedural bar gen deferred to Phase 5
- [x] Wire `heist_target_*` fields into ActiveMission during accept flow — `__main__.py` intercept accept block
- [x] Wire intercept combat completion — `CombatResult.defeated_heist_ids` (`combat/_types.py:67`), `on_kill` appends (`_rules_space.py:563`), post-victory loot spawn (`_encounter.py:147`)
- [x] Wire intercept delivery to barkeep — `active_is_deliverable_at` checks ship inventory for the looted good (complete on cargo hand-in, no auto-complete on kill)

### Phase 1.5: Playtest — Intercept

**Status: code complete, ready for playtest.** Crash fixed (`fix: heist loot spawn no longer crashes on_kill` — `753833e`): heist loot entities set `heist_mission` post-construction (Entity has no such field) and the flag survives save/load.

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

- [x] **Save/load:** New ActiveMission field `heist_target_good_id` → added to both `_ctx_to_dict()` AND `load_game()` (`saveload.py:359`); heist loot `heist_mission` flag persisted + restored
- [ ] **Save/load:** Smuggler's hold `hidden_cargo` → computed from modules (no new field needed, but verify module bonuses survive save/load)
- [x] **NPC spawns:** Merchant target ships → placed via `ctx.bounty_spawns` (BountySpawn with `heist_spawn_id`), saved/restored in saveload
- [x] **NPC cleanup:** Intercept target killed → `defeated_heist_ids` handled in `_encounter.py` post-victory; spawn removed via `_remove_bounty_spawn`
- [x] **Game guide:** Bar missions → `_GUIDE_BAR_MISSIONS` section (`help.py:896`)
- [ ] **Game guide:** Smuggler's hold module → update `_GUIDE_SHIPS` module table

## Open questions

1. **How does the player know WHERE in the system the target is?** Sensor ping on system entry (intercept/salvage), comms ping (extortion), landmark marker (salvage wreck).
2. **Should stolen goods be contraband for militia scans?** Yes — extends risk/reward tension to intercept missions too. Smuggler's hold module mitigates this.
3. **What happens if the player's ship is destroyed?** Mission auto-fails on death.
4. **Extortion: what if the target has nothing to give?** Always yields at least some credits. Higher tier = better payout.
5. **Salvage: can the player loot the wreck early and skip the patrol?** No — patrol must be cleared first (wreck is non-interactable until enemies are dead).
6. **What if the player already has the target good in their inventory (intercept/salvage)?** RESOLVED — mission completion checks the per-mission `heist_good_secured` flag (set only by securing the mission-tagged loot entity), not an inventory count. Buying the good at a terminal or carrying it from another mission never completes the intercept.
