# DESIGN: Player species & class identity

**Status: PHASE 1 COMPLETE 2026-09-27 — built (18 commits, gate 3197
green), reviewer round closed (both blockers + all minors fixed),
PLAYTEST PASSED (user sign-off 2026-09-27, after three in-playtest
card polish rounds: CHAR-NAME-HOME title, flavor-free homes + six
aligned stat rows, verbatim trait prose, hint dedup; guide edits
reviewed with the checklist). Next: phase 2 — class identity layer
(discussion open; unbriefed).**

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

**Card title revision (user, 2026-09-27, build session):** the right
pane's header row is the identity line `CHAR - NAME - HOME` (e.g.
`@ - HUMAN - Earth (Sol)`), painted in the species color; the body
drops the separate name/home rows. Second revision, same session: the
exotic home lines lose their flavor clauses (Cygni b (Cygni) /
Binary Station (Sirius) / Whisper (Lalande) — "the orbital yards" /
"the Binary Eye" / "the Vault" removed), and the stat block lists
ALL SIX stats as rows with the Armor/HP row directly under them;
third pass: stat names/points aligned — names padded to the longest
stat name, values in one shared right-aligned column (Armor's value
sits in it too, HP rides after).

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

- [x] **1. Species identity layer** — brief below (APPROVED).
      BUILT + PLAYTEST PASSED 2026-09-27: 18 commits (audit + 8 build +
      blocker fix + card revisions + minors + prose/hint polish), gate
      3197 green, reviewer round closed. Playtest findings folded in
      session: the CHAR-NAME-HOME card title, flavor-free homes,
      six-stat aligned rows, user-verbatim trait prose, hint dedup.
- [ ] **2. Class identity layer** — class trait lockdowns (pirate
      kinship / trade lens / rap-sheet sketches), stat/credit refresh,
      class-screen card parity. Discussion open; unbriefed.

## Pre-implementation audit (2026-09-27, code-anchored — phase 1)

**1. Existing classes / modules to extend or reuse.**

- `Species` (`data/species/__init__.py`) gains `glyph: str = "@"`, `color`,
  `home: str = ""`, `trait_id: str = ""` as declared fields
  (dataclass-field cohesion); `data/species/core.py::SPECIES` rewritten to
  the five-species roster. `skill_bonus`/`ground_bonus`/`hp_bonus` keep
  their semantics (starting stat spreads), so `character.starting_pilot_skills`
  / `starting_ground_stats` need NO changes — the new start values flow
  from data alone.
- `faction._SPECIES_REP` empties (SETTLED 3-B). `starting_reputation`
  already falls through to zero adjustments for missing keys — behavior
  complete with the table edit; no signature change.
- Trait layer (`data/traits/core.py`): `ORIGIN_TRAITS` dict sibling of
  `QUEST_PERKS`; `trait_name` resolves all three registries (the C screen
  via `character_screen_stats._trait_names` and `tombstone._trait_names`
  then render "Sturdy" with zero further edits). `_qualifying_traits`
  scans `ALL_TRAITS` only — origin traits can never be offered at
  milestones by construction.
- Creation grant: `game_loop._configure_new_context` (species_id in hand,
  `ctx.player_traits` exists) appends `find_species(id).trait_id` —
  the same append `trait_screen` uses. `player_traits` already
  round-trips save/load (`saveload.py:140/835`).
