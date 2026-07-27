# NPC Ships & Communications — Design Doc

## Overview

Add all NPC ships (pirates, merchants, civilians) to a **single unified catalog `data/npc_ships/`** and a **range-limited comms system** for interacting with non-hostile ships.

Migrates pirates out of `data/enemies/` into the shared catalog so that faction reputation (future) can make pirates neutral or merchants hostile without fighting the data model.

Rather than bump-to-interact (impractical with moving ships), the player presses `T` to open a comms panel, scans for ships within range, and hails them — opening trade, dialogue, or combat.

---

## Philosophy alignment

| Principle | How this design follows it |
|-----------|---------------------------|
| **Data-first** | `NpcShipSpec` is a frozen dataclass in `data/npc_ships/`. `data/enemies/` is deleted — pirates move into the shared catalog. One catalog, not two. |
| **Cross-cutting state through `ctx`** | `faction_reputation` lives on `GameContext`. Comms state (contacts list, active hail) is ephemeral (local to the comms modal). |
| **Domains own their flow** | `comms.py` owns the comms domain. `npc_ships.py` owns spawn + movement (replacing the pirate-specific helpers in `__main__.py`). `combat.py` stays combat-only — it reads `NpcShipSpec` instead of `EnemySpec`. |
| **Atomic commits** | Each phase lands as one commit. Phase 1 migrates pirates, so intermediate commits don't have a zombie `data/enemies/` and a half-built `data/npc_ships/`. |

---

## 1. Data — Unified NpcShipSpec catalog

`data/enemies/` is **replaced** by `data/npc_ships/`. `EnemySpec`, `AIProfile`, and `PilotSkills` are absorbed into `NpcShipSpec`.

### NpcShipSpec

```python
@dataclass(frozen=True)
class NpcShipSpec:
    id: str
    name: str
    char: str
    fg: tuple[int, int, int]
    ship_id: str                         # references Ship.id (hull, cargo capacity)
    faction: str                         # "pirate" | "merchant" | "militia" | "civilian"

    # Equipment
    weapons: tuple[str, ...] = ()
    modules: tuple[str, ...] = ()

    # Cargo (merchants, loot-on-destroy for pirates)
    cargo_goods: tuple[str, ...] = ()    # which goods this ship can carry
    cargo_count: int = 0                 # how many unique goods to spawn with (0 = none)

    # Combat
    ai_aggressiveness: int = 50          # 0-100: chance to attack vs reposition
    ai_preferred_range: int = 3
    ai_flee_threshold: float = 0.15      # hull % below which AI flees
    ai_accuracy_bonus: int = 0
    ai_dodge_bonus: int = 0
    pilot_gunnery: int = 20
    pilot_piloting: int = 20
    pilot_engineering: int = 10
    min_power_gen: int = 3
    detect_radius: int = 0               # 0 = won't auto-detect (non-hostile)

    # Comms / interaction
    comms_range: int = 15                # cells within which player can hail
    comms_lines: tuple[str, ...] = (
        "Greetings, pilot.",
    )
    base_speed: int = 1                  # cells per movement tick
```

**Why absorb `AIProfile` + `PilotSkills` into NpcShipSpec rather than keep them as nested objects:**
- Flat fields avoid nested import chains when `combat.py` reads them
- Pirates and merchants both might need them (a hostile merchant fights back)
- Single source of truth: `init_combat_state` reads `spec.pilot_gunnery` either way

### Faction field semantics

| `faction` | Default attitude | Can flip? |
|-----------|-----------------|-----------|
| `"pirate"` | hostile (detect_radius > 0, auto-engages) | Yes — via reputation |
| `"merchant"` | neutral (detect_radius = 0, comms-only) | Yes — attack them, they become hostile |
| `"militia"` | friendly (detect_radius > 0 for contraband, helps vs pirates) | Future |
| `"civilian"` | neutral (detect_radius = 0, no cargo, flavor only) | Unlikely but possible |

### Initial catalog (v1)

After migration from `data/enemies/`:

