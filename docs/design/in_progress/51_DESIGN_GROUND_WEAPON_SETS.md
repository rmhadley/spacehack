# DESIGN: Ground Weapon Sets — 4 slots, one-toggle swap

**Status: BUILDING (2026-09-25) — phases 1-2 LANDED + PLAYTEST
PASSED (phase 2 seven/seven incl. the X-on-explore-HUDs mid-playtest
ruling); phase 3 SETTLED 3 + brief PROPOSED — awaiting approval.
Core rulings SETTLED 1–3; open questions 1–2 (tutorial wording,
board immunity) parked at their phases.**

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

- [x] 1. **Data model + swap core** — LANDED af2c9388, PLAYTEST
  PASSED 2026-09-25 (six/six, no mid-playtest rulings).
  Classification table, ctx
  field, serialization + migration, `exchange_weapon_sets`, slot-law
  validation. Tests: round-trip incl. migrated saves, classification
  exhaustiveness over the catalog, magazine persistence, empty-set
  toggle, occupancy law.
- [x] 2. **The combat verb** — LANDED 488f5cb9..1b999796 (refactor
  + verb + free X + HUD + dev grant + guide), PLAYTEST PASSED
  2026-09-25 (seven/seven) incl. ONE mid-playtest ruling (X on the
  explore HUDs, a8fdd94b). Dispatch action + key (6a law:
  table + VIM + main-loop helpers), 1-AP cost, refresh, HUD
  indicator, input-path tests, guide Controls entry.
- [ ] 3. **Equipment UI** — armory/character screen set-aware equip;
  pack relief (holstered never counted); tinker-kit reach must cover
  holstered members (`tinker.py:141` `eligible_targets` enumerates
  only the equipped list today — reviewer catch, phase 1 review); UI
  tests.
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

## SETTLED 2 (2026-09-25, user) — phase 2 rulings

- **X fires EVERYWHERE in phase 2**, not combat-only: a 1-AP
  mid-turn action in ground combat (RELOAD-shaped rules hook) and
  FREE out of combat in the main loop (every non-space mode). The
  user chose this over the combat-only recommendation. Consequence
  accepted with it: game_loop.py (998/1000) cannot absorb the
  main-loop handler, so the phase pays its ratchet debt in-commit —
  the self-contained dev shift-key block (~88 lines: the `_dev_*`
  handlers + `_DEV_SHIFT_KEYS` + `_handle_dev_shift_keys`) extracts
  to a sibling module first, as its own refactor commit.
- **Playtest seeding = the New-Game dev grant**:
  `apply_dev_ground_loadout` seats the strongest RANGED weapon
  active + the strongest MELEE weapon holstered — every fresh dev
  game starts with a real two-set loadout.
- **HUD indicator = one dim names row**: `HOLSTER  <names>` under
  the WEAPONS block (names joined, truncated to the panel width),
  painted dim, HIDDEN when the holstered set is empty — the fists
  floor needs no advertisement.

### Phase 1 PLAYTEST (data layer — the save/load sniff)

**PASSED 2026-09-25 — all six items, no failures, no mid-playtest
rulings.** The mixed-pair migration (item 2) split as ruled: slot
0's class active, displaced weapon visible only via the Shift+W
dev dump.

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

### Phase 2 Implementation brief (PROPOSED 2026-09-25 — SETTLED 2;
### ready for /implement-phase 51.2 on approval)

**Scope (files / hook points; all sizes verified on the tree):**

- **game_loop refactor FIRST** (own commit, before any X wiring):
  extract the dev shift-key block — the 16 `_dev_*` async handlers
  (`_dev_city_teleport` :264-274 + the fifteen at :300-397),
  `_DEV_SHIFT_KEYS` (:401), `_handle_dev_shift_keys` (:422), PLUS
  `_is_dev` (:245) and `_reveal_all_fog` (:251, only
  `_dev_reveal_fog` reads it) — into a new sibling (working name
  `game_loop_dev.py`); game_loop re-imports `_is_dev` +
  `_handle_dev_shift_keys` so the public surface is unchanged.
  Import direction ONE-WAY (game_loop → game_loop_dev): `_is_dev`
  moves with the block or the module-level table cycles (ADVISE
  fold 4). The extraction commit also PRUNES game_loop's
  now-unused imports (Ruff F401): `_add_xp`, the shift matchers
  minus `_is_shift_o_press` (stays — quest handler :147),
  `dump_ground_weapon_sets` (ADVISE fold 5). True block ≈165
  lines → game_loop lands ≈840/1000 (the "~88/~910" figures in
  SETTLED 2 undercounted — ADVISE fold 6, safe direction). If a
  handler reference fights the extraction at build time, stop and
  re-scope in this doc — do not grow game_loop instead.
