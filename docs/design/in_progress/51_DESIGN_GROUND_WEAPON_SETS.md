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
| Save/load sacred | New ctx fields serialize; existing saves migrate (equipped weapons classify into their set — same-class loadouts unchanged, mixed pairs split per the phase 1 brief) |
| ctx-first | The holstered set is a declared `GameContext` field — no runtime attachment |
| Guide contract | Controls + Ground Gear sections reviewed; the toggle gets its entry |
| Doc 50 SETTLED 6 | The standard's board is the drift alarm for this landing — bars re-ruled in the same commit that lands the mechanic (benchmark-revision clause) |

## Data model

- **Set classification table** (pure, in NEW sibling module
  `ground_weapon_sets.py` — `ground_equipment.py` sits at 987/1000
  lines against the ratchet, so the new code gets its own home):
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
- **The swap** (`ground_weapon_sets.exchange_weapon_sets(equipped,
  holstered)` — in-place list swap, lists not ctx, per
  ground_equipment's take-the-collections convention): one action,
  whole set ↔ whole set, **cost 1 AP** in combat, free out of
  combat. The equipment-state refresh (active-weapon flags) is the
  PHASE-2 verb's job, not the data-layer exchange's.
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
  existing saves (classify equipped contents into their set;
  same-class loadouts unchanged, mixed pairs split — active = slot
  0's class; ruled with the phase 1 brief).
- `ground_weapon_sets.py` (NEW sibling — `ground_equipment.py` is
  987/1000 against the ratchet): classification table, set
  validation, `exchange_weapon_sets`, and the migration partition
  (pure split-by-class helper with direct tests).
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
  collision. Shift+X is the dev XP grant (`game_loop.py:401`) —
  also no collision (dev grants never run in combat), but phase
  2's input-path tests pin plain-x vs shift-x so it stays
  deliberate.
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
   the dev inspector, item 4); F-volley fires exactly the active
   set. The displaced weapon shows in NO UI until phase 2's HUD
   indicator — expected, not lost.
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

- **Classification table** (`ground_weapon_sets.py` — NEW sibling
  module; `ground_equipment.py` is 987/1000 against the
  architecture ratchet and cannot absorb the ~50 new lines): pure
  `weapon_set(weapon_id) -> "ranged" | "melee"` — resolves
  `find_ground_weapon(...).damage_type`; `"melee"` → melee,
  `"kinetic" | "energy" | "plasma" | "explosive"` → ranged. The
  table is a module-level dict of the five damage types — every
  current and future catalog entry (including `monsters.py`)
  resolves; an unknown type raises (exhaustiveness is load-bearing).
- **Set validation** (`ground_weapon_sets.py`): pure
  `can_fit_weapon_set(instances, new_weapon_id) -> bool` — Σ hands ≤ 2
  within the set AND class purity (the set's class is the class of
  its first member; an EMPTY set is class-agnostic — any class
  fits, occupancy counts from zero). Mirrors
  the existing `can_fit_weapons` occupancy arithmetic
  (`weapon_slot_occupancy` + `weapon_hands`); the OLD function stays
  untouched — it keeps serving the unchanged equip paths until
  phase 3 rebuilds them set-aware.
- **ctx field** (`game_context.py`, beside `equipped_ground_weapons`
  at :337): NEW `holstered_ground_weapons:
  list[ground_equipment_module.GroundWeaponInstance]`, default
  `[]`. Declared field, no runtime attachment (ratchet law).
- **The swap** (`ground_weapon_sets.py`):
  `exchange_weapon_sets(equipped, holstered)` — swaps the two
  lists in place (magazines and quality ride the instances
  untouched — no reseed, no copy; lists not ctx, matching
  ground_equipment's convention so the module stays
  ctx-free and directly testable). Works for empty on either side
  (SETTLED 1 fists floor). Double-toggle is the identity. AP cost
  and active-weapon-flag reset are combat-layer concerns — they
  land with phase 2's dispatch action, NOT here.
- **Serialization + migration** (`saveload_ground.py`):
  `"holstered_ground_weapons": _d(ctx.holstered_ground_weapons)`
  beside the existing equipped entry (:42); parse via the existing
  `parse_weapon_instance`. **Missing key = pre-doc-51 save →
  migration** (via the pure partition helper in
  `ground_weapon_sets.py`, not inline in the restore): classify
  each equipped instance by its set; the active set after
  migration is the set of the ORIGINAL slot 0 (slot 0 stays
  fire-able; where slot 1 was the other class its volley
  contribution moves to the holstered set — the accepted cost of
  the split). Same-class loadouts migrate with zero behavior
  change; mixed pairs split; real pre-51 saves are mostly empty or
  single-class (no starter loadout exists — new games begin with
  `equipped_ground_weapons=[]`), so no-ops dominate. Present key →
  load verbatim, no migration.
- **Dev inspector** (handler body in `dev_mode.py`, 695 lines —
  room to spare): SPACEHACK_DEV-gated log dump of both sets
  (weapon id, loaded_ammo, quality per instance), wired as an entry
  in `_DEV_SHIFT_KEYS` (`game_loop.py:400-417` — the ON-DEMAND dev
  surface; the existing `apply_dev_ground_loadout` grant at
  `dev_mode.py:269` is a New-Game-only hook and never runs on a
  continued save). Pick the free Shift-key at audit time from the
  live table. `game_loop.py` is 996/1000 — it gains ONLY the table
  entry, the body lives in `dev_mode.py`. This dump is the
  playtest's only visibility into the holstered field before
  phase 2's HUD.

**Build order:** new module `ground_weapon_sets.py` with the
classification table (+ exhaustiveness test) → ctx field → set
validation (+ tests) → `exchange_weapon_sets` (+ tests) →
serialization + migration via the partition helper (+ round-trip
and migration tests) → dev inspector → full `make check`.

**Binding rulings:** SETTLED 1 (empty-set toggle allowed — fists
floor; the swap always fires). The pack law is STRUCTURAL here:
holstered members live in their own ctx field, never in a stored
list, so `expedition_capacity` never sees them by construction — no
capacity-code change in this phase; the behavioral pin (holstered
weapons surviving pack-full states) lands with phase 3's flows.
Migration's active-set rule (slot 0's class) is proposed in this
brief — rule it with the brief's approval. (Mid-combat saves are
structurally impossible — `save_game` is reachable only from the
main-loop ESC path, and combat's only exit is window-close QUIT —
so migration can never touch a live fight.) Existing combat rules
read `equipped_ground_weapons` exactly as today — ZERO rules-module
edits in this phase; if the build reaches for one, stop: design
question, not a fix.

