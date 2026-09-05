# DESIGN: The Mars Epilogue — Deliver or Keep

## Overview

The first post-Act-0 beat: escape Mars with the deep-prison data and
choose a disposition — hand it to your faction for an appropriate
reward, or keep everything to yourself for a harder road with
end-twists. This replaces the existing post-escape content per the
user's ruling, and its rewards tee up Act 1's Luyten blockade
(companion: `future/37_DESIGN_POST_ACT0_CAMPAIGN.md`, the roadmap;
`07_DESIGN_MAIN_QUEST.md`, the narrative canon).

## What exists today (the removal inventory)

- `act1_prison` — the prison-descent objective (auto on entering the
  extension, completes on Floor 5 extraction). **KEPT**: the escape
  is the epilogue's entry point.
- Orbit disclosure (`main_quest/_act1.py` `maybe_show_post_prison_orbit`
  + `_scenes` disclosure scene): the post-launch choice-specific
  handoff (sealed / transmit fragment / safe destination).
  **REMOVE** (replaced by the disposition branch).
- `research_alpha` + `research_alpha_report` (act1_post_prong data,
  Alpha Centauri handoff + 14-day first-translation gate) and their
  tests/text. **REMOVE** — the user does not want to keep it. The
  translation-layer fiction survives as later-act canon (doc 07).
- `prologue_open` unlocks `act1_prison` today; the epilogue sits
  between extraction and the faction handoff.

## The branch (per doc 37 + user leanings)

- **Disposition flag** (`main_quest_disposition`: "delivered" |
  "kept") — persistent, save-safe, set once at the choice scene.
- **Delivered**: one reward step keyed on the chain —
  - merchants: the 8,000cr bond pays out (stated ruling)
  - militia: blockade clearance / papers (doubles as a blockade path)
  - bar: a scrubbed false transponder + fence access
  - lab: a sensor/analysis suite refit (helps unmask the derelict)
  Each reward is load-bearing in Act 1 (the four paths past the Line).
- **Kept**: no reward, heat from all sides, the user's end-twists —
  design space noted in 37 (unaffiliated carriers may read/activate
  alien systems the factions cannot).
- The choice itself: a scene at the faction's door after the escape
  (per chain), not a menu bolted onto the ascent.

## Rulings (2026-09-05, landed same day)

The choice happens IN THE POST-ESCAPE MODAL itself (user: replace the
old disclosure modal with the choice) — "Return to the faction that
helped you and get your reward as you share the data" vs "keep the
data to yourself and go full solo."

## Reward shapes — SETTLED 2026-09-05 (the perk pass)

Per the user's ruling: every reward is TANGIBLE sandbox power, wired
through the perk system as FREE trait grants (never milestone picks,
never consuming level-up choices). Blockade plot options are a later
design conversation.

- **Merchants**: 12,000cr (the 8,000 bond + 50% return) — liquid.
- **Bar**: `smugglers_instinct` — 10% of the hull's natural cargo
  (min 1) concealed as smuggler's hold on every ship, stacking with
  modules (starter 5, cruiser 20, hauler 40, freight 70). Smuggle
  payouts unchanged; tune via playtest (the bar generator's cargo
  multiplier is the one number).
- **Militia**: `warrant_license` — the Militia board posts WARRANTS
  (bounty reuse), tier band (3,4) at any post: frontier-tier pay at
  home, and militia standing accrues naturally from the work.
- **Lab**: `lab_credentials` — lab stations post CONTRACTS
  (specimen-run delivery / recovery salvage reuse), band (3,4) across
  the five-station network.

Power-scale frame (user): the rewards land ~a year in at cruiser
minimum, so tier floors beat payout bumps — felt power is the band
jump (600-950cr work posted on T1 Earth vs 60-120 entry work).

## Open questions

1. ~~Where does the choice physically happen~~ SETTLED: the orbit
   modal IS the choice.
2. ~~Reward shapes~~ SETTLED: the perk pass (see Reward shapes above).
3. Kept-run later-delivery door (one-way, or a later costlier
   deliver option) — MIGRATED to Act 1's doc: it only exists once
   the blockade gives keeping-a-second meaning.
4. Kept-branch first beat now vs baseline-until-Act-1 — MIGRATED to
   Act 1's doc; shipped state is the baseline (no step, heat-with-
   no-pass, the solo summon).

## Phases

### Phase 1 — audit — DONE via build
- [x] Removal inventory confirmed during the build (the disclosure
      scene, research steps, gates, breadcrumbs, texts, tools).
### Phase 2 — structure — LANDED 2026-09-05
- [x] Orbit disclosure + research steps removed (data, scenes, gates,
      breadcrumb, texts, tools, save migration onto the branch)
- [x] Disposition flag + the two-option orbit modal (per-chain body)
- [x] Four reward steps + the kept baseline (pending-summon teaser)
### Phase 2.5 — the perk pass — LANDED 2026-09-05
- [x] QUEST_PERKS registry (outside ALL_TRAITS; milestone screens can
      never offer them); `rewards_trait` on steps; complete_step
      grants free + logs "PERK GAINED"
- [x] Smuggler's Instinct in `smuggler_hold_capacity` (scan exposure
      + quest log honor it)
- [x] Militia/lab board registration (warrants + contracts
      generators), perk gating, tier band (3,4)
- [x] Tests: grant/free/milestone-exclusion, hold math + stacking +
      scan protection, board gating + floor

### Phase 3 — prose + playtest — DONE 2026-09-05
- [x] User played the full flow (escape → choice → handover → perk →
      board); the catches — trait id on the character screen, stale
      clearance/transponder/refit language, the month-wait on board
      posting — all fixed same day

### Phase 4 — closeout — CLOSED 2026-09-05
- [x] Corpus audit + `make check` green
- [x] User closed the doc

## Closeout notes (final state)

The epilogue as shipped: the post-escape orbit modal IS the choice —
deliver to the faction that opened the door, or keep everything and
fly solo. Delivered runs the chain's reward step as a FREE QUEST
PERK (never a milestone pick): merchants collect 12,000cr (the bond
+ 50%), bar learns the hold's dead space (10% of every hull
concealed), militia goes on the warrant list (frontier-tier board at
any post), lab gets network credentials (five stations posting
contracts). Both board perks post work the moment they land. Kept is
the baseline: no reward, no pass, the solo summon teasing the Line.

Kept-branch design (later-delivery door, first beat) migrates to
Act 1's doc, where the blockade gives those questions their meaning.