| id | name | faction | ship_id | weapons | cargo_goods | notes |
|----|------|---------|---------|---------|-------------|-------|
| `pirate_scout` | Pirate Scout | pirate | scout | light_laser | food_rations, fuel_cells | migrated from enemies, drops basic loot |
| `pirate_raider` | Pirate Raider | pirate | cruiser | light_laser, light_missile | electronics, luxury_goods, weapons_blackmarket | migrated from enemies, drops better loot |
| `merchant_hauler` | Merchant Hauler | merchant | hauler | none | electronics, machine_parts, food_rations, textiles | bulk trader, roams between gates |
| `merchant_scout` (future) | Merchant Courier | merchant | scout | none | luxury, tech | fast courier, Phase 2 |
| `civilian_transport` (future) | Civilian | civilian | hauler | none | none | Phase 2 |
| `militia_patrol` (future) | Militia Patrol | militia | cruiser | light_laser | none | Phase 4 |

### Faction reputation (future — designed for, not implemented)

```python
# On GameContext (added in Phase 1, empty until needed)
faction_reputation: dict[str, int] = field(default_factory=dict)
```

Attitude will be computed from reputation at runtime in a future design pass:

| Reputation | Attitude |
|-----------|----------|
| -100 to -51 | hostile |
| -50 to 50 | neutral |
| 51 to 100 | friendly |

When `detect_radius > 0` AND attitude is hostile → auto-engages combat.

**Design-for-future note**: All NPC ships carry a `faction` string field. The combat system reads `detect_radius` per-ship (not hardcoded to "always hostile"). A future faction pass can set `ctx.faction_reputation` and the existing per-ship attitude check will work without combat.py changes.

---

## 2. Data — SolarSystem gains unified NPC fields

`SolarSystem` gets **two new fields** that replace the pirate-specific chase/density:

```python
@dataclass(frozen=True)
class SolarSystem:
    ...
    # Was: pirate_chance, pirate_density
    npc_spawn_chance: float = 0.0       # per-visit probability of any NPC spawn
    npc_spawn_table: tuple[tuple[str, float], ...] = ()  # (spec_id, weight) pairs

    # Per-system tuning (old pirate_chance/density removed)
```

Example from `sol.py`:

```python
SYSTEM = SolarSystem(
    ...
    npc_spawn_chance=0.8,               # 80% chance of NPCs spawning on visit
    npc_spawn_table=(
        ("pirate_scout", 0.5),          # 50% of spawns are pirate scouts
        ("pirate_raider", 0.2),         # 20% raiders
        ("merchant_hauler", 0.2),       # 20% merchants
        ("civilian_transport", 0.1),    # 10% civilians
    ),
    npc_density=3,                      # total NPC ships to spawn when chance hits
)
```

This unifies all NPC spawning under one mechanism. Deep systems set higher `npc_density` and heavier pirate weights; core systems set higher merchant weights.

---

## 3. Runtime — Comms + faction state

On `GameContext`:

```python
faction_reputation: dict[str, int] = field(default_factory=lambda: {
    "pirate": -100,
    "merchant": 0,
    "militia": 50,
    "civilian": 0,
})
```

Comms state is **ephemeral** — not stored on ctx. Each `open_comms()` call scans contacts fresh.

---

## 4. Domain — `comms.py`

New module: `src/spacehack/comms.py`

### Entry point: `open_comms(ctx)`

**Range scan**: Iterate `ctx.game_map.entities`, check distance to player. Any entity with an `npc_ship_id` tag within `spec.comms_range` is a contact.

If no contacts → log "No ships in comms range." and return.

#### Comms panel (modal)

```
 ┌─────────────────────────────────────┐
 │  COMMS — 3 contacts in range       │
 │                                     │
 │  > Merchant Hauler                  │
 │      "Greetings, pilot..."          │
 │    Pirate Scout   (hostile)         │
 │      "Back off or be boarded!"      │
 │    Civilian Transport               │
 │      "Just heading home..."         │
 │                                     │
 │  UP/DOWN select  ENTER hail         │
 │  ESC close                          │
 └─────────────────────────────────────┘
```