- Trait hooks follow the `xp.py` bonus-helper pattern
  (`sharpshooter_hit_bonus` et al.): seven new ctx-aware getters
  (`fast_learner_skill_points`, `sturdy_armor_bonus`, `sturdy_melee_bonus`,
  `momentum_hit_bonus`, `momentum_kill_refund`, `longshot_range_bonus`,
  `nimble_ap_bonus`) read at the usage sites:
  - Fast Learner — `xp.add_xp` level-up grant + message.
  - Sturdy armor — `_rules_ground._armor_defense_total`; melee — the
    `_melee_bonus` assembly in `_rules_ground.damage` (line 444;
    `ground_damage_raw` itself untouched), melee detected by
    `damage_type == "melee"` (spec field, same test `is_charger_melee` uses).
  - Nimble — `_rules_ground._starting_ap_gain_twentieths`'s existing
    `80 + 20 * (bonuses)` sum.
  - Momentum hit — the `_hit_bonus` assembly in `_rules_space.hit_chance`
    (333) AND `_build_hit_chances` (460) — see hotspot 2.
  - Momentum refund — `_loop._handle_fire` deducts the volley's max AP at
    line 480 AFTER slot firing (explosive kills resolve even earlier,
    inside `_fire_active_slot`); a pre/post enemy-liveness snapshot around
    the volley plus a `_rules_hook(rules, "refund_volley_ap")` hook
    (only `_rules_space` implements it; body in `_space_kills.py` per the
    brief, mirroring the existing ground-only `record_player_kill` hook)
    refunds once per killing volley, both kill paths covered.
  - Longshot ground — `combat/_ground_charger.py::weapon_range` is THE
    one player range helper: `can_fire` and both HUD range readouts
    (`_ground_render.py:91/372`) route through it. Longshot space —
    `_space_focus.max_range/min_range` is the one space range seam
    (hit calc, range line, HUD all call it). Enemy AI reads raw spec
    ranges (`_ews.max_range`, `_ai.py:225/320`, `_ai_ground.py`) —
    untouched by construction.
- hp fold (SETTLED 3-A): the max-HP formula lives TWICE today
  (`_rules_ground._player_hp_state` and `game_loop.py:847`) — both gain
  the species term via one shared helper in `character.py`;
  `character.starting_stats` drops the species hp term (HudStats.hp =
  class `hp_base` only).
- Char/color: one `character.species_appearance(species_id) ->
  (glyph, color)` helper (safe `'@'`/white fallback for stale ids, the
  `_safe_lookup_*` pattern) read by every player-entity construction
  site: `game_interactions.py` 265/380, `city_interiors.py` 162/207
  (162 already copies `parent_player.fg` — only its char hardcode
  changes), `dungeon_extensions._make_player`, `saveload_maps
  ._make_walker_entity` (the ONE walker builder for all three load
  rebuild paths — `species_id` threaded from `rebuild_game_map`, which
  holds `data["character_info"]`), `game_loop._new_character_context`,
  `game_flow` player-copy sites. `hud.ground_player_fg` signature gains
  the healthy color (default `COLOR_PLAYER_HEALTHY`); the two callers
  (`game_loop._tint_player_glyph`, `_ground_render.render_frame`) pass
  the species color. Amber/critical constants unchanged.
- Player-id refactor: the four `char == '@'` filters
  (`saveload_maps:187`, `city_interiors:125`, `dungeon_extensions:806`,
  `game_flow:971`) become `name == "Player"` predicates. Space-mode
  ship `@` is a different entity (`_make_ship_entity`) — untouched.
