# DESIGN: Ground Combat, Crew & Dungeon Exploration (v2)

## Overview

A new content layer that reuses the existing combat engine, map system, and landing flow. The player docks at a derelict ship or alien structure, enters on foot with a crew, and explores a procedurally-generated interior with ground combat and loot.

### What already exists (reusable)

| System | Reuse for ground combat |
|--------|------------------------|
| **Combat loop** (`combat/_loop.py`) | Same turn-based engine. Ground combat reuses `run_combat` with ground weapons. No new combat system needed. |
| **Map rendering** (`world.render_world_view`) | Dungeon interiors use the same tile grid, camera, and entity rendering. |
| **Entity system** (`world.Entity`) | Player entity, crew entities, enemy entities — all reuse `world.Entity` with `width=1, height=1`. |
| **Landing flow** (`city.py`) | Boarding a derelict = landing on a planet. Switches from space map to interior map using the same scene-swap pattern. |
| **Message log** (`message_log.py`) | Ground combat logs to the same message log. |
| **Loot/inventory** (`ship.cargo_used`) | Ground loot transfers to ship cargo on exit. |
| **Movement** (h/j/k/l/y/u/b/n) | Same grid movement as space/combat. |
| **Modal UI** (`ui.Modal`) | Interaction dialogs (loot, terminals, doors) reuse the same modal pattern. |

### What's NEW

| New piece | Scope |
|-----------|-------|
| **Dungeon map generator** | Procedural room-and-corridor layout (30-60 tiles). New module. |
| **Ground weapons dataclass** | 7 weapon entries (knife through alien blaster). Like `data/weapons/lasers.py` but for ground. |
| **Ground armor/cybernetics data** | New data modules. |
| **Crew NPCs** | 6 hand-crafted crew members with recruitment quests. Like guild NPCs but recruitable. |
| **Multi-character turn order** | Crew members share the combat initiative with the player. Extends `enemy_insts` pattern. |
| **Fog of war** | Unexplored tiles rendered black. New render pass. |
| **Terminal interaction** | Hack doors, read lore. New interaction type. |

## Trigger: boarding a derelict

1. Player bumps a derelict entity on the space map (same as bumping a planet)
2. Dialog: "Board the {name}? You'll leave your ship docked outside."
3. Yes -> `_board_derelict(ctx, location_id)` — scene swap to dungeon mode
4. No -> fly past

**Where derelicts appear:**
- **Main quest Act 3** — the alien structure beyond Luyten's Star. First encounter.
- **Random events** — rare procedural spawn (like NPC ships), chance-based per system

## Boardable location types

The same dungeon generation + ground combat system supports multiple location types. Each type has its own tileset, enemy pool, and loot table — but the underlying engine is shared. No new systems per type.

### Location type catalog

| Type | Space glyph | Size | Floors | Enemies | Loot | Where found |
|------|-------------|------|--------|---------|------|-------------|
| **Derelict ship** | `%` grey | Medium | 1-2 | Pirate scavengers | Trade goods, ship modules | Random space encounter |
| **Asteroid base** | `*` brown | Small | 1-3 | Pirates, mercenaries | Weapons, black market goods | Asteroid belt systems |
| **Science facility** | `S` teal | Medium | 1-2 | Security drones, mercenaries | Research data, cybernetics | Near science ports |
| **Alien monolith** | `^` blue | Small | 1 | Alien constructs | Alien artifacts, unique tech | Beyond charted space |
| **Alien derelict** | `A` purple | Large | 2-3 | Alien drones, alien sentinel | Alien blaster, carapace, memory shard | Main quest Act 3 |
| **Orbital station** | `O` white | Large | 1-2 | Militia remnants, scavengers | Equipment, credits, lore | High-traffic systems |

### Visual differentiation

- Each type gets a unique glyph + color on the space map
- Different wall/floor tile colors in the dungeon (ship = metal grey, asteroid = stone brown, monolith = glossy black, facility = white tile, alien = dark purple)
- Different room narration on entry ("The air recyclers are dead. Silence." vs "The walls hum with light that has no source.")

### All types share one pipeline

```
Board (bump entity) -> generate_dungeon(type, floor)
                   -> scene swap to dungeon map
                   -> explore + ground combat
                   -> exit -> cargo transfer
```

Each type is just a parameter set (tileset, enemy pool, loot table, room weights, size).

## Dungeon generation

A new module `src/spacehack/dungeon.py` generates interior maps:

```python
def generate_dungeon(location_type: str, floor: int = 1) -> world.GameMap:
    """Generate a room-and-corridor dungeon map for a location type."""
```