Hostile ships show `(hostile)` tag and use aggressive comms lines.

#### Interaction sub-modal

```
 ┌─────────────────────────────────────┐
 │  Merchant Hauler — Hailing          │
 │                                     │
 │  "Greetings, pilot. Just passing    │
 │   through from Vega to Sol."        │
 │                                     │
 │  > Open Trade                       │
 │    Scan Cargo                       │
 │    End Transmission                 │
 └─────────────────────────────────────┘
```

For hostile ships, "Attack" replaces "Open Trade":

```
 ┌─────────────────────────────────────┐
 │  Pirate Scout — Hailing             │
 │                                     │
 │  "This is pirate space! Hand over   │
 │   your cargo or we'll take it!"     │
 │                                     │
 │  > Attack (initiate combat)         │
 │    End Transmission                 │
 └─────────────────────────────────────┘
```

| Option | Available for | Action |
|--------|--------------|--------|
| **Open Trade** | merchants, civilians | Opens trade modal using NPC's inventory |
| **Scan Cargo** | all | Reveals cargo manifest (auto-succeeds for neutral/friendly) |
| **Attack** | hostile ships / always | Exits comms, triggers combat encounter |
| **End Transmission** | all | Closes comms, returns to space |

---

## 5. Domain — NPC Ship lifecycle (`npc_ships.py`)

New module: `src/spacehack/npc_ships.py`

Replaces `_spawn_procedural_pirates` and `_move_pirates` in `__main__.py`.

### Spawn (`spawn_npcs`)

Called from `_jump_to_system` and `_launch_to_space`:

```python
def spawn_npcs(ctx, game_map: world.GameMap, system_id: str) -> None:
```

1. Resolve `SolarSystem` from `system_id`
2. Roll `RNG.random() < system.npc_spawn_chance`
3. If hit, roll `npc_density` times, weighted by `npc_spawn_table`
4. For each roll: pick spec, pick spawn position (near gates for traders, scattered for pirates), create entity with `npc_ship_id` and `procedural_movement_id` tags

### Movement (`move_npcs`)

Called from the space-mode dispatcher after player moves:

```python
def move_npcs(ctx, game_map: world.GameMap) -> None:
```

Replaces `_move_pirates`. Behaviour varies by faction:

| Faction | Movement target | On reaching target |
|---------|---------------|-------------------|
| pirate | planets/gates/stations (same as today) | patrol — pick new target |
| merchant | planets with trade terminals or jump gates | jump gate = despawn ("jumps to next system"), planet = despawn ("docks at port") |
| civilian | planets | despawn ("docks") |

Merchants **flee** from nearby pirates (move away if a pirate is within `detect_radius`).

### Despawn conditions

1. Jumped out (merchant at gate)
2. Docked at planet (merchant/civilian at planet)
3. Destroyed in combat (drops cargo as loot)
4. Player jumps/launches (system resets, fresh spawn on next visit)

---

## 6. Comms key + space-mode dispatcher

- New key: `T` (transmit/comms) — mirrors `C` for cargo
- New helper: `_is_t_press(event)`
- Guarded by `current_mode == 'space'`
- Dispatches to `comms.open_comms(ctx)`

---

## 7. HUD

- `T - Comms` added to space-mode help lines
- Future: contact count indicator `[3]` when ships are in range

---

## 8. Migration plan: `data/enemies/` → `data/npc_ships/`

Current files to be **deleted**:
- `src/spacehack/data/enemies/__init__.py` (EnemySpec, AIProfile, find_enemy)
- `src/spacehack/data/enemies/pirates.py` (ENEMIES tuple)

Current files to be **updated** to read from `data/npc_ships/`:
- `src/spacehack/combat.py` — `init_combat_state` reads `pilot_skills`, `ai.*` from `NpcShipSpec`
- `src/spacehack/__main__.py` — `_detect_combat_encounter`, `_spawn_procedural_pirates`, `_move_pirates`
- `src/spacehack/game_context.py` — remove `ProceduralSpawn`? Or keep and rename

Imports change:
```python
# Before
from .data.enemies import find_enemy
# After
from .data.npc_ships import find_npc_ship
```

