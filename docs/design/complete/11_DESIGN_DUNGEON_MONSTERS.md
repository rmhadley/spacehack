# 11 — Dungeon Monsters: populating procedural dungeons

Status: **complete** · shipped 2026-08-07 — monster catalog, biome spawns, quest-site guardians, derelict parasites; all phases implemented and playtested.

## Overview

Procedural planet-surface dungeons (`dungeon.generate_dungeon`, BSP
room-and-corridor) are **completely empty** today — bare rooms and
corridors, no enemies, no loot. Derelict ship interiors (`.layout`
files) are the only ground-combat content, and they only ever spawn
`pirate_raider` / `pirate_rifleman` via `ENEMY:` directives.

This doc designs a **monster catalog + spawn population** for
procedural dungeons, so every explorable site (Mars signal, Mercury
caves, Barnard's B, Wolf 359, Procyon C ice caves) has threatening,
theme-appropriate inhabitants.

Monsters deliberately live **outside the faction reputation system**
— they are non-sentient creatures/drones. Killing one must never
touch player rep with pirates, militia, etc. Hostility is a hard
flag, not a reputation score.

## Current state (verified)

| System | Where | State |
|---|---|---|
| Procedural dungeon gen | `dungeon.generate_dungeon` | Rooms + corridors only. **No entities.** |
| Planet dungeon params | `data/planets/*.py` → `DungeonParams` | 5 planets use it (mars, mercury, procyon_c, barnards_b, wolf_b) |
| Derelict interiors | `dungeon.load_layout` + `ENEMY:` directives | Pirates via squad scatter — works, but only 2 NPC types |
| Ground enemy templates | `data/npc_chars/` → `NpcCharSpec` | `pirate_raider`, `pirate_rifleman` only |
| Hostility | `faction.get_attitude(rep)` | All hostility is rep-driven (enemy/disliked) |
| Ground combat trigger | `combat._encounter.detect_ground_combat` | Proximity (`detect_radius`) + LOS, squad assist radius 20 |
| Enemy AI (combat) | `combat/_ai_ground.py` | Move-toward player; fire in weapon range; A* per AP |
| Enemy AI (overworld) | `ground_npcs.py` | Hostile: patrol random walkable cell; neutral: wander |
| Combat resolution | `combat/_rules_ground.py` | Hit/dodge/damage via reflexes/strength/stamina/weapon |
| Loot on kill | `NpcCharSpec.loot_pool` / `loot_count` | Works (pirates drop trade goods) |
| XP on kill | `NpcCharSpec.xp_reward` | Works |
| Entity save/load | `saveload.py` | `npc_char_id` + `squad_id` serialized ✓ |
| Fog of war | `dungeon.init_fog` / `reveal_around` | Works |

## Philosophy alignment

| Guardrail | How this doc obeys it |
|---|---|
| **Data-first** | Monsters are `NpcCharSpec` entries in a new `data/npc_chars/monsters.py` — the auto-discovering registry (`_build_registry`) picks them up with **zero registry edits**. |
| **Faction purity** | New `always_hostile: bool` field on `NpcCharSpec` (default `False`). Monsters skip the rep lookup entirely. No `"monster"` pseudo-faction polluting `_ALL_FACTIONS`, rep decay, kill deltas, or species adjustments. |
| **Tables over conditionals** | Behavior dispatch (`hunter`/`ambusher`/`guard`) is a static dict of handler functions. Hostility check is one shared helper used by both `detect_ground_combat` and `ground_npcs._is_hostile`. |
| **SRP / ≤40 lines** | `populate_dungeon` = spawn placement only. Each behavior handler is small. `_flood_room` extraction dedupes the existing copy-paste closure. |
| **Composition** | Reuse `NpcCharSpec` + `GroundWeaponSpec` verbatim. No new classes, no inheritance. |
| **Save/load contract** | Monsters are ordinary `npc_char_id` entities → serialize free. **Populate at generation time, before `ctx.interiors` caching** so re-entry and Continue are deterministic. Sniff-test in Phase 1. |
| **Guide contract** | New "Dungeon Monsters" guide section in Phase 1; numbers updated as balance lands. |
| **Performance** | `hunter` reuses the existing (cached) A* patrol. `ambusher`/`guard` don't path at all out of combat — *cheaper* than today's pirates on the 120×90 Mars map. |

## Data model

### 1. `NpcCharSpec` gains two fields (`data/npc_chars/__init__.py`)

```python
@dataclass(frozen=True)
class NpcCharSpec:
    # ... existing fields ...
    always_hostile: bool = False   # True = ignore faction rep; always combat
    behavior: str = "hunter"       # "hunter" | "ambusher" | "guard"
```

- `always_hostile=True` → `detect_ground_combat` and
  `ground_npcs._is_hostile` treat the NPC as hostile without a rep
  lookup. No faction required (faction stays `""`).
- `behavior` only affects *out-of-combat* movement in `ground_npcs.py`
  and the combat chase in `_ai_ground.py`. In-combat fire logic is
  unchanged.

### 2. Monster catalog — `data/npc_chars/monsters.py`

Seven monsters across **three biomes × two attack modes** (plus the
derelict stowaway). All
`always_hostile=True`, `faction=""`, `xp_reward` ≈ 0.5× pirate value,
loot biased to scrap/exotic goods.

| id | name | char | biome | behavior | attack | hp | notes |
|---|---|---|---|---|---|---|---|
| `rock_scavenger` | Rock Scavenger | `s` | desert/rock | hunter | melee (claws dmg 2) | 14 | swarmer — 3-5 per squad, low HP |
| `dust_prowler` | Dust Prowler | `p` | desert/rock | hunter | melee (dmg 4) | 22 | fast, strong single/duo hunter |
| `sentry_drone` | Sentry Drone | `d` | ruins/signal | guard | ranged (drone_laser rng 6) | 18 | holds position, fires on sight |
| `assault_drone` | Assault Drone | `D` | ruins/signal | guard | melee (dmg 5) | 34 | armored bruiser, slow |
| `ice_worm` | Ice Worm | `w` | ice | ambusher | melee (dmg 6) | 26 | waits in floor, bursts out on approach |
| `frost_spitter` | Frost Spitter | `f` | ice | hunter | ranged (frost bolt rng 5) | 20 | ranged harasser, 2-3 per squad |
| `hull_parasite` | Hull Parasite | `m` | **derelicts** | ambusher | melee (dmg 3) | 16 | rare stowaway — ~15% chance per derelict, 2-4 per infestation |

Monster weapons: 4 new `GroundWeaponSpec` entries in
`data/ground_weapons/monsters.py` (`monster_claws`, `drone_laser`,
`frost_bolt`, `parasite_mandibles`) — melee/energy projectiles,
tech_level 1-2, `price=0`.

**Shop-leak guard (verified):** `menus/_armory.py` lists *every*
registered weapon from `list_ground_weapons()` with **no filtering**
— auto-discovery means a new weapon module WOULD appear in the
armory. Add `shop_available: bool = True` to `GroundWeaponSpec`;
monster weapons set `False`; the armory's left panel filters
`if w.shop_available`. This is a mandatory part of Phase 1.

### 3. `DungeonParams` gains spawn fields (`dungeon.py`)

```python
@dataclass(frozen=True)
class DungeonParams:
    # ... existing fields ...
    monster_pool: tuple[str, ...] = ()     # npc_char ids allowed here
    monster_density: float = 0.0           # avg monsters per 100 floor cells
```

Per-planet config in `data/planets/*.py`:

| Planet | pool | density | tier | rationale |
|---|---|---|---|---|
| mars (signal) | `rock_scavenger`, `dust_prowler`, `sentry_drone`, `assault_drone` | 1.2 | 1 | ruins + fauna; prologue site stays light |
| mercury (caves) | `rock_scavenger`, `dust_prowler` | 1.5 | 1 | wild scorched caves |
| barnards_b | `rock_scavenger`, `dust_prowler` | 1.5 | 2 | hostile world (bar chain) |
| wolf_b | `frost_spitter`, `ice_worm` | 1.5 | 3 | cold claim site (merchant chain) — heaviest in act 0 |
| procyon_c (ice caves) | `ice_worm`, `frost_spitter` | 1.6 | 2 | lab chain delve |

Density × floor-cell count → target monster count, then scaled by
the planet's tier (`tech_level` + `mission_tier` — both fields already
exist on every `PlanetSpec`): tier 2 sites get a stronger pool mix +
higher effective density than tier 1 (Phase 2 implements the scaling
formula; Phase 1 lands the base config above).

