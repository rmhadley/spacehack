# DESIGN: Auto-pickup — walk-over collection

**Status:** OPEN — drafted 2026-09-27. Rulings SETTLED 1–6 recorded (open questions exhausted);
Implementation briefs for phases 1–3 PROPOSED with all three ADVISE reviewer passes folded
(space-goto hook, silent probe, heist markers, tutorial beat, no-DisplayConfig pref, per-key
config granularity, goto-halt consequence, existing-test re-pointing) — awaiting user approval.

## Overview

> "I'm thinking we need an auto-pickup option. Walking over certain things and auto-explore mode should definitely pick up all ammo it can. Trade goods should default to auto-pickup but it should be able to be disabled in options."
> — user, 2026-09-27

Today pickup is only the P key: a modal verb with 9-cell reach (current cell + cardinals first),
available in dungeon and space exploration, absent from ground combat entirely. Loot is a walkable
floor object — `blocking_entity_at` deliberately skips it — and stepping over it does nothing
(`_dungeon_post_move_tick` runs NPCs, LOS, combat-start, extensions; no loot branch exists).

This doc adds walk-over auto-pickup for three deliberate classes, an options toggle for cargo, and
teaches auto-explore to scoop instead of halt.

## The mechanic

### Auto-pickup classes

| Class | Auto? | Gate / rationale |
| --- | --- | --- |
| Ammo — all calibers incl. grenades & rockets | always, no toggle (SETTLED 1) | bandolier per-caliber caps are the gate; "all it can" = fill to cap |
| Trade-good debris | default ON, options toggle (SETTLED 1) | goes straight to the ship hold; full hold = pile stays |
| Credit piles (chip + lockbox) | always (SETTLED 2) | pure gain, no capacity; P's 9-cell reach already trivialized them |
| Weapons / armor / ship modules / ship weapons | never | build decisions |
| Data pads & site pads | never | discovery beats |
| Quest caches & heist cargo | never | securing is a deliberate beat; securing logic fires on pickup |
| Consumables | never | Expedition Pack slots are a Strength-capped loadout decision |

### Semantics — probe first, clean no-op

The walk-over runs the class validators read-only before applying (bandolier room, cargo room) —
the doc-54 refusal-probe pattern. A pickup either completes or is a full no-op: no prompts, no
half states, no AP, no turn cost beyond the step itself. Refusals are silent — the pile visibly
stays, and P still explains why if asked. The walk-over fires on **movement arrival only** — not
inside the shared post-move tick (which wait also runs): waiting on a pile cell picks nothing. Success logs the existing pickup lines verbatim
("Picked up rifle rounds x12."). No modals, no sound (none exists in the pickup path today).

### Partial ammo stacks

Walk-over takes what fits and **leaves the remainder as a smaller pile** (quantity reduced, entity
removed at zero). Auto-pickup must never destroy ammo the player would have chosen to time — and
neither may P anymore: the P flow's partial fit aligns with the same leave-remainder semantics
(SETTLED 4), amending doc 52's forfeit-overflow ruling. The at-cap behavior is untouched — the pile
stays and P still explains ("Your rifle rounds reserve is already full.").

### Where it runs

The exploration movement resolution only — on foot in dungeons/cities-interior, and flying over
debris in space (same payload class, same cargo-room check). **Not in ground combat** (SETTLED 3):
combat has no pickup at any price today, and free walk-over refills would cut against the doc-50
tuning doctrine; after the fight ends, walking the drops collects them anyway. Auto-explore and
dungeon goto inherit walk-over through the shared stepper helper (`_step_present_poll_move`);
space auto-nav (G in space) is its own step path and gets the same one-liner at its move
(`navigation_travel._goto_step`) — it flies over debris cell-by-cell and shares nothing with the
dungeon steppers.

### Auto-explore interplay

