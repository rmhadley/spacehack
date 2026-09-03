# DESIGN: Act 0 Merchants — "The Contract" Polish

## Overview

Polish the Merchants Act 0 chain to the standard of the hand-tuned Lab
chain: logical steps, rational time-gates that grant sandbox time,
tight bump→option→advance dialogue, and a quest log (Q) that always
shows the right next step — including while waiting on the faction.

Companion: `07_DESIGN_MAIN_QUEST.md` (system); Lab chain
(`act0_lab.py` + `04_lab.json`) is the tuned reference.

## What the tuned Lab chain does right (patterns to replicate)

Extracted from `act0_lab.py`, `04_lab.json`, `_core.py`, `_gates.py`,
`_breadcrumb.py`:

| Pattern | Mechanic | Lab evidence |
|---|---|---|
| Rational waits | `wait_days` on step N gates N+1; the wait is justified by the *faction doing work* | q2→q3 50d "terabytes to process"; q4→q5 95d cross-reference; q6→q7 80d tuning |
| Wait has two texts | `completion_flavor` (what's happening) + `ready_message` (the summon when the gate lifts) | q4 flavor "She'll contact you…" + ready "Great progress… but…" |
| Quest log never empty | While gated, breadcrumb shows "Awaiting word from the {faction}…" + the gating step's `completion_flavor` | `_gated_objective` |
| Dialogue = one beat | intro → one advancing option ("Hand over the data.") → step completes; next step starts immediately | every talk/smuggle step |
| Portrait-only steps | delve/salvage steps carry a portrait dialogue for the completion readout; the *gate summon is the briefing* — no extra talk beat | q3, q5 |
| Arc shape | 7 steps, 3 waits (~225 gate-days), each leg 1 system jump | q1..q7 |

## Current Merchants state ("The Contract", mer_q1→q5)

| Step | Type | Where | Gates next by | Story |
|---|---|---|---|---|
| q1 contract | talk | Earth | 60d (claim clearance) | sign; Guild files the deed |
| q2 strike | delve | Wolf 359 b | — | clear consortium, secure escrow ore |
| q3 transport | smuggle | Tau Ceti b | 130d (smelt) | ore → specialist; assay = impossible purity |
| q4 calibrate | salvage | Vega | — | fight through raiders, recover calibration data |
| q5 cutter | talk | Earth | — | collect the cutter → unlocks prologue_open |

- 5 steps, 2 waits (~190 gate-days). All dialogue text exists
  (`02_merchants.json`) and is close to the Lab voice.
- Both waits have flavor + ready_message; breadcrumb coverage works.
- q2/q4 are action steps (portrait-only / hand-over intro + option).

## Gap analysis vs goals

1. **Rhythm**: Lab's 7-step/3-wait cadence gives breathe-work-breathe;
   Merchants runs claim→smelt→fight→done with the two waits stacked
   early (after q1 and q3). The back half (q4→q5) is wait-free — the
   finale arrives immediately after the Vega fight.
2. **Step count**: 5 vs Lab's 7. The ore→alloy→cutter chain compresses
   two "the material is unusual" beats into q3's wait.
3. **Dialogue audit needed against the strict pattern**: verify every
   advancing dialogue is exactly one beat (intro + option + advance,
   ESC to decline), and no step chains extra popups after accepting.
4. **Questlog states**: verify each gating `completion_flavor` reads
   as "what the Guild is doing while you wait" (q1's and q3's do), and
   active steps show a concrete next-step description in Q.

## Proposals (to iterate — nothing below is decided)

- **P1 — third wait, post-Vega**: q4 gains `wait_days` (e.g. 40–60d)
  justified as "bonding the alloy to the cutter head / Guild smiths
  assembling under calibration". Restores breathe-work rhythm before
  the finale and gives the cutter payoff weight.
- **P2 — split q3's double duty**: the smelt wait currently carries
  both "ore is special" and "come back for alloy". Option A: leave as
  is (works). Option B: insert a short mid-step (consortium counters
  the deed — a legal/heat beat) to reach 6–7 steps.
- **P3 — dialogue tightening pass**: enforce the one-beat contract on
  every dialogue; trim any intro over ~3 sentences; ensure option
  labels are verbs ("Sign the contract", "Hand over the ore" —
  already good).
- **P4 — questlog sweep**: confirm Q during each state (active /
  gated / final) shows title + concrete next step, never a dead end.

## Phased implementation

### Phase 1 — audit (no code changes)
- [ ] Play through Merchants Act 0 fresh (Shift+O militia-skip does
      not apply; use a new game + merchants lock-in)
- [ ] Log every dialogue beat, Q state at each step, gate durations
- [ ] Confirm/adjust the gap analysis above

PLAYTEST: one full run noting rhythm pain points.

### Phase 2 — structure (whichever proposals are accepted)
- [ ] P1 third wait (+ ready/flavor texts)
- [ ] P2 if accepted: new step(s) with dialogue JSON
- [ ] Tests: chain linkage, gate days, unlock → prologue_open

PLAYTEST: full run — does the arc breathe like Labs?

### Phase 3 — dialogue + questlog polish
- [ ] One-beat enforcement pass over `02_merchants.json`
- [ ] Q states verified for every phase of the arc
- [ ] Tests: no behavioral change beyond texts

PLAYTEST: read-every-line run; flag any line that stalls or over-explains.

### Phase 4 — closeout
- [ ] Fresh full run to the Mars door
- [ ] Corpus audit + `make check`
- [ ] Ask user: move doc to complete?

## Acceptance criteria

- Steps read as a rational contract arc; every wait has an in-fiction
  "the Guild is working" justification and a summon on completion.
- Every advancing dialogue is one beat: bump → option → advance.
- Q shows an appropriate main-quest line in every state of the arc.
- Accepting a step starts the next objective immediately (no chained
  popups).
- `make check` green; no changes outside data/text + step data unless
  a proposal demands it.

## Open questions (for iteration)

1. P2: add a step at all? If yes: legal-pressure beat vs a second
   delivery vs leaving 5 steps but re-weighting waits?
2. Gate lengths: keep 60/130, or rebalance toward Lab's 50/95/80 feel?
3. Should the consortium heat escalate visibly in text (q4 mentions
   raiders; earlier steps only imply them)?
