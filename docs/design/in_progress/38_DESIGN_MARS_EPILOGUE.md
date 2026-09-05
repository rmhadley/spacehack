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

## Open questions (for the user)

1. Where does the choice physically happen — fly to the faction's
   home world after the escape (one more leg), or the faction hails
   you in orbit?
2. Can a kept run ever deliver later (one-way door, or a later,
   costlier deliver option)?
3. Reward shapes above right for militia/bar/lab — or swap any?
4. Does the kept branch get its own first beat now (the twists are
   later), or just the harder baseline (heat + no pass) until Act 1?

## Phases

### Phase 1 — audit
- [ ] Play the current escape → orbit disclosure → research_alpha
      flow once; confirm the removal inventory
### Phase 2 — structure
- [ ] Remove orbit disclosure + research steps (data, scenes, tests,
      text) with save migration for in-flight runs
- [ ] Disposition flag + the choice scene (per chain)
- [ ] Four reward steps + the kept baseline
### Phase 3 — prose + playtest
### Phase 4 — closeout
