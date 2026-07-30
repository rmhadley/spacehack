# DESIGN: Ground Combat, Crew & Dungeon Exploration — Framework

> **Scope**: Solid, testable framework — not full content. Crew and cybernetics deferred to a
> future content pass. This pass ships: dungeon generator, boarding flow, fog of war,
> basic ground combat with 3 weapons + 2 enemies, and loot pickup.
>
> **Updated**: Pre-implementation audit complete. Phases rewritten with playtest checklists.

## Overview

A new content layer that reuses the existing combat engine, map system, and landing flow.
The player docks at a derelict ship, enters on foot, and explores a procedurally-generated
interior with ground combat and loot. **No crew, no cybernetics, no terminals — those are
Phase 5+ content expansions.**

## What already exists (reusable, confirmed by audit)

| System | How ground combat reuses it |
|--------|-----------------------------|
| **`world.Entity`** | Generic dataclass (`char`, `fg`, `pos`, `name`, `width`, `height`, `owned`, `loot_data`, etc.). NOT frozen — `pos` is reassigned in-place. Ground player = `Entity(char='@')`. Ground enemies = `Entity(npc_ship_id='ground_enemy_...')`. No new entity class needed. |
| **`world.GameMap`** | `width` × `height` tile grid + entity list. Dungeon map = `GameMap` with `Tile(kind="wall"/"floor")` tiles. Same `in_bounds`, `is_walkable`, `entity_at` — all work unchanged. |
| **`world.Tile`** | Frozen dataclass: `kind`, `char`, `walkable`, `fg`, `bg`. We define `DUNGEON_WALL` and `DUNGEON_FLOOR` tile constants (same pattern as `WALL`/`FLOOR`). |
| **`world.try_move`** | Returns `("moved"|"wall"|"occupied", blocker)`. Dungeon movement reuses this directly — walls block, entities block, floor is walkable. |
| **`world.render_world`** | Paints `GameMap` tiles + entities into console. For dungeons ≤ 40×40 we can use this directly (no scrolling needed for v1). For scrollable dungeons, `render_world_view` accepts `camera_x`/`camera_y`. Fog of war adds an optional `seen` parameter — no new render function. |
| **Scene-swap pattern** (`city.py`) | `_launch_to_space` removes player from city map, builds space map, places ship entity, returns `(new_map, new_player)`. Dungeon boarding follows same pattern: remove player from space map, build dungeon, place ground entity, return. |
| **Planet bump flow** (`__main__.py`) | Bump planet → `_run_planet_menu` → LAND → scene swap. Derelict boarding = bump derelict → "Board?" dialog → scene swap. Same modal + entity-list splice pattern. |
| **`ui.Modal`** | `Modal(ctx.context, console).run(render_fn, update_fn)` — boarding dialog, loot pickup, any dungeon interaction reuses this. |
| **`open_loot_pickup`** (`trade.py`) | Already operates on `loot_data` dicts on entities. Dungeon loot containers = `Entity(char='%', loot_data={"good_id": ..., "quantity": ...})`. No changes needed. |
| **`input_helpers._vim_action`** | Translates KeyDown → `(dx, dy)` via `world.VIM_DELTAS`. Dungeon movement reuses this directly — same h/j/k/l/y/u/b/n keys. |
| **`combat/_types.py` EnemyInstance`** | Has `hull` (reused as HP), `weapons`, `pos`, `ap_remaining`, `spec_id`. Already generic enough for ground combatants — shields become armor DR. |
| **`combat/_loop.py` run_combat`** | Accepts `enemy_specs`, `enemy_positions`, `game_map`, `log`. Could be reused for ground combat if we feed it ground-compatible weapon/stats data. |
| **Data catalog pattern** | Every catalog: frozen `@dataclass` + `_BY_ID: dict[str, Spec]` + `find_*(id)`. Ground weapons/enemies follow the exact same pattern. |

## Pre-implementation audit (MANDATORY — knowledge.md)

### Existing classes / modules to extend or reuse

1. **Scene swap: `city._launch_to_space` → `_board_derelict`**
   The launch pattern (remove player from source map, build destination map, place entity, return tuple) is a template for dungeon boarding. The key difference: dungeon boarding has no ship animation — just an instant scene swap. We should extract a minimal `_swap_scene(ctx, new_map, new_player, mode)` helper rather than copy-paste the 40-line `_launch_to_space` body.

