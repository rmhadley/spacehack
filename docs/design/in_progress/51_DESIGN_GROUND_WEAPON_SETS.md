# DESIGN: Ground Weapon Sets — 4 slots, one-toggle swap

**Status: IN REFINEMENT (2026-09-25) — core rulings SETTLED 1 below;
open questions 1–2 (tutorial wording, board immunity) parked at their
phases; nothing implemented.**

## Overview

Ground equipment grows from 2 weapon slots to **4, organized as two
dedicated sets: 2 ranged slots + 2 melee slots**. A set holds either
one two-handed weapon or up to two one-handed weapons of its class.
In combat, a single new action swaps the ENTIRE active set for the
entire holstered set — any composition, **1 AP** — with magazines
persisting on the holstered weapons. Out of combat, set management is
free through the armory/character screens. The holstered set is
equipment, not cargo: it never occupies expedition-pack slots.

This is a **quality-of-life update, not a new mechanic** (user,
2026-09-25): the 1-AP swap economy already exists — the C → character
screen path charges 1 AP per change today (`_loop.
_handle_character_action`) — and weapon instances already carry their
magazines through equip/store round-trips. What's missing is the
frictionless verb, the dedicated slots, and the pack relief.

**Thematic frame** (user): holsters and straps — the quick-draw
harness that makes a four-weapon loadout plausible.

## Measured evidence (doc 50 session, 2026-09-25)

The design is driven by measured failures of the 2-slot world:

- **The min-range blind zone**: point-blank accuracy penalty is
  −35%/cell inside min range, so a railgun (min 3) at melee range
  shoots at ~2%. Vs the tutorial scavenger pack the railgun won 60%
  at 61% HP with 25.1 rounds sprayed; explosive launchers suicide on
  their own splash (0%/119%). Doubling 2H damage fixed the DPS race
  but left the blind zone bit-identical.
