# DESIGN: Player species & class identity

**Status: PHASE 2 BUILT 2026-09-27 — awaiting playtest. Phase 1
COMPLETE (built + playtest passed); phase 2 built in 7 commits (all
reviewer-passed, gate 3247), playtest checklist at the brief's
bottom.**

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
- [x] **2. Class identity layer** — brief below (APPROVED).
      BUILT 2026-09-27: 7 commits (5a488c10..56f1b6e8) — data
      rewrite + hp_base/HudStats cleanup, CLASS_TRAITS + two-trait
      grant, pirate/merchant/BH hooks, class screen, guide review.
      Reviewer: APPROVE x5 (one RC round on BH fully closed + delta
      pass); ratchet debts paid in-commit (_space_init, _ground_actions,
      saveload_ship extractions; _player_damage_mult + cost-line seams).
      Build amendments: rep row single-space (36-char budget), doc
      STR-16/HP-33 slip corrected to live STR 15/HP 29. PLAYTEST
      PENDING — checklist below.

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
  trait and the combined stamina) — and, per the 2026-09-28 playtest
  revision, the class' starting CREDITS ride the same row
  (`Armor 0   HP 25   Cr 25`; the viewport is at its 11-row cap, so
  Credits joins the row rather than adding one).
- **Rep next: the EFFECTIVE starting standings** (after defaults +
  class deltas — e.g. Human Pirate reads Pirates −70 / Merchants −10 /
  Militia 30; consortium hidden per HIDDEN_FACTIONS). Row format is
  the one open detail (viewport math below).
- **Trait block at the bottom** — class trait name + description,
  exactly like the species card.

**Viewport math — RESOLVED (user, 2026-09-27):** the split viewport
caps at 11 rows; rep renders as ONE aligned summary row → 11 total
with a two-line description budget. APPROVED as proposed. Build
amendment (2026-09-27, step 6): single-space separators
(`Pirates -70 Merchants -10 Militia 30` = 36 chars) — the two-space
example renders 38 and the panel budget is 36; full faction labels
kept, spacing conceded.

Phase 2 is fully ruled. All roll-through questions CLOSED (5/6/7/8).

## Phase 2 — Implementation brief (APPROVED 2026-09-27 — ADVISE-pass amended; trait descriptions approved verbatim)

**Scope (files + hook points):**

1. *Class data rewrite* — `data/classes/core.py`: spreads
   pirate Gunnery+3/Strength+3, merchant Engineering+4/Stamina+2,
   bounty_hunter Gunnery+2/Piloting+2/Reflexes+2; credits 25/50/75
   unchanged; **`GameClass.hp_base` DELETED** (SETTLED 5's universal
   ship+modules rule). Fallout: `character.starting_stats` stops
   reading hp_base; `HudStats.hp`/`max_hp` are vestigial (read only
   by saveload round-trip + debug_session reporting) — DELETED under
   the zero-save assumption, with `_ctx_to_dict`/`load_game`/
   debug_session readers updated in the same commit.
   `faction._CLASS_REP` → pirate {pirate +30, merchant −10,
   militia −20} (unchanged), merchant {pirate −30, merchant +30,
   militia 0}, bounty_hunter {pirate −30, merchant +10, militia +20}.
2. *Class trait layer* — `data/classes/__init__.py` gains
   `GameClass.trait_id: str = ""` (declared field, the Species
   precedent — no id convention buried in the grant). 
   `data/traits/core.py`: `CLASS_TRAITS`
   registry (sibling of `ORIGIN_TRAITS`, outside `ALL_TRAITS`):
   ids `pirate`/`merchant`/`bounty_hunter`, names
   "Pirate"/"Merchant"/"Bounty Hunter". `trait_name` resolves all
   four registries. `_configure_new_context` grants the class trait
   after the species trait (a fresh character holds exactly two).
   Descriptions DRAFT for user approval (two-LINE card budget at
   the 36-char wrap — advisor verified the earlier drafts wrapped to
   three; user wording wins):
   - Pirate: `+10 smuggler's hold on every ship` /
     `First attack: +hit, +damage`
   - Merchant: `+10 cargo space on every ship` /
     `+5% sell, -5% buy at stations`
   - Bounty Hunter: `+5% evade in space and ground combat` /
     `Missile racks hold double`