## Domain changes

1. **`dungeon.py`** — extract the `_flood_room` closure (currently
   nested inside `load_layout`) to a module-level helper; add
   `populate_dungeon(game_map, params)` that scatters monster squads
   into rooms via flood-fill (mirrors the layout enemy scatter), never
   spawning on the player spawn, quest-cache entities, or the EXIT.
2. **`__main__.py` EXPLORE handler** — after `generate_dungeon`,
   call `populate_dungeon` **before** `ctx.interiors[_surface_key] = _dungeon_map`
   so the population is cached/saved with the map.
3. **`data/npc_chars/__init__.py`** — add `always_hostile` +
   `behavior` fields (defaults preserve pirates exactly).
4. **`combat/_encounter.py` + `ground_npcs.py`** — shared
   `is_hostile_to_player(ctx, spec)` helper: `always_hostile` short-circuits
   the rep lookup. Both call sites use it.
5. **`combat/_encounter.py` kill-rep path** — verify `_COMBAT_KILL_DELTAS`
   lookup uses `.get()` (monsters have no faction → zero rep delta).
6. **`ground_npcs.py`** — behavior dispatch table: hunter = existing
   patrol; ambusher = stand still (no pathing); guard = stand still
   (or ≤1-cell jitter). In-combat, `_ai_ground.py` keeps the chase
   logic; guard gets a leash (returns to post past ~10 cells).