### Step-by-step data migration

```python
# Before: enemy/pirates.py
EnemySpec(
    id="pirate_scout",
    name="Pirate Scout",
    ...
    ai=AIProfile(aggressiveness=60, ...),
    pilot_skills=PilotSkills(gunnery=15, ...),
)

# After: data/npc_ships/core.py (flat fields)
NpcShipSpec(
    id="pirate_scout",
    name="Pirate Scout",
    faction="pirate",
    ...
    ai_aggressiveness=60,
    ...
    pilot_gunnery=15,
    ...
)
```

---

## 9. Implementation phases

### Phase 1 — Unified catalog + pirate migration + merchant haulers

**Goal**: `data/npc_ships/` exists, pirates live there, `merchant_hauler` spawns on map. All old code migrated to use the new catalog.

**Key change**: Loot drops come from `NpcShipSpec.cargo_goods` instead of iterating all `TRADE_GOODS` in combat.py. Each NPC spec defines what it may carry — pirates drop their `cargo_goods` on destruction, merchants carry theirs for trade. This replaces the hardcoded TRADE_GOODS iteration in combat.py with a per-spec loot table.

- [x] Create `data/npc_ships/` package (`__init__.py` + `core.py`) with `NpcShipSpec` absorbing `EnemySpec` + `AIProfile` + `PilotSkills`
- [x] Migrate `pirate_scout`, `pirate_raider` from `data/enemies/pirates.py` into `data/npc_ships/core.py` — set `cargo_goods` on each (see catalog table)
- [x] Delete `data/enemies/` directory
- [x] Update `combat.py`: `find_enemy()` → `find_npc_ship()`, flatten AIProfile/PilotSkills. **Replace `TRADE_GOODS`-iteration loot with `spec.cargo_goods`-based loot**
- [x] Update `__main__.py`: `_detect_combat_encounter` reads from `npc_ships`
- [x] Update `SolarSystem`: replace `pirate_chance`/`pirate_density` with `npc_spawn_chance`/`npc_density`/`npc_spawn_table`
- [x] Update all system data files (sol.py, sirius.py, etc.) — per-system weights: Sol = more merchants, fewer pirates; deep systems = more pirates
- [x] Update `game_context.py`: add `npc_targets`/`npc_paths`, update `ProceduralSpawn`
- [x] Update `world.Entity`: add `npc_ship_id` field
- [x] Add `merchant_hauler` to catalog (1 new merchant spec for Phase 1)
- [x] Implement `spawn_npcs()` in `npc_ships.py` (unified spawn — replaces pirate-only)
- [x] Wire `spawn_npcs()` in `_jump_to_system` and `_launch_to_space`
- [x] Merge pirate movement into `move_npcs()` in `npc_ships.py`, call from dispatcher
- [x] Run smoke + audit

**PLAYTEST — Phase 1**

> **Living document**: Update this section during implementation if new edge cases, behaviors, or failure modes emerge that aren't covered below. The playtest should reflect what actually needs testing, not just what we anticipated.

Run through each of these in order. Note any crashes, unexpected log messages, missing entities, or incorrect loot.

