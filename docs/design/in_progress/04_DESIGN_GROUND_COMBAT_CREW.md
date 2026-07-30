# DESIGN: Ground Combat, Crew & Dungeon Exploration

> **Updated**: After codebase audit — scope corrected downward. Most systems already exist.

## Overview

A new content layer that reuses the existing combat engine, map system, and landing flow. The player docks at a derelict ship or alien structure, enters on foot with a crew, and explores a procedurally-generated interior with ground combat and loot.

## What already exists (reusable, confirmed by audit)

| System | How ground combat reuses it |
|--------|-----------------------------|
| **`world.Entity`** | Generic dataclass (`char`, `fg`, `pos`, `name`, `width`, `height`, `owned`, `loot_data`, etc.). NOT frozen — `pos` is reassigned in-place. Ground player = `Entity(char='@')`. Ground enemies = `Entity(npc_ship_id='ground_enemy_...')`. No new entity class needed. |
| **`world.GameMap`** | ``width`` × ``height`` tile grid + entity list. Dungeon map = ``GameMap`` with ``Tile(kind="wall"/"floor")`` tiles. Same ``in_bounds``, ``is_walkable``, ``entity_at`` — all work unchanged. |
| **`world.Tile`** | Frozen dataclass: ``kind``, ``char``, ``walkable``, ``fg``, ``bg``. We define ``DUNGEON_WALL`` and ``DUNGEON_FLOOR`` tile constants (same pattern as ``WALL``/``FLOOR``). |
| **`world.try_move`** | Returns ``("moved"|"wall"|"occupied", blocker)``. Dungeon movement reuses this directly — walls block, entities block, floor is walkable. |
| **`world.render_world`** | Paints ``GameMap`` tiles + entities into console. For dungeons ≤ 40×40 we can use this directly (no scrolling needed for v1). For scrollable dungeons, ``render_world_view`` accepts ``camera_x``/``camera_y``. |
| **Scene-swap pattern** (`city.py`) | ``_launch_to_space`` removes player from city map, builds space map, places ship entity, returns ``(new_map, new_player)``. Dungeon boarding follows same pattern: remove player from space map, build dungeon, place ground entity, return. |
| **Planet bump flow** (`__main__.py`) | Bump planet → ``_run_planet_menu`` → LAND → scene swap. Derelict boarding = bump derelict → "Board?" dialog → scene swap. Same modal + entity-list splice pattern. |
| **`ui.Modal`** | ``Modal(ctx.context, console).run(render_fn, update_fn)`` — boarding dialog, loot pickup, any dungeon interaction reuses this. |
| **`open_loot_pickup`** (`trade.py`) | Already operates on ``loot_data`` dicts on entities. Dungeon loot containers = ``Entity(char='%', loot_data={"good_id": ..., "quantity": ...})``. No changes needed. |
| **`input_helpers._vim_action`** | Translates KeyDown → ``(dx, dy)`` via ``world.VIM_DELTAS``. Dungeon movement reuses this directly — same h/j/k/l/y/u/b/n keys. |
| **`combat/_types.py` EnemyInstance** | Has ``hull`` (reused as HP), ``weapons``, ``pos``, ``ap_remaining``, ``spec_id``. Already generic enough for ground combatants — shields become armor DR. |
| **`combat/_loop.py` run_combat** | Accepts ``enemy_specs``, ``enemy_positions``, ``game_map``, ``log``. Could be reused for ground combat if we feed it ground-compatible weapon/stats data. |
| **Data catalog pattern** | Every catalog: frozen ``@dataclass`` + ``_BY_ID: dict[str, Spec]`` + ``find_*(id)``. Ground weapons/armor/enemies follow the exact same pattern. |

## Pre-implementation audit (MANDATORY — knowledge.md)

### Existing classes / modules to extend or reuse

1. **Scene swap: `city._launch_to_space` → `_board_derelict`**
   The launch pattern (remove player from source map, build destination map, place entity, return tuple) is a template for dungeon boarding. The key difference: dungeon boarding has no ship animation — just an instant scene swap. We should extract a minimal ``_swap_scene(ctx, new_map, new_player, mode)`` helper rather than copy-paste the 40-line ``_launch_to_space`` body.

2. **Map building: `world.make_building` → `dungeon.py` room carving**
   ``make_building`` carves a labeled rectangle with walls, doors, and interior. The dungeon generator carves rooms with walls, corridors, and doors. Both return tile changes + entity lists. The dungeon generator is new code but the *pattern* (build a tile grid, carve shapes, return ``(tile_changes, entities)``) is identical.

3. **Render: `world.render_world` → fog-aware variant**
   ``render_world`` iterates tiles then entities into the console. For fog of war we need a variant that checks ``seen[y][x]`` before painting. Rather than duplicating the 30-line render loop, add an optional ``seen: list[list[bool]] | None = None`` parameter. Unseen = black tile; seen = normal render.