- **Combat verb** (`combat/_loop.py` 649/1000): `"x": "SWAP_SETS"`
  in `_key_action`'s action table (:77); `_dispatch_combat_action`
  routes SWAP_SETS through a NEW module-level
  `_run_rules_hook(ctx, rules, hook_name, unavailable_line)` with
  RELOAD refactored onto the same runner (:557-562 today) — a
  sixth inline elif pushes the 35-line dispatcher past the 40-line
  ratchet (ADVISE fold 2) and the twin branches deduplicate on the
  same extraction. Hook present on ground rules, absent in space,
  which logs `"Weapon swap is unavailable here."`.
- **The rules hook** (`combat/_rules_ground.py` 958/1000, ~13-line
  hook → lands ≈971): `async def swap_weapon_sets(ctx) -> bool`
  (async like `reload_weapon` — the dispatch awaits it; ADVISE
  fold 8) — refuse when `player_ap < 1` (`"Not enough AP to swap
  weapon sets."`, no mutation); otherwise call
  `ground_weapon_sets.exchange_weapon_sets(ctx.equipped_ground_weapons,
  ctx.holstered_ground_weapons)`, reset
  `_state.active_weapon_list = [True] * len(player_weapons(ctx))`
  — the fists-fallback list, combat-start semantics (:257 + :275).
  `len(equipped)` breaks the empty-set swap: FIRE's
  `_fire_slot_indexes(["fists"], [])` returns `[]` and the player
  cannot attack at all (ADVISE fold 1 — the SETTLED-1 fists
  floor). Charge 1 AP, log `"Weapon sets swapped."` (same outcome
  line on the free out-of-combat path — states, never teaches).
  Empty active set needs no special case: `player_weapons`
  already falls back to `["fists"]` (:338-340).
- **Free out-of-combat X** (`input_helpers.py` + `game_loop.py`):
  NEW `_is_x_press` matcher — keydown, key_name `'x'`, **shift
  excluded** (key names are lowercase-normalized; without the
  exclusion it would collide with the dev XP grant, which owns
  Shift+X in the main loop). Handler in `_handle_menu_event`
  (game_loop:431) gated to `state.current_mode != 'space'`: the
  free exchange + the shared log line. The branch is a 2-line
  delegation to a module-level `_swap_weapon_sets_explore(state)`
  helper — `_handle_menu_event` sits at 38 lines and an inline
  branch breaches the 40-line ratchet (ADVISE fold 3). No flag
  work — combat state is per-fight and derives flags fresh on
  start.
- **HUD** (`combat/_ground_render.py` 441/1000): after the weapons
  loop in `_render_weapons_panel` (:275) — when
  `ctx.holstered_ground_weapons` is non-empty, one dim row
  `HOLSTER  <display names joined>`, truncated to HUD_TEXT_MAX,
  using `_COLOR_GROUND_WEAPON_DIM`. X also joins the actions legend
  in `_render_actions_panel` (:430): `("[x]", "Swap")`.
- **Dev grant** (`dev_mode.py` 726/1000): `_dev_ground_loadout`
  returns the strongest-ranged instance + strongest-melee instance
  (class-filtered picks over `list_ground_weapons()` via
  `ground_weapon_sets.weapon_set`, not re-derived damage strings);
  `apply_dev_ground_loadout` seats them active + holstered; the
  `[DEV MODE]` log line names both sets. Pack + strength-30 bump
  stay (pack stays 6); the strongest melee riding holstered AND in
  the pack is harmless dev duplication. Existing pin
  `test_dev_mode.py:265-295` (equipped `[rocket_launcher]`, pack
  list, log line, strength) re-shapes in-commit; its SimpleNamespace
  ctx gains the holstered field (ADVISE fold 7).
  `_best_ground_weapon` is DELETED (replaced by the class-filtered
  `_best_set_weapon`; zero dangling references, picks identical —
  build-session call under self-audit dead-code rule, REVIEW minor 4;
  the ranged max is still `rocket_launcher`, melee max `mono_blade`).
