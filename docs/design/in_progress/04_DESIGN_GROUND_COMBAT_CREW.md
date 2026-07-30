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
| **`menus/_loadout.py`** | Split-screen buy/sell modal for ship equipment. Ground armory terminal (`menus/_armory.py`) mirrors this pattern: left panel = items for sale, right panel = equipped slots, ENTER to buy or sell. |

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

### Phase 1: Layout-based dungeon + boarding (COMPLETED)

**What shipped:** Designer-authored `.layout` files parsed by `dungeon.py`, replacing the planned procedural generator. Layouts are text files with tile markers—editable in any text editor, no code changes needed for new ship interiors.

#### Step 1a: Derelict ship wiring

- [x] Add `is_boardable: bool = False` to `NpcShipSpec` in `data/npc_ships/__init__.py`
- [x] Add `derelict_scout` spec to `data/npc_ships/core.py` (faction="neutral", base_speed=0, detect_radius=0, is_boardable=True)
- [x] Add `EnemySpawn` for derelict near Earth in `data/solar_systems/sol.py` at (140, 43)
- [x] Add `elif blocker.npc_ship_id:` → `is_boardable` check in `__main__.py` occupied handler
- [x] Smoke test + commit

#### Step 1b: Layout files + parser

- [x] Create `dungeon.py` — `load_layout(layout_id, *, loot_budget=(0,0))` parsing `.layout` text files
- [x] Create `data/layouts/scout_a.layout` — 80-wide ship interior: cockpit, engine room, crew quarters, cargo hold, corridors, doors
- [x] Define tile set: `#`=wall, `.`=floor, `+`=door (blocking/openable), `{`/`}`=see-through wall cluster, `X`=breach/entry, `>`=exit
- [x] Wire bump → "Board?" dialog → `load_layout()` → breach animation → fog init → scene swap
- [x] Exit via `>` tile → restore space map + ship entity
- [x] Add room-based loot markers via number annotations in layout (e.g., `1`=crew_quarters loot, `2`=cargo loot)
- [x] Breach animation: `#` wall replaced with `X` breaching cut, explosion flash inward
- [x] Ship computer (`C`) terminal — restore power, boost sight radius to 20
- [x] Derelict procedural spawning via `derelict_spawn_chance` on `SolarSystem`
- [x] Distance-based auto-hail (comms warning) via `comms_trigger_viewport` / `comms_warning_range`
- [x] Smoke test + commit

#### Playtest checklist

- [x] Launch from Earth, find derelict `s` via coordinates, bump it → "Board?" dialog appears
- [x] Board → breach animation plays, then dungeon renders with `#` walls, `.` floors, `+` doors
- [x] Walk with h/j/k/l → walls block, floor is passable, doors block (player vision stops at closed doors)
- [x] Walk into `X` breach → exit back to space
- [x] Re-board → same layout (deterministic from file)
- [x] ESC from dungeon → save, quit, continue → back in dungeon at same position with fog preserved

#### What was deferred from Phase 1 design doc

- **Procedural dungeon generator** → replaced by authorable `.layout` files    
  *Rationale: designed rooms are more interesting than random carve, and text files are faster to iterate on than code.
- **Dungeon tile constants** → not added to `world.py`; tiles are defined inline in the layout parser
- **Fog integration with `render_world`** → handled by `dungeon.py`'s own render path, not `render_world`

---

### Phase 2: Fog of war + loot (COMPLETED)

**What shipped:** Full fog-of-war with per-tile `seen` tracking, reveal radius, dimmed explored tiles, RNG-based loot placement from layout room markers with a loot budget system.

