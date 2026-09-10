# SIDEQUEST: NPC World Speed — the world moves on its own clock

**Status: REFINED — all questions settled (2026-09-10); brief (1)
PROPOSED awaiting approval; briefs 2-5 draft at each phase's
checkpoint.** Inserted as a sidequest between doc 41 phase 2
(implementation LANDED; playtest PARKED behind this doc) and phase
3. Companion: `41_DESIGN_THE_LINE.md`
(the watch is the first NPC schedule promised on the calendar — the
motivating system); `../complete/DESIGN_GAME_TIME.md` (the clock this
extends); `../complete/06_DESIGN_MILITIA_PATROLS.md` and
`npc_ships.py` (the stepper this changes).

## The ruling this doc serves (user, 2026-09-10)

> NPCs should have a speed stat. and they should move according to
> their speed stat, not the players speed stat.

Plus the adjacent time-consistency rulings made the same day:

1. **NPC world-speed is their own.** An NPC's tiles-per-day comes
   from the NPC's stat; the player's engine no longer dilates the
   universe.
2. **Combat costing 0 time is ACCEPTED** — user hand-wave, recorded
   so it is never re-litigated: in combat you greatly speed your
   ship up; that puts a lot of stress on the human body, and doing
   it in bursts for combat is OK — but it is not the speed you fly
   at comfortably. Combat is calendar-instant.
3. **Cities and dungeons passing no time is ACCEPTED** — "you can
   move a lot in a day. it's fine."
4. **The wait end goal**: NPCs move as far as they can in 1 day,
   **with carry-over** (a space-wait passes a full day of world
   movement, fractional progress included).

Ruled at refinement (Settled 1): jumps stay INSTANT — the burst
hand-wave extends to gate transit; the zero-time set (jumps, combat,
cities, dungeons) is final.

## What exists today (verified in code, 2026-09-10)

- **One clock, and it is the player's**: `time.tick_move` flips the
  day every `effective_speed` player moves (ship base + engine
  modules, 6–14); `advance_time` is the sole mutator.
- **NPCs have no map speed**: `move_npcs` runs once per PLAYER
  action (manual move, GO TO step, space wait); every squad gets ≤1
  tile at a flat 80% probability. `NpcShipSpec.base_speed` never
  touches map movement — it only gates stationary hulls (derelicts)
  out of the patrol machinery.
- **Consequence**: NPC tiles/day ≈ 0.8 × the player's engine. A
  speed-14 racer speeds every patrol and relief flight up to ~11
  tiles/day; a speed-6 hauler slows the universe to ~5.