7. **Derelicts** — `ENEMY:` directives already accept *any*
   `npc_char_id` (the parser stores `enemy_id` and sets
   `npc_char_id=_eid`). No engine change: add `hull_parasite` to the
   catalog + a low-chance line (e.g. `ENEMY: m = hull_parasite@0.15#2-4`)
   in `scout_a.layout` / `freightliner_a.layout`.
8. **`data/ground_weapons/__init__.py` + `menus/_armory.py`** — add
   `shop_available` to `GroundWeaponSpec`; filter the armory left panel
   so monster weapons never stock.
9. **`help.py`** — new "Dungeon Monsters" section: monster types,
   behaviors (ambush, guard, swarm), and the note that monsters ignore
   faction reputation.
10. **`combat/_animations.py`** — nothing (damage popups already generic).

## Phased implementation plan

### Phase 1 — Foundation: hostile flag, populate, 3 monsters

- [x] Add `always_hostile` + `behavior` (+ `squad_size`) fields to
  `NpcCharSpec`; `shop_available` to `GroundWeaponSpec` (armory guard)
- [x] Extract `_room_cells` + `_scatter_squad` to module-level; add
  `populate_dungeon(game_map, params, spawn_pos)` (spawn zone / EXIT /
  occupied exclusions; budget-skip never truncates a squad below its min)
- [x] Add 3 starter monsters: `rock_scavenger`, `sentry_drone`, `ice_worm`
  + 3 ground weapons (melee/ranged drone/ranged spit) in
  `data/ground_weapons/monsters.py` — all `shop_available=False`
- [x] Wire `populate_dungeon` into the EXPLORE handler (pre-cache, AFTER
  quest door/cache placement so squads never overlap them)
- [x] `always_hostile` short-circuit via shared `faction.spec_is_hostile`
  used by `detect_ground_combat` + `ground_npcs._is_hostile`; zero rep
  change on monster kills (faction `""` → `_COMBAT_KILL_DELTAS.get` no-op)
- [x] Guard/ambusher hold-still out of combat (landed early in Phase 1
  via `ground_npcs._spec_behavior` — ~5 lines)
- [x] Default pools on mars + mercury only (prototype sites)
- [x] Guide section; smoke test; verify script (16 monsters on Mars cap,
  13 on Mercury, packs honor `squad_size`, hostile at allied rep)

**PLAYTEST (Phase 1)**
1. New game → Mars signal site → monsters present in rooms, fog hides them
2. Fight: melee scavengers swarm, sentry drone holds ground + shoots
3. Kill a monster → loot + XP, **zero faction rep change** in log
4. Save/quit → Continue → exact same monsters alive/dead at same spots
5. Leave/re-enter dungeon → no monster duplication or respawn

### Phase 2 — Full catalog, behaviors, biomes

- [x] All 6 monsters + all weapons; per-planet pools (table above)
- [x] Ambusher: no out-of-combat movement (landed early in Phase 1);
  joins combat when detected ✓
- [x] Guard: no out-of-combat movement (landed early in Phase 1);
  in-combat **leash** — `guard_post` stamped at `_rules_ground.init`,
  `_ai_ground` disengages past 8 cells and returns to post ✓
