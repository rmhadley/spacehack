# DESIGN: Auto-pickup — walk-over collection

**Status:** OPEN — drafted 2026-09-27, briefs approved same day. Rulings SETTLED 1–9 recorded;
Implementation briefs for phases 1–3 APPROVED with all three ADVISE reviewer passes folded.
Build queue: `/implement-phase 55.1` first.

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
presses P and resumes. After this (SETTLED 5–7):

- **The halt stays — for every loot class (SETTLED 7).** A fresh pile stops the run exactly as
  today, in O and G both; the halt machinery (`interesting_at`, `_stop_if_fresh`, ignore-memory)
  is untouched by this arc.
- **Pickable piles become first-class targets.** The goal set widens from "nearest unseen cell"
  to "nearest target, whichever is closer — a pickable pile or the fog edge" (SETTLED 5,
  verbatim: "autoexplore should target the nearest target, nearest target being either autopickup
  or nearest unexplored fog"). Pressing O again after a halt resumes the run, routes it over the
  spotted pile (walk-over collects), then pushes the fog — **the halt is the news, the resume is
  the collection** (SETTLED 7). The run ends only when no unseen cells AND no pickable piles
  remain reachable.
- **Arrival refusals skip silently (SETTLED 6).** A pile the probe refuses mid-run (bandolier
  full for that caliber, hold full, toggle off) — the run visibly steps over it and continues; a
  full rifle reserve never blocks scooping grenade piles ahead. A refused pile still halts on
  first sighting like any loot (sight-stops are inventory-independent) but is not a target and
  never re-halts.
- Never-class piles are unchanged everywhere (halt + ignore-memory). The underfoot exemption at
  run start is unchanged. Goto is untouched outright — picker exclusion, halts, all of it.

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
- Auto-explore keeps DCSS manners: halts are the news (one stop per discovery), and every resume
  collects — by the time a floor is cleared, its ammo and credits are too.

## Phases

- [ ] 1. **Walk-over core + P remainder alignment** — probe + apply for the three classes at
  movement arrival (both theaters, manual + all three stepper/auto-nav paths); ammo
  remainder-splitting; silent refusal (the probe never logs); existing log lines; the P flow's
  partial fit aligns with leave-remainder (SETTLED 4, amending doc 52); the tutorial teaches
  both verbs — walk-over for Jack's salvage, P for his guaranteed laser (SETTLED 8). Tests:
  per-class pick / refuse / partial-split,
  every movement path, a sabotage-proven regression pin on the walk-over hook. Guide-diff item:
  none (guide lands with phase 3, when the behavior finalizes).
- [ ] 2. **The toggle** — `[gameplay] auto_cargo_pickup` in config.toml + the title OPTIONS row;
  toggle-off turns trade debris back into ordinary P-only loot (refused-probe class). Guide-diff
  item: the AUTO CARGO PICKUP row line in "Options & Display" **plus that section's intro
  rewording** (its "presentation only" claim becomes false).
- [ ] 3. **Auto-explore targeting + guide pass** — pickable piles join the goal set (SETTLED 5:
  nearest target = pile or fog edge); **halts unchanged for every loot class, O and G alike**
  (SETTLED 7) — a fresh pile stops the run as today, and pressing O again resumes and collects;
  arrival refusals skip silently (SETTLED 6); ignore-memory, the underfoot exemption, and goto
  are all untouched. Guide audit: classify every pickup/loot hit (P key, nearby-loot,
  ammo/ammunition carry limits, auto-walk, on-foot vs ship cargo) in the brief; guide text
  drafts get user approval in the brief before landing.

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
6. **(2026-09-27, user; scope narrowed by 7)** A pile the run refuses **on arrival** (bandolier
   full for that caliber, hold full, toggle off) is skipped without halting — the pile visibly
   stays and the run continues. (This entry originally added "auto-class piles never halt
   auto-explore" — SETTLED 7 restores the newly-visible halt; this entry covers arrival
   refusals only.) Never-class piles keep the existing halt.
7. **(2026-09-27, user, verbatim)** "It should still halt. but if you press auto explore again
   it will pick up. I'm thinking like dcss auto explore works." — the newly-visible halt stays
   for ALL loot classes, in O and G: the halt machinery is unchanged from today (no
   `interesting_at` reclassification, no goto changes). The halt is a notification stop —
   pressing O again resumes the run, pickable piles are targets (SETTLED 5), and the resumed
   run detours to collect them via walk-over before pushing the fog. A pile the probe refuses
   still halts on first sighting like any loot (sight-stops stay inventory-independent) but is
   not a target and never re-halts.
8. **(2026-09-27, user, verbatim)** "I'd prefer to keep the P teaching in the tutorial. Can we
   make the tutorial jack drop things that auto pickup and don't auto pickup? maybe we can teach
   both?" — Crimson Jack's drop is split so the tutorial teaches BOTH verbs: his cargo stays
   walk-over salvage (auto-class), and he gains one guaranteed P-only weapon drop carried on his
   spec and honored by the shared kill-drop path — data-driven, no tutorial special-case.
   Refinement, same day (verbatim): "It's the tutorial... let's make it drop a med laser. teach
   the user about ship upgrades." — the weapon is a **Medium Laser** (`medium_laser` in
   data/weapons/lasers.py:17), deliberately a tier above the starter Light Lasers: the drop's
   second lesson is that loot can UPGRADE your ship, with the prompt pointing at the Loadout
   screen to fit it. The `loot_dropped` prompt teaches both verbs; the beat still completes only
   when no loot remains.
