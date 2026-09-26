# DESIGN: Flee — the world's exits work during combat

**Status: all open questions ruled 2026-09-26 (SETTLED 1-3); both
Implementation briefs APPROVED. Nothing implemented — ready for
`/implement-phase 54.1`.**

## Overview

Combat gets a flee mechanic by unlocking the world's existing exits
rather than adding a new action: **landing on planets and jumping
through gates during space combat, using stairs during ground
combat.** No "flee" button, no special-case mechanic — the exits are
always the exits. The risk is the **reaction volley**: everything that
could hit you right now gets one parting shot as you go.

User rulings (2026-09-26, conversation):

> "I've finally thought of a way to 'flee' during space combat:
> allow landing on planets/using jump points while in combat."

> (1) adjacent escape allowed; (2) landing/jumping already resets
> the map — clean exit; (3) cost is fine (fuel/time); (4) no chase
> through jumps; (5) ground combat gets stair dancing.

> "to add some risk to it. anything in range gets 1 AP worth of
> reaction time to react"

> "yes. the reaction shots can kill you. that's the risk. dcss works
> this way."

## The mechanic (uniform, both theaters)

### Space: land or jump while in combat

- The planet-approach menu, station dock, and jump-gate bump fire
  from inside the combat loop — same interaction, same prompts, no
  combat-state gate blocking them (SETTLED 1: stations are exits).
- **Adjacent escape is allowed**: you can trigger the exit with
  hostiles at point-blank range. No disengage requirement.
- **Map reset = clean exit**: landing/jumping regenerates the space
  map (existing behavior); the pirate vanishes with it. No chase, no
  memory, no waiting hostile at the destination.
- **Cost is existing**: jumps burn 10 fuel; landing puts you on a
  surface where you must lift off through the same space. The
  economic pressure is already tuned.

### Ground: stair dancing during combat

- The stairs tile fires its floor transition from inside the combat
  loop — bump the stairs during a fight, spend the AP to step
  through, the fight ends, the transition runs.
- **The fight ends at the stairs**, not at VICTORY/DEFEAT: survivors
  on the exited floor revert to patrol (locks released, combat state
  cleaned up). The delve attrition economy keeps its wounds — you
  arrive on the next floor at whatever HP you fled with.
- Uses the existing stairs/exit machinery — no new interaction, no
  new UI.

### The reaction volley (the risk)

- **When an exit is triggered during combat, every enemy that could
  hit you right now gets one attack.** In range + LOS, one shot or
  swing each, then you're out.
  - Space: every hostile ship in weapons range fires once.
  - Ground: every enemy in range and LOS attacks once.
- **Reaction shots CAN KILL.** Death on the stairs or at the gate is
  the gamble — fleeing at low HP from multiple adjacent enemies is a
  coin flip on their damage rolls. "I fled with 8 HP into three
  parting shots" is a story, not a gotcha (user ruling, DCSS
  precedent).
- No movement in the reaction — enemies don't chase or reposition,
  they just get their parting shot from where they stand.
- Clean calculation: the player can see who's in range and roughly
  what they'll dish out before committing to the exit.

## Design intent

- **Fleeing is a decision, not a bail-out.** Without the reaction
  volley, "am I losing? press the exit" collapses the decision.
  With it, the calculation is "can I afford what the room will dish
  out in one volley?"
- **Surrounding is the punishment.** One enemy at range = one
  parting shot = usually fine. Three adjacent = three hits = the
  real cost of getting flanked. Teaches the same lesson as the
  shotgun rifleman: don't get surrounded.
- **The delve economy gets a pressure valve.** Stair dancing lets
  you skip a guardian you can't fight, at the cost of the XP/loot
  and the wounds you carry down. It makes delve depth a choice
  rather than a commitment.
- **No new machinery.** Landing, jumping, stairs, enemy fire — all
  existing. The only new code is the unlock (exits fire from inside
  combat) and the volley (one filtered round of enemy attacks).

## Phases

- [ ] 1. **Space flee** — unlock landing + jump interactions from
  inside the space combat loop; the reaction volley (every hostile
  in range fires once before the transition); the volley CAN kill.
- [ ] 2. **Ground stair dancing** — the stairs tile fires its
  transition from inside the ground combat loop; combat cleanup on
  exit (locks released, survivors revert to patrol); the reaction
  volley (every enemy in range + LOS attacks once); death on the
  stairs.

Each phase gets its Implementation brief at its own refine time —
both briefed 2026-09-26 (below). Close-out reminder: SYSTEMS.md's
"Absent: no disengaging once a space fight starts — fights run to
VICTORY" entry is amended when phase 1 closes.

