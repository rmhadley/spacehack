# DESIGN: Ground Combat, Crew & Dungeon Exploration

> **Updated**: After codebase audit — scope corrected downward. Most systems already exist.

## Overview

A new content layer that reuses the existing combat engine, map system, and landing flow. The player docks at a derelict ship or alien structure, enters on foot with a crew, and explores a procedurally-generated interior with ground combat and loot.

## What already exists (reusable, confirmed by audit)

| System | How ground combat reuses it |
|--------|-----------------------------|
| **`world.Entity`** | Generic dataclass (`char`, `fg`, `pos`, `name`, `width`, `height`, `owned`, `loot_data`, etc.). NOT frozen — `pos` is reassigned in-place. Ground player = `Entity(char='@')`. Crew = same. No new entity class needed. |
| **Combat loop** (`combat/_loop.py`) | `run_combat` accepts `list[enemy_insts]` — already multi-entity. Each crew member = one `EnemyInstance` in the list. Turn order currently player → all enemies; adding crew turns between them is a small change to the loop. |
| **EnemyInstance** (`combat/_types.py`) | Has `spec_id`, `name`, `char`, `fg`, `hull`, `max_hull`, `weapons`, `modules`, `pilot_gunnery`, `pilot_piloting`, `pos`, `ap_remaining`. Works for ANY combatant — ship or human. Ground HP replaces `hull`, ground AP replaces `ap_total`. |
| **Range checking** (`combat/_stats.py`) | `WeaponSpec.min_range`/`max_range` already supported. `calc_hit_chance` penalizes out-of-range shots. Melee = `min_range=1, max_range=1`. Ranged = `max_range=5+`. No changes needed. |
| **Damage resolution** (`combat/_actions.py`) | `resolve_damage(weapon_id, target_hull, target_shields, ...)` — pure function. Ground weapons feed `damage` stat pipe. No changes needed. |
| **Scene-swap pattern** (`city.py`) | `_launch_to_space` / `_return_to_city` can be copy-pasted for dungeon boarding: bump derelict → swap to dungeon map → set player as ground entity → on exit → swap back. Same pattern, different scenery. |
| **Planet landing flow** (`__main__.py`) | Bump planet → `_run_planet_menu` → LAND → scene swap. Derelict boarding = bump derelict → "Board?" dialog → scene swap. Reuses the same modal + entity-list splice pattern. |
| **Interaction system** | `loot_data` on entities for pickup modal, `trade_terminal`/`mech_terminal` bool for bump dispatch. Terminal hacking = reuse bump → modal pattern. Loot = reuse `open_loot_pickup`. |
| **ModuleSpec** (`data/modules/__init__.py`) | Additive bonus system (`power_gen_bonus`, `gunnery_bonus`, etc.). Cybernetics = same `ModuleSpec` with `slot_type="cybernetic"` and new bonus fields (`ground_hp_bonus`, `melee_skill_bonus`, `ranged_skill_bonus`, `tech_skill_bonus`). Same `find_module()`. Same mechanic terminal UI. |
| **Enemy AI** (`combat/_ai.py`) | Movement + targeting + firing. Minor tweak needed for melee AI (prefer `preferred_range=1`). |
| **Data catalogs** | `WeaponSpec`, `ModuleSpec`, `NpcShipSpec`, `PlanetSpec` — all follow the same frozen dataclass + tuple + `find_*()` pattern. Ground weapons = `GroundWeaponSpec` + one tuple. Ground enemies = `GroundEnemySpec` + one tuple. |
| **Input helpers** (`input_helpers.py`) | `_vim_action`, `_is_q_press`, `_try_open_guide` — all keyboard handling shared. Ground movement uses the same h/j/k/l/y/u/b/n keys. |
| **Message log** (`message_log.py`) | Same log. Ground combat logs to it. |

## What's genuinely NEW

