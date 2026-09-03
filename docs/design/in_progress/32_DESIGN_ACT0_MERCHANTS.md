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

## Settled design (user rulings 2026-09-03)

The cutter = a **drive** (heavy cutting rig) fitted with **teeth of
the Wolf 359 alloy**, cutting **where the Vega stress survey says the
door is weakest**. No resonance language (dropped from Labs' visible
text for the same reason — only "tuned" survived there).

**The drive is CONTRABAND, and the credits are the bribe that frees
it.** The rig is the consortium's own — seized when the Guild's deed
won the Wolf 359 claim — impounded at the Depot station while the
consortium's lawyers contest it. The bribe "resolves the paperwork."
Everything is a ledger entry; the antagonist supplies the weapon.

**The bribe is OPEN-ENDED fundraising.** No fixed job step: the
dialogue hints at Guild contracts, but trade, bounties, piracy — any
income counts. Q shows the shortfall until the player can pay. This
replaces the pay-vs-branch design (simpler: one path, no branching,
no multi-option extension needed).

| Step | What | Where | Gates next by |
|---|---|---|---|
| q1 contract | sign | Earth | 45d — deed clearance |
| q2 the claim | delve ore | Wolf 359 b | — |
| q3 the smelt | ore → alloy | Tau Ceti b | 60d — smelt + assay |
| q4 the bribe | **raise {cost}cr, free the rig** | Depot station | 45d — machinist refits the mount |
| q5 the calibration | salvage stress survey, carrying alloy | Vega | 70d — smiths bond teeth, tune |
| q6 the cutter | collect | Earth → `prologue_open` | — |

Four waits ≈ 220 gate-days (Lab: 225); no wait over 70d. Route:
Earth → Wolf → Tau Ceti → Depot → Vega → Earth.

**New mechanic (contained): credit-cost steps.**
`MainQuestStep.payment_credits: int = 0` — when set, the advancing
dialogue option renders as "Pay {n}cr" and is only offered while
`ctx.stats.credits >= n`; accepting consumes the credits and completes
the step. Q renders an active payment step as the shortfall:
"Raise the {n}cr bribe — the rig waits in the Depot bond." Works with
existing save/load (credits already persist). No new state.

**Cost: 8,000cr** — scout is 5,000, cruiser 25,000; the bribe sits
"slightly higher than a scout" per the user's target. A genuine
mid-arc investment without being a wall.

## Proposals (to iterate — nothing below is decided)

- ~~P1 — third wait~~ RESOLVED by settled design (refit + assembly waits).
- ~~P2 — split q3~~ RESOLVED by settled design (the bribe step IS the new mid-step).
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

### Phase 2 — structure — LANDED 2026-09-03 (d76bd72)
- [x] 6-step chain: q4_bribe (payment, Depot, 8,000cr) + renumbered
      q5_calibration / q6_cutter; save migration for old ids
- [x] Waits 45/60/45/70; every gate has flavor + ready_message
      (smoke-enforced)
- [x] `payment` objective type: option gated on credits, "Settle the
      bond ({credits}cr)" label, consume + complete; tests cover
      hidden-when-poor, exact consumption, refit-gate registration

PLAYTEST: full run — does the arc breathe like Labs?

### Phase 3 — dialogue + questlog polish
- [x] Full text pass shipped with Phase 2 (Lab voice, one-beat
      dialogues, resonance language dropped, consortium heat seeded
      in q2/q3 text)
- [ ] Q states verified in playtest for every phase of the arc

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

1. Who takes the bribe — the Guild Master brokers it from Earth, or
   the depot attendant at the Depot station in person? (Doc assumes
   in-person at the Depot: third NPC, better route spread.)
2. Should Q track the running shortfall ("3,400cr to go") or keep a
   static target? (Doc assumes static — simpler, log already shows
   credits.)
3. Consortium heat text escalation before Vega — worth a line in
   q3/q4 flavor? (Assumed yes, one clause each.)