- **Guide** (`data/guide/__init__.py`): Controls & Keybindings, in
  the Combat list after the R line — exact wording (proposed, red-
  line at approval): `- X: swap weapon sets (free while exploring,
  1 AP in combat)`. Lands in its own commit per the prose gate.

**Build order:** game_loop refactor commit → combat verb (table +
hook + dispatch + verb tests) → free out-of-combat X (matcher +
menu handler + input-path pins) → HUD row + actions legend → dev
grant → full `make check` → guide entry (own commit, settled
wording).

**Binding rulings:** SETTLED 1 (empty-set toggle = fists floor, no
refusal special case) and SETTLED 2 (X everywhere; New-Game dev
seed; HOLSTER names row). Derived rulings: mid-turn action like
FIRE — NEVER turn-ending (doc-50 measured: a turn-forfeit toggle
inverted the strength ladder); active flags reset all-True on swap;
0-AP refuses; space combat logs unavailable, space navigation
leaves X unmapped; the swap is SILENT (no noise event — a harness
adjustment, not a discharge); in combat Shift+X ALSO swaps — the
combat table is shift-blind today (Shift+R is already RELOAD) and
uniformity beats a special case, while the main loop's plain-x
matcher excludes shift (dev XP owns Shift+X there) — both pinned
by input-path tests per SETTLED 1.

**Required tests:** input-path (6a law) — plain-x in combat →
SWAP_SETS; Shift+x in combat → SWAP_SETS (the shift-blind pin);
main-loop `_is_x_press` false under shift (dev grant keeps
Shift+X); `x` absent from `MOVE_KEYS`/VIM diagonals (regression
pin); space rules lack the hook → unavailable log. Verb — 1-AP
charge, 0-AP refusal leaves sets + AP unchanged, wholesale
exchange, flags reset all-True, empty-active → fists volley path,
double-swap identity mid-fight, magazines persist through
swap→fire. Out of combat — dungeon-mode free swap (no AP concept),
space-mode no-op. HUD — HOLSTER row present with names when
populated, hidden when empty. Dev grant — strongest-ranged active +
strongest-melee holstered. Guide — the Controls entry present.
Every new pure/mutation-wrapper function carries its test in the
same commit.

**Stop point:** no equipment-UI changes (C screen and armory stay
per-weapon until phase 3 — including no holstered visibility in
the C screen), no pack-capacity work, no balance/board/`toggle_sets`
stance work (phase 4), no tutorial or other guide edits (phase 5).

### Phase 2 ADVISE pass (2026-09-25, pre-build — brief approved by
### the /implement-phase 51.2 invocation; this pass is the missing
### every-brief advisor round)

Verdict: **ADVICE — 3 blocking, 5 minor; no ruling changes.** All
eight folded into the brief above. Blockers: (1) the flag-reset
formula must count `player_weapons(ctx)` (fists fallback), not the
raw equipped list — else the empty-active swap kills FIRE entirely,
breaking the SETTLED-1 fists floor; (2) a sixth inline dispatch
elif breaches the 40-line ratchet on the 35-line
`_dispatch_combat_action` — extract the `_run_rules_hook` runner;
(3) `_handle_menu_event` (38 lines) takes the X branch as a 2-line
delegation only. Minors: `_is_dev` + `_reveal_all_fog` move with
the extraction (module-level table would cycle otherwise);
post-move import pruning (Ruff F401); SETTLED 2's "~88 lines/~910"
figures undercounted (true ≈165 lines → ≈840); the
`test_dev_mode.py:265-295` grant pin re-shapes in-commit; the
rules hook is async like `reload_weapon`. The pass also VERIFIED:
import graph acyclic with the one-way direction; no test or caller
references any moved symbol; `_handle_non_movement_event`
reachable in all modes with dev-keys-first ordering keeping
Shift+X dev-owned; plain-x unused everywhere today (faction-viewer
X is modal-scoped); combat table shift-blind (key names
lowercase-normalized, no x alias); dispatch can never fire with
`_state` None (`rules.init` contract); HUD budget absorbs the
HOLSTER row (worst case ends ACTIONS ≈row 48 of 60).