- Map sizes per type: small (20x20), medium (40x40), large (60x60)
- Rooms are rectangular with 1-tile walls, connected by corridors
- Each room has a random type from a weighted pool (per location type)
- Loot containers, enemies, and terminals placed per room type
- 1-3 floors per location, deeper = harder

**Room types and contents (shared pool, weighted differently per type):**

| Room type | Loot | Enemies | Terminals |
|-----------|------|---------|-----------|
| Crew quarters | Common goods | 0-1 | No |
| Bridge | Nav data | 1-2 | Lore |
| Cargo hold | Trade goods | 0-2 | No |
| Engine room | Components | 1 | Environmental hazard |
| Armory | Weapons/armor | 1-3 | No |
| Science lab | Cybernetics/research | 1-2 | Lore + data |
| Boss chamber | Rare loot | 1 boss | Lore |

## Ground combat

### Reusing the combat engine

The existing `run_combat()` function works for ground combat with minimal changes:

- **Player entity** -> the on-foot avatar (not the ship). Uses ground HP, AP, weapons.
- **Enemy entities** -> ground enemies (pirates, aliens, etc.) — reuse `EnemyInstance` pattern.
- **Crew entities** -> controlled by the player, each with their own turn in the turn order. Extends `enemy_insts` to support friendly NPC instances.
- **Damage resolution** -> same `resolve_damage()` — just different weapon stats.

### Ground weapons

A new `data/weapons_ground.py` module. Same `Weapon` dataclass as ship weapons, but ground-balanced:

| Weapon | Damage | Range | AP | Type | Special |
|--------|--------|-------|----|------|---------|
| Combat knife | 5-8 | 1 | 2 | Melee | Silent kill |
| Crowbar | 8-12 | 1 | 3 | Melee | Opens doors |
| Pistol | 6-10 | 5 | 3 | Ranged | Standard |
| Shotgun | 12-18 | 3 | 4 | Ranged | Cone AoE |
| Rifle | 10-15 | 8 | 4 | Ranged | Accurate |
| SMG | 4-7 | 4 | 3 | Ranged | 3-round burst |
| Alien blaster | 15-25 | 6 | 4 | Ranged | Rare |

### Ground armor

A new `data/armor.py` module:

| Armor | DR | Weight | Notes |
|-------|----|--------|-------|
| Flak vest | 5 | Light | Standard |
| Combat armor | 10 | Medium | Military |
| Power armor | 20 | Heavy | -1 AP |
| Alien carapace | 15 | Medium | Rare |

### Ground stats

Ground combat uses a **separate stat block** from pilot skills:

- `ground_hp: int = 30` — increases with player level (+5/level)
- `ground_ap: int = 4` — base action points
- `ground_armor: int = 0` — damage reduction from equipped armor
- `melee_skill: int = 20` — accuracy/damage with melee weapons
- `ranged_skill: int = 20` — accuracy with ranged weapons
- `tech_skill: int = 10` — hack terminals, disable traps

These live on `GameContext` like `pilot_skills` but separate. They don't affect ship combat and pilot skills don't affect ground combat.

### Ground enemies

Reuse the `NpcShipSpec` pattern but for ground:

```python
@dataclass(frozen=True)
class GroundEnemySpec:
    id: str
    name: str
    char: str
    fg: tuple[int, int, int]
    hp: int
    ap: int = 4
    armor: int = 0
    weapon_id: str = "pistol"
    ranged_skill: int = 20
    melee_skill: int = 10
    ai_aggressiveness: int = 50
    loot_table: tuple[str, ...] = ()
```

| Enemy | HP | Weapon | Behavior |
|-------|----|--------|----------|
| Pirate scavenger | 20 | Pistol or knife | Patrols, calls for help on sight |
| Militia guard | 30 | Rifle | Uses cover, disciplined |
| Mercenary | 35 | SMG | Aggressive, flanks |
| Alien drone | 25 | Energy blast | Patrolling, detects movement |
| Alien sentinel (boss) | 50 | Plasma beam | Calls drones, multi-phase |

## Crew system

### Recruiting

6 hand-crafted crew members, each with a unique recruitment path:

| Name | Location | Recruitment | Role | Weapon |
|------|----------|-------------|------|--------|
| Mara | Luyten's Star bar | Complete a bar mission | Combat | Shotgun |
| Doctor Vex | Alpha Centauri Science Port | Complete research delivery | Medic | Pistol |
| Finn | Earth (Mars bar) | Pay 2000cr debt | Tech | Crowbar |
| Commander Rourke | Sirius depot | Allied with militia OR combat path | Combat | Rifle |
| Zara | Procyon C research station | Bring rare trade good | Scientist | Pistol |
| Kael | Random derelict rescue | Save him from a derelict | Combat | SMG |

### Crew in combat