- **Zero-time actions**: jumps, combat, city stays, dungeon delves.
  A space-wait passes exactly 1 day but only ~1 NPC tile (the
  2026-09-10 fix; its asymmetry is this doc's ruling 4).
- **Day-granular consumers** (anything the rework must not break):
  quest deadlines/gates, economy ticks, shop stock (monthly),
  reputation decay, the doc-41 WATCH (tenure boundaries, launch
  leads, departures — all day-granular by design).
- **Step-granular movers**: pirate/patrol/merchant squads and the
  watch flights (`npc_ships._step_squad`,
  `navigation_line._advance_flight` — deliberately twin mechanics),
  plus city NPCs and ground hunters (own tickers, likely out of
  scope).

## Design sketch — the accumulator model (for refinement)

Every moving NPC entity (or squad — open question 5) carries a
**movement accumulator** of tiles owed:

- Per PLAYER STEP: the world advances `1 / player_speed` days, so
  each mover gains `npc_speed / player_speed` tiles of credit.
  Move one tile per whole credit; the fraction carries.
- Per SPACE-WAIT (and any future day-granular advance): each mover
  gains a full `npc_speed` tiles — ruling 4 verbatim, carry-over
  included.
- Multi-credit steps sub-step CELL BY CELL along the cached path
  (never teleport: detect radii, dark-spot challenges, and combat
  triggers must fire per cell — settled ruling 4 in the Settled
  section).
- Motion is DETERMINISTIC (settled): no throttle, no jitter — the
  accumulator's skip-then-step rhythm is the visual cadence.

### What this changes under the hood

- **Data**: `NpcShipSpec.base_speed` repurposed as THE map-speed
  stat, hull-derived by default (settled ruling 2): scout hulls 14,
  cruiser 9, frigate 8, hauler 7, freighter 6; explicit authoring
  wins (derelicts 0).
- **State**: the accumulators are new mutable state → a ctx field
  (dict keyed by squad id / spawn key, mirroring `npc_targets`
  naming) → **save/load contract work**. ADVISE round (2026-09-10):
  the accumulator persists EXACTLY WHAT THE PATH SYNC PERSISTS —
  current-system procedural squad mids round-trip (one line inside
  `_sync_spawn_entry`); watch tenure keys and other systems'
  squads default 0. Persisting watch keys would be incoherent (an
  in-flight relief restarts AT ITS BASE on load — build-side
  reconciliation — so forward credit on a position reset is dead
  credit) and unbounded (monotonic `tN` keys never popped:
  ~14 dead keys per boundary forever). The kernel POPS the
  accumulator at every site that pops `npc_targets`/`npc_paths`
  today (`_arrive`, `_despawn_merchant`). Existing saves default
  0 — no migration. The save-sync logic lives in the kernel module
  (`saveload.py` sits at 989/1000 — the doc-41 precedent: saveload
  takes no new logic).
- **Steppers**: `_step_squad` and `_advance_flight` converge on ONE
  shared movement kernel (pay credit → sub-step cells → pop path) —
  the phase-2 audit already flagged their twin mechanics.
- **The watch retunes**: launch leads were measured at speed 10
  under 0.8×player-speed math; under own-speed movement a picket at
  npc-speed ~10 flies ~10 tiles/day deterministic — leads are data,
  re-measure and retune (phase below).
- **Performance**: slow players see fast NPCs multi-step per player
  action (bounded: npc_speed/player_speed ≤ ~2.3 at speed 6 vs
  npc-speed 14); A* stays cached per mover; no new passes over
  `entities`.

## Settled — the ruling session (2026-09-10, `/refine-design 44`)

All eight open questions ruled; the sketch above stands as amended.

1. **Jumps stay INSTANT** — the burst hand-wave extends to gate
   transit (same fiction as combat: burst drive use stresses the
   body; comfortable cruise is what the calendar measures). The
   zero-time action set is final: jumps, combat, cities, dungeons.
2. **`base_speed` is repurposed — and its values DERIVE FROM THE
   HULL** (user: "the specs have a ship hull. player ships with
   those ship hulls have a base speed stat right? we should base
   npc base speed off of those speed values."). One source of
   truth: the ship catalog. `NpcShipSpec.base_speed` defaults to
   unresolved and resolves to `find_ship(spec.ship_id).speed`;
   explicit authoring wins (derelicts stay pinned at 0 — the
   stationary gate must keep working). Launch values:
   scout hulls 14, cruiser 9, frigate 8, hauler 7, freighter 6.
3. **The 80% throttle is DROPPED** — motion is deterministic and
   honest to the stat: a speed-9 cruiser crosses exactly 9
   tiles/day. The accumulator's skip-then-step rhythm (credit
   builds below 1 tile, then a tile) is the visual cadence.
4. **Per-cell sub-stepping, checks at every cell** — a fast mover
   never tunnels through the player's detect radius or a picket's
   challenge range between checks. Per-step cap ~2.3 cells
   (speed-14 NPC vs a speed-6 player); a WAIT pays up to a full
   day — 14 cells in one pass — which is exactly the tunneling
   case this ruling exists for (phase 3 re-states it). BINDING
   clamp constraints (ADVISE round, 2026-09-10): (a) the proximity
   predicate is evaluated per intermediate cell BEFORE committing
   each step — post-hoc checks cannot see in-and-out tunneling
   (the movement passes run encounters at their TOP and move NPCs
   at the TAIL); (b) STOP ≠ FIRE — the kernel parks the mover at
   the triggering cell and the encounter opens at the top of the
   NEXT pass; the kernel never opens combat or comms itself
   mid-`move_npcs` (modal recursion into the movement pass);
   (c) perf is argued at the 14-cell wait bound, not the step
   bound (cached path pops + `try_step_with_slip` per cell —
   still cheap).
5. **Per-SQUAD accumulators** — one per squad, keyed like today's
   path dicts (movement id / watch spawn key); the leader's speed
   drives the squad, cohesion stepping keeps formation. Convoys
   stay convoys; the watch's single-ship flights are one-member
   squads of the same mechanism.
6. **City NPCs and ground hunters are OUT OF SCOPE** — they tick
   off their own wander/pursuit systems with no calendar presence.
7. **Merchant timing resolves via the hull rule** — haulers at 7,
   freighters at 6 (slightly slower than today's effective 8 at a
   speed-10 player). Ambient density reads slightly sparser per
   system-crossing; the phase-5 playtest watches it, no separate
   retune phase.
8. **The parked 41.2 playtest runs AFTER 44 lands** — on the new
   movement math, with the watch leads retuned (phase below).

**Consequence worth watching (not blocking): scout-hull NPCs fly
at 14 — the game's top speed.** Today nothing on the map outruns
the player (NPCs step 1:1); under own-speed, a pirate scout
outruns every player hull except the scout itself (equal speed —
a standoff). A starter (10) cannot disengage a scouting pirate by
running. If that texture reads wrong in play, the cheap knob is
per-spec authoring overrides on the fast hulls (explicit
`base_speed` values win over the hull default) — the mechanism
ships with this phase either way.

**Alternative rejected (ADVISE round, 2026-09-10 — do not
re-propose): deriving credit from the clock instead of
accumulators.** The clock is day-granular (a wrapping triple;
`tick_move` flips a day per `effective_speed` moves — no sub-day
state to difference), so delta credit would arrive as
`npc_speed`-sized bursts on day flips (a scout sits 13 steps,
then jumps 14 cells), violating the ruled skip-then-step cadence
and hitting the 14-cell tunneling case for every mover on every
flip day. Per-squad accumulators stand; the genuinely cheaper
variant folded in above is the path-sync lifecycle mirror, which
keeps the new persisted surface no larger than what already
round-trips.

## Phases (build queue — `/implement-phase 44.<p>` works top-down)

- [x] Phase 1 — Hull-derived speeds: `base_speed` resolves from
      the spec's hull (derelicts pinned 0; explicit authoring
      wins), every spec resolves, tests

  LANDED 2026-09-10 (1667e5a) — reviewer APPROVE (reproduced the
  predicted `None > 0` TypeError read-only; confirmed the seam
  test catches it); no player-visible change (the resolver is
  dead data until phase 2 wires it), guide diff NONE.