### Phase 2 pre-implementation audit (2026-09-25, build session)

**1. Existing modules to reuse** (anchors verified on the tree at
911fc181):

- `ground_weapon_sets.exchange_weapon_sets` + `weapon_set` (phase
  1) — the verb body; the dev grant's class-filtered picks resolve
  through `weapon_set`, never re-derived damage strings.
- `combat/_loop.py` RELOAD dispatch (:557-562) — the rules-hook
  shape the `_run_rules_hook` runner generalizes (RELOAD moves onto
  it in the same commit; the 6a action-table entry at :77).
- `_rules_ground` init semantics (:257 `player_weapons(ctx)` →
  :275 `[True] * len(_weapons)`) — the swap's flag reset reuses the
  same expression; `refresh_equipment_state` (:354) is the
  precedent for flag maintenance after equipment changes.
- `input_helpers` matcher family (`_is_c_press` shape + the
  `_is_shift_press` factory :291) — `_is_x_press` mirrors `_is_c_press`
  plus `not pygame_engine.has_shift(event)`.
- `_ground_render` panel idioms: `_render_weapons_panel`'s return-y
  flow, `display_name` + `[:HUD_TEXT_MAX]` truncation, and
  `_COLOR_GROUND_WEAPON_DIM` for the HOLSTER row; the actions
  legend pairs in `_render_actions_panel` (:435-440).
- `dev_mode.apply_dev_ground_loadout` (:269) +
  `_best_ground_weapon` (:247, stays = strongest-ranged) — the
  grant re-shape site.

**2. Duplication hotspots:** (a) the swap outcome line
`"Weapon sets swapped."` written at two call sites (combat hook +
explore helper) — drift risk against the UI-text-economy rule;
(b) the dev grant re-deriving class filtering — folded to
`weapon_set` (ADVISE); (c) the HUD row re-deriving name-join +
truncation instead of the panel idiom; (d) RELOAD and SWAP_SETS
twin dispatch branches — the runner IS the dedup (ADVISE fold 2).

**3. DRY strategy:** (a) single-source the outcome line inside
`ground_weapon_sets` as a lists+log mutation-wrapper
(`exchange_weapon_sets` stays pure; the wrapper stays ctx-free —
lists + log in, no ctx), both call sites route through it;
(b) `weapon_set` for every class question; (c) one
`_holster_names_row` helper inside `_ground_render` building the
joined, truncated label; (d) the shared `_run_rules_hook` runner.
Ratchet posture: game_loop ≈840 after the refactor (X branch +
helper fit trivially); `_loop.py` ≈660; `_rules_ground.py` ≈971;
`_ground_render.py` ≈455; `dev_mode.py` ≈735 — all under 1000,
every touched function ≤40 (the two 40-line-wall sites handled per
the folds).

**Build-session rulings:** the outcome-line wrapper (3a) hosts in
`ground_weapon_sets.py` taking `(equipped, holstered, log)` —
ctx-free convention preserved, testable directly. The
`_swap_weapon_sets_explore` helper lives at game_loop module level
(post-refactor budget); its gate reads
`_is_x_press(event) and state.current_mode != 'space'` at the
2-line branch so the mode gate is visible at the call site.

**Build record (2026-09-25):** REVIEW verdict **APPROVE, zero
blocking** (4 minors: the dev-grant log line re-derivation — fixed
to read the seated instances; `_handle_menu_event` landed at
EXACTLY 40 lines — the next key added there forces an extraction;
the holster row's getattr read-tolerance — kept, matches
`_reserve_count`'s file idiom, no declared-field violation; the
`_best_ground_weapon` deletion vs the brief's "keeps" wording —
doc corrected here). The reviewer AST-verified the refactor commit
as a verbatim one-way move, simulated the ADVISE fold-1 bug to
prove the fists-floor pin bites, and mapped all 17 brief-required
tests present.

