# Tutorial Mode

## Overview

New players bounce off spacehack because the game's depth (two combat
systems, economy, missions, main quest) is only documented in the in-game
guide and HUD hints — both passive. This adds an **active, scripted
tutorial**: a menu option that drops the player into a guided first run
as a **Human Merchant** on Earth, walking them through their first
bounty, first ship loadout, first space combat, first loot pickup, first
jump (which triggers the main quest signal), gearing up for Mars, their
first ground combat, and their first level-up (spending skill points on
the `C` character screen) — via a sequence of dismiss-only modal popups
that fire exactly when the player reaches each beat.

The tutorial **is** the real game, not a separate mode: the player keeps
credits, XP, the Crimson Jack mission, and the main quest. When the final
popup fires, tutorial hints stop and the run continues as a normal
sandbox.

## Goals / non-goals

**Goals**
- Teach the core loop: move → talk → accept mission → equip → launch →
  auto-nav → fight → loot → jump → explore → ground combat.
- Teach the space-combat UI vocabulary (AP, multi-weapon firing, energy,
  shield regen, dodge) and the ground-combat vocabulary (AP, LOS, range,
  cover) *at the moment the player first needs it*.
- Make the main quest the tutorial's narrative spine (the signal is
  triggered by the tutorial's required jump, exactly as designed).

**Non-goals**
- No hand-holding in normal New Game runs. Tutorial state is entirely
  opt-in via the menu.
- No new combat mechanics, economy changes, or content. Purely
  guidance + a few deterministic spawn/setup tweaks.
- No changes to existing main-quest design; the tutorial rides it.

## How it works

### Entry point

`ui.py` title menu gains **Tutorial** below Continue:

```
New Game
Continue
Tutorial   <-- new
Exit
```

- `TitleMenuOutcome.TUTORIAL` added; `update_title_menu` max index 2→3.
- `__main__.run()`: `TUTORIAL` → `_run_game(context, "human", "merchant", tutorial=True)`.
  No species/class menus, no confirm screen — the tutorial **forces**
  Human Merchant (the most approachable class, and the one whose story
  framing fits a rookie pilot).

### Tutorial state (GameContext)

Three new fields (all survive save/load — tutorial runs autosave like
any other game):

| Field | Type | Purpose |
|-------|------|---------|
| `tutorial_mode` | `bool` | True for tutorial runs; gates all tutorial behavior. |
| `tutorial_steps` | `set[str]` | Step ids already fired (idempotent). |
| `tutorial_complete` | `bool` | True after the final popup; `tick()` then stops. |