**Required tests:** classification exhaustiveness over the whole
catalog (all five damage types, monsters included; unknown type
raises); set validation — 2×1H fits, 1×2H fits, 2H+anything
refused, 3×1H refused, class-mix refused, EMPTY set accepts any
class (occupancy counts from zero); exchange — wholesale
swap, magazine + quality persistence through the swap, empty↔full
both directions, double-toggle identity; save round-trip — fresh
holstered contents round-trip exactly; migration — same-class pair
stays active with other set empty, mixed pair splits with active =
slot 0's class, empty equipped → both empty, no-key save never
crashes, and migration payloads explicitly STRIP
`holstered_ground_weapons` so they stay true pre-51 shapes (a
current-`save_game` payload would carry the key and silently skip
the legacy path). Every new pure function carries its test in the same
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

### Phase 1 pre-implementation audit (2026-09-25, build session)

**1. Existing modules to reuse** (all anchors verified on the tree):

- `ground_equipment.GroundWeaponInstance` (frozen; weapon_id /
  loaded_ammo / quality) — the holstered set holds exactly these;
  magazines + quality ride instances with zero new per-instance code.
- `ground_equipment.can_fit_weapons` / `weapon_hands` /
  `weapon_slot_occupancy` / `WEAPON_SLOT_COUNT` — the occupancy
  arithmetic `can_fit_weapon_set` reuses (calls `can_fit_weapons`
  rather than re-deriving Σ hands).