3. *Pirate hooks* — smuggler hold: +10 flat term in
   `ship.smuggler_hold_capacity`. Opener: fight-scoped
   `enemy_fired: bool` field on BOTH combat states (declared fields,
   never serialized, set at every enemy shot — hit or miss; the
   funnel points are `_ai._enemy_attack` for space and
   `_ai_ground._fire_enemy_burst` for ground — each covers every
   enemy path incl. flee reactions; self-splash never sets it), PLUS
   an `opener_spent: bool` sibling: the bonus applies to the player's
   FIRST attack of the encounter only, requires `enemy_fired` False
   at that moment, and is consumed by the attack (once per fight,
   never on later volleys even vs a weaponless enemy). Values
   **+10% hit and +25% damage**, playtest-tunable. Hit leg: ground
   `hit_chance`, space `_player_hit_bonus`. Damage leg covers BOTH
   ground paths — the volley path (`_rules_ground.damage`) AND the
   explosive path (`_ground_blast.apply_explosive_enemy_hit`, which
   never routes through `damage`) — plus the space volley damage
   mult.
4. *Merchant hooks* — cargo: +10 flat in `ship.effective_max_cargo`
   via the optional-ctx precedent (`smuggler_hold_capacity` shape).
   Advisor-pass enumeration — EVERY decide-relevant reader threads
   ctx: trade.py `_free_cargo`/buy/sell quantity checks, game_flow
   landing checks, hud cargo row, character_screen_stats, all four
   mission/_lifecycle cargo gates (a merchant must never be refused
   cargo their own trade screen says fits); `menus/_ship_buy` stays
   on the catalog spec deliberately (base-hull comparison).
   Prices: BOTH class modifiers fold into the attitude `_mod` chain
   at ONE site each side — never `-_5%` inside `_unit_price` AND
   `+5%` inside `_sell_price` (sell derives from buy; compounding
   would drop a merchant's sell price BELOW a neutral trader's).
   Stacks with rep attitude mods (liked buy 0.95 / sell 1.05) — the
   class trait and earned reputation are separate sources by design
   (~0.9025 / ~1.1025 at liked). Goods only: equipment, ammo, and
   ship prices are untouched.
5. *Bounty hunter hooks* — evade: ground lands as ONE term in
   `_rules_ground._player_ground_dodge` (the assembly that already
   folds `ground_evade_bonus`, threaded into `_ai_ground` as an int —
   never a second assembly layer); space lands at the RESOLUTION site
   `_ai._resolve_enemy_shot` only — the AI-belief reads
   (`_find_reposition`, `_ranked_weapons`) deliberately stay
   unmodified so enemies underestimate the hunter. Missile racks: an
   `effective_missile_capacity(ws, ctx)` helper (×2 with the trait)
   used at EVERY capacity site, per the advisor enumeration:
   `_seed_missile_ammo`, `_install_weapon`'s direct magazine seed
   (ship.py:460), `buy_ammo`'s refill room (:238),
   `install_stored_equipment`'s storage clamp (:638 — a doubled rack
   must not halve on a storage round-trip), `total_ammo_cargo`
   (doubled racks book doubled reserve cargo), and the HUD/loadout
   capacity displays (hud_combat, menus/_loadout).
6. *Class choice screen* — `ui.class_split_frame(species_id,
   selected)` mirroring the species screen: title
   `CHAR - SPECIES - CLASS` colored with the chosen species' color;
   six COMBINED stat rows (base+species+class via
   `starting_pilot_skills`/`starting_ground_stats`); Armor/HP row via
   the live naked-start fold (combined stamina + species trait); ONE
   aligned effective-rep row (`starting_reputation` values,
   consortium hidden); trait name + description bottom. Hosted by
   `_run_class_pick(context, species_id)` in `input_helpers` via
   `run_dynamic_screen`; generic menu fallback; class_menu data
   source unchanged; confirm screen unchanged.
7. *Guide review* — Character & Skills: species-trait sentence
   becomes species AND class; skill-point line already carries Fast
   Learner. Guide-diff item on the playtest checklist.

**Build order (atomic commits):** (1) class data + hp_base/HudStats
cleanup + rep tables + pins; (2) CLASS_TRAITS + two-trait grant +
pins; (3) pirate hooks + pins; (4) merchant hooks + pins; (5) bounty
hunter hooks + pins; (6) class screen + pins; (7) guide review.

