# SIDEQUEST: NPC World Speed — the world moves on its own clock

**Status: DESIGN DUMP — ruled direction, unrefined. Do not implement
until `/refine-design 44` settles the open questions.** Inserted as a
sidequest between doc 41 phase 2 (implementation LANDED; playtest
PARKED behind this doc) and phase 3. Companion: `41_DESIGN_THE_LINE.md`
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
  triggers must fire per cell).
- The 80% throttle's fate is an open question (it was organic
  jitter; accumulators make motion near-deterministic).

### What this changes under the hood

- **Data**: `NpcShipSpec` gains (or repurposes — open question 2) a
  map-speed stat with sane per-spec defaults (merchants,
  patrols/pirates per weight class, watch pickets). Data-first: one
  field per spec, retunable.
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

## Phases (build queue — UNREFINED, refine before building)

- [ ] Data: the NPC map-speed stat + per-spec defaults + tests
- [ ] The accumulator kernel: shared by patrols and watch flights;
      per-player-step credit; cell-by-cell sub-stepping; tests
- [ ] Save/load: accumulator persistence + existing-save defaults;
      round-trip tests
- [ ] The wait: a space-wait pays every mover a full day of
      movement with carry-over; tests
- [ ] The watch retune: re-measure transits under own-speed
      movement, retune leads (data), regression sweep of the doc-41
      phase-2 checklist items
- [ ] Playtest: fly the same route at a slow and a fast ship — the
      world's speed reads constant; wait a day at the Line —
      reliefs visibly cover a day of ground

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

## Open questions (for `/refine-design 44`)

1. **Do jumps cost time?** Unruled. Today: instant. If yes — how
   many days per hop, and what does that do to quest deadlines and
   the watch (a jump that eats 3 days skips watch due-days — the
   day-skip heal exists but is dev-coarse)?
2. **Stat field**: repurpose `base_speed` (already on every spec,
   currently only a stationary gate) or add `map_speed`? Repurposing
   is one migration of meaning; a new field is additive.
3. **The 80% throttle**: keep as jitter (accumulator pays 1 tile,
   RNG decides presentation) or drop it for deterministic motion?
   Deterministic motion changes the dark-run/lure texture at the
   Line.
4. **Multi-tile steps vs. triggers**: when a fast NPC crosses the
   player's detect radius mid-sub-step, does the encounter check
   fire mid-step (per cell — recommended) or only at rest?
5. **Squad vs per-entity accumulators**: today squads move as
   leader+cohesion; one accumulator per squad (leader-driven)
   preserves that; per-entity lets stragglers catch up at their own
   speed. Which fiction?
6. **Scope**: city NPCs and ground hunters out (own tickers, no
   calendar)? Assumed yes.
7. **Merchant timing**: merchant spawn→A*→despawn loops and the
   "transit days depend on the player's ship speed" slop — under
   own-speed merchants, does the ambient-traffic density need
   retuning (they'll cross systems in fixed days now)?
8. **Watch interlock**: does this sidequest land before the parked
   41.2 playtest (retuned leads) — assumed YES, that is why the
   playtest is parked — or does 41.2 playtest first on the old
   math and the retune becomes its own re-playtest?