- [x] Phase 2 — The accumulator kernel: per-squad credit at
      `npc_speed / player_speed` tiles per player step,
      deterministic sub-stepping with the Settled-4 clamp
      constraints (per-cell predicate, stop-≠-fire, argued at the
      14-cell bound), the patrol stepper and the watch flight
      stepper converge on one shared kernel, accumulator
      persistence MIRRORING the path-sync lifecycle (current-system
      patrol mids round-trip; watch keys default 0; pop at every
      target-pop site; sync logic in the kernel module — saveload
      takes no new logic)

  Implementation brief (2) — APPROVED (drafted at phase 1's
  checkpoint 2026-09-10; user invoked ``/implement-phase 44.2``):

  - **Scope.** NEW ``src/spacehack/npc_movement.py`` — the credit
    kernel (``npc_ships.py`` is 909/1000 and cannot grow;
    ``navigation_line.py`` is the Line's domain): ``step_credit``
    (accrue ``map_speed(spec) / player_speed`` on the squad's key,
    spend whole tiles sub-stepping the cached path cell-by-cell,
    keep the fraction), the clamp (BEFORE committing each cell: if
    the cell about to be entered lies inside that spec's
    player-encounter trigger, ENTER it, park there, spend no
    further credit — stop ≠ fire, the encounter opens at the top of
    the NEXT pass; the kernel never opens modals), and a blocked
    direct step keeps its credit (retry next pass — the kept-path
    collision idiom). Consumers: ``npc_ships._step_squad``'s
    movement section and ``navigation_line._advance_flight``
    converge on the kernel (the twin-mechanics debt the doc-41
    audit flagged); the 80% throttle and its RNG call are REMOVED
    from stepping (deterministic ruling; RNG stays for target
    picks). The no-path aggro drift fallback stays 1-tile-per-step
    (far-away only, untouched). ``player_speed`` computed ONCE per
    ``move_npcs``/``step_watch`` pass (perf rule), via
    ``ship.effective_speed``. State: ``GameContext.npc_credit:
    dict[str, float]`` (declared on the type's own module);
    persistence MIRRORS the path sync — the kernel module owns the
    sync shape, ``saveload`` grows only mechanical lines
    (``_sync_spawn_entry`` carries credit beside targets/paths for
    current-system mids; watch keys and other systems never
    round-trip — they default 0); every site that pops
    ``npc_targets`` (``_arrive``, ``_despawn_merchant``, path-drop
    branches) pops the credit key with it. saveload.py is at
    ~990/1000 — if the mechanical lines push it over, the parse
    side moves into the kernel module in the same commit.
  - **Build order.** (1) the kernel + unit tests (credit math,
    carry-over, clamp-parks, blocked-keeps, purity of the credit
    helpers); (2) ``npc_credit`` on GameContext + save/load mirror
    + round-trip tests (patrol mid persists; watch key drops);
    (3) ``_step_squad`` rewires to the kernel + tests (deterministic
    — the throttle RNG is no longer consumed by stepping);
    (4) ``_advance_flight`` rewires + tests (picket 9 vs player 10
    ≈ 9 tiles/10 steps with visible carry-over); (5) full-gate
    regression (the watch pass, merchants, and dark-spot tests all
    still pass under deterministic motion).
  - **Binding rulings.** Settled 2/3/4/5 + the ADVISE lifecycle
    mirror; NO wait-day payment yet (phase 3 — a wait still pays
    one ordinary step of credit until then); no watch lead retune
    (phase 4 — reliefs run slow/late against the tuned leads in
    the interim, expected); no doc-41 files change.
  - **Required tests.** Credit math incl. the 14/6 ≈ 2-tile case
    with carry; fraction carried across steps exactly; clamp parks
    at the triggering cell and spends no further credit; blocked
    step retains credit; persistence round-trip (current-system
    patrol mid survives; watch spawn key does not); pop-parity
    (arrival/despawn clears credit with the target); throttle
    removal (stepping consumes no RNG); both consumers step by
    credit (picket-vs-player-10 cadence).
  - **Stop point.** NOTHING from phase 3 — no day-granular wait
    payment, no ``advance_time`` changes; NOTHING from phase 4 —
    no lead retune; no phase-5 playtest items.
  - **Playtest checkpoint.** None in-phase (observability arrives
    with phase 3's wait); phase 2's verification is the gate +
    the watch/merchant regression suite.

## Pre-implementation audit — phase 2 (2026-09-10, verified in code)

**Seams (all verified):**

- **Kernel home**: new ``src/spacehack/npc_movement.py``
  (``npc_ships.py`` 909/1000 and ``navigation_line.py`` 817/1000 —
  neither can own shared machinery). The kernel owns the CREDIT
  ACCOUNT (accrue/settle — settle caps retained credit at 1.0:
  fractions carry, bursts don't bank), the CLAMP (pure
  ``enter_trigger(cell, player_pos, radius)`` — Euclidean, the
  spec's ``detect_radius``, checked on the cell about to be
  entered BEFORE committing; enter, park, stop spending), the
  single-entity sub-step loop (``spend_credit`` — walks
  ``ctx.npc_paths[key]`` with ``try_step_with_slip``, pops the
  head only on direct steps, returns an outcome), the
  ``player_moves_per_day(ctx)`` read (mirrors ``tick_move``:
  ``effective_speed`` over the owned ship, fallback 10, computed
  ONCE per pass by each consumer) and the save-side shape helper
  (``pick_synced_credits``; the load side is one inline mechanical
  line in ``_restore_core_fields``, beside the target restore) so
  ``saveload.py`` grows only mechanical lines (+5 total; 989 → 994).
- **DRY judgment (pinned)**: the two consumers' walking loops do
  NOT fully merge — the patrol moves leader+members per cell
  (cohesion stepping is squad-specific), the flight is
  single-entity with arrival semantics. The CONVERGED surface is
  the credit account + clamp + settle + stale/blocked idioms;
  ``npc_ships`` extracts its per-cell squad block into a local
  helper and loops it under credit. Full-loop sharing would need
  callbacks — rejected.
- **State**: ``GameContext.npc_credit: dict[str, float]`` declared
  beside ``npc_targets``/``npc_paths`` (the type's own module).
  Persistence mirrors the path sync exactly: ``save_game``
  attaches ``pick_synced_credits(ctx.npc_credit, synced_mids)``
  (current-system patrol mids only — empty/other-system mids are
  ""); ``_restore_core_fields`` restores
  ``dict(data.get("npc_credit"))``. Watch spawn keys never
  round-trip (session-scoped flights, doc-41 ruling) — they
  default 0.0 and lose only a sub-tile fraction on rebuild.
- **Pop parity (all sites enumerated)**: credit pops beside every
  FULL target-pop — ``npc_ships._despawn_merchant`` (:749),
  ``npc_ships._step_squad``'s empty-path branch (:795),
  ``navigation_line``'s unreachable-drop (:560) and ``_arrive``
  (:577). The two STALE-PATH pops (:802, :566 — path only, target
  kept, still moving) keep their credit. ``merchant flee``
  (a dodge, not travel) and the no-path ``aggro drift`` fallback
  stay 1-tile-per-pass, uncredited — audit ruling, revisit only
  if the playtest reads wrong.
- **Throttle removal**: the 80% RNG gate at ``npc_ships._step_squad``
  is deleted; RNG remains in target picks / spawn rolls only. A
  test pins that stepping consumes no RNG.

**Duplication hotspots + DRY:** the clamp predicate must not be
re-derived at call sites (one pure kernel function); the settle
cap lives in ONE place (never inline ``min()`` at consumers); the
save-shape helpers live in the kernel, not saveload.

**Judgment calls pinned:** settle caps retained credit at 1.0
(anti-burst; phase 3's wait SPENDS its day, not banks it);
clamp radius = ``spec.detect_radius`` (the combat trigger; comms
ranges are larger and non-modal — a mover may cross a comms ring
between passes, acceptable); no clamp while AGGRO-chasing the
player (the player IS the destination — parking beside them is
the intent anyway).
  LANDED 2026-09-10 — reviewer REQUEST_CHANGES then APPROVE-grade
  fixes: the audit's one false claim (the ``_despawn_merchant``
  credit pop) shipped missing and is now test-pinned; the
  empty-path recompute gate restored to falsy (a ghost target can
  never pin a picket outside the lifecycle checks); the slip-case
  documented + pinned (blocked never implies motionless). Stepping
  is RNG-free; quest_ctx carries a default clamp-neutral player;
  guide reviewed — no section stale (movement cadence is not
  guide material). No player-facing checklist: observability
  arrives with phase 3's wait.

- [x] Phase 3 — The day-granular wait: a space-wait pays every
      mover a full day of movement with carry-over (ruling 4) —
      per-cell clamping REAPPLIES at the 14-cell wait bound

  Implementation brief (3) — APPROVED (drafted at phase 2's
  checkpoint 2026-09-10; user invoked ``/implement-phase 44.3``):

  - **Scope.** The wait path pays a FULL DAY of movement: thread a
    ``day_pass`` flag from ``game_loop._handle_wait_event`` through
    ``game_flow._run_combat_loop(also_move_npcs=...)`` into
    ``move_npcs`` and ``step_watch`` — in day mode each mover's
    rate is its whole ``map_speed`` (not ``/ player_speed``), so
    one wait walks up to 14 cells (scout) under the SAME
    per-cell clamp (Settled-4c). Ordering unchanged: the passes
    run, THEN ``advance_time(ctx, 1)``. Manual steps and GO TO
    keep the per-step rate (flag defaults False). Arrival and
    despawn bookkeeping resolves on the action after a day pass
    (the movers outrun the once-per-action target refresh —
    accepted; the day is one action). ``npc_movement`` may grow a
    tiny rate-picker (``rate_for(spec, player_speed, day_pass)``)
    so the two steppers share the mode logic. BOARDED waits are
    fights — no movement, no day (existing ruling).
  - **Build order.** (1) the rate-picker + unit tests; (2) thread
    the flag through the three call layers + tests (a wait walks
    ~speed tiles with carry and clamps per cell; a manual step's
    rate unchanged); (3) regression: the wait-day fix's own test
    (test_time) extended — the world moved a day AND the clock
    flipped.
  - **Binding rulings.** Settled 4 (carry-over) + 4c (the 14-cell
    bound re-clamps); deterministic (no RNG); the wait still runs
    the ordinary spawn/encounter passes exactly once.
  - **Required tests.** Day-mode rate == map_speed (picker units);
    a wait moves a scout-hull squad ~14 cells in one pass with
    the fraction carried; the clamp fires mid-day-pass (parks at
    the trigger cell exactly as per-step); manual/goto rates
    untouched; the clock flip still follows the passes.
  - **Stop point.** NOTHING from phase 4 — no watch lead retune
    (reliefs now OVERSHOOT their tuned leads: picket speed 9 vs
    leads tuned for effective-8 — arrivals run early; expected
    until phase 4 re-measures); no phase-5 items.
  - **Playtest checkpoint.** None in-phase (phase 5 owns the
    formal checklist); quick observability: waiting a day at the
    Line visibly walks reliefs a day of ground.

## Pre-implementation audit — phase 3 (2026-09-10, verified in code)

**Seams:** the flag threads exactly three layers, all verified —
``game_loop._handle_wait_event``'s space branch (the ONLY day-mode
caller; dungeon/city waits never reach the steppers),
``game_flow._run_combat_loop``'s ``also_move_npcs`` tail (adds
``day_pass`` beside it; the BOARDED guard already skips movement),
and the two stepper entry points (``move_npcs`` /
``step_watch`` → ``_move_one_squad`` / ``_step_flights`` →
``_step_squad`` / ``_advance_flight`` — each passes ``day_pass``
into ONE ``rate_for`` call; no other logic branches on it). The
kernel needs NO changes: ``spend_credit``'s while-loop already
sub-steps arbitrarily many cells with the per-cell clamp — the
14-cell wait bound is just a big credit, and ``settle``'s 1.0 cap
still bounds only the retained fraction. ``rate_for`` joins
``credit_rate`` in ``npc_movement`` (float(npc_speed) on a day
pass — the player's speed is irrelevant to a full day).

**Tests pin three independent facts:** the picker's math; the
day-mode BEHAVIOR (a scout-hull squad walks ~14 cells with carry
and the clamp parks mid-pass — via ``_step_squad``/``step_watch``
directly); and the WIRING (the wait handler passes
``day_pass=True`` into ``_run_combat_loop`` — captured at the
handler seam; the manual/goto callers keep the default).

**Judgment call pinned:** ``debug_session._run_space_turn``
simulates a MOVE, not a wait — default ``day_pass=False`` there;
a headless wait action can be added when a test needs it, not
speculatively.

  LANDED 2026-09-10 (acaa32e) — reviewer APPROVE (verified the
  threading's single day-mode caller + re-derived every test's
  arithmetic); the world's asymmetry the user flagged on 2026-09-10
  is closed: a wait moves the world a full day AND flips the
  clock. Guide diff NONE (no player-facing text; movement cadence
  is not guide material).

- [x] Phase 4 — The watch retune: re-measure base→station
      transits at picket speed 9, retune the launch leads (data),
      regression sweep of the doc-41 phase-2 checklist

  Implementation brief (4) — APPROVED (drafted at phase 3's
  checkpoint 2026-09-10; user invoked ``/implement-phase 44.4``):

  - **Scope.** DATA: the ``lead_days`` on every ``WatchStation``
    in ``luyten_star.py`` re-measured at picket speed 9 — the
    self-verifying form: a new data test computes the REAL
    ``world.find_path`` base-dock → station over the real Luyten
    map and asserts ``lead_days == ceil(path_len / map_speed(
    militia_blockade))`` per station, so the leads can never drift
    from the measured transits again. Tests: the count-pinned
    watch-build fixtures update to the retuned schedule (the
    run-day-1 muster count, the day-12 two-wave counts, the
    day-22/24/29 fixtures) — the numbers move, the semantics do
    not. Doc: one pointer line in doc 41's phase-2 LANDED note
    (its ``mustering`` observable and wait asymmetry both read
    differently under the retuned math; the parked playtest runs
    under THIS schedule). NO watch mechanics, no kernel, no lead
    semantics beyond the numbers.
  - **Build order.** (1) the measurement test (red against the
    phase-1 leads); (2) retune the data table to measured; (3)
    update the pinned-count fixtures; (4) full gate — the doc-41
    phase-2 suite IS the regression sweep.
  - **Binding rulings.** Leads are DATA (retunable); relief
    arrives ≈ shift end (round the transit UP — early beats
    late: an early relief parks and holds, a late one dips the
    line); deterministic speeds; nothing else in the watchbill
    moves (``shift_days``, cycle, rosters, spacing).
  - **Required tests.** The lead table == ceil(measured transit /
    picket speed) per station (the self-verifying pin); every
    existing watch test green on the retuned numbers.
  - **Stop point.** NOTHING from phase 5 — no playtest checklist
    is written or run here; no doc-42/43 hooks; no convergence
    work (doc 41 phase 3 stays parked behind the 41.2 playtest).
  - **Playtest checkpoint.** None — phase 5 owns the formal
    checklist; this phase's verification is the gate.

## Pre-implementation audit — phase 4 (2026-09-10, measured)

**The measured table** (real ``world.find_path`` base-dock →
station over the real Luyten map, ``ceil(len / 9)``):

| station y | base | path | lead now | lead new |
|---|---|---|---|---|
| 7 / 21 / 35 / 25 | north | 76 | 10 | **9** |
| 49 | south | 67 | 9 | **8** |
| 63 | south | 53 | 7 | **6** |
| 77 | south | 39 | 5 | 5 |
| 91 | south | 25 | 4 | **3** |
| 105 / 119 / 133 / 115 | south | 16–17 | 3 | **2** |
| 55 | south | 61 | 8 | **7** |
| 85 | south | 31 | 5 | **4** |

**Fixture arithmetic under the new leads** (launch(T) =
tenure_start(T) − lead): the day-1 build musters FOUR t1 reliefs
at the bases (y63's launch moves to run-day 2 — was five); the
day-12 two-wave fixture moves to DAY 13 with its counts intact
(t2 = 10, the thin vanguard t3:y25 launches exactly then — the
old day-12 numbers relocate cleanly); the same-station stacking
fixture moves to DAY 6 (t2 north launches run-day 6); the day-22
thin build carries FOUR t4 reliefs (was five); the day-skips test
keeps its asserts (base-stamped reliefs take orders on ANY step —
``_order_base_relief`` lives in the per-step pass, not the due
gate) with its stale comment fixed; ``test_boundary_rotates`` and
the murdered-relief tests are key-based and move nothing beyond
comments.

**Self-verifying pin**: the new data test recomputes this exact
table (``find_path`` over ``make_solar_system(system=LUYTEN,
watch_day=…)``) and asserts every ``lead_days == ceil(len /
map_speed(militia_blockade))`` — leads can never again drift from
the map they fly over. Round UP per the binding ruling (early
parks and holds; late dips the line).
  LANDED 2026-09-10 (e9a01f0) — reviewer APPROVE with its own
  re-measurement of the full table (and one catch: my comment
  edit wrongly said day 24 stamps four reliefs — it stamps SIX,
  y77 launches exactly that day; reverted). The leads are now
  self-verifying against the live map.

- [ ] Phase 5 — Playtest: same route at a slow and a fast ship —
      the world's speed reads constant; wait a day at the Line —
      reliefs visibly cover a day of ground; density + pursuit
      texture checks (settled consequence 7 + the speed-14 note)

  Implementation brief (5) — APPROVED (drafted at phase 4's
  checkpoint 2026-09-10; user invoked ``/implement-phase 44.5``).
  This phase is the user's playtest; the brief is its checklist.
  On PASS, doc 44 closes and doc 41's parked phase-2 checklist
  resumes IN THE SAME RUN.

  - **Setup.** SPACEHACK_DEV run: it starts on the granted
    frigate (speed 8) with credits. For the speed contrast, buy
    the freighter (speed 6) and the scout (speed 14) at a city
    showroom (Earth's pad) — items 1-2 need both; the frigate
    itself is a fine middle reference.
  - **The checklist (numbered, in-game):**
    1. Fly a fixed Sol→Alpha Centauri leg at a SLOW hull, noting
       how many days the calendar advances and how far the
       ambient traffic (merchants, patrols) moves per day. Repeat
       the same leg at a FAST hull: the calendar advances FASTER
       per tile but the SAME SHIPS cross the same ground in the
       same number of DAYS — the world's speed reads constant.
    2. Pursuit texture: let a pirate scout (speed 14) notice you
       in a hull slower than 14 — it closes on the map. In the
       scout yourself, the same pirate holds distance (equal
       speed — the settled standoff). If it reads wrong, the knob
       is per-spec base_speed overrides.
    3. Ambient density: merchants cross in fixed days now
       (haulers 7, freighters 6) — space should read slightly
       sparser per crossing but not empty.
    4. At the Line (luyten_star): wait (.) a full day next to an
       inbound relief — it visibly covers ~9 cells of its
       approach per wait, and the calendar flips exactly one day.
    5. The watch schedule under the retuned leads: reliefs arrive
       ≈ shift end (early arrivals park and hold; no visible
       dip except the boundary's own turnover).
    6. Regression: doc 41's parked phase-2 checklist (items 1-11,
       in that doc) — its amended LANDED note describes the math
       this run uses.
  - **Guide edits: NONE** — movement cadence is not guide
    material (the round-1 ruling's spirit); no guide text changed
    in any phase of this doc.
  - **Stop point.** On PASS: close doc 44 (move to complete/,
    SYSTEMS.md inventory pass), then the doc-41 phase-2 playtest
    result is recorded and phase 3 (the convergence) is next —
    its brief is UNWRITTEN and drafts at that checkpoint.

  Implementation brief (1) — APPROVED (`/refine-design 44`
  2026-09-10, amended per the ADVISE reviewer round; user invoked
  ``/implement-phase 44.1``):

  - **Scope.** Data: `NpcShipSpec.base_speed` (``data/npc_ships/
    __init__.py``) becomes ``int | None = None`` — None resolves
    from the hull — AND the field's docstring + the default's
    comment update to the new meaning (hull-derived map speed +
    the stationary gate). Code: ONE pure resolver
    (``data/npc_ships/__init__.py`` — ``map_speed(spec) -> int``:
    explicit ``base_speed`` wins; else ``find_ship(spec.ship_id)
    .speed`` under ``except KeyError`` → a safe 1 — never raises
    mid-game) plus EXACTLY ONE call-site change (ADVISE blocker):
    the load-path stationary gate ``saveload_maps._add_procedural
    _npcs`` reads ``getattr(espec, 'base_speed', 0) > 0`` — under
    ``None`` it raises TypeError on EVERY Continue carrying a live
    procedural NPC — reroute it through ``map_speed(espec) > 0``
    (behavior-preserving: derelicts 0, movers 6-14, unknown 1).
    NEVER ``(base_speed or 0) > 0``: that truthy-fallbacks None to
    0, silently strips ``procedural_squad_id`` from every loaded
    NPC, and freezes the universe — a worse bug class than the
    crash. Derelicts keep their explicit 0 (``core.py`` already
    authors it — verify, don't touch). No stepper changes (the
    80% throttle still stands until phase 2).
  - **Build order.** (1) the resolver + the override-wins /
      derelict-0 / unknown-hull tests; (2) the field-type flip +
      docstring + the stationary-gate reroute + a save→load
      round-trip test with a live pirate (it must still move);
      (3) the data test pinning the launch table — hull-derivation
      asserts cannot pass before the flip (under ``int = 1`` every
      spec reads as explicit).
  - **Binding rulings.** Settled items 2 (hull derivation,
    explicit-wins, derelicts 0) and the speed-14 consequence note;
    data-first (a frozen dataclass field, no runtime attachment);
    NO stepper changes in this phase.
  - **Required tests.** The launch table per spec — with a NAMED
    pin that ``militia_blockade`` resolves 9 (phase 4's whole
    premise is transits at picket speed 9; a hull-grouped table
    could pass without naming the picket); override-wins;
    derelict-0; unknown-hull → 1 (never raises); the
    save→load round-trip with a live procedural NPC; the resolver
    is pure (no ctx, no RNG).
  - **Stop point.** NOTHING from phase 2 — no accumulators, no
    stepper changes, no wait changes, no watch retune. The one
    gate reroute above is data-plumbing, not a stepper change.
  - **Playtest checkpoint.** None — a pure data+resolver phase
    with no player-visible behavior change; the numbers first
    become observable in phase 2.

## Pre-implementation audit — phase 1 (2026-09-10, verified in code)

**Seams to extend:**

- **The spec field** — ``NpcShipSpec.base_speed``
  (``data/npc_ships/__init__.py``): currently ``int = 1`` with the
  docstring line "cells per movement tick". Flips to
  ``int | None = None``; docstring restates the hull-derivation
  contract. Only the two derelicts author it today
  (``core.py:34/66``, explicit ``0`` — the stationary pin,
  verified, untouched).
- **The resolver** — ``map_speed(spec) -> int`` in the same
  module: explicit ``base_speed`` wins; else
  ``find_ship(spec.ship_id).speed`` under ``except KeyError → 1``
  (``find_ship`` raises on miss — ``data/ships/__init__.py:52``).
  Lazy ``from ..ships import find_ship`` inside the function (the
  ships catalog imports nothing back — no cycle; catalog idiom).
- **The registry accessor** — the catalog exposes ``find_npc_ship``
  only; the every-spec test needs enumeration → add
  ``list_npc_ships()`` (the ``list_solar_systems`` sibling
  pattern, 3 lines).
- **The ONE call site reading base_speed outside data/** —
  ``saveload_maps._add_procedural_npcs``'s stationary gate
  (``getattr(espec, 'base_speed', 0) > 0``) reroutes through
  ``map_speed(espec) > 0``; the ADVISE round's TypeError blocker
  and the ``(or 0)`` trap are pinned by a seam test against this
  exact function (pirate keeps its squad id and moves; derelict
  gets none). A full save→load harness adds nothing the seam
  test does not pin — the crash lives in this function.

**Duplication hotspots + DRY strategy:**

1. Hull reads → one resolver, one truth; the gate reroute uses it
   (no inline ``find_ship`` calls anywhere else).
2. The test table vs. the data — the every-spec test derives the
   expectation FROM the hull catalog
   (``map_speed(spec) == find_ship(spec.ship_id).speed``) plus
   NAMED numeric pins (``militia_blockade`` 9, one per hull
   class) so an accidental hull-stat change trips a number, not
   just a tautology.

**Judgment call pinned:** ``list_npc_ships()`` ships in this phase
(data accessor for the test — in scope beside the resolver, same
module, same idiom).

## Acceptance criteria (draft)

- NPC world-speed is independent of the player's engine: the same
  patrol crosses the same system in the same number of DAYS at
  player speed 6 and 14.
- A space-wait advances every mover a full day of movement,
  fractions carried (ruling 4).
- The doc-41 watch schedule holds at any player speed after the
  lead retune (reliefs arrive ≈ shift end; dips last the flight,
  not the engine).
- Accumulators survive save/load; pre-sidequest saves load with
  zeroed accumulators and no other migration.
- Space still feels busy: no visible population drain or teleport
  popping at either engine extreme; per-step cost within the
  knowledge.md performance rules.

## Open questions

None — all eight ruled in the Settled section below (2026-09-10).
New questions surface at the phase briefs' pre-implementation
audits.