**Binding rulings:** SETTLED 4-8 verbatim; class traits named the
class name; ±30 rep envelope; hull HP ship+modules-only; no class
colors; opener window closes on any enemy shot (hit or miss);
descriptions user-worded before `/implement-phase`.

**Required tests (sabotage-proven pins):** per-class spread/credits/
rep table pins (exact effective standings); hp_base field gone +
HudStats keys out of the save; two-trait creation grant per class ×
species sample; milestones never offer class traits; smuggler +10
(stacks with module + perk terms); cargo +10; ±5% price edge on
terminal AND NPC surfaces; evade +5 in both theaters; missile racks
seed double; opener +hit/+damage on the first attack and NOT after an
enemy shot, both theaters; class card combined stats + effective rep
+ Armor/HP exact values; screen order + card-follows-selection +
title color; save/load roundtrip carrying both traits.

**Budget note (advisor forecast, not a placement driver):**
   `_rules_ground` sits at 989/1000 — the pirate and BH ground terms
   will likely trip the ratchet mid-build; the in-commit split is
   the expected response (phase-1 precedent: `_ground_blast`).

**Stop point:** no class-locked gear or kits (deferred); no
kinship/trade-lens/rap-sheet mechanics (explicitly not chosen); no
new classes; no species changes; no rep-system changes beyond the
_CLASS_REP tables; no balance retunes beyond the locked numbers.

**Playtest checkpoint (numbered in-game):**
1. Species pick → class pick as Human×each class: card title
   `@ - HUMAN - PIRATE` (human white) etc.; combined stats (Human
   Pirate Gunnery 14/Strength 14; Human Merchant Engineering 15/
   Stamina 13; Human BH Gunnery 13/Piloting 13/Reflexes 13); Armor/HP
   0/25 with Cr 25/75/50 riding the same row; effective rep row
   (Pirate: Pirates -70 Merchants -10 Militia 30; Merchant: Pirates
   -100 Merchants 30 Militia 50; BH: Pirates -100 Merchants 10
   Militia 70 — single-space separators, the built format); trait
   block reads the approved wording.
2. Martian Pirate: Armor 2 / HP 29 (martian sta 14 + pirate 0 = 14
   → 20+7+2 = 29; combined STR 15 = martian 12 + pirate 3 — the
   earlier "STR 16/HP 33" lead was a slip, amended at build).
3. Start each class: C screen lists BOTH traits (species + class).
4. Pirate: starter ship smuggler hold 10 (trade screen); first fight
   — opening attack shows the bonus hit/damage; second fight after
   an enemy shot lands first — no bonus.
5. Merchant: starter ship cargo +10; terminal prices −5%/+5% vs a
   non-merchant save; NPC trader prices likewise.
6. BH: enemy shots miss ~5% more (both theaters); a fresh missile
   ship's racks seed double.
7. Save/quit → Continue: both traits intact; hull numbers gone from
   the save (vestigial keys).
8. Guide-diff: Character & Skills species-trait sentence now covers
   classes — record before/after.

## Pre-implementation audit (2026-09-27, code-anchored — phase 2)

Every brief anchor re-verified against the post-phase-1 tree (line
numbers current at audit time).

**1. Existing classes / modules to extend or reuse.**

- `GameClass` (`data/classes/__init__.py`): `hp_base` field DELETED,
  `trait_id: str = ""` declared (Species precedent); `core.py`
  spreads/credits rewritten. `character.starting_stats` drops the hp
  read → `HudStats(credits, skills)`; `HudStats.hp`/`max_hp` fields
  die — readers verified VESTIGIAL-ONLY: saveload round-trip
  (`saveload.py:192-193/463`), debug_session reporting (237/349), and
  tests (test_hud 166/328, test_debug_session 37, test_origin_traits
  46, test_ship_purchase 38/229, test_saveload 41/280-281,
  test_readability 270 — all fixed in the same commit). No HUD render
  path reads them.
- `faction._CLASS_REP` (82): table swap only; `starting_reputation`
  (158) unchanged. `_SPECIES_REP` stays empty.