1. **Smoke test** — Run `python3 tools/smoke.py` + `python3 tools/audit_loose_refs.py`. Must pass before starting the game.
2. **Game starts** — Launch the game, create a character, land on Earth. No import errors or startup crashes.
3. **Launch to Sol space** — Launch from Earth. Verify you see pirate entities on the map (same `p`/`P` glyphs as before). Verify `merchant_hauler` entities appear with a distinct glyph/color (e.g. `M` in green). Verify both types move on `.` (wait).
4. **Jump to another system** — Jump to Alpha Centauri. Verify NPCs spawn there too, with the correct per-system weights (fewer pirates, more merchants in Sol; more pirates in deep systems). No crash on jump.
5. **Engage pirates in combat** — Fly near a pirate scout, trigger combat. Verify combat init works (no crash). Kill the scout. Verify it drops loot from its `cargo_goods` only (`food_rations`, `fuel_cells`) — NOT goods it shouldn't carry (e.g. `luxury_goods`).
6. **Engage pirate raider** — Find and fight a raider. Verify it drops its `cargo_goods` (`electronics`, `luxury_goods`, `weapons_blackmarket`).
7. **Engage merchant (attack)** — Fly near a merchant hauler, bump into it. Verify combat triggers. Kill it. Verify it drops its `cargo_goods` (`electronics`, `machine_parts`, `food_rations`, `textiles`).
8. **Weight verification** — Jump between Sol (high merchant weight) and a deep system like Wolf 359 (high pirate weight). Do 3 visits each. Verify Sol tends to have more merchants than pirates, and deep systems tend to have more pirates than merchants. Count roughly — this is stochastic, so look for trend not exact numbers.
9. **Check HUD** — Verify space-mode HUD renders NPC ship glyphs on the map. No rendering glitches.
10. **Edge case: zero-density system** — Visit a system with `npc_spawn_chance=0` (if any). Verify no NPCs appear. No crash.

**PLAYTEST — Phase 2**

> **Living document**: Update this section during implementation if new edge cases, behaviors, or failure modes emerge that aren't covered below. The playtest should reflect what actually needs testing, not just what we anticipated.

1. [ ] **Smoke + audit** — Must pass before starting the game.
2. [ ] **Merchant movement** — Launch into a system with merchants. Watch them for several turns. Verify they move toward a destination (planet or gate), not randomly.
3. [ ] **Merchant docks at planet** — Follow a merchant headed for a planet. When it reaches the adjacent cell, verify it despawns and the log reads like "Merchant Hauler docks at Earth."
4. [ ] **Merchant jumps through gate** — Follow a merchant headed for a jump gate. When it reaches the adjacent cell, verify it despawns and the log reads "Merchant Hauler jumps through Sol Gate."
5. [ ] **Flee from pirates** — Position a merchant within ~10 cells of a pirate. Verify the merchant moves away from the pirate for the next few turns.
6. [ ] **HUD + no glitches** — Verify space-mode HUD renders correctly after merchants despawn. No console errors.
7. [ ] **Multiple systems** — Jump between 3 systems. Verify merchants despawn/respawn correctly on each visit.
8. [ ] **Edge case: empty system** — Jump to a system with no merchants. Verify no despawn messages appear.

**PLAYTEST — Phase 3**

> **Living document**: Update this section during implementation if new edge cases, behaviors, or failure modes emerge that aren't covered below. The playtest should reflect what actually needs testing, not just what we anticipated.

1. **Smoke + audit** — Must pass before starting the game.
2. **Comms key** — In space mode, press `T` with no NPCs nearby. Verify the log says "No ships in comms range."
3. **Comms panel opens** — Fly within 15 cells of a merchant. Press `T`. Verify a comms panel modal opens listing the merchant with its comms flavor text.
4. **Comms panel navigation** — Verify UP/DOWN or j/k navigate between contacts. Verify ENTER selects a contact. Verify ESC closes the panel.
5. **Hail a merchant** — Select a merchant, press ENTER. Verify an interaction sub-modal opens showing "Open Trade" and "End Transmission" options.
6. **End Transmission** — Select "End Transmission." Verify the modal closes, you return to space mode, no crash.
7. **Hail a pirate** — Fly within range of a pirate. Press T. Verify the pirate shows `(hostile)` tag in the comms list. Select it. Verify the interaction sub-modal shows "Attack" instead of "Open Trade."
8. **Attack via comms** — Select "Attack" on a pirate. Verify the comms modal closes and combat triggers immediately. Verify combat works normally.
9. **HUD update** — Verify `T - Comms` appears in the space-mode HUD help lines.
10. **Multiple contacts** — Position yourself between a merchant and a pirate. Press T. Verify both appear in the list. Verify the pirate has `(hostile)` tag and the merchant does not.
11. **Edge case: no NPCs** — Jump to an empty system. Press T. Verify "No ships in comms range."

**PLAYTEST — Phase 4**

> **Living document**: Update this section during implementation if new edge cases, behaviors, or failure modes emerge that aren't covered below. The playtest should reflect what actually needs testing, not just what we anticipated.