2. **Map building: `world.make_building` → `dungeon.py` room carving**
   `make_building` carves a labeled rectangle with walls, doors, and interior. The dungeon generator carves rooms with walls, corridors, and doors. Both return tile changes + entity lists. The dungeon generator is new code but the *pattern* (build a tile grid, carve shapes, return `(tile_changes, entities)`) is identical.

3. **Render: `world.render_world` → fog-aware variant**
   `render_world` iterates tiles then entities into the console. For fog of war we add an optional `seen: list[list[bool | None]] | None = None` parameter rather than duplicating the 30-line render loop. Unseen = black tile; seen-out-of-sight = dim; seen = normal.

4. **Entity construction: `world.Entity` kwargs**
   `Entity` already supports `npc_ship_id`, `loot_data`, `name`, `char`, `fg`, `pos`. Ground entities (player, enemies, loot containers, exit markers) use the same class with different field combinations. No subclassing needed.

5. **Combat: `EnemyInstance` as ground combatant**
   The existing `EnemyInstance` has `hull` (reuse as ground HP), `shields` (reuse as armor DR), `weapons`, `pos`, `ap_remaining`. `init_combat_state` already builds these from specs. A ground-combat variant feeds ground weapon stats and armor values.

6. **Movement: `world.try_move` unchanged**
   Same `VIM_DELTAS`, same `try_move` with `("moved"|"wall"|"occupied", blocker)` return. The dungeon game loop calls this identically to city mode.

7. **Loot: `trade.open_loot_pickup` unchanged**
   Already reads `loot_data` dicts on entities. Dungeon loot containers set `loot_data` on construction. No changes needed.

### Three duplication hotspots + DRY strategies

#### Hotspot 1: Scene-swap boilerplate

**Risk:** Copying `_launch_to_space`'s 40-line body for dungeon boarding duplicates: entity-list management, map generation, entity placement, mode tracking.

**DRY strategy:** Extract a `_swap_scene(ctx, new_map, new_entity, mode)` helper (~8 lines):

```python
def _swap_scene(ctx, new_map, new_entity, mode):
    """Atomically swap ctx to a new map, player entity, and mode."""
    ctx.game_map = new_map
    ctx.player = new_entity
    ctx._current_mode = mode  # 'city' | 'space' | 'dungeon'
    new_map.entities.append(new_entity)
    return (new_map, new_entity)
```

The current launch/land flow pre-animates the ship entity and spawns NPCs before calling the equivalent logic — those stay in their callers. The swap itself is the shared part.

#### Hotspot 2: Entity construction drift

**Risk:** Ground player, ground enemies, loot containers, exit markers all construct `Entity(...)` with slightly different keyword combinations.

**DRY strategy:** Use explicit keyword arguments at every construction site. `Entity` already has sensible defaults. Don't create factory functions for a 10-arg dataclass — the dataclass IS the factory. Every construction site uses keyword args, never positional beyond `char` and `fg`:

```python
# Good — keywords, self-documenting
Entity(char='@', fg=(255,255,255), pos=start_pos, name='Player')

# Bad — positional args, order-dependent
Entity('@', (255,255,255), start_pos, 'Player', 1, 1)
```

#### Hotspot 3: Render pass for fog of war

**Risk:** Copying `render_world`'s 30-line tile+sprite loop into a `render_fog_view` duplicates the iteration, entity culling, and footprint logic.

**DRY strategy:** Add an optional `seen` parameter to `render_world` (not a separate function):

```python
def render_world(console, game_map, *, region_x, region_y, region_w, region_h,
                 seen: list[list[bool | None]] | None = None):
    # None | True | False per cell: None = unseen (black),
    # False = explored-out-of-sight (dim), True = visible (normal)
```

For city/space mode, `seen=None` skips the check entirely (no perf impact).

## Dungeon generator — the one genuinely new piece

```python
# dungeon.py
def generate_dungeon(location_type: str, *, seed: int = 0) -> world.GameMap:
    """Generate a room-and-corridor dungeon map."""
```

