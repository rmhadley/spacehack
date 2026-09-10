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

Explicitly NOT yet ruled: whether JUMPS cost time (today they are
instant on the calendar). Open question 1.

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
  naming) → **save/load contract work** (persisted; existing saves
  default 0 — no migration needed beyond the default).
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
   challenge range between checks. At the ruled speed range the
   cap is ~2.3 cells/step (speed-14 NPC vs a speed-6 player), so
   the cost is tiny. Exact clamp mechanism (e.g. stop at the first
   cell that would trigger the proximity encounter) is the
   pre-implementation audit's to pin.
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

## Phases (build queue — `/implement-phase 44.<p>` works top-down)

- [ ] Phase 1 — Hull-derived speeds: `base_speed` resolves from
      the spec's hull (derelicts pinned 0; explicit authoring
      wins), every spec resolves, tests
- [ ] Phase 2 — The accumulator kernel: per-squad credit at
      `npc_speed / player_speed` tiles per player step,
      deterministic sub-stepping with per-cell checks, the patrol
      stepper and the watch flight stepper converge on one shared
      kernel, accumulator persistence + existing-save defaults
- [ ] Phase 3 — The day-granular wait: a space-wait pays every
      mover a full day of movement with carry-over (ruling 4)
- [ ] Phase 4 — The watch retune: re-measure base→station
      transits at picket speed 9, retune the launch leads (data),
      regression sweep of the doc-41 phase-2 checklist
- [ ] Phase 5 — Playtest: same route at a slow and a fast ship —
      the world's speed reads constant; wait a day at the Line —
      reliefs visibly cover a day of ground; density + pursuit
      texture checks (settled consequence 7 + the speed-14 note)

  Implementation brief (1) — PROPOSED (`/refine-design 44`,
  2026-09-10):

  - **Scope.** Data: `NpcShipSpec.base_speed` (``data/npc_ships/
    __init__.py``) becomes ``int | None = None`` — None resolves
    from the hull. Code: ONE pure resolver
    (``data/npc_ships/__init__.py`` — ``map_speed(spec) -> int``:
    explicit ``base_speed`` wins, else ``find_ship(spec.ship_id)
    .speed``, else a safe 1) — no call-site changes yet (the
    stepper still ignores it; phase 2 wires it). Derelicts keep
    their explicit 0 (``core.py`` already authors it — verify,
    don't touch). Tests: every registered spec resolves; the
    launch table holds (scout-hull NPCs 14, cruiser 9, frigate 8,
    merchant haulers 7 / freighters 6); derelicts resolve 0;
    an explicitly-authored override beats the hull default; the
    resolver is pure (no ctx, no RNG).
  - **Build order.** (1) the resolver + tests; (2) the field-type
    change + derelict verification; (3) data test pinning the
    launch table.
  - **Binding rulings.** Settled items 2 (hull derivation,
    explicit-wins, derelicts 0) and the speed-14 consequence note;
    data-first (a frozen dataclass field, no runtime attachment);
    NO stepper changes in this phase.
  - **Required tests.** The launch table per spec; override-wins;
    derelict-0; unknown-hull fallback (a spec whose ship_id is not
    in the ship catalog resolves to 1, never raises mid-game).
  - **Stop point.** NOTHING from phase 2 — no accumulators, no
    stepper changes, no wait changes, no watch retune; the 80%
    throttle still stands until phase 2 replaces it.
  - **Playtest checkpoint.** None — a pure data+resolver phase
    with no player-visible behavior change; the numbers first
    become observable in phase 2.

## Acceptance criteria (draft)

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