## SETTLED 1 (2026-09-26, user — the volley's timing and the death threshold; open questions 1-2)

- **Open question 1 RULED — the volley fires AFTER the confirm.**
  The existing exit prompt runs first (planet approach menu,
  jump-gate "ENTER jump"); the committing choice triggers the
  volley; the volley resolves visibly; then the transition. You see
  what the room charged you before the map changes. Cancelling
  (ESC / fly past) fires nothing.
- **Consequences of the uniform rule (flagged for veto at brief
  approval; ADVISE-reviewed 2026-09-26):**
  - Every committing choice that leaves the combat map triggers
    the volley — Land, Explore, Dig, dock, jump alike. Only a
    cancel is free. They are all exits; the mechanic knows one
    rule.
  - **Stations are exits.** Docking at a station mid-fight is the
    same flee (the dock bump resolves through the same three-way
    exit resolution as out-of-combat).
  - **Refusals precede the volley.** A refused commit — dark-dock
    refusal, no fuel for the jump, an Explore/Dig build failure —
    leaves the map unchanged and fires nothing. The volley is the
    price of leaving; no leaving, no price. Full no-op semantics
    (no AP, position restored, same turn) ruled at brief approval —
    SETTLED 3.
- **Open question 2 RULED — death wins.** If the volley kills you,
  the transition never runs. You die at the threshold: the normal
  death path (doc-53 tombstone written from the combat loop,
  autosave deleted), no landing, no jump. DCSS behavior.

## SETTLED 2 (2026-09-26, user — boarding interiors and teaching; open questions 3-4)

- **Open question 3 RULED — boarded hulls get the same rule.** The
  hull's exit tile is the exit: step on it mid-fight, eat the
  crew's volley, you're back in space. No special case in code —
  the same unlock covers boarded interiors. The gamble is real:
  the hull was consumed at entry (doc 40), so fleeing forfeits the
  interior's loot/XP and there is no re-boarding.
- **Open question 4 RULED — one guide line per theater, no
  tutorial.** No tutorial modal (discoverable — players already
  know stairs and gates; today's "Blocked." is the only habit to
  break). The guide's Combat section and the ground section each
  gain ONE line: exits work during combat, everything in range gets
  one parting shot. Exact wording proposed in each brief below;
  diffs ride the playtest checklists.

## SETTLED 3 (2026-09-26, user — brief approval: the three flagged consequences)

- **All committing exits trigger the volley.** Ruled yes — Land,
  Explore, Dig, dock, jump alike; one rule.
- **Anything that is an exit is a flee chance.** User wording:
  "yes, anything that is an exit is a flee chance" — stations
  included; the rule covers exits as a class, not an enumerated
  list.
- **A refused exit is a full no-op.** User wording: "failure to
  use the exit should result in no change. no AP lost, back in the
  fight just as you were before." — no volley, no AP spent, no
  position change (a ground step onto a refusing transition is
  refunded: position restored, AP back), same turn, fight
  continues exactly as before the attempt. Build note: the
  momentary sight reveal from the refunded ground step may
  persist — position, AP, and turn state are what restore.
- **Both Implementation briefs APPROVED** with these rulings; the
  two guide wordings (Combat revision, Ground Exploration line)
  are settled as quoted in the briefs.

## Open questions

None open — all four ruled in SETTLED 1-2 (2026-09-26).

## Implementation brief — Phase 1: space flee (APPROVED 2026-09-26)

**Scope (exact files / hook points)**

- `src/spacehack/combat/_loop.py` — `_dispatch_combat_action`'s
  MOVE branch (~line 586): in space, a failed move routes to an
  exit check before logging "Blocked." — reusing
  `_resolve_space_wall`'s three-way resolution order
  (`game_interactions.py:64-72`): station bump → station dock,
  planet bump → the planet menu (Explore/Dig/Land), jump gate →
  the jump-confirm menu ("ENTER jump / ESC fly past"). Walls and
  asteroids log "Blocked." as today. Routing is space-rules-only;
  ground gets nothing here (phase 2).
- The volley fires IN-LOOP, after the committing menu choice and
  before ANY map build (`_build_surface_dungeon`,
  `enter_dig_site`): new rules hook `reaction_volley(console, ctx,
  game_map)` on `combat/_rules_space.py` — every live hostile
  whose weapons reach the player fires ONE shot, reusing the
  enemy-shot machinery (`_ai._resolve_enemy_shot` /
  `_enemy_attack` / `_animate_enemy_shot` / `_enemy_attack_line`,
  weapon selection via `_volley_picks`), no movement. Refusals
  resolve BEFORE the volley (SETTLED 1): split
  `_resolve_planet_wall` at the outcome branch so a refused commit
  (dark dock, jump fuel, build failure) fires nothing.
