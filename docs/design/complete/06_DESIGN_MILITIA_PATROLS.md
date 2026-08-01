# DESIGN: Militia Patrol System

## Overview

Add patrolling militia ships to systems that scan the player's cargo, creating risk/reward decisions around smuggling, contraband, and faction reputation. Militia patrols are **powerful, well-equipped ships** that players should think twice about fighting.

### What already exists

- `militia_blockade` NpcShipSpec — well-armed cruiser with heavy laser + light missile, shield modules, high AI stats
- `npc_ships.spawn_npcs` / `move_npcs` — procedural NPC spawning and movement, currently supports pirate patrol + merchant travel patterns
- `comms.open_comms_direct` — skip-the-list hail for auto-contact
- `comms._run_interaction_modal` — interaction options (Open Trade, Scan Cargo, Attack, End Transmission)
- `ctx.faction_reputation` — tracks militia rep, impacts attitude
- `faction.get_attitude()` — current 3-zone, to be upgraded to 5-zone (see `DESIGN_FACTION_REPUTATION.md`)
- `_detect_combat_encounter` — detects enemies in range after player movement
- Auto-hail for bounty targets at `comms_warning_range`

### What needs to be built

1. **Militia patrol movement** — ships that follow planned patrol routes (system-specific waypoints or gate-to-gate loops)
2. **Patrol ship variants** — light (scout), medium (cruiser), heavy (frigate/battleship) for different systems
3. **Auto-hail for cargo scans** — militia patrollers can auto-hail the player when within `comms_warning_range`
4. **Scan outcome system** — allow scan / flee / attack choices
5. **Contraband detection** — certain trade goods flagged as contraband in certain systems
6. **Reputation integration** — scan outcomes affect militia rep; rep affects scan frequency
7. **Contraband ship module** — smuggler's hold (hides X cargo from scans)

## Design decisions

### Patrol movement

Militia patrols use a **new movement pattern** distinct from pirates (random loop) and merchants (despawn at destination):

- **Patrol routes:** Each militia ship has a sequence of waypoints (planets/gates/stations in their assigned system). They patrol between them in order, ping-ponging back and forth.
- **No despawning on contact:** Militia ships stay in-system indefinitely. They do NOT despawn at gates like merchants — they reach the gate, pause, and patrol back.
- **Reaction to player:** At `comms_warning_range` (18+ cells), they have a chance to auto-hail. At `detect_radius` (7 cells), they close in if player evades.
- **Call for reinforcements:** If attacked, militia ships can spawn a backup patrol (see Phase 3).

### Patrol ship variants

| Spec ID | Name | Ship hull | Weapons | Armor | System tier | Role |
|---------|------|-----------|---------|-------|-------------|------|
| `militia_patrol_light` | Militia Scout | Scout | Light laser | Light | T1-T2 | Border patrol, early warning |
| `militia_patrol` | Militia Patrol | Cruiser | Heavy laser, light missile | Medium (shield + armor) | T2-T3 | Standard patrol (replaces militia_blockade) |
| `militia_patrol_heavy` | Militia Enforcer | Frigate | Heavy laser, heavy missile, plasma cannon | Heavy (full shields + armor + computer) | T4 | Blockade / core system defense |

**Combat stats:**
- All variants have high `ai_aggressiveness` (70-85), low `ai_flee_threshold` (0.05-0.10)
- Higher `pilot_gunnery` / `pilot_piloting` than pirates of equivalent tier
- `detect_radius` = short (5-7) so they don't auto-aggro from across the map; `comms_warning_range` = longer (15-20) for the hail window
- Heavy variant has `ai_accuracy_bonus=30`, `ai_dodge_bonus=15` — a legitimate threat

### Auto-hail for cargo scans

When the player moves within `comms_warning_range` of a militia patrol, there is a **chance** (not guaranteed) that the patrol auto-hails:

| Factor | Effect on chance |
|--------|-----------------|
| Base chance | 40% per proximity event |
| Player is Liked/Allied with militia | 0% (they wave you through) |
| Player is Disliked/Enemy with militia | 80% (suspicious) |
| Player has contraband in cargo | +30% bonus |
| Player has smuggler's hold | -X% based on module tier |

The auto-hail opens `open_comms_direct` with the patrol ship, showing the militia's hailing message:

```
Militia Patrol: "Attention pilot. This is a routine cargo inspection.
Halt your vessel for inspection."
```

**Player options:**

| Option | Effect |
|--------|--------|
| **Allow Scan** | Patrol scans your cargo. If contraband found → lose contraband + militia rep penalty + fine. If clean → +militia rep, +civilian rep. |
| **Flee** | Break line of sight. 60% chance to escape (modified by ship speed vs patrol speed). If failed → forced combat with militia. |
| **Attack** | Initiate combat with the patrol. Guarantees -militia rep, -civilian rep. Patrol may call reinforcements. |

### Contraband

Certain trade goods are flagged as contraband in specific systems / factions:

| Good | Contraband in | Notes |
|------|--------------|-------|
| `weapons_blackmarket` | All systems | Always illegal |
| `luxury_goods` | Militia-controlled systems (Luyten, Blockade) | Deemed "non-essential" |
| `electronics` | Only in high-security systems | Rare — only at Tier 4 stations |

**Implementation:**
- `ctx.contraband_goods: set[str]` — computed per-system based on system flags
- Solar system gets a `contraband_list: tuple[str, ...] = ()` field (empty = no contraband)
- OR a simpler approach: `data/trade_goods/core.py` flags each good with `contraband_factions: tuple[str, ...]` — if the militia faction is in that list for the current system, the good is contraband

**Scan result when contraband found:**
```
Militia Patrol: "Contraband detected! Weapons-grade materials in your cargo hold.
You are in violation of system security protocols."
```
- All contraband goods confiscated (removed from cargo)
- Fine: contraband_value × 2 (up to a system-defined max)
- If player can't pay → ship impounded (game over / debt mission)
- Militia rep: -5 per scan event
- Player choice: "Accept fine" (lose credits + goods) or "Attack" (forced combat)

**Scan result when clean:**
```
Militia Patrol: "Clean scan. Apologies for the inconvenience, pilot.
Safe travels."
```
- Militia rep: +1
- Civilian rep: +1

### Reputation integration

| Player militia rep | Scan frequency | Hail tone | Fight consequences |
|-------------------|---------------|-----------|-------------------|
| Enemy (-100 to -76) | 80% chance | "Halt or be fired upon!" | Reinforcements called immediately |
| Disliked (-75 to -26) | 60% chance | "You. Stop for inspection." | Standard combat |
| Neutral (-25 to +25) | 40% chance | "Routine inspection. Hold." | Standard combat |
| Liked (+26 to +75) | 10% chance | "Sir/Ma'am, quick scan and you're on your way." | -militia rep if attacked (betrayal) |
| Allied (+76 to +100) | 0% chance | "Patrol leader {name} salutes you as you pass." | -massive militia rep if attacked (treason) |

### Smuggler's hold module

A new ship module type that reduces scan detection:

| Module ID | Name | Tier | Cargo hidden | Cost | Effect |
|-----------|------|------|-------------|------|--------|
| `smuggler_hold_mk1` | Smuggler's Hold Mk1 | 2 | 10 units | 500 | Hides 10 cargo from scans |
| `smuggler_hold_mk2` | Smuggler's Hold Mk2 | 3 | 25 units | 2000 | Hides 25 cargo from scans |
| `smuggler_hold_mk3` | Smuggler's Hold Mk3 | 4 | 50 units | 8000 | Hides 50 cargo from scans |

**How it works:**
- When a scan happens, the engine checks `total_contraband_cargo <= hidden_capacity`
- If the player's contraband fits in the smugger's hold → scan finds nothing
- If contraband exceeds hidden capacity → remaining contraband is detected
- The module also reduces auto-hail chance by 10% per tier (the hold is shielded)