4. **Entity construction: `world.Entity` kwargs**
   ``Entity`` already supports ``npc_ship_id``, ``loot_data``, ``name``, ``char``, ``fg``, ``pos``. Ground entities (player, enemies, loot containers, exit markers) use the same class with different field combinations. No subclassing needed — just different construction arguments.

5. **Combat: `EnemyInstance` as ground combatant**
   The existing ``EnemyInstance`` has ``hull`` (reuse as ground HP), ``shields`` (reuse as armor DR), ``weapons``, ``pos``, ``ap_remaining``. ``init_combat_state`` already builds these from specs. A ground-combat variant of ``init_combat_state`` feeds ground weapon stats and armor values.

6. **Movement: `world.try_move` unchanged**
   Same ``VIM_DELTAS``, same ``try_move`` with ``("moved"|"wall"|"occupied", blocker)`` return. The dungeon game loop calls this identically to city mode.

7. **Loot: `trade.open_loot_pickup` unchanged**
   Already reads ``loot_data`` dicts on entities. Dungeon loot containers set ``loot_data`` on construction. No changes needed.

### Three duplication hotspots + DRY strategies

#### Hotspot 1: Scene-swap boilerplate

**Risk:** Copying ``_launch_to_space``'s 40-line body for dungeon boarding duplicates: entity-list management (remove from old map, add to new), map generation, entity placement, mode tracking. Every future "swap scene" feature would repeat this.

**DRY strategy:** Extract a ``_swap_scene(ctx, new_map, new_entity, mode)`` helper (∼8 lines):

```python
def _swap_scene(ctx, new_map, new_entity, mode):
    """Atomically swap ctx to a new map, player entity, and mode."""
    ctx.game_map = new_map
    ctx.player = new_entity
    ctx._current_ground_mode = mode  # 'city' | 'space' | 'dungeon'
    new_map.entities.append(new_entity)
    return (new_map, new_entity)
```

The current launch/land flow pre-animates the ship entity and spawns NPCs before calling the equivalent logic — those stay in their callers. The swap itself is the shared part.

#### Hotspot 2: Entity construction drift

**Risk:** Ground player, ground enemies, loot containers, exit markers all construct ``Entity(...)`` with slightly different keyword combinations. Over 5+ phases these tend to drift (different defaults, inconsistent field population).

**DRY strategy:** Use explicit keyword arguments at every construction site. ``Entity`` already has sensible defaults (``width=1, height=1, ship_id='', npc_id='', ...``). Don't create factory functions for a 10-arg dataclass — the dataclass IS the factory. The DRY check is: every construction site uses keyword args, never positional beyond ``char`` and ``fg``:

```python
# Good — keywords, self-documenting
Entity(char='@', fg=(255,255,255), pos=start_pos, name='Player')

# Bad — positional args, order-dependent
Entity('@', (255,255,255), start_pos, 'Player', 1, 1)
```

#### Hotspot 3: Render pass for fog of war

**Risk:** Copying ``render_world``'s 30-line tile+sprite loop into a ``render_fog_view`` duplicates the iteration, entity culling, and footprint logic. If ``render_world`` changes (e.g. entity sorting), the fog variant silently diverges.

**DRY strategy:** Add an optional ``seen`` parameter to ``render_world`` (not a separate function):

```python
def render_world(console, game_map, *, region_x, region_y, region_w, region_h,
                 seen: list[list[bool | None]] | None = None):
    # None | True | False per cell: None = unseen (black),
    # False = explored-out-of-sight (dim), True = visible (normal)
```

This keeps the render logic in one place. The caller builds the ``seen`` array from the dungeon's exploration state. For city/space mode, ``seen=None`` skips the check entirely (no perf impact).

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

## Contracts compliance (MANDATORY — see knowledge.md)

- [ ] **Save/load:** New GameContext fields (ground_hp, ground_ap, ground_armor, ground skills, crew roster) → both `_ctx_to_dict()` AND `load_game()`
- [ ] **Save/load:** Dungeon state (map, enemies, fog of war) — may need specialized serialization or procedural regeneration
- [ ] **NPC spawns:** Ground enemies → if they persist outside the dungeon map, register in appropriate spawn tracking
- [ ] **Game guide:** Ground combat, crew, dungeons → new `_GUIDE_GROUND_COMBAT` section
- [ ] **Module-level state:** No new module-level globals expected (dungeon map is entity on space map)

## Open questions (resolved by audit)

1. ~~**Should ground XP be separate from ship XP?**~~ Resolved: Same XP/level track. Ground kills give combat XP, same as ship kills.
2. ~~**Should dungeons persist after leaving?**~~ Resolved: Cleared rooms stay cleared. Enemies may respawn in uncleared rooms. The map is regenerated on re-entry with the same seed so the layout is deterministic.
3. ~~**Should crew members have their own inventory?**~~ Resolved: Share the player's inventory for simplicity (reuse ship cargo).
4. ~~**Does the combat engine need changes for friendly units?**~~ Resolved: No. `EnemyInstance` works for any combatant. Crew = `EnemyInstance` with `is_crew=True`. The turn order extension is the only change needed.
