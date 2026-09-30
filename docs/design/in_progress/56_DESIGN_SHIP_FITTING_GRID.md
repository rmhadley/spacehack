# DESIGN: Ship fitting grid — one grid, one power budget

Status: DRAFT for review (2026-09-30). Nothing implemented. Successor to
`complete/DESIGN_SHIP_CUSTOMIZATION.md` (the slot system this replaces for
the player). Advisor ADVISE pass folded same day (12 issues: catches
1/3/4/5 + minors 6-11 amended in place; catch 2 and catch 12 ruled by
the user the same day — SETTLED 11/12). Refine pass same day: open
questions 1 and 3 settled (SETTLED 13/14), the pre-implementation
audit live-verified, phase-1 Implementation brief proposed.
Phase 1 BUILT same day (`/implement-phase 56.1`): brief ADVISE-folded
(2 blocking + 7 minor, all dispositioned below), gate green 3308,
commits de06db72/dd33ce26/a96b88cc/1c3b7c18. PLAYTEST PASSED
2026-09-30 ("playtest is good"; glyph letters ruled in the same
exchange — SETTLED 15; open questions renumbered, 4 remain).
Phase-2 refine pass same day (second `/refine-design` session):
placement shape RESOLVED at brief time per the pre-committed census
procedure (open question 3 — see Data model), the reader census and
every hook point re-verified live, the dev-mode grant exposed as a
fifth stamping site that cannot pack (audit addendum), phase-2
Implementation brief proposed below, ADVISE-folded in the same
session (verdict ADVICE, 3 blocking + 5 minors — all dispositioned
  inside the brief; the `_d` Position-branch collision and the
  unpackable dev grant were the blockers). Brief APPROVED the same
  exchange ("approved. we can always adjust later after
  playtesting" — the refusal strings, guide sentence, and dev-grant
  mix are expected to move at the playtest). Phase 2 BUILT same day
  (`/implement-phase 56.2`, gate 3335, nine commits; the goal-1
  collision and its measured re-fund recorded inside the phase-2
  entry — the AC1-mechanism ruling and the re-fit power feel are the
  playtest's first items). **Phase-2 playtest DEFERRED to the
  phase-3 checkpoint by user ruling 2026-09-30**: "got it. I'll wait
  for the UI so I don't have to do this invisibly. no reason to
  check it before the ui is there" — auto-placement is invisible in
  the slot-shaped interim modal, so both phases playtest together
  once the grid editor exists; the open power rulings and the
  SYSTEMS.md close obligations (Ship ops + parity mirror) ride the
  same combined checkpoint. Phase-3 refine pass same day (second
  command session): SETTLED 16-19 (cursor + pick/place editor,
  hand-off installs, slot-summary retirement verbatim, hangar read-only
  grid — open question 2 retired by the user's ruling), phase-3
  Implementation brief proposed + ADVISE-folded in the same session
  (verdict ADVICE, 5 blocking + 7 minor — the slot-guard
  part-destruction path, the under-counted split key surface, and the
hand-off pre-check contradiction were the blockers; all folded,
dispositions inside the brief). Brief APPROVED by the build
invocation (`/implement-phase 56.3`, 2026-09-30). Phase 3 BUILT same
day: gate green **3368** (+1 ruff fix), commits 8fe159df (editor
state machine + letters) / 578fdb48 (split GRID: key surface) /
c47e206d (loadout modal rewrite + slot-guard retirement, ONE commit
per brief blocking 1) / 8d3f00d0 (HUD + ledger retirement) /
6f1aa181 (hangar + mechanic grids, AMMO reword) / 0108a95b (guide) /
1ad2c81a (review minors). REVIEW pass: REQUEST_CHANGES → 1 blocking
(the doc's own landing record, deliberately queued behind the review)
+ 5 minors — 3/5/6 folded in 1ad2c81a; minor 2 (the brief's
gate-refused-switch "leg") RESOLVED BY CONSTRUCTION: with single-hold
+ vacated origins + never-fitted storage neutrality there is no
branch a gate check could even occupy — the by-construction
neutrality is pinned (`test_never_fitted_storage_neutrality`) instead
of a fabricated-state test against a predicate that cannot fire
(RULING PENDING at the playtest: add a dead defensive leg anyway, or
keep the by-construction record); minor 4 (unknown installed ids
render nothing on the grids) is fabricated-state-only — the save
parsers reject unknown ids before load normalization ever runs (and
`normalize_fitted_grid`'s label pass raising on fabricated unknowns
is pre-existing phase-2 shape, unreachable from real saves). The two
NEW refusal strings ("You are already holding a part.", "Bought
{name} for {price}$.") land unapproved-prose-for-review at the
checkpoint per the phase-2 strings precedent. **The merged phase-2 +
phase-3 PLAYTEST PASSED 2026-09-30** — user: "we'll go through a
balance pass once we finish this whole migration. right now the
system is looking very good and will give us so many new 'builds' to
try. playtest passes". Checkpoint rulings folded: the phase-2
gen-4-vs-gen-3+upkeep-0 question DEFERS to the balance pass (phase 4,
now explicitly ordered AFTER the whole migration per the quote — it
also weighs on open question 2's ordering); the new strings ("You are
already holding a part.", "Bought ...", "Nothing installed.",
Dmg/Acc/Rng/AP/Pow labels) passed with no wording objections; the
gate-refused-switch disposition stands by-construction (raised, no
objection). Seven in-play fixes landed during the playtest (see the
fixes list above; SETTLED 20/21 among them). SYSTEMS.md closed in the
same commit ("Ship ops", "Space combat init — parity mirror",
"Spec-sheet buy modal"). Next: phase 5 (NPC parity) or phase 4
(calibration) — ordering is open question 2, and the user's quote
leans parity-first; brief via /refine-design 56.
PLAYTEST FIXES (in-play, user-reported, 2026-09-30): (1) cursor
brackets now WRAP the glyph — every glyph centers in its 3-char cell
(` S `/`[S]`), so the bracket no longer shifts the letter one column
(856e98a8, alignment pinned); (2) empty-handed hover highlights the
WHOLE piece in accent, mirroring the ghost's whole-footprint
green/red — hover reads the piece, not the cell (c015de1a); (3) the
pane-bottom tooltip: the pinned-detail zone only reads row 0, so the
FITTING GRID divider gave way to the letter grid and the
hovered/held readout rides row 0 — tiered name + the effective stat
line at the instance's tier, stats not prose (c8fe3425; this also
fixed the tooltip never showing — the row-0 detail had been sitting
on the first LETTER row where the pane never reads it); (4) WEAPON
stat lines are terse and carry the firing costs (66de9c17):
'Dmg 6  Acc 72%  Rng 1-5  AP 1  Pow 1' for energy/plasma, missiles
'Dmg 14  Acc 72%  Rng 2-9  AP 2  Ammo 4/4' (no Pow — racks pay ammo,
not watts); one formatter serves tooltip + market + storage rows.; (5) SETTLED 20 — the hangar LOADOUT
tab becomes the list view (52d4e022); (6) the hangar tab gains an
OVERVIEW block — Hull cur/max, Shields + free shield regen, AP
per-turn (incl. the fraction, e.g. 3.5), Max power (pool cap incl.
trait bonuses), Power regen (clamped per-turn generation) — read
through ``_player_combat_values`` so it can never drift from combat
(181175db; the tab pages when a full rack outgrows one screen, keeping
the shared font rung).; (7) SETTLED 21 — the mechanic
LOADOUT tab matches the hangar via the shared ``loadout_readout``
builder; the static letter grid retired from every read surface (it
renders only in the editor; ``read_only_rows`` dead and gone)
(b726d33e).

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
| Save/load sacred | Placement is serialized; old saves strip fitted gear to storage on load (SETTLED 14) |
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
13. **Frigate stays 6×5** (2026-09-30, ruling open question 3). User
    picked the recommended shape: "overwhelming firepower" on 30 cells
    means many-medium volleys or few-big-plus-support — eight 2×2+
    heavies never all fit, which is the defense-vs-offense fight
    working as designed.
14. **Strip-on-load for old saves** (2026-09-30, ruling open question
    1). A save whose installed gear carries no placements loads with
    that gear moved to storage (reusing
    `move_installed_equipment_to_storage`), ready to re-fit. This is
    also the machinery SETTLED 11's power-invalid normalization uses.
15. **Glyph letters ruled** (2026-09-30, at the phase-1 playtest). User:
    "yes the letters are good too" — the fixture render's proposal
    stands: module families S (shields incl. capacitor/recharger) /
    R (reactors) / T (targeting) / G (gyro) / C (cargo) / A (armor) /
    H (smuggler holds), weapons L (lasers) / M (missiles) / E (EMP) /
    P (plasma), `.` empty. Tier colours and red/green legality remain
    phase-3 UI scope; the breach prototype's `B` is a render-tool-only
    assignment (no fixture carries it — its game glyph, if it ever
    needs one, is phase 3's).
16. **Cursor + pick/place editor** (2026-09-30, phase-3 refine —
    SETTLED 6 made concrete). User picked the recommended shape:
    arrows move a cursor over the grid; ENTER picks up the item under
    it and it follows the cursor as a ghost (green where legal, red
    where not); ENTER again drops it; while holding, D stores the
    held item and X sells it; ESC returns it to where it was.
17. **Installs hand off into the editor** (2026-09-30, phase-3
    refine — the doc's "auto-place prompt or hand-off" resolved).
    User picked hand-off: Install (buy or storage) drops the part
    straight into the editor's hand on the grid pane — you place it
    yourself; no auto-place anywhere in the modal; the gate refuses
    bad drops in place (the red ghost is the refusal). New ships
    still arrive auto-fitted outside the modal (unchanged).
18. **Slot-count summaries retire** (2026-09-30, phase-3 refine —
    open question 2 settled by user, verbatim): "This UI element
    added nothing useful to the user. I think we can drop these
    little summaries. the Weapons 2/2 and Modules 4/4 especially
    were pretty useless to the player." The Wpn/Mod slot-count
    readouts RETIRE from every reader surface rather than converting
    to cells: the HUD ship-block line keeps only Spd; the loadout
    footer becomes the ruled POWER line; the ship-buy ledger drops
    its Weapon slots / Module slots rows. Power detail lives on the
    fitting screen.
19. **Hangar LOADOUT tab = read-only letter grid** (2026-09-30,
    phase-3 refine). The hangar's LOADOUT tab renders the same
    letter grid as the mechanic's editor, no interaction — the
    layout is visible away from the mechanic.
20. **Hangar LOADOUT tab = the list view** (2026-09-30, in-play —
    AMENDS 19). User: "Now, when I view my loadout from my hangar
    menu, instead of showing the grid with all the letters, how about
    a list of active weapons and modules with their stats attached?"
    The hangar tab lists active weapons and modules — tier-coloured
    names, the same stat lines the editor's tooltip shows. 19's
    letter grid lives on at the mechanic's tab and editor.
21. **Mechanic LOADOUT tab matches the hangar** (2026-09-30, in-play
    — completes 20's amendment of 19). User, asked whether the
    mechanic tab should match or keep its static grid: "yeah, match
    it!" Both LOADOUT tabs share one readout — the OVERVIEW numbers,
    then the active weapons/modules with stats — with the mechanic's
    Manage row kept on top as the editor entry. The letter grid
    renders ONLY in the editor; read_only_rows retired.

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
  to storage at load (the SETTLED 14 strip-on-load path), and the
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
  **RESOLVED 2026-09-30 (phase-2 brief time, per the pre-committed
  procedure)**: per-entry placement, concretely as optional fields
  `grid_x: int | None = None` / `grid_y: int | None = None` on
  `StoredEquipment` itself (stored entries leave them None). Census
  re-verified live this session:
  removal re-indexing at `ship.py:520-527` touches only `weapon_ammo`
  (a parallel placement map would need the same pass duplicated);
  tinker `_tuple_field_apply` (`tinker.py:130-146`) rebuilds the tuple
  replacing one entry, preserving siblings — placement survives
  quality raises by construction; the tombstone GEAR dump iterates
  entries generically; the save twins ride the entry shape once. A
  parallel index-keyed map loses on every axis (second re-index pass,
  two sources of truth per entry); a `FittedEquipment` subtype would
  touch every constructor site including NPC specs (phase-5 scope).
  **Field names are `grid_x`/`grid_y`, NOT `x`/`y`** (ADVISE blocking
  1): `_d`'s Position branch (`saveload.py:72-82`) checks
  `hasattr(obj, "x") and hasattr(obj, "y")` BEFORE the dataclass
  field pass — plain `x`/`y` names would serialize EVERY entry
  (installed and stored) as the 2-list `[x, y]`, and the entry
  parsers would silently drop the whole loadout and storage on the
  next load. The `ammo` precedent does not extend to an `(x, y)`
  attribute pair; names that cannot form the pair kill the
  collision class at the source.
- Save: placements serialize (`grid_x`, `grid_y` beside the
  StoredEquipment payload).
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

Frigate confirmed at 6×5 (SETTLED 13) — no resize.

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
  the grid editor (SETTLED 6, concretized by SETTLED 16); left pane
  (STORE/STORAGE) keeps its shape. A new UI archetype — cursor +
  pick-up/collide ghost, keyboard-driven, letter blocks colored by
  tier, red/green legality including power-illegal placements,
  net-power readout in the footer. Installs hand off into the editor
  (SETTLED 17); slot-shaped legality and its wording retire at the
  same time (SETTLED 18's consequence — phase 3 drops the slot term,
  as the phase-2 interim rule always intended).
- **Reader surfaces** (SETTLED 18/19): the HUD ship block and the
  ship-buy ledger's slot rows retire their counts (the ledger keeps
  Hull/Shields/Power/Cargo; the HUD line keeps Spd); the hangar's
  LOADOUT tab becomes the read-only letter grid. Power detail lives
  on the fitting screen's POWER line.
- **Purchase flow**: buy-then-install hands the part into the editor
  (SETTLED 17) with the existing validate-before-charge ordering —
  the gate pre-checks and refuses (existing strings) before credits
  move, then the part enters the hand.
- **start_weapons/start_modules**: deterministic auto-fit at new-game
  setup and ship purchase.
- **Combat math**: unchanged seams (`_calc_power_gen` already sums the
  field; module bonus sums already iterate modules). Net generation
  feeding the pool emerges for free.
- **NPC side**: untouched until the parity phase. Specs stay flat tuples;
  the existing slot lint keeps passing (fields retained).

## Phases

- [x] **1. Catalog data pass (geometry only)** — grid dims on the 6
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
  BUILT 2026-09-30 (`/implement-phase 56.1`): gate green **3308**
  (14 new tests), commits `de06db72` (spec fields + loot-quality
  allowlist) / `dd33ce26` (dims + 39 sizes) / `a96b88cc`
  (`fitting.py` + lints) / `1c3b7c18` (render tool). Brief ADVISE-folded
  pre-build (2 blocking — the loot-quality pin test + the census —
  both independently hit and fixed; 7 minors folded: first_fit
  primitive + auto_fit fold, dims/sizes pinned verbatim, family
  coverage assert, mk-chain-only monotonicity, dead-content guard,
  render tool via auto_fit only, family table stays test-side).
  REVIEW pass: REQUEST_CHANGES → em-dashes in the tool's printed
  headers fixed (CP437, doc-56 catch-9 class); item-size pin adopted
  (minor 3); start-loadout resolver duplication test-vs-tool ACCEPTED
  for phase 1 — phase 2 gets four more stamping sites and must extract
  ONE shared resolver at the first third caller (minor 2, recorded).
  PLAYTEST PASSED 2026-09-30 (user: "playtest is good"; glyph letters
  ruled same follow-up — "yes the letters are good too" — SETTLED 15).
  SYSTEMS.md: deferred to the phase-2/3 closes by design — phase 1
  adds no player-facing mechanic (`fitting.py` has no live callers);
  the slot-system entries stay authoritative until placements land.
- [x] **2. Fitting model + gate + upkeep data** — upkeep authors WITH
  the gate, so the first power change is already guarded (companion to
  advisor catch 1); `OwnedShip` placements (per-entry `grid_x`/
  `grid_y`, resolved above); the resting gate
  (install/store/sell symmetric, held-in-hand semantics); auto-fit for
  EVERY install path — new-game starts (`game_loop.py:818`), purchases
  (`game_flow.py:675-676`), BOTH modal install paths (`_loadout.py`
  buy-install and storage-install; the modal stays slot-shaped until
  phase 3, so interim installs auto-place — advisor catch 3, blocking),
  AND the dev-mode grant (`dev_mode.py:342`, audit addendum — its
  loadout is re-authored to pack);
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
  BUILT 2026-09-30 (`/implement-phase 56.2`), PLAYTEST PASSED
  2026-09-30 at the merged phase-3 checkpoint (ruling above; the
  goal-1/open-power questions ride phase 4's balance pass): gate
  green **3335**, commits a2f3b876 (fitting net-power/power_legal) /
  2593bd14 (upkeep + starter re-fund) / ad16dbf0 (ship_fitting model)
  / 8466f410 (stamping sites + dev grant) / 80082d98 (tinker gate) /
  90944e2c (modal routing + refusal strings) / 22a5232b (save twins +
  load normalize) / de891347 (tool+lints adopt the resolver) /
  77c64544 (guide sentence). BUILD SURPRISES (all measured, ruling
  expected at the playtest):
  - **Goal-1 collision → starter base gen 3 → 4.** The ruled draft
    curve's shield_mk1 −1 took back the watt doc 50 tuned the starter
    for: goal-1 (suite-pinned floor 0.94) measured **0.71** with the
    curve authored. The hull now funds the ruled equilibrium AFTER
    upkeep (4 − 1 = 3 effective; goal-1 measured back at exactly the
    pre-phase-2 0.94; pre-change state also measured 0.94). Fallout:
    AC1's *mechanism* moved — an EMPTY skiff fields a bare shield_mk4
    at net 0 (the brief's "3 − 4 < 0" refusal and the
    standing-pin-as-written were authored against gen 3); the FRESH
    skiff (start laser aboard) still cannot field it — the 3×3 needs
    all nine cells and the laser holds one, so the refusal is
    geometric. Pins landed as the true relations (fresh-skiff room
    refusal + empty-skiff zero-headroom power refusal). **Open ruling
    for the playtest:** keep gen 4 + amended pins (current), or gen 3
    + shield_mk1 upkeep 0 (curve amended; both original pins hold;
    goal-1 also measures 0.94 under that shape).
  - **The played save is unfieldable — by design.** The probe
    character's cruiser flies 41 cells (3 plasma + medium + 2 shields
    + 2 reactors) on the 20-cell grid: as-saved it loads post-strip
    (SETTLED 14; probe rows 0.000 — naked, must re-fit), and a
    deterministic same-order re-fit (medium + 2 plasma + compact
    reactor, 16/20, net +8, no shield modules) still sweeps bands
    1-3 at zero damage but drops to **0.200 vs the warlord (23.5 mean
    hull dmg)** vs the baseline's 1.000/0.00 — the shield loss, not
    upkeep (that re-fit flies nothing upkept). Band-1/2/3 turns
    drifted 1.0→1.0 / 1.4→1.9 / 1.8→2.1. Magnitude calibration is
    phase 4; the loadout CHOICE is the playtest's step-2 subject.
  - **ship.py ratchet fired** → the gated model lives in new sibling
    `ship_fitting.py` (ship.py re-exports the seam; imports of ship
    stay function-level — no cycle). The `or []` empty-list sink in
    load normalization (stripped entries appended into a list nobody
    held) was caught by the overlap round-trip test pre-commit.
  REVIEW pass (same session): **APPROVE, 6 minors, zero blockings**
  (save-twin ordering, gated seams, deviation pins, the split, and
  every cross-check independently verified; the goal-1 floor pin and
  the post-strip probe rows reproduce at HEAD). Minors folded in
  fa35e00e: the unreachable unplaced-install fallback now fails
  loudly (was a silent strip-at-next-load class), the tinker refusal
  test pins the kit charge is retained, the modal's triplicated
  kind/slot resolution extracts to `_slot_action_kind` +
  `_installed_slots`, and two import placements lift to module level.
  Deferred with the reviewer's sanction: the `_install_refusal_text`
  reason→string table (guardrail 3-branch; phase 3 retires the slot
  wording there anyway — convert then at the latest), and one
  recorded edge — a HAND-EDITED partial-strip save (weapon strips
  while another missile stays installed) recomputes `cargo_ammo`
  ctx-free in `_remove_weapon`, dropping the Bounty Hunter rack
  doubling (doc 49 SETTLED 7 class); unreachable for real saves
  (old-shape strips everything; power/overlap strips touch modules
  only), and a full fix needs `player_traits` restored before
  normalization — phase-3/5 seam if it ever matters.
- [x] **3. Fitting UI** — the grid editor pane at the mechanic terminal
  (cursor + pick/place, SETTLED 16), letter blocks + tier colors +
  red/green legality, hand model with pane-switch auto-return
  (SETTLED 12 lands here), installs hand off into the editor
  (SETTLED 17); the slot-count summaries retire everywhere
  (SETTLED 18) and the hangar tab becomes the read-only grid
  (SETTLED 19); guide rewrite of the mechanic/loadout sections.
  Budget note (advisor catch 11): the grid editor is a new UI
  archetype — by cohesion it lives in a sibling module beside
  `menus/_loadout.py` (731 lines today); the phase-3 brief carries
  the split forecast (placement stays cohesion-driven — a forecast,
  not a placement driver).
  BUILT 2026-09-30 (`/implement-phase 56.3`): gate green **3368**,
  seven commits + the review-minor fold (see the Status header for
  the full record and the review dispositions). PLAYTEST PASSED
  2026-09-30 at the merged checkpoint, after seven in-play fixes
  (SETTLED 20/21 among them) and the ruling that both LOADOUT tabs
  carry the overview + list — the letter grid renders only in the
  editor. SYSTEMS.md closed with the pass.
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
  retire. (Ordering vs the enemy-volley parity fix: open question 4.)

Each phase gets an Implementation brief at `/refine-design` time before
any build. Every phase close amends the SYSTEMS.md entries it touched
in the same commit ("Ship ops", "Space combat init — parity mirror",
and "Spec-sheet buy modal" are all in scope by phase 3 — advisor
catch 11).

## Implementation brief — Phase 1 (PROPOSED 2026-09-30; ADVISE-folded + BUILT same day, `/implement-phase 56.1`)

Geometry-only catalog pass. Zero behavior change: no live seam reads
the new fields, and upkeep data does NOT land (phase 2, advisor
catch 1).

**Scope (files/hook points)**
1. `src/spacehack/data/ships/__init__.py` — `Ship` gains `grid_w`/
   `grid_h` (int, sentinel default 0 = unsized; the lint fails on 0,
   so forgotten authoring cannot silently pass as 1×1). **ADVISE
   blocking 1 (folded)**: `tests/test_loot_quality.py`'s
   `test_module_bonus_fields_pin_the_module_spec_axes` reads the
   ModuleSpec field set implicitly — the new fields join the test's
   `non_bonus` allowlist (catalog-fixed like price), NEVER
   `_MODULE_BONUS_FIELDS` (quality must never scale geometry,
   SETTLED 5). Landed in de06db72.
2. `src/spacehack/data/ships/core.py` — dims per the ruled table:
   starter 3×3, scout 4×3, hauler 4×4, cruiser 5×4, frigate 6×5
   (SETTLED 13), freighter 6×5.
3. `src/spacehack/data/weapons/__init__.py` and
   `data/modules/__init__.py` — `WeaponSpec`/`ModuleSpec` gain the
   same sentinel-defaulted `grid_w`/`grid_h`.
4. Size authoring across the catalogs — `lasers.py` (3), `missiles.py`
   (3), `plasma.py` (1), `breach.py` (breach_charge_test 1×1),
   `systems.py` (22), `engines.py` (5), `smuggler.py` (4) — the draft
   tables verbatim. (ADVISE blocking 2: census corrected — 31 modules,
   not 32/26.)
5. NEW `src/spacehack/fitting.py` — pure geometry only: a `Placement`
   record + occupancy sets, placement legality (bounds + overlap +
   non-positive-size rejection), and ONE deterministic single-item
   first-fit primitive `first_fit` with `auto_fit` as a fold over it
   (ADVISE minor 3: phase-2 installs place one item into a partially
   occupied grid — primitive + fold, one seam, two consumers). Plain
   int/tuple inputs, no catalog imports, no ctx, no `OwnedShip`
   mutation, no gameplay callers this phase (lints + render tool only).
6. NEW `tests/test_fitting_geometry.py` — the lints + packer units.
7. NEW `tools/fitting_render.py` — prints each hull's grid with its
   start loadout placed as letter blocks (S/R/T/G/C/A/H families,
   L/M/P/E weapons, `.` empty — the glyph proposal (ruled at the
   playtest, SETTLED 15) got its first eyeball here). Builds grids ONLY via `fitting.auto_fit` +
   occupancy helpers, never its own placement loop (ADVISE minor 5);
   output CP437-safe ASCII (REVIEW blocking 1: em-dashes → hyphens).

**Build order**: spec fields → hull dims → item sizes → `fitting.py`
→ tests → render tool → `make check`.

**Binding rulings**: mk scales size, quality never (SETTLED 5); no
rotation (SETTLED 2); frigate 6×5 (SETTLED 13); geometry ONLY — no
upkeep authoring, because `_calc_power_gen` (`combat/_stats.py:87`)
feeds `_build_enemy` (`:291`) and NPC specs fly exactly the families
the upkeep table prices; the draft tables are the user-approved
starting point; `breach_charge_test` sized 1×1 with no exemption
mechanism (it is a registered catalog member — advisor catch 5f
resolved).

**Required tests (permanent — AC5)**: every registered item sized
(ints ≥ 1, catching sentinels); mk-monotonic sizes per family (shield,
targeting, gyro, cargo, armor, smuggler, reactor — w and h each
weakly non-decreasing by mk; chains are the mk ladders ONLY —
capacitor/recharger/heavy_reactor sit outside as singles, ADVISE
minor 4c); family-table coverage asserted against the registry
(ADVISE 4b — a future `shield_mk5` cannot dodge the lint silently);
hull dims pinned verbatim to the ruled table (ADVISE 4a) and item
sizes pinned verbatim likewise (REVIEW minor 3 — a monotone-preserving
mid-chain drift must be a deliberate edit); every hull's start loadout
packs via `auto_fit`; hull dims within the render-budget ceiling
(grid_w ≤ 8, grid_h ≤ 6 — every ruled dim fits with margin; phase 3
may raise it deliberately); dead-content guard — every item fits at
least one hull (ADVISE 4d); packer units (exact fit, no-fit, overlap
rejection, determinism). Pure-function contract: `fitting.py` tests
land same-commit.

**Stop point (do NOT start)**: no `OwnedShip` changes, no placement
fields, no save/parser changes, no power gate, no upkeep data, no UI
of any kind (grid pane, HUD/hangar/ship-buy readouts), no guide
edits. That is phases 2-3.

**Playtest checkpoint**
1. `python3 tools/fitting_render.py` — eyeball all six hull grids
   with start loadouts placed (Skiff 3×3 nearly empty; Cruiser
   13/20 cells used; Frigate 17/30); shapes match the ruled table and
   the glyph letters read clean.
2. `make check` green with the new lints in the suite.
3. New game + Continue an existing dev save — identical behavior
   (nothing reads the new fields; save shape untouched).
4. Guide diff: NONE this phase (no player-facing change) — recorded
   per the every-checklist-carries-a-guide-item rule.

## Implementation brief — Phase 2 (APPROVED 2026-09-30 — "approved.
we can always adjust later after playtesting"; PROPOSED +
ADVISE-folded same day, dispositions below)

Fitting model + resting power gate + upkeep data. Player-facing
effect: every install path becomes grid-and-power gated (auto-placed);
the modal itself stays slot-shaped until phase 3.

**Scope (files/hook points)**

1. `src/spacehack/data/modules/systems.py` — upkeep authors WITH the
   gate (advisor catch 1's companion rule): `shield_mk1..mk4`
   −1/−2/−3/−4; `shield_capacitor` −1; `shield_recharger` −1;
   `targeting_computer/mk2/mk3/mk4` −1 flat;
   `gyro_stabilizer/mk2/mk3/mk4` −1 flat — 14 authored values, the
   doc's draft curve verbatim. Armor (−1..−4) exists; reactors stay
   positive; cargo/smuggler structural 0. Enemy side effect (AC7,
   accepted): `_calc_power_gen` (`combat/_stats.py:87`) already sums
   the field, so NPC specs flying these families lose pool — strictly
   player-favor direction, probe-refereed, no enemy code changes.
2. `src/spacehack/fitting.py` — pure power-gate helpers, plain ints,
   no catalog imports (the module's standing contract): net =
   base + Σ bonuses and a `power_legal` predicate. The signature
   takes an explicit bonus list so phase 3's held-items-count-as-
   fitted (SETTLED 12) passes the hand's items with no redesign.
3. `src/spacehack/ship.py` — the placement model (resolved open
   question 3):
   - `StoredEquipment` gains `grid_x: int | None = None` and
     `grid_y: int | None = None`; stored entries are always None.
     Names deliberately avoid the `(x, y)` pair — see item 4 (ADVISE
     blocking 1). `__post_init__`'s bare-id normalization passes
     placed entries through unchanged (verified: entries already
     `StoredEquipment` are kept as-is).
   - `resting_power(owned, ship_spec, ctx=None) -> int` — the
     SIGNED net: base gen + Σ effective `power_gen_bonus`, computed
     by the SAME quality/randart-scaled sum combat uses
     (`_module_bonus_sum`, function-level import — ADVISE minor 5:
     no second implementation to drift). Distinction stated once,
     pinned by test: `_calc_power_gen` (`combat/_stats.py:87`)
     CLAMPS at 0 for the combat pool; the gate reads the unclamped
     signed net. Weapons contribute nothing (no upkeep — doctrine:
     guns cost power when fired, modules cost power to exist).
   - Gated commit wrappers for the player's single-item actions
     (the modal's four paths route here): install/place stamps via
     `fitting.first_fit` over live occupancy + power check;
     store/sell refuses when the post-removal resting grid would go
     negative (SETTLED 3). The mechanical primitives
     (`_install_*`, `_remove_*`, `store_*`,
     `move_installed_equipment_to_storage`) stay ungated BY DESIGN —
     the strip-all primitive and load-time normalization must bypass
     (they end valid by construction; a gate inside `store_*` would
     make the strip loop RAISE the moment a reactor precedes
     shields — `ship.py:716-720` turns a refused store into a
     ValueError).
   - `start_fitted_entries(ship_spec, ctx=None)` — THE shared
     start-loadout resolver: base entries + `auto_fit` stamps, tuple
     order preserved (weapon_ammo coupling free). This is the
     phase-1 REVIEW minor-2 extraction firing at its trigger: the
     test, the render tool, and three live sites resolve start
     loadouts today; phase 2 makes five — one resolver in `ship.py`
     (it owns entry construction and may import catalogs;
     `fitting.py` stays catalog-free).
   - `normalize_fitted_grid(owned, storage, ship_spec) -> list[str]`
     — SETTLED 11/14 made deterministic (ADVISE minor 4: the
     storage sink is a parameter — the `store_*` primitives need
     it): entries without placements strip (14); power-invalid
     grids strip highest-upkeep-first, ties by later tuple
     position, until net ≥ 0 (11); geometrically illegal placements
     (overlap/out-of-bounds — hand-edited saves) strip the later
     entry, and in a cross-tuple overlap the MODULE strips —
     weapons win (one grid, two tuples, one rule). Returns stripped
     labels for the caller to log.
4. `src/spacehack/saveload.py` + `saveload_ship.py` — installed-entry
   parsers read grid_x/grid_y (dict entries only; bare-id legacy stays
   placement-less and strips). The writer gets a
   `StoredEquipment`-aware branch in `_d` that emits the field dict
   MINUS placement keys whenever they are None (ADVISE blocking 1 +
   the standing decision): installed entries serialize
   `grid_x`/`grid_y` ints, storage payloads never carry placement
   keys. The branch must sit AHEAD of the Position check regardless
   of the renamed fields — defense in depth on the serializer order.
   `load_game` runs `normalize_fitted_grid` once owned ship AND
   storage both exist (after `saveload.py:766`); the notice line is
   logged post-ctx.
5. Stamping sites — the `OwnedShip(` construction census, grep-verified
   complete this session: `game_loop.py:818` (new game) and
   `game_flow.py:_new_owned_ship` (purchase) switch to
   `start_fitted_entries`; `saveload_ship.py:38` is the load path
   (item 4); `dev_mode.py:342` **re-authored** — the current grant is
   64 cells of hardware on a 30-cell frigate and cannot pack. New
   dev grant (ADVISE blocking 2 — at most THREE 2×3 plasmas fit a
   6×5 grid, rotation excluded; the row-2 residue class caps it):
   3× `plasma_cannon` (18 cells, rows 0-2) + `compact_reactor`
   (1×2) + `shield_mk1` (2×2) = 24/30, net 6+3−1 = +8 — still the
   volley monster, with a 2×3-free remainder (rows 3-4) so the
   playtest's geometry-refusal step has a live subject (another
   plasma can NEVER fit; a small part still can). Lint: dev grant
   packs and is power-valid.
6. `src/spacehack/tinker.py` — SETTLED 11 refusal: an installed-module
   raise (`_installed_targets` → `_tuple_field_apply`) whose
   quality-scaled upkeep would send the resting grid negative is
   refused (weapons and STORED modules untouched — nothing draws
   power while stored). `_tuple_field_apply` preserves sibling fields,
   so successful raises keep x/y by construction.
7. `src/spacehack/menus/_loadout.py` — the four commit paths
   (`_apply_purchase` INSTALL branch, `_apply_stored_install`,
   `_apply_store`, `_apply_sell_installed` — sell removes via
   `_remove_*` directly, so it gets its own gated wrapper) route
   through the gated wrappers; every bespoke slot-arithmetic site
   routes through the same predicates (ADVISE minor 6: these are
   `_log_storage_failure`'s counts at :312-326 AND
   `_apply_purchase`'s in-branch refusal at :580-583 — audit
   hotspot 1: no bespoke arithmetic anywhere). Interim legality is
   DUAL while the modal stays slot-shaped: slot free AND grid fits
   AND power ok — a slots-full-but-grid-free install is refused on
   slots with the EXISTING string ("No compatible … slot is
   available"), keeping the displayed counts honest until phase 3
   drops the slot term. Validate-before-charge ordering preserved
   (install decides, then `_apply_purchase` charges). The
   "Wpn x/y Mod a/b" footer is UNTOUCHED — reader surfaces are
   phase 3.
8. `tools/fitting_render.py` + `tests/test_fitting_geometry.py` —
   both adopt `start_fitted_entries`; the resolver duplication dies
   at its trigger.
9. Guide — ONE sentence, `data/guide/__init__.py:403`: "installing a
   part is useful only when the ship has a compatible free slot." →
   "installing a part needs free grid space and spare power." (final
   wording the user's; the full fitting-screen rewrite rides phase 3).

**Refusal strings (prose gate — land only as approved here)**
- No room: `No room on the grid for {name}.`
- Power, install: `{name} needs more power than the ship generates.`
- Power, removal: `Removing {name} would leave the ship short on power.`
- Tinker: `That upgrade would draw more power than the ship generates.`
- Load normalization (only when non-empty):
  `Fitted gear moved to storage: {names}.`
- Slots-full (interim, unchanged existing string): `No compatible
  {kind} slot is available on this ship.`

**Build order**: upkeep data → `fitting.py` gate helpers → `ship.py`
model + resolver + wrappers + normalization → stamping sites + dev
re-author → tinker gate → modal routing + refusal strings → save
twins → tests → tool/test adopt the resolver → guide sentence →
probe re-run → `make check`.

**Binding rulings**: SETTLED 3 (gate symmetric on removal), 4 (upkeep
= negative `power_gen_bonus`), 5 (quality never scales GEOMETRY;
upkeep magnitude does scale — geometry fixed, watts tiered), 11 (no
dark state: boundary normalization + tinker refusal), 14
(strip-on-load), resolved open question 3 (per-entry placement as
`grid_x`/`grid_y` on `StoredEquipment`), the phase-1 REVIEW minor-2
extraction (fires as `start_fitted_entries`), draft upkeep curve
authored verbatim (phase 4 retunes against the probe),
validate-before-charge preserved.

**Close obligations + budget note**: SYSTEMS.md amends at the
phase-2 close — "Ship ops" and "Space combat init — parity mirror"
(ADVISE minor 7; phase 1's deferral lands here; "Spec-sheet buy
modal" can wait for phase 3). Budget (ADVISE minor 8):
`saveload.py` (958 lines) and `ship.py` (762) both take real
additions this phase — expect the in-commit extraction of cohesive
siblings when the 1000-line ratchet fires; placement stays
cohesion-driven (a forecast, not a driver).

**Required tests (permanent — same-commit per the pure-function
contract)**
- AC1 pin: `install_stored_equipment` of `shield_mk4` on the starter
  Skiff is refused (power side: 3 − 4 < 0) AND the standing pin —
  the cheapest 3×3 shield's upkeep exceeds the starter hull's base
  generation — fails loudly through any phase-4 retune (advisor
  catch 6).
- Start-loadout power validity, every hull, base quality (nets +3/
  +6/+3/+7/+6/+7 under the draft curve; re-run after every phase-4
  magnitude change — advisor catch 8).
- Dev grant packs + power-valid.
- Gate symmetry: storing/selling the reactor funding shields is
  refused; storing a shield never is (net only improves).
- Tinker: refusal when the bump trips net; a successful raise
  preserves grid_x/grid_y.
- Ammo coupling with placements stamped (advisor catch 4): store the
  middle missile → `weapon_ammo` re-keyed, survivors keep their
  placement.
- Save round-trip: a placed grid survives exactly; storage payload
  dicts carry NO placement keys; a placement-less (old-shape) save
  strips to storage with the notice; a hand-crafted power-invalid
  save AND an overlapping-placement save (including a cross-tuple
  weapon-module overlap — module strips) each normalize
  deterministically.
- Clamp pin (ADVISE minor 5): gate net vs combat pool stay related
  by exactly the clamp — `_calc_power_gen(spec, modules) ==
  max(0, signed_net)` — so a phase-4 drift that makes the gate
  disagree with the pool fails loudly.
- Purity units for the net-power helper (negative bonuses, quality
  scaling, randart axis).
- Probe (ADVISE blocking 3 rewording): re-run `tools/balance_probe.py`
  against the recorded baseline and REPORT the deltas — the player's
  own pool drops alongside the enemy's (the save's cruiser flies the
  upkept families), so row direction is indeterminate, not
  monotone; regressions are investigated, magnitude changes are
  phase 4.

**Stop point (do NOT start)**: no grid editor pane, hand model, or
pane-switch auto-return (SETTLED 12 lands phase 3 — the pure gate's
signature is the only preparation), no HUD/hangar/ship-buy readout
changes (the footer stays slot-shaped), no tier colours or glyph UI,
no magnitude retuning (phase 4 — the probe is the referee), no NPC
spec or slot-field changes (phase 5), no missile/EMP work.

**Playtest checkpoint**
1. Load the existing long-run save: all installed gear arrives in
   storage with the notice line (SETTLED 14 strip-on-load); the grid
   starts empty.
2. Re-fit through the mechanic: installs auto-place; fight something
   — playable, and note the power-pressure feel as phase-4 input.
3. Gate stress on a live ship: (a) install a part larger than the
   remaining space → "No room on the grid"; (b) spend the power
   headroom, then install one more upkept module → power refusal;
   (c) store the reactor funding the shields → removal refusal;
   (d) tinker an installed shield until the bump would trip →
   tinker refusal.
4. Dev mode (`SPACEHACK_DEV=1`): the frigate arrives 24/30 packed
   (3 plasma + compact reactor + shield_mk1), power-valid; a fourth
   plasma is refused (no 2×3 space remains); a small part still
   installs.
5. Save/quit/continue with a fitted grid: identical placements,
   ammo, and storage after the round-trip.
6. Probe: `python3 tools/balance_probe.py` — deltas vs the doc's
   evidence table reported; regressions investigated (your own
   cruiser's pool drops too — direction is indeterminate; magnitude
   is phase 4).
7. Guide diff: the one mechanic sentence — before "…useful only when
   the ship has a compatible free slot." / after "…needs free grid
   space and spare power." (or the user's edit; note the sentence
   says "grid" a phase before any grid is visible — defensible
   because the refusals already say it, phase 3 shows it).

**ADVISE dispositions (folded 2026-09-30, same day as proposal)** —
verdict ADVICE, 3 blocking + 5 minor, all folded:
- Blocking 1 (`_d` Position-branch collision): field names ruled
  `grid_x`/`grid_y` (Data model + items 3-4); serializer branch
  ordered ahead of the Position check as defense in depth.
- Blocking 2 (dev grant unpackable — max three 2×3 on 6×5):
  re-author is 3× plasma, 24/30 (item 5, playtest 4).
- Blocking 3 (probe "may only improve" unsound — the player pool
  drops too): reworded to report-deltas/investigate-regressions
  (tests + playtest 6).
- Minor 4: `normalize_fitted_grid` signature takes the storage sink;
  cross-tuple overlap rule = module strips (item 3).
- Minor 5: `resting_power` reuses `_module_bonus_sum`; clamp
  distinction stated + pinned by test (item 3, tests).
- Minor 6: slot-arithmetic anchors corrected (`_log_storage_failure`
  + `_apply_purchase`); interim legality is DUAL (slots AND grid AND
  power), slots-full keeps the existing string (item 7, strings).
- Minor 7: SYSTEMS.md close obligations added ("Ship ops",
  "Space combat init — parity mirror").
- Minor 8: budget note added (saveload.py 958 / ship.py 762).
- Q2 correction adopted: the strip-loop failure mode is a ValueError
  crash, not a deadlock (item 3).

## Implementation brief — Phase 3 (PROPOSED 2026-09-30, `/refine-design`; ADVISE-folded same session — dispositions below)

Fitting UI: the grid editor pane at the mechanic terminal, installs by
hand, the slot-count retirement everywhere, and the guide rewrite.
Zero combat-math change — no probe run this phase.

**Scope (files/hook points)**

1. NEW `src/spacehack/menus/_grid_editor.py` — the editor in two
   layers: a PURE state machine (cursor position, held entry + its
   origin anchor or None for a handed-over part, ghost legality
   computed by REUSING `fitting.in_bounds`/`footprint`/`net_power` —
   never re-derived; plain ints and catalog-free like `fitting.py`)
   and the presentation layer (grid rows as runs-coloured letter
   lines, cursor + ghost painted in, the POWER footer). Also exports
   the read-only letter-grid renderer the hangar and the mechanic
   tab reuse (SETTLED 19).
2. `src/spacehack/pygame_split.py` — the grid key surface, fully
   counted (ADVISE blocking 2): a `grid_pane: bool = False` frame
   flag; when the right pane hosts the grid, a KEY TABLE maps
   arrows, ENTER, D, X, and TAB to `GRID:*` outcomes — arrows for
   the cursor, `GRID:ENTER` pick/drop (ENTER is otherwise dead:
   letter rows carry no actions), `GRID:STORE`/`GRID:SELL`, and TAB
   SURFACED to the host (today it is swallowed inside the worker
   with a focus flip, so the SETTLED-12 auto-return could never
   fire). `GRID:*` outcomes route through the keep-open
   `apply_action` path (a bare outcome would exit the modal on the
   first arrow). `_handle_key` restructures behind a key table to
   stay within the 40-line cap. Nothing else in split behavior
   moves; B/S left-tab MODE outcomes are unchanged.
3. `src/spacehack/menus/_loadout.py` — right pane becomes the grid
   (SETTLED 16/6); left pane STORE/STORAGE keeps its shape. The
   MANAGE chooser family (`_ship_rows`, `_choose_ship_action`,
   `_apply_manage_ship_item`) dies; `_apply_store`/`_apply_sell_installed`
   fold into the D/X handlers (the removal gate + price confirm are
   reused, not rebuilt). Hand-off installs (SETTLED 17): the chooser
   checks AFFORDABILITY ONLY, charges, and the part enters the
   editor's hand on the grid pane — no room/power pre-check (the red
   ghost is the refusal, per SETTLED 16/17; a bought part that
   cannot place auto-returns to storage at session end and is never
   destroyed — the part, not the placement, is what was charged
   for). While holding: D stores, X sells (both through
   `removal_trips_power`, SETTLED 3; X carries the price confirm).
   Install actions refuse while the hand is full (single-hold
   invariant). The footer becomes the POWER line. THE SLOT GUARDS
   RETIRE HERE (ADVISE blocking 1): `install_refusal` drops its
   slots check AND `_install_weapon`/`_install_module` lose their
   slot guards in the same commit — as-is, a grid-legal
   beyond-slots install would pop the part from storage, charge the
   player, and silently destroy the part (`gated_install_entry`
   discards the primitives' False). A beyond-slots install must land
   on the grid, pinned. `INSTALL_REFUSAL_SLOTS` and its pins retire;
   `_install_refusal_text` converts to the reason→string dispatch
   table (phase-2 REVIEW minor 1, due here). ESC is two-stage while
   holding (ADVISE minor 8): holding → return to origin and stay;
   empty-handed → exit the terminal.
4. `src/spacehack/hud.py` — the ship-block line drops `Wpn x/y Mod
   a/b` (SETTLED 18), keeps `Spd n`; `_render_ship_stat_rows`'s
   dead weapons_n/weapon_slots/modules_n/module_slots parameters go
   in the same edit; the layout comment's slot sketch updates.
5. `src/spacehack/menus/_ship_buy.py` — the ledger drops its
   `Weapon slots` / `Module slots` rows (Hull/Shields/Power-per-turn/
   Cargo stay; SETTLED 18).
6. `src/spacehack/menus/_ship_menu.py` — the hangar LOADOUT tab
   renders the read-only letter grid (SETTLED 19);
   `_slot_rows`/`_weapon_row`/`_module_row` retire with it.
7. `src/spacehack/menus/_mechanic.py` — the mechanic LOADOUT tab's
   slot lists become the same read-only grid under the Manage row
   (the last slot-shaped surface dies with SETTLED 18); the AMMO
   tab's `Slot {n}:` row labels reword to the weapon name (stale
   vocabulary once slots retire).
8. `src/spacehack/data/guide/__init__.py` — the fitting-screen
   rewrite (draft below) PLUS the slot-vocabulary audit across the
   WHOLE corpus and live UI strings (ADVISE minor 9): guide +
   tutorial text + the AMMO row labels + the WEAPON SLOTS/MODULE
   SLOTS headers + the HUD layout comment. The guide's ground-gear
   "Armour covers five slots" line is classified untouched.
9. NEW `tests/test_grid_editor.py` + updated pins across
   test_pygame_ui, test_mechanic, test_ship_mutation (the
   INSTALL_REFUSAL_SLOTS and buy-refusal pins retire or re-shape),
   test_ship_buy_ledger, test_hud.

**The hand model (ADVISE minor 7, pinned)**: the hand is modal-runner
LOCAL session state — never module-level (the module-level state
contract), never serialized, never stored in the frame (GUIDE
rebuilds re-derive presentation from the session). A PICKED-UP entry
stays in the owned tuple at its origin anchor — the tuple is always
the whole truth, so any snapshot is exact, held-as-fitted power is
free, and D/X keep valid slot indices; a HANDED-OVER part is not in
the tuple until dropped. Every session exit resolves the hand:
pane TAB (auto-return), ESC (return-to-origin), terminal exit
(auto-return; `_run_loadout_menu` hooks `run_interactive`'s return,
currently discarded), and QUIT/SystemExit — which write no save, so
disk state simply predates the session (safe; say so in tests).

**Binding rulings**: SETTLED 2 (no rotation), 6 (free rearrangement —
held-in-hand never trips the gate; only commits do), 12 (auto-return;
the gate-refused leg is a DEFENSIVE invariant — unreachable by design
with single-hold + vacated origins + never-fitted storage neutrality,
unit-tested against fabricated state only, and it speaks the approved
removal string if it ever fires; ADVISE minors 4+6), 15 (letters),
16 (cursor + pick/place; two-stage ESC), 17 (hand-off, affordability
pre-check only; new ships still arrive auto-fitted outside the
modal), 18 (summaries retire), 19 (hangar read-only grid); the
power-gate section's fitting-screen readout format; tier colours
reuse `quality_color` (base reads plain, randart reads legendary;
the ghost's legality colour overrides the tier colour) — the visual
taste itself rules at the playtest.

**Strings (prose gate — land only as approved here)**
- Editor hint line: `ENTER pick up/drop`, `D store held`,
  `X sell held`, `TAB parts`, `ESC back` (composed with the existing
  `modal_hint`).
- POWER footer, sign-conditional per component exactly as the
  power-gate section's example (`POWER: +9 gen / -2 upkeep / +7 net`;
  a zero component renders bare `0` — never `-0`; ASCII hyphen).
- Guide, Mechanic section — replacing "The mechanic handles repairs,
  refueling, ammunition, and ship equipment. STORE keeps equipment
  for later; installing a part needs free grid space and spare
  power." with: "The mechanic handles repairs, refueling, ammunition,
  and ship equipment. Your hull's fitting grid holds every weapon
  and module - each takes grid space, and working modules draw power
  every turn. Install a part by placing it on the grid: green means
  it fits, red means it does not. STORE keeps equipment for later."
  (final wording the user's).

**Build order**: editor state machine + tests → split grid key
surface → grid render + cursor → pick/place/drop + two-stage ESC →
D/X gates → hand-off installs + SETTLED-12 auto-return + hand-model
exits → slot-guard retirement → footer POWER line → reader-surface
retirement (hud/ledger) → hangar + mechanic grids + AMMO reword →
guide rewrite + corpus audit → `make check`.

**Required tests (permanent — same-commit per the pure-function
contract)**
- State-machine units: cursor bounds, pick-up/drop, ghost legality
  (bounds + overlap + POWER, each red), determinism; reuse-pinned
  (no re-derived geometry/power).
- Hand-off flow: affordability refused before charge; a part that
  cannot fit anywhere still enters the hand, ghosts red everywhere,
  and auto-returns to storage at exit — bought once, never
  destroyed (this re-shapes phase-2's buy-refusal pin).
- Slot-guard retirement pin: a beyond-slots install LANDS on the
  grid (Skiff + three 1×1 lasers).
- Auto-return (SETTLED 12, first live test): TAB/exit with a picked
  item → snap-back; with a handed-over part → storage. The
  gate-refused leg: pure-resolver unit test on fabricated state
  only (unreachable by design through the UI).
- D/X from the hand: the funding reactor refuses (removal string);
  a shield stores/sells freely; X carries the price confirm;
  install actions refuse while the hand is full.
- Rearrangement never trips the gate mid-edit; only commits do.
- Save/load round-trip of HAND-placed anchors (not auto-fit's);
  QUIT-with-held writes no save (disk predates the session).
- Reader pins: HUD line (`Spd n` only, dead params gone), ledger row
  set, footer format (sign-conditional, zero bare), hangar/mechanic
  grid renders (letters at anchors).
- Retirement pins: no slots refusal string reachable; guide corpus +
  live UI carry no stale slot vocabulary after the audit.
- CP437 check on every new glyph string.

**Stop point (do NOT start)**: no rotation, no tier-colour palette
beyond reusing `quality_color`, no HUD cells/net-power counters
(SETTLED 18 retired them — do not reintroduce), no magnitude
retunes (phase 4), no NPC/enemy work (phase 5; `weapon_slots`/
`module_slots` FIELDS and the NPC slot lint stay untouched), no
runtime brownouts, no grid resizing.

**Close obligations + budget**: SYSTEMS.md amends at the phase-3
close (the merged checkpoint) — "Ship ops", "Space combat init —
parity mirror" (phase 2's parked obligations), AND "Spec-sheet buy
modal" (the ledger row retirement touches it). Split forecast
(ADVISE minor 11): `_loadout.py` (731) NETS DOWN — the MANAGE family
dies; `pygame_split.py` (883) takes the grid key surface to ~940;
`_grid_editor.py` lands ~300. Placement stays cohesion-driven — a
forecast, not a driver.

**Playtest checkpoint** (merged phase-2 + phase-3 — the deferred
items ride here)
1. Load the long-run save: strip notice, empty grid (SETTLED 14).
2. Re-fit BY HAND on the visible grid: storage install hands the
   part over; green/red ghosts; drop; rearrange freely; fight
   something — the re-fit power feel is phase-4 input.
3. Gate stress: no-room ghost stays red everywhere; power-illegal
   drop red; D-store/X-sell of the funding reactor refused; tinker
   refusal (phase 2's SETTLED 11).
4. Auto-return: TAB away while holding (snap-back), leave the
   terminal while holding (handed-over parts land in storage).
5. Dev mode (`SPACEHACK_DEV=1`): frigate 24/30 as granted; a fourth
   plasma hands over, ghosts red everywhere, auto-returns to
   storage — bought, never lost.
6. Save/quit/continue: hand-placed anchors, ammo, storage identical.
7. Reader surfaces: HUD line shows Spd only; the ledger has no slot
   rows; the hangar LOADOUT tab shows the letter grid.
8. Guide diff review: the Mechanic-section rewrite (before/after in
   this brief) + every corpus-audit hit dispositioned.
9. The phase-2 deferred rulings: starter gen 4 (as built) vs gen 3 +
   shield_mk1 upkeep 0; refusal-string wording tweaks expected here.
10. Probe: NOT re-run (zero combat-math change this phase; the
   phase-2 report stands).

**ADVISE dispositions (folded 2026-09-30, same session as proposal)**
— verdict ADVICE, 5 blocking + 7 minor, all folded:
- Blocking 1 (slot guards destroy parts): the guards retire with the
  slots check in the same commit + beyond-slots landing pin + the
  missed test files join the pin list (item 3, tests).
- Blocking 2 (split extension under-counted): full grid key surface
  named — GRID:ENTER (ENTER otherwise dead on action-less rows),
  D/X mappings, TAB surfaced (auto-return needs the host to see the
  switch), keep-open routing for GRID:*, key table for the 40-line
  cap (item 2).
- Blocking 3 (hand-off pre-check contradiction): resolved toward the
  rulings — affordability only at hand-off; the red ghost is the
  placement refusal; unplaceable bought parts auto-return to storage
  (never destroyed). The "never enters the hand" test re-shaped;
  playtest step 5 rewritten (item 3, tests, step 5).
- Blocking 4 (no approved refused-switch string): routes to the
  approved removal string; the leg itself is defensive-only per
  minor 6.
- Blocking 5 (SYSTEMS.md absent): close obligations added — all
  three entries, at the merged checkpoint.
- Minor 6: the gate-refused switch is unreachable by design
  (single-hold, vacated origins, never-fitted storage neutrality);
  unit-test on fabricated state, no playtest step, install-refused-
  while-holding invariant added.
- Minor 7: the hand model subsection (local session state; picked
  items stay in the tuple at origin; every exit resolves; QUIT
  writes no save).
- Minor 8: two-stage ESC pinned.
- Minor 9: the audit covers live UI strings too (AMMO row labels,
  slot headers, HUD comment); ground-gear "five slots" classified
  untouched.
- Minor 10: the MANAGE family's death and D/X reuse named;
  `_slot_rows`/`_weapon_row`/`_module_row` retire; ghost legality
  reuses `fitting` (never re-derives); test_mechanic/test_ship_mutation
  join the pin list; phase-2's buy-refusal pin re-shapes.
- Minor 11: split forecast added (_loadout nets down; pygame_split
  ~940) + `_render_ship_stat_rows` signature cleanup.
- Minor 12: POWER footer sign-conditional, zero bare, pinned.

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

1. **Upkeep magnitudes** beyond the draft curve (tied to phase 4).
2. **Enemy-volley parity slotting** — before phase 5, after phase 4, or
   its own fix doc whenever (it is independent of the grid).

(HUD readout shape — formerly open question 2 — SETTLED 2026-09-30 at
phase-3 brief time as SETTLED 18/19: the summaries retire rather than
convert. Renumbered; older prose citing three open questions predates
this.)

(Placement data shape — formerly open question 3 — RESOLVED
2026-09-30 at phase-2 brief time per the pre-committed census
procedure: per-entry x/y on `StoredEquipment`; see Data model.
Renumbered twice: first when the glyph letters settled as SETTLED 15,
again at this resolution; older prose citing "open question 4" for
placement predates both.)

## Pre-implementation audit

REQUIRED before phase 1 builds (per knowledge.md) — **VERIFIED
against live code 2026-09-30** (refine session, before the phase-1
brief). Every advisor-catch anchor confirmed:

- **The save twin pair**: writer `_d(ctx.player_owned_ship)`
  (`saveload.py:197`) and parsers `_parse_owned_ship`
  (`saveload_ship.py:21-59`, rebuilding through
  `_parse_loadout_entries` → `parse_weapon_entry`/`parse_module_entry`)
  and `_stored_equipment_from_dict` (`saveload.py:86+`). Standing
  decision: placement rides the INSTALLED entry (x/y read by the entry
  parsers in phase 2); storage payloads never carry placement keys —
  stored items have no position, so nothing is dropped. Binding shape
  settles with the phase-2 brief (open question 3; per-entry x/y is
  the lean).
- **The tinker kit seam**: `_installed_targets`/`_flown_weapon_targets`
  (`tinker.py:232-257`) apply through `_tuple_field_apply`
  (`tinker.py:130-142`), which rebuilds the tuple in order replacing
  one entry — per-entry placement survives by construction; the
  SETTLED 11 refusal hooks the apply.
- **The tombstone GEAR dump** (`tombstone.py:272-293`): iterates
  `owned.weapons`/`.modules` generically — placement-carrying entries
  survive.
- **The enemy parity seam**: `space_scale.roll_flown_equipment`
  (`space_scale.py:45`) and `combat/_stats._build_enemy`
  (`_stats.py:280`, calling `_calc_power_gen` at `:291`) — where
  phase-2 upkeep lands (AC7) and where the phase-5 lint replaces the
  slot lint.
- **The auto-fit stamping sites**: new game `game_loop.py:818`;
  purchase `_new_owned_ship` (`game_flow.py:673-681`, including
  `top_off_missile_magazines`).
  **Phase-2 brief addendum (2026-09-30, full `OwnedShip(` grep)**: a
  FIFTH construction site the original audit missed — the dev-mode
  grant `_dev_owned_ship` (`dev_mode.py:340-353`), whose loadout
  (4 plasma + 4 heavy missiles + reactor_mk4 + shield_mk4 +
  recharger + targeting/gyro/armor mk4 ≈ 64 cells) cannot pack on
  the frigate's 30 cells and is re-authored by the phase-2 brief.
  The load-side twin `saveload_ship.py:38` is covered by the save
  twin pair above (verified live this session).
- **`breach_charge_test`** (`data/weapons/breach.py:13`): a real
  auto-registered catalog weapon (the militia quest prototype), NOT a
  test-side fixture — the every-item-sized lint covers it (1×1); no
  exemption mechanism needed.
- **Census**: 6 hulls (`data/ships/core.py`), 8 weapons (lasers 3,
  missiles 3, plasma 1, breach 1), **31 modules (systems 22, engines
  5, smuggler 4)**; every id maps to a draft size-table row.
  (Corrected at build time + ADVISE blocking 2: this audit originally
  said "32 modules (systems 26...)" — internally inconsistent and
  wrong; the registry is ground truth.) Construction sites: the only
  spec construction outside `data/` is the keyword-based synthetic
  `ModuleSpec` in `tests/test_loot_quality.py:176` (harmless — and its
  field-set pin test now allowlists the grid fields; ADVISE blocking
  1). The NPC slot lint
  `test_every_loadout_fits_its_hull_slots`
  (`tests/test_space_scale.py:208`) reads slot counts via `find_ship`
  — green while the fields are retained.
- **`debug_session.py` / `tools/save_debug.py`**: load through the
  production deserializer, so SETTLED 14's strip-on-load happens
  before they see state — phase-2 tests pin the post-strip shape.
- **Three duplication hotspots (the audit template's requirement)**:
  1. Gate legality vs `_loadout.py`'s slot arithmetic and
     `_log_storage_failure` vocabulary — phase 2 routes every refusal
     through `fitting.py`'s pure checks, no bespoke arithmetic.
  2. Geometry packing vs any auto-fit reimplementation — ONE
     deterministic packer in `fitting.py` serves the phase-1 lints,
     the render tool, and the phase-2 install paths.
  3. The grid pane vs the existing `pygame_split` row model — phase
     3's new UI archetype is a sibling module beside
     `menus/_loadout.py` (695 lines, verified), not a SplitRow
     extension.
