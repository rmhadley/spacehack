# DESIGN: Bar Missions — Shady Pirate Contracts

## Overview

Give the Barkeep NPC (guild `bar`) an active mission board with shady pirate-style contracts. Unlike clean merchant deliveries or guild-sanctioned bounty hunting, bar missions are criminal work on the fringe of the law. Four mission types provide variety:

1. **Intercept** (merchant hunting) — track down a merchant vessel, destroy it, loot a specific good, return to the bar.
2. **Smuggling** — move contraband goods through militia-patrolled systems to a destination. Risk of cargo scans.
3. **Extortion** — "collect what they owe us." Fly to a system, find a target via comms, demand tribute.
4. **Salvage rights** — a pirate crew lost a wreck in hostile space. Clear the patrol guarding it, **board the wreck**, fight the scavenger crew inside, extract the mission component, return.

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

**Mixed-squad escort (playtest feature):** The squad system was already type-agnostic at the plumbing level — every `BountySpawn` carries its own `enemy_id`, and `_detect_combat_encounter` / comms Attack / `_add_bounty_spawns_to_map` / `_remove_bounty_spawn` all resolve specs per-spawn. Adding `bounty_wingmate_enemy_id` to `MissionSpec` (and mirroring it on `ActiveMission` for save/load + quest log) lets a hand-crafted mission declare a different wingmate ship. Escorts fight as one squad with the merchant, and only the merchant leader counts for heist completion.

**Escort status:** The AC Run (T1) was briefly used to stress-test an extreme 5-escort config (6-ship squad); the wingmate spawn loop's 4-offset cap was lifted to 5 (`(2, 2)` added in `__main__.py`) so 5 escorts can spawn. Per playtest feedback the AC Run was reverted to an **unescorted** solo hauler — the mixed-squad mechanic stays available for future intercepts via `bounty_wingmate_enemy_id` (e.g. `bounty_target_squad_size=2` + `bounty_wingmate_enemy_id="pirate_scout"` puts one Pirate Scout in the merchant's squad).