No module-level globals — this lives entirely on `ctx` (the save/load
contract's preferred shape).

### The tutorial module — `src/spacehack/tutorial.py`

New domain module (kept small; the runtime pattern already exists in
`main_quest/_act0.py`). Contents:

- `TUTORIAL_MISSION_IDS = frozenset({"bhguild_sol_scout"})` — the only
  mission offered in tutorial mode.
- `TUTORIAL_CREDIT_BONUS = 250` — merchant starts with 75$; laser (30$)
  + shield (60$) + kinetic rifle (80$) = 170$; 325$ total gives margin.
- `tick(ctx)` — one call per outer game-loop iteration (next to
  `main_quest_module.check_quest_gates(ctx)` in `_run_game`). Runs only
  when `ctx.tutorial_mode and not ctx.tutorial_complete`. Evaluates step
  conditions in order; fires **at most one** modal per call (dismiss-only
  overlay reusing the `show_gate_popup` box style); marks the step done.
- `notify_pickup(ctx)` — called from `__main__`'s `P` handler after
  `_pickup_loot_near`; fires the jump-teaching step when nearby loot was
  cleared.
- `maybe_space_combat_intro(ctx)` — called from
  `combat/_encounter.py::_handle_combat_encounter` **before** `_rs_init`
  (space combat intro fires before the combat UI takes over).
- `maybe_ground_combat_intro(ctx)` — called from `_run_ground_combat_tick`
  **before** `_ground_init` (no combat-module change needed).

Each step is data-defined: `(id, condition_fn(ctx), modal_text)`.
Conditions are pure/cheap predicates where possible so they're unit
testable without a `tcod` context.

### Mission board forcing

`mission.fill_empty_slots(...)` already receives `ctx`. In tutorial mode:
- The `available` static pool is intersected with `TUTORIAL_MISSION_IDS`
  (so only "Wanted: Crimson Jack" ever appears on Earth's bounty board;
  merchant/bar boards end up empty → "no work right now").
- Procedural generation is skipped entirely (no delivery/bounty clutter).

Tutorial setup also pre-seeds the Earth bounty board with
`bhguild_sol_scout` in slot 0 and stamps `last_refresh_month` so the
first talk doesn't refill it.

### Bounty placement — already correct

`bhguild_sol_scout` targets **Sol** (pirate scout, squad 1, loadout 20%).
`_pick_bounty_spawn_pos` picks the first unused landmark sorted by
distance from the system centre, and Mercury is Sol's closest planet —
so the first Sol bounty (Crimson Jack) already spawns just east of
Mercury with zero changes. The tutorial's "press G and auto-nav toward
Crimson Jack near Mercury" teaching is accurate out of the box.

## The step script (the user's 14 beats)

All modals are dismiss-only (ENTER/ESC), styled like the existing
gate popup. Text is short — one idea per popup.

| # | Step id | Fires when | Teaches |
|---|---------|-----------|---------|
| 1 | `intro` | first `tick` after setup | What the tutorial covers; movement keys; HUD layout; `?` = guide, ESC = menu; "first job: the Bounty Master (D), SE guild hall." |
| 2 | `first_move` | first successful city move | Bump the Bounty Master to talk; choose work to see the contract. |
| 3 | `accepted_crimson` | active mission id == `bhguild_sol_scout` | `Q` = quest log. Before launching: buy a 2nd Light Laser + Shield Mk. 1 at the Mechanic terminal in the space port (credits are pre-funded). |
| 4 | `equipped_loadout` | ship has ≥2 energy weapons **and** ≥1 shield module | Bump your ship in the space port and choose **Launch**. |
| 5 | `launched` | first frame in space | Bounty ping is in the log; press `G` for auto-nav and pick Crimson Jack (near Mercury). |
| 6 | `space_combat_intro` | first space combat, before the combat UI | Space combat 101: AP per turn, firing multiple weapons, energy generation/consumption, shield-regen setting, movement + dodge chance. |
| 7 | `loot_dropped` | space combat done, loot entity present | Crimson Jack dropped loot (`%`); press `P` to pick up (works in space + ground, incl. diagonals). |
| 8 | `picked_up_loot` | `notify_pickup` — nearby loot cleared | How to jump: fly to a jump gate (`J`); each jump costs 10 fuel (watch the HUD gauge). Jumping out of Sol triggers the main quest. |
| 9 | `signal_triggered` | `prologue_signal` step becomes completed | The signal resolves to **Mars** — that's your main quest. Jump back to Sol, land on Earth, gear up at the Armory before heading out. |
| 10 | `earth_armory` | land on Earth while signal completed | Visit the Armory terminal (`A`) and buy two Kinetic Pistols + a Pistol Rounds stack for ground combat. One-handed, so both fit and volley for 12 damage at 1 AP; pistol rounds cost 1$ each; reload with `R`. |
| 11 | `armed_ground` | a ground weapon is equipped | Launch and press `G` to auto-nav to Mars; explore the signal source. |
| 12 | `mars_ground_combat_intro` | first ground combat, before the combat UI | Ground combat 101: AP, LOS-based aggro, range, cover, weapons/armor, loot. |
| 13 | `level_up` | first ground combat ends | Guarantees the player reaches level 2 (topped-up XP if needed), then teaches `C` = character screen and spending skill points (+1/point, cap 100). |
| 14 | `finale` | `level_up` shown **and** all skill points spent | Final tips (trade, other guilds, `?` guide, permadeath) + "the galaxy is yours". Sets `tutorial_complete`. |

Steps 1–5, 7, 9–11, 14 fire from `tick()`; steps 6 and 12 fire from the
two combat hooks; step 8 fires from `notify_pickup`; step 13 fires from
`notify_ground_combat_ended`.

### Setup tweaks in `_run_game` (tutorial only)

- credits += 250 (merchant 75 → 325)
- bounty board pre-seeded with `bhguild_sol_scout`
- `ctx.tutorial_mode = True` (rest is pure `tick()` behavior)
- Main quest left untouched — the signal fires normally on the tutorial's
  required jump out of Sol.

## Domain changes

| File | Change |
|------|--------|
| `src/spacehack/tutorial.py` | **new** — step table, `tick`, hooks, modal renderers. |
| `src/spacehack/ui.py` | `TitleMenuOutcome.TUTORIAL`; menu order New Game / Continue / Tutorial / Exit; `_max` 2→3; `Tutorial` highlightable. |
| `src/spacehack/__main__.py` | `run()` routes TUTORIAL → `_run_game(..., tutorial=True)`; `_run_game(tutorial=False)` param + setup tweaks; `tutorial.tick(ctx)` call in loop; `notify_pickup` in `P` handler; `maybe_ground_combat_intro` in `_run_ground_combat_tick`. |
| `src/spacehack/game_context.py` | `tutorial_mode`, `tutorial_steps`, `tutorial_complete` fields. |
| `src/spacehack/saveload.py` | serialize/restore the three tutorial fields. |
| `src/spacehack/mission.py` | `fill_empty_slots` tutorial filter (whitelist + no procedural). |
| `src/spacehack/combat/_encounter.py` | `maybe_space_combat_intro(ctx)` before `_rs_init`. |
| `src/spacehack/help.py` | Guide section for Tutorial mode (menu option + what it covers). |
| `tests/test_tutorial.py` | **new** — see Testing. |
| `tests/test_saveload.py` | tutorial-field round-trip case. |

## Testing

- `tests/test_tutorial.py`:
  - `fill_empty_slots` in tutorial ctx → only `bhguild_sol_scout`, no
    procedural missions, other boards empty.
  - `_has_loadout(owned_ship)` predicate (≥2 energy weapons + shield).
  - `mark_step` idempotence + `tutorial_complete` stops `tick` (with a
    stub ctx).
  - credits-bonus constant sanity (covers laser+shield+rifle).
- `tests/test_saveload.py`: tutorial fields survive a round-trip.

## Phases

### Phase 1 — Foundation & menu

- [x] `TitleMenuOutcome.TUTORIAL` + title menu row + navigation.
- [x] `run()` routes Tutorial → `_run_game("human","merchant",tutorial=True)`.
- [x] GameContext fields + saveload serialization.
- [x] `tutorial.py` skeleton: step table, `tick`, gate-popup-style modal.
- [x] `fill_empty_slots` tutorial filter + board pre-seed + credit bonus.
- [x] `intro` + `first_move` steps live.

**Playtest notes:** all 254 tests pass (8 new tutorial tests); smoke green.
Reviewer pass found two fixes, both applied: `_any_loot` now guards a
`None` game_map, and `notify_pickup` fires only after the space map is
clear of loot (the "after picking up loot" beat). Window-close mid-popup
marking a step done was accepted as low-severity (autosaved tutorial).

**PLAYTEST:** Tutorial from the title → no species/class menus → Human
Merchant starts on Earth → `intro` popup fires on first frame → take a
step → `first_move` popup fires once → no popups on subsequent moves →
ESC-quit + Continue resumes with tutorial state intact.

### Phase 2 — Mission & loadout flow

- [x] `accepted_crimson` (fires on accepting Crimson Jack).
- [x] `equipped_loadout` (predicate on weapons+modules).
- [x] `launched` (first frame in space).

**Playtest notes:** the three steps shipped in the Phase 1 step table;
Phase 2 verified the trigger chain end-to-end. Loadout purchases
mutate `ctx.player_owned_ship` via `ship._install_weapon` /
`_install_module`, so the predicate sees them next tick. Added
`TestTickOrder` (monkeypatched `_show_step` recorder): accept →
loadout → launch fire in order, each once; buying early is gated on
having accepted the contract; launching un-equipped skips the launch
popup and the script self-heals from the combat beat onward. Other
Earth boards stay empty (whitelist filter + no procedural). 258 total
tests pass.

**PLAYTEST:** Talk to Bounty Master → only Crimson Jack offered → accept
→ popup teaches `Q` + mech terminal → buy 2nd light laser + Shield Mk.1
at the mech terminal → popup → bump ship → Launch → popup in space.
Verify credits cover the purchases. Verify other NPCs have no work.

### Phase 3 — Space combat & loot

- [x] `maybe_space_combat_intro` hook in `_handle_combat_encounter`.
- [x] `loot_dropped` (space loot entity present).
- [x] `picked_up_loot` + `notify_pickup` hook in `P` handler.
- [x] `signal_triggered` (on `prologue_signal` completion).

**Playtest notes:** all hooks/steps shipped with the Phase 1 table;
Phase 3 added `TestSpaceCombatAndLoot`: the combat intro fires once
before the battle UI; loot popup → jump-lesson fallback once the space
map clears; `notify_pickup` waits for actual loot removal (P on loot
that stays on the map does nothing); the signal popup fires after the
jump lesson and is gated on it. `maybe_trigger_signal` is confirmed
wired in `navigation._jump_to_system` (jump out of Sol), so the
signal beat uses the existing main quest — no changes needed. 263
total tests pass.

**PLAYTEST:** Auto-nav to Crimson Jack near Mercury → first combat opens
with the combat-intro popup BEFORE the battle UI → win → loot popup →
`P` picks it up (incl. diagonal) → jump popup → jump out of Sol → signal
popup + transmission → jump back (fuel is tight but affordable — verify
starter fuel 80 covers 2 jumps + travel).

### Phase 4 — Mars, ground combat & finale

- [x] `earth_armory` + `armed_ground` steps.
- [x] `maybe_ground_combat_intro` hook in `_run_ground_combat_tick`.
- [x] `level_up` step + `_ensure_level_up` XP top-up (guaranteed L2).
- [x] `finale` moved to a tick step gated on all skill points spent.
- [x] Guide section + full test suite.

**Playtest notes:** the armory equips purchases straight into
`ctx.equipped_ground_weapons`, so `armed_ground` fires on the first
armory buy. Added `TestMarsAndFinale`: armory popup fires only after
the signal beat and only on Earth; armed popup follows the armory
beat (buying early still gets the armory popup first); ground-combat
intro fires once; the finale fires once, sets `tutorial_complete`, and
silences every hook + tick afterwards; a stray combat resolution before
the ground intro cannot end the script.

Post-playtest refinement: the finale originally fired immediately at
combat end, but the player should also learn leveling. `level_up` now
fires at combat end (XP topped up to guarantee level 2 — a single
Mars cave fight may not reach the 90 XP threshold), teaching `C` =
character screen + skill point allocation; the finale is gated on
`level_up` shown **and** `player_skill_points <= 0`, so the script
ends only after the points are actually spent. Verify on the final
playtest: LEVEL UP popup → `C` → spend all 9 points → YOU'RE READY →
tutorial complete. 272 total tests pass.

**PLAYTEST (final, passed):** Land on Earth → armory popup → buy two
kinetic pistols + pistol rounds → popup → launch → `G` to Mars →
explore signal source → first ground combat opens with intro popup →
win → LEVEL UP popup → `C` → spend all skill points → YOU'RE READY
finale → no further popups; run continues as normal sandbox (main quest
door chain intact). Save/Continue through the whole arc.

## Acceptance criteria

- [x] Tutorial accessible from the title menu, below Continue.
- [x] Forces Human Merchant; skips species/class/confirm screens.
- [x] Only Crimson Jack is offered on Earth; credits suffice for the ship
      loadout (2nd laser + shield) and the armory pistols + ammo.
- [x] All user beats fire exactly once, in order, at the right moment.
- [x] Combat intros appear before the combat UI, not during/after.
- [x] Tutorial autosaves + Continue resumes mid-script.
- [x] After `finale`, no more popups; sandbox continues (main quest live).
- [x] Non-tutorial New Game behavior is byte-for-byte unchanged.

## Decisions (confirmed)

1. **Shared save slot** — tutorial runs autosave/continue through the
   single roguelike save file, same as New Game. Continue resumes a
   tutorial run mid-script.
2. **No skip affordance** — the script is short and ESC-quit works
   anytime. No skip key.
3. **Bounty placement unchanged** — the standard landmark picker already
   puts Crimson Jack near Mercury (see above). No code change.

## Open questions

(none)
