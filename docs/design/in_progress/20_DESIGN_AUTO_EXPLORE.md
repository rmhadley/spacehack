# 20 — Auto-Explore in Dungeons (the `O` key)

**Status:** in progress
**Owner:** agent + user
**Depends on:** nothing (standalone QoL feature)

## Overview

DCSS-style auto-explore for dungeon / derelict interiors. Press `O`
and the player walks through unrevealed tiles until:

1. something **interesting** comes into sight (stairs, the exit, a
   hull breach, a ship computer, a cache of supplies, a quest NPC),
2. a hostile becomes visible — the shared ground-combat tick starts
   the fight and auto-explore stops (`COMBAT`), or
3. the player presses **any key** to cancel.

Only *newly revealed* interesting content stops the run: content
already in view when `O` is pressed is seeded into a known set, so a
single press never stalls next to loot the player already spotted.

## Design

### New module: `src/spacehack/autoexplore.py`

Pure, testable decision helpers + a thin presentation loop (mirrors
`navigation._run_goto`'s step-and-poll pattern):

| Function | Purpose |
|----------|---------|
| `interesting_at(game_map, x, y) -> str \| None` | Short label for interesting content at a cell (transition tiles `stairs_up/stairs_down/exit/breach`; entities with `loot_data`, `computer_terminal`, `main_quest_console`, `main_quest_door`, `npc_id`), else `None`. Table-driven labels. |
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
2. Seed `known` with currently visible interesting cells.
3. Each iteration: fresh interesting in LOS → stop with a label
   ("You notice a cache of supplies and stop.").
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

## Playtest checklist

- [ ] Press `O` in a derelict with unrevealed rooms — walks there,
      stops beside stairs/exit instead of stepping on them.
- [ ] Loot in an unseen room: stops when it comes into view.
- [ ] Loot already on screen when `O` pressed: does NOT re-stop.
- [ ] Enemy comes into view: combat starts, auto-explore ends.
- [ ] Any key cancels mid-run.
- [ ] Everything explored: "You have explored every reachable area."
- [ ] `O` in city/space logs the dungeon-only hint.