- `saveload_ground._parse_equipped_ground_weapons` +
  `ground_equipment.parse_weapon_instance` — the holstered key parses
  through the same helper (legacy strings, clamping, unknown-id drops
  all inherited).
- `data.ground_weapons`: `find_ground_weapon` resolves membership
  input; `list_ground_weapons()` (auto-discovery incl. `monsters.py`)
  enumerates the exhaustiveness test. All five damage types are live
  in the catalog (melee/kinetic/energy/plasma/explosive; 1H and 2H
  exist in both classes — e.g. kinetic_pistol/railgun ranged,
  combat_knife/mono_blade melee).
- `dev_mode.log_rumor_routing` (:505) — the log-dump model for the
  Shift+W sets dump; `dev_mode` at 695 lines has room for the body +
  a tiny formatter.
- `_DEV_SHIFT_KEYS` (game_loop.py:400) + the `_is_shift_press`
  matcher factory (input_helpers.py:291) — the on-demand dev surface.

**2. Duplication hotspots:** (a) migration logic inline in
`_restore_ground_fields` — must be the pure `partition_weapon_sets`
helper in the new module (brief mandates); (b) `can_fit_weapon_set`
re-deriving hand occupancy — reuse `can_fit_weapons`; (c) a second
instance-list parse loop in saveload_ground — reuse
`_parse_equipped_ground_weapons`; (d) bespoke per-instance dump
formatting — one tiny `_describe` helper in dev_mode (name + ammo +
quality; nothing shared does all three).

**3. DRY strategy:** every new pure function lives in
`ground_weapon_sets.py`; `game_context.py` gains only the declared
field; `saveload_ground.py` gains only the key + the migration
branch; `ground_equipment.py` is NOT touched (987/1000 preserved);
`game_loop.py` gains only a module-level import + the table entry
(996 → 998/1000 — see rulings below).

**Audit rulings (build-shape discoveries):**

- **The dev dispatch body lives in dev_mode as an async
  state-taking adapter.** game_loop is 996/1000: a conventional
  7-line handler (+ table entry) = 1003 — over. Instead dev_mode
  exports `dump_ground_weapon_sets(state)` (async, thin wrapper over
  the sync, testable `log_ground_weapon_sets(ctx)`), and game_loop
  adds `from .dev_mode import dump_ground_weapon_sets` + one table
  entry = 998. Cycle-safe: dev_mode's module-level imports never
  reach game_loop (verified). The sync ctx dump follows the
  `log_rumor_routing` shape so tests call it directly.
- **The Shift key is W** (Shift+W). Live table: X/T/S/R/D/L/G/K/J/
  B/N/M/Y/V/P/C + Shift+O (menu-scoped). No `'W'`/`K_w` binding
  exists anywhere in src (verified by grep) and W is not in
  MOVE_KEYS — mnemonic: weapon sets.
- **Loader tolerance:** a PRESENT holstered key loads verbatim — the
  restore path never enforces class purity (validation guards
  mutations, not restoration). Keeps mixed-pair round-trips
  (test seeds 53/62) green and avoids destructive save "repairs".
- **Existing test seed 61** (`legacy_string_weapons_migrate_to_full_
  magazines`) saves via current `save_game`, so its payload will
  carry the holstered key and skip the legacy path — the brief's
  flagged trap, live. Updated in-commit: payload explicitly pops
  `holstered_ground_weapons`; assertions extended to the post-51
  partition (pistol active at full magazine, knife holstered). The
  strings→full-magazines intent is preserved.

## Open questions

1. **Tutorial teaching**: does the tutorial's armory beat teach the
   toggle (buy 2 + 2?), and with what wording? (Prose-gated; phase 5.)
2. **Balance blast radius**: landing this re-rules the doc-50 board
   (phase 4). Any bar the user wants held IMMUNE to re-rule (e.g.,
   the space rows)?
