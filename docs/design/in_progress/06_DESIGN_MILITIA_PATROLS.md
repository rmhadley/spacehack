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

### Phase 1: Patrol movement + ship specs

- [ ] Add 3 new militia NpcShipSpec entries to `data/npc_ships/core.py` (light, standard, heavy)
- [ ] Add `patrol_density: int = 0` field to SolarSystem dataclass
- [ ] Set patrol_density on all 10 systems per the table above
- [ ] Add militia-specific movement logic to `npc_ships.spawn_npcs` — patrols spawn from system `patrol_density` (separate from `npc_spawn_chance`)
- [ ] Add militia patrol movement to `npc_ships.move_npcs` — patrols follow waypoint loops, don't despawn at gates
- [ ] Militia patrols should appear on a separate faction check: `_faction_of(_e) == 'militia'` gets patrol behavior
- [ ] Smoke test + commit

#### Playtest checklist

- [ ] Jump to Sol → verify 3-4 militia patrols visible on the map
- [ ] Jump to Wolf 359 → verify 0 militia patrols
- [ ] Watch militia movement → verify they patrol between bodies, don't despawn
- [ ] Get close to a militia patrol → verify they don't attack on sight (default: neutral)
- [ ] Check enemy (pirate) players don't get attacked on sight by militia (use combat to move toward them; they should detect but not engage)

### Phase 2: Auto-hail + cargo scan flow

- [ ] Add auto-hail chance calculation to `_detect_combat_encounter` or a new militia-specific detection function
- [ ] Auto-hail opens `open_comms_direct` with the militia ship
- [ ] Add scan outcome logic to `comms.py` — `_run_cargo_scan` function that checks contraband and applies consequences
- [ ] Wire scan outcomes to `modify_rep` (from faction rep system — stub with direct `ctx.faction_reputation` mutation if not implemented yet)
- [ ] Add contraband detection to scan: check cargo against `contraband_goods` set
- [ ] Implement fine/confiscation logic on contraband found
- [ ] Log messages for scan results (clean, contraband found, flee attempt)
- [ ] Smoke test + commit

#### DRY eval

- [ ] Is the auto-hail code shared with bounty auto-hail, or duplicated?
- [ ] Is the contraband check centralized (one function), or duplicated between scan and other systems?
- [ ] Are scan consequences using the same `modify_rep` path as other rep changes?

#### Playtest checklist

- [ ] Fly near a militia patrol → verify auto-hail triggers (~40% chance, may need multiple passes)
- [ ] Auto-hail opens the interaction modal with correct militia dialogue
- [ ] "Allow Scan" with no contraband → clean scan message, +militia rep
- [ ] "Allow Scan" with contraband → contraband confiscated, fine applied, -militia rep
- [ ] "Flee" → 60% chance escape (log message "You break line of sight..."), failed flee = combat
- [ ] "Attack" → combat with militia
- [ ] As Allied with militia → verify no auto-hail
- [ ] As Disliked/Enemy → verify much higher auto-hail rate

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

### Phase 5: Contraband data + system flags

- [ ] Add `contraband_factions: tuple[str, ...]` field to `TradeGood` dataclass in `data/trade_goods/core.py`
- [ ] Flag existing trade goods as contraband per the table above
- [ ] Add `contraband_goods: tuple[str, ...] = ()` field to SolarSystem or compute from per-good faction flags
- [ ] Wire contraband list into scan detection (Phase 2 already references this)
- [ ] Add `ctx.contraband_goods` — recompute on system entry
- [ ] Smoke test + commit

#### Playtest checklist

- [ ] Load weapons_blackmarket → scan in Sol → flagged as contraband
- [ ] Load food_rations → scan in any system → never contraband
- [ ] Load luxury_goods → scan in Sol → clean; scan in Luyten's Star → contraband

### Phase 6: Guide + final polish

- [ ] Update in-game guide with militia patrols, cargo scans, contraband, smuggler's hold
- [ ] Full DRY/RNG audit on all new code
- [ ] Final playtest pass

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