- `data/traits/core.py`: `CLASS_TRAITS` sibling of `ORIGIN_TRAITS`
  (252); `trait_name` (292) resolves the 4th registry (docstring
  "all three" updated); outside `ALL_TRAITS` so `_qualifying_traits`
  can never offer them.
- Grant: `game_loop._configure_new_context` (849) appends
  `find_class(class_id).trait_id` right after the species trait
  (858-860) — a fresh character holds exactly two.
- Pirate smuggler: `ship.smuggler_hold_capacity(owned, ctx=None)`
  (411) gains the +10 flat term; its three callers
  (navigation_scan 27/73, _quest_log 579) already pass ctx.
- Pirate opener: `enemy_fired`/`opener_spent` declared on
  `SpaceCombatState` (`combat/_types.py:135`) and
  `GroundCombatState` (`_rules_ground.py:127`), never serialized
  (fights never save mid-combat — `_loop` contract comment). Funnel
  points VERIFIED exhaustive: `_ai._enemy_attack` (438) covers the
  normal enemy turn (:139 caller) AND the space flee reaction
  (`_rules_space.py:932`); `_ai_ground._fire_enemy_burst` (287)
  covers enemy actions AND the ground flee reaction (`_try_ground_fire`
  260→279; `_ground_flee:45` routes through it). Hit leg: ground
  `_rules_ground.hit_chance` (410) `_hit_bonus` sum; space
  `_player_hit_bonus` (324) — the ONE assembly (live fire at 340 +
  preview `_build_hit_chances` 456 both inherit; preview showing the
  opener bonus is correct). Damage leg: ground volley `damage` (433),
  explosive `_ground_blast.apply_explosive_enemy_hit` (29 — one
  `_full_damage` fold; primary AND splash ride it), space `damage`
  (356) via the `damage_taken_mult` param. Consumption:
  `_loop._handle_fire` (468) is the ONE attack action in both
  theaters — a `mark_opener_spent` rules hook (both rules modules,
  `_rules_hook` dispatch) fires after the volley actually fired
  (`_max_ap_cost > 0`); refused volleys (no ammo/no target) never
  burn the opener.
- Merchant cargo: `ship.effective_max_cargo(spec, owned)` (403)
  gains optional ctx (the smuggler_hold_capacity precedent). Reader
  enumeration VERIFIED, slightly WIDER than the brief's list — also
  `menus/_ship_menu.py` 160/187 (hangar/cargo displays — same drift
  class, threaded) and `loot.py:670` via `_free_cargo` (inherits the
  fix); `trade.py` 152/346/395/737/927, `game_flow.py:711`,
  `hud._cargo_used_max` (228; callers 414/484),
  `character_screen_stats.py:120`, `mission/_lifecycle.py`
  17/59/123/183. `_ship_buy` stays catalog-spec (deliberate,
  base-hull comparison).
- Merchant prices: `_sell_price` (276) derives from `_unit_price`
  (251) — the anti-compounding fold: extract the class-free buy core
  (`_terminal_buy_base`) so −5% buy and +5% sell multiply the
  attitude chain independently (buy 0.95×core; sell
  0.75×core×1.05 — above the neutral 0.75; liked stacking
  0.9025/1.1025 exactly as ruled). NPC surface:
  `_npc_price_multipliers` (523) — buy/sell derive from base_price
  independently, both mods fold there (one site per surface).
  Equipment/ammo/ship prices verified untouched (no other callers of
  the faction modifier functions).
- BH evade: ground ONE term in `_rules_ground._player_ground_dodge`
  (764) — the int `_ai_ground` already receives. SURPRISE vs brief:
  the dodge assembly exists in THREE places (also
  `_ground_flee.reaction_volley` :34 and `_ground_render
  ._ground_evasion` :240) — per "never a second assembly layer" the
  two siblings REDIRECT to `_player_ground_dodge` (pre-existing debt
  paid at the touch site; behavior identical — same inputs). Space:
  `_ai._resolve_enemy_shot` (468) `_dodge` at resolution only;
  `_find_reposition`/`_ranked_weapons` stay unmodified (AI
  misjudges the hunter by design).
