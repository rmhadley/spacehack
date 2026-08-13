# 21 — Dungeon Go-To (the `G` key)

**Status:** complete
**Owner:** agent + user
**Depends on:** #20 auto-explore (same movement machinery, same module)

## Overview

DCSS-style travel inside dungeons/derelicts. Press `G` in dungeon mode to
open a GO TO picker listing **discovered** destinations — stairs up/down,
the exit, and interactables (ship computers, quest consoles, sealed doors,
NPCs, interaction tiles) — then auto-walk to the chosen one using the
auto-explore step machinery:

- The walk uses the same passability rules: walkable cells, visible solid
  entities seal, unseen entities are walked through (revealed → LOS aggro
  combat), transitions are never stepped on.
- The walk **stops at interesting things** exactly like auto-explore
  (newly-visible caches, other stairs, quest content), so passing a cache
  you hadn't spotted interrupts the run.
- The chosen target itself is seeded into the known set — approaching it
  does NOT trigger its own "interesting" stop.
- Arrival = 8-adjacent to the target (the player then steps onto the
  stairs / bumps the console / talks to the NPC manually).
- Stops on combat start, DEFEAT, or any keypress (cancel window), like O.

Also requested: the HUD key hints gain `O Explore` and `G Go To` in
dungeon mode (space mode already shows G).

## Pre-implementation audit

**Modules to extend / reuse:**
- `src/spacehack/autoexplore.py` — the entire step machinery:
  `_plan_explore_step` (BFS), `_visible_blocker` (visibility rule),
  `_first_step_toward`, `_poll_cancel_window`, `_default_present_frame`,
  `newly_interesting_positions`, `interesting_at` (prose labels).
- `src/spacehack/navigation.py::_run_pygame_goto_menu` — the GO TO picker
  modal (labels + description, ENTER go / ESC cancel / ? guide). Reused
  as-is for dungeons; returns `(handled, selected_index)`.
- `src/spacehack/__main__.py` — dungeon key dispatch; the O handler is the
  template for the G handler (same `_dungeon_post_move_tick` injection,
  same DEFEAT/COMBAT returns).
- `src/spacehack/hud.py` — dungeon-mode `_help_lines` list.
- `src/spacehack/help.py` — Controls + Auto-Explore guide section.
- Tests: `tests/test_autoexplore.py` fixtures (`_corridor`, `_run`,
  `_reveal_frame`) — the goto loop tests mirror the auto-explore loop
  tests.

**Three duplication hotspots:**
1. **The BFS.** `next_goto_step` must NOT be a second copy of
   `_plan_explore_step`'s neighbor loop. DRY strategy: parameterize the
   one BFS with a goal mode — `_plan_step(game_map, player_pos, *,
   target=None)`; explore mode returns the step toward the nearest unseen
   cell, goto mode returns the step toward the nearest cell adjacent to
   `target`. Both modes share passability (walkable, transition-excluded,
   `_visible_blocker`).
2. **The step-present-poll-move sequence.** `run_auto_explore` and
   `run_goto` share "present frame → cancel window → move → post tick".
   DRY strategy: extract `_step_present_poll_move(...)` returning
   `"CANCELLED" / "DEFEAT" / "COMBAT" / None`, used by both loops.
3. **The picker menu.** Do NOT reimplement the GO TO modal loop; import
   `navigation._run_pygame_goto_menu` lazily (navigation does not import
   autoexplore, so no cycle).

## Design decisions

- **Targets:** seen cells only (`game_map.seen`), nearest-first. Tile
  kinds: `stairs_up`, `stairs_down`, `exit`. Entity flags:
  `computer_terminal`, `main_quest_console`, `main_quest_door`, `npc_id`,
  `dungeon_interaction`. Loot caches are NOT goto targets — O handles
  pickup; a dungeon can hold 20+ caches and the picker would drown.
- **Labels:** picker title ("Stairs down", "Ship computer") + prose label
  for logs resolved via `interesting_at` ("a stairway down") — one source
  of prose truth.
- **Arrival is adjacent, never on top:** transitions are never entered
  (same as O); consoles/NPCs are bumped by the player. Wall-embedded
  quest NPCs work too — the walker stops beside the wall cell.
- **The target is seeded into the known set** so its own sighting cannot
  interrupt the approach.
- **Unreachable target** (sealed pocket): BFS exhausts → "Cannot reach
  <label>." (message mirrors the auto-explore exhausted message).

## Steps

- [x] Refactor: goal-mode BFS + shared step machinery (behavior-preserving;
      the 855 existing tests are the proof; committed separately as
      `07464fb`).
- [x] `goto_targets(game_map, player_pos) -> list[GotoTarget]` — seen-only
      targets, nearest-first, loot excluded, deduped by cell.
- [x] `next_goto_step(game_map, player_pos, tx, ty)` — goal-mode wrapper;
      None when adjacent or no path.
- [x] `run_goto(...)` — the walk loop (arrival / interesting / cancel /
      combat / defeat / cannot-reach outcomes).
- [x] `run_dungeon_goto(...)` — picker (navigation helper) + `run_goto`.
- [x] `__main__.py`: dungeon `_is_g_press` handler (mirror O).
- [x] HUD: dungeon `_help_lines` += `("O", "Explore")`, `("G", "Go To")`
      (HUD panel is 20 chars — "Auto-Explore" would overflow).
- [x] Guide: Controls dungeon list + Auto-Explore section (O and G).
- [x] Tests: targets discovery/ordering/exclusions, goal BFS (adjacent →
      None, visible blocker → None, invisible blocker passable, no path),
      loop outcomes (arrival beside stairs, interesting stop, target-seed
      no-self-stop, cancel, combat, cannot-reach).

Verified against real layouts: `scout_a` discovers Exit (adjacent to
spawn → step None = already arrived) + Ship computer; `freightliner_a`
same. The focused auto-explore/go-to suite contains 44 tests; the full
repository gate is recorded below.

Note: the HUD hints are gated at mode level (dungeon shows O/G
unconditionally) — target-aware gating would need map access per
frame in `render_hud`, not worth it; G with nothing discovered logs
the no-targets message.

## Playtest checklist

- [x] `G` in a derelict lists stairs + consoles; ENTER walks to stairs and
      stops adjacent; stepping onto stairs leaves.
- [x] Passing a cache you haven't seen en route interrupts the walk.
- [x] Walking past a monster camped in the dark starts LOS combat.
- [x] `G` with nothing discovered logs the no-targets message.
- [x] HUD shows `O Explore` and `G Go To` in dungeon mode only.

**PLAYTEST: COMPLETE.** Manual playtesting covered target discovery and ordering,
adjacent arrival without stepping onto transitions, interruption by newly seen
content, LOS combat, empty-target handling, and dungeon-only HUD hints.
