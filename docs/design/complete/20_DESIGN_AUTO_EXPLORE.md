# 20 — Auto-Explore in Dungeons (the `O` key)

**Status:** complete
**Owner:** agent + user
**Depends on:** nothing (standalone QoL feature)

## Overview

DCSS-style auto-explore for dungeon / derelict interiors. Press `O`
and the player walks through unrevealed tiles until:

1. something **interesting** comes into sight (stairs, the exit, a
   ship computer, a cache of supplies, a quest NPC),
2. a hostile becomes visible — the shared ground-combat tick starts
   the fight and auto-explore stops (`COMBAT`), or
3. the player presses **any key** to cancel.

Only *newly revealed* interesting content stops the run. Each dungeon
floor also keeps a persistent set of interesting cells already presented
to the player, so intentionally left loot is not reported again after a
new `O` press or after leaving and returning to a cached floor. The same
memory is serialized with dungeon interiors and autosaves.

## Design

### New module: `src/spacehack/autoexplore.py`

Pure, testable decision helpers + a thin presentation loop (mirrors
`navigation._run_goto`'s step-and-poll pattern):

| Function | Purpose |
|----------|---------|
| `interesting_at(game_map, x, y) -> str \| None` | Short label for interesting content at a cell (transition tiles `stairs_up/stairs_down/exit`; entities with `loot_data`, `computer_terminal`, `main_quest_console`, `main_quest_door`, `npc_id`), else `None`. Table-driven labels. |
| `newly_interesting_positions(game_map, known) -> set[Position]` | Interesting cells in the current LOS frame (`game_map.visible`) not already in `known`. Empty when the map has no fog. |
| `next_explore_step(game_map, player_pos) -> (dx, dy) \| None` | BFS over passable cells (walkable + unblocked by `blocking_entity_at`) toward the nearest **unseen** walkable cell; returns the first step. Transition tiles are never routed through or targeted — auto-explore stops *beside* stairs/exit and lets the player decide. `None` = nothing left to explore. |
| `run_auto_explore(ctx, console, game_map, player, *, post_step_tick, map_w, map_h, location, present_frame=None) -> str` | The loop. Returns `"DONE"` (interesting sighting / exploration complete / standing on something), `"COMBAT"` (tick started a fight), `"DEFEAT"` (died in it), `"CANCELLED"` (keypress). `post_step_tick` and `present_frame` are injected (DI) so tests run headless; the default presenter renders the dungeon view + `pygame_overlay.present_exploration` exactly like the main loop. |

### Shared tick extraction (`__main__.py`)

Both the dungeon move and wait handlers run the same post-step
sequence today: `_run_ground_combat_tick` → defeat/continue control
flow → `tick_activation`. Extract `_dungeon_post_move_tick(ctx,
console, game_map) -> str | None` (`"DEFEAT"` / `"COMBAT"` / `None`)
and have move, wait, **and** auto-explore all call it — one source of
truth for NPC movement, LOS refresh, combat-on-sight, and activations.

### Key binding

- `O` (lowercase, via new `_is_o_press` in `input_helpers.py`) — the
  plain `o` is unbound today; `Shift+O` stays a dev-mode key.
- Dungeon mode only; other modes log "Auto-explore only works inside
  dungeons."
- Any keydown during the per-step delay window (`AUTO_EXPLORE`, new
  `animation_timing` constant, 0.02s) cancels — the key is swallowed,
  matching `_run_goto`.

### Stop semantics (DCSS-faithful)

1. Standing on interesting content at press → stop immediately.
2. Seed `known` with the floor's remembered cells and currently visible
   interesting cells; persist newly visible cells immediately.
3. Each iteration: fresh interesting in LOS → remember it and stop with a
   label ("You notice a cache of supplies and stop.").
4. No BFS target → "You have explored every reachable area." stop.
5. Tick returns `COMBAT`/`DEFEAT` → stop (combat owns the frame).

## Pre-implementation audit

**Reuse:**
- `world.GameMap.seen/visible` + `dungeon.reveal_around` — LOS/fog
  grids are exactly the "interesting in sight" predicate.
- `world.blocking_entity_at` (skips loot) — BFS passability, same as
  `world.find_path` consumers.
- `navigation._run_goto` — the step/render/poll/cancel loop template.
- `pygame_overlay.present_exploration` — mode-agnostic dungeon render.
- `_run_ground_combat_tick` (already shared by move + wait) — the
  per-step tick that auto-explore reuses.

**Duplication hotspots + DRY strategy:**
1. Post-step tick sequence (move vs wait vs auto-explore) → extract
   `_dungeon_post_move_tick`; all three call it.
2. Frame rendering (main loop dungeon branch vs auto-explore loop) →
   default `present_frame` reuses `camera_for_view` +
   `render_world_view` + `present_exploration` (same calls, one
   function).
3. Cancel-window polling vs `_run_goto` → same
   `events()`-during-delay pattern; kept local (different cancel
   predicate: any key vs movement keys) rather than over-abstracted.

## Implementation phases

### Phase 1 — shared tick refactor (commit 1) ✅ `c844cc0`
- [x] Extract `_dungeon_post_move_tick` in `__main__.py`.
- [x] Rewrite dungeon wait + move handlers onto it.
- [x] Gate green (existing tests prove behavior preservation).

### Phase 2 — auto-explore (commit 2)
- [x] `autoexplore.py` module (helpers + loop).
- [x] `_is_o_press` in `input_helpers.py`; `AUTO_EXPLORE` timing.
- [x] `O` handler in `__main__.py` (dungeon-only; map_w/map_h/location
      passed; `DEFEAT` → return, `COMBAT` → continue).
- [x] Guide: controls entry + `_GUIDE_AUTO_EXPLORE` section.
- [x] `tests/test_autoexplore.py` (BFS targeting, transition
      avoidance, interesting labels, fresh-vs-known, loop outcomes:
      complete / cancel / combat / interesting-stop / no-fog).
- [x] Gate green (842), self-audit, code review (blocking nit fixed:
      loop split into `_poll_cancel_window`; tables derived from one
      source).

### Post-playtest fix (both bugs, one root cause) ✅

**Bug:** auto-explore cornered the player at the derelict entry shaft
and declared everything explored while the whole ship was dark; walls
never revealed.

**Root cause:** derelict entry shafts are made of walkable `breach`
tiles (the player spawns on them and walks through them), but
`breach` was in `_TRANSITION_KINDS` — the BFS refused to route
through the very tiles the player stands on (0 steps from spawn, 746
unseen cells unreachable). Verified with `tools/repro_autoexplore.py`
on a real scout_a layout; after the fix the walk covers the ship
(188 steps) and ends with 0 reachable unseen cells.

- [x] Removed `breach` from `_TILE_LABELS`/`_TRANSITION_KINDS` — the
      leave-transition is the `exit` tile (still excluded).
- [x] Regression tests: breach passability (unit), breach not
      interesting, real-layout escape-from-spawn (scout_a, enemies
      stripped for determinism).

**Second fix (both remaining bugs — fog-edge walls):** the player's
save showed `next_explore_step → None` with **8574/10800 cells dark**
and **154 unseen wall cells** directly adjacent to seen floor: the
BFS only targeted unseen *walkable* cells, but fog boundaries are
made of unseen *walls* just beyond LOS. Once all reachable floor was
seen it declared everything explored, and the run never walked up to
boundary walls ("rooms explored up to the wall but the wall stayed
dark").

- [x] `next_explore_step` now targets ANY unseen cell — floor, wall,
      or transition — so the run advances to the fog edge and reveals
      it. Transitions are still never stepped on (an unseen one is
      walked toward so it can be spotted). Verified on the user's
      save: the walk runs (345 steps, boundary walls 154 → 26, all
      reachable cells revealed) and on scout_a (263 steps, 0
      reachable unseen).
- [x] Tests reworked for the semantics (walls seeded as seen in
      fixtures, like `reveal_around` in-game) + new wall-targeting
      regressions (walk toward unseen walls, progress through walls,
      none-when-walls-revealed).

## Playtest checklist

- [x] Press `O` in a derelict with unrevealed rooms — walks there,
      stops beside stairs/exit instead of stepping on them.
- [x] Loot in an unseen room: stops when it comes into view.
- [x] Loot already on screen when `O` pressed: does NOT re-stop.
- [x] Enemy comes into view: combat starts, auto-explore ends.
- [x] Any key cancels mid-run.
- [x] Everything explored: "You have explored every reachable area."
- [x] `O` in city/space logs the dungeon-only hint.
- [x] Press `O` right after entering a derelict (breach shaft) — the
      walk proceeds into the ship instead of stopping instantly.
- [x] Mid-run on a well-explored map: the walk continues to the fog
      edges (revealing boundary walls) instead of instantly reporting
      everything explored.

**PLAYTEST: COMPLETE.** Manual playtesting covered unrevealed-room traversal,
interesting-content stops, already-visible content, enemy discovery and combat,
keypress cancellation, exhausted maps, mode gating, breach-shaft entry, and
fog-edge wall revelation. The follow-up monster-blocking behavior was also
verified against the regression scenarios recorded above.

**Third fix (new save — invisible monster in the only door):** a
second autosave (Mars Surface, player at 36,33) showed
`next_explore_step → None` again with **7646/10800 cells dark**, but
this time the sealing ring around the reachable pocket was **201 seen
walls + exactly one walkable cell — (26,33), occupied by an
invisible rock scavenger** (10 cells beyond sight radius 8, so it is
never rendered). The monster was standing in the pocket's only
doorway; with it passable, **487 unseen cells** open up behind it.

- [x] Pathing rule: an entity outside the current LOS frame can
      never seal the route — the BFS treats it as passable, walks
      toward it, and the shared LOS-aggro tick starts ground combat
      the moment it comes into view (verified: BFS now returns
      `(-1, 0)` from the player and the walk stops at (34,33) with
      the scavenger visible). Design rule from the user: "a monster
      the game knows about can't block moving if the player doesn't
      know about it."
- [x] Visible solid entities still block; when one sits in the only
      exit of the explored region, `run_auto_explore` now logs
      "A rock scavenger blocks the only way forward." instead of the
      misleading "explored every reachable area." (DCSS-style
      monster-in-the-way). Detector flood-checks that removing the
      entity opens unseen territory, so an incidental visible
      terminal inside a wall-sealed room does not trigger it.
- [x] Tests: visible-blocks vs unseen-passes, way-out detector
      (monster / invisible-monster / incidental-terminal / step-
      available), loop stops at visible monster, loop walks to and
      reveals an unseen monster.

### Persistent interesting-cell memory ✅

Auto-explore now stores the coordinates of interesting content it has
already presented on each `GameMap`. The memory is floor-local: cached
interiors retain their own cells, and the dungeon save format round-trips
the set for Continue. Content already visible when `O` is pressed is
recorded immediately; newly revealed content is recorded before the run
stops. This means choosing to leave loot on the floor no longer causes
successive auto-explore runs to repeat the same warning, while a different
floor still gets its own independent discovery memory.

- [x] Persist remembered cells on `GameMap`.
- [x] Serialize/restore the memory for active and cached dungeon maps.
- [x] Regression tests for repeated auto-explore and cached-floor
      serialization.
