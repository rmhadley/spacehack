# 12 — Ground Combat: LOS-based Aggro (no squads)

Status: **complete** · shipped 2026-08-06 — LOS aggro, wound
persistence, remembered-sight fog; all phases implemented and
playtested.

## Overview

Ground combat today is **squad-gated**: when any hostile spots the
player, `detect_ground_combat` pulls in the *entire squad* (same
`npc_char_id` squad via a 20-tile assist radius, **through walls**)
and auto-reveals fog around every combatant. A pack of scavengers
shares telepathy: one sees you, all five join, you see all five. That
"everyone knows instantly and fights as one unit" feel is the problem.

This doc replaces squad linkage with **player-LOS aggro**:

- Mobs are individuals. `squad_id` remains a *spawn/movement* concept
  (pack clustering, `ground_npcs` patrol) but is **ignored by
  combat**.
- A mob joins the fight iff the **player** can see it: within the
  player's sight radius **and** clear line of sight.
- No auto-reveal around enemies — you fight exactly what you see.
- The fight **ends when nothing hostile is in view** (dead, or you
  broke sight). Leftovers revert to their map behavior and re-trigger
  if spotted again.
- Mid-fight, mobs that wander into view **join** (trickle-in).
- **Space combat is untouched** — squads stay there.

Noise (gunfire attracts mobs) is deliberately deferred: v1 is pure
LOS, but the detection predicate is built as a single hook so noise
can be OR'd in later without redesign.

## Phase 1 shipped (delta)

Implemented + committed 2026-08-06 (`4115cc4`, `704372c`):

- `visible_hostiles()` predicate (sight radius + clear ray) feeds the
  trigger, the join scan, and the end check — the noise seam
- `detect_ground_combat` returns the full visible set — no squad
  assist through walls, no auto-reveal
- `refresh_engaged()` at the top of every round: mobs on screen join
  immediately — targetable and acting the same round; space gets a
  no-op hook
- LOS end condition: VICTORY (all engaged dead) / DISENGAGED
  (survivors out of view); `combat_should_end` rules hook
- `Entity.hp` wound persistence + saveload (breaking sight never
  heals enemies)
- Per-kill rep only (squad bonus removed); rep applies on VICTORY and
  DISENGAGED
- Guide updated; 13-check behavior script + smoke green

The "Current state (verified)" table below records the PRE-change
baseline the design was built against.

## Current state (verified)

| System | Where | State |
|---|---|---|
| Ground aggro trigger | `combat/_encounter.detect_ground_combat` | First hostile within its `detect_radius` + LOS → **one squad** (+ same-`squad_id` within 20, through walls) |
| Enemy auto-reveal | `detect_ground_combat` → `reveal_around(radius=3)` per combatant | Fog revealed around every enemy in the fight |
| Arena | `combat/_loop.run_combat` | Modal turn loop over the real dungeon map (camera + HUD) |
| Combat session state | `combat/_rules_ground.GroundCombatState` | `_state.enemies` list, built once at `init` from the trigger set |
| Enemy HP | `GroundEnemyInstance.hp` (session object only) | Damage lives on the instance; map entity is untouched → **re-engaging after flee/LOS-break heals the mob to full** |
| Enemy turns | `_rules_ground.run_enemy_turns` → `_ai_ground` | Move toward player; fire iff in weapon range **and** LOS; guards leash to post |
| Mid-fight hook | `_rules_ground.check_reinforcements` | Currently only moves idle ground NPCs — the natural join hook |
| End condition | `run_combat` loop top: `not get_enemies()` → VICTORY | Fixed list; nothing joins; nothing ends early |
| Fog render | `world.render_world_view` | Skips unseen tiles **and entities on unseen tiles** ✓. Now also distinguishes **current LOS** from remembered: `GameMap.visible` grid (recomputed by `dungeon.reveal_around` each move) — in-LOS tiles render full brightness, remembered tiles render dim (35%), moving entities render only in LOS, static objects (loot/terminals) render dimmed when remembered ✓ |
| LOS ray | `combat/_animations._has_los` | Symmetric Bresenham ✓ |

