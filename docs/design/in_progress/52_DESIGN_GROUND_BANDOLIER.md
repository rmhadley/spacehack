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
  | rifle_rounds | 240 | ~41 (rifle) / ~85 (battle ×2) |
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
- `GroundArmorSpec` gains `ammo_bonus: int = 0`, folded through the
  existing `sum_armor_bonus` (fifth bonus field beside ap/hit/
  melee/hp; quality-scaled). FIRST ITEMS (ruling pending on flat vs
  per-type): a conventional body-slot rig trading defense for cap,
  and an endgame cybernetic (the "never count rounds again" piece at
  eyes/arms/legs pricing).

## Domain changes

- `ground_equipment.py`: bandolier helpers (`add_rounds`,
  `space_remaining`, effective-cap fold); reload path re-point
  (`_reloadable_slots` / `apply_reload` / `reserve_ammo_count`
  call sites).
- Pack: the ammo stack class RETIRES from the expedition pack
  (consumables/kits remain); migration converts carried stacks into
  bandolier counts, overflow → credits.
- Drops: `field_item_loot_pool` ammo entries refill the bandolier
  (capped); over-cap pickups ignored (HUD reads "topped up" —
  ruling pending).
- Armory terminal: **restock-to-cap** per carried caliber replaces
  stack purchase (price = rounds added × `price_per_round`).
- HUD: current/max per carried caliber (like fuel/power lines).
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
- [ ] 4. **Cap gear** — `ammo_bonus` field + first items (conventional
  rig + cybernetic per the flat/per-type ruling), quality scaling,
  armory stock. Tests: bonus fold, effective-cap math, endurance
  delta rows.
- [ ] 5. **Standard rows + re-rule** — kills-of-endurance pins per
  caliber (± cap gear), board re-measure coordinated with doc 51's
  phase-4 re-rule (one benchmark-revision commit if the waves land
  together).
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

### Phase 1 Implementation brief (PROPOSED 2026-09-25 — SETTLED 1;
### gated on doc 51's core landing; ready for /implement-phase 52.1
### on approval + handoff)

**Scope (files / hook points):**

- **Caps on the catalog** (`src/spacehack/data/ground_items/`):
  `GroundAmmoSpec` gains `carry_cap: int`; the six rows get SETTLED
  1's values (160/240/250/130/18/10).
- **The ctx field** (`game_context.py`): declared
  `bandolier: dict[str, int]` (ammo_type → rounds), default empty;
  serialized in `saveload_ground.py`.
- **Bandolier helpers** (`ground_equipment.py`): `add_rounds(ctx,
  ammo_type, n)` clamping at the effective cap (phase 1 = base cap;
  the gear-bonus seam lands with phase 4, same fold as
  `sum_armor_bonus`), `bandolier_space`, and the reload re-point —
  `_reloadable_slots` / `_ground_ammo_reason` /
  `reserve_ammo_count` call sites read the bandolier instead of pack
  stacks; `apply_reload` draws from it.
- **Drop re-point** (`combat/_actions.py
  _spawn_field_item_loot_at_position`): ammo entries become
  `add_rounds` refills (capped), never pack stacks — SETTLED 1's
  interim-dead-cargo fix.
- **Migration** (`saveload_ground.py` load path): carried pack ammo
  stacks convert into bandolier counts at their cap; overflow
  refunds credits (logged); the pack slots free up.
- **Doc-50 seam** (`tests/balance/harness.py`): `_ground_ammo_total`
  counts `ctx.bandolier` alongside magazines, and
  `build_ground_loadout` seeds the bandolier from
  `PlayerSheet.ground_ammo` instead of pack stacks — the rows'
  declared 40-round reserves ride the new store; the board's ammo
  bars must not move (same rounds available, same seeds — verified
  in-build).

**Build order:** catalog caps → ctx field + serialization → helpers
+ reload re-point → drop re-point → migration → doc-50 harness seam
→ full gate → PLAYTEST checkpoint.

**Binding rulings:** SETTLED 1 (caps table; build-after-51; drop
re-point in-phase; migration-with-refund). Fixed points from the
draft: independent per-type pools; plasma/melee never touch the
bandolier; magazine mechanics and the R key unchanged; multi-caliber
carried simultaneously is intended.

**Required tests:** cap clamp + multi-caliber independence (pure
helpers); reload integration (dry slot reloads from bandolier,
decrements it, charges AP — update the existing reload pins that
seed pack stacks); save round-trip (fresh saves carry the bandolier);
migration (a pre-52 save with stacks loads to bandolier counts +
credit refund + freed slots); drop re-point (a pool drop tops the
bandolier, never the pack); board bars unchanged
(`test_balance` green without edits beyond the seam).

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
3. Kill a sentry drone / raider whose pool drops ammo — the pickup
   tops the bandolier (no stack appears in the pack).
4. Sustained fight: fire past the old 40-round reserve — reloads
   keep working to the cap.
5. `make check` green; `python3 -m tests.balance.report` — the
   board's ammo numbers unchanged from the standard.
6. Guide diff: NONE this phase, but the Ground Gear line "need
   matching ammunition in your Expedition Pack" is now stale — its
   rewrite is phase 3, wording settles at this checkpoint (guide
   edits never ride silently; flagged here for review).
7. Save/load: migrated save re-saves and re-loads cleanly (sniff
   test).

## Open questions

1. **`ammo_bonus` shape**: flat (+N to every cap — the no-special-
   cases move) vs per-type (+N to one caliber — build-defining,
   needs a type field). Working lean: FLAT on the conventional rig,
   PER-TYPE on the cybernetic (the premium piece gets the expressive
   mechanic).
2. ~~**Cap levels**~~ ANSWERED — SETTLED 1: the proposed table
   confirmed as-is.
3. ~~**Overflow pickups**~~ ANSWERED — SETTLED 2: ignored.
4. ~~**Restock pricing**~~ ANSWERED — SETTLED 2: per-round.
5. ~~**Sequencing with doc 51**~~ ANSWERED — SETTLED 1: after doc
   51's core lands.
6. **Bandolier visibility off-load**: does the character screen show
   all six calibers or only carried ones (lean: carried only)?