### Phase 2 PLAYTEST (the verb)

**Mid-playtest ruling (2026-09-25, user): "X needs to go on the huds
too"** — the explore HUDs' help block gains `[X] Swap Sets`
(`hud._render_city_help_lines` shared list: city AND dungeon; the
space list stays clean — X is gated off there, and the space list is
pinned never to advertise it). Landed as its own commit after a
focused REVIEW (APPROVE, 4 minors applied: the negative space-list
pin via the extracted `_SPACE_HELP_LINES` constant; ruling recorded
here; explicit-path staging past the tmp_png intent-to-adds). Guide
diff UNCHANGED by the ruling — the Controls entry already covers X.
hud.py 997/1000 after it (headroom warning: the next addition there
forces the split; natural seam = the combat-HUD half, and the
`_render_help_lines`/`_render_action_pairs` twin pair is the backlog
extraction when it comes).

1. **Dev seed**: fresh game with SPACEHACK_DEV → dev log names both
   sets (strongest ranged active + strongest melee holstered).
2. **In combat**: X swaps the WHOLE set — HUD weapon list flips,
   HOLSTER row flips with it, 1 AP charged, turn continues (enemies
   do not move); F fires the new set.
3. **Fists floor**: X to the melee set, C-store both melee weapons,
   X again → active = ranged, holstered empty, HOLSTER row gone.
   (Reaching an empty ACTIVE set via C-store of everything is the
   phase-3 UI's job; the floor is pinned by tests.)
4. **0-AP refusal**: spend to 0 AP → X → refusal line, sets
   unchanged.
5. **Out of combat**: X in the dungeon (and in a city) swaps free
   with the same log line, and the explore HUD's help block shows
   `[X] Swap Sets` in both modes; X in space does nothing (the space
   HUD carries no X hint).
6. **Save/load sniff**: swap out of combat → ESC save → continue →
   Shift+W shows the swapped arrangement with magazines intact.
7. **Guide diff**: Controls & Keybindings, Combat list — ADD after
   the R line: "X: swap weapon sets (free while exploring, 1 AP in
   combat)". Before: no such line.

## SETTLED 3 (2026-09-25, user) — phase 3 rulings (equipment UI)

- **Sets are CLASS-KEYED**: there is exactly one ranged home and one
  melee home. A weapon always equips into its class's set;
  active/holstered are ROLES that X flips, not identities. Dual
  same-class loadouts are impossible by construction. UI labels:
  the ranged/melee set with its current role marker.
- **C-screen equipment pane = two class groups + role markers**
  (e.g. `WEAPONS - RANGED [ACTIVE]` / `WEAPONS - MELEE [HOLSTER]`);
  empty sets still render (the fists floor stays visible).
- **Mid-combat, ANY equipment change through C costs 1 AP —
  uniform**: active set, holstered set, armor, all of it (extends
  SETTLED 1's per-change economy; X's 1-AP whole-set swap is never
  undercut by free restructuring).