- [x] Add `seen: list[list[bool | None]]` to dungeon `GameMap` as dynamic attribute (`game_map.seen`)
- [x] `init_fog(game_map)` — initialize all tiles as `None` (unseen)
- [x] `reveal_around(game_map, pos, radius)` — mark tiles within radius as `True` (visible)
- [x] Player move → `reveal_around` with `sight_radius` (default 6, boosted to 20 via ship computer)
- [x] Render: unseen = `' '` black, explored-out-of-sight = dim (30% brightness), visible = normal
- [x] Loot budget system: roll total value from `loot_budget=(min, max)` tuple on `NpcShipSpec`
- [x] Room loot markers in layout files (`1`=crew_quarters, `2`=cargo, etc.) with weighted good tables
- [x] Up to 4 RNG passes through rooms to spend budget, multiple loot per room possible
- [x] Loot entity: `%` glyph, gold FG, `loot_data={"good_id": ..., "quantity": ...}`
- [x] Walk into loot → `open_loot_pickup` (reused from `trade.py`, no changes)
- [x] Ship computer (`C`) → power restoration → `sight_radius = 20` + `reveal_around` at 20
- [x] See-through wall clusters (`{`/`}`) — all tiles in a cluster share reveal state
- [x] Derelict despawns once boarded (removed from space map + procedural spawn list)
- [x] Save/load dungeon state (map tiles, entities, fog, power status, loot)
- [x] Smoke test + commit

#### Playtest checklist

- [x] Board derelict → most of map is black (unseen)
- [x] Move around → tiles revealed in sight radius
- [x] Walk behind a door → area behind door stays black until door is open/player crosses threshold
- [x] Walk away from revealed area → tiles remain visible but dim (30% brightness)
- [x] Find loot `%` → bump → pickup modal shows good + quantity
- [x] Take loot → added to cargo (verify with `I` cargo menu)
- [x] Find `C` computer → bump → restore power → sight radius jumps to 20
- [x] Save + continue while on derelict → back in derelict with same fog/loot state
- [x] Exit → back in space, cargo has looted goods

---

### Phase 3: Ground gear + armory terminal (COMPLETED)

**What shipped:** Two new data catalogs (ground weapons, ground armor), armory terminal on city maps, 2 weapon slots + 5 armor slots, tabbed C screen equipment viewer.

#### Step 3a: Ground weapons catalog

- [x] Create `data/ground_weapons/__init__.py` with `GroundWeaponSpec` frozen dataclass
- [x] Fields: `id`, `name`, `damage_type` (melee/kinetic/energy/explosive), `damage`, `accuracy`, `ap_cost`, `hands` (1 or 2), `min_range`, `max_range`, `ammo_capacity` (-1=infinite), `ammo_per_shot`, `price`, `tech_level`
- [x] `data/ground_weapons/melee.py` — fists, combat_knife, stun_baton, survival_axe (all damage_type="melee", range=1, infinite ammo)
- [x] `data/ground_weapons/pistols.py` — laser_pistol (100 ammo, damage_type="energy"), kinetic_pistol (12 ammo, damage_type="kinetic")
- [x] `data/ground_weapons/rifles.py` — laser_rifle, kinetic_rifle, shotgun (2-handed, longer range)

#### Step 3b: Ground armor catalog

- [x] Create `data/ground_armor/__init__.py` with `GroundArmorSpec` frozen dataclass
- [x] Fields: `id`, `name`, `slot` (head/body/hands/legs/feet), `defense` (flat DR), `description`, `price`, `tech_level`
- [x] `data/ground_armor/vests.py` — light/heavy helmet (head), light/medium/heavy vest (body), tactical_gloves (hands), armour_pads/heavy_legs (legs), combat_boots (feet)

#### Step 3c: Armory terminal

- [x] Add `armory_terminal: bool = False` to `world.Entity`
- [x] Place `A` glyph terminal on every planet with a spaceport (south wall, left of mechanic)
- [x] Wire bump → armory_terminal → `menus/_armory.py`
- [x] Armory menu mirrors `menus/_loadout.py`: left panel = items for sale, right panel = equipped slots
- [x] ENTER on left = buy + auto-equip to first empty compatible slot (rejects if no slot free)
- [x] ENTER on right = sell equipped item for half price (frees the slot)
- [x] HUD shows `A  Armory` terminal indicator on city map

#### Step 3d: Ground equipment slots

