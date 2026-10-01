# DESIGN: Missile flight — interceptible long-range artillery

Status: DRAFT for review (2026-10-01). Nothing implemented. Born in
the doc-56 phase-4 parts walk (SETTLED 35's coda): the walk held
missile magnitudes for the probe, and this rework — proposed by the
user the same day — supersedes those magnitudes when it lands. Doc
56's calibration pass proceeds meanwhile on the non-missile dials.

## Overview

Missiles stop being instant damage numbers and become **physical
projectiles in flight**: strictly long-range (worse minimums than
today), roughly doubled damage, and — the heart of it — **while a
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
  (contrails/inbound markers, motion not prose).
- **One mercy already banked**: combat never saves mid-fight (doc 56
  phase-5 record), so in-flight missiles are transient state — no
  save/load work.

## Evidence baseline (current launchers, 2026-10-01)

| | Size | Price | Dmg | Acc | Range | AP | Pow | Mag | Restock |
|---|---|---|---|---|---|---|---|---|---|
| light_missile | 1×2 | 40cr | 14 | 72% | 2–9 | 2 | 0 | 4 (+mag) | 8cr/rd |
| heavy_missile | 1×2 | 90cr | 32 | 72% | 3–13 | 2 | 0 | 3 (+mag) | 20cr/rd |
| emp_missile | 1×2 | 120cr | 0 (100% strip) | 75% | 2–10 | 2 | 0 | **2, hard-capped** (SETTLED 35) | 25cr/rd |

Post-volley doctrine (doc 56): the first 2-AP weapon sets the volley
cadence; missiles pair with plasma (both 2 AP), never with pure
laser walls. Damage racks receive the magazine bonus; EMP never
does.

## Philosophy alignment

| Project convention | How this design aligns |
|---|---|
| Data-first | Flight stats (speed, HP, intercept difficulty) are catalog fields on WeaponSpec, not per-site constants |
| Existing fields over new systems | In-flight missiles reuse the Entity/world model and the existing target cycle; interception reuses hit-chance math |
| Table-driven | Flak decisions (AI target priority: inbound vs shooter) resolve through a scorer, not bespoke branches |
| Wordless visual communication | Flight is animated travel; no popup prose |
| Save/load sacred | In-flight state is combat-transient — nothing serializes |
| Enemies should have a counter (user doctrine) | Missiles counter standoff; flak counters missiles; saturation counters flak |

## Data model (draft)

- `WeaponSpec` gains flight fields for `slot_type="missile"`:
  `flight_speed` (cells per tick), `missile_hp` (intercept
  difficulty), authored per launcher (heavies: slower, fatter —
  easier to hit, harder to kill; lights: fast, thin).
- In-flight missiles are **combat entities**: position, vector to
  impact, owning side, launcher spec + quality (arrival damage rides
  the shooter's rolled tier, doc 48.7). They join
  `game_map.entities` for rendering and the target cycle — NOT the
  enemy_insts roster (no AI turn of their own; movement is
  deterministic per tick).
- Arrival resolution at impact: the existing `resolve_damage` path,
  unchanged.

## Domain changes (draft)

- **Fire**: a volley member with `slot_type="missile"` spawns a
  projectile instead of resolving instantly; ammo pays at launch
  (unchanged).
- **Targeting**: the TAB cycle includes hostile in-flight missiles
  (nearest-first?). Firing at a missile uses normal hit chances and
  weapon costs.
- **Auto-flak (open)**: light lasers may auto-engage inbound when
  their volley's primary target is dead/unreachable — the
  build-expression option beside manual targeting.
- **Enemy AI**: a flak decision layer — score(inbound missile) vs
  score(shooter) per available action; enemies with fast cheap
  weapons prefer flak. Enemy missiles are equally interceptible by
  the player.
- **Back-off dance**: worse minimums make the existing back-off AI
  (doc 48 SETTLED 40) mandatory missile behavior; rushdown inside
  the floor is the counter-play.
- **Animation**: per-tick projectile travel along the vector;
  intercept = a small explosion at the missile's cell.

## Phases (draft — refined at /refine-design)

- [ ] 1. Flight entities + arrival resolution (player-fired only;
      interceptible via manual targeting; no AI changes)
- [ ] 2. Enemy missiles + the flak AI layer (both sides fly them)
- [ ] 3. Auto-flak stance + magazine saturation balance (probe
      re-derived; doubled damage calibrated against intercept rates)
- [ ] 4. Calibration (probe-refereed; owns the ×2 magnitudes, the
      new minimums, missile_hp/speed tuning)

## Acceptance criteria (draft)

1. A missile fired at range resolves at impact, not at launch; both
   sides' missiles are interceptible by the same mechanics.
2. light_laser-heavy builds demonstrably suppress missile volleys
   (probe row: a flak escort reduces inbound arrival rate).
3. The magazine's depth measurably trades against flak (saturation
   is a real strategy, not a paper one).
4. EMP behavior matches its ruling (see OQ2) — deliberately.
5. Combat pacing preserved: fights read slower-but-dreadful, not
   fiddly (playtest ruling).

## Open questions (for /refine-design)

1. **Flight model**: one-action delay (arrives at the shooter's next
   action start — exactly one intercept window) vs multi-tick travel
   across the map. Simplest viable is the former; the glyph-crossing
   fantasy wants the latter.
2. **EMP: pulse or projectile?** Lean: instant pulse, never
   interceptible — the key is already counter-balanced by its
   hard-capped magazine; making it shootable makes boss fights
   RNG-shaped. Against: a juggernaut with flak killing your key is
   very DCSS. User ruling needed.
3. **Interception economy**: does firing at a missile cost the full
   volley action (max-AP once, shared with shooter-targeting) or a
   separate reaction? Doc 54's reaction volley is the natural seam.
4. **Auto-flak rules**: when do idle light lasers engage inbound
   without the player asking? Never (manual only) / when no live
   shooter target / a toggleable stance?
5. **New minimums**: light 2→4, heavy 3→5 (riff's opening numbers)?
   What closes inside the floor is immune to racks — the rushdown
   counter-play — so the floors are a balance surface, not a detail.
6. **Intercept difficulty**: missile_hp per launcher family; do
   strip/pulse weapons affect missiles? (Lean: damage weapons only.)
7. **Doubled damage timing**: land with phase 1 (feel the gamble
   immediately) or hold until phase 4 (calibrate against measured
   intercept rates)? Lean: land ×2 at phase 1, calibrate at 4.
8. **Doc 56 seam**: which SETTLED-35 interactions move (magazine
   bonus on doubled racks, the BH ×2, cargo-per-round booking when
   magazines deepen) — re-derive the capacity sites at phase 1.

## PLAYTEST (per phase, detailed at refine)

- Phase 1: fire a heavy at a distant target; watch it travel; shoot
  it down with light lasers; eat one unanswered and feel the ×2.