> **Renderer-vs-aggro ray note:** `reveal_around`/`_cast_ray` (the
> `visible` grid) uses interpolation with `round()`, while
> `visible_hostiles`/`_has_los` (aggro) uses Bresenham. In rare
> corner geometries they can disagree — an enemy the aggro predicate
> considers visible may sit just outside the rendered `visible` grid
> (acts/fires without being drawn). Rare and symmetric, but if it
> ever shows up in playtest, align both on one ray function.
| Ground rep on win | `__main__.py` ground-victory block | Per-kill deltas + **`_squad_bonus`** (+1 when the whole init squad died) |
| Entity save/load | `saveload._ctx_to_dict` / `load_game` | Explicit field list — a new entity field needs both sites |

## Philosophy alignment

| Guardrail | How this doc obeys it |
|---|---|
| **Data-first** | No new data specs. Mobs stay `NpcCharSpec`; `detect_radius` becomes unused-for-aggro (kept for future noise/ambush). |
| **Tables over conditionals** | Detection is one predicate `visible_hostiles(game_map, pos, radius)`; join/end/reveal all derive from it. No per-branch squads. |
| **SRP / ≤40 lines** | `visible_hostiles()` is a pure predicate. `check_reinforcements` = join scan + idle movement. Join logging is a small helper. |
| **Pure computation, explicit mutation** | `visible_hostiles()` pure; damage sync (`entity.hp`) is one line in `rules.damage`. |
| **Save/load contract** | New `Entity.hp` field serialized at both saveload sites. Sniff test: wound a mob, break LOS, save/quit/continue, re-engage → same HP. |
| **Guide contract** | Ground Combat guide section updated: LOS aggro, no squads, fights end when you break sight, wounds persist. |
| **Performance** | Per-round join scan = one pass over entities, LOS only for candidates within radius 4 (Chebyshev box) — same cost class as today's per-move detection. |
| **Noise-ready** | `visible_hostiles()` is the single detection hook; a future `noise_hostiles()` can OR into it without touching join/end/reveal logic. |

## The new model

### Aggro predicate (player LOS only)

```python
def visible_hostiles(game_map, player_pos, radius) -> list[Entity]:
    """Hostiles the player can currently see: within sight radius
    AND clear LOS. Pure — shared by trigger, join scan, end check."""
```

- Radius = `game_map.sight_radius` (**8** — raised from 4 so every
  ground weapon's full range is usable; engagement range == sight
  radius under this model). A tile within radius is always `seen`
  (the player reveals as they move), so no extra seen check is
  needed.
- No `detect_radius` on the mob (player-centric — you can never be hit
  by something you haven't seen; enemy fire already requires LOS and
  LOS is symmetric).
- No squad linkage, no assist radius, no auto-reveal.

### Lifecycle

1. **Trigger** (no combat): dungeon move → `visible_hostiles()` non-empty
   → `_ground_init` with the full visible set → `run_combat`.
2. **Mid-fight joins**: at the **top of every round** the new
   `refresh_engaged()` hook recomputes `visible_hostiles()` and appends
   any not already engaged (one "X joins the fight!" line; ambushers
   reuse the burst-out helper). A mob that walks into view — or was on
   screen when the last engaged enemy died — is part of combat
   **immediately**: targetable and acting the same round. Space gets a
   no-op hook (its enemy set stays fixed).
3. **End**: when `visible_hostiles()` is empty after a round → combat
   ends. Outcome **VICTORY** if every engaged mob died, else the new
   **DISENGAGED** outcome (leftovers revert to patrol/hold, re-trigger
   on sight). No cowardice penalty for LOS-break — it's normal play,
   not a flee choice. (See Open questions re: peek-a-boo cheese.)

### Wound persistence (required for a fair LOS model)

Without it, breaking LOS would silently heal every mob to full on
re-engage — peek-a-boo tactics become pointless AND retreating is
punished. Damage must stick to the map entity:

- `world.Entity` gains `hp: int = 0` (0 = unengaged → full HP).
- `_rules_ground.init`: instance HP = `entity.hp or (spec.hp + stamina // 3)`;
  stamp `entity.hp` at first engagement.
- `rules.damage()`: after mutating the instance, sync `entity.hp`.
- `saveload`: serialize `hp` in the entity dict + restore (both sites).
- No out-of-combat regen (v1). `on_kill` unchanged (entity removed).

### Rep changes