- **Equipping into a full set opens a MEMBER chooser**: the picked
  member is displaced (to the pack on the C-screen path, to the
  warehouse on the armory path — today's displacement containers);
  a 2H pick displaces the whole set as today.

Phase-3 ADVISE round rulings (2026-09-25, user; the pass itself is
recorded below the brief):

- **Armory screens go FULLY set-aware**: the equipment view
  mirrors the C screen (both class groups + role markers); Store/
  Sell works on members of either set.
- **The C-screen reload is REMOVED** (user, verbatim): "why do we
  need a c screen reload? let's just remove it? reload is either
  in combat or out of combat. not inside the menus." R becomes the
  single reload verb — in combat at the weapon's reload AP, in
  dungeon exploration via the existing `reload_exploration`. Every
  menu reload offering (weapon-row options, pack ammo-stack
  reload) is deleted; the two-price row/counter tangle dissolves
  with them.
- **Magazines PRESERVE through store/displacement**:
  `StoredGroundEquipment` gains serialized loaded ammo (legacy
  saves / absent field default to a full magazine); a half-spent
  pistol stores, displaces, and comes back half-spent. Kills
  today's store-reseed free-ammo round-trip and makes the
  Overview's magazine-persistence promise true on every path.

### Phase 3 Implementation brief (PROPOSED 2026-09-25 — SETTLED 3 +
### ADVISE-folded; ready for /implement-phase 51.3 on approval)

**Scope (files / hook points; all anchors advisor-verified):**

- **Set-targeting primitives** (`ground_weapon_sets.py`, 113
  lines — owns the set law; `ground_equipment.py` at 987/1000
  cannot absorb anything): NEW pure planners — resolve a weapon's
  class home and an equip plan (target list + displacement set
  when the home is full). **Founding rule, TOTAL over reachable
  states (ADVISE fold 7)**: home = the set holding the class; if
  BOTH hold it (hand-edited save) the ACTIVE set wins; if unfounded
  → the empty set that is not the other class's home; if both
  empty → the ACTIVE set (equip-to-wield). Degenerate mixed sets
  with no empty set (purity refuses every entry) → deterministic
  refusal with a log line. Capacity validation imports
  ground_equipment's existing helpers (one-way; no cycle).
- **Magazine preservation (SETTLED 3)**: `StoredGroundEquipment`
  gains a serialized loaded-ammo field (absent/legacy = full via
  the `weapon_instance` seeding default); `weapon_entry` carries
  the instance's loaded ammo; every store/displacement path
  preserves it. The balance harness's "magazines seed FULL"
  docstring contract updates (its loadouts build full anyway).
- **The slot-model weapon functions RETIRE** (the ratchet payment
  IS the retirement): `swap_weapon_from_expedition`,
  `install_weapon`, `_plan_weapon_install`, `_apply_weapon_install`,
  `_replace_weapon_slot`, `_validated_swap_weapon`, and
  `_set_swapped_weapon` (the "+helpers" enumeration closed — ADVISE
  fold 9; 146 lines out → ground_equipment ≈841/1000) leave for
  the set-aware equip/store/install primitives. **Callers moving
  in the SAME commit (ADVISE folds 1-2)**: character_screen
  pack-equip, armory `_install_from_container`, armory
  `_install_purchase` (the BUY_INSTALL branch — buy-and-equip IS
  an equip flow; the buy-destination branches stay), AND
  `tests/balance/harness.py:412` `build_ground_loadout` (rerouted
  onto the set-aware install — a mechanical caller move, NOT
  balance work; the stop point does not forbid it). Armor twins
  and shared validators stay.
- **C-screen reshape** (`character_screen_weapons.py` 140 +
  `character_screen.py` 921): `_weapon_rows` renders TWO class
  groups with role markers (empty sets shown); manage actions
  (equip/store) offered per member of BOTH sets;
  `_swap_options`/`_pack_weapon_slots` (the `range(2)` slot
  vocabulary) → class-set targeting; the pack-equip slot chooser →
  the member chooser when the class home is full (2H pick
  displaces the whole set); store flow works from either set
  (storing every active member leaves it EMPTY — the fists floor
  is reachable through the UI, phase-2 playtest item 3's deferred
  half). **Chooser capacity failure (ADVISE fold 10)**: the
  chooser is always offered; a 2H displacement whose +1 member
  overflows the pack aborts atomically with the existing
  "Expedition inventory is full" line — zero partial mutation.
  **Menu reload REMOVED (SETTLED 3, verbatim ruling)**:
  `ground_reload_ui.py` enters scope — the menu-facing plumbing is
  deleted (character_screen's `weapon_reload_option` row options,
  `reload_weapon_slot` row handler, `reload_pack_ammo`, and the
  pack-ammo reload branch of `manage_pack_ammo` — the exact
  split verified at build), while `reload_exploration` and its
  internal helpers stay as R's engine. R becomes the only reload
  verb: in combat at the weapon's reload AP, in dungeon
  exploration free — the row/counter two-price tangle dissolves.
- **Armory fully set-aware (SETTLED 3)** (`menus/_armory.py` 921):
  `_weapon_slot_rows`/`store_weapon`/`remove_weapon` become
  two-group set-aware (mirroring the C screen); the weapon branch
  of `_install_from_container` + `_install_purchase` route through
  the set-aware install with the member chooser;
  `_needs_displacement`/`_displacement_container` recompute
  against the class home (not the equipped list — ADVISE fold 3a).
  The BUY flow's destination logic is otherwise untouched.
- **Tinker reach** (`tinker.py` 289, `_weapon_targets` :139):
  enumerate BOTH sets (`KIT:WEAPON:{set}:{index}` — keys are
  opaque/equality-matched, no binder change needed); the phase-1
  reviewer catch lands.
- **Guide** (`data/guide/`): Ground Gear :317-319 — the two-slot
  sentence replaced by set wording, RETAINING the trailing
  "Every weapon lists its damage type…" sentence (ADVISE fold 13);
  the reload blurb :300-302 reworded for menu-reload removal.
  Proposed text (red-line at approval): "Weapons are carried as
  two sets — one ranged, one melee. Each set holds one
  two-handed weapon or up to two one-handed weapons; X swaps the
  whole active set for the holstered set." Own commit per the
  prose gate.

**Build order:** magazine field + set-targeting primitives +
tests → retire/replace the slot-model functions with ALL callers
(character_screen pack-equip, armory install + buy-install,
balance harness) → C-screen two-group reshape + member chooser +
store flows + menu-reload removal → armory set-aware view/manage →
tinker reach → guide entry (own commit) → full `make check`.

**Binding rulings:** SETTLED 3 (all seven — class-keyed sets,
class groups + markers, uniform 1 AP per change, member chooser,
armory fully set-aware, menu reload removed, magazines preserve)
+ SETTLED 1 extension (uniform 1 AP: armor economics UNCHANGED —
armor already counts today, ADVISE fold 11; the new deltas are
holstered edits and the mid-combat store, both pinned). Derived
mechanics (red-line at approval): the total founding rule above;
loader tolerance unchanged (degenerate same-class/mixed saves load
verbatim and resolve per the rule); X, HOLSTER row, dev grant
untouched; R's dungeon-exploration gate unchanged (city reload
was never offered and still isn't — managing ammo happens in
dungeons or via R in combat). Pre-committed ratchet seams (ADVISE
fold 12 — no improvising mid-build): character_screen's pack/
equip manage flows overflow into `character_screen_weapons.py`
(or a new sibling beside it); the armory's install/manage flows
overflow into a sibling of `_armory.py`; the four named 40/36-line
walls (`_swap_from_pack`, `_install_from_container`,
`reload_weapon_slot` remnant, `_apply_equipment_select`) get
their extractions as part of their owning commits.