- Max **3 crew members** accompany the player
- Each crew member has their own HP, AP, weapon, armor
- Crew are **player-controlled** — each gets a turn in the initiative order
- Crew use the same `EnemyInstance` model but with `is_crew=True` flag
- Turn order: player -> crew #1 -> crew #2 -> crew #3 -> enemies -> repeat
- Crew death in roguelike mode = permanent loss
- Crew death in adventure/RPG mode = injured (skip one dungeon)

### Crew relationships

| Pair | Bonus |
|------|-------|
| Mara + Finn | +1 AP each |
| Doctor Vex + Zara | +10% heal effectiveness |
| Commander Rourke + Kael | +2 damage each |

## Fog of war

- All dungeon tiles start unexplored (rendered black)
- Player and crew reveal tiles within 3-cell radius as they move
- Previously-explored tiles that are out of sight render dimly ("fog" state)
- Enemies in fog = invisible (can be heard? sound indicator for proximity?)

## Interaction types

- **Open door** (bump) — 1 AP, may require tech_skill check if locked
- **Loot container** (bump) — Open inventory modal, take items
- **Use terminal** (bump + tech check) — Lore text, unlock doors, disable traps
- **Return to ship** (bump entrance) — Exit dialog, transfer loot, leave dungeon

## Cybernetics

Permanent upgrades installed at a station's medbay (new interaction option for lab/research buildings):

| Cybernetic | Effect | Found |
|------------|--------|-------|
| Subdermal armor | +5 armor | Military outposts |
| Reflex booster | +1 ground AP | Science stations |
| Neural link | +20 tech skill | Research labs |
| Targeting eye | +20 ranged skill | Black market |
| Adrenal pump | +2 AP when HP < 25% | Alien derelicts |
| Memory shard | Unique dialogue | Main quest reward |

## Implementation phases

### Phase 1: Dungeon generation + basic boarding

- [ ] Add `dungeon.py` — procedural room-and-corridor generator
- [ ] Add derelict entity types to space map (unique glyph per type)
- [ ] Wire bump -> board dialog (reuse planet-bump flow)
- [ ] Scene swap: space map -> dungeon map (reuse landing pattern)
- [ ] Render dungeon with fog of war (unexplored = black)
- [ ] Smoke test + commit

### Phase 2: Ground combat integration

- [ ] Add ground stat fields to `GameContext`
- [ ] Add `ground_enemy_specs` data module
- [ ] Wire ground combat into dungeon encounters — reuse `run_combat`
- [ ] Add ground weapons data table
- [ ] Add ground armor data table
- [ ] Wire loot drops in dungeon rooms
- [ ] Wire exit -> transfer loot to ship cargo
- [ ] Smoke test + commit

### Phase 3: Crew

- [ ] Add 6 crew members with recruitment paths
- [ ] Add multi-character turn order to combat (crew + player + enemies)
- [ ] Wire crew UI: show crew HP, AP, weapon in combat HUD
- [ ] Crew death handling (permadeath / injury)
- [ ] Crew relationship bonuses
- [ ] Smoke test + commit

### Phase 4: Terminals + cybernetics

- [ ] Terminal interaction (tech check to unlock, lore display)
- [ ] Hackable doors
- [ ] Cybernetics data table + installation at medbay
- [ ] Cybernetic effects wired into ground stats
- [ ] Smoke test + commit

### Phase 5: Alien derelict + main quest integration

- [ ] Wire Act 3 alien structure as the first dungeon
- [ ] Add alien drone + sentinel ground enemies
- [ ] Boss room with multi-phase sentinel fight
- [ ] Alien blaster + carapace as unique loot
- [ ] Memory shard as main quest reward
- [ ] Smoke test + commit

## Prerequisites

Before ground combat can be implemented, these existing systems must be stable:

1. Ship combat (existing)
2. City landing/boarding flow (existing)
3. World map + entity system (existing)
4. Game infrastructure / save/load (designed)
5. Main quest Act 3 content (designed)

The scope is moderate — comparable to adding a new mission type, not a whole new game.

## Open questions

1. **Should crew members have their own inventory, or share the player's?** Share the player's for simplicity.
2. **Should ground XP be separate from ship XP?** Separate track — ground kills give ground XP, ship kills give ship XP. Both feed into the same player level.
3. **Floating alien ship = Act 3 dungeon?** Yes — the alien derelict beyond Luyten's Star is the entry point.
4. **Should dungeons persist after leaving?** Cleared rooms stay cleared, but enemies may respawn in uncleared rooms after some time.
5. **Should the player be able to retreat mid-dungeon?** Yes — reaching the entrance and choosing "Return to ship" saves progress (loot earned so far). The dungeon resets cleared state on re-entry.