## System-level patrol density

Each solar system gets a `patrol_density: int` field (default 0 = no patrols):

| System | Patrol density | Notes |
|--------|---------------|-------|
| Sol (Earth/Mars) | 3-4 | Core territory — heavy patrols |
| Alpha Centauri | 2-3 | Major colony — standard patrols |
| Sirius | 1-2 | Mining colony — light patrols |
| Tau Ceti | 1-2 | Agricultural world — light patrols |
| Wolf 359 | 0 | Frontier — no patrols |
| Luyten's Star (Blockade) | 4-5 | Blockade — maximum security |
| Barnard's Star | 0 | Uncharted — no patrols |
| Procyon | 0-1 | Remote — very light |
| Epsilon Eridani | 1 | Depot — occasional patrols |
| Vega | 0 | Uncharted — no patrols |

Patrol density determines how many militia ships are spawned per system and affects the per-tick respawn rate.

## Data model

### New fields on `SolarSystem`
- `patrol_density: int = 0` — how many militia patrols spawn (separate from `npc_spawn_chance`)

### New NpcShipSpec entries
See Phase 1 table above (3 new specs: light, standard, heavy).

### New fields on `GameContext`
- `smuggler_hold_capacity: int = 0` — total hidden cargo capacity from smuggler's hold modules (computed from equipped modules)
- `contraband_goods: set[str]` — set of good IDs that are contraband in the current system (recomputed on system entry)

### New trade good flags
Add `contraband_factions: tuple[str, ...] = ()` to `TradeGood` dataclass in `data/trade_goods/core.py`.

### New module data
Add `smuggler_hold_mk1/2/3` to `data/modules/systems.py` with a new `module_type: str = "smuggler_hold"` and `hidden_cargo: int` field.

### Change to existing `NpcShipSpec`
No changes needed — `comms_warning_range`, `detect_radius`, and `comms_lines` already exist and are used by the militia spec.

## Implementation phases

### Phase 1: Patrol movement + ship specs (COMPLETE — playtest passed)

**Implementation:** 3 new ship specs, `patrol_density` tuple field on `SolarSystem`, militia spawn pass in `spawn_npcs()` (separate from NPC table, before early-return so it works in systems with no NPCs). Movement reuses existing pirate-style patrol loops — `faction="militia"` falls through to the non-merchant path in `move_npcs`. Ship type auto-derived from max density: 5+ → heavy, 3+ → patrol, 1-2 → light. `militia_blockade` preserved unchanged for Luyten's storyline.

- [x] Add 3 new militia NpcShipSpec entries (`militia_patrol_light`, `militia_patrol`, `militia_patrol_heavy`)
- [x] Add `patrol_density: tuple[int, int] = (0, 0)` field to SolarSystem dataclass
- [x] Set patrol_density on all 10 systems: Sol (3,4), AC (2,3), Sirius (1,2), Tau Ceti (1,2), Luyten (4,5), Procyon (0,1), Epsilon Eridani (1,1), Wolf 359/Vega/Barnard's Star (0,0)
- [x] Militia spawn pass in `spawn_npcs()` — separate from NPC table, uses patrol_density, respects `player_spawn_exclusion`
- [x] Militia movement reuses pirate-style patrol loops (no new AI needed)
- [x] Smoke test + commit

#### Playtest checklist (all passed)

- [x] Jump to Sol → 3-4 militia patrol cruisers visible (teal `B` glyphs)
- [x] Jump to Wolf 359 → 0 militia patrols
- [x] Watch militia movement → patrol between bodies, don't despawn
- [x] Get close to militia → don't attack on sight at neutral rep
- [x] Luyten's Star → 4-5 Militia Enforcers + static blockade picket line intact
- [x] Mid-range systems (Sirius/Tau Ceti) → 1-2 Militia Scouts
- [x] Arrival zone exclusion → no militia spawn on top of player
- [x] Save/load → patrols persist across Continue