- BOARD-seam result flow (the inventoried mechanism for a world
  transition out of a live fight): **the loop never runs the
  transition.** Died to the volley → result "DEFEAT", break.
  Survived → break with a new outcome **"FLED"** + payload on
  CombatResult naming the chosen transition (the `boarded_spec_id`
  pattern, `combat/_types.py`). `_run_combat_impl`'s single
  `_finish_combat` runs once either way — doc-53
  tombstone-then-delete ordering preserved; no second call from
  the dispatch branch.
- Caller-side execution + adoption (GameLoopState belongs to the
  caller, never the combat loop):
  - `combat/_encounter.py:241-256` — `_handle_combat_encounter`
    gains a FLED branch calling a `begin_flee_transition` that
    runs the SAME resolve/adopt code the main loop runs
    (land/explore/dig/dock/jump).
  - The four `game_loop.py` sites that check `== "BOARDED"`
    (movement ~680, wait ~396, goto ~364, comms ~383) get the
    flee adoption — `_adopt_capture_boarding`
    (`game_loop.py:348-357`) is the precedent.
  - `game_flow.py:97-99` — the `also_move_npcs` guard gets the
    FLED twin of the BOARDED guard: space-NPC drift and the watch
    pass must never run against the post-flee map.
- `_handle_meta_action`'s docstring "fleeing is not a mechanic"
  (`combat/_loop.py:549-550`) goes stale — updated in this phase.
- Budget note: `_rules_space.py` (899 lines) and `_loop.py` (721)
  sit near the 1000-line ratchet — the volley may force the
  in-commit split. Expected; not a placement driver.

**Build order**

1. `reaction_volley` on `_rules_space` + unit tests (in-range
   fires once each, out-of-range doesn't, can kill, refusal fires
   nothing).
2. Loop wiring: exit check → prompt → commit → volley →
   FLED/DEFEAT break; cancel fires nothing.
3. Caller side: FLED branch in `_handle_combat_encounter` +
   `begin_flee_transition` + the four game_loop adoptions + the
   game_flow guard.
4. Harness sync: `tests/balance/harness.py` mirrors
   `_run_combat_impl` step by step — cross-reference the
   MOVE-branch change there per its own docstring mandate.
5. Guide edit + stale-sentence revision (own commit; wording
   below).
6. `make check` + reviewer (REVIEW) + sabotage-proof one pin.

**Binding rulings**

- Adjacent escape allowed — no disengage requirement (conversation
  2026-09-26).
- No chase: nothing follows through a landing, dock, or jump.
- Volley AFTER the confirm; cancel is free (SETTLED 1).
- Land/Explore/Dig/dock/jump all trigger the volley — one rule
  for every map-leaving commit (SETTLED 1/3).
- A refused exit is a full no-op — no volley, no AP spent, same
  turn, fight continues exactly as before the attempt (SETTLED 3).
- Death wins: volley kill = DEFEAT at the threshold, tombstone +
  save delete, no transition (SETTLED 1).
- Volley shots can kill (conversation ruling, DCSS).

**Required tests**

- Cancel fires nothing: open the exit menu mid-combat, ESC → no
  shots, fight continues (menu-capable input fakes).
- Every in-range hostile fires exactly once (two in range + one
  out → exactly 2 shots); no enemy movement in the volley.
- Refused commits are a full no-op: no fuel for the jump → menu
  refusal, no shots, no AP change, same turn, fight continues
  (SETTLED 3).
- Volley kill → outcome DEFEAT, `tombstone_path` set, no map
  change. Harness: the `tests/balance/` real-combat contracts
  (pygame.init(), absorbing console, RNG snapshot/restore, HOME
  sandbox — DEFEAT deletes the autosave).
- Survive → outcome FLED, the named transition ran (mode/map
  changed), fuel −10 on jump, hostiles gone.
- No victory bookkeeping on FLED (rep/kills unchanged by the flee
  itself); no space-NPC drift against the post-flee map.
- Non-exit blocked bump still logs "Blocked." (regression pin).
- Sabotage-proof the volley pin (disable the call → test fails →
  restore → passes).

**Stop point — do NOT start**

- No ground/stairs work (phase 2), no boarding-interior specifics,
  no ground DISENGAGED changes, no tutorial modal, no pursuit/chase
  mechanics, no new exit UI, no changes to out-of-combat exits.

**Playtest checkpoint (numbered, in-game)**

1. SPACEHACK_DEV frigate grant; hostiles near a planet. Open the
   planet menu mid-fight, ESC. EXPECT: no shots fired, fight
   continues.