Algorithm:
1. Start with a blank grid of DUNGEON_WALL tiles (20×20 for derelict, 40×40 for stations)
2. Carve 5-8 rooms at semi-random positions (non-overlapping)
3. Connect rooms with L-shaped corridors
4. Place doors at room-to-corridor junctions
5. Place player spawn in first room, exit in last room
6. Place 1-2 loot containers per room (50% chance each)
7. Place 1 enemy per non-spawn room (from location type's enemy pool)

Room types: storage, crew quarters, engine room, bridge, armory.

No multi-floor support in v1 — that's Phase 4.

## Ground combat — minimal viable set

### Weapons (3 for framework)

New `data/ground_weapons.py` — same frozen dataclass + `find_*()` pattern:

| Weapon ID | Damage | Range | AP | Type |
|-----------|--------|-------|-----|------|
| `knife` | 5-8 | 1 (melee, min_range=1, max_range=1) | 2 | Melee |
| `pistol` | 6-10 | 5 | 3 | Ranged |
| `rifle` | 10-15 | 8 | 4 | Ranged |

### Enemies (2 for framework)

New `data/ground_enemies.py` — same frozen dataclass + `find_*()` pattern:

| Enemy ID | HP | Weapon | Char | FG |
|----------|-----|--------|------|-----|
| `scavenger` | 20 | `knife` or `pistol` (50/50) | `s` | (200,150,100) |
| `guard` | 30 | `rifle` | `g` | (150,200,150) |

### Ground stats (on GameContext)

```python
ground_hp: int = 30
ground_max_hp: int = 30
ground_armor: int = 0       # damage reduction (0 for framework — no armor items yet)
```

No melee/ranged/tech skills for framework — those come with the content pass.
No crew, no cybernetics, no terminal hacking.

## Fog of war

- All dungeon tiles start unseen (rendered as black space)
- Player reveals tiles within 3-cell radius on each move
- Previously-seen tiles out of sight render dim (70% brightness)
- Enemies in unseen tiles are invisible (not rendered, not interactable)

**Implementation:** Add `seen: list[list[bool | None]]` to `GameMap` or a parallel array on the dungeon state. `render_world` checks it per cell. Player movement marks cells as seen.

## What a framework session looks like

```
Space mode:
  [%] Derelict debris drifting near Mars

  Bump it → "Board the derelict? Your ship will be docked outside."

  Yes → Scene swap:
    - Player becomes '@' on foot (30 HP)
    - 20×20 dungeon with walls, corridors, 5-8 rooms
    - Fog of war (unseen = black)
    - 1-2 enemies per room
    - Loot containers (% glyphs) in ~50% of rooms

  Move with h/j/k/l/y/u/b/n (same keys)

  Walk into an enemy → combat:
    - Same combat loop (run_combat)
    - Player uses pistol or rifle
    - Enemies use their assigned weapon

  Walk into loot (%) → open_loot_pickup (reused)

  Walk into exit (>) → "Return to ship?" → transfer loot → scene swap to space
```

## Implementation phases

### Phase 1: Dungeon generator + boarding

**Goal:** Generate a dungeon, board it, walk around, see walls and floors. No enemies, no loot, no fog, no combat. Just a walkable dungeon you can enter and leave.

- [ ] Create `dungeon.py` — `generate_dungeon(location_type, seed)` returning `world.GameMap`
- [ ] Add `DUNGEON_WALL` / `DUNGEON_FLOOR` tile constants to `world.py`
- [ ] Add derelict entity (`%` glyph) to space map as a hardcoded test spawn near Sol's Earth
- [ ] Wire bump → "Board?" dialog (`ui.Modal` pattern from `_run_planet_menu`)
- [ ] Scene swap: save space map + player entity, build dungeon, swap `ctx.game_map` / `ctx.player`
- [ ] Dungeon movement: reuse `_vim_action` + `try_move` (city-mode style)
- [ ] Walk into exit (`>` glyph) → "Return to ship?" → restore space map + ship entity
- [ ] Smoke test + commit

#### Playtest checklist

- [ ] Launch from Earth, fly to derelict `%`, bump it → "Board?" dialog appears
- [ ] Board → dungeon map renders with `#` walls and `.` floors
- [ ] Walk with h/j/k/l → walls block, floor is passable
- [ ] Walk into `>` exit → "Return to ship?" → back in space at derelict position
- [ ] Re-board → same dungeon layout (deterministic seed)
- [ ] ESC from dungeon → save on space map, quit, continue → back in space (dungeon state not persisted yet)

---

### Phase 2: Fog of war + loot

**Goal:** Dungeon exploration feels like discovery. Unexplored areas are hidden. Loot containers provide the reward loop.

- [ ] Add optional `seen` parameter to `render_world` (DRY hotspot #3)
- [ ] Track `seen[y][x]` array on dungeon state — 3-cell reveal radius on player move
- [ ] Unseen tiles = black; seen-out-of-sight = dim (70% brightness); seen = normal
- [ ] Spawn 1-2 loot containers (`%` glyph, `loot_data=...`) in each room during generation
- [ ] Walk into loot → `open_loot_pickup` (reused from `trade.py`, no changes)
- [ ] Smoke test + commit

#### Playtest checklist

- [ ] Board derelict → most of map is black
- [ ] Move around → tiles revealed in 3-cell radius
- [ ] Walk away from a revealed area → tiles remain visible but dim
- [ ] Find a loot `%` glyph → bump it → pickup modal shows the good + quantity
- [ ] Take loot → added to player inventory (verify in cargo menu `I`)
- [ ] Exit dungeon → back in space, cargo has the looted goods

---

### Phase 3: Ground combat

**Goal:** Walk into an enemy → fight them with ground weapons using the existing combat engine.

- [ ] Create `data/ground_weapons.py` — 3 weapons (knife, pistol, rifle) — frozen dataclass + `find_*()`
- [ ] Create `data/ground_enemies.py` — 2 enemies (scavenger, guard) — frozen dataclass + `find_*()`
- [ ] Add `ground_hp`, `ground_max_hp`, `ground_armor` fields to `GameContext`
- [ ] Spawn enemies as `Entity(npc_ship_id='ground_enemy_...', char=..., fg=...)` in dungeon rooms
- [ ] Walk into enemy → ground combat: build `EnemyInstance` from ground enemy spec, call `run_combat`
- [ ] Ground combat: hull = HP, shields = armor, ground weapons feed the same `resolve_damage` pipe
- [ ] Enemy death → remove entity from dungeon map (reuse `_remove_dead_entity` pattern)
- [ ] Player death → log "You collapse..." → exit dungeon → respawn at ship with 1 HP
- [ ] Smoke test + commit

#### Playtest checklist

- [ ] Board derelict → see enemy glyphs (`s` or `g`) in rooms
- [ ] Walk into enemy → combat starts, combat HUD renders
- [ ] Fire weapon (F) → damage applied to enemy HP, enemy name + HP shown in HUD
- [ ] Kill enemy → "destroyed" message, enemy glyph removed from dungeon map
- [ ] Enemy hits player → ground_hp decreases in HUD
- [ ] Player HP hits 0 → "You collapse" → back in space at derelict, HP = 1
- [ ] Save after exiting dungeon, quit, continue → back in space (ground stats reset — dungeon not persisted)

---

### Phase 4: Save/load + guide (future)

Deferred until the framework is solid. Dungeon state persistence (map, entities, fog, ground stats) is the biggest remaining piece.

- [ ] Serialize dungeon state (map seed + cleared room flags → regenerate on load)
- [ ] Save/restore ground_hp, ground_armor
- [ ] Add `_GUIDE_GROUND_COMBAT` section to `help.py`

### Phase 5: Crew, cybernetics, terminals (future content pass)

Full content expansion — deferred. See original sections below for the design.

## Contracts compliance (MANDATORY — see knowledge.md)

- [ ] **Save/load:** New GameContext fields (ground_hp, ground_max_hp, ground_armor) → both `_ctx_to_dict()` AND `load_game()` (Phase 4)
- [ ] **Save/load:** Dungeon state — procedural regeneration from seed + cleared-room flags (Phase 4)
- [ ] **NPC spawns:** Ground enemies are dungeon-only, not in `ctx.procedural_spawns` — no persistence needed (entities rebuilt from seed on re-entry)
- [ ] **Game guide:** Ground combat section in `help.py` (Phase 4)
- [ ] **Module-level state:** No new module-level globals expected

## Open questions

1. **Save/load strategy for dungeons?** Regenerate from seed + track cleared rooms. Simplest approach: on re-entry, regenerate the same layout, skip enemies in cleared rooms. This avoids serializing the entire dungeon map.
2. **Should the derelict despawn after clearing?** For framework: no — it stays. Content pass can add one-shot derelicts.
3. **Player death in dungeon?** Respawn at ship with 1 HP. Don't save dungeon state on death — the player can re-board (dungeon regenerates fresh from same seed).
4. **Does the combat engine need changes?** Minimally. We need a ground-combat variant of `init_combat_state` that reads ground weapon specs and sets shields=armor. The core loop (`run_combat`) should work unchanged if we feed it compatible data.
