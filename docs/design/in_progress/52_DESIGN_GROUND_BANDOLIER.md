# DESIGN: The Bandolier — tracked ammo reserves, never in the pack

**Status: PHASE 6 = THE LAST PHASE, BRIEF PROPOSED (2026-09-25
refine). Phases 1-3 COMPLETE (playtest passed, incl. the
mid-playtest rulings — feeder-free aligned Ammo column; "bandolier"
retired from player-facing text). Phase 4 (cap gear) DEFERRED to the
future armor/cybernetics polish pass (the `effective_cap` seam
shipped). Phase 5 (endurance rows) MOVED to doc 50's resumption
(SETTLED 6). Phase 6's wording is RULED (SETTLED 6) and its brief is
proposed — doc 52 closes after 52.6 passes its playtest.**

## Overview

Ammo stops being pack cargo and becomes a **tracked reserve with a
per-type carry cap — the bandolier**: thematically the harness that
carries doc 51's weapon sets. Each ammo type (pistol rounds, rifle
rounds, energy cells, shells, grenades, rockets) has its own
current/max counter; reloading draws from it; drops and armory
restocks refill it; it never occupies an expedition-pack slot. Armor
and cybernetics can grow the caps through a new `ammo_bonus` — the
same fold that grants HP and AP from worn pieces today.

User rulings (2026-09-25, doc-50 tuning session):

> "ammo is tracked and you have a max ammo you can carry per ammo
> type. But ammo doesn't live in your backpack."

> "and then we could have some day armor/cybernetics that gives +
> to ammo cap"

The change sits between the two options considered and rejected:
infinite ammo (kills the attrition economy and plasma/melee
identity) and stacks-in-pack (measured non-viable at depth — below).

## SETTLED 1 (2026-09-25, user — the phase-1 rulings)

- **Caps confirmed at the proposed table** (~40-50 kills of endurance
  for gun calibers: pistol 160 / rifle 240 / cells 250 / shells 130;
  premium explosives grenades 18 / rockets 10 ≈ 10 uses) — one full
  delve with margin; scavenging binds only under sustained spray.
- **Sequencing: doc 52 builds AFTER doc 51's core lands** — the
  shared surgery (pack contents, save migration, tutorial armory
  beat, armory UI) is done once; phase-1 briefs are written now and
  wait on the handoff.
- **Phase-scope amendment (same ruling pass)**: the DROP re-point
  (corpse ammo → bandolier refill, not pack stacks) moves from
  phase 2 into phase 1 — without it, the post-migration interim
  leaves newly dropped stacks as dead pack cargo for a phase gap.
- Migration as drafted stands: pack stacks convert into bandolier
  counts (capped), overflow refunded as credits.

## SETTLED 2 (2026-09-25, user — the phase-2 economy rulings)

- **Overflow pickups: IGNORED.** A drop past a caliber's cap simply
  doesn't refill; the HUD reads "topped up" (phase 3). No credits.
- **Restock pricing: PER-ROUND.** Armory restock-to-cap charges
  rounds-actually-added x `price_per_round` (1/1/2/2/8/20 across the
  six calibers).

## SETTLED 3 (2026-09-25, user — the armory gap + phase 1 approval)

- **Armory gap: ACCEPTED** — phases 1 and 2 build back-to-back, so
  the one-session gap (armory selling pack stacks that are dead
  cargo once reload reads the bandolier) never reaches a player.
  Phase 2's brief inherits an explicit "builds immediately after
  phase 1" note.
- **Phase 1 Implementation brief APPROVED** (amended form, 1ed0b2bd:
  pickup-time re-point, complete reload call-site list, the
  `bandolier.py` sibling module for the ratchet, `stances.py` in the
  doc-50 seam, report-diff verification). Phase 1 is refined and
  gated on the doc 51 handoff.

## SETTLED 4 (2026-09-25, user — gear deferred, HUD ruled)

- **`ammo_bonus` gear DEFERRED to a future armor/cybernetics polish
  pass** (user: "Let's make sure we have the future ability to add
  armor that expands ammo. But I'll tackle that in a future polish
  pass when we really look at what kind of armor/cybernetics we
  have available."). Doc 52's obligation is the SEAM only: phase 1's
  `effective_cap` accepts a bonus term the future pass can feed from
  a worn-gear fold. The `GroundArmorSpec.ammo_bonus` field, the
  first items, and the flat-vs-per-type ruling all move to that
  pass. Phase 4 below is DEFERRED (kept numbered for reference).
- **Visibility (refined same day by user amendment):** the combat
  HUD shows the RELEVANT bandolier ammo — current/max for the
  calibers your equipped weapons use; the character screen's
  equipment tab shows ALL ammo types (the full bandolier, six
  current/max entries — the inventory view).

## SETTLED 5 (2026-09-25, user — the phase-2 ADVISE blockers)

- **ALL calibers restockable, unconditionally** (user: "You should
  be able to pickup and buy any kind of ammo no matter what.") —
  the armory's restock section offers every caliber regardless of
  what is equipped/holstered/owned; pickups of any type refill the
  bandolier up to cap (SETTLED 2's over-cap-ignore unchanged).
  SUPERSEDES the earlier "carried-calibers-only shop" inference for
  RESTOCK; the HUD's relevant-caliber line (SETTLED 4) and the
  character screen's all-six view stand. The buy-then-restock
  prompt is dropped — moot when every caliber is always a row.
- **Quantity chooser stays, and the modal gets fast keys** (user:
  "the current quantity modal is a bad UX. Pressing right 60 times
  sucks. I vote we keep the current quantity modal + improve it to
  be able to buy faster. maybe up/down moves the quantity by 10s?
  page up/page down go min/max? something like that, I'm open to
  thoughts"). Build shape: left/right stay ±1; up/down become ±10;
  PageUp/PageDown jump min/max; and (agent proposal, in the same
  pass) the modal OPENS pre-filled at min(affordable, space-to-cap)
  so the common case is confirm, not crawl. Key names verified
  against the runtime at build. The tutorial's arithmetic survives
  unchanged — 40 rounds for 40 credits, exactly the old economy.
- **Tutorial rewording stays in phase 6, with an explicit accepted
  gap**: between phase 2 and phase 6, new players are instructed to
  "buy a stack of Pistol Rounds" the armory no longer sells —
  accepted interim damage (the restock rows sit on the same screen;
  the wording lands in phase 6's prose-gated pass).
- **Landing order pinned: doc 52's tutorial/guide rewrites (52.3,
  52.6) land AFTER doc 51 phase 5's teaching pass** — 52 rewrites
  51's fresh prose once, not the other way around. (SATISFIED by the
  time SETTLED 6 ruled: doc 51's teaching pass — renumbered phase 4 —
  landed and RETAINED the stack clause for 52.6 to rewrite.)

## SETTLED 6 (2026-09-25, user — phase 5 moves to doc 50; phase 6
## wording ruled)

- **Phase 5 (endurance rows) MOVES to doc 50's resumption** (user:
  "yes, phase 5 will be revisited when I pick back up doc 50."). The
  phase-5 bullet's coordination partner was doc 51's re-rule phase —
  removed by doc 51 SETTLED 4, whose re-measure + fresh sweeps +
  proposed ×2-2H doctrine now live in doc 50's resumption queue, and
  that queue waits on doc 52's close. Landing the kills-of-endurance
  rows there pins them ONCE under the final world (the ×2-2H retune,
  if ruled, is the only known mover of those numbers — pinning now
  would buy a tripwire for a planned change and pay a
  benchmark-revision commit on retune). The "with and without cap
  gear" half is dead anyway (phase 4's deferral). The battle-×2
  measurement travels with the rows. Doc 52's remaining scope is
  phase 6 only; after 52.6 lands and passes, doc 52 closes and doc
  50's resumption unblocks with the endurance rows in its first
  passes. The phase-1 store swap's byte-identical board diff stands
  as doc 52's balance obligation, already discharged.
- **Phase 6 wording: AGNOSTIC — no round count in the popup** (user:
  "yes, keep it agnostic. yes Pistol Rounds works."). The earth_armory
  beat's stale clause becomes, verbatim: "...and buy two Kinetic
  Pistols and a Combat Knife, then restock your Pistol Rounds." The
  restock modal's prefill (min(affordable, space-to-cap) ≈ 145
  rounds for the tutorial character) and fast keys are the teacher;
  naming no count means nothing in the teaching contradicts the
  modal's prefill, and the credit-margin choice (rounds vs armor/med
  packs) stays the player's. "Pistol Rounds" = the RESTOCK row's own
  item name. The 52.3 playtest ruling binds: the tutorial never says
  "bandolier" — the approved wording already complies.

## Measured evidence (doc 50 session, 2026-09-25)

A 4-floor delve (Mars reference: real generator, 16 mobs/floor, 64
enemies, ~1,380 HP pool, 3-6 armor-1 drones per floor) against the
4-slot pack (strength 10; 6 slots at str 20):

| loadout | measured rds/kill | delve demand | stack | slots needed |
|---|---|---|---|---|
| kinetic_pistol ×2 | 4.1 | ~265 | 40 | 6.6 |
| laser_pistol ×2 | 6.5 | ~414 | 50 | 8.3 |
| kinetic_rifle | 5.8 | ~371 | 40 | 9.3 |
| shotgun | 3.2 | ~206 | 20 | 10.3 |
| laser_carbine ×2 | 2.4 | ~156 | 50 | 3.1 |
| railgun | 2.5 | ~160 | 40 | 4.0 |
| plasma / melee | 0 | 0 | — | 0 |