| New piece | LOC estimate | Why it's new |
|-----------|-------------|--------------|
| **Dungeon map generator** (`dungeon.py`) | ~200 | Procedural room-and-corridor layout. No existing equivalent. |
| **Fog of war render pass** | ~50 | Unexplored tiles rendered black; explored-but-out-of-sight dimmed. New render state + pass. |
| **Ground weapon data** | ~30 entries | `GroundWeaponSpec` dataclass + weapons tuple. Trivial (same pattern as lasers.py). |
| **Ground armor data** | ~10 entries | `GroundArmorSpec` dataclass + armor tuple. Trivial. |
| **Ground enemy data** | ~10 entries | `GroundEnemySpec` dataclass + enemy tuple. Trivial (same pattern as NPC ships). |
| **Crew recruitment story content** | ~6 NPC specs + dialogue | Hand-crafted content, not engine work. |
| **Cybernetic data** | ~6 entries | `ModuleSpec` entries with `slot_type="cybernetic"` + new bonus fields. Trivial. |
| **Melee AI tweak** | ~10 lines | Prefer `preferred_range=1` when equipped with melee weapon. |
| **Turn order extension** | ~15 lines | Insert crew turns between player and enemies in `run_combat`. |
| **Ground stat fields on `GameContext`** | ~4 fields | `ground_hp`, `ground_ap`, `ground_armor`, `melee_skill`, `ranged_skill`, `tech_skill` |

**Total new code:** ~350-400 lines of engine code + ~100 lines of data = **~500 lines total**.

This is comparable to adding a new mission type (like bounties), not a whole new game.

## What a ground combat session looks like

```
Space mode:
  [%] Derelict debris drifting near Mars
  
  Bump it → "Board the derelict? Your ship will be docked outside."
  
  Yes → Scene swap (same pattern as landing on a planet):
    - Player entity becomes '@' on foot
    - Dungeon map with walls, corridors, rooms
    - Fog of war (unexplored = black)
    - Ground enemies patrol rooms
  
  Move with h/j/k/l/y/u/b/n (same keys)
  
  Enter combat:
    - Same combat loop (run_combat)
    - Player uses ground weapons (pistol/rifle/knife)
    - Crew members act on their turns
    - Fog of war hides enemies until in detect range
  
  Bump loot containers → open_loot_pickup (reused)
  Bump terminals → tech_skill check → unlock doors / read lore
  Bump exit → "Return to ship?" → Transfer loot → scene swap back to space
```

## Trigger: boarding a derelict

1. Player bumps a derelict entity on the space map (same as bumping a planet)
2. Dialog: "Board the {name}? You'll leave your ship docked outside."
3. Yes → `_board_derelict(ctx, location_id)` — scene swap to dungeon mode
4. No → fly past

**Where derelicts appear:**
- **Procedural spawns** — rare chance per system, like NPC ship spawns
- **Main quest Act 3** — the alien structure beyond Luyten's Star

## Boardable location types

Each type is just a parameter set — the dungeon generator, combat engine, and interaction system are shared:

| Type | Glyph | Size | Floors | Enemies | Theme color |
|------|-------|------|--------|---------|-------------|
| Derelict ship | `%` grey | 20×20 (small) | 1 | Pirate scavengers | Metal grey |
| Lost station | `O` white | 40×40 (medium) | 1-2 | Militia remnants | Tech white |
| Alien structure | `^` blue | 40×40 (medium) | 1-2 | Alien drones | Dark purple |

**Dungeon generator** (`dungeon.py`): Rooms + corridors, 1-2 floors, loot containers and enemies placed per room type. Reuses `world.GameMap` with `world.Tile` for walls/floors.

## Ground combat

### Reusing the combat engine

The existing `run_combat()` works for ground combat with minimal changes:

- **Player entity** → on-foot avatar (`Entity(char='@')`). Uses ground HP instead of hull, ground AP, ground weapons.
- **Enemy entities** → ground enemies (pirates, aliens). Reuse `EnemyInstance` model — it has `hull` (reused as ground HP), `weapons`, `modules`, `pos`, `ap_remaining`.
- **Crew entities** → player-controlled `EnemyInstance` with `is_crew=True`. They get their own turn in the initiative order.
- **Damage resolution** → same `resolve_damage()` — just different `WeaponSpec` stats.

### Ground weapons

New `data/weapons_ground.py` module. Same `WeaponSpec` dataclass repurposed:

| Weapon | Damage | Range | AP | Type |
|--------|--------|-------|----|------|
| Combat knife | 5-8 | 1 (melee) | 2 | Melee |
| Crowbar | 8-12 | 1 (melee) | 3 | Melee (opens doors) |
| Pistol | 6-10 | 5 | 3 | Ranged |
| Shotgun | 12-18 | 3 | 4 | Ranged (short range) |
| Rifle | 10-15 | 8 | 4 | Ranged |
| SMG | 4-7 | 4 | 3 | Ranged (burst) |
| Alien blaster | 15-25 | 6 | 4 | Ranged (rare) |

