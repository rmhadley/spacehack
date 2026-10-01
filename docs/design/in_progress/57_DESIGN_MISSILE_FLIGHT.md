# DESIGN: Missile flight — interceptible long-range artillery

Status: PHASE 1 PLAYTEST PASSED 2026-10-01 (v2 flight model;
built via `/implement-phase 57.1`, reworked by the first playtest
into SETTLED 11, prose settled at the second checkpoint; gate 3445
green; reviewer APPROVE ×2). Briefs 57.2–57.3 remain PROPOSED until
their checkpoints. Refined 2026-10-01 (`/refine-design`): rulings
SETTLED 1–9, every open question closed; Implementation briefs 1–3
written with the ADVISE reviewer pass folded (14 catches, 6
blocking — kill-path bookkeeping, merged-index readers, entity
solidity, sync sweep, enemy-side floor gate). Nothing
implemented. Born in the doc-56 phase-4
parts walk (SETTLED 35's coda): the walk held missile magnitudes for
the probe, and this rework — proposed by the user the same day —
supersedes those magnitudes when it lands. Doc 56's calibration pass
proceeds meanwhile on the non-missile dials.

## Overview

Missiles stop being instant damage numbers and become **physical
projectiles in flight**: strictly long-range (hard-gated floors, worse
than today), roughly doubled damage, and — the heart of it — **while a
missile is in flight it can be targeted as an enemy and shot down**.
The proposal verbatim (user, 2026-10-01):

> - Missiles get even worse minimum range than they are now. They
>   are strictly long distance only
> - We double their damage
> - They move slower than lasers. When a missile is in flight, they
>   can be targetted as an enemy and shot down.

The design goal is the one the whole doc-56 arc serves, extended to
projectiles: **every threat has a counter, and every counter can be
saturated**. Missiles counter watt-scarcity and standoff; point
defense counters missiles; magazine depth (doc 56 SETTLED 35's
Missile Magazine, +3/rack) counters point defense. The chain closes.

## What the riff established (2026-10-01, pre-doc)

- **light_laser is the born flak gun**: 80% accuracy, 1 AP, 1 cell —
  the starter weapon's endgame job is point defense, a role no
  plasma cannon can fill. The "everything has a purpose" doctrine
  pays retroactively.
- **The Missile Magazine becomes saturation, not optimization**:
  deep racks are volume-vs-flak. Today's ruling is load-bearing.
- **Dread rendered as a glyph crossing the map** — flight is the
  wordless-visual-communication doctrine applied to ordnance
  (travel is motion not prose; SETTLED 1 makes it literal).
- **One mercy already banked**: combat never saves mid-fight (doc 56
  phase-5 record), so in-flight missiles are transient state — no
  save/load work.

## Evidence baseline (launchers at refine, 2026-10-01 → ruled)

| | light_missile | heavy_missile | emp_missile |
|---|---|---|---|
| Price | 40cr | 90cr | 120cr |
| Damage | 14 → **28** | 32 → **64** | 0 (100% strip) |
| Accuracy | 72% | 72% | 75% |
| Range | 2–9 → **4–9** | 3–13 → **5–13** | 2–10 (pulse, unchanged) |
| Floor semantics | penalty → **hard gate** | penalty → **hard gate** | n/a (instant) |
| missile_hp | — → **2** | — → **6** | — (never interceptible) |
| flight_speed | — → **4** cells/round | — → **2** | — (0 = pulse) |
| Magazine | 4 (+mag) | 3 (+mag) | **2, hard-capped** (SETTLED 35) |

Post-volley doctrine (doc 56): the first 2-AP weapon sets the volley
cadence; missiles pair with plasma (both 2 AP), never with pure laser
walls. Damage racks receive the magazine bonus; EMP never does.

## SETTLED rulings (2026-10-01, `/refine-design`)

1. **Flight model: multi-tick crossing.** A launched missile is a
   live combat entity advancing `flight_speed` cells per combat
   round along its track; every round it remains on the map is an
   intercept window. Close shots (just above the floor) arrive in
   1–2 rounds and are barely flak-able; max-range heavies telegraph
   3–4 rounds of dread. Chosen over the one-action delay — the
   glyph crossing the map is the point.
2. **Floors are a hard gate, missiles only.** light 4 / heavy 5
   (the riff's opening numbers; phase 3 may nudge them). Inside the
   floor the rack will not fire at all — `can_fire` refuses, the
   card/range line shows it. Lasers/plasma keep today's 5%/cell
   penalty semantics untouched. "Strictly long distance only" reads
   literally; rushdown inside the floor makes racks dead sticks.
   The gate reads the CATALOG floor — Focus's doubled min-range
   does not widen the refusal band (a focused light refuses inside
   4, not 8; strictly-long-distance is a property of the rack, not
   the shot mode).
3. **×2 damage lands with phase 1.** The gamble reads the moment
   flight exists — the moment a heavy gets through flak, the payoff
   lands. Phase 3 recalibrates the multiplier against measured
   intercept rates.
4. **EMP stays an instant pulse, never interceptible.** Its counter
   is the hard-capped magazine (2, doc 56 SETTLED 35) and its price,
   not flak RNG — a flak juggernaut deleting the boss key would read
   as losing the fight to a dice roll. Authored in data as
   `flight_speed=0` (never travels); the fire path branches on that
   alone.
5. **The hit roll moves to arrival.** Accuracy becomes a guidance
   roll resolved at impact against the target's then-current dodge —
   moving during flight is the universal anti-missile defense (the
   kiting doctrine extends to ordnance), and every inbound on the
   map might hit, so flak is never wasted on a known dud. Miss at
   arrival = harmless detonation. Interception is the other miss
   path. No range terms in the guidance roll — range was paid at
   launch (the target sat inside [floor, max] when fired).
6. **Interception costs the full volley action.** TAB cycles onto
   hostile in-flight missiles; F fires the volley at one exactly as
   at a ship — max-AP-once, per-weapon power/ammo, existing seams
   everywhere. Choosing flak IS choosing not to shoot the shooter.
7. **Intercept difficulty: light thin+fast, heavy fat+slow.**
   light `missile_hp` 2 / `flight_speed` 4; heavy 6 / 2 (exact
   numbers are phase-3 dials). Missiles carry no shields — strip
   and pulse weapons naturally do nothing to them (damage weapons
   only, by construction not by special case).
8. **Auto-flak: manual only.** No hands-free layer, ever —
   per-weapon active toggles + TAB already express the flak escort
   (deactivate the heavies, TAB to the inbound, F). The drafted
   phase-3 auto-flak component is dead; saturation balance folds
   into the calibration phase (former phase 4; phases renumber to
   three).
9. **Doc-56 seam (derived, no ruling needed).** The magazine bonus,
   the BH ×2, and cargo-per-round booking are CAPACITY sites —
   untouched by doubled damage, floors, and flight. Missile
   magnitude ownership (the held missile feel + the new intercept
   numbers) moves from doc 56 phase 4 to this doc's phase 3; doc
   56's calibration proceeds on the non-missile dials meanwhile.
10. **Glyphs: family by shape, side by color** (2026-10-01, user:
    "this works"). Heavy missile `♦` — dense, fat, matches
    hp 6 / speed 2; light missile `*` — small, quick, matches
    hp 2 / speed 4. The card-suit glyph renders crisp (procedural
    patch), and the `*`/`♦` collisions are city tiles (neon,
    monuments) that never co-render with a space fight. Ownership
    reads by COLOR — hostile inbound hot red (the dread read at a
    glance), player-owned the cyan/friendly accent — so the family
    shape stays legible. The EMP pulse never renders. Wordless
    target priority: a `♦` crossing the map is the one worth a flak
    volley; a `*` is thin enough to maybe eat. One-glyph fallback
    stays a phase-1 playtest call if two glyphs read as noise.
11. **Flight model v2 — deploy, stagger, mini-turns** (2026-10-01,
    playtest ruling, user verbatim: "Missiles shouldn't stack on each
    other." + the nine-rule rework, lightly condensed):
    1. You fire a volley of 2 light missiles.
    2. One light missile appears in a cell near you but not on you.
    3. That light missile moves towards its target half of its normal
       move range.
    4. The next missile appears in a cell near you but not on you.
    5. That next missile moves towards its target half of its normal
       move range.
    6. Missiles cannot collide with other missiles; they actively
       avoid missiles from the same shooter.
    7. Missiles that collide with a ship explode, even if it's not
       its target.
    8. Missiles that collide with a planet/star/station explode.
    9. After the initial half move phase, missiles don't move again
       until before the shooter's turn: at the start of the shooter's
       turn missiles resolve their mini-turn first, going through each
       missile in flight one at a time, this time moving their full
       distance, still following rules 6-9.

    Derived mechanics (agent, from the rules + rulings):
    - Spawn cell: a walkable, ship-free, missile-free 8-neighbor of
      the shooter, nearest to the target (fixed tie order); fallback
      to the shooter's own cell when every neighbor is blocked.
    - Launch half-move: `max(1, flight_speed // 2)` cells immediately
      at launch (light 2, heavy 1), full movement rules; burns fuel.
      Target-arrival at launch is geometrically impossible (floors).
    - Collision with ANY ship (target or not — the player's own hull
      included, RULING: full damage on contact): the SAME guidance
      roll against that ship's dodge-at-contact; a hit rides the
      normal damage path and any kill runs the full kill chain; a
      miss is the harmless detonation. Self-splash is live.
    - Collision with blocking terrain / world bodies: detonation at
      the previous cell, harmless (`Missile detonates short.`).
    - Same-shooter missiles: never share a cell — sidestep to the
      best progress-preserving free neighbor, hold (no fuel burn)
      when boxed. Cross-shooter missiles ignore each other.
    - Mini-turn timing: the player shooter's missiles resolve at the
      existing hook (after enemy turns + reinforcements, before the
      player's AP); movement is FULL `flight_speed`, one missile at a
      time in launch order. 57.2's enemy shooters mirror this inside
      the enemy's own turn (amends that brief's scope).
    - A flight rack fired at a MISSILE target is a legal dud: the
      missile never connects (rule 6), burns fuel, exhausts — point
      defense is guns (SETTLED 8's doctrine); no refusal prose.
    - Launch-window collision kills happen inside the volley, so the
      count-based Momentum refund can fire for them; mini-turn kills
      never do (no volley is open). Ruling-consistent: refund stays
      volley-time mechanics.
    - Beyond-max launch (RULING, same exchange): the fuel dud stands
      — it flies, exhausts, detonates; ammo + AP spent. SETTLED 2
      stays a floor-only gate.

## Pre-implementation audit (2026-10-01, phase 57.1)

### 1. Existing classes / modules to extend or reuse

- **`EnemyInstance`-compatible targeting** (`combat/_types.py`): the
  flight missile needs no adapter into `hit_chance` / `damage` /
  `can_fire` if its dataclass carries the reads those paths use —
  `name`, `pos`, `hull = max_hull = missile_hp`, `shields =
  max_shields = 0`, `alive`, `cells_moved_this_turn = 0`,
  `pilot_piloting = 0`, `weapons = ()` (the ADVISE pin, verbatim).
- **`resolve_damage`** (`combat/_actions.py:440`): arrival damage
  and intercept damage both ride it unchanged (doubled rack damage
  is spec data; quality rides the launcher's stored tier). The
  strip path no-ops on `shields=0` by construction — SETTLED 7.
- **`calc_hit_chance`** (`combat/_stats.py:160`): the guidance roll
  is this formula minus its range terms; extract the shared
  assembly so both stay one formula family.
- **`_space_kills.on_kill`** (`combat/_space_kills.py:220`): the
  arrival kill chain, called exactly as `_handle_fire`'s tail calls
  it. The intercept kill NEVER calls it (dedicated branch).
- **`SpaceCombatState`** (`combat/_types.py:135`): gains
  `in_flight: list` — combat-transient, never serialized (combat
  never saves mid-fight; only loot entities serialize off the map
  anyway, verified in `saveload.py`).
- **`world.Entity` + `blocking_entity_at`** (`world.py:321/477`):
  missiles render as entities via the standard world draw path
  (fg/char picked at spawn — hostile hot red, player-owned cyan);
  a new declared `non_blocking: bool = False` field makes
  `blocking_entity_at` skip them (the zero-footprint pin). Entity
  save path is loot-only, so the field is save-neutral.
- **`_render_anim_frame` + `_animate_explosion`**
  (`combat/_animations.py`): the per-step advance frame (the
  wordless dread beat, same as the enemy step renders) and the
  intercept-kill explosion beat.
- **`render_combat_hud` / `_render_enemy_row`**
  (`hud_combat.py`): missile rows ride the ENEMIES block — the
  row already skips the Shd line at `max_shields == 0` and bars
  hull from `hull/max_hull`, so a merged list renders missiles
  with zero row changes; only the target marker's index space and
  the floor-band color differ.
- **`range_band_color`** (`hud.py:122`): the distinct missile-floor
  refusal read lands here (+ `_paint_range_cell` consumers) as a
  flag, so lasers keep penalty-orange untouched.
- **`_build_target_card` seam** (`_space_presentation.py`): a
  missile variant (name / HP / speed; no band, AP, weapons,
  shield rows) beside the ship card, same geometry helpers.
- **`pygame_target_card` / `_card_presentation`**: shared card
  geometry and row builders reused as-is.

### 2. Three potential duplication hotspots

1. **Target-index plumbing in `_loop.py`**: TAB cycle, fire path,
   retarget, HUD marker, and board resolution each currently index
   `rules.get_enemies(ctx)` — five sites that could each grow a
   subtly different "missiles too?" patch. Ground rules have no
   missiles, so naive edits would also leak into ground combat.
2. **Arrival resolution vs the volley kill tail**: the arrival
   kill's destroyed-line + `on_kill` + result bookkeeping would be
   easy to copy-paste out of `_handle_fire`'s tail (and the
   intercept kill's entity-pop + explosion out of
   `_space_kills.on_kill`) instead of sharing one finisher.
3. **Advance/arrival math inside `_rules_space`** (955/1000
   lines): step math, fuel, guidance roll, and entity sync written
   inline there would both duplicate the pure-stat family in
   `_stats.py` and trip the module ratchet.

### 3. DRY strategy per hotspot

1. One loop-side helper `_targetables(rules, ctx)` (prefers
   `rules.targetables`, falls back to `rules.get_enemies`) feeding
   every index-space site in `_loop.py`; ground rules implement
   nothing new. Ships-only readers (`combat_should_end`,
   `reaction_volley`, `board_target`, `get_enemies`) are untouched
   by construction.
2. The flight finishers live in `_missile_flight.py`:
   `_finish_arrival` (guidance roll → damage → destroyed line →
   `on_kill`) and `_finish_intercept` (entity pop → explosion →
   `Missile destroyed.`), each called from exactly one seam
   (round boundary / `_handle_fire`'s intercept branch).
3. All pure flight math (advance step, fuel, arrival detection,
   guidance roll) is born in `_missile_flight.py` as pure
   functions with same-commit tests; `_rules_space` keeps only
   thin seams (spawn-on-fire branch, floor gate in `can_fire`,
   merged accessor, round-boundary hook) — the budget-note
   refactor pays the ratchet by construction.

### Audit updates as the build reveals surprises

- The forecast ratchet refactor fired as budgeted: the reinforcement
  block moved to `combat/_space_reinforce.py` (state-explicit, the
  `_space_kills` pattern), keeping `_rules_space` at 995 lines.
- Authoring-invariant coupling (doc 48 SETTLED 40): the heavy floor
  3→5 outgrew four carriers' `ai_preferred_range` — pirate_captain,
  militia_patrol_heavy, pirate_marauder, pirate_warlord bumped to 5
  (standoff heavies, thematically the doc's own "strictly long
  distance" read; light carriers already sat at 4). Committed with
  the ruled rows, not the mechanics.
- Reviewer round 1 (REQUEST_CHANGES → APPROVE on re-review): the
  blocking catch was a real hole — a flight rack fired at a crossing
  MISSILE (the merged fire path allows it; the default volley arms
  every slot) would arrive into the SHIP kill chain and crash on
  ordnance's missing `spec_id`. Ruling: an arrival at ordnance takes
  the INTERCEPT bookkeeping (guidance roll → damage onto missile_hp →
  `Missile destroyed.`, never `on_kill`) — the intercept ruling
  extended to the arrival seam, pinned by
  `test_arrival_at_a_missile_takes_the_intercept_branch`.
- The floor read consolidated into ONE helper (`catalog_floor`) after
  the reviewer flagged four scattered copies (gate, range line, HUD
  distance, card HIT color, then the WEAPONS stat row as a fifth):
  Focus never widens a rack's refusal band, everywhere.
- RULING (user, same checkpoint, with SETTLED 11): the beyond-max
  fuel dud STANDS (ammo + AP spent; kiting past a rack's max is the
  outrun counter with legible feedback). SETTLED 2 stays floor-only.
- The doc-53 tombstone harness's space-victory fixture was re-authored
  for v2 physics (heavy lasers, not twin missile racks): under the
  mini-turn model a standoff double-heavy volley no longer guarantees
  a turn-1 kill — the seeded scout rushed inside the floor after two
  guidance misses and won. The fixture's purpose is the tombstone
  surface, not missile balance; 57.3 owns the balance questions.
- Contact-damage prose SETTLED 2026-10-01 (user, checkpoint):
  non-target ship hits speak the detonates form — "Your Heavy
  Missile detonates on Escort for 64 damage." (the fire-form line
  stays the target arrival's, so the log distinguishes intended hits
  from clips); self-splash as drafted — "Your Heavy Missile detonates
  on your own hull for N damage."; guide sentence with the comma —
  "Any ship its flight path crosses takes the hit, including yours."
  Same exchange, style ruling: the spaced hyphen " - " is an AI tell
  (now prose tell 17 in knowledge.md); the guide paragraph's own
  instance rewritten with a comma/colon.
- PLAYTEST PASSED 2026-10-01, no failures reported. Fuel legibility
  was surfaced at the checkpoint (per-missile remaining fuel is
  invisible; the RNG band readout carries the reach story) and the
  user took no readout option — the range readout stays the story;
  revisit only if a playtest ever misses it.
- Reviewer round (v2, APPROVE): rulings recorded — (a) contact reads
  ANCHOR CELLS: a crossing missile can pass a capital ship's
  non-anchor footprint without contact, and a ship parking on a
  resting missile detonates it at the next mini-turn (both implemented
  or ruled; revisit if 57.2 makes cross-shooter overlap common).
  The parked-detonation reads only while the missile's OWN target is
  alive — a missile whose target died that round dissipates first
  (dud warhead either way);
  (b) a launch-half-move self-splash kill is backstopped by the
  loop's post-action hp gate (the volley's remaining slots still
  fire — contrived geometry only); (c) GUIDE DECISION: the v2
  contact rules are player-facing and the missile guide paragraph
  gains ONE sentence at the checkpoint prose approval ("any ship its
  flight path crosses takes the hit — including yours"), nothing
  else; current guide text stays true under v2.

## Pre-implementation audit (2026-10-01, phase 57.2)

### 1. Existing classes / modules to extend or reuse

- **`advance_flights`** (`combat/_missile_flight.py:553`) — already
  side-parameterized; gains a `shooter` filter (per-shooter
  mini-turns, SETTLED 11.9's enemy mirror) and a sibling
  `advance_orphan_flights` for dead-shooter missiles, both sharing an
  extracted `_mini_turn` body.
- **`_enemy_volley` / `_enemy_shot_tail` / `_apply_enemy_hit`**
  (`combat/_ai.py:485/521/634`) — the volley mirror: one `target`
  parameter (None = the player, an `InFlightMissile` = flak), a
  flight-member spawn branch, and the arrival tail called VERBATIM
  (attack line, damage counters, `last_attacker`, DEFEAT
  presentation) — zero bookkeeping copies.
- **`enemy_attack_line`** (`combat/_messages.py:168`) — the `" you. "`
  object gains a `target_name` parameter for flak lines; every form
  stays existing vocabulary (the player's own flak already logs
  "at Heavy Missile. It misses!" through the mirror builder).
- **`score_weapon` pattern** (`combat/_ai.py:241`) → new `score_flak`:
  the same `calc_hit_chance` + per-AP shape at dodge 0, × hull
  coverage × the inbound's threat.
- **Phase-1 player-side interception** — `merged_targets` is
  side-agnostic, so enemy missiles already ride the TAB cycle, the
  card, `hit_chance`/`damage` (EnemyInstance-compatible reads), and
  the intercept branch. The player's TAB+F defense is live unchanged.
- **`_reaction_pick`** (`combat/_ai.py:328`) — the single choke point
  every reaction caller reads; the flight exclusion lands here (NOT
  in `_rules_space.reaction_volley` — that module sits at 999/1000
  lines and the ruling is unchanged; scope-line deviation recorded
  below).

### 2. Three potential duplication hotspots

1. **Target plumbing fork**: volley target, shot-tail target, and the
   flak roll could grow three near-duplicate resolve → animate → log
   stacks inside `_ai.py`.
2. **Enemy-arrival bookkeeping**: the arrival-on-player path could
   copy `_apply_enemy_hit`'s writes (shields/hull, counters,
   `last_attacker`, death presentation) instead of calling it.
3. **Mini-turn filters**: per-shooter and orphan sweeps could
   duplicate the whole `advance_flights` loop body.

### 3. DRY strategy per hotspot

1. `_enemy_volley(target=...)` computes member inclusion in ONE walk
   (affordability ∧ floor ∧ flak-capability) and dispatches each
   member to exactly one of three tails (spawn / flak shot / shot
   tail); the flak roll is its own small helper with only the
   dodge-0 + target-name reads it needs.
2. The arrival calls `_ai._apply_enemy_hit` directly; the side-aware
   guidance roll lives in `_guided` (player side keeps LIVE reads —
   the opener window can close mid-flight; enemy side reads the
   launch-time `pilot_gunnery` snapshot, static per instance).
3. `_mini_turn(state, ctx, game_map, missile)` is the one body;
   `advance_flights` and `advance_orphan_flights` are one-line
   filters over it.

### Audit findings before code (scan results)

- **Spin hole in the brief's floor-gate scope**: gating
  `_affordable_members` alone is NOT enough. `_volley_picks` →
  `_ranked_weapons(affordable_only=True)` can still hand
  `_engagement_decision` a fire pick that is an in-floor rack; the
  volley then fires zero members, returns `None` having spent no AP,
  the decision reports `"SPENT"`, and `_take_enemy_turn`'s
  `while _ei.ap_remaining > 0` loops forever — the "never a spin"
  contract (doc 48 SETTLED 40). Today the empty-volley spin is
  unreachable (non-None fire pick ⇒ an affordable member). The gate
  therefore lands in the ranked walk too — the honest mirror of the
  player's `can_fire`, which gates the player's volley the same way.
- **Phase-1 latent bug gone live**: `_same_shooter_missile_at`
  (`_missile_flight.py:200`) compares SIDE. True only while each
  side has one shooter. With multiple enemy shooters it must compare
  shooter identity (SETTLED 11.6: avoid same-SHOOTER missiles;
  cross-shooter missiles ignore each other). Player missiles all
  carry `shooter=None` — semantics unchanged.
- **SETTLED 10 supersedes the brief's render line**: "enemy missile
  glyph distinct from the player's" predates the same-day glyph
  ruling; family-by-shape, SIDE-BY-COLOR is binding, and
  `_build_missile` already paints side fg (hostile hot red / player
  cyan). No glyph change; color is the distinction.
- **Enemy launch is wordless** (SETTLED 1: the glyph crossing IS the
  dread beat; travel is motion, not prose). The arrival speaks the
  EXISTING `enemy_attack_line` forms verbatim — hit with damage, or
  the hit=False miss form — so the phase lands ZERO new prose (the
  six player-side lines stay the complete set; "Missile destroyed."
  covers both sides' intercepts through the shared finisher).
- **Orphan cadence**: dead-shooter missiles move at the START of the
  enemy phase, ahead of live shooters' turns — AT MOST one move per
  round (occasionally zero: a shooter killed after the sweep but
  before its own turn leaves its missiles unmoved that round; they
  resume next round, ADVISE 6), with no moved-flag: a shooter dying
  mid-phase AFTER its turn has already moved its missiles; a missile
  launched mid-phase whose shooter then dies waits for the next
  phase's sweep. The sweep's DEFEAT propagates (`_run_enemy_turn` →
  the 999 signal → `_end_turn`, ADVISE 3).
- **Enemy-launch player-kill IS reachable** (ADVISE blocking 1,
  2026-10-01): the floor gate reads Euclidean distance while flight
  is per-cell Bresenham — a light rack at the (3,3) diagonal sits at
  Euclidean 4.24 (passes floor 4), its spawn lands 2 out and the
  half-move is 2, so the launch can walk onto the player. The enemy
  spawn seam therefore propagates DEFEAT through the volley's
  existing `_outcome == "DEFEAT": break` shape (heavies ARE
  geometrically safe: min Chebyshev standoff past a Euclidean-5 gate
  is 4, spawn 3 + half-move 1 never closes below 2). The player
  side's discard stays — its post-action hp gate is the ruled
  backstop ("remaining slots still fire"). The ORPHAN sweep's DEFEAT
  propagates the same way (`_run_enemy_turn` → the 999 signal →
  `_end_turn`).
- **Fratricide contact (ADVISE blocking 2)**: an enemy missile
  contacting a NON-target enemy ship deals identical physics (rule 7
  verbatim: ANY ship) but must NOT speak the player-possessive
  detonates form NOR run the player-crediting kill chain (no XP,
  loot, bounty, rep, or `defeated_*` for a pirate's own crossfire —
  the intercept-kill precedent: ordnance deaths the player did not
  cause record nothing). DRAFT forms (checkpoint approval, the
  settled player forms parameterized by speaker): hit — `Pirate
  Scout's Heavy Missile detonates on Pirate Escort for 64 damage.`
  kill — the existing `{name} destroyed!`; miss stays `Missile
  detonates short.` The victim's entity still leaves the map (no
  ghost hull).
- **Pinned-test re-pins required**: the cornered rack-only ship now
  fires NOTHING (dead stick, SETTLED 2) instead of firing through
  the penalty; `test_pick_takes_the_top_scorer...` moves to a legal
  distance (rack floor 5 > its 4.0); `_reaction_pick`'s reach test
  loses the rack (was the reachable pick at 6.0) and re-pins on
  guns; `_turn_state` fixtures gain `in_flight=[]`.

### Audit updates as the 57.2 build revealed surprises

- The ratchet fired as forecast on four functions (the four new/
  reshaped AI/flight seams); paid in-commit with cohesive
  extractions: `_advance_toward_standoff` (the out-of-position
  verb), `_run_volley_members` (the member loop), `_apply_flak_
  damage` + `_apply_guided_arrival` (the resolve tails), keeping
  every function under 40.
- A REAL bug the flak tests caught before it shipped:
  `_select_fire_weapon` returns ``(slot, spec)`` — the ranked walk
  strips its score — so `_flak_pick`'s first draft compared the
  intercept EV against the SLOT INDEX (always 0, flak always won).
  The pick now recomputes the fire EV from the pick's own weapon at
  the live player distance (one `score_weapon` call, shared
  formula).
- `_damage_quality` rolls a 0.51–1.5× multiplier, so a light laser
  CAN one-shot a hp-6 missile — the phase-1 chip test was
  latent-flaky on the ambient RNG sequence and the new tests'
  consumption shifted it; pinned (`roll=50, spread=1.0`).
- The combat guide section sits at a 3000-char conciseness cap; the
  two new guide sentences were trimmed to fit ("Enemy racks fire the
  same rounds at you."; the guns-only flee sentence).
- Enemy flak lines reuse `enemy_attack_line` through a
  `target_name` parameter (the object segment was hard-coded
  " you. ") — the exact mirror of the player's own flak lines; the
  kill rides `finish_intercept`'s existing line. Zero new prose
  beyond the fratricide DRAFT above.

## The shape

### Flight entity

- `WeaponSpec` gains two missile-only fields (defaults 0):
  `flight_speed` (cells per combat round; 0 = resolves at launch —
  the EMP pulse) and `missile_hp` (intercept difficulty).
- An in-flight missile holds: position, target reference, owning
  side, launcher `weapon_id` + its rolled quality (arrival damage
  rides the shooter's tier, doc 48.7), current `missile_hp`,
  remaining fuel. It joins `game_map.entities` for rendering and the
  target cycle — NOT the `enemy_insts` roster (no AI turn of its
  own; movement is deterministic). Two ADVISE pins: the entity is
  NON-BLOCKING (zero footprint — `blocking_entity_at`, enemy
  stepping, and A* treat a crossing missile as empty space; the
  reinforcement matcher `_find_reinforcement_entity` skips it), and
  its field shape is EnemyInstance-COMPATIBLE (`name`, `pos`,
  `hull = max_hull = missile_hp`, `shields=0`, `alive`,
  `cells_moved_this_turn=0`, `pilot_piloting=0`, `weapons=()`) —
  `hit_chance`, `damage`, `can_fire`, and the strip path
  (shields=0 → no-op by construction) all work with no adapter
  layer.
- **Homing, fuel-capped**: each advance re-vectors toward the
  target's live position; total travel is capped at the launcher's
  `max_range` cells (fuel). Kiting a missile extends its flight
  (more intercept windows for the defender's flak) and raises the
  target's dodge at arrival — outrunning it is a real counter.
  Target dead at re-vector time → the missile dissipates next step
  (fuel spent). The shooter's death does not recall a launched
  missile.
- **Round-boundary cadence**: all in-flight missiles advance one
  `flight_speed` step at one fixed phase point — after enemy turns
  and reinforcements complete, before the player's next action —
  each step rendering (the wordless dread beat). Arrival resolves
  there: guidance roll, then the existing damage path on a hit. An
  ARRIVAL kill runs the full kill chain (`on_kill` — XP, loot,
  bounty, rep, `defeated_*` records) exactly like a volley kill;
  bookkeeping never depends on which path dealt the blow. The
  Momentum volley refund is volley-time mechanics and does not
  reach delayed kills — missile-arrival kills simply don't refund.
- **Guidance roll** (pure, shared by both sides): quality-scaled
  launcher accuracy − the target's dodge-at-arrival (the existing
  `_calc_dodge_bonus` assembly: cells moved + piloting/2, cap 30),
  clamp 5–95. Hit → `resolve_damage` with the doubled rack damage
  (quality × variance as today). Miss → harmless detonation at the
  impact cell. EMP never reaches this path.

### Fire, targeting, floors

- **Fire**: a volley member with `slot_type="missile"` and
  `flight_speed > 0` spawns a flight entity instead of resolving
  instantly; ammo/power/AP pay at launch exactly as today (the
  volley's max-AP-once and refund rules unchanged).
- **Floors**: `can_fire` refuses missile shots inside the floor
  (SETTLED 2); the refusal surfaces on the card/range line like
  the existing out-of-range states.
- **Targeting**: a NEW merged accessor (`targetables`:
  `enemy_insts`, then hostile in-flight missiles) feeds exactly the
  TAB cycle, the target card, the hit-chance/range-line reads, and
  the fire path. Every other index-space reader stays SHIPS-ONLY:
  `combat_should_end` (VICTORY ignores live missiles — they die
  with the fight, never gate the end), `reaction_volley`, and
  `board_target` (D on a missile target DENIES — nothing to
  board). The HUD enemy block gains missile rows and a target
  marker that tracks the merged selection. A volley fired at a
  missile applies member damage to `missile_hp`; the INTERCEPT KILL
  takes a dedicated branch — entity removed, explosion beat,
  `Missile destroyed.` — and never reaches `rules.on_kill` (no XP,
  loot, or reputation for shooting down ordnance). Missiles have
  dodge 0 (they are deterministic travelers) and no shields.
- **Enemy AI (phase 2)**: a flak decision layer — score(inbound) vs
  score(shooter) per action through the existing scorer pattern;
  enemies with fast cheap weapons prefer flak. Enemy missiles are
  interceptible by the player through the identical machinery.

### Player-facing lines (DRAFT — settle before `/implement-phase`)

Six new lines, system voice, terse (the existing fire lines are
outcome-shaped hit/miss forms and cannot carry a launch):

- launch: `Heavy missile away.`
- intercept kill: `Missile destroyed.`
- arrival miss: `Missile detonates short.`
- fuel exhaustion: `Missile exhausts its fuel.`
- floor refusal: `Target inside minimum range.`
- board denial on a missile: `Nothing to board.`

## Phases

- [x] **1. Flight + player-side interception** — brief below
      (BUILT + PLAYTEST PASSED 2026-10-01, v2 flight model per
      SETTLED 11; prose settled same day)
- [x] **2. Enemy missiles + the flak AI layer** — brief below
      (BUILT 2026-10-01 via `/implement-phase 57.2`; brief was
      PROPOSED, the ADVISE pass ran at the top of the build session —
      13 catches, 4 blocking, all folded before code; playtest
      pending)
- [ ] **3. Calibration** — brief below (PROPOSED)

## Implementation brief 57.1 — flight + player-side interception

**Scope** (files / hook points):

- `data/weapons/__init__.py` — `WeaponSpec` gains `flight_speed:
  int = 0`, `missile_hp: int = 0` (+ docstring: 0 = resolves at
  launch / not interceptible).
- `data/weapons/missiles.py` — the ruled row: light dmg 28 / range
  4–9 / hp 2 / speed 4; heavy dmg 64 / range 5–13 / hp 6 / speed 2;
  EMP unchanged magnitudes + `flight_speed=0`.
- New `combat/_missile_flight.py` — the flight domain: an
  `InFlightMissile` dataclass, and pure helpers for advance-step
  math (re-vector, fuel accounting, arrival detection), the
  guidance roll, and intercept-damage application. State-holder
  coordination lives in `SpaceCombatState`.
- `combat/_types.py` — `SpaceCombatState.in_flight: list` field
  (combat-transient; combat never saves mid-fight).
- `combat/_rules_space.py` — spawn-on-fire for flight members
  (branch on `flight_speed > 0`; EMP rides today's instant path);
  `can_fire` floor gate (missiles only); missile-arrival resolution
  at the round boundary; target-adapter reads for hit-chance /
  card / range line.
- `combat/_loop.py` — `_handle_fire` accepts a missile target via
  the merged `targetables` accessor (volley rules unchanged:
  max-AP-once, per-weapon costs, mid-volley target death breaks
  the loop, refund rules untouched); `_cycle_target` over the
  merged list; round-boundary advance hooked after `_end_turn`
  (enemy turns + reinforcements) and before the player's next
  action. `_handle_fire` sits AT the 40-line function limit — the
  intercept branch must be an extracted helper, never inline.
- `hud.py` / `hud_combat.py` — missile rows in the enemy block, a
  target marker tracking the merged selection, and a DISTINCT
  refusal read on `range_band_color` inside a missile floor (not
  the penalty-orange the lasers keep).
- `combat/_space_presentation.py` — a missile target-card variant
  (name / HP / speed; no band, AP, weapons, or shield rows).
- Cleanup — `sync_state` sweeps `state.in_flight` AND removes
  missile entities from `game_map.entities` on every combat end
  path (victory / disengage / flee / defeat), re-run at
  `_activate_combat_state` as the abnormal-end belt-and-braces:
  entities serialize with the map, so a leftover glyph corrupts
  the next save (save/load contract).
- Rendering — missiles as entities via the world draw path: heavy
  `♦`, light `*` (SETTLED 10), hostile inbound hot red, player-owned
  the cyan/friendly accent; intercept kill = small explosion beat
  at the cell.
- Guide (`data/guide/`) — the missile/weapon sections gain flight,
  interception, and the floor gate; call the diff out on the
  checklist.

Budget note (forecast, not a placement driver): `_rules_space.py`
sits at 955/1000 lines — the spawn branch, floor gate, arrival
wrapper, and accessor reads trip the module ratchet; expect the
in-commit refactor that moves flight mechanics into
`_missile_flight.py` (the cohesive home — pure advance/guidance
math + the entity type; the state field on `SpaceCombatState`).

**Build order**: data fields + pins → flight module + state field +
spawn-on-fire (+ non-blocking entity) → round-boundary advance +
arrival resolution (full kill chain) → floor gate → merged cycle +
dedicated intercept branch + HUD/card → cleanup sweep → render
beats → guide.

**Binding rulings**: SETTLED 1–7, 9 as written above, plus the
ADVISE-folded pins: the intercept kill NEVER reaches `rules.on_kill`
(dedicated branch — no XP/loot/rep for ordnance); an arrival kill
runs the full kill chain but never the Momentum refund
(volley-time mechanics); the floor gate reads the catalog min —
Focus does not widen the refusal band; volley-at-a-missile follows
normal volley inclusion — the active-weapon toggles are the
flak-escort expression (SETTLED 8); enemy volley members still
resolve INSTANTLY this phase (expressible without touching `_ai`),
and the shared catalog means THEIR damage is already doubled —
enemy heavies hit at ×2 with no intercept window until 57.2 lands
(known interim spike; 57.2 follows promptly); in-flight state dies
with the fight on every end path via the sync sweep — nothing
serializes, nothing leaks.

**Required tests** (same commit): spec pins for the new fields and
magnitudes (incl. EMP `flight_speed=0`); advance-step math (re-vector
toward live target, fuel cap at `max_range`, dissipate-on-dead-target,
arrival detection incl. overshoot); floor gate (missile refused
inside 4/5, laser penalty path untouched, Focus does not widen the
gate); interception (damage applies to `missile_hp`, kill removes
entity, strip weapons do nothing); bookkeeping split (intercept kill
records NOTHING — no XP/loot/rep/`defeated_*`; arrival kill records
EVERYTHING through the kill chain); end-check ignores live missiles
(last ship killed by lasers while a friendly missile flies →
VICTORY, missile swept); D-denial on a missile target; entity
non-blocking (walk and A* through a missile cell); arrival (guidance
roll formula incl. dodge-at-arrival and clamp, miss = zero damage,
hit = doubled base × quality × variance through the resolve path);
flight-state cleanup on every combat end (no missile entities on the
map post-fight); merged-cycle ordering. Existing volley tests adapt:
player missile members no longer resolve instantly.

**Stop point**: no enemy AI changes, no enemy-fired flight (57.2),
no calibration (57.3), no contrail/motion polish beyond the intercept
beat, no magazine/BH/cargo edits.

**Playtest checkpoint** (dev mode: SPACEHACK_DEV start → buy heavy
missile + light lasers + rounds at the mechanic):

1. Kite a pirate to range ≥ 5; F the heavy — the missile launches
   (existing fire line), crosses cells over rounds, arrives with the
   ×2 feel (≈64 base through quality/variance).
2. While YOUR missile is mid-flight (self-intercept sandbox), TAB
   cycles onto it; the card reads Heavy Missile / HP 6 / speed 2;
   F a light laser at it — HP chips, the killing shot removes it
   with the explosion beat, nothing arrives.
3. Try the heavy inside range 5 — refused (`Target inside minimum
   range.`); a laser inside ITS floor still fires at the penalty
   (semantics unchanged).
4. EMP at a shielded pirate: instant 100% strip, no entity ever on
   the map, cap 2 enforced as before.
5. Rushdown: sit inside the heavy's floor — dead stick; back off
   above 5 — it fires again (the back-off dance, doc 48 SETTLED 40).
7. Kite-test: fire at a runner, then keep moving — flight extends,
   fuel can exhaust (`Missile exhausts its fuel.`).
8. Expect the interim spike: ENEMY missiles fire instantly this
   phase and already hit at ×2 (heavy ≈64, no intercept window) —
   known and accepted until 57.2 lands.
9. Regression: a pure-laser fight plays exactly as before — no
   cycle noise, no pacing change; save/quit/continue outside combat
   is clean.
10. Guide diff review (flight/interception/floor entries).

## Implementation brief 57.2 — enemy missiles + the flak AI layer

**Scope**:

- `combat/_missile_flight.py` — owner-side arrival vs the player
  (the same pure guidance roll; DEFEAT possible at the boundary);
  enemy missiles join the merged target cycle — the player's
  TAB+F interception becomes real defense. SETTLED 11 timing: the
  enemy shooter's missiles resolve their mini-turn at the START of
  that enemy's turn (inside `_take_enemy_turn`, before its first
  verb), one at a time — the mirror of the player's hook.
- `combat/_ai.py` — enemy volley missile members spawn flight
  entities (the mirror of the player seam); the ENEMY FLOOR GATE:
  `_affordable_members` AND the affordable branch of
  `_ranked_weapons` gain the missile floor refusal (a member inside
  its floor sits out, exactly like the player's per-member
  `can_fire` refusal — composes with doc 56 SETTLED 24's
  affordability inclusion; the dual gate is load-bearing: a gated
  pick with an ungated ranked walk spins `_take_enemy_turn` forever
  on a zero-member "SPENT", ADVISE confirm 5; the wish list
  `affordable_only=False` stays ungated — it keeps a hugged
  rack-carrier backing off to its floor instead of going inert),
  and the cornered fallback no longer fires missile members inside
  the floor (updating the pinned `tests/combat/test_enemy_fire.py`
  behavior); the doc records: this supersedes SETTLED 24's
  fire-at-penalized-floor rule for MISSILE members only. The flak
  decision layer: per action, score(inbound missile) vs
  score(shooter) through the existing scorer pattern (expected
  intercept value = p(hit) × hull coverage × threat / AP vs
  expected volley EV), enemies with fast cheap weapons prefer flak
  — a scorer, not branches. Flak sits INSIDE the fire branch
  (passive agg-0 ships never point-defend: flak is an attack verb,
  the roll is the temperament, ADVISE 9c).
- `combat/_rules_space.py` — the flee reaction volley (doc 54)
  excludes FLIGHT racks only, gated on `flight_speed > 0`: reaction
  fire is guns-only because missiles cannot chase a fleeing ship
  (the fight ends before arrival — wasted rounds); the EMP pulse
  is instant and STAYS a reaction weapon. [ADVISE 8 amendment] the
  exclusion lands in `_ai._reaction_pick` — the single production
  choke point (only caller: `reaction_volley`), beside its other
  selection-time filters; `reaction_volley` itself is untouched.
- Rendering — [SETTLED 10 supersedes this line's original "glyph
  distinct" wording] enemy missiles read by COLOR: `_build_missile`
  already paints side fg (hostile hot red, player cyan) over the
  shared family glyphs; no glyph change.
- Guide — enemy-missile / point-defense note (the paragraph covers
  only the player's own racks today) plus the reaction-fire wording
  fix ("everything in range fires" stops being true when racks
  hold); exact before/after on the checklist.
- Prose (DRAFT, checkpoint approval — ADVISE blocking 2): the
  fratricide hit line `"{shooter}'s {Missile} detonates on {victim}
  for N damage."` (the settled player form parameterized by
  speaker); enemy launches are WORDLESS (SETTLED 1's glyph doctrine:
  the crossing IS the notice); arrivals speak the existing
  `enemy_attack_line` forms verbatim; enemy flak at the player's
  missiles parameterizes the attack line's object (`at {Missile}.
  It misses!` / `It hits for N damage!` — the exact mirror of the
  player's own flak lines) and the kill rides `finish_intercept`'s
  existing `Missile destroyed.`

**Build order**: enemy spawn mirror → player-side interception of
enemy missiles (mostly free from 57.1) → flak scorer → reaction
exclusion → render + guide.

**Binding rulings**: SETTLED 1–8 apply symmetrically; both sides'
missiles obey identical physics INCLUDING the floor gate (the
enemy-side gate is this phase's SETTLED-24 supersession, scoped to
missile members). Reaction-volley exclusion gates on
`flight_speed > 0` (EMP remains a reaction weapon). Shooter death
mid-flight does not recall the missile; target death mid-flight
dissipates it next step.

**Required tests**: enemy missile spawn on volley; the enemy floor
gate (member sits out inside the floor; cornered missile-ships no
longer fire through it — pinned tests updated, incl. the ranked-walk
gate); flak scorer table (flak preferred when intercept EV beats
shooting EV; the score-zero never-picked rule preserved); player
interception of enemy missiles; DEFEAT via arrival; DEFEAT via the
launch half-move at the (3,3) diagonal (the light-rack geometry,
ADVISE 1); reaction volley fires no flight racks but MAY fire the
EMP pulse; reinforcement joiners with racks fly them; shooter-
identity avoidance (same-shooter sidestep, cross-shooter ignore);
orphan cadence (dead shooter: exactly-once-per-round, never both
paths); the enemy guidance roll derives from the shooter's snapshot
gunnery, never the player's perks (ADVISE 11); the fratricide kill
records NOTHING for the player.

**Stop point**: no calibration (57.3), no probe rows, no magazine
changes.

**Playtest checkpoint**:

1. Fight missile-carriers (pirates → warlord): watch THEIR heavy
   cross the map at you — the dread beat.
2. TAB+F it down with the light-laser escort (toggles off the
   heavies first); feel the manual-flak rhythm under saturation.
3. Eat an unanswered heavy (≈64 into hull) — the gamble's teeth.
4. Kite during flight: your movement extends its flight and raises
   your dodge at arrival.
5. Flee through an exit under racks: reaction fire is guns only.
6. Kill a shooter with its missile inbound: the missile still
   arrives (already launched).
7. Regression: ground combat untouched; reinforcement joins carry
   racks cleanly.
8. Guide diff review (exact edits, section "Combat"):
   - Missile paragraph — before: "…shot down in flight, just like
     an enemy ship. Any ship its flight path crosses takes the
     hit…"; after inserts one sentence: "Enemy racks fire the same
     rounds at you." between those two sentences.
   - Flee paragraph — before: "Everything in range fires once as
     you go, and those shots can kill you - or do not start the
     fight in the first place." (note the pre-existing spaced
     hyphen); after: "Guns in range fire once as you go and can
     kill you; missile racks cannot chase a fleeing ship, though an
     instant EMP strike can. Or do not start the fight in the first
     place."
9. Prose review (DRAFT until approved here): the fratricide line
   "Pirate Scout's Heavy Missile detonates on Pirate Escort for 64
   damage." (speaker-parameterized settled player form); enemy
   launches are WORDLESS and arrivals speak the existing attack
   lines; enemy flak speaks "…fires its Light Laser at Heavy
   Missile. It hits for 4 damage!" / "It misses!" (the player
   mirror's exact forms).

## Implementation brief 57.3 — calibration

**Scope**: `tools/balance_probe.py` rows + the magnitude dials this
doc owns: the ×2 multiplier (28/64), the floors (4/5), the intercept
families (hp 2/6, speed 4/2), and the magazine-saturation trade
(arrival rate vs flak density vs rack depth — SETTLED 8's expression
measured, not assumed). Numbers move only with probe rows; missile
magnitudes are owned HERE now (doc 56's phase 4 proceeds on
non-missile dials — its "missiles → doc 57" note stands). Runs
naturally in the same conversation as doc 56 phase 4 if convenient.
SYSTEMS.md entries land at the doc close. Harness note: flight
stretches space fights — expect `TURN_CAP`/`ACTION_CAP` bumps in
`tests/balance/harness.py` (its `_mirror_loop` drives the real
dispatch loop, so the round-boundary hook is picked up for free);
confirm the advance's render beats tolerate the absorbing console /
inert presentation.

**Build order**: probe rows (arrival-rate by band vs flak loadout;
saturation curves vs magazine depth) → dial passes → spec pins
updated in the same commits.

**Binding rulings**: the probe is the referee (doc 56's calibration
doctrine); acceptance = the criteria below measurably hold.

**Required tests**: updated spec pins per dial move; probe harness
rows land as reported outputs.

**Stop point**: this is the closing phase — after its playtest, the
doc close conversation (move to `complete/`, SYSTEMS.md inventory).

**Playtest checkpoint**:

1. A missile fight reads as artillery-vs-flak: standoff racks,
   crossing heavies, intercept beats — slower-but-dreadful, not
   fiddly (acceptance 5).
2. Saturation is real: deep racks beat thin flak; light-laser walls
   beat thin racks (acceptance 2–3).
3. Floors make rushdown total: inside 4/5 the racks say nothing
   (acceptance 5).
4. Probe rows reviewed with the user before any dial moves.

## Acceptance criteria

1. A missile fired at range resolves at impact, not at launch; both
   sides' missiles are interceptible by the same mechanics (the EMP
   pulse excepted, SETTLED 4).
2. light-laser builds demonstrably suppress missile volleys (probe
   row: a flak loadout cuts inbound arrival rate).
3. The magazine's depth measurably trades against flak (saturation
   is a real strategy, not a paper one).
4. EMP resolves instantly, never interceptible; its cap-2 magazine
   and price are its counters, unchanged.
5. The floors hard-gate missile fire inside light 4 / heavy 5;
   rushdown inside the floor is total immunity (SETTLED 2).
6. Combat pacing preserved: fights read slower-but-dreadful, not
   fiddly (playtest ruling).

## Open questions

None remain — all eight (plus the arrival-roll and floor-semantics
questions the flight model opened) settled 2026-10-01 above.