### Phase 2: Auto-hail + cargo scan flow (COMPLETE — playtest passed)

**Implementation:** Renamed `militia_warned_systems` → `militia_scanned` with per-entity tracking (squad-ID based for moving entities, position-based for static). Added `_militia_scan_chance()` (rep-gated table: allied 0%, liked 20%, neutral 40%, disliked/enemy 80%), `_calc_flee_chance()` (speed+piloting formula, clamped 15-90%), and `_run_space_cargo_scan()` (planet-independent scan reusing exposure/confiscation logic). Militia patrols get 3-option modal (Allow Scan / Flee / Attack) in `comms.py`. `militia_blockade` retains its original warning-only behavior (End Transmission only).

**Bugs fixed during playtest:**
- IndentationError after rename (comment+code merged onto one line)
- `militia_scanned.discard(system_id)` wrong — set stores per-entity keys, not system IDs; changed to `.clear()`
- Derelict auto-hail firing every tick (per-entity check only in militia path, missing from viewport/bounty/spec-distance paths)
- Militia patrol re-rolling every tick (position-based key changed as patrols moved; switched to `procedural_squad_id`)
- Militia blockade showing wrong options (faction=='militia' caught both blockade and patrols; added `_is_blockade` check by ID)
- `_wreck_spawn_id` UnboundLocalError for non-combat missions (declared inside target_enemy_id block, referenced outside)
- Militia spawning inside celestial bodies (no collision check against planets/gates/stations; DRY'd `_blocked` set to share with NPC spawn)

- [x] Auto-hail chance calculation via `_militia_scan_chance()` — reputation-gated
- [x] Per-entity tracking via `militia_scanned` (squad-ID key for moving entities)
- [x] Militia-specific interaction modal (Allow Scan / Flee / Attack, no End Transmission)
- [x] `_run_space_cargo_scan()` reusing planet-landing scan logic (exposure, confiscation, fines)
- [x] Flee chance formula: 40% + speed bonus + piloting bonus, clamped [15%, 90%]
- [x] Blockade retains original warning-only behavior (End Transmission only)
- [x] Non-militia auto-hails (derelicts, bounty targets) unchanged — once per entity
- [x] Smoke test + commit

#### Playtest checklist (all passed)

- [x] Blockade still hails 100% immediately
- [x] Militia patrol auto-hail at neutral (40% chance, may need multiple passes)
- [x] Allow Scan — clean: +1 militia rep
- [x] Allow Scan — contraband: confiscation, fine, -5 militia rep
- [x] Flee — success: log "You break line of sight"
- [x] Flee — fail: forced combat with full squad
- [x] Attack: standard combat with full squad
- [x] Per-entity tracking: one patrol scanned, another gets its own roll
- [x] Allied rep → 0% (wave through)
- [x] Disliked/Enemy → 80% (frequent hails)
- [x] Save/load preserves scanned entity tracking
- [x] Jump resets tracking (militia_scanned cleared)
- [x] Smuggler's hold protects contraband from scan
- [x] No crash on edge cases

### Phase 3: Combat + reinforcements — DROPPED

**Status: DROPPED.** The call-for-backup / reinforcement system was deemed unnecessary for v1. Killing a militia ship is already punitive enough through faction rep loss (see `_COMBAT_KILL_DELTAS` in `faction.py`).

- [x] (dropped) Reinforcement spawning on militia attack
- [x] (dropped) Call-for-help messages
- [x] (dropped) Betrayal penalties for attacking as Allied

### Phase 4: Smuggler's hold module

- [ ] Add `smuggler_hold_mk1/2/3` to `data/modules/systems.py` with `module_type="smuggler_hold"` and `hidden_cargo` field
- [ ] Add smuggler's hold to `ship.py` — computed `effective_hidden_cargo(owned_ship) -> int` that sums hidden_cargo from all equipped smuggler holds
- [ ] Wire hidden cargo into scan detection: if total contraband <= hidden cargo → clean scan
- [ ] Wire hidden cargo into auto-hail chance reduction (-10% per tier)
- [ ] Add smuggler hold to the shop/loadout systems (Can they be bought? Are they in the ship equipment menu?)
- [ ] Smoke test + commit

#### Playtest checklist

- [ ] Buy a smuggler's hold Mk1 → verify it shows in ship stats
- [ ] Load 10 units of contraband with Mk1 equipped → scan finds nothing
- [ ] Load 15 units of contraband with Mk1 equipped → scan finds 5 units
- [ ] Auto-hail chance reduced with smuggler's hold equipped

### Phase 5: Contraband data + system flags — CANCELED

**Status: CANCELED.** Per-system contraband (luxury_goods illegal in Luyten, etc.) was rejected as a feature. The single `category="contraband"` flag on `weapons_blackmarket` is sufficient — all militia scans treat it as contraband everywhere. No new data fields or scan logic changes needed.

- [x] (canceled)

### Phase 6: Guide + code review + contracts audit (COMPLETE)

- [x] Added `_GUIDE_MILITIA_PATROLS` section to help.py covering patrols, auto-hail chance table, Allow Scan/Flee/Attack, flee formula, planet landing scans, blockade, contraband
- [x] Appended to `GUIDE_SECTIONS` tuple (between Navigation and Derelicts)
- [x] Contracts audit:
  - Save/load: `militia_scanned` serialized in `_ctx_to_dict()` + `load_game()` ✅
  - Game guide: new section added ✅
  - Module-level state: no new globals introduced ✅
  - Code quality: per-entity tracking DRY'd via `_entity_hail_key()`; `_militia_scan_chance()` and `_calc_flee_chance()` are pure; `_run_interaction_modal` uses table-driven dispatch ✅
  - Performance: `_check_auto_comms_warning` runs only on player move ticks (same pattern as `_detect_combat_encounter`) ✅

## Contracts compliance (MANDATORY — see knowledge.md)

- [ ] **Save/load:** New GameContext fields (`smuggler_hold_capacity`, `contraband_goods`) → both `_ctx_to_dict()` AND `load_game()`
- [ ] **Save/load:** New SolarSystem field (`patrol_density`) — validated at load, no serialization needed (recomputed from system spec)
- [ ] **NPC spawns:** Militia patrol entities → registered in `ctx.procedural_spawns` with matching `squad_id`
- [ ] **NPC cleanup:** Patrol killed in combat → spawn removed via per-kill handler in `_weapons.py`
- [ ] **Game guide:** Militia patrols, cargo scans, contraband → update `_GUIDE_NPCS` or new `_GUIDE_MILITIA` section
- [ ] **Module-level state:** No new module-level globals expected (patrol density per-system, not global)

## Open questions

1. **Should fleeing from a scan always engage combat on failure, or should there be degrees of failure (e.g. lose some cargo vs full combat)?** For v1, let's keep it simple: flee = 60% escape, 40% forced combat. No partial outcomes.
2. **Should militia auto-hail also happen during auto-nav (G-key mode)?** Yes — auto-nav should respect the same detection/hail rules. If the player is auto-navigating and passes near a militia patrol, the patrol hails and auto-nav pauses (like combat detection).
3. **Can the player bribe militia to avoid a scan?** Not in v1. Would require a bribe mechanic + faction rep check. Defer.
4. **Dead militia pilots — should they drop loot?** Standard loot rules apply (same as any combat kill). But consequence is severe rep loss.
5. **Should there be a "disguised smuggler" NpcShipSpec that looks like a merchant but is actually a militia decoy?** Fun idea but out of scope for v1.
6. **Reinforcements dropped** — Phase 3 (call-for-backup) was removed from scope. Killing a militia ship is already punitive via faction rep.
