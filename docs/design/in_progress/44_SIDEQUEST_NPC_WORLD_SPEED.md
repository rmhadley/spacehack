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

- [ ] Phase 1 — Hull-derived speeds: `base_speed` resolves from
      the spec's hull (derelicts pinned 0; explicit authoring
      wins), every spec resolves, tests
- [ ] Phase 2 — The accumulator kernel: per-squad credit at
      `npc_speed / player_speed` tiles per player step,
      deterministic sub-stepping with the Settled-4 clamp
      constraints (per-cell predicate, stop-≠-fire, argued at the
      14-cell bound), the patrol stepper and the watch flight
      stepper converge on one shared kernel, accumulator
      persistence MIRRORING the path-sync lifecycle (current-system
      patrol mids round-trip; watch keys default 0; pop at every
      target-pop site; sync logic in the kernel module — saveload
      takes no new logic)
- [ ] Phase 3 — The day-granular wait: a space-wait pays every
      mover a full day of movement with carry-over (ruling 4) —
      per-cell clamping REAPPLIES at the 14-cell wait bound
- [ ] Phase 4 — The watch retune: re-measure base→station
      transits at picket speed 9, retune the launch leads (data),
      regression sweep of the doc-41 phase-2 checklist
- [ ] Phase 5 — Playtest: same route at a slow and a fast ship —
      the world's speed reads constant; wait a day at the Line —
      reliefs visibly cover a day of ground; density + pursuit
      texture checks (settled consequence 7 + the speed-14 note)

  Implementation brief (1) — PROPOSED (`/refine-design 44`,
  2026-09-10; AMENDED same day per the ADVISE reviewer round):

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