2. Commit to LAND with two ships in range. EXPECT: both fire once
   (watch the beams), damage lands, then the landing transition;
   hostiles gone from the surface map.
3. Same at low hull. EXPECT: the volley can kill — death screen +
   tombstone line (doc 53), NO landing.
4. Jump-gate flee mid-combat: confirm the jump. EXPECT: volley →
   10 fuel burned → new system, no pursuit, nothing waiting.
5. Station flee: dock at a station mid-fight. EXPECT: the same
   volley rule, then the dock transition; the city map and its
   NPCs intact (no space drift against it).
6. Jump with an empty tank mid-fight. EXPECT: fuel refusal, NO
   shots, fight continues.
7. Bump an asteroid/wall mid-combat. EXPECT: "Blocked." exactly as
   today.
8. Save → quit → continue right after a survived flee. EXPECT:
   intact state on the surface/station.
9. Guide diff: "Combat" — the disengage sentence REVISED to the
   flee wording below — review the diff.

**Guide edit (draft; approving this brief approves the wording;
lands in its own commit)**

"Combat" — the existing sentence "If your shields are falling and
your weapons cannot turn the fight, disengage by moving away if
the situation allows - or do not start the fight in the first
place." is REVISED to:

> If your shields are falling and your weapons cannot turn the
> fight, flee through the world's exits: land on a planet, dock at
> a station, or take a jump gate mid-fight. Everything in range
> fires once as you go, and those shots can kill you - or do not
> start the fight in the first place. Jumps burn fuel as usual.

## Implementation brief — Phase 2: ground stair dancing (APPROVED 2026-09-26)

**Scope (exact files / hook points)**

- `src/spacehack/combat/_loop.py` — after a successful ground
  MOVE, if the player's tile kind is in `world.TRANSITION_KINDS`
  ("exit", "stairs_up", "stairs_down"), fire the flee path. The
  step itself is the commit — the AP spent to step through; no
  extra prompt (SETTLED 1's ordering with the step as the
  confirmation).
- The flee path probes the transition's refusal conditions BEFORE
  the volley — the same failures the out-of-combat handler hits
  (sealed stairs, `game_loop.py:556`; dig/extension refusals). A
  refusal refunds the step: position restored, AP back, no
  volley, same turn, fight continues (SETTLED 3).
- `reaction_volley` on `combat/_rules_ground.py` (mirror of the
  space hook, same name): every enemy in range + LOS attacks once
  — reuse the ground enemy-turn attack resolution and animations;
  no movement.
- The DISENGAGED result is synthesized directly —
  `_combat_end_check` cannot produce it while hostiles are visible
  (`_rules_ground.py:894-906`). Call `on_disengage` directly
  (`_rules_ground.py:882-892`) so survivors investigate the
  stairs via last-seen memory rather than patrol blind. "Locks
  released" rides `sync_state`, which `_finish_combat` already
  runs for every outcome — no separate cleanup path.
- BOARD-seam result flow: died on the stairs → result "DEFEAT",
  break (single `_finish_combat`; doc-53 ordering). Survived →
  result "DISENGAGED" + an exit payload on CombatResult; **the
  loop never runs the transition.**
- The CALLER falls through to its existing dispatch — the fight
  ends, `_handle_dungeon_move`'s 'COMBAT' short-circuit
  (`game_loop.py:593-599`) releases, and the ordinary
  `_handle_dungeon_stairs` / `exit_city_interior` /
  `_handle_dungeon_exit_tile` handling right after runs the
  transition:
  - stairs_down branches (`game_loop.py:501-532`): dig floors →
    `digs.transition`; active extension → `transition_floor`;
    otherwise `enter_extension` (the Mars surface stairs — a
    quest beat, same rule).
  - `_handle_dungeon_exit_tile` (`game_flow.py:829-861`) carries
    the boarded-interior exit (needs `space_game_map`/
    `space_player` — GameLoopState-shaped, so it MUST stay
    caller-side).