1. **Smoke + audit** — Must pass before starting the game.
2. **Open Trade from comms** — Hail a merchant. Select "Open Trade." Verify the trade modal opens showing the merchant's cargo inventory (its `cargo_goods` at stock levels derived from `cargo_count`).
3. **Buy from merchant** — Buy a good from the merchant. Verify credits are deducted, cargo is added to your inventory, and the trade modal updates.
4. **Sell to merchant** — Sell a good to the merchant. Verify credits are added, cargo is removed, and the trade modal updates.
5. **Close trade** — ESC out of the trade modal. Verify you return to space mode (not back to the comms menu).
6. **Hail a civilian** — Fly near a civilian transport. Hail it. Verify flavor text reads like a passenger ship (no trade option, no cargo).
7. **Hail a milit ia patrol** — Fly near a militia patrol. Hail it. Verify flavor text reflects law enforcement. "Open Trade" may not be available (militia don't trade).
8. **Flavor text per spec** — Hail 3 different NPC types. Verify each has distinct comms lines (read from `comms_lines` on the spec).
9. **Edge case: merchant with no cargo** — If a merchant has been looted (e.g. you already bought everything), verify the trade modal shows 0 stock gracefully.
10. **Edge case: no credits** — Try to buy from a merchant with 0 credits. Verify the trade modal blocks the purchase with a log message.

### Phase 5 — Faction reputation

**Dropped from this design pass. Faction reputation will get its own dedicated design doc later.**

Built-in hooks: `NpcShipSpec.faction` field, `ctx.faction_reputation` placeholder, per-ship `detect_radius` check in combat init. These are enough to support a future faction system without combat.py rewrites.

---

## 10. Open questions

| Question | Decision |
|----------|----------|
| Should pirate ships still drop loot when destroyed? | Yes — reuse existing combat loot system. |
| Can merchants be attacked without entering comms? | Yes — same bump/combat trigger as pirates. Comms is for peaceful interaction, not the only way to engage. |
| What happens to `ctx.bounty_spawns`? | Stays as-is (bounty targets are still dynamically placed enemy entities, now using `npc_ship_id` tags). |
| What about `ctx.procedural_spawns`? | Absorbed into general NPC spawn tracking. |
| Do merchants have `detect_radius`? | 0 by default — they don't auto-engage. But if you attack one and it survives, it could become hostile with a temporary detect_radius. |

---

## 11. Related files

| File | Action |
|------|--------|
| `src/spacehack/data/npc_ships/__init__.py` | **Create** — auto-discovery + `find_npc_ship()` |
| `src/spacehack/data/npc_ships/core.py` | **Create** — `NpcShipSpec` dataclass + full catalog (pirates + merchants + civilians) |
| `src/spacehack/data/enemies/__init__.py` | **Delete** |
| `src/spacehack/data/enemies/pirates.py` | **Delete** |
| `src/spacehack/comms.py` | **Create** — comms modal + interaction |
| `src/spacehack/npc_ships.py` | **Create** — spawn + movement logic |
| `src/spacehack/combat.py` | **Modify** — `find_enemy` → `find_npc_ship`, flatten AIProfile/PilotSkills fields |
| `src/spacehack/__main__.py` | **Modify** — wire T key, wire `spawn_npcs`, replace `_move_pirates` with `move_npcs` |
| `src/spacehack/hud.py` | **Modify** — add T - Comms help line |
| `src/spacehack/world.py` | **Modify** — add `npc_ship_id` to `Entity` |
| `src/spacehack/game_context.py` | **Modify** — add `faction_reputation`, update `ProceduralSpawn` |
| `src/spacehack/data/solar_systems/__init__.py` | **Modify** — replace `pirate_chance`/`pirate_density` with unified NPC fields |
| `src/spacehack/data/solar_systems/*.py` | **Modify** — update system data with `npc_spawn_chance`/`npc_spawn_table`/`npc_density` |
| `src/spacehack/trade.py` | **Modify** — support NPC ship as trade partner |
