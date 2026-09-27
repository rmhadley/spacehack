# DESIGN: Player species & class identity

**Status: IN REFINEMENT 2026-09-27 — species layer fully locked
(SETTLED 1/2); phase 1 open on three rulings, then its brief. Class
layer (phase 2) unruled beyond sketches.**

Companion: `48_DESIGN_ENEMY_POLISH.md` (the roster revamp — this doc's
origin; the two interlock through the faction rep tables).

## The seed (user, 2026-09-22, verbatim)

> A player that has two barely different options for species:
> human/martian and 3 barely different options for class: pirate/
> merchant/bounty hunter.

> Yes, dump a short blurb for doc 49 -- player species/class design.

## Current state (from the 2026-09-22 audit, code-anchored — PRE-BUILD)

- The tables pre-date the repo with a literal "cosmetic only - they
  don't affect gameplay yet" comment (`character.py` @ `976d172`);
  migrated to `data/species/` + `data/classes/` the next day. No
  differentiation doc ever existed.
- **Species:** Human vs Martian = +1 hp and ±2-4 stat/skill points plus
  a small rep table (militia +10 / pirate −10). `SpeciesSpec` has no
  mechanics fields — bonuses only.
- **Class:** stat spreads (pirate: gunnery/strength spikes, 25cr;
  merchant: 75cr + engineering/stamina; bounty hunter: +4 all three
  skills/stats), rep tables, nothing else. No starting-kit field, no
  class-locked gear or abilities.
- **The tell:** the Pirate class's +30 pirate rep starts at −70 — still
  inside the engage band — so even a pirate fights pirates on turn
  one. The class fantasy buys nothing observable at start.
- Doc 07's "species/class combos see different angles and endings" is
  aspiration, not mechanics. SYSTEMS.md absent list: "species beyond
  human/martian, classes beyond pirate/merchant/bounty_hunter".

## SETTLED 1 — 2026-09-27: the species layer (design conversation)

**Approach.** One unique trait per species + one per class, granted at
character creation into a third registry alongside `QUEST_PERKS`
(milestone screens can never offer them; mechanics live at usage-site
hooks per trait-system pattern). Species = biology/aptitude (what the
body is built for — which fight); class = profession (the loop:
economy, missions, factions). Stat spreads stay as texture; flavor
lines, credits, and class numbers are placeholders except where locked
below.

**+6 stat pool principle (user ruling).** Every species gets a +6
stat-point budget on start (hp_bonus is a separate knob); Lalandan's
−5s are the one deliberate exception.

**The roster (all fields user-locked 2026-09-27).** Base stats are 10;
"start" column = creation values (base + spread). Ground HP shown with
SETTLED hp semantics (open ruling A below).

| Species | Home | Char | Color | Stats (start) | hp_bonus | Trait |
|---|---|---|---|---|---|---|
| Human | Earth (Sol) | `@` | white (255,255,255) | all six 11 | 0 | **Fast Learner** |
| Martian | Mars (Sol) | `@` | leaf green (130,225,90) | STR 12 / STA 14, rest 10 | +2 | **Sturdy** |
| Cygnian | Cygni b — the orbital yards (Cygni) | `&` | violet (170,130,230) | PIL 14 / GUN 12, rest 10 | 0 | **Momentum** |
| Sirian | Binary Station — the Binary Eye (Sirius) | `♦` | powder blue (185,215,245) | GUN 14 / REF 12, rest 10 | 0 | **Longshot** |
| Lalandan | Whisper — the Vault (Lalande) | `Q` | magenta-pink (255,130,195) | REF 16 / STR 5 / STA 5, rest 10 | 0 | **Nimble** |

- `♦` is U+2666 (CP437 card-suit diamond, procedurally patched by the
  engine) — NOT `◆` U+25C6, which is not on the bitmap tilesheet.
- Char philosophy: `@` marks the human-adjacent bodies (Human white,
  Martian "similar to human, just green" — user), symbols/letters mark
  the exotics. `&`, `Q`, `♦` collide with no entity or tile glyph.

**Trait mechanics (values playtest-tunable; shapes locked):**
- **Fast Learner** — +1 skill point per level (5→6; endgame 354 vs
  295 — permanent, unlike an xp% that converges at the level-60 cap).