Med packs stack 3 (~11 HP each, ~33 HP/slot) and wanted 3–5 slots of
their own. Drops roll 0–1 per kill from the victim's pool (~25% ammo
for two-entry pools), planet-keyed — Mars fauna drop nothing
field-usable, so kinetic calibers starve on Mars entirely. Findings:
no ammo weapon can carry a deep delve; melee/plasma dominance at
depth is logistically forced; ammo credits were decorative (1–2
cr/round) except explosives (8–20).

**Endurance = cap ÷ measured rounds-per-kill** is the new derived
balance stat: kills-of-endurance per caliber, pinnable as standard
rows (doc 50 SETTLED 6).

## Philosophy alignment

| Principle | How this design holds it |
|---|---|
| No special cases | One caps table in the ammo catalog; one bonus field on armor; every caliber resolves through the same mechanism |
| Data-first | `carry_cap` lives on `GroundAmmoSpec`; `ammo_bonus` on `GroundArmorSpec` (quality-scaled via `effective_armor_spec` like every other bonus) |
| Save/load sacred | `bandolier` is a declared, serialized ctx field; existing pack stacks migrate into it (capped), overflow refunded |
| ctx-first | The bandolier is a GameContext field — no runtime attachment |
| Uniform mechanisms | The reload path re-points from pack stacks to the bandolier; armor caps ride the existing `sum_armor_bonus` fold |
| Guide contract | Ground Gear ammo paragraph + armory flow reviewed; plasma/melee "never runs dry" identity PRESERVED (they simply never touch the bandolier) |

## Data model

- `GroundAmmoSpec` gains `carry_cap: int` — the per-type maximum.
  Proposed starting caps (tuned to ~40-50 kills of endurance at
  measured efficiency, forcing scavenging only for spray):

  | ammo type | cap | endurance (measured) |
  |---|---|---|
  | pistol_rounds | 160 | ~39 kills (pistol pair) |
  | rifle_rounds | 240 | ~41 (rifle) / ~85 (battle ×2, estimate —
    unmeasured until phase 5) |
  | energy_cells | 250 | 38 (laser pistol pair) – 104 (carbine pair) |
  | shotgun_shells | 130 | ~41 |
  | grenades | 18 | ~10 fights (premium scarcity) |
  | rockets | 10 | ~10 booms (premium scarcity) |

- `GameContext.bandolier: dict[str, int]` — ammo_type → rounds
  carried. Reload draws from it (replacing `reserve_ammo_count` over
  pack stacks); `add_rounds` clamps at the effective cap.
- **Effective cap** = `carry_cap` + worn gear bonus (below). Multiple
  calibers carried are INDEPENDENT pools (doc 51's mixed ranged set —
  pistol + carbine — carries two partial endurance pools: a real
  trade).
- FUTURE PASS (SETTLED 4, out of doc 52's build): `GroundArmorSpec`
  gains `ammo_bonus: int = 0`, folded through the existing
  `sum_armor_bonus` (fifth bonus field beside ap/hit/melee/hp;
  quality-scaled) — the future armor/cybernetics polish pass owns
  the field, the first items, and the flat-vs-per-type ruling. Doc
  52's phase 1 ships the `effective_cap(base, bonus)` seam it will
  feed.

## Domain changes

- `ground_equipment.py`: bandolier helpers (`add_rounds`,
  `space_remaining`, effective-cap fold); reload path re-point
  (`_reloadable_slots` / `apply_reload` / `reserve_ammo_count`
  call sites).
- Pack: the ammo stack class RETIRES from the expedition pack
  (consumables/kits remain); migration converts carried stacks into
  bandolier counts, overflow → credits.
- Drops: ammo entities refill the bandolier ON PICKUP (capped;
  over-cap ignored per SETTLED 2; the spawners themselves are
  unchanged).
- Armory terminal: **restock-to-cap** per carried caliber replaces
  stack purchase (price = rounds added × `price_per_round`).
- HUD: current/max for CARRIED calibers only (SETTLED 4), like the
  fuel/power lines.
- Tutorial: the armory beat's "buy a stack of Pistol Rounds" wording
  → restock phrasing (prose-gated; phase with guide edits).
- Guide: Ground Gear ammunition paragraph rewrite; Controls
  unchanged (R still means reload — the magazine mechanic and its
  AP tempo are untouched).
- Doc 50's standard: `ammo_spent` bars unchanged (rounds fired still
  measures shot efficiency); NEW pin family — kills-of-endurance per
  caliber. (The "with and without the cap gear" half retired with
  phase 4's deferral; the rows themselves MOVED to doc 50's
  resumption — SETTLED 6.)

## Phases

- [x] 1. **Bandolier core** — caps on the catalog, ctx field,
  serialization + pack migration, reload draw path re-point, drop
  re-point (SETTLED 1 scope amendment). Tests: round-trip incl.
  migrated saves, cap clamps, multi-caliber independence, reload
  integration, plasma/melee untouched.
- [x] 2. **Economy surfaces** — armory restock-to-cap, pack
  ammo-class retirement, market/sell handling for legacy stacks.
  Tests: restock pricing.
- [x] 3. **HUD + guide** — bandolier line(s), Ground Gear paragraph,
  plasma/melee identity wording check. Guide diff rides the phase
  checklist.
- [ ] 4. **Cap gear — DEFERRED (SETTLED 4)** to the future armor/
  cybernetics polish pass: `ammo_bonus` field + first items +
  quality scaling + the flat-vs-per-type ruling. Doc 52 ships only
  the `effective_cap` bonus seam (phase 1).
- [ ] 5. **Endurance rows — MOVED to doc 50's resumption (SETTLED 6,
  2026-09-25)**: kills-of-endurance pins per caliber + the battle-×2
  measurement land with doc 50's first re-measure passes (the re-rule's
  new home after doc 51 SETTLED 4 removed it), pinned once under the
  final post-retune world. The "with and without cap gear" half retired
  with phase 4's deferral. (The original clause — "coordinated with
  doc 51's re-rule phase" — went stale when doc 51 SETTLED 4 removed
  that phase; rewritten by SETTLED 6.)
- [ ] 6. **Teaching** — tutorial armory beat rewording (prose-gated:
  user wording before data strings).

Each phase gets its Implementation brief at its own refine time.

### PLAYTEST sketches (per phase; detailed at brief time)

1. Old save → continue → pack stacks became bandolier counts +
   refund; reload works; caps hold.
2. Armory restock tops a caliber to max at the right price; a drone
   drop refills energy cells; over-cap pickups ignored.
3. HUD reads 132/160 under fire; guide paragraph accurate.
4. Equip the rig → caps rise; Modded quality scales the bonus.
   (Deferred with phase 4 — the future armor/cybernetics pass.)