**Required tests:** set targeting — the resolution table incl.
every degenerate row (founded, unfounded-with-other-founded,
both-empty → active, same-class-both → active wins, mixed-no-empty
→ refusal line); member chooser — 1H pick displaces the picked
member, 2H pick displaces the whole set, 2H-at-pack-capacity
aborts atomically; magazines — a half-spent instance round-trips
half-spent through pack-store, displacement, and armory install;
legacy no-field saves load full; store — capacity-checked,
store-all leaves the active set empty (fists floor via UI);
uniform AP — a mid-combat holstered equip AND a mid-combat store
each charge exactly 1; C-screen rows — both class groups with
role markers, empty sets visible, X flips markers, NO reload
options anywhere in the screen; armory — install/buy-install
route to the class home, store/sell on either set, displacement
containers correct for a holstered home; tinker targets enumerate
holstered members; pack relief behavioral pin (holstered members
survive a pack-full state); save/load round-trip through every
new flow; guide entries present. **Test surgery named (ADVISE
fold 8)**: `test_ground_equipment.py` — 15 retired-name
references across the slot-model tests (rewrite as set-model;
delete pure slot-behavior pins like
`test_swap_weapon_from_expedition_replaces_requested_slot`);
`test_pygame_ui.py` — the "Weapon slot 1/2" row vocabulary,
`SWAP:weapon:0`, and 6 `RELOAD_SLOT` pins re-anchored;
`test_tinker.py` — `KIT:WEAPON:0` pins re-keyed. Every retired
name rg-verified gone (src, tests, tools). Every new pure/
mutation-wrapper function carries its test in the same commit.