- **Sturdy** — +2 armor_defense always, additive into the worn-armor
  sum (user's model: "A martian has 2 armor even if they have no armor
  on. Adding gloves that give +1 armor? martian now has +3 armor." —
  per-hit soak, min 1 damage, plasma halves, armor_bypass ignores) +
  +2 flat melee damage (melee-only, incl. fists).
- **Momentum** — +5% space hit chance always-on + a space kill refunds
  that volley's AP cost (user's power curve: "a bonus you feel early
  on that fades as the free AP kill shot starts to emerge").
- **Longshot** — +1 max_range on all ranged weapons (melee UNTOUCHED
  at max_range 1 — user-confirmed; min_range untouched so the close-in
  blind zone stays); +1 space-weapon range as a harmless rider.
- **Nimble** — +1 ground AP per round (4→5; ground only — space AP is
  the ship's). Stacks with Ace Pilot / cybernetic legs through the
  existing AP-bonus sum.

**Char/color system rulings.**
- Species color replaces ONLY the healthy state of the on-map health
  tint (`ground_player_fg`); wounded amber / critical red stay
  universal. Species colors must read clear of the alarm colors.
- Space-mode cyan `@` is the ship — species tint applies to on-foot
  views only.
- Distinct chars are live (`&`, `Q`, `♦`): the `char == '@'` player-id
  filters (saveload_maps, city_interiors, dungeon_extensions,
  game_flow) must be refactored to identify the player by name/id.

**Classes (user ruling): keep 3** — pirate/merchant/bounty_hunter;
untouched in phase 1. Phase-2 sketches only: pirate = kinship fix
(trait crosses the hostility threshold — pirate ships don't engage at
"disliked", boarded pirate crews don't aggro until you act; fixes the
audit's "tell"), merchant = trade lens (galactic baseline vs local
price), bounty hunter = rap sheet on sight + better capture payouts.

## SETTLED 2 — 2026-09-27: phase-1 scope (user, verbatim structure)

1. The species created as just designed.
2. The char system updated to take the new char/color options.
3. The species choice screen revamp.
4. Nothing changed for classes yet — leave those the same.

Species choice screen (user spec): options on the left, cycled as
usual in menus; on the right an easy-to-read card showing the species'
name, their char + color, and — right below the name/char header —
their home planet/system; then starting stats as absolute base values
(no +/-, e.g. Martian reads Strength 12, Stamina 14, rest 10); then
starting Armor/HP; the bottom of the card shows the trait name and
description. No flavor-blurb field — the card carries no new prose
beyond mechanical trait descriptions.

## Phases

- [ ] **1. Species identity layer** — five species specs (+glyph,
      color, home, trait), third trait registry + creation grant, five
      trait hooks, char/color system (health-tint fold + player-id
      refactor), species-choice screen revamp. Brief pending rulings
      A–C below.
- [ ] **2. Class identity layer** — class trait lockdowns (pirate
      kinship / trade lens / rap-sheet sketches), stat/credit refresh,
      class-screen card parity, new-species rep tables. Not started in
      phase 1.

## Open questions

1. **(phase 1, ruling A) Martian hp_bonus semantics** — hp_bonus
   today feeds only the cosmetic HUD/ship HP (`character.py:112`); the
   locked table's 29-ground-HP math requires it in the ground max-HP
   formula (`20 + stamina//2 + …`). Lean: ground HP only (species
   hp_bonus leaves ship HP; ship HP becomes class-only).
2. **(phase 1, ruling B) New-species rep tables** — Cygnian/Sirian/
   Lalandan have none designed. Lean: neutral defaults (no
   adjustments) this phase; design rep identity with the phase-2 class
   pass.
3. **(phase 1, ruling C) Existing saves** — species traits granted at
   creation only, so current characters keep what they have? Note:
   ruling A's formula fold gives old Martians +2 ground HP on load
   either way (fix-forward). A retro-grant migration is one line if
   preferred.
4. **(phase 2) Pirate-class kinship** — sketch exists (trait crosses
   the hostility threshold); shape unruled.
5. **(phase 2) Starting kits / class-locked gear** — in scope here or
   with trade? Unruled.