5. Endurance rows green in `make check`. (Moved with phase 5 to doc
   50's resumption — SETTLED 6.)

### Phase 1 Pre-implementation audit (2026-09-25 build session)

**1. Existing modules to extend or reuse (verified in code):**

- `ground_weapon_ammo.py` — the reload engine doc 51 phase 3
  extracted; `reserve_ammo_count` / `apply_reload` /
  `reload_amount` are THE reserve surface, re-exported by
  `ground_equipment.py:770-780` so every caller imports stay
  stable. The re-point swaps their store from the pack list to the
  bandolier dict; import lines at all call sites stay identical.
- `GroundItemStack` / `parse_item_stack` / `item_stack_capacity`
  (`ground_equipment.py:583-625`) — legacy stack parsing STAYS
  forever (phase-2 brief pins it); migration reads parsed stacks.
- `saveload_ground.py::_ground_fields` / `_restore_ground_fields`
  (wired at `saveload.py:251` / `:939`) — the serialization seam;
  `_safe_ground_int`'s clamp/skip convention is the parse pattern
  the bandolier follows. Log restore happens at ctx construction
  (`saveload.py:733`), BEFORE `_restore_ground_fields` — a refund
  log line in the restore path persists to gameplay.
- `loot.py::_apply_field_item_loot_pickup` (:496) — the SINGLE
  field-item pickup entry (`_apply_field_item_loot` :760 delegates
  to it); the ammo branch re-points here. `_finish_loot_pickup`
  (:427-475 neighborhood) consumes the entity + logs.
- `harness.build_ground_loadout` / `build_ground_ctx` /
  `_ground_ammo_total` (tests/balance/harness.py:401/437/585) and
  `stances._dry_reloadable_slot` (:54) — the doc-50 seam; sheets
  declare at most `pistol_rounds`×40 (verified — all 3
  `ground_ammo` rows), far under the 160 cap, so seeding via
  `add_rounds` cannot clamp and drift the bars.
- `dev_mode.apply_dev_ground_loadout` — grants weapons/armor only,
  no ammo stacks; no phase-1 change (verified :283-310).

**2. Three potential duplication hotspots:**

- TWO reload paths (combat `_rules_ground._reloadable_slots` +
  `_reload_slot`; exploration `ground_reload_ui.reloadable_pack_slots`
  + `reload_weapon_slot`) repeating the reserve read and the
  apply call — risk of re-pointing one and missing the other.
- The ammo_type→spec lookup (needed by `effective_cap`, the save
  parser's clamp, and the migration's refund pricing) re-derived
  in three places from `list_ground_ammo()`.
- Pickup vs migration both "add rounds, compute accepted vs
  overflow" — risk of two hand-rolled clamp loops instead of the
  shared `add_rounds` core.

**3. DRY strategy per hotspot:**

- Both reload paths already delegate to the shared engine
  (`reserve_ammo_count` + `apply_reload`); the re-point changes
  each call site's STORE ARGUMENT to `ctx.bandolier` and nothing
  else — the engine stays single-sourced (the state-table/one-
  mechanism guardrail). `reloadable_pack_slots` (no external
  callers — verified) renames to `reloadable_slots` so the name
  stops lying about the store.
- `bandolier.py` owns one lazy `_spec_by_ammo_type()` registry;
  `effective_cap`, the parser, and the migration all resolve
  calibers through it. `reserve_ammo_count` does NOT get a
  bandolier twin — one reserve read (the engine's) is re-exported
  everywhere (no parallel-path drift).
- Both pickup and migration call the pure `add_rounds` and derive
  accepted/overflow from the before/after counts; the migration's
  refund pricing is its own pure step (price × overflow) with no
  second clamp loop.

**Audited call-site list for the re-point (complete, from grep):**
`_rules_ground.py:620` + `:642`, `ground_reload_ui.py:30` + `:72`,
`_ground_render.py:272` (`_reserve_count`), `stances.py:73`,
`test_balance.py:342`, plus the pack-stack pins in
`test_ground_equipment.py`, `tests/combat/test_rules_ground.py`
(`_ammo_ctx` :1275 + reload pins :1319/:1351), and
`test_saveload.py:1337-1350` (round-trip pins an expedition ammo
stack — becomes a migration pin). `matching_ammo_stack_index`
becomes dead (only `_apply_reload_at` called it) — removed with
its test. `loot.py`'s two spawners stay untouched (verified :113,
kit-drop path) — legacy on-map entities convert on pickup.

**Build-note surprises to carry forward:**
- A concurrent design session landed the ratchet ruling
  (514f84c3) + this doc's cohesion re-grounding (1aba1194)
  mid-build; the build already conformed (bandolier.py earned its
  place on cohesion; no size arithmetic was leaned on).
- Reviewer issue 2 (harness assert semantics): the loadout assert
  now checks the PER-ROW delta so a future multi-row same-caliber
  sheet can't false-fail under a mismatched message — fixed
  in-commit (a01e422a).
- The four pack-loot choreography pins (merge/remainder, full-pack,
  drop-to-fit, prompt-twice) converted to CONSUMABLE entities —
  the pack path is consumables-only now, and those pins keep
  guarding it verbatim; ammo gets its own three bandolier pins.

### Phase 1 build record (LANDED 2026-09-25 — PLAYTEST PASSED)

**Playtest: PASSED 2026-09-25 (user).** All checkpoint items; the
migration/reload/pickup/endurance behaviors confirmed in play, and
the `RES` HUD read confirmed understood (transient until phase 3's
current/max rework). The log-line verbatims were exercised in play
unamended and stand as shipped. The brief's "walk over the drop"
wording was corrected mid-playtest (see findings below). The
at-cap-silence wording question parked here was RESOLVED by user
ruling during the 52.2 playtest (see the phase-2 build record): a
short at-cap line now logs on the explicit pickup path, reusing the
restock guard's wording verbatim.

**Commits:** 6ca1bb17 (pre-implementation audit) → cc6fe159 (catalog
`carry_cap`, SETTLED 1 values pinned) → 27f793f4 (`bandolier.py`
pure core + tests) → b40b88b1 (ctx field + serialization, parse
clamp/skip) + a8467525 (tinker fake pinned) → a01e422a (the store
swap: reload re-point at every call site, `reloadable_pack_slots` →
`reloadable_slots`, pickup re-point, pack migration with refund,
doc-50 harness/stances seam, updated pins).

**Reviewer (REVIEW): APPROVE** — two [minor]: the prose-gate item
below (resolved by quoting the lines at this checkpoint), and the
harness assert semantics (fixed in-commit, see build note).

**Board preservation verified by DIFF, not green bars:** the balance
report ran on a detached HEAD worktree (pack store) and the working
tree (bandolier store) — byte-identical (59 lines, all scenarios,
same seeds). Doc 50 SETTLED 6's benchmark-revision clause NOT
triggered: this was a behavior-preserving store swap.

**Prose gate — new/changed player-facing strings, landing at this
checkpoint for sign-off (verbatims):**
1. Ammo pickup (loot.py): `Picked up {name} x{n}.`
   (e.g. "Picked up Pistol Rounds x12." — the accepted count only;
   overflow past cap is forfeited silently per SETTLED 2.)
2. Migration conversion (saveload_ground.py): `Packed {n} reserve
   rounds into the bandolier.`
3. Migration refund (saveload_ground.py): `Refunded {n} rounds past
   carry caps: {cr}$.`
4. Swapped reload-failure error (ground_weapon_ammo.py): was `No
   {ammo_type} ammo in the Expedition Pack`, now `No {ammo_type} ammo
   in the bandolier` (raw caliber id — pre-existing voice, kept).

**Rulings made at build time (from SETTLED 2's wording, surfaced for
the playtest):** an AT-CAP pickup is ignored as an event — no log
line, the entity stays on the floor for later; a PARTIAL fit
consumes the entity and forfeits the remainder rounds (no floor
remainder, no credits).

**Playtest findings (user, item 3):** the brief's "walk over the
drop" wording was WRONG about the game's pickup UX — field items are
picked up via P + the loot chooser (`game_flow._pickup_loot_near` →
`loot.open_loot_pickup`), never walk-over auto-pickup. The bandolier
refill is pinned through that exact chooser flow
(`test_trade.py::test_p_pickup_chooser_lists_all_nearby_stacks`),
so the build behaves correctly; checkpoint item 3's wording is
corrected above. OPEN for ruling: at-cap silence now happens after
an EXPLICIT choose (P → pick ammo → nothing visibly happens) —
SETTLED 2 says silent, but through a chooser that may read as
broken; a "bandolier full" style line for the explicit path is a
candidate wording ruling at this checkpoint.

### Phase 1 Implementation brief (APPROVED 2026-09-25, SETTLED 3 —
### amended per the ADVISE pass; gated on doc 51's core landing;
### ready for /implement-phase 52.1 on the handoff)

**Scope (files / hook points):**

- **Caps on the catalog** (`src/spacehack/data/ground_items/`):
  `GroundAmmoSpec` gains `carry_cap: int`; the six rows get SETTLED
  1's values (160/240/250/130/18/10).
- **The ctx field** (`game_context.py`): declared
  `bandolier: dict[str, int]` (ammo_type → rounds), default empty;
  serialized in `saveload_ground.py`.
- **Bandolier module** (NEW `src/spacehack/bandolier.py`): its own
  cohesive responsibility with a PURE core —
  `add_rounds(bandolier, ammo_type, n, cap) -> dict` (clamped),
  `space_remaining`, `effective_cap` (base cap in phase 1; the gear
  fold's seam ready for phase 4) — plus thin ctx wrappers; the pure
  core ships with pytest in the same commit. (Design note per the
  2026-09-25 ratchet ruling: the module earns its place on cohesion
  — an isolated reserve-store responsibility with a testable pure
  core — NOT on line-count arithmetic. BUDGET NOTE ONLY: if any
  part of this phase instead lands in `ground_equipment.py` and the
  ratchet fires, the build pays that debt in-commit, with the real
  code open.)
- **Reload re-point** (complete call-site list, ADVISE issue 2):
  `combat/_rules_ground._reloadable_slots` + `apply_reload`
  (`_rules_ground.py:641` caller) AND `ground_reload_ui.
  reloadable_pack_slots` + `apply_reload` (`ground_reload_ui.py:81`
  caller — this gates the EXPLORATION R key via `reload_exploration`,
  `game_loop.py:483`) read the bandolier instead of pack stacks; the
  HUD reserve read `_ground_render._reserve_count` re-points or it
  shows 0 post-migration. (`_ground_ammo_reason` needs NO re-point —
  it reads only the magazine; removed from the earlier draft's list.)
- **Pickup re-point** (`loot.py` `_pack_field_item` /
  `add_item_stack` ammo branch, ADVISE issue 1): picking up an ammo
  entity refills the bandolier via `add_rounds` — over-cap ignored
  (SETTLED 2, and SETTLED 2's own wording is PICKUP-time). BOTH
  spawners (`_spawn_field_item_loot_at_position`,
  `_spawn_kit_drop`) keep spawning map entities unchanged — which
  also converts legacy on-map stack entities on pickup for free
  (ADVISE issue 8) and keeps the sim's bars untouched (stances never
  pick up).
- **Migration** (`saveload_ground.py` load path): carried pack ammo
  stacks convert into bandolier counts at their cap; overflow
  refunds credits (logged); the pack slots free up. Load-side parse
  for `bandolier`: clamp at `carry_cap`, skip unknown ammo_type keys
  (the file's existing clamp/skip conventions). Armory-STORED stacks
  (`ground_armory_items`) are NOT converted here — explicitly phase
  2's "legacy stacks" scope (ADVISE issue 9a).
- **Doc-50 seam** (`tests/balance/harness.py` + `tests/balance/
  stances.py`, ADVISE issue 7): `_ground_ammo_total` counts
  `ctx.bandolier` alongside magazines; `build_ground_loadout` seeds
  the bandolier from `PlayerSheet.ground_ammo` instead of pack
  stacks; `build_ground_ctx` gains the `bandolier` field; AND
  `stances._dry_reloadable_slot`'s reserve read re-points — without
  it every ground stance reads 0 reserve and never reloads. This is
  a BEHAVIOR-PRESERVING STORE SWAP, not a policy change: doc 50
  SETTLED 6's benchmark-revision clause is NOT triggered, and the
  checkpoint verifies it via the report DIFF (bars are ceilings —
  green tests alone would hide downward drift; ADVISE issue 4).

**Build order:** catalog caps → ctx field + serialization →
bandolier module (pure core + tests) → reload re-point (all call
sites) → pickup re-point → migration → doc-50 harness/stances seam →
full gate → PLAYTEST checkpoint.

**Binding rulings:** SETTLED 1 (caps table; build-after-51; drop
re-point in-phase; migration-with-refund). Fixed points from the
draft: independent per-type pools; plasma/melee never touch the
bandolier; magazine mechanics and the R key unchanged; multi-caliber
carried simultaneously is intended.

**Required tests:** cap clamp + multi-caliber independence (the pure
bandolier core); reload integration (dry slot reloads from
bandolier, decrements it, charges AP — update the existing reload
pins that seed pack stacks, BOTH the combat and exploration reload
paths); save round-trip (fresh saves carry the bandolier; parse
clamps + skips); migration (a pre-52 save with stacks loads to
bandolier counts + credit refund + freed slots); pickup re-point (a
dropped entity tops the bandolier on walk-over, never the pack;
over-cap ignored; a legacy pre-52 entity converts on pickup);
board bars unchanged via the report diff (same seeds, same 40
rounds).

**Stop point:** no armory restock UI (2), no pack ammo-class
retirement or market handling (2), no HUD or character-screen
readout (3), no guide edits beyond flagging the one now-stale line
(3 — see checkpoint), no `ammo_bonus` gear (4), no endurance rows or
board re-rule (5), no tutorial prose (6).

**Playtest checkpoint (numbered, in-game):**
1. Old save → Continue → the pack's ammo stacks are gone, credits
   refund logged, slots freed (pack view).
2. Any ground fight: dry a magazine, press R — reload draws from the
   bandolier (same behavior, new store).
3. Kill a sentry drone / raider whose pool drops ammo — press P by
   the drop and choose it from the loot chooser (field items are
   NEVER walk-over auto-pickup; ammo rides the same P + chooser flow
   as every field item): the bandolier tops up (no stack enters the
   pack; an over-cap pickup is silently ignored and the drop stays).
4. Sustained fight: fire past the old 40-round reserve — reloads
   keep working to the cap.
5. `make check` green; `python3 -m tests.balance.report` — the
   board's ammo numbers byte-identical to the standard's recorded
   baseline (verified by DIFF, not just green bars).
6. Guide diff: NONE this phase, but the Ground Gear line "need
   matching ammunition in your Expedition Pack" is now stale — its
   rewrite is phase 3, wording settles at this checkpoint (guide
   edits never ride silently; flagged here for review).
7. Save/load: migrated save re-saves and re-loads cleanly (sniff
   test).

### Phase 2 Implementation brief (APPROVED 2026-09-25 — SETTLED
### 2/3; builds IMMEDIATELY after phase 1 per the accepted gap)

**Scope (files / hook points):**

- **Armory restock** (`menus/_armory_buy.py` + `_armory.py`):
  RETIRE the ammunition buy section (`_buy_ammo_rows`); add RESTOCK
  rows for ALL calibers, unconditionally (SETTLED 5 — pickups and
  purchases are never gated on what you carry), quantity chosen via
  the modal, priced rounds-chosen × `price_per_round` (SETTLED 2).
  Restock row labels are player-facing strings — prose gate applies
  (settled at this phase's checkpoint).
- **Quantity modal fast keys** (the shared `pygame_quantity` modal,
  `menus/_armory.py`'s existing instrument): left/right stay ±1;
  up/down ±10; PageUp/PageDown min/max; the modal OPENS pre-filled
  at min(affordable, space-to-cap) (SETTLED 5; benefits every
  quantity consumer — armory, trade). Input-path tests for the new
  keys; existing modal callers stay green.
- **Armory-storage migration** (`saveload_ground.py` load path,
  extending phase 1's): `ground_armory_items` ammo stacks convert
  into bandolier counts at cap + credit refund — the "legacy
  stacks" scope the ADVISE pass deferred here.
- **Pack ammo-class retirement + dead-code sweep** (ADVISE issues
  5+6): pin the STATE — after load_game / pickup / any armory
  action completes, no ammo stack persists in
  ground_expedition_items or ground_armory_items (NOT a
  construction-site pin: the load parser must keep constructing
  ammo stacks forever to migrate legacy saves, and
  item_stack_capacity's ammo branch STAYS for those records). No
  sell/market path exists for ground ammo (verified — the migration
  refund is pure gain); retire the dead ammo branches:
  `_field_item_name`/`_field_item_detail`,
  `_choose_field_item_destination`'s ammo title/pricing,
  `_purchase_field_item`'s ammo paths (`menus/_armory.py`),
  `ground_reload_ui.reload_pack_ammo` + `manage_pack_ammo` (the
  guide's "select an ammo stack... choose Reload" interaction —
  dead once phases 1+2 land), and `character_screen`'s
  `_item_stack_name`/`_item_stack_detail`/`_discard_pack_stack`
  ammo branches.

**Build order:** restock UI → armory-storage migration → class
retirement + dead-sell removal → tests → full gate → PLAYTEST.

**Binding rulings:** SETTLED 2 (per-round pricing, overflow
ignored), SETTLED 3 (back-to-back with phase 1), SETTLED 5 (all
calibers restockable; modal fast keys; tutorial gap accepted to
phase 6; 52.3/52.6 land after doc 51.5).

**Required tests:** restock pricing (chosen rounds × per-round;
the tutorial flow buys 40 rounds for 40 credits exactly as today),
restock rows for ALL calibers regardless of loadout, the modal's
fast-key handling (±1/±10/min-max, open-at-max prefill),
armory-storage migration round-trip, the state-level retirement pin
(no ammo stack persists in either container after load/pickup/
armory actions complete).

**Stop point:** no HUD/character-screen readout (3), no guide edits
(3), no endurance rows or board re-rule (5), no tutorial prose (6).

**Playtest checkpoint:** 1) A new character: buy two pistols,
restock 40 pistol rounds at the armory (fast keys + prefill make it
two presses), fight — the tutorial's credit arithmetic works
unchanged, no pack stacks anywhere. 2) An old save's armory-stored stacks convert
+ refund on load. 3) No path anywhere produces a pack ammo stack.
4) Restock price reads exactly rounds-added × per-round. 5) `make
check` green.

### Phase 2 Pre-implementation audit (2026-09-25 build session)

**1. Existing modules to extend/reuse (verified in code):**

- `pygame_quantity._handle_key` (:30) — the ONE key-mapping point; the
  fast keys land here plus `QUANTITY_HINT` (:25); `run_shared`/
  `run_for_context` (:79/:119) gain a `prefill` param clamped to
  [1, maximum]. Live callers: trade `_run_quantity_prompt` (:310 —
  planet BUY :736, SELL :744, NPC buy/sell :396/:416, jettison :843
  with price=0) and armory `_choose_field_item_quantity` (:407).
  Jettison's price=0 CONFIRMS prefill must be caller-wired, never
  modal-computed: the modal cannot distinguish buy from sell, and a
  credits//price prefill would misfire jettison at dump-everything.
  Build ruling from SETTLED 5's formula: `prefill` is an explicit
  opt-in parameter, wired at BUY sites only (restock, field-item
  buys, trade planet BUY, `_npc_buy`); SELL and jettison keep
  opening at 1.
- `bandolier.refill` (phase 1) — the one mutation path; restock
  calls it. `space_remaining` + `effective_cap` give the restock
  bound: maximum = min(affordable, space-to-cap).
- `_armory_buy._buy_ammo_rows` (:69) — retired in place by
  `_restock_rows(ctx)` (row grammar unchanged: SplitRow + price_cell
  + section_header); `_armory_left_panel`'s BUY branch (:312) swaps
  the call.
- `_migrate_pack_ammo_to_bandolier` (`saveload_ground.py:243`) —
  extends to BOTH containers via one shared per-container converter
  returning (added, refund_rounds, refund_credits); the phase-1 log
  verbatims stand, one log pair for both containers.
- `parse_item_stack` / `item_stack_capacity` (`ground_equipment.py`
  :602/:583) — STAY verbatim: the load parser constructs legacy ammo
  stacks forever, and the capacity ammo branch serves those records
  (pinned by the brief).
- Test seams: `test_armory._ammo_purchase_context` (fake ctx
  factory), `as_async`/`run` (tests/support/asyncutil),
  test_pygame_ui's local FakePygame key constants (:1082-1096) —
  extend with LEFT/RIGHT/PAGEUP/PAGEDOWN. `_choose_field_item_
  quantity`'s maximum<1 guard (:418) is the model for the restock
  full/unaffordable guard.

**2. Three potential duplication hotspots:**

- Restock's flow (compute maximum → modal → charge → log) beside the
  field-item purchase family (`_choose_field_item_quantity` /
  `_purchase_field_item`) — risk of a parallel hand-rolled purchase
  path.
- The pack migration's convert-and-refund loop duplicated for the
  armory container (two copies of the refill/tally loop).
- The ammo-branch retirement repeats the same `item_type == "ammo"`
  ternary collapse across 6 functions in two files — risk of
  retiring five and missing two (parallel-paths drift).

**3. DRY strategy per hotspot:**

- Restock is a DIFFERENT transaction (bandolier refill, no container
  destination) — it gets its own small `_restock_bandolier` handler
  routed from `_apply_buy_action`, reusing `refill` as the single
  mutation and the shared modal; it does NOT ride
  `_purchase_field_item` (that family mutates container stacks —
  exactly what retires). Pricing is one expression: rounds ×
  `price_per_round` (SETTLED 2).
- One `_convert_ammo_stacks(ctx, stacks)` converter (mutates only
  via `refill`, the only clamp); the migration calls it per
  container and sums tallies. No second clamp loop.
- Grep-driven sweep: every ammo branch is enumerated below and
  removed in one retirement commit; the state-level pin (no ammo
  stack persists in either container after load/pickup/armory
  action) is the drift guard.

**Retirement call-site list (complete, from grep):**

- `menus/_armory.py`: `_buy_ammo_rows` re-export (:18) + BUY-panel
  call (:314); `_field_item_name` ammo max (:165);
  `_field_item_detail` ammo price/effect (:168-187);
  `_choose_field_item_destination` ammo title/unit/price
  (:369-387); `_field_item_purchase_maximum` ammo price (:396);
  `_choose_field_item_quantity` ammo price (:421);
  `_purchase_field_item` ammo default + unit price + "afford that
  ammunition" line (:426-441); `_apply_buy_action`'s BUY_AMMO branch
  (:919-933) → RESTOCK routing.
- `character_screen.py`: `_item_stack_detail` ammo branch
  (:312-313); `_manage_pack_stack` ammo dispatch (:648-650);
  `_manage_pack_ammo` (:656-682). Brief-name correction: the brief
  says "`ground_reload_ui.reload_pack_ammo` + `manage_pack_ammo`" —
  grep shows `reload_pack_ammo` NO LONGER EXISTS (doc 51.3 removed
  it) and `_manage_pack_ammo` lives in character_screen.py, not
  ground_reload_ui.
- Tests converting: `test_armory.py` :115-119 (ammo buy-row pins →
  restock pins), :139-159 (field-item rows fixture → consumables-
  only), :162-196 + :217-236 (ammo purchase pins → restock/consumable
  pins), `test_pygame_ui.py` :213-216 (`_manage_pack_ammo` pins),
  `test_saveload.py` :1328-1355 (armory-stack round-trip → migration
  pin), :1357-1416 (armory stack stays → converts; the
  pre-52 migration pin gains the armory leg), :1466-1502 (malformed
  armory stacks survive → convert).
- Stays verbatim: `parse_item_stack`/`item_stack_capacity` ammo
  branch (legacy records), `loot.py` spawners + the phase-1 pickup
  re-point, `_discard_pack_stack` (type-generic), trade's SELL/
  jettison modal calls (prefill deliberately not wired).

**Budget note (ratchet):** `_armory.py` sits at 998/1000 — the
RESTOCK handler + routing arrives net-positive against the ternary
collapses; if the module crosses 1000 the in-commit refactor
extracts the field-item purchase family (or the restock handler)
into a cohesive sibling of `_armory_buy`. Measured at build, paid
in-commit.

**Guide sweep (phase-2 scope):** every ground-ammo/armory guide hit
(:249, :271-272, :294-300) is already classified in the phase-3
brief's three-edit audit; the quantity modal's keys appear NOWHERE
in the guide (the modal's own hint line is the only teacher) — so
the hint rewrite is the modal's business, quoted at this phase's
checkpoint as a player-facing string. No phase-2 guide edits.

### Phase 2 build record (LANDED 2026-09-25 — PLAYTEST PASSED)

**Playtest: PASSED 2026-09-25 (user).** All checkpoint items — the
tutorial arithmetic (40 pistol rounds for exactly 40 credits), fast
keys + prefill ("two presses" confirmed in play), the old-save
armory migration, at-cap/unaffordable guards, and the
no-pack-stacks-anywhere state. The seven prose verbatims were
exercised in play unamended and stand as shipped. Mid-playtest
events, all recorded below: the RESTOCK dispatcher crash (7decd373),
the Pack-footer miscount + "Armory: unlimited" tail ruling
(0a624777), and the at-cap pickup line ruling (f73783aa). KEPT (no
ruling after two flags): the ARMORY view's empty-row "Armory Storage
is unlimited and shared between terminals." — revisit on request.

**Commits:** 4a9b7304 (pre-implementation audit) → fd81d32e
(quantity modal fast keys + buy-side prefill; trade BUY sites wired)
→ 7f82736f (armory RESTOCK replaces the ammunition buy section; pack
ammo class retires across armory + character screen; field-item
family splits to `menus/_armory_field_items.py`, paying `_armory.py`'s
ratchet 998 → 861 in-commit as the audit budget-noted) → 9504bf9a
(armory-storage migration joins the pack's on load: both containers
convert at cap via shared `_convert_ammo_stacks`, overflow refunds,
one log pair; state-level retirement pin).

**Reviewer (REVIEW): APPROVE** — six [minor], all applied
mechanically + test-pinned in the same session, no re-spawn (loop
rule): (1) `PygameQuantityQuit` now converts to `SystemExit` at both
armory modal sites (trade's existing convention — closing the window
mid-restock quits, never bubbles a RuntimeError); (2)
`_transfer_field_item` reuses `_destination_storages` (the extraction
had stopped one call site short); (3) prefill pins extended — no-
prefill opens at 1, non-positive clamps to 1, and the trade wiring is
pinned (BUY prefills at its bound, SELL passes none); (4) the
consumable-buy guard splits its conflated message (cannot-afford vs
destination-full, reusing restock's afford line verbatim); (5) the
new module renamed `_armory_items` → `_armory_field_items` (name
collision with `_armory._armory_items(ctx)` was a patch-time trap);
(6) prose verbatims quoted below. The reviewer independently re-ran
the test cohorts, re-derived the refund arithmetic (200 pistol → 160
cap + 40cr; 12 rockets → 10 cap + 40cr; 12 rifle under cap →
"Packed 182"/"Refunded 42 ... 80$."), verified zero surviving dead
references by rg, and confirmed no ammo-stack creation path survives
(loot → refill, armory → literal "consumable", dev grants →
consumables, migration strips both containers).

**Rulings made at build time (from SETTLED 5's wording, surfaced for
the playtest):** prefill is an opt-in parameter wired at BUY sites
only — the modal cannot distinguish buy from sell (jettison passes
price=0; a modal-computed credits//price prefill would misfire sells
and dump-everything jettisons). PLUS/EQUALS/MINUS and vim H/L join
LEFT/RIGHT as the +/-1 fine keys (the old +/-1 arrows UP/DOWN/K/J
become the +/-10 coarse keys).

**Doc-50 board: no report diff run this phase** — phase 2 changes no
reload or combat path (stances never shop); the phase-1
byte-identical board stands.

**Playtest finding (fixed 7decd373, checkpoint item 1):** selecting
any RESTOCK row crashed — `ValueError: Unknown armory action` from
`_apply_pygame_armory_action`, surfaced by the split runner as
"Pygame split frame could not be rebuilt". ROOT CAUSE: RESTOCK was
wired into `_apply_buy_action` but never into the dispatcher above
it; every restock pin called the handler directly, bypassing the
dispatch frame — and the REVIEW verified the transaction, not the
entry routing. Fix: the dispatcher's buy branch takes
`("BUY_", "RESTOCK:")`; new dispatcher-level pin fails pre-fix and
passes post-fix. Playtest resumes from checkpoint item 1.

**Playtest finding + ruling (fixed 0a624777, mid-playtest):** the
armory footer read `Pack: 4/8` against a full 8/8 backpack — the
footer counted EQUIPMENT ONLY while the `[E]xpedition` tab beside it
counted equipment + field-item stacks (pre-existing disagreement,
surfaced now that stacks are consumables-only). USER RULING: the
footer's `Armory: unlimited` tail is DROPPED from the UI entirely.
Footer now `Pack: {equipment+stacks}/{capacity}`; both surfaces
pinned at the same count. KEPT (flagged for the checkpoint): the
ARMORY view's empty-row explanation "Armory Storage is unlimited and
shared between terminals." — different string, explains storage
scope; extend the ruling there if wanted.

**Playtest ruling — at-cap pickup speaks (phase 1's parked
question, ANSWERED):** the user ruled from play ("I do want a short
message when you try to pick up ammo that you don't have room to
carry"). An explicit P + chooser pick that cannot fit logs
`Your {name} reserve is already full.` — VERBATIM the armory
restock guard's line (one wording per state, both paths); the drop
still stays on the floor and SETTLED 2's no-credits stand.
Supersedes the phase-1 build-time silence ruling for the explicit
pickup path; the doc-52.1 pin converted from
`..._is_silently_ignored` to `..._logs_full_and_stays_on_floor`.

**Prose gate — new/changed player-facing strings, landing at this
checkpoint for sign-off (verbatims):**
1. Quantity modal hint (pygame_quantity.py): `LEFT/RIGHT +/-1,
   UP/DOWN +/-10, PGUP/PGDN min-max` (was `UP/DOWN adjust`).
2. Restock row detail (_armory_buy.py): `Reserve {current}/{cap}
   {price}$/round` (e.g. "Reserve 132/160  1$/round"); section
   header stays `AMMUNITION`; row label = the caliber name.
3. Restock modal label (_armory_field_items.py): `RESTOCK {name}`.
4. Restock at cap: `Your {name} reserve is already full.`
5. Restock unaffordable: `You cannot afford {name}.` (also now the
   consumable-buy guard's afford branch).
6. Restock purchase: `Restocked {added} {name} for {cost}$.`
7. Consumable re-check tail (_armory_field_items.py): was `You can
   no longer afford that ammunition.`, now `You can no longer afford
   that consumable.`

### Phase 3 Implementation brief (APPROVED 2026-09-25 — SETTLED 4
### + the user's HUD-scope amendment; AMENDED 2026-09-25 pre-build,
### user — exploration weapons block + split Equipment tab, below)

**Amendment (2026-09-25, user — pre-build design pass):**

- **Exploration weapons block (scope ADD):** "now that we have X and
  R available outside of combat, I'd like to show the same
  weapon/ammo lines outside of combat too." The DUNGEON-mode HUD
  (`hud.py::_render_city_hud`, the mode-gated help lines are the
  precedent) gains the weapons block: one row per active-set weapon
  (name + magazine cur/cap — no combat volley checkboxes, no
  HIT line: no target outside combat), the dim HOLSTER names row,
  then the shared per-caliber ammo lines (same label family as the
  combat block). City mode stays as-is (the armory + C screen serve
  the city loadout view). X swap (game_loop, non-space) and R reload
  (dungeon) already work beside it.
- **Equipment tab becomes the split UX (replaces the paged-list
  section insertion):** "left column is the current equipment tab.
  right column is the ammo info. using the same split screen
  multi-col ux experience we already have." The Equipment tab
  renders as a `pygame_split` two-column frame — LEFT: the equipment
  rows exactly as today (weapon-set sections, ARMOR, backpack; same
  actions, same management gating); RIGHT: the BANDOLIER readout
  (all six calibers, full names, current/max via `effective_cap`,
  plus which equipped weapons feed each shown caliber). TAB/
  SHIFT-TAB keep cycling the C tabs on every tab; the right column
  is a READ-ONLY panel (nothing to select — no panel-focus key
  needed, no keymap changes to the C screen).
- **Defaults folded from the design pass — READ-ONLY right column
  and the 3-letter codes USER-CONFIRMED 2026-09-25 ("right col read
  only. we'll go with the 3 letter codes for now. I'll adjust if I
  get confused."); the active+holstered union stands as the folded
  default, veto at the checkpoint:** HUD caliber labels are
  PST/RFL/CEL/SHL/GRN/RKT
  (matching the AP/EVA/HIT abbreviation voice; the C screen carries
  full names); the combat block shows the UNION of active + holstered
  calibers (SETTLED 4's "equipped weapons" reads as both carried
  sets in doc-51 terms — X-swap reveals a reserve already on
  screen).

**Scope (files / hook points):**

- **Combat HUD** (`combat/_ground_render.py`): the reserve read
  (re-pointed in phase 1) renders as current/max for the RELEVANT
  (carried) calibers — one line per caliber the equipped weapons
  use (SETTLED 4). MAX SOURCE: this and the character screen read
  max from `bandolier.effective_cap(...)` (the phase-1 seam), never
  `spec.carry_cap` directly — the deferred gear pass then lights up
  with zero HUD rework (ADVISE issue 10). COORDINATION (issue 9):
  doc 51 phase 2 adds a compact holstered-set indicator to the same
  weapons panel — the caliber lines' placement relative to it and
  the panel's line budget is settled against the LANDED doc-51 HUD,
  named in this phase's build.
- **Character screen** (`character_screen.py`): per the 2026-09-25
  amendment, the equipment tab renders as the SPLIT UX — LEFT column
  the equipment rows exactly as today (weapon-set sections, ARMOR,
  backpack rows; same actions and management gating), RIGHT column
  the FULL bandolier: all six ammo types with current/max (user
  amendment: "character screen equipment tab needs to show all ammo
  types somewhere") — the inventory view the HUD deliberately
  omits — plus which equipped weapons feed each shown caliber.
  Right column is read-only; TAB/SHIFT-TAB keep cycling the C tabs.
- **Exploration HUD** (`hud.py`): per the same amendment, the
  DUNGEON-mode branch of `_render_city_hud` gains the weapons block
  — one row per active-set weapon (name + magazine cur/cap; no
  volley checkboxes or HIT line — no target outside combat), the
  dim HOLSTER names row, then the shared per-caliber ammo lines in
  the combat block's label family. City mode unchanged.
- **Guide** (`data/guide/__init__.py`) — THREE edits, exact
  before/after (prose-gated — settles at this phase's checkpoint):
  1. GROUND GEAR, the ammunition paragraph (the "matching
     ammunition in your Expedition Pack" line flagged stale since
     phase 1; "Buy ground ammo at the Armory" becomes restock
     phrasing; the pack-stack preparation sentence goes — the
     interaction no longer exists):
     BEFORE: "Reloadable weapons need matching ammunition in your
     Expedition Pack. Buy ground ammo at the Armory, then press R
     in ground exploration or combat to reload. In combat, R
     reloads the first active weapon with room in its magazine and
     a matching reserve. Outside combat, reloading is free; select
     an ammo stack in the Equipment tab and choose Reload when you
     want to prepare a weapon. If multiple carried weapons can use
     the reserve outside combat, R opens a chooser. Melee and
     plasma weapons never need ammunition."
     AFTER: "Reloadable weapons draw from your bandolier — the
     rounds you carry for each caliber, topped up at any armory or
     from battlefield pickups, up to a per-caliber carry limit. In
     combat, R reloads the first active weapon with room in its
     magazine. Outside combat, reloading is free. If multiple
     carried weapons can use the reserve outside combat, R opens a
     chooser. Melee and plasma weapons never need ammunition."
  2. GROUND COMBAT section (audit catch, 2026-09-25 — missed by the
     first brief): "press R to reload from the ammunition in your
     pack" is equally stale.
     BEFORE: "Weapons with a magazine consume rounds as you fire;
     press R to reload from the ammunition in your pack."
     AFTER: "Weapons with a magazine consume rounds as you fire;
     press R to reload from your bandolier."
  3. GROUND GEAR intro (audit catch): "sells ... ground
     ammunition" describes the retired stack purchase.
     BEFORE: "The armory terminal sells personal weapons, armour,
     and ground ammunition for when you leave your ship."
     AFTER: "The armory terminal sells personal weapons and armour
     for when you leave your ship, and tops up your ammunition
     reserves."
  Checkpoint wording notes (ADVISE issue 8): the AFTER consciously
  drops "and a matching reserve" from the combat-R sentence (an
  empty bandolier still fails R — deliberate simplification,
  surfaced for review); "multiple carried weapons" aligns with doc
  51's ACTIVE-set terminology at the wording checkpoint (the
  chooser enumerates active-set weapons only).
  Verified-unchanged lines (the audit's other finds): Controls
  "R: reload your active weapon" (store-agnostic), the
  kinetic/energy/explosive/melee bullets ("limited ammunition",
  "never run dry", "Rockets are scarce" — all still true, some
  MORE true under caps), the exploration tip "Press R to reload a
  carried ground weapon", and every space-ammo line (missiles —
  doc 52 is ground-only).

**Build order:** combat HUD lines → exploration weapons block →
split equipment tab → guide paragraphs (user-approved wording) →
tests → full gate → PLAYTEST.

**Binding rulings:** SETTLED 4 (carried calibers only); the 2026-09-25
pre-build amendment (exploration weapons block; split Equipment tab;
folded defaults: PST/RFL/CEL/SHL/GRN/RKT HUD codes, active+holstered
caliber union, dungeon-mode-only exploration block); the guide
contract (diff rides this checkpoint verbatim); the prose gate
(wording approved before the data string lands).

**Required tests:** combat HUD renders current/max for carried
calibers only (a pistol pair shows one line; plasma/melee show
none); dungeon HUD renders the weapons block + ammo lines (city
mode renders none); equipment tab renders BOTH columns — left
actions unchanged, right shows ALL six calibers' current/max,
read-only; guide-content pins for all three rewritten passages.

**Stop point:** no gear seam work (4 is deferred), no rows (5), no
tutorial prose beyond the guide (6).

**Playtest checkpoint:** 1) In a ground fight with pistols: the HUD
shows e.g. 132/160; a reload visibly decrements it. 2) Plasma or
melee equipped: no ammo line. 3) Exploring a dungeon (no combat):
the same weapons/ammo block is on the HUD; X swaps sets, R reloads
against the shown counts. 4) Character screen equipment tab: two
columns — left unchanged equipment management, right all six
calibers (current/max each, carried or not, read-only).
5) GUIDE DIFF (before/after, exact —
   all three edits above). 6) `make check` green.

### Phase 3 Pre-implementation audit (2026-09-25 build session)

**1. Existing modules to extend/reuse (verified in code):**

- `hud.py` — the shared HUD module the combat renderer ALREADY
  imports from (`_ground_render` pulls `_bar_str`,
  `_render_action_pairs`, colors): the caliber-line and holster-names
  builders land THERE so combat and dungeon read one source. hud.py
  sits at 997/1000 — the dungeon weapons block trips the ratchet →
  the SPACE-COMBAT HUD family (`render_combat_hud` + its private
  helpers + combat palette, ~330 lines, untouched by this phase)
  extracts to `hud_combat.py` in-commit, with the three external
  consumers repointed to the new module (combat/_animations.py,
  combat/_rules_space.py, test_readability) — NO re-export, keeping
  the navigation.py sibling-never-imports-hub DAG (a hud→hud_combat
  re-export would partial-init-crash whenever hud_combat imported
  first; corrected post-review — the original audit draft said
  "re-exporting", the landed shape is repointing).
- `pygame_split.py` — the split UX family the amendment names. Its
  armory runner consumes TAB for panel focus; the C screen needs
  TAB = tab cycle with a read-only right panel → a SECOND entry
  point (`run_for_screen`) returning pygame_screen's outcome
  vocabulary + 3-tuple shape, plus `screen_tabs`/`active_screen_tab`
  frame fields drawn via the shared `pygame_screen.draw_tab_bar`
  (the one tab treatment), with `_frame_height` reserving the
  tab-bar height (font-ladder contract: the split's fixed reserve
  must fit at the ladder top; the 11/13 row caps stay split).
  `_draw_frame` gains a `selected` override so flag-selectable
  action-less rows (the C screen's non-management equipment rows)
  highlight correctly WITHOUT touching the armory's action-based
  key semantics (phase-2's RESTOCK dispatcher crash is the
  cautionary tale for divergent entry routing).
- `character_screen_weapons._weapon_rows` +
  `character_screen._equipment_rows` — the LEFT column verbatim; a
  ScreenRow→SplitRow converter (header→divider) at the frame builder
  leaves every row builder and its pins untouched.
- `bandolier.effective_cap` — the ONLY max source for the HUD and C
  screen (ADVISE issue 10); `ground_weapon_ammo.reserve_ammo_count`
  reads current. `character_screen_weapons._weapon_ammo_indicator`
  (the `[loaded/cap]` suffix) MOVES to `ground_weapon_ammo.
  magazine_indicator` — the engine owns magazine presentation and
  its base-spec capacity is what reload actually fills; hud must not
  import upward into character_screen_weapons; the old site
  re-imports.
- Dungeon R/X verified live before building on them:
  `game_loop.py:280` (`_swap_weapon_sets_explore`, non-space) and
  `:331` (`reload_exploration`, dungeon). `render_hud(mode=
  "dungeon")` flows through `pygame_overlay._render_hud_capture` —
  no call-site changes; the block gates inside `_render_city_hud`.

**2. Three potential duplication hotspots:**

- THREE renderers of carried-caliber readouts (combat panel, dungeon
  block, C right column) drifting on labels, max source, or order.
- TWO weapon-list presentations gaining near-identical rows (combat
  weapon blocks vs dungeon name+mag rows) beside the C screen's — a
  third copy of the `[loaded/cap]` format is the trap.
- The Equipment tab's split frame beside the Stats/Cargo
  ScreenFrames — a bespoke tab cycle/keymap for one tab (parallel
  runner drift, the phase-2 dispatcher class).

**3. DRY strategy per hotspot:**

- `bandolier.HUD_CODES` (ammo_type → PST/RFL/CEL/SHL/GRN/RKT, the
  user-confirmed codes) + `bandolier.carried_ammo_types(weapons)`
  (catalog-ordered union of the active+holstered sets, pure) +
  `hud.bandolier_hud_lines(ctx)` (cur/max via `effective_cap`) —
  combat and dungeon call the same builders; the C right column
  reuses `carried_ammo_types`/`effective_cap` in its full-name
  label family (SETTLED 4's split: codes on the HUD, full names on
  the C screen).
- `ground_weapon_ammo.magazine_indicator` (moved, one formatter) +
  `hud.ground_holster_names(ctx)` (one holster-names source;
  combat's `_print_holster_row` re-points to it).
- The split gains a RUNNER, not a keymap fork: `run_for_screen`
  emits pygame_screen's outcomes, so `_advance_character_screen`
  and the host loop stay untouched (tab-treatment contract:
  outcomes advance the host's sheet).

**Placement rulings named at build (per the brief's issue-9
coordination note):** doc 51's landed holstered indicator IS
`_print_holster_row` — the caliber lines go directly AFTER it at the
end of the combat weapons panel (≤4 lines, one per union caliber,
dim, aligned with the weapon-detail indent); the per-weapon AMMO
line drops its `RES` suffix (the caliber lines supersede it — the
phase-1 "transient until phase 3" read retires, `_reserve_count`
goes with it). The dungeon block sits between the stat rows and the
help lines (the dungeon's terminal section is empty); worst case is
≤10 rows (1 header + 4 weapon rows + 1 holster + 4 caliber lines —
corrected post-review from the draft's ≤8; the layout still fits
with the help lines and footer anchored below).

**Guide BEFORE-correction (verified against the live file):** the
brief's BEFORE for edit 1 quotes a "select an ammo stack in the
Equipment tab and choose Reload" sentence that phase 2's dead-code
sweep already removed — the AFTER lands verbatim on the current
text. The AFTER's em-dash lands as `" - "` (the guide's CP437-safe
convention, doc 45's bitmap gate — no em-dash anywhere in the guide
today); flagged at the checkpoint.

**Budget note (ratchet):** hud.py 997/1000 pays in-commit via the
`hud_combat.py` extraction above; character_screen.py 895 +
~50 (split frame builder + converter) stays under; pygame_split.py
583 + ~90 (runner + fields + override) stays under; every touched
function stays ≤40 lines.

### Phase 3 build record (LANDED 2026-09-25 — PLAYTEST PASSED)

**Playtest: PASSED 2026-09-25 (user).** All checkpoint items — the
combat caliber lines (visible decrement on R), plasma/melee silence,
the dungeon weapons block with live X/R, the split Equipment tab
(read-only Ammo column, cursor visible unmanaged, TAB cycling), the
guide's three rewrites, and the huge-fight ACTIONS cap. The UNION
default was NOT vetoed (active+holstered calibers both show). The
retired body sentences stay retired (no restore requested — the
hint + row choosers teach the actions). Two mid-playtest rulings
landed and are recorded below (feeder-free aligned column;
"bandolier" leaves player-facing text); every standing verbatim —
the `PST …` line family, `Ammo is read-only`, the `ammo storage`
wording — was exercised in play and stands as shipped.

**Commits:** 552fe130 (pre-implementation audit) → 60ab1952
(`bandolier.HUD_CODES` + `carried_ammo_types`;
`magazine_indicator` moves to `ground_weapon_ammo`) → 7b6e331e
(hud.py ratchet paid: the space-combat HUD family extracts verbatim
to `hud_combat.py`; the three external consumers repointed, NO
re-export — sibling-never-imports-hub DAG) → 0ca508ae (combat
weapons panel gains the per-caliber current/max lines after the
holster row; the per-weapon `RES` suffix retires with
`_reserve_count`; shared builders `bandolier_hud_lines` +
`ground_holster_names` land in hud) → ef877927 (dungeon weapons
block: active rows name+magazine, dim holster names, shared caliber
lines; fists floor silent; city mode unchanged) → 36535c24 (the
Equipment tab becomes the split UX: `pygame_split.run_for_screen`
with pygame_screen outcomes + flag-based left selection,
screen-tabs chrome with an honest 46px font reserve, right column =
all six calibers read-only with feeder names) → be84ec9e (guide ×3)
→ ec77e516 + eb09fac1 + bd8eecf2 (reviewer fixes, atomically split).

**Reviewer (REVIEW) — three rounds:**
- **Round 1** (full range): REQUEST_CHANGES — one blocking
  (flag-selectable action-less rows never painted a cursor: the
  screen contract's rows are exactly the action-less ones, so the
  unmanaged Equipment tab's cursor was invisible) + five minor (lost
  body sentences; dead `floor_available` param; two stale doc lines;
  enemies panel missing the space family's bottom cap).
- **Round 2** (fix commit): REQUEST_CHANGES — issues 1/3 confirmed
  resolved, but the cap fix itself was WRONG: anchored to
  SCREEN_HEIGHT (the ground HUD owns only rows 0-53; the message
  band owns 54-59) and under-counted the ACTIONS tail (5 rows +
  spacer, not 3) — the legend landed in the message band exactly
  when the cap engaged, and the pin locked a vacuous bound.
- **Round 3** (corrected cap, commits split atomically per the
  hygiene minor): **APPROVE** — "the cap is correct and tight (43 =
  the tightest safe value; the worst stack ends flush at row 53;
  loosening to 44 would push into the message band)". Remaining
  minors recorded, none blocking: (a) the paint pin locks the gate
  and the `_draw_frame`→left-panel hop but no test drives
  `run_for_screen` itself (hop 1 is unlocked — stated residual, not
  claimed away); (b) the true worst case (3-detail armed target at
  the boundary row) is covered by derivation + the
  `_ENEMY_BLOCK_ROWS` constant, not an executed assertion (the
  `== 45` drift guard fires on any loosening); (c) reviewer numeric
  corrections adopted: the max real caliber union is THREE lines
  (only two 1H calibers exist — PST, CEL), so the audit's ≤4 is a
  safe over-estimate.

**Rulings made at build time (surfaced for the playtest):**
- **Playtest feedback (mid-checkpoint, 2026-09-25):** the bandolier
  column's feeder suffixes ("Rockets 8/10 (Rocket Launcher)" — user:
  "that's weird. remove it.") are REMOVED, and the counts are
  COLUMN-ALIGNED (name column padded; cur, "/", cap each own a
  right-justified column) — the variable-length suffixes were also
  what broke the count alignment ("it's all over the place with 0
  alignment"). The brief's "which equipped weapons feed each shown
  caliber" clause is retired by this ruling.
- **Playtest feedback (mid-checkpoint, 2026-09-25, second ruling):**
  the player NEVER sees the word "bandolier" — it stays as code
  vocabulary. The Equipment right panel's title is "Ammo"; every
  other player-facing reference uses "ammo storage": the guide's
  ammunition paragraph ("draw from your ammo storage") and Combat
  R line, the reload error (now "No {ammo_type} ammo in storage"),
  and the migration line ("Packed {n} reserve rounds into ammo
  storage."). Supersedes the shipped 52.1 verbatims for the two log
  lines and the 52.3 guide wording's use of the word.
- The per-weapon AMMO line dropped its `RES` suffix — the caliber
  lines own the reserve read (the phase-1 "transient RES" rework).
- The dungeon block renders only when some weapon is carried (the
  fists floor stays silent, doc 51 SETTLED 2).
- The Equipment split's chrome: left label "Equipment", right label
  "Bandolier", footer_left `Expedition Pack: {used}/{capacity}`,
  footer_right `Ammo is read-only`; the hint keeps the C screen's
  existing NAV/ENTER swap/TAB stats/ESC/? family (management-gated
  "ENTER swap").
- The old Equipment body sentences are GONE pending checkpoint
  ruling: "Select a row and press ENTER to equip, use, or discard."
  and "Equipment is read-only outside management mode." (the split
  has no body; the hint and the per-row choosers teach the actions).
  Restore as footer/hint wording at the checkpoint if missed
  (reviewer minor, round 1).
- Equipment section rows now carry `header=True` (the converter
  renders them as split dividers); "(occupied by 2H)" and "[empty]"
  stay informational rows.
- The enemies listing cap is NEW behavior: huge fights stop listing
  so the ACTIONS legend stays on the HUD (derivation in
  `_ground_render._ENEMY_LIST_BOTTOM`'s comment).

**Prose gate — new/changed player-facing strings, landing at this
checkpoint for sign-off (verbatims):**
1. Guide ×3 passages — exact BEFORE/AFTER below at the checkpoint.
2. HUD caliber lines (combat + dungeon):
   `{PST|RFL|CEL|SHL|GRN|RKT} {current}/{cap}` (user-confirmed codes).
3. Dungeon block: `WEAPONS` header; `{Weapon Name} [{loaded}/{cap}]`
   rows; `HOLSTER  {names}` (existing vocabulary, new surface).
4. Equipment split: labels `Equipment` / `Bandolier`; footer
   `Expedition Pack: {used}/{capacity}` / `Ammo is read-only`.
5. Wording note: the approved AFTER's em-dash ("bandolier — the
   rounds") renders as `bandolier - the rounds` — the guide's
   CP437-safe convention (no em-dash anywhere in the guide today).

**Guide BEFORE-correction (found at build):** the brief's edit-1
BEFORE quoted a "select an ammo stack in the Equipment tab and
choose Reload" sentence phase 2 had already removed — the AFTER
lands verbatim on the live text.

**Tests added:** carried-union/catalog-order/dedupe + HUD-code
completeness pins (test_bandolier); combat caliber-line pins ×4 +
AMMO-suffix retirement + enemies-cap pins (test_ground_weapon_sets);
dungeon-block pins ×3 (test_hud); split screen keymap, paint
contract (sabotage-proven), flag threading, screen-tabs font
reserve, and the Equipment split-frame pins (test_pygame_ui);
guide-content pins ×3 (test_help_guide). Cohorts + full gate green
throughout (3026 passed at close).

### Phase 6 Implementation brief (PROPOSED 2026-09-25 — SETTLED 6;
### amended per the ADVISE pass (all five issues folded); wording
### ruled in-session, prose gate satisfied; doc 52's last phase)

**Scope (files / hook points):**

- **`src/spacehack/tutorial.py` ONLY** — the same file-only shape as
  doc 51.4's teaching brief. Two edits:
  1. `_STEP_BODIES["earth_armory"]` (:158-168), the stale clause —
     prose gate: user-approved wording, verbatim (SETTLED 6):
     BEFORE: `"...and buy two Kinetic Pistols, a Combat Knife, and a
     stack of Pistol Rounds.\n\n"`
     AFTER: `"...and buy two Kinetic Pistols and a Combat Knife, then
     restock your Pistol Rounds.\n\n"`
     Everything else in the beat is live-accurate and UNTOUCHED — the
     12-damage volley sentence, the R-reload sentence ("Kinetic guns
     need ammo - press 'R' to reload when a magazine runs dry."), and
     doc 51's sets/X teaching. Full-corpus verification (done at this
     refine): this is the ONLY stale player-facing clause in
     tutorial.py; no body contains "bandolier" or "reserve"; "Melee
     weapons never need ammunition." stays true.
  2. The `TUTORIAL_CREDIT_BONUS` comment block (:27-31; ADVISE issue 5
     — :26 is blank): the "40-round Pistol Rounds stack (40$) = 130$"
     arithmetic is stale — rewrite to the restock world (gear 90$
     leaves ~145$; the restock prefill offers min(affordable,
     space-to-cap) ≈ 145 rounds at 1$/round; the popup deliberately
     names no count — rounds-vs-armor margin is the player's choice).
     Dev-facing, rides the same phase.
- **`tests/test_tutorial.py`** — the content pin at :91 updates to
  the new clause verbatim (it rides the PROSE commit — see build
  order). `"a stack of"` gets its OWN small 52.6 corpus test: the
  existing banned-phrase loop is `test_stale_slot_sentence_gone`
  inside `TestDoc51WeaponSetCopy` (:103-106), named and docstringed
  for doc 51's slot sentence — a 52.6 concern doesn't smuggle into it
  (ADVISE issue 4).
- **Guide: NONE.** 52.3 landed the guide's three rewrites; the
  tutorial popup is not the guide. The build greps
  `src/spacehack/data/guide/__init__.py` for stack-buy vocabulary as
  verification and reports the none-found result on the checklist
  (guide diffs never ride silently — here the diff IS none, verified
  and stated; ADVISE note: the guide corpus lives at that path, not
  repo-root data/).
- **Cross-doc annotation** (`docs/design/in_progress/
  50_DESIGN_COMBAT_BALANCE_SIMULATOR.md`, SETTLED 4's parenthetical
  at :169-170; ADVISE issue 3): doc 50 defines its first ground
  scenario as "the loadout the tutorial itself teaches (two Kinetic
  Pistols + a stack of Pistol Rounds)" — the parenthetical goes stale
  when this phase lands (the taught LOADOUT is unchanged; the
  stack-buy phrasing is gone). One-line annotation rides this phase
  so the stale clause doesn't travel into doc 50's re-measure passes
  — doc 50's resumption is the very next event after doc 52 closes.

**Build order:** body clause + its :91 pin update (ONE commit — the
prose commit; committing the clause without its pin leaves
`make check` red, and a pin on the prose is not a "mechanical rider"
in the gate's sense — ADVISE issue 1) → comment rewrite + the 52.6
corpus test + the doc-50 annotation → full gate → PLAYTEST.

**Binding rulings:** SETTLED 6 (the verbatim wording; phase 5's move
puts all balance work out of scope); the 52.3 playtest ruling
("bandolier" never player-facing — binds the tutorial; the approved
wording complies); SETTLED 5's landing-order pin (satisfied — doc
51.4's teaching landed and retained the stack clause for this phase
to rewrite once).

**Required tests:** the updated earth_armory content pin (new clause
verbatim); a DEDICATED 52.6 corpus test asserting no `_STEP_BODIES`
entry contains `"a stack of"` (the doc-51-named loop at :103-106 left
alone); the doc-51 wording pins at :92-93 stay green UNTOUCHED —
proof the phase changes one clause and nothing else; no new
machinery.

**Stop point:** no other tutorial step copy (doc-51-fresh prose
stands), no guide edits, no armory/HUD/code behavior changes, no
save-format changes (step KEYS unchanged — bodies are static copy),
no balance/rows work (phase 5 lives in doc 50 — this phase's ONE
doc-50 touch is the annotation above, nothing else), no dev-mode
changes. `tutorial.py` + its pins (and the one-line doc-50
annotation) ONLY.

**Playtest checkpoint:** 1) Fresh tutorial game (new Human Merchant
run) → reach Earth's armory beat: the popup reads the new wording.
2) Follow it: buy two Kinetic Pistols + Combat Knife (~90$), open the
AMMUNITION section, RESTOCK Pistol Rounds (modal prefills; fast keys
work), land on Mars with rounds in reserve and credits to spare.
3) The beat's remaining sentences (volley/R/X) read unchanged.
4) GUIDE DIFF: none (grep-verified at build against
`src/spacehack/data/guide/__init__.py` — stated on this checklist).
5) Doc 50's SETTLED 4 parenthetical annotated (one line: taught
loadout unchanged, stack phrasing gone). 6) Save → quit → Continue
mid-tutorial: the beat's state is unchanged (nothing stateful moved).
7) `make check` green.