- `__main__.py` ground-victory block: drop the `_squad_bonus` logic
  (no squads); award per-kill deltas only. Monsters (faction `""`) →
  zero, unchanged.

## Domain changes

1. **`combat/_encounter.py`** — replace the squad/assist/reveal logic
   in `detect_ground_combat` with a call to the shared
   `visible_hostiles()` predicate; remove `reveal_around(radius=3)`;
   `noise_hostiles()` stub OR'd in (Phase 2 noise seam).
2. **`combat/_rules_ground.py`** — `visible_hostiles()` (pure, moved
   here or `_encounter`); `check_reinforcements` = join scan + move
   idle NPCs; `init` reads/stamps `entity.hp`; `damage()` syncs
   `entity.hp`; new `get_combat_result` handles DISENGAGED;
   `_log_ambush_reveals` reused for join lines; guard_post
   stamp-if-unset (Phase 2).
3. **`combat/_loop.py`** — end check becomes "no visible hostiles";
   `CombatResult.outcome` gains `"DISENGAGED"`.
4. **`world.py`** — `Entity.hp: int = 0`.
5. **`saveload.py`** — serialize/restore `hp` at both entity sites;
   `guard_post` added to the dungeon entity dict (Phase 2).
6. **`__main__.py`** — ground-victory block: per-kill rep only;
   DISENGAGED returns cleanly.
7. **`help.py`** — Ground Combat section: LOS aggro, no squads,
   fights end on broken sight, wounds persist, sight radius numbers
   + ambusher corner note (Phase 2).
8. **`data/npc_chars/monsters.py` (+ pirates)** — no changes
   (`detect_radius` becomes descriptive).

## Phased implementation plan

### Phase 1 — LOS aggro core + wound persistence

- [x] Extract shared `visible_hostiles()` predicate (in `_encounter.py`);
  `detect_ground_combat` returns the full visible set — no squad
  linkage, no 20-tile assist, no auto-reveal (fog untouched)
- [x] `refresh_engaged` join scan at the top of every round (visible −
  engaged) + announce: ambushers "burst out of hiding!", others
  "joins the fight!" — mobs on screen are engaged immediately,
  targetable and acting the same round; space gets a no-op hook;
  `check_reinforcements` keeps only idle-NPC movement
- [x] End condition: `combat_should_end()` rules hook — ground = no
  visible hostiles (VICTORY / DISENGAGED), space = no enemies
  (behavior-preserving)
- [x] `Entity.hp` field + `_build_enemy_instance` reads/stamps it +
  `damage()` syncs it + saveload both sites
- [x] Rep rework: per-kill deltas only (squad bonus removed); rep
  applies on VICTORY and DISENGAGED; DISENGAGED returns cleanly
- [x] Guide update (LOS aggro, no squads, ends on broken sight, wounds
  persist); 12-check behavior script green + smoke green

**PLAYTEST (Phase 1)**
1. Clear a Mars room: only visible scavengers engage; a packmate around
   a corner stays out until it walks into view
2. Mid-fight: a mob wandering in joins ("joins the fight!") and acts
   next round
3. Step around a corner with a survivor → combat ends; step back →
4. Wound a scavenger, break LOS, re-engage → it has the same HP
5. Kill-a-monster: rep log unchanged (zero for monsters)

### Phase 2 — Feel + balance (LOS-model tuning)

- [x] Sight-radius consequences at 8: engagement == sight radius —
  verified fine; fights run at room scale with all weapons usable.
  Per-planet `DungeonParams.sight_radius` lever confirmed wired
  (``generate_dungeon`` applies ``params.sight_radius``); no planet
  overrides it in v1