**Squad-wide aggro (follow-up fix):** Every squad member — leader AND wingmates — carries `Entity.bounty_squad_id` (the leader's spawn id), set at spawn in `_add_bounty_spawns_to_map` and restored in both `saveload.load_game` restore loops. Comms Attack resolves the full squad from `bounty_squad_id`, so hailing ANY member (merchant OR escort) and attacking pulls the whole group into combat — matching the "one squad" expectation. Previously only the leader carried a squad reference, so hailing an escort attacked just that one ship.

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

Mechanically similar to delivery missions, but the cargo is **hot** — militia cargo scans (`_run_cargo_scan`) can confiscate it. The **smuggler's hold ship module** protects cargo from scans.

#### Design decisions (locked in design review)

1. **Cargo model: mission cargo (like intercept).** Smuggled cargo lives in `OwnedShip.mission_reserved` (MISSION CARGO hold) — it is **never** in `owned.inventory`, so it can't be sold at a terminal and can't be bought to complete the mission. Delivery is a straight NPC hand-in (no "secure loot" step — the cargo is loaded on accept). The militia scan is **extended to check smuggling mission cargo**, not just inventory. The hand-crafted good ids are flavor only — the mission's `is_smuggle` flag is what makes the cargo hot, not the good's category.
2. **Smuggler's Hold protects any contraband you carry, mission cargo first.** Hold capacity `C` (sum of installed `smuggler_cargo` module bonuses; 0 without a module). Total contraband = mission cargo volume `M` + inventory contraband volume `I`. Protection is allocated **mission-first**: `min(M, C)` of mission cargo is safe, then inventory up to the remaining `max(0, C - M)`. Anything beyond capacity is at risk — and since mission cargo claims the hold first, when the hold is full it's the **inventory contraband that gets confiscated**, leaving the mission cargo safe.
3. **On confiscation: mission auto-fails.** If any mission smuggling cargo is confiscated (only possible when `M > C` — mission cargo overflows the hold), the mission is marked failed and removed from the active list (static mission returns to the bar's board so it can be re-accepted). Inventory contraband confiscation applies the existing fine; the mission survives.

Tier progression:

| Tier | Cargo size | Hold needed (mk) | Scan risk | Route type | Reward premium over delivery |
|------|-----------|------------------|-----------|------------|------------------------------|
| 1 | 5-10 | mk1 (10) | Low (few militia planets) | 1 hop | +25% |
| 2 | 10-20 | mk2 (25) | Medium (1-2 militia planets) | 1-2 hops | +40% |
| 3 | 20-40 | mk3 (50) | High (must pass through militia) | 2-4 hops | +60% |
| 4 | 40-60 | mk3 (50) — 40-50 safe, 51-60 at risk | Extreme (militia home system) | 3-6 hops | +100% |

**Design note:** T4 (51-60 units) can exceed even the mk3 hold's 50 — that overflow is genuinely at risk, which is the intended high-stakes tension. Destination-planet scans count (the hold is the mitigation), tuned during playtest.

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

### Salvage rights — Boarded wreck recovery

Player flow: accept at bar → travel to target system → find the wreck marked on the map → **clear (or evade) the patrol guarding it (space combat)** → **board the wreck** → **fight the scavenger crew inside (ground combat)** → secure the mission component from the interior → exit to space → return to bar → deliver.

The wreck is a **boardable derelict** — this phase reuses the entire boarding + ground-combat framework shipped in ``04_DESIGN_GROUND_COMBAT_CREW.md`` (board dialog, ``load_layout`` interiors, fog of war, ``_rules_ground`` combat). A patrol squad guards it in space; boarding is possible whenever the player is out of combat (decision 3). Inside: a layout-built interior with a scavenger crew and a **guaranteed mission-tagged component** hidden in one of several marked rooms (decision 2).

Tier progression:

| Tier | Space patrol | Interior crew (layout) | Wreck | Component value |
|------|-------------|------------------------|-------|----------------|
| 1 | 1 pirate_scout | 1-2 scavengers (``scout_a``) | ``derelict_scout`` | 180$ |
| 2 | 2 pirate_scouts | 2-4 scavengers (``scout_a``) | ``derelict_scout`` | 400$ |
| 3 | 1 pirate_raider + 1 pirate_scout | 8 crew (shared ``freightliner_a`` — T3 scaling at impl) | ``derelict_freighter`` | 850$ |
| 4 | 2 pirate_raiders + 1 pirate_captain | 8 crew, heavy squads (``freightliner_a``) | ``derelict_freighter`` | 2000$ |

Patrols don't despawn until cleared (you can leave and come back). The wreck persists until the component is secured.

#### Design decisions (locked in design review)

1. **Component = heist cargo, delivered like intercept.** The mission component reuses the entire intercept delivery machinery — ``heist_target_good_id`` on MissionSpec/ActiveMission, a mission-tagged loot entity (``heist_mission=True`` + ``heist_mission_id``), ``_secure_heist_cargo`` on pickup, the ``heist_good_secured`` flag, ``mission_reserved`` hold space, and delivery to the barkeep. No new delivery path — the only difference is WHERE the component is found (inside a boarded interior instead of floating space debris).
2. **Component hides in a random marked room.** Each wreck layout declares several component-candidate rooms (bridge, engine room, cargo bay, personal storage). On FIRST board, the loader RNG-picks one and places the mission-tagged ``%`` there — the player must search the wreck, and the placement persists (interior cache, decision 6). The quest log says "somewhere in the wreck" rather than pinpointing it.
3. **Board anytime you're out of combat (no hard patrol gate).** You can't board mid-combat anyway (bump-dialog only fires between combat rounds), so the wreck is boardable as soon as the player is out of combat — however they got there (won, fled, evaded). The patrol squad still spawns around the wreck and will engage on approach, so in practice it's usually cleared first; a stealthy/evasive player can board around it. Patrol = BountySpawn squad (leader + wingmates via ``bounty_wingmate_enemy_id``); the wreck is a separate **non-combatant** BountySpawn (derelict spec: no weapons, ``ai_aggressiveness=0``).
4. **Wreck persists until the component is secured.** Unlike random derelicts (consumed on board), a mission wreck stays on the space map so the player can leave and re-board. The component can only be secured once (``heist_good_secured`` flag), so it cannot be duplicated. Once secured AND the player exits to space, the wreck despawns and its interior cache entry is dropped.
5. **Interior crew = existing pirate NPC chars as "scavengers".** ``pirate_raider`` / ``pirate_rifleman`` (``data/npc_chars/core.py``) already fill the "salvager stripping a wreck" role — their docstring says exactly that. Reuse them via layout ``ENEMY:`` directives; tiers scale squad sizes. New ``freightliner_a.layout`` (larger wreck interior) for T3+; ``scout_a`` reused for T1-2.
6. **Persistent interiors — the anti-farm answer (open question 8 RESOLVED).** Interiors must live consistently across exit/re-board AND save/load, like nethack levels live inside the save file:
   - **In-memory cache:** ``GameContext.interiors: dict[str, world.GameMap]`` keyed by a stable interior id (the wreck's BountySpawn id). First board → ``load_layout()`` → store in the cache → use. Exit → keep in the cache (don't discard the map). Re-board → reuse the cached map: fog, taken loot, dead crew, restored power, and component placement all exactly as left.
   - **Save/load:** the existing single-dungeon serialization (the ``_data["dungeon"]`` block) is the exact format we need — extract it into shared ``_dungeon_to_dict(gm, space_player_pos)`` / ``_dungeon_from_dict(data)`` helpers (DRY: currently duplicated inline in ``save_game`` / ``load_game``), then save ``_data["interiors"] = {id: _dungeon_to_dict(...)}`` for every cached interior and restore them all on load. The autosave IS the on-disk cache.
   - **Why this kills farming:** no respawn — the crew you killed stays dead, loot you took stays taken. Re-boarding a half-explored wreck is a half-explored wreck.
   - **Scope:** mission wrecks get persistent interiors now; random derelicts keep their current consume-on-board behavior (the cache infra is general and they can adopt it later if wanted).

## New ship module: Smuggler's Hold

A module that protects up to X volume of contraband from militia scans. Higher-tier versions protect more:

| Module | Cargo protected | Slots | Tech level | Price |
|--------|-----------------|-------|-----------|-------|
| `smuggler_hold_mk1` | 10 | 1 | 1 | 200$ |
| `smuggler_hold_mk2` | 25 | 1 | 2 | 500$ |
| `smuggler_hold_mk3` | 50 | 1 | 3 | 1200$ |
| `smuggler_hold_mk4` | 75 | 1 | 4 | 2500$ |

**Semantics (locked):** a new `ModuleSpec.smuggler_cargo: int = 0` bonus field (summed like every other module bonus — the combat/loadout engine already sums bonuses generically, no if/else). The scan computes total hold capacity `C` from installed modules and protects **mission smuggling cargo first**, then inventory contraband up to the remainder. It does NOT change cargo capacity or storage — only scan outcome. Contraband in inventory beyond the hold's remaining capacity is confiscated as today; mission cargo beyond the hold is confiscated → mission auto-fails.

## Faction reputation impact

*(To be designed — see `docs/design/in_progress/DESIGN_FACTION_REPUTATION.md`)*

## Hand-crafted missions (Phase 1)

### Intercept

| ID | Title | Tier | Target Good | Target Ship | System | Rewards |
|----|-------|------|-------------|-------------|--------|---------|
| `bar_intercept_earth_ac` | The AC Run | 1 | `electronics` | `merchant_hauler` (unescorted) | Alpha Centauri | 200$ / 40xp |
| `bar_intercept_vega_components` | Vega Components | 2 | `machine_parts` | `merchant_hauler` | Vega | 400$ / 70xp |
| `bar_intercept_sirius_luxury` | Sirius Luxury | 3 | `luxury_goods` | `merchant_freighter` | Sirius | 800$ / 140xp |
| `bar_intercept_frontier_tech` | Frontier Tech | 4 | `electronics` | `merchant_caravan` | Luyten's Star | 1800$ / 300xp |

**Escort rule:** T1+ intercepts may include pirate fighter escorts via `bounty_wingmate_enemy_id`. Escorts spawn with the merchant, share its squad id, and trigger like bounty wingmen (auto-hail / combat start). Only the merchant leader completes the mission; escorts are bonus kills + bonus rep/loot.

**Deadline rule (playtest fix):** Intercepts are ROUND TRIPS — fly out, kill, fly back — so deadlines are scaled to real travel distance at starter-ship speed (10 moves/day), with ~2.1-2.2x headroom so BOTH on-time completion AND the early bonus (< half the deadline) are achievable at starter speed (faster ships get slack). Measured round trips: AC ~41d (deadline 90), Vega ~32d (70), Sirius ~69d (150), Luyten ~169d (360). The old 30/40/50/60 ladder was impossible (T1 needed 41d on a 30d clock; T4 is a 10-jump/100-fuel run on an 80-fuel tank).

### Smuggling

> **Goods are flavor only** — the mission's `is_smuggle` flag makes the cargo hot, not the good's category (design decision 1). Destination NPCs verified to exist on the target planet during implementation.

| ID | Title | Tier | Good (flavor) | Cargo | Destination | System | Rewards |
|----|-------|------|--------------|-------|-------------|--------|---------|
| `bar_smuggle_mars_weapons` | Mars Weapons Run | 1 | `weapons_blackmarket` | 8 | Mars Barkeep (`barkeep`) | Sol | 150$ / 25xp |
| `bar_smuggle_sirius_tech` | Sirius Black-Tech | 2 | `electronics` | 15 | Binary Observer (`research_officer`) | Sirius | 350$ / 60xp |
| `bar_smuggle_vega_drugs` | Vega Narcotics | 3 | `luxury_goods` | 30 | Cloud Host (`barkeep`) | Vega | 700$ / 120xp |
| `bar_smuggle_frontier_fuel` | Frontier Fuel Heist | 4 | `fuel_cells` | 55 | Bounty Master (`bounty_master`) | Luyten's Star | 1500$ / 250xp |

### Extortion

| ID | Title | Tier | Target | System | Rewards |
|----|-------|------|--------|--------|---------|
| `bar_extort_mars_debt` | Mars Debt | 1 | Civilian hauler | Sol | 200$ / 30xp |
| `bar_extort_sirius_protection` | Sirius Protection | 2 | Merchant runner | Sirius | 400$ / 65xp |
| `bar_extort_vega_interest` | Vega Interest | 3 | Trade convoy | Vega | 900$ / 150xp |
| `bar_extort_frontier_tribute` | Frontier Tribute | 4 | Outpost supply | Luyten's Star | 2000$ / 350xp |

### Salvage rights (boarding-integrated)

| ID | Title | Tier | Component | System | Patrol | Wreck / Layout | Rewards |
|----|-------|------|-----------|--------|--------|----------------|---------|
| `bar_salvage_tau_parts` | Tau Ceti Wreck | 1 | `machine_parts` | Tau Ceti | 1 pirate_scout | scout / ``scout_a`` | 180$ / 35xp |
| `bar_salvage_epsilon_drive` | Epsilon Drive | 2 | `electronics` | Epsilon Eridani | 2 pirate_scouts | scout / ``scout_a`` | 400$ / 70xp |
| `bar_salvage_procyon_core` | Procyon Core | 3 | `fuel_cells` | Procyon | raider + scout | freighter / ``freightliner_a`` | 850$ / 140xp |
| `bar_salvage_luyten_blackbox` | Luyten Black Box | 4 | `luxury_goods` | Luyten's Star | 2 raiders + captain | freighter / ``freightliner_a`` | 2000$ / 320xp |

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
- [x] Wire intercept delivery to barkeep — `active_is_deliverable_at` checks the per-mission `heist_good_secured` flag (set only by securing the mission-tagged `%` loot entity), never the trade inventory — buying the good cannot complete the mission (see "Mission-tagged cargo" above)

### Phase 1.5: Playtest — Intercept

**Status: COMPLETE — playtest passed.** Intercepts (T1-T4), mission-tagged cargo, the mixed-squad escort mechanic (stress-tested at 5 escorts, then reverted to unescorted), squad-wide aggro, round-trip deadlines, and the save/load heist-loot fix were all verified in play.

**Checklist:**
- [x] Visit Earth bar → missions visible
- [x] Accept intercept → merchant spawns in target system
- [x] Destroy merchant → mission-tagged `%` loot drops → SECURE → shows under MISSION CARGO (not TRADE GOODS), cannot be sold
- [x] Buying the target good at a terminal does NOT complete the mission
- [x] Escort squad: hailing ANY member (merchant or escort) pulls the whole squad; only the merchant completes the mission
- [x] Save in target system → Continue → killing the merchant still drops loot
- [x] Return to bar → deliver → reward granted, reserved cargo released

### Phase 2: Smuggling (design locked — see "Smuggling — Contraband transport" above)

- [x] Add `is_smuggle: bool = False` to `MissionSpec` + `ActiveMission` (snapshot; persisted in saveload); `mission_type="smuggling"` for rep deltas
- [x] Add `smuggler_cargo: int = 0` to `ModuleSpec` + `data/modules/smuggler.py` (mk1 10 / mk2 25 / mk3 50 / mk4 75, TL 1/2/3/4)
- [x] Extend `_run_cargo_scan`: compute hold capacity from modules; protect mission smuggling cargo first, then inventory contraband; confiscate the excess (mission overflow → auto-fail via `_fail_smuggle_mission`)
- [x] Add 4 hand-crafted smuggling missions to `bar.py` (cargo auto-loaded on accept via `required_cargo_size`; all `origin_planet_id="earth"`)
- [x] Quest log: show contraband type, route, scan-risk warning (Cargo: <good> — SCAN RISK: High/Med/Low via `_smuggle_scan_risk`)
- [x] Guide: `_GUIDE_BAR_MISSIONS` smuggling block + `_GUIDE_SHIPS` module table entry
- [x] Faction rep: `_MISSION_REP_DELTAS` entry for `"smuggling"` (pirate +2, merchant -5, civilian -5, militia -8 — pre-existing, verified)
- [x] Verify destination NPCs exist on each target planet; wire delivery targets (Mars Barkeep, Binary Observer, Cloud Host, Bounty Master)

**Playtest config (Phase 2):** Earth's `mission_tier` raised 1 → 4 so all hand-crafted bar missions (intercept + smuggling) are offered at the home bar for playtesting (the design tier table covers 1-4 from the Earth barkeep). All four Smuggler's Holds (mk1-mk4) are stocked at Earth's mechanic terminal for testing — mk4 is otherwise a deep-space TL4 item.

### Phase 2.5: Playtest — Smuggling

**Status: COMPLETE — playtest passed.** All four smuggling missions, the smuggler's-hold protection model (mission-cargo-first allocation), scan confiscation + auto-fail, quest-log scan risk, the militia-scan telegraphing UX, and save/load persistence were verified in play.

**Checklist:**
- [x] Earth mechanic stocks all 4 Smuggler's Holds; installing one shows in the loadout
- [x] Accept a smuggling mission → cargo auto-loads into MISSION CARGO (never trade goods, cannot be sold; buying the good at a terminal does not complete the mission)
- [x] Quest log shows `Cargo: <good> (N units)` + live `SCAN RISK: Low/Medium/High` from installed hold capacity
- [x] Land on a militia planet WITH a hold sized ≥ cargo → scan passes clean
- [x] Land WITHOUT a hold → cargo confiscated, mission FAILED, static mission returns to the bar board (re-acceptable)
- [x] Mission-first protection: inventory contraband confiscated while mission cargo stays safe when the hold covers mission cargo
- [x] **Frontier Fuel Heist** (55 cargo): at risk with mk3 (50), safe with mk4 (75) — overflow tension confirmed
- [x] Deliver to destination NPC → reward + XP + rep (`+2 pirate, -5 merchant, -5 civilian, -8 militia`)
- [x] Save mid-smuggle → Continue → mission active with correct scan-risk display
- [x] All 4 smuggling missions offered at Earth's bar (Earth `mission_tier=4` playtest config)

**Post-playtest polish (scan telegraphing UX):** Militia scans are no longer a silent 40% roll — the mechanic is now discoverable through gameplay, not just the guide (`navigation.py`, `menus/_planet.py`):

- **Approach:** the planet menu shows a red "MILITIA CHECKPOINT ACTIVE - INBOUND CARGO IS SUBJECT TO SCANS" warning when bumping a militia planet (new `has_militia_presence()` helper in `data/planets/__init__.py`, shared with the scan)
- **Landing:** carrying exposed contraband logs a red at-risk warning BEFORE the 40% roll (pure `_compute_scan_exposure()`)
- **Scan event:** a triggered scan announces itself in gold ("A militia patrol hails you for a routine cargo scan...") before the outcome — even clean scans are visible

**Code-quality audit (knowledge.md, post-playtest):** DRY + guardrail fixes from the self-audit pass:
- `release_mission_cargo()` extracted in `mission.py` — the reservation-release math existed in 3 copies (abort / complete / smuggle auto-fail)
- `_good_display_name()` extracted in `menus/_quest_log.py` — the intercept + smuggling good-name lookup blocks were duplicated
- `_smuggle_scan_risk` converted from a 3-branch chain to a table lookup (`_SCAN_RISK_STEPS`, divisor-based) — integer-division thresholds preserved exactly
- `_militia_scan_target()` extracted in `navigation.py` — brings `_run_cargo_scan` under the 40-line rule, pure guards separated from mutation

### Phase 3: Extortion — DEFERRED

**Status: DEFERRED.** Extortion depends on a full-featured comms system (demand tribute, threaten, flee responses, militia response) — the current comms is a bare hail/trade/attack dialog. Revisit after the comms expansion (``docs/design/in_progress/09_DESIGN_COMMS_RP_EXPANSION.md``). The tier table and 4 mission ideas above remain the target design for when comms is ready.

- [ ] (deferred) Add extortion comms dialog (demand payment, demand cargo, threaten, let go)
- [ ] (deferred) Add civilian NPC ship spec (non-hostile, carries credits + cargo)
- [ ] (deferred) Wire extortion outcome: pay (instant reward) or fight (combat + possible militia)
- [ ] (deferred) Add 4 hand-crafted extortion missions to `bar.py`
- [ ] (deferred) Quest log: show target name, system, "collect what they owe"

### Phase 4: Salvage rights — BOARDING-INTEGRATED (COMPLETE — playtest passed)

**Player flow:** accept at bar → travel to target system → find the wreck (marked) → clear the space patrol → board the wreck → fight the scavenger crew inside → secure the mission component from the interior → exit to space → return to bar → deliver.

Reuses the entire boarding + ground-combat framework (board dialog, ``load_layout`` interiors, fog of war, ``_rules_ground`` combat) and the intercept heist-cargo delivery path.

- [x] Add boardable wreck NpcShipSpec(s) — ``derelict_scout`` exists; add ``derelict_freighter`` for T3+ (larger hull, bigger ``loot_budget``)
- [x] Add ``freightliner_a.layout`` — larger wreck interior with crew + component-candidate rooms; ``scout_a`` reused for T1-2 (hand-edited by user for the "oh this is a ship" silhouette)
- [x] Layout: component-candidate room markers (2-3 per layout); on first board RNG-pick one and place the mission-tagged ``%`` (``heist_mission=True`` + ``heist_mission_id``) — placement persists via the interior cache
- [x] MissionSpec/ActiveMission fields: reuse ``heist_target_good_id``/``target_system_id``/``bounty_*``; add ``salvage_wreck_enemy_id`` + ``salvage_layout_id`` (no new patrol fields — patrol reuses ``target_enemy_id`` + ``bounty_target_squad_size`` + ``bounty_wingmate_enemy_id``)
- [x] Spawn wreck as non-combatant BountySpawn at a landmark + patrol squad nearby (both in ``ctx.bounty_spawns`` → save/load for free)
- [x] Boarding: bump wreck → Board dialog whenever the player is out of combat (no patrol-alive gate; you can't board mid-combat anyway)
- [x] **Persistent interiors:** ``GameContext.interiors: dict[str, world.GameMap]`` cache keyed by wreck spawn id; exit keeps the map in the cache; re-board reuses it (fog/loot/crew/power intact)
- [x] **Save/load:** extract shared ``_dungeon_to_dict`` / ``_dungeon_from_dict`` helpers (currently duplicated inline); save ``interiors`` dict + restore on load; drop a wreck's entry when it despawns
- [x] Wreck lifecycle: persists until component secured; despawns after secure + exit (design decision 4)
- [x] Ground victory: killing the scavenger crew applies pirate rep deltas (already wired in the ``__main__.py`` post-combat block)
- [x] Add 4 hand-crafted salvage missions to `bar.py` (component, system, patrol, wreck, layout per tier)
- [x] Quest log: show component, system, patrol threat level + "component somewhere in the wreck"
- [x] Save/load: new ActiveMission fields (``salvage_wreck_enemy_id``, ``salvage_layout_id``) on both sides
- [x] Guide: `_GUIDE_BAR_MISSIONS` salvage block (patrol threat, board flow, search + secure, component delivery)

**Implementation notes (post-review):**
- Patrol kill does NOT auto-complete the salvage mission — ``_encounter.py`` skips bounty-completion for missions with ``salvage_layout_id`` but still removes the dead patrol's BountySpawn (no respawn on reload).
- Boarding an abandoned wreck: the abandon path (Q) now also removes the wreck BountySpawn + its interior cache entry.
- Active-wreck save/load identity: ``load_game`` overwrites ``ctx.interiors[wsid]`` with the freshly-loaded active dungeon map so post-load progress (crew killed, loot taken) isn't lost to a stale deserialized twin.
- ``_dungeon_to_dict``/``_dungeon_from_dict`` now also preserve ground-combat ``squad_id`` + heist loot flags on the ACTIVE dungeon (strict improvement over the old inline blocks).

**PLAYTEST — Phase 4 (salvage): COMPLETE — all steps passed (6 bugs fixed in play).**

- [x] 1. Earth bar → accept a salvage mission (shuffle fix: salvage now appears in board slots)
- [x] 2. Travel to target system → sensor ping + wreck + patrol on the map
- [x] 3. Destroy the patrol → mission NOT auto-completed; no component drops in space
- [x] 4. Board the wreck → breach animation (first time only, re-board skips it); explore + fight scavenger crew; gold % hidden in one RNG room
- [x] 5. Secure the component → MISSION CARGO; quest log shows SECURED (friendly names, no raw IDs)
- [x] 6. Exit to space → wreck despawns; return to bar → deliver → reward + rep
- [x] 7. Anti-farm: re-board → dead crew stay dead, loot stays gone, fog stays revealed; no repeated breach animation; no `{`/`}` bracket glyphs rendered
- [x] 8. Save/load: save inside wreck → Continue → everything identical; exit + deliver works (world import fix for _dungeon_from_dict)
- [x] 9. Abandon (Q) → wreck + patrol gone; mission returns to bar board
- [x] Bonus: ground combat HP rebalanced (stamina 2× → 1×, less spongy)

**Playtest bug log (6 items fixed):**
1. Shuffle `available_ids` in `fill_empty_slots` — salvage missions at end of tuple never got board slots
2. Quest log shows friendly NpcShipSpec names instead of internal IDs (`pirate_raider` → `Pirate Raider`)
3. Layout bracket markers `{` `}` no longer render as visible glyphs (always show as `#`)
4. Skip breach animation on re-board (cached interior already breached)
5. `world` import at module level in `saveload.py` for `_dungeon_from_dict` (crash on Continue)
6. Ground combat stamina HP multiplier 2× → 1× (enemies were damage sponges)

### Phase 5: Procedural generation + polish (COMPLETE)

**Status: COMPLETE.** Procedural bar mission generation wired into `fill_empty_slots` via table-driven dispatch alongside merchants + bhguild. Missions generate when board slots are empty after static fill (month rollover or accepted/completed missions). Bar missions are faction-gated by pirate reputation — enemy attitude blocks procedural fill.

- [x] `generate_bar_mission` dispatcher — rolls tier + weighted type pick (intercept 35%, smuggling 35%, salvage 30%), delegates to sub-generators
- [x] `_generate_bar_intercept` — merchant targets, heist goods, pirate escorts at T2+, round-trip deadlines
- [x] `_generate_bar_smuggling` — one-way contraband delivery, destination NPC lookup, `is_smuggle=True`
- [x] `_generate_bar_salvage` — pirate patrol + derelict wreck, layout by tier (`scout_a` / `freightliner_a`), round-trip deadlines
- [x] `fill_empty_slots` refactored from boolean flags (`_is_merchant`, `_is_bh`) to table-driven dispatch (`_PROCEDURAL_GENERATORS` dict) — DRY improvement, adds bar guild
- [x] Help guide — already covered by `_GUIDE_BAR_MISSIONS` (Phase 4)
- [x] RNG audit — all sub-generators use shared `_roll_tier`, `_planet_to_system`, seeded RNG
- [x] DRY scan — three sub-generators follow the same pattern as existing generators; `_BAR_GENERATORS` dict avoids if/elif chains; `_BAR_TYPE_WEIGHTS` dict (not tuple) avoids fragile coupling

## Contracts compliance (MANDATORY — see knowledge.md)

- [x] **Save/load:** New ActiveMission field `heist_target_good_id` → added to both `_ctx_to_dict()` AND `load_game()` (`saveload.py:359`); heist loot `heist_mission` flag persisted + restored
- [x] **Save/load:** Smuggler's hold `hidden_cargo` → computed from modules (no new field needed; module bonuses survive save/load via `OwnedShip.modules`). `is_smuggle` + `smuggle_good_id` deserialized on `ActiveMission` in `saveload.load_game()`
- [x] **NPC spawns:** Merchant target ships → placed via `ctx.bounty_spawns` (BountySpawn with `heist_spawn_id`), saved/restored in saveload
- [x] **NPC cleanup:** Intercept target killed → `defeated_heist_ids` handled in `_encounter.py` post-victory; spawn removed via `_remove_bounty_spawn`
- [x] **Game guide:** Bar missions → `_GUIDE_BAR_MISSIONS` section (`help.py:896`)
- [x] **Game guide:** Smuggler's hold module → `_GUIDE_SHIPS` module table updated (mk1-mk4)

## Open questions

1. **How does the player know WHERE in the system the target is?** Sensor ping on system entry (intercept/salvage), comms ping (extortion), landmark marker (salvage wreck).
2. **Should stolen goods be contraband for militia scans?** Yes — extends risk/reward tension to intercept missions too. Smuggler's hold module mitigates this.
3. **What happens if the player's ship is destroyed?** Mission auto-fails on death.
4. **Extortion: what if the target has nothing to give?** Always yields at least some credits. Higher tier = better payout.
5. **Salvage: can the player board the wreck early and skip the patrol?** RESOLVED — the wreck is boardable whenever the player is out of combat (you can't board mid-combat anyway). The patrol still spawns around the wreck and engages on approach, so it's *usually* cleared first, but a player who evades or flees can board around it. No hard gate.

8. **Salvage: can the player farm crew XP / random loot by re-boarding?** RESOLVED — persistent interiors (design decision 6). The interior is cached and serialized with the save: crew stay dead, loot stays taken, fog stays revealed. Re-boarding a half-explored wreck is a half-explored wreck. No respawn, no farming, and the map survives exit → dump cargo → return, plus save/quit/continue. (This is a concrete instance of the entity/map persistence problem that ``docs/design/future/DESIGN_SAVE_LOAD_V2.md`` addresses architecturally — Phase 4 implements the contained version inside the current save system, and the v2 rewrite can subsume it later.)
6. **What if the player already has the target good in their inventory (intercept/salvage)?** RESOLVED — mission completion checks the per-mission `heist_good_secured` flag (set only by securing the mission-tagged loot entity), not an inventory count. Buying the good at a terminal or carrying it from another mission never completes the intercept.