**Stop point:** no balance/board WORK (phase 4) — the harness
caller reroute in the retirement commit is a mechanical move, not
balance work; no tutorial or further guide edits (phase 5); no
HUD changes; no new keys; no dev-grant changes; no space-side
anything.

**Playtest checkpoint:**

1. **Two-group C screen**: open C → weapons render as RANGED and
   MELEE groups with `[ACTIVE]`/`[HOLSTER]` markers matching the
   dev seed; X in the dungeon flips the markers.
2. **Founding**: on a fresh non-dev game, equip a melee weapon from
   the pack → it founds/joins the melee home; the other group shows
   empty.
3. **Member chooser**: with the ranged set full (2×1H), equip
   another 1H ranged from the pack → chooser lists the set's
   members; the pick is displaced to the pack, magazine intact.
4. **Uniform AP**: in combat, C-equip into the HOLSTERED set →
   exactly 1 AP (same for a mid-combat store).
5. **Store-to-empty**: store every active-set member → the group
   shows empty, X swaps to it, F fights with fists.
6. **Magazines**: fire the pistol half-empty → store → re-equip →
   still half-empty (no free top-off).
7. **No menu reload**: the C screen and pack submenus offer no
   reload options anywhere; R reloads in combat (weapon's reload
   AP) and in the dungeon (free).
8. **Armory**: the equipment view shows both groups; install and
   buy-and-equip land in the class home; store/sell works on
   holstered members.
9. **Tinker**: the kit's chooser lists holstered members.
10. **Save/load sniff**: build both sets via the new flows → ESC
    save → continue → sets, markers, and magazines identical.
11. **Guide diff**: Ground Gear — the two-slot sentence replaced
    (trailing damage-type sentence retained) + the reload blurb
    reworded; exact before/after quoted at handoff.

### Phase 3 ADVISE pass (2026-09-25, pre-approval — every-brief rule)

Verdict: **ADVICE — 7 blocking, 6 minor; three blocking findings
escalated to user rulings (armory scope, reload economy → the
menu-reload removal, magazine round-trip), the rest folded into
the brief above.** Blockers: (1) the balance harness imports
`install_weapon` — retirement without rerouting breaks pytest
collection; (2) the armory BUY_INSTALL branch calls the retired
function; (3) `_needs_displacement`/`_displacement_container`
compute against the equipped list + the armory manage flow is
active-set-only (→ ruled: armory fully set-aware); (4)
`ground_reload_ui` is slot-keyed (`RELOAD_SLOT:{int}` parsers
raise on set keys) and was missing from scope; (5) the row-reload
price is path-dependent today — 1 AP flat on member rows,
`reload_ap_cost` on ammo stacks (→ ruled: menu reload removed
entirely); (6) stored weapons carry NO magazine — re-equip seeds
FULL, contradicting the brief's "keep magazines" line (→ ruled:
preserve through store); (7) the founding rule wasn't total over
hand-edited saves (same-class-both-sets tiebreak, mixed-no-empty
refusal — both folded as derived mechanics). Minors: test surgery
enumerated (test_ground_equipment ×15, test_pygame_ui row
vocabulary + 6 RELOAD_SLOT pins, test_tinker key pins);
`_set_swapped_weapon` named (146 lines total → ≈841 remaining);
2H-displacement capacity failure stated; armor-AP delta stated
honestly (no change) + the mid-combat store pin; four ratchet
walls + module headroom → pre-committed overflow seams; guide
anchors corrected (trailing sentence retained, reload blurb).
Verified clean: save/load introduces no new state beyond the
magazine field; tinker keys are opaque (no binder change); the
Equipment tab scrolls (doubled rows paginate); the tinker/kit
mechanics and the purity guards block every state the loader
would mangle.

## Open questions

1. **Tutorial teaching**: does the tutorial's armory beat teach the
   toggle (buy 2 + 2?), and with what wording? (Prose-gated; phase 5.)
2. **Balance blast radius**: landing this re-rules the doc-50 board
   (phase 4). Any bar the user wants held IMMUNE to re-rule (e.g.,
   the space rows)?
