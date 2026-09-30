# DESIGN: Ship fitting grid — one grid, one power budget

Status: DRAFT for review (2026-09-30). Nothing implemented. Successor to
`complete/DESIGN_SHIP_CUSTOMIZATION.md` (the slot system this replaces for
the player). Advisor ADVISE pass folded same day (12 issues: catches
1/3/4/5 + minors 6-11 amended in place; catch 2 and catch 12 ruled by
the user the same day — SETTLED 11/12).

## Overview

Replace the slot-based equipment model — two integer counts per hull
(`weapon_slots`, `module_slots`) — with a single fitting **grid** per hull
and a static **power budget**. Every weapon and module occupies grid cells
sized by its mark; modules that do work carry an inherent negative power
draw (upkeep) reusing the existing `power_gen_bonus` field; the ship's
resting power balance must be net non-negative to field the hardware.

The design goal is the one the user named: **defense vs power vs offense
fights itself** — for physical space on the grid and for watts in the
power budget — so that stacking two big shields, running three plasma
cannons, and keeping a reactor to feed them become mutually exclusive
choices instead of a forced dominant build.

## Evidence baseline (measured 2026-09-30, before any changes)

Source: the user's played character `saves/merchant_sirian_bountyhunter.json`
(Sirian Bounty Hunter, level 36, ~19 in-game months, 500 kills) and
`tools/balance_probe.py` run against it (10 seeded runs/row):

| Probe row | Win | Mean hull dmg | Turns |
|---|---|---|---|
| s_scout_b1 | 1.000 | 0.00 | 1.0 |
| s_raider_b2 | 1.000 | 0.00 | 1.4 |
| s_marauder_b3 | 1.000 | 0.00 | 1.8 |
| s_warlord_b4 (catalog ceiling) | 1.000 | 0.00 | 2.0 |
| s_2x_marauder (swarm) | 1.000 | 0.00 | 2.3 |

- Career space hull damage: **9** (counter `total_damage_taken`) vs 152
  ground damage over the same run. The hull gate is unreachable.
- The ship: Cruiser, 134 shields on 71 hull (+4/turn free regen, up to
  ~20/turn paid divert), 18 power gen. Two shield modules contributed 109
  max shields at **zero** power cost.
- Burst-fire asymmetry: the player's fire action is a volley — all active
  weapons for `max(AP)` once (`combat/_loop.py` `_handle_fire`) — while
  enemies pay per weapon (`combat/_ai.py` `_pay_fire_costs`) and fire one
  top-scoring weapon per action. Weapon *count* is the DPS lever.
