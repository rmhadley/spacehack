# DESIGN: Player species & class identity

**Status: IN REFINEMENT 2026-09-27 — species layer locked (SETTLED
1/2/3); phase-1 Implementation brief PROPOSED (awaiting approval);
class layer (phase 2) unruled beyond sketches.**

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

## SETTLED 3 — 2026-09-27: phase-1 rulings A/B/C (user, verbatim keys)

- **A — hp_bonus is ground HP.** "yes, ground HP. it doesn't change
  hull hp." Species hp_bonus folds into the ground max-HP formula;
  `HudStats`/hull HP no longer reads it (ship HP becomes class-only).
- **B — species never changes starting rep.** "Let's set all species
  to have the same rep start as human. species shouldn't change your
  starting rep." `faction._SPECIES_REP` empties (Martian's
  militia +10 / pirate −10 is removed). Class rep tables unchanged.
- **C — zero existing saves.** "assume there are 0 existing saves." No
  migration, no retro-grant; new games only.

## Phases

- [ ] **1. Species identity layer** — brief below (PROPOSED).
- [ ] **2. Class identity layer** — class trait lockdowns (pirate
      kinship / trade lens / rap-sheet sketches), stat/credit refresh,
      class-screen card parity. Not started in phase 1.

## Phase 1 — Implementation brief (PROPOSED 2026-09-27)

**Scope (files + hook points):**

1. *Species data model* — `data/species/` (`__init__.py` + `core.py`):
   extend `Species` with `glyph` (default `"@"`), `color`,
   `home: str`, `trait_id: str = ""`; rewrite stats per SETTLED 1's
   table; add cygnian / sirian / lalandan entries. New species
   `description` reuses the `home` string — no new prose. Neutralize
   `faction._SPECIES_REP` per SETTLED 3-B.
2. *Trait layer* — `data/traits/core.py`: `ORIGIN_TRAITS` registry
   (sibling of `QUEST_PERKS`): fast_learner, sturdy, momentum,
   longshot, nimble; `trait_name` resolves all three registries;
   milestone screens never offer them (outside `ALL_TRAITS`).
   Creation flow grants `find_species(id).trait_id` into
   `ctx.player_traits`.
3. *Trait hooks* — Fast Learner: `xp.py` level-up grant 5→6 via a
   ctx-aware helper (ace_pilot pattern). Sturdy: +2 into
   `combat/_rules_ground.py::_armor_defense_total`; +2 melee via the
   existing `melee_bonus` param assembled at the player-volley caller
   (`ground_damage_raw` itself unchanged). Momentum: +5 space hit
   (`xp.py` bonus-helper pattern, read at the space hit calc) + kill
   refund of the killing volley's AP (`combat/_space_kills.py`).
   Longshot: species-aware player max_range helper (+1 ranged only)
   used by every player range check + HUD range readout (enemy
   weapons untouched); +1 space-weapon range. Nimble: +20 twentieths
   in `_starting_ap_gain_twentieths`'s existing bonus sum.
4. *hp_bonus fold (SETTLED 3-A)* — ground max-HP formula
   (`_rules_ground.py::_player_hp_state` + `game_loop.py:847`)
   adds species hp_bonus; `character.starting_stats` HudStats.hp
   drops the species term; `character_screen.py` species-bonus lines
   updated to match.
5. *Char/color system* — one helper reads
   `(glyph, color)` off the species spec; the hardcoded `'@'`-white
   player-creation sites read it (`game_interactions.py` 265/380,
   `city_interiors.py` 125/162/207, `dungeon_extensions.py` 806,
   `saveload_maps.py` 456, `game_loop.py` 806, `game_flow.py` 971
   area). `hud.ground_player_fg` healthy state = species color
   (signature takes the healthy color; amber/critical unchanged).
   Player-id refactor: the `char == '@'` filters in `saveload_maps`,
   `city_interiors`, `dungeon_extensions`, `game_flow` identify the
   player by `name == "Player"`. Space-mode ship `@` cyan untouched.
6. *Species choice screen* — `ui.py::species_menu` host: left cycling
   options (existing menu mechanics), right card per SETTLED 2 —
   name / glyph-in-color / home line / six stats as absolutes
   (species-only, class adds later) / Armor + ground HP row / trait
   name + description bottom. Class screen unchanged.

**Build order (atomic commits):** (1) species data + rep neutral; (2)
trait registry + creation grant; (3) ground hooks (sturdy, nimble) +
hp fold; (4) space hooks (momentum, longshot); (5) xp hook (fast
learner); (6) char/color system + player-id refactor; (7) screen
revamp; (8) guide review.

**Binding rulings:** SETTLED 1's table verbatim (values tunable in
playtest, shapes not); +6 pool; `♦` U+2666 not `◆`; melee max_range
untouched; alarms amber/red universal; SETTLED 3 A/B/C; traits
creation-granted, zero-save assumption.

**Required tests (sabotage-proven pins):** per-species starting stats
(all five, exact table values); creation grant lands the species
trait; milestone screens never offer origin traits; Fast Learner 6-vs-5
level-up; Sturdy naked-armor +2 and melee +2; Momentum hit +5 + kill
refund; Longshot ranged +1 (melee and enemy ranges unchanged); Nimble
100-vs-80 twentieths; `ground_player_fg` healthy=species color with
universal alarms; save/load roundtrip for `&`/`Q`/`♦` glyphs
(player-id refactor pin); identical `starting_reputation` across all
five species; species menu order + card render (fake-pygame menu
state).

**Stop point:** no class anything (data, traits, screen, rep tables);
no flavor prose beyond mechanical trait descriptions; no additional
species; no balance retunes beyond the locked numbers; no doc-07
endings work.

**Playtest checkpoint (numbered in-game):**
1. New game → species screen: cycle all five. Card per species:
   Martian Armor 2 / HP 29 / STR 12 STA 14; Lalandan HP 22 / STR 5 /
   REF 16; Cygnian PIL 14 / GUN 12; Sirian GUN 14 / REF 12; Human all
   11s. Glyph renders in species color; home line under the header.
2. Martian start: on-map `@` leaf green; C-screen traits list Sturdy.
3. Naked ground fight: incoming damage −2 vs pre-build behavior;
   melee hits +2.
4. Wound check on two species: below half → amber, below quarter →
   red (species color only at healthy).
5. Lalandan: 5 AP in ground combat; 3 pack slots.
6. Cygnian: space volley hit +5% vs same-stats other species; a kill
   costs no AP that volley.
7. Sirian: rifle max range +1 in the HUD readout; melee range still 1.
8. Human: level-up grants 6 skill points.
9. Save/quit → Continue as Cygnian (`&`) and Lalandan (`Q`): glyph,
   position, traits intact.
10. Space mode: ship `@` cyan on every species.
11. Rep: identical starting standings for all five (Martian no longer
    militia +10 / pirate −10).
12. Guide-diff: character-creation guide section reviewed — species
    list updated or deliberately unchanged; record before/after.

## Open questions

1. **(phase 2) Pirate-class kinship** — sketch exists (trait crosses
   the hostility threshold — pirate ships don't engage at "disliked",
   boarded pirate crews don't aggro until you act); shape unruled.
2. **(phase 2) Starting kits / class-locked gear** — in scope here or
   with trade? Unruled.
3. **(phase 2) Class stat/credit refresh + class-screen card parity**
   — the class screen keeps the old layout until phase 2.