- [x] `GameContext.equipped_ground_weapons: list[str]` — up to 2 weapon ids (empty list = fists)
- [x] `GameContext.equipped_ground_armor: dict[str, str]` — slot→id for head/body/hands/legs/feet
- [x] Save/load for both fields (backward-compatible `.get()` defaults)

#### Step 3e: C screen equipment tab

- [x] TAB cycles between Stats tab (unchanged) and Equipment tab
- [x] Equipment tab shows: Weapon Slot 1 / Weapon Slot 2, then Head/Body/Hands/Legs/Feet slots
- [x] Empty slots show "Fists" for weapon, "None" for armor

#### Step 3f: Game guide

- [x] `_GUIDE_GROUND_GEAR` section in `help.py` — armory terminal, weapon types, armour slots, buy/sell flow

#### Playtest checklist

- [x] Walk into `A` Armory terminal on city map → split-screen modal opens
- [x] Left panel shows weapons + armor with prices
- [x] ENTER on a weapon → bought + auto-equipped to first empty weapon slot
- [x] ENTER on a weapon when both slots full → "Both weapon slots are full" error
- [x] ENTER on armor → bought + equipped to its slot (head/body/hands/legs/feet)
- [x] TAB to right panel → shows equipped slots with sell prices
- [x] ENTER on a filled slot → item sold for half price, slot freed
- [x] Press C → TAB to Equipment tab → shows both weapon slots + all 5 armor slots
- [x] Save/continue → equipment persists correctly

---

### Phase 4: Ground stats — REFLEXES / STRENGTH / STAMINA (COMPLETED)

**What shipped:** `GroundStats` dataclass with REF/STR/STA, species/class bonuses via
`ground_bonus` fields, unified Stats tab on C screen (6 rows, 2 tabs), shared skill point
pool, HUD display of REF/STR/STA line below GUN/PIL/ENG, caps raised to 100 for all
skills, dev mode XP hotkey (Shift+X), and max level enforcement at 30.

#### Step 4a: GroundStats dataclass

- [x] `GroundStats(reflexes=10, strength=10, stamina=10)` dataclass in `character.py`
- [x] Base values all start at 10 ("average human" baseline)
- [x] `ground_stats: GroundStats` field on `GameContext` (default factory)
- [x] `GROUND_STAT_BASE = 10` module constant

#### Step 4b: Species/class integration

- [x] `ground_bonus` field on `Species` dataclass:

  | Species | REF | STR | STA | Rationale |
  |---------|-----|-----|-----|-----------|
  | Human   | +1  | +1  | +1  | Versatile baseline |
  | Martian | +2  | +0  | +1  | Low-grav agility |

- [x] `ground_bonus` field on `GameClass` dataclass:

  | Class          | REF | STR | STA | Rationale |
  |----------------|-----|-----|-----|-----------|
  | Pirate         | +0  | +3  | +0  | Brawler |
  | Merchant       | +0  | +0  | +3  | Survivability |
  | Bounty Hunter  | +1  | +1  | +1  | Balanced |

- [x] `starting_ground_stats(species_id, class_id) -> GroundStats` in `character.py`
- [x] Computed at character creation (initially missed — hotfixed: was defaulting to 10/10/10)
- [x] Save/load `ground_stats` in saveload.py

#### Step 4c: Unified Stats tab on C screen

- [x] Ground stats sit alongside ship skills on the single **Stats** tab (2 tabs total — no third tab)
- [x] Stats tab shows 6 rows: Gunnery, Piloting, Engineering, Reflexes, Strength, Stamina
- [x] TAB cycles between `[Stats]` and `[Equipment]` tabs
- [x] ENTER spends a skill point on whichever row is selected (all 6 share the point pool)
- [x] Cap for **all** skills raised to **100** (originally 30 for ground stats, changed during playtest)

#### Step 4d: Level-up + HUD integration

- [x] Skill points shared between ship skills and ground stats — one pool, player chooses
- [x] HUD shows REF/STR/STA on a second line below GUN/PIL/ENG in both city and space mode
- [x] All 4 render_hud call sites pass `ctx` (refactored to prevent future missed-site bugs)
- [x] Max player level enforced at 30 (`MAX_PLAYER_LEVEL = 30` in `xp.py`)
- [x] Dev mode Shift+X hotkey awards 200 XP (gated behind `SPACEHACK_DEV` env var)