## Open questions

1. ~~**`ammo_bonus` shape**~~ ANSWERED — SETTLED 4: deferred to the
   future armor/cybernetics polish pass; doc 52 ships the seam only.
2. ~~**Cap levels**~~ ANSWERED — SETTLED 1: the proposed table
   confirmed as-is.
3. ~~**Overflow pickups**~~ ANSWERED — SETTLED 2: ignored.
4. ~~**Restock pricing**~~ ANSWERED — SETTLED 2: per-round.
5. ~~**Sequencing with doc 51**~~ ANSWERED — SETTLED 1: after doc
   51's core lands.
6. ~~**Bandolier visibility off-load**~~ ANSWERED — SETTLED 4 +
   same-day amendment: HUD = relevant (carried) calibers;
   character screen = all six.
7. ~~**The armory gap (ADVISE issue 5)**~~ ANSWERED — SETTLED 3:
   the one-session gap is accepted (phases build back-to-back).
8. ~~**Phase 5 sequencing** (posed 2026-09-25: pin endurance rows
   now, or fold into doc 50's resumption? — doc 51 SETTLED 4's
   removal of the re-rule phase made the original "coordinated with
   doc 51's re-rule" clause stale, and doc 50's queue waits on doc
   52's close)~~ ANSWERED — SETTLED 6: moved to doc 50's resumption.
9. ~~**Phase 6 wording: teach a round count or stay agnostic?**~~
   ANSWERED — SETTLED 6: agnostic, verbatim "then restock your
   Pistol Rounds." (the modal's prefill + fast keys are the teacher).