- **The toggle dissolves it**: railgun + mono blade with a simulated
  1-AP mid-turn toggle won 100% at 25% HP on CURRENT specs, and
  full-cleared (re-engagement loop) at **100% at every rung of the
  strength AND reflexes 10–100 ladders** — viability unconditional,
  stats modulate cost only (reflexes 9%→0%; strength inert — the
  blade's str//10 never crosses a TTK step vs 18 HP trash).
- **Melee is the anti-ranged answer already** (mono blade 96% vs the
  sentry trio — guards never kite) — the set system formalizes
  carrying both answers.
- **Pack pressure**: a backup weapon today occupies one of ~4
  strength-capped expedition slots (SYSTEMS.md "Ground gear").

## Philosophy alignment

| Principle | How this design holds it |
|---|---|
| No special cases / uniform mechanisms | One swap verb for every composition; set membership is a table (`damage_type` → set), not per-weapon flags |
| Data-first | Set membership derives from the catalog (`damage_type`); no new content fields |
| Save/load sacred | New ctx fields serialize; existing saves migrate (equipped weapons classify into their set, other set starts empty) |
| ctx-first | The holstered set is a declared `GameContext` field — no runtime attachment |
| Guide contract | Controls + Ground Gear sections reviewed; the toggle gets its entry |
| Doc 50 SETTLED 6 | The standard's board is the drift alarm for this landing — bars re-ruled in the same commit that lands the mechanic (benchmark-revision clause) |

## Data model

- **Set classification table** (pure, in `ground_equipment`):
  `damage_type == "melee"` → melee set; `kinetic | energy | plasma |
  explosive` → ranged set. Every current and future weapon resolves
  through the table — no per-spec flag.
- **GameContext fields** (declared, serialized):
  - `equipped_ground_weapons: list[GroundWeaponInstance]` — unchanged
    meaning: the ACTIVE set. All combat rules keep reading exactly
    this list — zero rules-module churn.
  - NEW `holstered_ground_weapons: list[GroundWeaponInstance]` — the
    other set, moved wholesale on swap (magazines ride the
    instances).
- **Slot law**: each set independently obeys today's occupancy rule —
  Σ hands ≤ 2 per set (one 2H or up to two 1H). A set may be EMPTY
  (toggling to an empty set = fists; player's choice, uniform
  mechanism — SETTLED 1).
- **The swap** (`ground_equipment.exchange_weapon_sets(ctx)` or a
  combat-action helper): exchange the two lists, refresh equipment
  state, **cost 1 AP** in combat, free out of combat. One action,
  whole set ↔ whole set.
- **Pack law**: holstered set members are equipment — never stored,
  never counted against `expedition_capacity`.

## Domain changes

- `combat/_loop.py`: new action id (working name `SWAP_SETS`) in the
  dispatch — `rules-hook` shaped like RELOAD (ground-only; space
  combat logs "unavailable"). Key = **X** (SETTLED 1; collision check
  already discharged at refine time: clear of the action table
  `s/w/f/r/c/v/d` + tab/backslash + number keys, clear of
  `MOVE_KEYS` incl. VIM diagonals, unused in the main loop — the only
  other X is modal-scoped inside the faction viewer).
- `game_context.py`: the holstered field.
- `saveload_ground.py`: serialize both lists; **migration** for
  existing saves (classify equipped 2-slot contents into their set;
  holstered starts empty).
- `ground_equipment.py`: classification table, set-occupancy
  validation on equip, `exchange_weapon_sets`.
- Character screen + armory terminal: set-aware equipment UI (equip
  into ranged/melee sets; the C-screen mid-combat per-weapon swap
  REMAINS at 1 AP per change for set *editing* — SETTLED 1).
- HUD: active-set slots as today, plus a compact holstered-set
  indicator (design at build).
- Stances (tests/balance): `toggle_sets` policy rung via the REAL
  dispatch action — the probe's simulated toggle becomes honest.

## Phases

- [ ] 1. **Data model + swap core** — classification table, ctx
  field, serialization + migration, `exchange_weapon_sets`, slot-law
  validation. Tests: round-trip incl. migrated saves, classification
  exhaustiveness over the catalog, magazine persistence, empty-set
  toggle, occupancy law.
- [ ] 2. **The combat verb** — dispatch action + key (6a law:
  table + VIM + main-loop helpers), 1-AP cost, refresh, HUD
  indicator, input-path tests, guide Controls entry.
- [ ] 3. **Equipment UI** — armory/character screen set-aware equip;
  pack relief (holstered never counted); UI tests.
- [ ] 4. **Standard re-rule** — the doc-50 board re-measured under
  the new world (SETTLED 6 benchmark revision, bars re-ruled in the
  same commit), `toggle_sets` stance, candidate protected row: the
  railgun+blade full-clear matchup.
- [ ] 5. **Teaching** — tutorial beat + guide Ground Gear wording
  (prose-gated: user wording before data strings land).

Each phase gets its Implementation brief at its own refine time.

## SETTLED 1 (2026-09-25, user) — the core rulings (open questions 1/2/3)

- **The swap key is X.** Verified collision-free at refine time (the
  draft's "verified at build time" caveat is discharged): free in the
  combat action table (`s/w/f/r/c/v/d` + tab/backslash + number keys),
  free in `MOVE_KEYS` (VIM diagonals `b/n/y/u`, `hjkl`, arrows,
  numpad), unused in the main loop. The only other X in the codebase
  is modal-scoped (faction viewer transponder-log delete) — no
  collision.
- **Toggling to an EMPTY holstered set is allowed** — the player
  fights with fists until toggling back. Uniform mechanism: the toggle
  always fires; no refusal special case.
- **The C-screen mid-combat per-weapon swap STAYS** alongside the new
  whole-set toggle, at its current 1 AP per change. X flips whole
  sets; C is for surgical mid-combat edits (swap one weapon,
  rearrange a set).

### Phase 1 PLAYTEST (data layer — the save/load sniff)

1. **Regression**: continue the current save → active loadout and
   combat are IDENTICAL (F volley, R reload, number-key weapon
   toggles all as before; phase 1 changes no rule the fight reads).
2. **Migration — mixed pair**: a save with one 1H ranged + one 1H
   melee equipped → continue → the C screen's equipped list shows
   only slot 0's class; the other weapon is holstered (verify via
   the dev inspector, item 4); F-volley fires exactly the active set.
3. **Migration — same-class pair**: two 1H ranged equipped → both
   stay active, melee set empty; nothing observable changes.
4. **Dev inspector**: with SPACEHACK_DEV on, the dev dump prints both
   sets with per-instance magazine + quality; magazines match their
   pre-save values.
5. **Save/load sniff on migrated state**: after items 2-3, save →
   quit → continue → sets, magazines, and quality identical.
6. **Guide diff: NONE** — nothing player-facing lands in phase 1
   (the holstered field has no UI until phase 2's HUD indicator).

### Phase 1 Implementation brief (PROPOSED 2026-09-25 — SETTLED 1;
### ready for /implement-phase 51.1 on approval)

**Scope (files / hook points):**

- **Classification table** (`ground_equipment.py`): pure
  `weapon_set(weapon_id) -> "ranged" | "melee"` — resolves
  `find_ground_weapon(...).damage_type`; `"melee"` → melee,
  `"kinetic" | "energy" | "plasma" | "explosive"` → ranged. The
  table is a module-level dict of the five damage types — every
  current and future catalog entry (including `monsters.py`)
  resolves; an unknown type raises (exhaustiveness is load-bearing).
- **Set validation** (`ground_equipment.py`): pure
  `can_fit_weapon_set(instances, new_weapon_id) -> bool` — Σ hands ≤ 2
  within the set AND class purity (the set's class is the class of
  its first member; a different-class weapon never fits). Mirrors
  the existing `can_fit_weapons` occupancy arithmetic
  (`weapon_slot_occupancy` + `weapon_hands`); the OLD function stays
  untouched — it keeps serving the unchanged equip paths until
  phase 3 rebuilds them set-aware.
- **ctx field** (`game_context.py`, beside `equipped_ground_weapons`
  at :337): NEW `holstered_ground_weapons:
  list[ground_equipment_module.GroundWeaponInstance]`, default
  `[]`. Declared field, no runtime attachment (ratchet law).
- **The swap** (`ground_equipment.py`):
  `exchange_weapon_sets(ctx) -> None` — swaps the two lists
  wholesale (magazines and quality ride the instances untouched —
  no reseed, no copy). Works for empty on either side (SETTLED 1
  fists floor). Double-toggle is the identity. AP cost and
  active-weapon-flag reset are combat-layer concerns — they land
  with phase 2's dispatch action, NOT here.
- **Serialization + migration** (`saveload_ground.py`):
  `"holstered_ground_weapons": _d(ctx.holstered_ground_weapons)`
  beside the existing equipped entry (:42); parse via the existing
  `parse_weapon_instance`. **Missing key = pre-doc-51 save →
  migration**: classify each equipped instance by its set; the
  active set after migration is the set of the ORIGINAL slot 0
  (preserves today's volley order — the first weapon stays
  fire-able); all other-class members move to the holstered set.
  Same-class loadouts therefore migrate with zero behavior change;
  mixed pairs split. Present key → load verbatim, no migration.
- **Dev inspector** (`dev_mode.py`): SPACEHACK_DEV-gated log dump of
  both sets (weapon id, loaded_ammo, quality per instance) on the
  existing dev-grant surface — the playtest's only visibility into
  the holstered field before phase 2's HUD. Read the existing
  ground-loadout grant's shape at audit time; extend, don't fork.

**Build order:** classification table (+ exhaustiveness test) → ctx
field → set validation (+ tests) → `exchange_weapon_sets` (+ tests)
→ serialization + migration (+ round-trip and migration tests) → dev
inspector → full `make check`.

**Binding rulings:** SETTLED 1 (empty-set toggle allowed — fists
floor; the swap always fires). The pack law is STRUCTURAL here:
holstered members live in their own ctx field, never in a stored
list, so `expedition_capacity` never sees them by construction — no
capacity-code change in this phase; the behavioral pin (holstered
weapons surviving pack-full states) lands with phase 3's flows.
Migration's active-set rule (slot 0's class) is proposed in this
brief — rule it with the brief's approval. Existing combat rules
read `equipped_ground_weapons` exactly as today — ZERO rules-module
edits in this phase; if the build reaches for one, stop: design
question, not a fix.

**Required tests:** classification exhaustiveness over the whole
catalog (all five damage types, monsters included; unknown type
raises); set validation — 2×1H fits, 1×2H fits, 2H+anything
refused, 3×1H refused, class-mix refused; exchange — wholesale
swap, magazine + quality persistence through the swap, empty↔full
both directions, double-toggle identity; save round-trip — fresh
holstered contents round-trip exactly; migration — same-class pair
stays active with other set empty, mixed pair splits with active =
slot 0's class, empty equipped → both empty, no-key save never
crashes. Every new pure function carries its test in the same
commit (pure-function contract). Existing suites stay green.

**Stop point:** no combat verb, key binding, HUD indicator, or
active-flag reset (phase 2); no equipment-UI changes — armory,
character screen, `install_weapon`/`swap_weapon_from_expedition`
and friends untouched (phase 3); no balance/board work (phase 4);
no tutorial or guide edits (phase 5 — nothing player-facing, guide
diff recorded as NONE above).

**Playtest checkpoint:** the Phase 1 PLAYTEST list above — its
center is item 2 (the mixed-pair migration); the phase ticks only
with all six items passing.

## Open questions

1. **Tutorial teaching**: does the tutorial's armory beat teach the
   toggle (buy 2 + 2?), and with what wording? (Prose-gated; phase 5.)
2. **Balance blast radius**: landing this re-rules the doc-50 board
   (phase 4). Any bar the user wants held IMMUNE to re-rule (e.g.,
   the space rows)?