#### Step 4e: Game guide

- [x] `_GUIDE_CHARACTER` section updated to mention all six skills and max level 30
- [x] `_GUIDE_GROUND_GEAR` section in `help.py` — armory terminal, weapons, armor, buy/sell

#### Bugfixes discovered during playtest

- [x] **`starting_ground_stats` never called during new game setup** — C screen showed flat 10/10/10
- [x] **Armory cursor jump** — buying armor from left panel clamped `_sel` against right panel length
- [x] **Message log missing from split-screen modals** — `render_split_frame` didn't render message log
- [x] **Animation HUD missing ground stats** — 3 call sites (city, auto-nav, jump) not passing `ground_stats`
- [x] **Ground stats cap at 30** — changed to 100 to match ship skills

#### Playtest checklist

- [x] New game: C screen has **2 tabs** — TAB cycles Stats / Equipment
- [x] Stats tab shows 6 rows: GUN/PIL/ENG/REF/STR/STA with species+class bonuses
- [x] Human starts at 11/11/11 (REF/STR/STA), Pirate at 11/13/10, Merchant at 11/10/13
- [x] Martian Bounty Hunter starts at 13/10/12
- [x] Spend skill point on REFLEXES → increases by 1, points decrease by 1
- [x] Ground stats show MAX at 100, ship skills show MAX at 100
- [x] Level stops at 30 — no more skill points
- [x] HUD shows `REF:11 STR:13 STA:10` below `GUN:30 PIL:30 ENG:30` in both city and space
- [x] Shift+X in dev mode awards 200 XP
- [x] Save/continue → ground stats preserved
- [x] Guide section explains all six skills + max level 30

---

### Phase 5: Ground combat — enemy catalog, sight detection, combat loop (COMPLETED)

**What shipped:** `GroundEnemySpec` catalog, layout enemy markers, sight-based combat
  detection, full turn-based ground combat loop, ground combat HUD, loot drops on kill,
  player death handling, ground HP save/load.

#### Step 1: Ground enemy catalog

- [x] Created `data/ground_enemies/__init__.py` with `GroundEnemySpec` frozen dataclass
- [x] Created `data/ground_enemies/core.py` with two enemies:
  - `derelict_scavenger` (char=`s`, HP=20, knife/pistol 50/50, REF=8, STR=12, STA=10, detect=4)
  - `derelict_guard` (char=`g`, HP=30, kinetic_pistol, REF=10, STR=10, STA=12, detect=5)

#### Step 2: Layout enemy markers

- [x] `ENEMY:` directive parser in `dungeon.py` — format: `ENEMY: s = derelict_scavenger@0.6`
- [x] Enemy glyphs `s` and `g` added to `_ENTITY_GLYPHS` and `_ENEMY_GLYPHS`
- [x] `scout_a.layout` updated: `s` in engine room, `g` in mess hall
- [x] Enemy entities created with `hostile=True` + `ground_enemy_id` during `load_layout()`

#### Step 3: Sight-based detection

- [x] `_detect_ground_combat(ctx, game_map, player_pos)` in `dungeon.py` — checks each hostile
  entity within `detect_radius` with LOS raycast through walkable tiles (walls/doors block)
- [x] Wired in `__main__.py` dungeon movement handler (triggers after fog reveal, before exit check)
- [x] First triggered entity → `run_ground_combat(console, ctx, enemy_entity, game_map)`

#### Step 4: Ground combat loop (`combat/_ground.py`)