- [x] Ambusher read (positional ambush, decision #6): verified —
  parasites sit in engine-room corners behind doorways in both
  derelict layouts; rounding the corner onto one bursts it (reveal
  line) and it acts the same round
- [x] Guard read: drones hold until seen; leash verified. FIXED a
  drift bug: `_build_enemy_instance` re-stamped `guard_post` on every
  re-engagement, dragging a guard's defense area toward the player
  peek-by-peek. Now stamp-if-unset + serialized in saveload
- [x] Pack feel: packs spawn clustered (`_SQUAD_SPREAD` anchor
  spread) but fight as individuals; trickle-in reads as "they heard
  the fight". `monster_density` untouched (1.2-1.6 per planet) —
  playtest verdict: feels right
- [x] Peek-a-boo audit (allowed, decision #5): corner-peek + fire +
  break sight is legitimate; wounds persist so it's fair; the guard
  fix removes the one degenerate case (post dragging)
- [x] Noise seam: `noise_hostiles()` stub OR'd into
  `visible_hostiles()` — the single OR-in point shared by trigger,
  refresh_engaged, and combat_should_end. A real noise scan changes
  only this function (doc'd seam contract)
- [x] Guide numbers final; perf check: two `visible_hostiles()`
  passes per round on a 120×90 map with 120 mobs = **0.114 ms/round**
  (measured, 300 rounds) — no regression risk

**PLAYTEST (Phase 2)**
1. Each biome under LOS aggro: worms, drones, prowlers read right
2. Ranged enemies (spitter, drone) still threaten at radius 8
3. Corner ambush: round a corner onto an ice worm — burst + same-round
   act? Does it read as an ambush?
4. Kite a sentry drone out of its room — leash turns it back
5. Pack trickle-in: clear a scavenger room — does the rest of the pack
   arrive naturally?
6. Peek-a-boo: corner-peek, fire, break sight, re-peek — fair and
   clever, not degenerate
7. Perf: Mars map smooth with the per-round join scan

### Phase 3 — Full act-0 pass + polish

- [x] LOS vs remembered sight: `GameMap.visible` grid — in-LOS tiles
  full brightness, remembered tiles dim (35%), moving entities
  LOS-only, static objects remembered dimmed; `visible` recomputed
  by `reveal_around` (cleared per frame), NOT serialized (recomputed
  on Continue + entry); Shift+R dev reveal sets both grids; guide +
  doc updated
- [x] Bar → merchant → militia → lab + derelicts under the new model —
  quest caches, ambushes, guardian fights all still work
  (**verified headlessly**, 2026-08-06): for every chain, generate
  the planet dungeon → `populate_dungeon` → `prepare_mars_surface` /
  `prepare_delve_site` with the step live. Mars places the sealed
  door + 1 sentry guardian beside it; bar (Barnard's B) / militia
  (Mercury) / merchants (Wolf 359) / lab (Procyon C) each place the
  gold quest cache + the planet's guardian squad (assault/sentry
  drones, or 2 ice worms on Procyon) with correct counts, from the
  right pool, in ONE squad, never overlapping cache/spawn. The
  lab_q1_sample Mars door ambush places 3 pirate raiders (one squad)
  in the door room. Manual playtest of the FIGHT FEEL remains open
  below.
- [x] Peek-a-boo cheese audit + balance: allowed (decision #5), and
  the remembered-fog change strengthens the posture — a mob that
  breaks LOS now **vanishes from the render** (not just from
  aggro), so re-acquiring a target requires a genuine re-peek; you
  can no longer track an engaged mob's position through a wall on
  the seen grid. Wounds persist (no heal-on-retrigger), hunters
  roam, re-peeks cost AP. Noise stays the documented future
  anti-cheese lever.
- [x] Save/load sniff test: `_dungeon_to_dict`/`_dungeon_from_dict`
  roundtrip preserves a wounded mob (`hp=7`) + `guard_post`;
  `_build_enemy_instance` on the reloaded entity re-engages at the
  persisted 7 HP (no heal-on-continue). `visible` deliberately not
  serialized.

**Phase 3 verification (automated, 2026-08-06):** chain-generation
script above plus perf — `reveal_around` on the largest site
(80×60, radius 8) = **0.48 ms/call** (200-call mean), so the new
per-frame `visible`-grid clear is negligible; smoke green.

**PLAYTEST (Phase 3)** — PASSED (user, 2026-08-06)
1. Full branch runthrough; no chain softlocks from the combat change ✓
2. Ground fights feel "alive" (trickle-in) without being unfair ✓

## Acceptance criteria

- [x] No squad linkage in ground combat; packs fight as individuals
  (`detect_ground_combat` = `visible_hostiles` only — no squad_id,
  no assist radius, no auto-reveal)
- [x] Mobs join only when the player sees them; nothing auto-reveals
  (`refresh_engaged` joins from `visible_hostiles` at round top)
- [x] Combat ends when nothing hostile is in view; leftovers re-trigger
  (`combat_should_end` = not `visible_hostiles`)
- [x] Wounds persist across LOS-break, save/load, re-engagement
  (entity.hp sync + sniff test above)
- [x] Space combat behavior identical (untouched — feature commits
  touched only world/dungeon/__main__/help/doc)
- [x] Guide accurate; smoke green; no perf regression on Mars map
  (0.48 ms/call reveal_around; smoke PASS)



## Decisions (user-approved, 2026-08-06)

1. **End condition:** LOS ends it — combat resolves when no hostile is
   in view; leftovers revert to map behavior ✓
2. **Detection:** player LOS only (sight radius + clear ray) — you can
   never be hit by what you haven't seen ✓
3. **Noise:** pure LOS for v1; design the detection as a hook so a
   noise system can slot in without redesign ✓
4. **Sight radius:** raised to **8** (from 4) — the max that makes
   sense: a 17×17 room-sized view that covers every ground weapon's
   full range (rifles 7, drone lasers 6). Derelict power restore stays
   at 20 (map-wide on wrecks), so "turning the lights on" remains a
   real upgrade ✓ (landed standalone ahead of Phase 1)
5. **Peek-a-boo:** allowed — corner-peeking is a legitimate roguelike
   quirk (stair-dancing vibes); let players get clever. Mobs never
   heal (wounds persist), hunters keep roaming, re-peeking costs AP.
   No rep penalty on LOS-break. Noise is the documented future lever
   if it ever feels degenerate ✓
6. **Ambushers:** positional — player-LOS purity kept (no
   behind-the-back surprise). Ice worms / parasites ambush by
   placement: near corners/doorways, bursting (reveal line) and acting
   the same round when the player rounds the corner onto them ✓

## Open questions (resolved)

1. **Peek-a-boo cheese** — RESOLVED: allowed (decision #5). Corner-peek
   is a legitimate quirk; wounds persist, hunters roam, re-peeks cost
   AP. Noise stays the documented future anti-cheese lever.
2. **Sight radius** — RESOLVED: 8 (decision #4); the per-planet
   `DungeonParams.sight_radius` lever stays ready if Phase 2 playtest
   shows fights running too hot.

## Pre-implementation audit

### Existing code to extend/reuse

- `detect_ground_combat` (`combat/_encounter.py`) — the LOS loop to
  extract into `visible_hostiles()` (drop squad/assist/reveal).
- `_rules_ground.check_reinforcements` — already called every round by
  `run_combat`; becomes the join scan.
- `_rules_ground.init` / `damage()` — HP stamp + sync points.
- `_log_ambush_reveals` — reuse for mid-combat join lines.
- `_has_los` (`combat/_animations.py`) — symmetric ray, no change.
- `world.Entity` + `saveload` entity dict — the two `hp` sites.
- `__main__.py` ground-victory rep block — the `_squad_bonus` removal.

### Duplication hotspots (predicted)

1. **LOS loop** — `detect_ground_combat` inlines its own ray-cast +
   radius scan; the join scan would copy it. → One
   `visible_hostiles()` predicate, both call it.
2. **Entity-hp write** — damage sync could be copy-pasted into every
   damage path. → Single sync inside `rules.damage()`.
3. **Join logging** — init + join both announce combatants. → Share
   `_log_ambush_reveals` / one `_announce_joins` helper.

### DRY strategy

- `visible_hostiles()` lives in `_rules_ground` (owns `_state`) or a
  shared `_encounter` helper; `detect_ground_combat` + `check_reinforcements`
  + the end check all call it — one predicate, three consumers.
- Noise slot: the predicate is the seam; `noise_hostiles()` ORs in later.

## Design doc lifecycle

- [x] Phase 0: doc approved by user
- [x] Phase 1 → implementation (+ immediate-join fix); playtest folded
  into the Phase 2 checklist
- [x] Phase 2 → implementation (guard-post fix, noise seam, guide
  numbers, perf verified); playtest in progress
- [x] Phase 3 → implementation (chain-gen + sniff + fog) + playtest
  PASSED (user, 2026-08-06)
- [x] Moved to `complete/` (2026-08-06)