- [x] Difficulty scaling: **planet-tier driven** (user-confirmed) —
  `populate_dungeon(..., tier=mission_tier)`; per-tier (density mult,
  cap) table: t1 (1.0, 16), t2 (1.4, 22), t3 (1.8, 28). Verified
  counts: Mars 16, Mercury 13, Barnard's B 18, Procyon C 19, Wolf 22
- [x] Balance pass: stats tuned relative to pirates (prowler 4 dmg
  melee, assault drone 34 hp bruiser, spitter ranged 4); playtest
  verdict still pending

**PLAYTEST (Phase 2)**
1. Each dungeon biome → correct monster mix (no ice worms on Mercury)
2. Ice worm ambushes only when approached; drones hold rooms
3. Procyon C feels harder than Mars signal; early game not brutal
4. Performance: 120×90 Mars map movement stays smooth (ambushers/guards
   don't path)

### Phase 3 — Quest interplay + polish

- [x] Quest-site guardians: every quest site is guarded via
  `prepare_mars_surface` + `prepare_delve_site` (shared
  `_spawn_squad_near` helper, refactored from the door-ambush copy):
  Mars door = sentry drone ×1; Mercury cache = assault drone ×1;
  Barnard's B = assault drone ×1; Wolf 359 = 2 drones; Procyon C =
  ice-worm pack ×2. `DungeonParams` gained `cache_guardian_pool` +
  `cache_guardian_count` (data-first, per-planet). Placed at
  generation time → persists via interior cache (save/load safe)
- [x] Monster loot tuning — confirmed all drops use trade goods
  (`research_data`, `scrap_metal`, `electronics`, `machine_parts`,
  `ship_components`); XP ≈ 0.5× pirates (10–30 vs 20–35)
- [x] XP/rep balance + guide numbers final — guide updated with cache
  guardians + derelict parasite; reveal-line flavor matches
- [x] Derelict ships: `hull_parasite` stowaway landed in both layouts
  (`ENEMY: m = hull_parasite@0.15#2-4`) with a hardcoded-glyph fix —
  the parser now treats ANY glyph with an `ENEMY:` directive as an
  enemy marker, so future enemy types need no glyph-set entry.
  Verified: ~15% infested, 2-4 per wreck, one squad

**PLAYTEST (Phase 3)**
1. [x] Full act-0 branch playthrough (bar → merchant → militia → lab)
   with monsters active — quest chains still completable, caches
   reachable. Covered by the doc-12 Phase 3 playtest (chains + fights
   felt good with monsters live in every dungeon).
2. [x] Kill-a-monster pace vs. ammo/AP economy feels fair — user
   verdict (2026-08-07): "feels good for now" — tune per-planet
   stats/density as future playtests show issues
3. [x] Guide matches implementation exactly — verified headlessly
   against the monster catalog + behavior dispatch.

## Acceptance criteria

- [x] Every procedural dungeon with a non-empty `monster_pool` has
  monsters on first explore; derelicts keep pirate squads plus the
  rare `hull_parasite` roll
  - Headless sweep (2026-08-06): Mars 16, Mercury 15, Barnard's B 22,
    Wolf 359 b 24, Procyon C 20 — all within tier caps, never on the
    spawn cell. 60-seed derelict sweep: scout_a 17% infested,
    freightliner_a 10% (target ~15%), parasite squads of 2-4, pirate
    squads always present alongside.
- [x] Monsters are always hostile regardless of faction reputation;
  killing them changes no rep score
  - `spec_is_hostile` returns True for all 7 monsters at rep +100 with
    every faction; pirate control returns False at +100. Ground kill
    path (`_rules_ground.on_kill`) awards XP only — no `modify_rep`
    call anywhere in the ground path.
- [x] Save → quit → Continue reproduces monster state exactly (no dupes,
  no resets) — sniff test passes
  - 16 monsters on Mars: `_dungeon_to_dict` → `_dungeon_from_dict`
    roundtrip identical (id, position, squad_id, hp).
- [x] Ambusher/guard/hunter behaviors match their descriptions
  - ice_worm/hull_parasite = ambusher, sentry_drone = guard,
    rock_scavenger = hunter; `move_ground_npcs` skips guard/ambusher
    movement (they hold still out of combat).
- [x] Guide section accurate; smoke test green
  - "Dungeon Monsters" section matches implementation: hunters patrol,
    guards hold + fire at range, ambushers burst out, monsters ignore
    faction rep, derelict parasite roll. `tools/smoke.py` green.
- [x] No movement/perf regression on the 120×90 Mars map
  - `move_ground_npcs` 4.5 ms/tick (16 entities incl. non-pathing
    guards/ambushers), `reveal_around` 0.88 ms/call — both smooth.

## Decisions (user-approved, 2026-08-06)

1. **Lore:** fauna + security drones mix, themed per biome ✓
2. **Quest dungeons:** populate all of them — Mars prologue included
   (light pool so it stays a gentle first-combat) ✓
3. **Derelicts:** keep pirates primary, but add a **rare** alien
   predator/parasite (`hull_parasite`, ~15% per wreck) ✓
4. **Difficulty:** scale off the **planet tier level** (`tech_level` +
   `mission_tier`, both already on `PlanetSpec`) ✓

## Open questions (resolved)

1. **Monster loot flavor** — RESOLVED: pirate-style trade goods
   (`scrap_metal`, `electronics`, `research_data`, `machine_parts`,
   `ship_components`). No "monster parts" line — reused the existing
   goods so drops feed straight into the existing trade economy.
2. **Ambusher reveal** — RESOLVED: the burst message lands at combat
   start (one colored log line per ambusher — "Ice Worm bursts out of
   hiding!"). The pre-telegraph "floor shifts" step was dropped: the
   worm's first hit already carries the surprise, and a telegraph
   would tip off the player one step early for little gain.

## Pre-implementation audit

### Existing code to extend/reuse

- `NpcCharSpec` (`data/npc_chars/__init__.py`) — the whole monster
  template. New fields default to pirate-compatible values.
- `_build_registry()` auto-discovery — new `monsters.py` module is
  picked up with zero registry edits.
- `dungeon.load_layout` enemy-scatter pattern — the flood-fill +
  squad spawn template `populate_dungeon` will mirror.
- `combat/_encounter.detect_ground_combat` — proximity+LOS trigger,
  squad assist radius 20. Monsters slot in via `always_hostile`.
- `combat/_ai_ground.py` — move-toward + fire per AP; melee monsters
  "fire" at range 1 (existing `combat_knife` pattern).
- `ground_npcs.py` — squad patrol/wander; behavior dispatch extends it.
- `world.Entity(npc_char_id=..., squad_id=...)` — spawn flag pattern.
- `data/ground_weapons/melee.py` — stat block pattern for monster
  weapons (frozen `GroundWeaponSpec`).
- `faction._COMBAT_KILL_DELTAS` — must be a `.get()` lookup so
  factionless monsters produce zero rep delta (verify call site).
- `dungeon._flood_room` (nested closure) — extraction target.

### Duplication hotspots (predicted)

1. **Room flood-fill** — `_flood_room` is a closure inside
   `load_layout`; `populate_dungeon` needs the same BFS. → Extract to
   module-level `_room_cells(game_map, ox, oy)`, pass the occupied set.
2. **Hostility check** — the rep+attitude snippet in
   `detect_ground_combat` and `ground_npcs._is_hostile` is nearly
   identical today. → Single `spec_is_hostile(ctx, spec)` helper in
   `faction.py` or `combat/_encounter.py`, both call it.
3. **Squad scatter** — the "pick N distinct cells from a room, set
   `npc_char_id` + `squad_id`" block exists in `load_layout` and will
   be re-created for monsters. → One `_scatter_squad(game_map, cells,
   spec, squad_id, count, fg)` helper shared by both.
4. **Armory weapon leak (verified)** — `list_ground_weapons()`
   auto-discovers every module's `WARES`, and the armory lists them
   unfiltered. Monster weapons would stock in shops. → `shop_available`
   flag + armory filter; also keep monster weapons in their own module
   so `list_ground_weapons()` output stays greppable.

### DRY strategy

- Module-level `_room_cells` + `_scatter_squad` in `dungeon.py`;
  `load_layout` refactored to call them (behavior-preserving).
- `spec_is_hostile` in `faction.py` (it already owns attitude logic);
  `always_hostile` returns `True` before any rep math.
- Behavior dispatch table in `ground_npcs.py` keyed by
  `spec.behavior`, falling back to the existing hunter path.

## Design doc lifecycle

- [x] Phase 0: doc approved by user
- [x] Phase 1 → implementation + playtest (passed)
- [x] Phase 2 → implementation + playtest (passed)
- [x] Phase 3 → implementation + playtest (act-0 chains + guide verified)
- [x] Moved to `complete/` (2026-08-07)