- Quality scales damage AND accuracy (q3 plasma: ×1.45 damage, accuracy
  70→101, pinned at the 5-95 clamp's cap), so gunnery/dodge modules have
  nothing left to buy.
- User report: "EMP missiles are so underpowered they're not worth using.
  Missiles even with double ammo were useless compared to my plasma
  cannons. I had no need for storage, targetting, shield recharge, gyro
  stabalizer, modules. so many fun things we have in the game were just
  straight up pointless."

This doc covers the fitting system. Related queued work it does NOT cover:
enemy volley parity, the missile/EMP retune, and the shield/enemy-damage
magnitude retune (that lands with the grid, probe-driven — phase 4).

## Goals / non-goals

**Goals**
1. Physical size as a first-class constraint: a lucky Shield Mk. 4 cannot
   ride a starter hull ("early game shenanigans" — user).
2. One grid so weapons and modules compete for the same space.
3. Static power budget: modules cost watts to run, generators fund them,
   and the budget is enforced symmetrically on install AND removal.
4. Expressiveness: small-vs-big loadouts are real choices, not slot-count
   forced moves.

**Non-goals (v1)**
- Rotation. Fixed orientations; revisit if fitting feels starved.
- Runtime brown-outs (modules going dark mid-combat from pool drain).
  Held as a possible later phase only if the static gate lacks teeth.
- Missile/EMP rework, magnitude retunes, enemy volley parity — separate,
  after the grid exists ("we can deal with those numbers later though.
  Once we have a working grid system to test with." — user).
- NPC parity — player-only first, then a dedicated phase.

## Philosophy alignment

| Project convention | How this design aligns |
|---|---|
| Data-first | Sizes, upkeep, and hull grid dims are catalog data on frozen specs — zero runtime special-casing |
| Existing fields over new systems | Upkeep IS `power_gen_bonus` negative (Armor Plating precedent, already summed by `_calc_power_gen`); no new mechanic, a data pass + one gate rule |
| Table-driven | Fitting legality (geometry + power) is pure computation over catalog tables; UI never branches on item id |
| CP437/ASCII aesthetic | Grid renders as letter blocks (`S` 3×3 for a shield) — user's explicit picture |
| Save/load sacred | Placement is serialized; old saves get the cheap fallback (open question 1) |
| Gates beat playtests | Phase 1 ships a lint (sizes valid, mk-monotonic, start loadouts pack); the probe rides every later phase |
| Player-facing feature → guide review | The loadout/mechanic guide section is on every phase's playtest checklist |

## SETTLED (user rulings, 2026-09-30 — this conversation)

1. **ONE grid.** "one grid! So that defense vs power vs offense fights
   each other." Weapons and modules share the hull's grid; shields crowd
   out guns.
2. **No rotation in v1.** "I don't think we do in v1. I'm thinking of
   Hell Clock's grid system and I don't remember being able to rotate. We
   can always add rotation later if it feels needed."
3. **Static power gate, symmetric on removal.** "we can start with static
   gate. if we add a power gen the gate has to happen for removal too. so
   you can't remove a power generator if removing it would trip the gate."
4. **Module upkeep via inherent negative power.** "should we have some
   modules have an inherent negative power attached to them and they don't
   function if you have negative power" — motivated by "I stacked TWO
   powerful shield modules that felt wrong. 0 power hit, massive shields."
5. **mk scales size; quality never does.** "Quality does not change size.
   no. But mk1 - mk4 should. a mk4 module should require more space than
   a mk1."
6. **ASCII grid at the mechanic terminal.** "instead of slots on the
   right we have the grid system. I was picturing an ASCII system to keep
   the ASCII roguelike theme going. a 3x3 block of S for a sheild module.
   it's red if where you're placing it is illegal, green if it's legal.
   when on the right pane you can freely put down and pick up modules so
   you can rearrange."
7. **No save migration machinery.** "don't worry about existing saves.
   I'm still LARGELY the only player. Although I'm geting some interest
   and we may have to [worry] about them in a few weeks." — freedom is
   time-boxed; revisit before outside players depend on saves.
8. **Grid first; player-only first.** "This grid system first" (ahead of
   the enemy-volley parity fix), and "We can get it working for the player
   before we roll out parity with NPC ships."
9. **Missiles deferred.** Default racks stay; a future ammo-expander
   module is the likely shape ("I could see them keeping their default
   ammo but adding a new module that expands ammo"), but only after
   missiles are worth using vs plasma. Parked.
10. **Magnitude retune acknowledged** — "we may need to go through and
    rebalance numbers too" — owned by phase 4, probe-driven.
11. **Boundary normalization confirmed** (2026-09-30, ruling open
    question 8). User: "yes. I like that. bump things that can't be
    powered. and tinker used on an installed module refused if it
    bumps the gate." Power-invalid resting grids normalize by
    stripping the offenders to storage at load; a tinker kit applied
    to an installed module is refused when its quality bump would
    trip the gate. No dark state exists anywhere.
12. **Held item on pane switch** (2026-09-30, ruling open question 9).
    User: "if you have an item held when you tab to store pane, it
    should snap back to where it was or go to storage if it can't."
    The same auto-return applies at any commit boundary (leaving the
    terminal included); if snap-back is impossible and storage would
    trip the gate, the switch is refused — the gate outranks the
    auto-return (composition of SETTLED 3 + 12).

## The power gate (concrete rule — agent synthesis of SETTLED 3 + 6)

The gate is a check on the **resting state** of the grid:

- **Net power** = hull `base_power_gen` + Σ `power_gen_bonus` over all
  fitted items (upkeep is the negative summands). Computed pure, shown on
  the fitting screen (`POWER: +18 gen / -7 upkeep / +11 net` — ASCII
  hyphen in the actual readout, advisor catch 9).
- **Held-in-hand counts as fitted.** Picking an item up inside the grid
  pane does NOT un-power it — free rearrangement (SETTLED 6) never trips
  the gate mid-edit.
- **Commit operations are gated**: placing an item from the store/storage
  pane into the grid, and storing/selling a fitted item (including the
  case SETTLED 3 names: removing a generator whose removal would send the
  resting grid negative). Illegal placements render red like geometric
  collisions.
- **Switching panes or leaving the terminal while holding an item
  auto-returns it** (SETTLED 12): snap back to where it was, or into
  storage if it can't; if storage would trip the gate, the switch
  itself is refused.
- **Weapons draw no upkeep.** Guns cost power per shot (existing economy);
  defenses and systems cost watts to run. Doctrine sentence: *guns cost
  power when fired, modules cost power to exist.*
- **"Don't function if negative" is RULED as: it never happens
  (SETTLED 11).** ADVISOR CATCH 2 (blocking): the dark state IS
  reachable in normal play — tinker kits bump installed-module quality
  (`tinker.py:234-249`), and quality scales `power_gen_bonus` in
  magnitude, so a legal resting grid can go negative with no commit
  ever firing; a phase-4 upkeep retune would likewise make well-formed
  saves power-invalid on load. A live "contributes nothing" rule would
  also be a new mechanic across ~8 bonus-sum sites
  (`_module_bonus_sum`, `_effective_installed`, `hull_cur_max`,
  `effective_speed`, `effective_max_cargo`, `smuggler_hold_capacity`,
  `_skill_bonuses`), contradicting the philosophy table's
  no-new-mechanics claim. RULED: invalid resting states are NORMALIZED
  at the boundaries — power-invalid grids strip their offending items
  to storage at load (reusing the open-question-1 machinery), and the
  tinker apply refuses a quality bump that would trip the gate — so
  every fitted module always contributes, and no dark state exists
  anywhere. (Cargo-hold brownouts with cargo aboard are the other
  reason the gate is commit-time rather than live.)
- Quality/randarts scale upkeep in magnitude (existing negative-field
  scaling): legendaries are bigger AND hungrier. The user's "Late
  Meridian" randart (power_gen −2 axis) is the pattern.

## Data model

- `Ship` (catalog) gains `grid_w`, `grid_h`. `weapon_slots` /
  `module_slots` REMAIN during the player-only phases — the NPC lint
  (`tests/test_space_scale.py::test_every_loadout_fits_its_hull_slots`)
  still reads them; they retire at the NPC-parity phase.
- `WeaponSpec` / `ModuleSpec` gain `grid_w`, `grid_h` (ints ≥ 1; no
  rotation). Catalog-fixed like price and slot_type: never quality-scaled.
- `ModuleSpec.power_gen_bonus` gains authored negatives across module
  families (Armor Plating already models this exactly).
- `OwnedShip`: installed items carry grid coordinates. The
  weapons-vs-modules distinction stays as item kind (firing iterates
  weapons; bonus sums iterate modules) with reader helpers preserving
  existing consumer seams. The deciding input for the exact shape
  (advisor catch 4, blocking): `weapon_ammo` keys magazines by
  weapons-tuple index (`ship.py:331`), re-indexed on removal and
  re-read by combat (`_player_weapon_ammo`) — **per-entry placement**
  (x/y on the entry, tuple order preserved) keeps that coupling for
  free, while a parallel index-keyed placement field breaks it on every
  reorder. Settled at brief time against the reader census, with that
  coupling as the tiebreaker.
- Save: placements serialize (x, y beside the StoredEquipment payload).
  Storage (`ctx.ship_storage`) is unchanged — stored items have no
  position.

## Draft tables (phase 1 starting point — "good starting point", user)

Hull grids:

| Hull | Grid | Cells | Old slots (w/m) |
|---|---|---|---|
| Skiff | 3×3 | 9 | 2/1 |
| Scout | 4×3 | 12 | 4/2 |
| Hauler | 4×4 | 16 | 2/2 |
| Cruiser | 5×4 | 20 | 6/4 |
| Frigate | 6×5 | 30 | 8/6 |
| Freighter | 6×5 | 30 | 3/4 |

Item sizes (mk scales; anchors from the user-approved sketch):

| Size | Items (draft) |
|---|---|
| 1×1 | light laser, targeting computer, gyro stabilizer, armor plating mk1 |
| 1×2 | medium laser, light/heavy/EMP missile racks, shield capacitor, shield recharger, compact reactor, targeting/gyro mk2, smuggler hold mk1 |
| 2×2 | heavy laser, shield mk1/mk2, cargo mk1, armor mk2-4, targeting/gyro mk3-4, reactor mk2, smuggler mk2 |
| 2×3 | plasma cannon, shield mk3, reactor mk3, cargo mk2, smuggler mk3 |
| 3×3 | shield mk4, reactor mk4, heavy reactor, cargo mk3/mk4, smuggler mk4 |

Upkeep draft (armor's existing −1..−4 curve as the pattern; magnitudes
tuned in phase 4): shields −1/−2/−3/−4 by mk; shield capacitor −1 and
shield recharger −1 (advisor catch 7 — every family gets a row before
authoring); targeting/gyro −1 flat; reactors positive (existing
values); cargo/smuggler holds 0 (structural). Authoring lands in
phase 2, not phase 1 (see phases).

Worked check (the motivating cases):
- Skiff 3×3 + Shield Mk. 4 (3×3): fits nowhere for anything else — and
  the Skiff's gen 3 can't fund −4 anyway. The luck-spike is dead.
- Skiff + Shield Mk. 3 (2×3): two-thirds of the grid, room for one light
  weapon.
- Cruiser 20 cells: two Shield Mk. 3 (12) + Reactor Mk. 4 (9) = 21 — the
  user's exact degenerate stack is geometrically impossible.

## Domain changes

- **Mechanic loadout modal** (`menus/_loadout.py`): right pane becomes
  the grid editor (SETTLED 6); left pane (STORE/STORAGE) keeps its shape.
  A new UI archetype — place/pick-up/collide, keyboard-driven, letter
  blocks colored by tier, red/green legality including power-illegal
  placements, net-power readout in the footer.
- **Reader surfaces**: HUD ship block, ship-buy ledger, hangar menu —
  "Wpn 4/6 Mod 3/4" becomes cells used/total + net power.
- **Purchase flow**: buy-then-install needs a placement (auto-place
  prompt or hand-off to the grid pane). Auto-place failures keep the
  existing validate-before-charge ordering (`_loadout.py:567-591`) —
  the player is never charged for a part that found no cell (advisor
  catch 12's second half, folded as a requirement rather than a
  question).
- **start_weapons/start_modules**: deterministic auto-fit at new-game
  setup and ship purchase.
- **Combat math**: unchanged seams (`_calc_power_gen` already sums the
  field; module bonus sums already iterate modules). Net generation
  feeding the pool emerges for free.
- **NPC side**: untouched until the parity phase. Specs stay flat tuples;
  the existing slot lint keeps passing (fields retained).

## Phases

- [ ] **1. Catalog data pass (geometry only)** — grid dims on the 6
  hulls, sizes on all weapons + modules; the size table above as the
  starting point; lints: every item sized (covering — or explicitly
  exempting — the auto-registered `breach_charge_test` fixture weapon,
  advisor catch 5f), mk-monotonic sizes per family, every hull's start
  loadout packs, hull grids within render budget. **Upkeep data does
  NOT land here** (advisor catch 1, blocking): `_calc_power_gen`
  (`combat/_stats.py:87-92`) feeds `_build_enemy`, and NPC specs fly
  exactly the families the upkeep table prices (`shield_mk1`,
  `shield_capacitor`, `targeting_computer`, `shield_recharger` —
  quality-rolled via `roll_flown_equipment`), so authoring negatives
  now would change enemy power pools and stale the recorded probe
  baseline while this phase claims no behavior change. Sizes alone
  change nothing — nothing reads them yet.
  PLAYTEST: a rendered fixture of each hull grid with its start loadout
  placed — open each fixture and eyeball the shapes (the concrete user
  step, per the advisor's conformance note).
- [ ] **2. Fitting model + gate + upkeep data** — upkeep authors WITH
  the gate, so the first power change is already guarded (companion to
  advisor catch 1); `OwnedShip` placements; the resting gate
  (install/store/sell symmetric, held-in-hand semantics); auto-fit for
  EVERY install path — new-game starts (`game_loop.py:818`), purchases
  (`game_flow.py:675-676`), and BOTH modal install paths (`_loadout.py`
  buy-install and storage-install; the modal stays slot-shaped until
  phase 3, so interim installs auto-place — advisor catch 3, blocking);
  save shape. Lints and tests added here (advisor catches 4/6/8/10):
  start-loadout power validity (net ≥ 0 per hull at base quality —
  RE-RUN after every phase-4 retune), the pinned numbers behind AC1
  (the cheapest 3×3 shield's upkeep exceeds the starter hull's base
  generation), and the pure-function test set the contract requires
  same-commit: geometry packing, net-power, auto-fit, and
  ammo-coupling reorder (magazines stay keyed to their weapon across
  placement changes). Probe regression green — the recorded baseline
  is the referee.
  PLAYTEST: dev-mode build ledger — fit/stress the gate rules on a
  live ship (including the tinker refusal, SETTLED 11); save/quit/
  continue round-trip of a fitted grid.
- [ ] **3. Fitting UI** — the grid editor pane at the mechanic terminal,
  letter blocks + tier colors + red/green legality, hand model, pane
  switching; HUD/ship-buy/hangar surfaces to cells + net power; guide
  review of the mechanic/loadout sections. Budget note (advisor catch
  11): the grid editor is a new UI archetype — by cohesion it likely
  lives in a sibling module beside `menus/_loadout.py` (695 lines
  today); the phase-3 brief carries the split forecast (placement
  stays cohesion-driven — a forecast, not a placement driver).
  PLAYTEST: fit the motivating cases by hand (Skiff + mk4 shield
  refused; cruiser two-mk3+reactor refused; rearrange freely; remove
  funding reactor refused), plus the full save/load sniff test.
- [ ] **4. Calibration** — probe-driven tuning of upkeep magnitudes and
  power pressure; re-runs the phase-2 power lints after every
  magnitude change (advisor catch 8); the deferred magnitude questions
  (shield bonus vs enemy damage) land here or get their own doc with
  the probe as referee.
  PLAYTEST: the user's next space fight feels dangerous in the intended
  bands; probe rows show real mean hull damage.
- [ ] **5. NPC parity** — NPC loadouts adopt sizes: the flat-tuple lint
  becomes packability + power validity; `weapon_slots`/`module_slots`
  retire. (Ordering vs the enemy-volley parity fix: open question 7.)

Each phase gets an Implementation brief at `/refine-design` time before
any build. Every phase close amends the SYSTEMS.md entries it touched
in the same commit ("Ship ops", "Space combat init — parity mirror",
and "Spec-sheet buy modal" are all in scope by phase 3 — advisor
catch 11).

## Acceptance criteria

1. A fresh Skiff cannot field a Shield Mk. 4 by any path (buy, loot,
   store-install) — pinned by a phase-2 lint so the refusal survives
   phase-4 retunes (advisor catch 6).
2. The cruiser double-shield + capital-reactor stack does not fit.
3. Net power is visible on the fitting screen and enforced on install
   AND removal; removing the last reactor funding a shield is refused.
4. In-pane rearrangement never trips the gate; only commits do.
5. Phase-1 lints permanent in the suite; probe rows tracked from phase 2
   onward with the pre-change baseline recorded above.
6. Guide entries for the changed mechanic reviewed at every phase close.
7. NPC specs are untouched through phase 4 (parity is phase 5). The one
   NPC-side effect before then: upkeep authoring (phase 2) lowers enemy
   power generation for specs flying upkept modules — accepted,
   probe-refereed, and strictly in the player's favor direction
   (advisor catch 1's resolution).
8. A tinker kit that would push the resting grid power-negative is
   refused; a power-invalid grid arriving through load normalizes by
   stripping offenders to storage; a held item auto-returns on pane
   switch or terminal exit (SETTLED 11/12).

## Open questions (for /refine-design)

1. **Old-save fallback**: hard break vs strip-on-load. Lean: a
   ~10-line strip-on-load reusing `move_installed_equipment_to_storage`
   so dev saves stay loadable during the build; zero further machinery.
2. **Glyph letters + empty cell**: proposal S/R/T/G/C/A/H families,
   L/M/P/E weapons, `.` empty. Needs the user's eye on a render.
3. **Frigate identity**: 30 cells cannot hold eight 2×2+ guns — is
   "overwhelming firepower" many-small or few-big? May resize the grid
   (6×6/7×5) or accept the new shape.
4. **Upkeep magnitudes** beyond the draft curve (tied to phase 4).
5. **HUD readout shape** (cells + net power wording).
6. **Placement data shape** (brief-time, after the reader census).
7. **Enemy-volley parity slotting** — before phase 5, after phase 4, or
   its own fix doc whenever (it is independent of the grid).

## Pre-implementation audit

REQUIRED before phase 1 builds (per knowledge.md). The census, with
anchors — the advisor pass (catch 5, blocking) names what it MUST
cover beyond the obvious:

- The save twin pair: writer `_d(ctx.player_owned_ship)`
  (`saveload.py:197`) AND parsers `_parse_owned_ship`
  (`saveload_ship.py:21-59`) and `_stored_equipment_from_dict`
  (`saveload.py:86+`) — including the recorded decision on whether
  placement rides `StoredEquipment` (storage payloads would gain x/y
  keys the parser silently drops; benign, but decide it).
- The tinker kit seam (`tinker.py:234-249`): kit target selection and
  `dataclasses.replace` must preserve placement (and refuses
  gate-tripping quality bumps, SETTLED 11).
- The tombstone GEAR dump (`tombstone.py:281-287`) — iterates
  `owned.weapons/.modules`; must survive placement-carrying entries.
- The enemy parity seam (`space_scale.roll_flown_equipment`,
  `combat/_stats._build_enemy`) — where upkeep's power impact lands
  and how the phase-5 lint replaces the slot lint.
- The auto-fit stamping sites: new game (`game_loop.py:818`) and
  purchase (`game_flow.py:675-676`).
- The `breach_charge_test` fixture weapon (`data/weapons/breach.py`,
  auto-registered) — size-lint coverage or explicit exemption.
- `debug_session.py` / `tools/save_debug.py` behavior under
  strip-on-load.
- Three duplication hotspots (the audit template's requirement):
  gate-legality logic vs `_loadout.py`'s slot arithmetic and
  `_log_storage_failure` vocabulary; geometry packing vs any
  auto-fit reimplementation; the grid pane vs the existing
  `pygame_split` row model.

Filled with live-code verification at refine time, before the phase-1
brief is approved.
