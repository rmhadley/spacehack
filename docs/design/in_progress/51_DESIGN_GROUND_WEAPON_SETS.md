# DESIGN: Ground Weapon Sets — 4 slots, one-toggle swap

**Status: DRAFT for review (2026-09-25) — rulings captured from the
doc-50 checkpoint conversation; not yet refined, no briefs, nothing
implemented.**

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
  mechanism).
- **The swap** (`ground_equipment.exchange_weapon_sets(ctx)` or a
  combat-action helper): exchange the two lists, refresh equipment
  state, **cost 1 AP** in combat, free out of combat. One action,
  whole set ↔ whole set.
- **Pack law**: holstered set members are equipment — never stored,
  never counted against `expedition_capacity`.

## Domain changes

- `combat/_loop.py`: new action id (working name `SWAP_SETS`) in the
  dispatch — `rules-hook` shaped like RELOAD (ground-only; space
  combat logs "unavailable"). New key binding per the 6a keymap law
  (must clear the action table, VIM diagonals, and main-loop
  helpers; **X is the working candidate** — verified at build time).
- `game_context.py`: the holstered field.
- `saveload_ground.py`: serialize both lists; **migration** for
  existing saves (classify equipped 2-slot contents into their set;
  holstered starts empty).
- `ground_equipment.py`: classification table, set-occupancy
  validation on equip, `exchange_weapon_sets`.
- Character screen + armory terminal: set-aware equipment UI (equip
  into ranged/melee sets; the C-screen mid-combat per-weapon swap
  REMAINS at 1 AP per change for set *editing*).
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

### Phase 1 PLAYTEST (sketch — brief lands at refine time)

Save/load sniff: old save → continue → weapons in the right set;
equip two pistols + two batons out of combat → toggle works; migrate
a mid-game save.

## Open questions

1. **Key binding**: X (working candidate) — any preference before the
   6a collision check rules it?
2. **Empty-set toggle**: ruling says allowed (fists). Confirm.
3. **C-screen per-weapon combat swap** stays alongside the toggle
   (1 AP/change) — confirm, or retire the mid-combat menu path?
4. **Tutorial teaching**: does the tutorial's armory beat teach the
   toggle (buy 2 + 2?), and with what wording? (Prose-gated; phase 5.)
5. **Balance blast radius**: landing this re-rules the doc-50 board
   (phase 4). Any bar the user wants held IMMUNE to re-rule (e.g.,
   the space rows)?