- Five ground-combat entry points need the fall-through verified:
  dungeon move/wait/autoexplore/goto (`game_flow.py:304-343`) and
  `run_city_fight` (`city_npcs.py:372-396`, whose shim writes must
  survive `_apply_movement_interaction`'s copy-back).
  GameLoopState handlers never run inside the combat loop (the
  BOARDED lesson).
- Budget note: `_rules_ground.py` sits at 948 lines — the volley
  lands it over the ratchet; expect the in-commit split.

**Build order**

1. Ground `reaction_volley` + unit tests (range+LOS filter, one
   attack each, can kill).
2. Loop: post-move TRANSITION_KINDS check → refusal probe (refund
   the step on refusal, SETTLED 3) → volley →
   DEFEAT / DISENGAGED-with-payload break (`on_disengage` called
   directly).
3. Caller fall-through across the five entry points (verify each
   routing: delve stairs, dig floors, extension stairs, city
   interior exit, boarded interior exit).
4. Harness sync: cross-reference the `_run_combat_impl` change in
   `tests/balance/harness.py`.
5. Guide line (own commit; wording below).
6. `make check` + reviewer (REVIEW) + sabotage-proof one pin.

**Binding rulings**

- Stair dancing works both directions (up and down).
- The step is the commit: AP spent, no extra prompt. A fight that
  STARTS with the player standing on the stairs stays put until
  they step off and back on (eating the volley) — MOVE is the
  only trigger; WAIT fires nothing.
- A refused exit is a full no-op: sealed stairs or any refusing
  transition refunds the step (position restored, AP back), no
  volley, same turn, fight continues (SETTLED 3).
- Wounds carry — no heal on transition; the delve economy keeps
  its pressure valve honest.
- Survivors revert via `on_disengage` (they investigate the
  stairs' last-seen position); locks released via `sync_state`;
  no kills booked (DISENGAGED semantics verified safe at
  `game_flow.py:139`).
- Death wins: volley kill on the stairs = DEFEAT + tombstone, no
  transition (SETTLED 1).
- Boarded hulls: same rule; loot/XP forfeit, hull consumed at
  entry, no re-board (SETTLED 2).
- No pursuit between floors. Automation is already safe:
  autoexplore/goto never enter transition tiles
  (`autoexplore.py:362,481`); NPC swap-in refuses them
  (`ground_npcs.py:89`) — no changes there.

**Required tests**

- Step onto stairs mid-fight: only enemies in range + LOS attack
  (one each); result DISENGAGED + exit payload; the transition
  ran via the caller dispatch; `on_disengage` invoked; no kills
  booked.
- Volley kill on the stairs → DEFEAT + `tombstone_path`, no floor
  change (same harness contracts as phase 1).
- Fight starting ON the stairs: no transition until re-stepped
  (pin the MOVE-only trigger).
- Sealed/refusing stairs: step refunded — previous cell, AP
  restored, no volley, fight continues (SETTLED 3).
- Boarded interior: exit mid-fight → volley from the crew → back
  in space; the hull is NOT re-boardable.
- City interior: fight near an interior exit tile, step out
  mid-fight → volley, exit to the street, same cleanup (the
  `run_city_fight` path).
- AP spent on the committing step.
- Exited-floor survivor persistence pins whatever the transition
  machinery does today (cache semantics) — no new persistence.
- Sabotage-proof the volley pin.

**Stop point — do NOT start**

- No space-side changes (phase 1 owns them), no tutorial modal, no
  pursuit/chase between floors, no volley on WAIT/fire, no new
  outcome strings (DISENGAGED is reused), no changes to
  out-of-combat transitions, no autoexplore/goto changes.

**Playtest checkpoint (numbered, in-game)**

1. Delve fight on the stairs: engage a guardian, step onto `>`
   mid-fight with one ranged enemy in LOS. EXPECT: it fires once,
   the transition runs, wounds carried down, no kill booked.
2. Bait three adjacent enemies, flee at low HP. EXPECT: the volley
   can kill on the stairs — death screen + tombstone, NO floor
   change.
3. Climb back up (`<`) to the floor you fled. EXPECT: survivors
   hunting near the stairs (last-seen), locks released, no
   auto-restart of the fight.
4. Start a fight while standing ON stairs, then WAIT. EXPECT: no
   transition; step off and back on to leave (the volley fires).
5. Step onto sealed stairs mid-fight (a story-gated transition).
   EXPECT: step refunded — back on your previous cell, AP
   restored, no shots, fight continues.
6. Boarded hull: bail out the exit mid-crew-fight. EXPECT: volley
   from the crew, back in space, hull gone (consumed at entry),
   interior loot forfeited.
7. Fight inside a landmark interior near its exit; step out
   mid-fight. EXPECT: volley, back on the street, survivors
   revert.
8. Save → quit → continue after a stair-dance. EXPECT: correct
   floor, position, HP.
9. Guide diff: the ground line below — review the diff.

**Guide line (draft; approving this brief approves the wording;
lands in its own commit)**

"Ground Exploration" section, adjacent to the existing stairs text:

> Stairs work during combat: step on one to leave the fight for
> the next floor. Every enemy that can hit you fires once as you
> go, and those shots can kill you. Survivors on the floor you
> left go back to patrol.