- BH missiles: new `ship.effective_missile_capacity(ws, ctx=None)`
  (×2 with the trait) at EVERY capacity site:
  `_seed_missile_ammo` (196), `_install_weapon`'s magazine seed
  (460), `buy_ammo` room (238) + its cargo recalc (250),
  `install_stored_equipment`'s storage clamp (638),
  `total_ammo_cargo` (172 — doubled racks book doubled reserve),
  `hud_combat._render_weapon_row` ammo readout (267),
  `menus/_loadout._weapon_detail` (66). `__post_init__` has no ctx
  (base seed stands for legacy fixtures); fresh-ship moments top off
  via new `ship.top_off_missile_magazines(owned, ctx)` (fill to
  effective, only ever increases) called from
  `game_flow._new_owned_ship` (669 — spaceport buys incl. missile
  hulls). Starter hulls carry NO missiles (verified: `starter`
  start_weapons = light_laser only) so new-game setup needs no
  top-off; `dev_mode.py:340`'s frigate grant is pre-ctx harness —
  stays base.
- Class screen: `ui.class_split_frame(species_id, selected)`
  mirrors `species_split_frame` (195) + `_species_card_rows` (175);
  `_run_class_pick(context, species_id)` in input_helpers mirrors
  `_run_species_pick` (142) via `run_dynamic_screen`;
  `title_flow.py:55` swaps `_run_pick(context, ui.class_menu())` →
  the new runner; generic menu fallback + confirm screen unchanged.
  Viewport math: 6 stat rows + Armor/HP + ONE rep row + trait name +
  2-line description = 11 = `pygame_split.MAX_VISIBLE_ROWS` ✓ (the
  SETTLED 8 resolution). Rep row via
  `faction.starting_reputation(species_id, class_id)` minus
  HIDDEN_FACTIONS.
- Guide: `data/guide/__init__.py:461-463` — the species-trait
  sentence ("Every species grants one permanent trait at creation…")
  becomes species AND class; :492-493 already carries Fast Learner.

**2. Three potential duplication hotspots.**

1. Ground dodge triple-assembly (pre-existing; `_player_ground_dodge`
   + `_ground_flee` + `_ground_render`) — the BH term would drift
   across three copies.
2. Missile capacity: `ws.ammo_capacity` read at 7+ sites — the
   ×2 would paste `* 2 if trait` per site.
3. Price modifiers: the class mods pasted at 4+ price sites instead
   of one helper + one fold per surface (terminal core / NPC
   multipliers) — the exact anti-compounding trap the brief pins.

**3. DRY strategy per hotspot.**

1. Fold the two sibling assemblies to `_player_ground_dodge` in the
   same commit as the BH term (like-for-like, inputs identical).
2. One `effective_missile_capacity(ws, ctx)` helper; every site reads
   it (the advisor enumeration is the checklist).
3. xp.py helpers (`merchant_buy_price_mod`, `merchant_sell_price_mod`,
   `bounty_hunter_evade_bonus`, `pirate_opener_armed` + the two
   tunable constants) — the ace_pilot pattern; combat sites read
   helpers, never inline `has_trait` conditionals. Guardrails:
   CLASS_TRAITS stays a dict registry; the class catalog stays a
   frozen tuple; state tables over conditional logic.

**Budget note (forecast, not a placement driver):** `_rules_ground`
989/1000 and `_rules_space` 972/1000 at audit — the opener + BH terms
land in both; if either crosses, the in-commit split follows the
phase-1 `_ground_blast` precedent. `trade.py` 931 and `ship.py` 716
have headroom.
2. Martian Pirate: Armor 2 / HP 29 (martian sta 14 + pirate 0 = 14
   → 20+7+2 = 29; combined STR 15 = martian 12 + pirate 3 — the
   earlier "STR 16/HP 33" lead was a slip, amended at build).
3. Start each class: C screen lists BOTH traits (species + class).
4. Pirate: starter ship smuggler hold 10 (trade screen); first fight
   — opening attack shows the bonus hit/damage; second fight after
   an enemy shot lands first — no bonus.
5. Merchant: starter ship cargo +10; terminal prices −5%/+5% vs a
   non-merchant save; NPC trader prices likewise.
6. BH: enemy shots miss ~5% more (both theaters); a fresh missile
   ship's racks seed double.
7. Save/quit → Continue: both traits intact; hull numbers gone from
   the save (vestigial keys).
8. Guide-diff: Character & Skills species-trait sentence now covers
   classes — record before/after.