- [x] AP pool: **4 per turn** (brisker than ship combat's 3)
- [x] Movement: vim keys (h/j/k/l/y/u/b/n), 1 AP per cell
- [x] Hit formula: `weapon.accuracy + reflexes*3 - target_reflexes*2` (clamped 5-95)
- [x] Damage formula: `weapon.damage + STR//4` (melee only) minus armor DR
- [x] Player HP: `20 + stamina * 2` (e.g. 40 HP at STA 10)
- [x] Armor DR: sum of all 5 equipped armor slots
- [x] No shields, no power pool — ammo-based ranged, infinite melee
- [x] Ground combat HUD on right panel: player HP, enemy HP/name/distance, AP, weapon
- [x] Enemy AI: simple attack-if-in-range melee/ranged each turn
- [x] Flee: 60% flat chance, returns to dungeon at current position

#### Step 5: Combat resolution + loot

- [x] Enemy death → remove entity, `_spawn_ground_loot()` drops `%` at death position (no explosion)
- [x] Loot pool from `GroundEnemySpec.loot_pool`, 1-2 items per kill, 1-2 qty each
- [x] XP reward on kill (`xp_reward` field)
- [x] Player death → `ctx.player_dead = True` → main loop returns to title
- [x] `ground_hp` / `ground_max_hp` on `GameContext`, serialized in save/load
- [x] HP persists across multiple combat encounters in one dungeon visit
- [x] `hostile: bool` and `ground_enemy_id: str` fields added to `world.Entity`

#### Playtest checklist

- [ ] `SPACEHACK_DEV=1` → launch from Earth → derelict at (150, 40)
- [ ] Board derelict → `s` and `g` glyphs visible in rooms (when revealed by fog)
- [ ] Walk toward enemy within detect_radius → combat auto-triggers on sight
- [ ] Combat HUD shows player HP and enemy name/HP
- [ ] Move with h/j/k/l during combat → AP consumed per step
- [ ] Fire equipped weapon → hit formula uses REFLEXES, damage uses STRENGTH for melee
- [ ] Kill enemy → no explosion, loot `%` at death spot
- [ ] Pick up loot → added to cargo
- [ ] Flee combat → back in dungeon at current position
- [ ] Player HP hits 0 → death screen, return to title
- [ ] Save/continue while on derelict → ground HP preserved

---

### Phase 6: Planet/station dungeon entrances (NEXT)

**Goal:** Walk into a building on a planet or station → enter a dungeon. Same layout system, different tile/room themes.

- [ ] Add `has_dungeon: bool = False` + `dungeon_layout_id: str = ""` to `PlanetSpec`
- [ ] Wire planet bump → EXPLORE option (already wired) → load layout for that planet
- [ ] Create 1-2 station-themed layouts (e.g., "abandoned research station")
- [ ] Planet dungeons don't consume the planet (can re-enter)
- [ ] Different loot tables for station vs ship interiors
- [ ] Smoke test + commit

---

### Phase 7: Save/load polish + guide (NEXT)

- [ ] Add `_GUIDE_GROUND_COMBAT` section to `help.py`
- [ ] Verify derelict despawn + no-respawn on save/load
- [ ] Verify ground stats reset on exit

### Phase 8: Crew, cybernetics, terminals (future content pass)

Full content expansion — deferred. See original sections below for the design.

## Contracts compliance (MANDATORY — see knowledge.md)

- [x] **Save/load:** GroundStats field added to `_ctx_to_dict` + `load_game` with `.get("ground_stats", ...)` fallback
- [x] **Game guide:** `_GUIDE_CHARACTER` section updated to mention all six skills and cap at 100; `_GUIDE_GROUND_GEAR` section documents armory terminal and equipment
- [x] **Module-level state:** No new globals
- [ ] **Ground combat guide:** Pending Phase 5

## Open questions

1. **Save/load strategy for dungeons?** Solved — dungeon map is fully serialized (tiles, fog, entities, loot, power status) via `_d() / load_game()`
2. **Should the derelict despawn after clearing?** Derelict despawns from space map once boarded (consumed).
3. **Player death in dungeon?** Not implemented yet — deferred to Phase 5 (ground combat).
4. **Does the combat engine need changes?** Not yet — ground combat uses the existing `combat._loop` with ground-weapon data. Minimal changes expected.
5. **Should skill points be shared between ship and ground?** Yes — implemented as a single shared pool across all 6 skills.