### Ground armor

Add an `armor_bonus` field to `ModuleSpec` (or create a `GroundArmorSpec`):

| Armor | DR | Weight | Notes |
|-------|----|--------|-------|
| Flak vest | 5 | Light | Standard |
| Combat armor | 10 | Medium | Military |
| Power armor | 20 | Heavy | -1 AP |
| Alien carapace | 15 | Medium | Rare |

### Ground stats

New fields on `GameContext`:

```python
ground_hp: int = 30
ground_max_hp: int = 30
ground_ap: int = 4
ground_armor: int = 0       # damage reduction from equipped armor
melee_skill: int = 20
ranged_skill: int = 20
tech_skill: int = 10
crew: list[CrewMember] = field(default_factory=list)
```

### Ground enemies

New `data/ground_enemies.py` — same pattern as `NpcShipSpec`:

| Enemy | HP | Weapon | Behavior |
|-------|----|--------|----------|
| Pirate scavenger | 20 | Pistol or knife | Patrols, calls for help |
| Militia guard | 30 | Rifle | Disciplined |
| Mercenary | 35 | SMG | Aggressive, flanks |
| Alien drone | 25 | Energy blast | Detects movement |

## Crew system

### Recruiting

6 hand-crafted crew members, each recruited via a short quest or payment:

| Name | Location | Recruitment | Role | Weapon |
|------|----------|-------------|------|--------|
| Mara | Luyten's Star bar | Complete bar mission | Combat | Shotgun |
| Doctor Vex | Alpha Centauri Science Port | Research delivery | Medic | Pistol |
| Finn | Earth/Mars bar | Pay 2000cr debt | Tech | Crowbar |
| Commander Rourke | Sirius depot | Allied with militia OR combat path | Combat | Rifle |
| Zara | Procyon C station | Bring rare trade good | Scientist | Pistol |
| Kael | Random derelict rescue | Save him from a derelict | Combat | SMG |

### Crew in combat

- Max **3 crew members** accompany the player
- Each has their own HP, AP, weapon, armor
- Crew are **player-controlled** — each gets a turn in the initiative order
- Crew use `EnemyInstance` model with `is_crew=True` flag
- Turn order: player → crew #1 → crew #2 → crew #3 → enemies → repeat
- Crew death in roguelike mode = permanent loss

### Multi-character turn order

Small change to `run_combat` in `_loop.py`:

```python
# Current:
#   player acts → ALL enemies act → repeat

# New:
#   player acts → crew[0] acts → crew[1] acts → crew[2] acts → ALL enemies act → repeat
```

Each crew member gets a `_run_crew_turn` function that reuses the player's weapon-firing and movement logic but is controlled via a simplified UI (select target → fire, or select position → move).

## Fog of war

- All dungeon tiles start unexplored (rendered black)
- Player and crew reveal tiles within 3-cell radius as they move
- Previously-explored tiles that are out of sight render dimly ("fog" state)
- Enemies in fog = invisible until they enter detect range

**Implementation:** Store a 2D `bool` array `seen[y][x]` in the dungeon map (or on `GameContext`). The render pass checks this array and skips unseen tiles. Add a `world.render_fog_view` variant of `render_world_view`.

## Cybernetics

Permanent upgrades installed at a station's medbay (new interaction):

| Cybernetic | Bonus | Found |
|------------|-------|-------|
| Subdermal armor | +5 ground armor | Military outposts |
| Reflex booster | +1 ground AP | Science stations |
| Neural link | +20 tech skill | Research labs |
| Targeting eye | +20 ranged skill | Black market |
| Adrenal pump | +2 AP when HP < 25% | Alien derelicts |

**Implementation:** New `ModuleSpec` entries with `slot_type="cybernetic"`. New bonus fields on `ModuleSpec`:

```python
ground_hp_bonus: int = 0
ground_ap_bonus: int = 0
ground_armor_bonus: int = 0
melee_skill_bonus: int = 0
ranged_skill_bonus: int = 0
tech_skill_bonus: int = 0
```

