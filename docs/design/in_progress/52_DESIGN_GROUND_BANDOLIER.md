# DESIGN: The Bandolier — tracked ammo reserves, never in the pack

**Status: DRAFT for review (2026-09-25) — rulings captured from the
doc-50 tuning session; not yet refined, no briefs, nothing
implemented. Companion wave to doc 51 (ground weapon sets).**

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
  caliber, with and without the cap gear.

## Phases

- [ ] 1. **Bandolier core** — caps on the catalog, ctx field,
  serialization + pack migration, reload draw path re-point, drop
  re-point (SETTLED 1 scope amendment). Tests: round-trip incl.
  migrated saves, cap clamps, multi-caliber independence, reload
  integration, plasma/melee untouched.
- [ ] 2. **Economy surfaces** — armory restock-to-cap, pack
  ammo-class retirement, market/sell handling for legacy stacks.
  Tests: restock pricing.
- [ ] 3. **HUD + guide** — bandolier line(s), Ground Gear paragraph,
  plasma/melee identity wording check. Guide diff rides the phase
  checklist.
- [ ] 4. **Cap gear — DEFERRED (SETTLED 4)** to the future armor/
  cybernetics polish pass: `ammo_bonus` field + first items +
  quality scaling + the flat-vs-per-type ruling. Doc 52 ships only
  the `effective_cap` bonus seam (phase 1).
- [ ] 5. **Standard rows + re-rule** — kills-of-endurance pins per
  caliber, board re-measure coordinated with doc 51's re-rule phase
  (one benchmark-revision commit if the waves land together).
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
5. Endurance rows green in `make check`.

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
- **Bandolier module** (NEW `src/spacehack/bandolier.py` — the
  doc-51 `ground_weapon_sets.py` sibling precedent; ADVISE issue 3:
  `ground_equipment.py` sits at 987/1000 lines and the ratchet makes
  its debt blocking the moment it is touched): a PURE core —
  `add_rounds(bandolier, ammo_type, n, cap) -> dict` (clamped),
  `space_remaining`, `effective_cap` (base cap in phase 1; the gear
  fold's seam ready for phase 4) — plus thin ctx wrappers. Pure
  core ships with pytest in the same commit.
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
3. Kill a sentry drone / raider whose pool drops ammo — walk over
   the drop and the bandolier tops up (no stack enters the pack;
   an over-cap pickup is silently ignored).
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

### Phase 2 Implementation brief (PROPOSED 2026-09-25 — SETTLED
### 2/3; builds IMMEDIATELY after phase 1 per the accepted gap)

**Scope (files / hook points):**

- **Armory restock-to-cap** (`menus/_armory_buy.py` + `_armory.py`):
  RETIRE the ammunition buy section (`_buy_ammo_rows`); add
  RESTOCK rows for CARRIED calibers only (the HUD ruling's logic
  applied to the shop — you restock what you're armed with), priced
  rounds-actually-added × `price_per_round` (SETTLED 2). Buying a
  weapon you lack ammo for is followed by an immediate restock
  prompt in the same terminal visit (flow detail at build).
- **Armory-storage migration** (`saveload_ground.py` load path,
  extending phase 1's): `ground_armory_items` ammo stacks convert
  into bandolier counts at cap + credit refund — the "legacy
  stacks" scope the ADVISE pass deferred here.
- **Pack ammo-class retirement**: with purchase retired, spawners
  spawning entities, and pickups refilling the bandolier, no
  creation path for pack ammo stacks remains — pin it (a test that
  no code path constructs `GroundItemStack("ammo", ...)` into the
  pack) and remove any dead sell/market handling for the class.

**Build order:** restock UI → armory-storage migration → class
retirement + dead-sell removal → tests → full gate → PLAYTEST.

**Binding rulings:** SETTLED 2 (per-round pricing, overflow
ignored), SETTLED 3 (back-to-back with phase 1), SETTLED 4
(carried-caliber display logic extends to the shop).

**Required tests:** restock pricing (a near-full caliber costs
pennies; an empty one costs cap × per-round), restock rows appear
for carried calibers only, armory-storage migration round-trip, the
no-pack-ammo-creation pin.

**Stop point:** no HUD/character-screen readout (3), no guide edits
(3), no endurance rows or board re-rule (5), no tutorial prose (6).

**Playtest checkpoint:** 1) A new character: buy two pistols, top
the bandolier at the armory, fight — full tutorial flow works
without pack stacks. 2) An old save's armory-stored stacks convert
+ refund on load. 3) No path anywhere produces a pack ammo stack.
4) Restock price reads exactly rounds-added × per-round. 5) `make
check` green.

### Phase 3 Implementation brief (PROPOSED 2026-09-25 — SETTLED 4
### + the user's HUD-scope amendment: HUD relevant-calibers,
### character screen full bandolier)

**Scope (files / hook points):**

- **Combat HUD** (`combat/_ground_render.py`): the reserve read
  (re-pointed in phase 1) renders as current/max for CARRIED
  calibers only (SETTLED 4) — one line per caliber the equipped
  weapons use.
- **Character screen** (`character_screen.py`): the equipment tab
  shows the FULL bandolier — all six ammo types with current/max
  (user amendment: "character screen equipment tab needs to show all
  ammo types somewhere") — the inventory view the HUD deliberately
  omits.
- **Guide** (`data/guide/__init__.py`, Ground Gear): rewrite the
  ammunition paragraph — the "matching ammunition in your
  Expedition Pack" line flagged stale since phase 1, and "Buy
  ground ammo at the Armory" becomes restock phrasing. PROPOSED
  WORDING (prose-gated — settles at this phase's checkpoint):
  "Reloadable weapons draw from your bandolier — the rounds you
  carry for each caliber, topped up at any armory or from
  battlefield pickups, up to a per-caliber carry limit. In combat,
  R reloads the first active weapon with room in its magazine.
  Outside combat, reloading is free. If multiple carried weapons
  can use the reserve outside combat, R opens a chooser. Melee and
  plasma weapons never need ammunition." (Plasma/melee identity
  sentences unchanged.)

**Build order:** HUD line → character-screen readout → guide
paragraph (user-approved wording) → tests → full gate → PLAYTEST.

**Binding rulings:** SETTLED 4 (carried calibers only); the guide
contract (diff rides this checkpoint verbatim); the prose gate
(wording approved before the data string lands).

**Required tests:** HUD renders current/max for carried calibers
only (a pistol pair shows one line; plasma/melee show none);
character screen renders ALL six calibers' current/max;
guide-content pins for the rewritten paragraph.

**Stop point:** no gear seam work (4 is deferred), no rows (5), no
tutorial prose beyond the guide (6).

**Playtest checkpoint:** 1) In a ground fight with pistols: the HUD
shows e.g. 132/160; a reload visibly decrements it. 2) Plasma or
melee equipped: no ammo line. 3) Character screen equipment tab
shows all six calibers (current/max each), carried or not.
4) GUIDE DIFF (before/after, exact):
the Ground Gear ammunition paragraph as above. 5) `make check`
green.

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