9. **(2026-09-27, user: "approved")** The three Implementation briefs stand as written, and both
   prose drafts are approved verbatim — the tutorial `loot_dropped` prompt v2 ("Crimson Jack was
   destroyed - and dropped loot (%).\n\nFly over the salvage and it's collected automatically.
   His Medium Laser is an upgrade - fly next to it and press 'P' to take it, and fit it from the
   Loadout screen next time you dock. 'P' works in space and on the ground, and it reaches loot
   on diagonal squares too.") and the guide "Options & Display" intro ("These settings change
   how the game looks and plays. They are saved separately from game saves."). Phase 1 is
   buildable: `/implement-phase 55.1`.

## Open questions

None — questions 1–2 (P-flow overflow alignment; probe timing for auto-explore stops) were
resolved by SETTLED 4 and 5–6 respectively on 2026-09-27.

## Implementation briefs (APPROVED 2026-09-27 — SETTLED 9)

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
- `src/spacehack/tutorial.py:138-143` + `data/enemies/pirates.py` (Crimson Jack's spec) —
  **teach both verbs + the upgrade lesson (SETTLED 8).** Jack's natural cargo drop stays
  walk-over salvage; his spec gains a guaranteed weapon drop — a **Medium Laser**
  (`medium_laser`, data/weapons/lasers.py:17) — honored by `_spawn_loot_drops`
  (combat/_actions.py:335) using the existing ship-weapon loot payload shape
  (`loot._ship_weapon_loot_entry`, loot.py:207): one P-only entity at the wreck, data-driven,
  no tutorial special-case. The Medium Laser is deliberately a tier above the starter Light
  Lasers — the drop's second lesson is that loot can upgrade your ship; the fight is already
  over when it lands and the sell value is trivial, so the balance impact is accepted by the
  ruling. The `loot_dropped` prompt is reworded to teach both — draft: **"Crimson Jack was
  destroyed - and dropped loot (%).\n\nFly over the salvage and it's collected automatically.
  His Medium Laser is an upgrade - fly next to it and press 'P' to take it, and fit it from the
  Loadout screen next time you dock. 'P' works in space and on the ground, and it reaches loot
  on diagonal squares too."** (approved verbatim — SETTLED 9). The beat machinery needs no change:
  `picked_up_loot` waits for `not _any_loot` (tutorial.py:322-327), so the beat completes only
  after BOTH the fly-over salvage and the P'd laser are cleared — `notify_pickup` fires from
  the P path today and from the space walk-over apply (this brief).
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

**Stop point:** no options/config work (phase 2); no auto-explore changes at all (phase 3 widens
targeting only — halts never change in this arc); no guide edits (the tutorial line above is
tutorial, not guide); no new pickup classes.

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
9. Auto-explore still halts at newly-visible piles (halts never change in this arc), but piles
   crossed on the route are scooped.
10. Space G auto-nav onto/over debris → scooped en route (interrupt a transit over a debris field).
11. New game through the Jack fight: fly over the salvage → collected automatically (existing
    log lines) while his Medium Laser stays put; press P next to it → picked; the beat advances
    to JUMPING only after BOTH are cleared; the two-verb prompt (with the fit-it-at-Loadout
    upgrade pointer) reads correctly; docked, the Loadout screen fits the salvaged laser.
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
  from game saves."** (approved verbatim — SETTLED 9).

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

### Phase 3 — Auto-explore targeting + guide pass

**Scope (files / hook points):**

- `src/spacehack/auto_pickup.py` — `pickable_positions(ctx, game_map)`: every **seen** auto-class
  pile whose **silent probe** accepts (recomputed per step; state can change mid-run). Per-step
  cost is noise beside the existing per-step passes (`steps_aside_ids`, `_blocker_index`,
  `_stop_if_fresh`), but the probe must stay pure AND quiet — including the ammo caliber's
  catalog resolve — because it now runs per seen pile per step.
- `src/spacehack/autoexplore.py` — **goal-widening only.** `_plan_step` (autoexplore.py:407)
  gains an optional `goal_cells` frozenset: a cell is a goal if unseen OR a member — BFS
  nearest-wins then IS SETTLED 5 (nearest pile or fog edge, whichever is closer);
  `next_explore_step` passes it through; `run_auto_explore` computes it per step. Planner
  invariants for the build: **goal membership never overrides passability or
  transition-non-entry** (the non-walkable/transition `continue` at :362 precedes any goal
  check — a pickable pile on a stairs/exit tile is simply unreachable and the run may end with
  it visible; accepted, not special-cased), equal-distance ties resolve by the existing
  deterministic enqueue order, and the underfoot exemption leaves its one distance-zero
  exception (a pickable pile can remain under the player at run end).
- **Halts are untouched (SETTLED 7).** `interesting_at`, `_ENTITY_INTEREST_FLAGS`,
  `_stop_if_fresh`, known-seeding, and ignore-memory behave exactly as today for every loot
  class — no reclassification, no fall-through change. Goto is untouched outright:
  `next_goto_step`, the picker tables (`_GOTO_TILE_TITLES` :96 / `_GOTO_ENTITY_TITLES` :101),
  and its halts. The halt-resume flow this creates: a fresh pile stops the run as today;
  pressing O again resumes with pickable piles as targets (SETTLED 5) — the resumed run detours
  to collect via walk-over, then pushes the fog; a refused pile halts once on sighting
  (sight-stops are inventory-independent) and is simply not a target.
- `src/spacehack/debug_session.py` — `_action_explore` drives `next_explore_step` directly
  (twin-path rule): it passes `goal_cells` too, so `save_debug simulate … explore` matches the
  real O (the move twin was wired in phase 1).
- Guide: audit the single-file corpus `data/guide/__init__.py` for: P key / "pick it up" /
  "nearby-loot" / "P: collect nearby loot", loot, auto-explore / auto-walk, ammo / ammunition /
  per-caliber carry limit / battlefield pickups, trading & cargo prose. The O bullet
  (:527-530 — stops + "loot you chose to leave behind") **stays true** under SETTLED 7 and
  should need no edit; the known must-edit is the on-foot/ship-cargo split (:555-556 — "Loot
  found on foot is handled separately from ship cargo" is contradicted by trade walk-over
  straight to the hold). Every new or changed entry's exact text is approved HERE, in this
  brief, before the build lands it.

**Build order:** planner goal-widening (pure + tests) → run-loop wiring → debug_session twin →
guide pass (after prose approval).

**Binding rulings:** SETTLED 5 (nearest target = pickable pile or unexplored fog; not a
post-frontier stage); SETTLED 6 as narrowed (arrival refusals skip silently, never a halt);
SETTLED 7 (halts unchanged for every loot class in O and G; the resume collects); underfoot
exemption, ignore-memory, and goto all untouched.

**Required tests:** nearest-wins ordering both ways (pile nearer than fog detours first; fog
nearer wins) **plus the tie-break pin**: a goal member at BFS depth d fires from its depth d-1
parent before a fog-adjacent goal at depth d during depth-d expansion; a refused pile is not a
target **but still halts on first sighting** (the existing fresh-loot halt tests stay green
unchanged — no existing test is invalidated by this phase); the run ends only when no unseen
cells and no pickable piles are reachable (underfoot exception included); resume-after-halt
detours to the halted pile before the fog; trade toggle Off → trade piles are not targets;
goto's picker still excludes loot; planner purity preserved (headless fakes).

**Stop point:** no halt changes anywhere; no goto changes; no new pickup classes; no changes to
stop messages beyond the existing lines; no doc-100 in-game menu work (the future menu can
mirror the row).

**Playtest checkpoint:**

1. A fresh pile halts the run as today ("You notice a cache of supplies and stop.").
2. Press O again → the run detours to the halted pile first, scoops it via walk-over, then
   pushes the fog.
3. A cluster revealed at once → one halt; the resume collects the whole cluster without further
   halts.
4. A refused pile (full caliber): halts on first sighting like any loot; the resume does not
   target it; stepping over it mid-run never halts; other calibers still collected.
5. Nearest-target both ways: a nearer pile beats the fog; nearer fog beats a pile; a combat
   interrupt during a detour stops the run through the existing machinery.
6. Trade toggle Off → trade piles are not targets (ammo/credits still are).
7. G unchanged: loot absent from the picker, halts at fresh loot exactly as today.
8. `python3 tools/save_debug.py simulate <save> explore` over a pile-bearing floor matches the
   real O's route (twin parity).
9. Guide review: every changed entry matches the approved drafts word-for-word (the
   on-foot/ship-cargo split is the known must-edit; the O bullet should be untouched).
10. Save → quit → Continue: identical map state (remaining piles) and bandolier.