Same `find_module()` lookup. Same mechanic terminal UI for browsing and installing.

## Dungeon generator (the one genuinely new piece)

```python
# dungeon.py
def generate_dungeon(location_type: str, floor: int = 1) -> world.GameMap:
    """Generate a room-and-corridor dungeon map."""
```

Algorithm:
1. Start with a blank grid of WALL tiles
2. Carve rooms at semi-random positions (non-overlapping)
3. Connect rooms with corridors (simple L-shaped or straight)
4. Place doors at room entrances
5. Place loot containers in ~50% of rooms
6. Place enemies in ~60% of rooms (from location type's enemy pool)
7. Place exit at the far end

Room types (data-driven weights per location type): crew quarters, cargo hold, engine room, bridge, armory, science lab, boss chamber.

## Implementation phases

### Phase 1: Dungeon generator + boarding (NEW code)

- [ ] Create `dungeon.py` — room-and-corridor generator (~200 lines)
- [ ] Add derelict entity type to space map (reuse NPC spawn pattern)
- [ ] Wire bump → "Board?" dialog (copy planet bump flow)
- [ ] Scene swap: space map → dungeon map (copy `_launch_to_space`)
- [ ] Player entity swaps to ground `@` avatar

### Phase 2: Fog of war + render (NEW code)

- [ ] Add `seen[y][x]` 2D bool array to dungeon GameMap
- [ ] Create `render_fog_view` — unseen = black, seen-out-of-sight = dim
- [ ] Mark tiles as seen within 3-cell radius of player movement

### Phase 3: Ground combat data + integration (trivial data + small wiring)

- [ ] Add `GroundWeaponSpec` dataclass + weapons tuple
- [ ] Add ground stat fields to `GameContext`
- [ ] Add `GroundEnemySpec` dataclass + enemy tuple
- [ ] Wire ground combat into dungeon encounters — call `run_combat` with ground enemies
- [ ] Wire loot drops in dungeon rooms (reuse `open_loot_pickup`)
- [ ] Wire exit → transfer loot to ship cargo (reuse cargo transfer)

### Phase 4: Crew + multi-character turns (mostly wiring)

- [ ] Add 6 crew members with recruitment paths (story content)
- [ ] Add `is_crew` flag to `EnemyInstance`
- [ ] Extend turn order in `run_combat`: player → crew → enemies
- [ ] Add simple crew action UI (select target → fire, select position → move)
- [ ] Wire crew death handling (permadeath / injury)

### Phase 5: Terminals + cybernetics (trivial data + wiring)

- [ ] Terminal interaction: tech_skill check → unlock doors / lore display
- [ ] Add `slot_type="cybernetic"` module entries
- [ ] Add new bonus fields to `ModuleSpec`
- [ ] Wire cybernetic effects into ground stats
- [ ] Wire medbay installation UI (reuse mechanic terminal pattern)

## Total effort estimate

| Phase | Engine code | Data/content | Dependencies |
|-------|-------------|-------------|--------------|
| 1. Dungeon gen + boarding | ~200 lines | None | None |
| 2. Fog of war | ~50 lines | None | Phase 1 |
| 3. Ground combat | ~50 lines | ~60 entries | Phase 1-2 |
| 4. Crew | ~50 lines | ~6 NPCs + dialogue | Phase 3 |
| 5. Terminals + cybernetics | ~30 lines | ~12 entries | Phase 3 |

**Total: ~380 lines of engine code + ~72 data entries across ~4 new data files.**

Comparable effort to the bounty missions implementation. Not a v3 mega-project.

## Open questions (resolved by audit)

1. ~~**Should ground XP be separate from ship XP?**~~ Resolved: Same XP/level track. Ground kills give combat XP, same as ship kills.
2. ~~**Should dungeons persist after leaving?**~~ Resolved: Cleared rooms stay cleared. Enemies may respawn in uncleared rooms. The map is regenerated on re-entry with the same seed so the layout is deterministic.
3. ~~**Should crew members have their own inventory?**~~ Resolved: Share the player's inventory for simplicity (reuse ship cargo).
4. ~~**Does the combat engine need changes for friendly units?**~~ Resolved: No. `EnemyInstance` works for any combatant. Crew = `EnemyInstance` with `is_crew=True`. The turn order extension is the only change needed.