- Species screen: `pygame_split.SplitFrame` + `run_for_screen` (the
  doc-52.3 Equipment-tab pattern: read-only right panel, ENTER returns
  the left row's action verbatim) — left = the five species options,
  right = the card (informational `SplitRow`s, ≤11 rows so the viewport
  never clips: name+glyph, home, stats block, Armor+HP row, trait name,
  wrapped description). Hosted by a species pick runner in
  `input_helpers`/`title_flow`; `ui.species_menu` remains the options
  source; `class_menu` + `_run_confirm` unchanged.

**2. Three potential duplication hotspots.**

1. Ground max-HP formula copy-pasted between `_player_hp_state` and
   `_configure_new_context` (pre-existing) — the hp fold edits BOTH.
   (Landed: the shared formula lives in `xp.ground_max_hp_total` —
   cohesive beside `ground_max_hp_bonus`; the reviewer's round also
   caught and folded a FOURTH pre-existing copy in
   `trait_screen._apply_ironclad_hp`.)
2. Space hit-bonus assembly duplicated between `hit_chance` and
   `_build_hit_chances` (pre-existing sharpshooter/specialist duplication)
   — Momentum would become a third copy-paste.
3. Player `world.Entity(...)` construction blocks at ~8 sites — the
   glyph/color lookup copy-pasted per site instead of one helper (plus
   the armor_defense sum duplicated between `_armor_defense_total` and
   `refresh_equipment_state`, which the Sturdy edit would double).

**3. DRY strategy per hotspot.**

1. Extract `character.ground_max_hp_total(ctx)`-style shared formula
   (pure computation over ground_stats + equipped armor + traits +
   species hp_bonus); both call sites shrink to calls.
2. Extract a `_player_hit_bonus(ctx, weapon_id)` helper in
   `_rules_space` assembling sharpshooter + specialists + momentum;
   both assemblers call it — pays the pre-existing debt where the trait
   lands (ratchet-friendly: `_rules_space` is at 966/1000 lines, and the
   extraction nets lines).
3. One `character.species_appearance(species_id)` helper + the walker
   rebuild threading; `refresh_equipment_state` re-calls
   `_armor_defense_total` instead of re-summing. Guardrails: SRP/one-verb
   helpers, pure-computation-vs-mutation split, state tables over
   conditional logic (species catalog stays a frozen data tuple; trait
   effects stay table-driven getters, no call-site conditionals beyond
   the bonus reads).

**Budget note (forecast, not a placement driver):** `_rules_ground` is
985/1000 and `game_flow` 978/1000 — the ground hook edits are +5-8 net
lines (inside budget); the `game_flow` edit is a like-for-like predicate
swap (net 0). If any hook push crosses the limit, the in-commit refactor
is the helper extractions above, which already pull lines OUT of the
touched modules.

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
1. New game → species screen: cycle all five. Card per species —
   title `CHAR - NAME - HOME` in species color (flavor-free homes),
   then all six stats as rows with Armor/HP under them: Martian
   STR 12 / STA 14 / Armor 2 / HP 29; Lalandan REF 16 / STR 5 /
   STA 5 / HP 22; Cygnian PIL 14 / GUN 12; Sirian GUN 14 / REF 12;
   Human all 11s.
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

## SETTLED 4 — 2026-09-27: the phase-2 frame (user)

Keep the three classes (pirate / merchant / bounty_hunter). EACH class
gets, rolled class-by-class in that order:

1. **Stat spread re-ruled to a +6 budget** — the class layer's
   contribution to starting stats, mirroring the species +6 pool
   (replaces the legacy +12/+12 and +4-everywhere spreads; where the
   six points land is a per-class ruling).
2. **Starting rep shape** — the `_CLASS_REP` table re-ruled per class
   (species stays rep-neutral per SETTLED 3-B).
3. **One class trait** — a second creation-granted trait matching the
   class theme (species trait + class trait = the fresh character's
   two), granted into a class-trait registry sibling of
   `ORIGIN_TRAITS`; never offered at milestones.

Then, after all three classes are rolled: **class choice screen
polish** — same look/feel as the species screen (split card: title
`CHAR - NAME - ...`, aligned stat rows, trait block).

Per-class knobs that STAY class-owned unless re-ruled during the
roll-through: hull `hp_base` (class-only per SETTLED 3-A) and starting
credits. Starting kits / class-locked gear: not in the user's phase-2
list — deferred unless re-opened.

## SETTLED 5 — 2026-09-27: Pirate (roll-through 1 of 3, user)

- **Stats: Gunnery +3 / Strength +3** (the +6 budget; silhouette kept).
- **Hull HP is not a class stat — UNIVERSAL ruling:** "HULL HP is
  determined by ship + modules, not species/class." `GameClass.hp_base`
  dies for ALL classes (already vestigial in code — space hull reads
  the ship; the field only fed the serialized HudStats constants).
  Disposition lands in the phase-2 brief.
- **Starting credits: 25.**
- **Rep: the trait crosses the threshold (ruling a of the fork); the
  class rep-delta envelope for the OTHER two classes is +30/−30**
  (pirate's table stays pirate +30 / merchant −10 / militia −20 →
  opens at pirate −70 "disliked", merchant −10, militia 30).
- **Trait name: "Pirate"** — the class traits are named the class name.
- **Trait leg 1 (early game):** all ships gain **+10 smuggler's-hold
  capacity** (flat, additive into
  `ship.smuggler_hold_capacity` beside the module terms and the
  epilogue perk's 10% — opens early smuggling work on a bare hull).
- **Trait leg 2 (whole game), ruling (b) BOTH theaters:** the opening
  attack of an encounter gains **+hit and +damage** when no enemy has
  attacked yet — space volleys and ground attacks alike. Ground
  consequence (accepted by design): the player usually acts before a
  fresh fight's first enemy swing, so on ground this reads "first
  attack of each fight"; space consumption semantics (pre-combat
  enemy shots) get pinned in the brief. Values playtest-tunable.
- **Threshold effect: DROPPED** (user): no engage-threshold mechanic.
  "Pirate starting closer to neutral for pirates than the other two
  classes is good enough" — the class table stands, the −70
  disliked-pirates-still-engage tell is accepted behavior.

## SETTLED 6 — 2026-09-27: Merchant (roll-through 2 of 3, user)

- **Stats: Engineering +4 / Stamina +2** (the +6 budget; ruling b).
- **Starting credits: 75.**
- **Rep: pirate −30 / merchant +30 / militia +0** — the full ±30
  extremes: opens at pirate −100 (clamped, ENEMY — pirates hunt
  merchants from day one), merchant +30 (LIKED), militia 50 (liked,
  the shared default). Market intel therefore starts at the liked
  tier with no trait needed.
- **Trait "Merchant", two legs (user):**
  1. All ships get **+10 cargo storage** (flat capacity — "this
     actually makes an impact with starter ship at beginning").
  2. **+5% sell / −5% buy at all stations AND the spaceport.**

## SETTLED 7 — 2026-09-27: Bounty Hunter (roll-through 3 of 3, user)

- **Stats: Gunnery +2 / Piloting +2 / Reflexes +2** (the +6 budget;
  the tracker).
- **Starting credits: 50.**
- **Rep: militia +20 / pirate −30 / merchant +10** — opens at
  militia 70 (liked, upper), pirate −100 (clamped, enemy), merchant
  +10 (neutral).
- **Trait "Bounty Hunter", two legs (user):**
  1. **+5% evade/dodge chance in both ground and space combat.**
  2. **x2 missile storage per missile weapon installed** (each
     installed missile weapon's ammo rack holds double).
- The rap-sheet sketch was NOT chosen (superseded by the two legs
  above).

## SETTLED 8 — 2026-09-27: class choice screen (user)

Same split-card screen as species (left cycling options, right card,
cursor-following). **Classes do NOT get colors** — the identity color
on the class card is the ALREADY-CHOSEN species'. Card format:

- **Title: `CHAR - SPECIES - CLASS`** (e.g. `@ - HUMAN - PIRATE`),
  colored in the chosen species' color, via the same per-panel
  label-color override.
- **Six stat rows: BASE + SPECIES + CLASS** — the combined REAL start
  values (live formulas: `character.starting_pilot_skills` /
  `starting_ground_stats` with the picked species id in hand).
- **Armor/HP row** stays (live naked-start fold incl. the species
  trait and the combined stamina).
- **Rep next: the EFFECTIVE starting standings** (after defaults +
  class deltas — e.g. Human Pirate reads Pirates −70 / Merchants −10 /
  Militia 30; consortium hidden per HIDDEN_FACTIONS). Row format is
  the one open detail (viewport math below).
- **Trait block at the bottom** — class trait name + description,
  exactly like the species card.

**Viewport math — RESOLVED (user, 2026-09-27):** the split viewport
caps at 11 rows; rep renders as ONE aligned summary row
(`Pirates -70  Merchants -10  Militia 30`) → 11 total with a
two-line description budget. APPROVED as proposed.

Phase 2 is fully ruled. All roll-through questions CLOSED (5/6/7/8).