Today auto-explore routes only toward **unseen cells** (`next_explore_step`) and collects piles
purely through the halt: every **newly visible** loot pile stops the run ("You notice {label} and
stop." — `_stop_if_fresh`; `loot_data` is an `_ENTITY_INTEREST_FLAGS` entry) until the player
presses P and resumes. After this (SETTLED 5–6):

- **Pickable piles become first-class targets.** The run's goal set widens from "nearest unseen
  cell" to "nearest target, whichever is closer — a pickable pile or the fog edge" (SETTLED 5,
  verbatim: "autoexplore should target the nearest target, nearest target being either autopickup
  or nearest unexplored fog"). BFS nearest-wins gives this for free once pile cells join the goal
  set. The run ends only when no unseen cells AND no pickable piles remain reachable — a cleared
  floor has its ammo and credits, without twenty halts.
- **Auto-class piles never halt the run.** A pile the probe refuses on arrival (bandolier full for
  that caliber, hold full, toggle off) is skipped without halting (SETTLED 6) — the pile visibly
  stays, the run continues, and a full rifle reserve never blocks scooping grenade piles ahead.
- **Never-class piles keep the existing halt** ("a cache of supplies") — weapons, armor, modules,
  ship weapons, pads, quest caches, consumables are decisions. The per-map ignore-memory keeps
  covering exactly these on re-runs.
- The underfoot exemption at run start is unchanged. Goto's loot exclusion from the **picker**
  is unchanged — but its newly-visible **halt** for auto-class piles goes away with O's: the halt
  is the same shared `interesting_at` call, so a G walk past a fresh ammo pile no longer stops
  either (doc amendment recorded with the phase-3 brief; never-class piles still halt both).

### The toggle

A new row in the existing title-screen OPTIONS menu — `AUTO CARGO PICKUP: On/Off` — persisted
per-user in `~/.spacehack/config.toml` under a new `[gameplay]` section (`auto_cargo_pickup = true`
default). The config parser was built to tolerate unknown sections/keys for exactly this. Per-user,
not per-save, matching the menu's existing promise ("Preferences are saved separately from game
saves"). Doc 100's future in-game menu can mirror the row. Ammo and credits get no toggle by
design. No GameContext / save-format changes anywhere in this arc.

## Design intent

- Kill the key-press tax on zero-decision pickups. Ammo frustration is documented history (delve
  ammo logistics, doc 52); the user plays ground like a roguelike, and stopping to press P over
  every calibre pile is friction with no decision inside it.
- Keep every decision-laden pickup deliberate — the never-list is the point, not an omission.
- Nothing silently lost or destroyed: refusal is a clean no-op; partial fits leave the remainder.
- Auto-explore's promise sharpens: a cleared floor has its ammo and credits, without twenty halts.

## Phases

- [ ] 1. **Walk-over core + P remainder alignment** — probe + apply for the three classes at
  movement arrival (both theaters, manual + all three stepper/auto-nav paths); ammo
  remainder-splitting; silent refusal (the probe never logs); existing log lines; the P flow's
  partial fit aligns with leave-remainder (SETTLED 4, amending doc 52); the tutorial's pickup
  beat completes on arrival (line reworded). Tests: per-class pick / refuse / partial-split,
  every movement path, a sabotage-proven regression pin on the walk-over hook. Guide-diff item:
  none (guide lands with phase 3, when the behavior finalizes).
- [ ] 2. **The toggle** — `[gameplay] auto_cargo_pickup` in config.toml + the title OPTIONS row;
  toggle-off turns trade debris back into ordinary P-only loot (refused-probe class). Guide-diff
  item: the AUTO CARGO PICKUP row line in "Options & Display" **plus that section's intro
  rewording** (its "presentation only" claim becomes false).
- [ ] 3. **Auto-explore nearest-target + guide pass** — pickable piles join the goal set: the run
  routes to the nearest target, pile or fog edge (SETTLED 5); refused piles skip without halting
  (SETTLED 6); never-class piles keep the halt; ignore-memory and the underfoot exemption are
  unchanged; goto keeps its picker exclusion but loses the auto-class newly-visible halt (shared
  `interesting_at`). Full-corpus guide audit: grep the whole guide for the pickup/loot vocabulary
  (P key, auto-explore/auto-walk lines, ammo & ammunition carry limits, battlefield pickups,
  trading/cargo prose) and classify every hit in the brief; guide text drafts get user approval
  in the brief before landing.

## SETTLED

1. **(2026-09-27, user)** Ammo always auto-picks on walk-over, including in auto-explore mode —
   "all ammo it can" — with no toggle. Trade-good debris defaults to auto-pickup, disableable in
   options.
2. **(2026-09-27, user)** Credit piles auto-pick too (ruling: "Credits too"). Consumables stay
   P-only (Strength-capped pack slots).
3. **(2026-09-27, user)** Exploration only — walk-over auto-pickup does not run during ground
   combat.
4. **(2026-09-27, user)** The P flow's partial fit aligns with the walk-over semantics: a partial
   fit leaves the remainder as a smaller pile. This **amends doc 52's forfeit-overflow ruling**
   (a partial fit used to consume the entity and destroy the rest); the at-cap behavior (pile
   untouched, "already full" line) is unchanged.
5. **(2026-09-27, user, verbatim)** "autoexplore should target the nearest target, nearest target
   being either autopickup or nearest unexplored fog" — pickable piles are first-class
   auto-explore targets alongside the fog edge, not a post-frontier sweep stage; nearest wins.
6. **(2026-09-27, user)** A pile the run refuses on arrival (bandolier full for that caliber,
   hold full, toggle off) is skipped without halting — the pile visibly stays and the run
   continues. Auto-class piles never halt auto-explore; never-class piles keep the existing halt.

## Open questions

None — questions 1–2 (P-flow overflow alignment; probe timing for auto-explore stops) were
resolved by SETTLED 4 and 5–6 respectively on 2026-09-27.

## Implementation briefs (PROPOSED — each awaiting user approval)

### Phase 1 — Walk-over core + P remainder alignment

**Scope (files / hook points):**

- NEW `src/spacehack/auto_pickup.py` — owns the whole feature: the auto/never **class table**
  (a table over `loot_data` shapes, reusing loot's own parsing helpers — `_field_item_loot_stack`
  and friends — never re-parsing raw dicts; guardrail 1 forbids an item_type if-chain), the
  read-only **and silent** probe, and the entry `maybe_pickup_at(ctx, pos)` reading
  `ctx.game_map` (ctx-first). Probe rules:
  - **Never call `_cargo_room` (loot.py:667) or `_quest_loot_goods` (loot.py:624) — both log.**
    Trade room is computed directly: `ctx.player_owned_ship is not None` and
    `_pickup_volume(...) (loot.py:640, pure) ≤ trade._free_cargo(owned)`. Ammo room reuses the
    existing pure pair `bandolier.space_remaining` (bandolier.py:73) + `effective_cap`
    (bandolier.py:64) — no new extraction; `refill` (bandolier.py:92) stays the only mutator.
    Credits: always yes.
  - **Never-class markers, exactly:** equipment/modules/ship weapons/pads/consumables, AND any
    trade shape bearing `main_quest_step_id` (loot.py:803) or `heist_mission`/`heist_mission_id`
    (checked at loot.py:570-571) — read as plain attributes. The walk-over must NEVER auto-fire
    `_secure_heist_cargo`: securing is a deliberate beat.
  - Apply runs through the existing appliers (`loot._apply_ammo_loot_pickup`'s refill path,
    `loot._apply_credits_loot` (loot.py:897), the trade `_apply_loot_pickup` path), logging the
    existing lines verbatim. The space apply also fires `tutorial.notify_pickup`
    (tutorial.py:400 — today only the P path fires it, game_loop.py:338).
- `src/spacehack/game_loop.py` — `_handle_movement_event` (game_loop.py:699): on
  `code == 'moved'`, fire `maybe_pickup_at` for the arrival cell in **dungeon mode (interiors
  ride dungeon mode) and space mode**; city mode excluded. Placement: right after the move
  resolves, before the mode-specific handling (a pickup resolved on the arrival step stands even
  when that same step's tick starts a fight — the arrival was exploration).
- `src/spacehack/autoexplore.py` — **one** stepper hook: `_step_present_poll_move`
  (autoexplore.py:612-644) after the pos assignment (:641-643), before `await post_step_tick` —
  covers O, dungeon goto, and swap-steps with no twin drift. **Not** inside
  `_dungeon_post_move_tick` (game_flow.py:383) — it is shared with wait, and waiting on a pile
  must pick nothing.
- `src/spacehack/navigation_travel.py` — `_goto_step` (:398-400): fire on the arrival cell right
  after the pos assignment (:400, before the cancel poll). Space auto-nav (G) flies over debris
  step-by-step and bypasses `_handle_movement_event` — without this hook, manual space flight
  scoops and auto-nav silently doesn't.
- `src/spacehack/debug_session.py` — `_apply_dungeon_step` duplicates the move (twin-path rule):
  it gets the same walk-over call so `save_debug simulate` matches the real game.
- `src/spacehack/loot.py` — SETTLED 4: `_apply_ammo_loot_pickup` (loot.py:496) leaves the
  remainder via the existing `_leave_field_item_remainder` (loot.py:460), logging
  "Picked up {name} x{added}; left {n} on the floor." (mirrors the field-item wording,
  loot.py:545); at-cap branch untouched. Verified blast radius: one caller (the P chain,
  loot.py:534).
- `src/spacehack/tutorial.py:140` — the scripted line "Fly onto (or next to) the loot and press
  'P' to pick it up." completes on arrival now; reword to **"Fly onto the loot to pick it up."**
  (draft, user-approved below; P remains the pickup verb for every non-auto class — the guide
  keeps teaching it).
- Tests: `tests/test_auto_pickup.py` (new) + `tests/test_ground_equipment.py` — the doc-52
  forfeit pin `test_field_ammo_pickup_partial_fit_forfeits_overflow` (:543) updates in-commit;
  its at-cap twin (:564) pins the unchanged branch.

**Build order:** class table + silent probe (pure, tested first) → `maybe_pickup_at` apply
wiring + tutorial notify → game_loop hook → stepper hook → space-goto hook → debug_session twin →
P remainder alignment → regression pins.

**Binding rulings:** SETTLED 1–4. Silent refusal — the pile visibly stays, **no log line ever**
(this is why the probe may not touch the logging validators); partial fits leave a smaller pile
(entity removed at zero); movement-arrival only (never wait); exploration only — never inside the
ground-combat loop; existing log lines verbatim; no modals, no sound.

**Per-step cost (guardrail answer):** one O(entities) scan of the single arrival cell with an
early `loot_data is None` skip — do NOT reuse `nearby_loot_entities` (9 positions × full entity
scan); the discriminator is table-driven.

**Required tests:** per-class pick / refuse / partial (ammo incl. multi-caliber, credits chip +
lockbox, trade incl. full-hold and no-ship; quest-marked and never-classes excluded — heist
markers pinned); remainder-split leaves a smaller pile and removes the entity at zero; the P path
now leaves remainders (the updated :543 pin; at-cap line unchanged); **every movement path**
fires the hook (manual move, auto-explore stepper, space auto-nav) and wait does not; two loot
entities on one arrival cell both picked; O pressed standing on a pile picks nothing (no arrival
— pins the underfoot exemption); unknown ammo `item_id` is a silent never (the apply path would
log "Invalid field item", loot.py:509); **sabotage-proven** regression pin on the walk-over hook
(disable the hook → test fails → restore → passes).

**Stop point:** no options/config work (phase 2); no auto-explore goal or stop changes — halts
behave exactly as today (phase 3); no guide edits (the tutorial line above is tutorial, not
guide); no new pickup classes.

**Budget note:** loot.py sits at 941/1000 — new logic lands in `auto_pickup.py`; loot.py gains
only the remainder branch. game_loop.py 884, autoexplore.py 835, navigation_travel.py and
debug_session.py — small hooks only.

**Playtest checkpoint:**

1. (dev ground loadout) Walk over an ammo pile with bandolier room → existing log line, pile gone.
2. Partial fit → "Picked up … x{added}; left {n} on the floor." and a smaller pile remains; P over
   the remainder takes the rest.
3. At-cap caliber → walk over: no log, pile stays; P still explains ("already full").
4. Credit chip and lockbox walk-overs → credit lines, entity gone, credits up.
5. Trade debris on foot AND in space → hold gains; full hold → pile silently stays; heist cargo /
   quest-marked goods never auto-pick (walk over them: nothing).
6. Weapon / quest cache / consumable pile → walk over does nothing.
7. P partial fit now leaves the remainder (the doc-52 forfeit is gone) — confirm on purpose.
8. During a ground fight, moving over drops picks nothing; after DISENGAGED, walking the drops
   collects them.
9. Auto-explore still halts at newly-visible piles (phase 3 not built), but piles crossed on the
   route are scooped.
10. Space G auto-nav onto/over debris → scooped en route (interrupt a transit over a debris field).
11. New game: fly onto the tutorial debris → the reworded line plays and the beat completes on
    arrival (no P press needed); the JUMPING beat unlocks.
12. Save → quit → Continue: identical bandolier / hold / credits / remaining piles.
    Guide-diff: none (guide lands with phase 3).

### Phase 2 — The toggle

**Scope (files / hook points):**

- `src/spacehack/auto_pickup.py` — module-level runtime pref with a test-reachable setter (the
  `animation_timing.set_speed_scale` shape, animation_timing.py:108-116): set at every runtime
  open (pygame_runtime.py:296 family, where `_SPEED_SCALE` is set) and directly by the OPTIONS
  APPLY handler; never serialized, never in the save; headless default true (matches the shipped
  default — `tools/save_debug.py` and the balance harness never open a runtime, and phase-3 tests
  set it explicitly). **The pref must NOT become a `DisplayConfig` field**: the engine stitch
  (pygame_engine.py:488-492) rebuilds `DisplayConfig` from window state only and
  pygame_runtime.py:268-270 re-stitches just `animation_speed` — a pref riding there would be
  silently re-defaulted on every Apply and the save at :273-275 would persist the default (it
  could never stay Off). No `DisplayConfig` or stitch changes at all.
- `src/spacehack/display_config.py` — the single owner of `config.toml` (docstring reframed
  accordingly): parse `[gameplay]` (`auto_cargo_pickup`, default true) with **per-key malformed
  granularity** (a bad `[gameplay]` value defaults that one key; `[display]` and the raw file
  stay untouched — never the whole-file ValueError fallback for a gameplay typo, which the next
  APPLY would then persist). The writer gains the **two-mode rule**: known sections (`[display]`,
  `[gameplay]`) re-serialized from parsed state, foreign sections and `#` comments preserved as
  raw text — both in the same commit (today's `save_display_config`, display_config.py:143-150,
  is a full rewrite that destroys foreign sections).
- `src/spacehack/pygame_title.py` — OPTIONS screen (rows + APPLY, pygame_title.py:105-240): new
  row `AUTO CARGO PICKUP: On/Off`; APPLY sets the runtime pref via the setter and persists it
  through the writer. The title-menu OPTIONS blurb (:75, "Change display and animation
  preferences") is reworded to cover the gameplay row (the modal body's "Preferences are saved
  separately from game saves" stays true).
- `knowledge.md` — the module-level state registry table gains the pref's row in-commit (the
  `_SPEED_SCALE` lifecycle columns).
- Guide: "Options & Display" gains the row line **and the section intro is reworded** — the
  current intro (guide/__init__.py:58-60: "These settings affect presentation only; they never
  change your pilot, world, or save data.") becomes false the moment a gameplay row exists.
  Draft intro: **"These settings change how the game looks and plays. They are saved separately
  from game saves."** (user-approved below).

**Build order:** config parse + two-mode writer round-trip (tested first) → runtime pref + setter
→ trade-class gate in the probe/apply → OPTIONS row + APPLY → runtime-open wiring → knowledge.md
row → guide line + intro.

**Binding rulings:** SETTLED 1 (trade default ON, disableable; ammo/credits never gated);
per-user in config.toml, NOT per-save — no GameContext / save-format changes anywhere.

**Required tests:** config round-trip ([display] + [gameplay] + hand-edited unknown sections and
comments all survive a save; default-on both when the key is absent AND when no file exists at
all — different code paths, display_config.py:139-141); per-key malformed granularity (bad
`[gameplay]` value → key defaults true, `[display]` values intact); toggle-off → the trade probe
refuses while ammo/credits still auto-pick; the autosave JSON does not contain the pref; the
Apply path writes the file through the setter+writer pair; headless default true without a
runtime open.

**Stop point:** no auto-explore changes (phase 3); no guide prose beyond the row line + intro
rewording; no DisplayConfig/stitch changes.

**Playtest checkpoint:**

1. OPTIONS → AUTO CARGO PICKUP Off → APPLY: trade debris walk-over silently refused on foot and
   in space; ammo and credits still auto-pick.
2. APPLY persists `[gameplay] auto_cargo_pickup = false`; relaunch → row reads Off, behavior
   holds (the pref STAYS Off — this pins the no-DisplayConfig ruling).
3. Fresh config (no file at all) → row reads On, phase-1 behavior unchanged.
4. Display preferences still save/apply alongside; hand-edited unknown sections, keys, and
   comments survive an APPLY untouched.
5. A hand-typo'd `[gameplay]` value (e.g. `auto_cargo_pickup = mayb`) → defaults On at load,
   `[display]` untouched, file not clobbered until a clean APPLY.
6. Continue an autosave: the pref is not in the save (both saves share the one pref).
   Guide-diff: "Options & Display" gains the AUTO CARGO PICKUP row line + the reworded intro
   (exact before/after in the diff).

### Phase 3 — Auto-explore nearest-target + guide pass

**Scope (files / hook points):**

- `src/spacehack/auto_pickup.py` — `pickable_positions(ctx, game_map)`: every **seen** auto-class
  pile whose **silent probe** accepts (recomputed per step; state can change mid-run). Per-step
  cost is noise beside the existing per-step passes (`steps_aside_ids`, `_blocker_index`,
  `_stop_if_fresh`), but the probe must stay pure AND quiet — including the ammo caliber's
  catalog resolve — because it now runs per seen pile per step.
- `src/spacehack/autoexplore.py` — `_plan_step` (autoexplore.py:407) gains an optional
  `goal_cells` frozenset: a cell is a goal if unseen OR a member — BFS nearest-wins then IS
  SETTLED 5 (nearest pile or fog edge, whichever is closer); `next_explore_step` passes it
  through; `run_auto_explore` computes it per step. Two planner invariants to state for the
  build: **goal membership never overrides passability or transition-non-entry** (the
  non-walkable/transition `continue` at :362 precedes any goal check — a pickable pile on a
  stairs/exit tile is simply unreachable and the run may end with it visible; accepted, not
  special-cased), and equal-distance ties resolve by the existing deterministic enqueue order.
  `interesting_at` (autoexplore.py:186) — the `loot_data` entry becomes class-aware with
  **fall-through**: an auto pile stacked with a never-class pile or console on one cell still
  halts on the never-class entity (first-match must skip, not return, for auto-class piles).
  Auto-class piles are never interesting (never halt); never-class piles keep "a cache of
  supplies", and `_stop_if_fresh` + ignore-memory keep covering exactly those.
- **Goto consequence (intended, named):** `interesting_at` is also goto's stop path — auto-class
  piles stop halting G walks exactly as they stop halting O. What stays is the loot **exclusion
  from the picker** (`_GOTO_TILE_TITLES` :96 / `_GOTO_ENTITY_TITLES` :101 remain loot-free) and
  `next_goto_step` itself. The underfoot exemption at run start is unchanged (the run-end
  wording carries its one distance-zero exception: a pickable pile can remain under the player).
- `src/spacehack/debug_session.py` — `_action_explore` drives `next_explore_step` directly
  (twin-path rule): it passes `goal_cells` too, so `save_debug simulate … explore` matches the
  real O (the move twin was wired in phase 1).
- **Same-commit test updates** (pure-function test contract): `tests/test_autoexplore.py` pins
  trade-shaped `loot_data` halts that this phase invalidates —
  `test_run_auto_explore_stops_at_newly_visible_loot` (:442), `…ignores_already_visible…` (:460),
  `…remembers_left_loot_on_return_to_floor` (:482), `test_interesting_at_labels…` (:281),
  `test_newly_interesting_positions…` (:289). Re-point them at never-class shapes (equipment
  payloads) and add auto-class counterparts.
- Guide: **full-corpus audit** — the corpus is the single file `data/guide/__init__.py`; grep it
  for: P key / "pick it up" / "nearby-loot" / "P: collect nearby loot", loot, auto-explore /
  auto-walk, ammo / ammunition / per-caliber carry limit / battlefield pickups, trading & cargo
  prose. Two entries are already known load-bearing and must be classified in the build's audit:
  Ground Exploration's O bullet (:527-530 — "stops when danger or something interesting appears …
  including loot you chose to leave behind" is directly contradicted) and the on-foot/ship-cargo
  split (:555-556 — "Loot found on foot is handled separately from ship cargo" is contradicted by
  trade walk-over straight to the hold). Every new or changed entry's exact text is approved
  HERE, in this brief, before the build lands it.

**Build order:** planner goal-widening (pure + tests incl. the existing-test re-pointing) →
`interesting_at` class-awareness + fall-through → run-loop wiring → debug_session twin → guide
pass (after prose approval).

**Binding rulings:** SETTLED 5 (nearest target = pickable pile or unexplored fog; not a
post-frontier stage); SETTLED 6 (arrival refusal skips without halting; auto-class piles never
halt O or G); never-class halts, ignore-memory, underfoot exemption, and goto's picker exclusion
all unchanged.

**Required tests:** nearest-wins ordering both ways (pile nearer than fog detours first; fog
nearer wins) **plus the tie-break pin**: a goal member at BFS depth d fires from its depth d-1
parent before a fog-adjacent goal at depth d during depth-d expansion; a refused pile is not a
target; never-class pile still halts and ignore-memory prevents the re-halt on resume; a stacked
cell (auto pile + never-class entity) still halts; underfoot exemption at run start; goto's
picker excludes loot AND a G walk past a newly-visible auto pile does not halt; the run ends
only when no unseen cells and no pickable piles are reachable; planner purity preserved
(headless fakes); the five re-pointed existing tests above.

**Stop point:** no goto targeting of loot; no new pickup classes; no changes to stop messages
beyond the existing lines; no doc-100 in-game menu work (the future menu can mirror the row).

**Playtest checkpoint:**

1. Seed a room with piles OFF the frontier path → O detours to the nearest pickable pile before
   the fog when it is nearer, scoops it, resumes; the run ends only when the fog is done AND no
   pickable piles remain (a pile can legitimately remain underfoot or on an unreachable/stairs
   tile).
2. A full caliber: the run crosses its piles without halting; other calibers still collected.
3. A newly-visible weapon / quest cache → "You notice a cache of supplies and stop." unchanged;
   resuming without picking it up does not re-halt (ignore-memory).
4. Mid-run fill: one pile tops a caliber → later same-caliber piles are silently skipped.
5. Trade toggle Off → trade piles are never targets (ammo/credits still are).
6. G: loot still absent from the picker; a G walk past a newly-visible ammo pile no longer stops;
   a never-class pile still stops it; a combat interrupt during a pile detour stops the run
   through the existing machinery.
7. `python3 tools/save_debug.py simulate <save> explore` over a pile-bearing floor matches the
   real O's route (twin parity).
8. Guide review: every new/changed entry matches the approved drafts word-for-word (the O bullet
   and the on-foot/ship-cargo split above are the known must-edits).
9. Save → quit → Continue: identical map state (remaining piles) and bandolier.
