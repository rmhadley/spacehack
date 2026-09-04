# DESIGN: Act 0 Militia — "The Incident" Polish

## Overview

Bring the Militia Act 0 chain to the shipped standard of the Lab and
Merchants chains: atomic steps, structural (not gated) ordering,
Lab-cadence waits, one-beat dialogues, a quest log that never
dead-ends, and prose with zero AI tells.

Companions: `07_DESIGN_MAIN_QUEST.md` (system),
`complete/32_DESIGN_ACT0_MERCHANTS.md` (the standard's source — its
closeout notes list the shipped mechanics this doc assumes:
tombstones, `rewards_goods`, migration pattern, prose tells).

## The standard (extracted from the merchants closeout)

1. **One beat per step.** A pickup is not a run — if a step's talk
   both delivers cargo and briefs the action, consider splitting
   (mer_q5 → alloy + survey).
2. **Ordering is structural.** A step's spawns/content cannot exist
   before its step is reachable. No skip paths; no completing from a
   state that skipped a prerequisite beat.
3. **Waits breathe**: ~220–225 gate-days total, no single wait >~95d,
   each justified by the faction doing work, each with
   `completion_flavor` + `ready_message`.
4. **Q never dead-ends**: active steps show a concrete objective;
   gated steps show "Awaiting word from the {faction}…".
5. **Dialogue is one beat**: bump → one verb-label option → advance.
   No chained popups after accepting.
6. **Prose has six banned tells**: abstraction-for-transaction, formal
   negation, information-free similes, personified objects,
   negation-contrast-dash + broken craft collocations,
   preordained-outcome / unplayed-event claims. Outcome causality runs
   from the ACTOR ("Cut those lines and the door comes down").
   Bureaucratic deadpan is an allowed register per character.
7. **No kill farms**: quest guards tombstone on death (both stampers —
   system entry AND save load); boardable interiors cache their
   cleared state.
8. **No stat-wall squads**: enemies fill behavior×attack×terrain
   cells; never stack N identical top-tier specs.
9. **Renumbering migrates**: RENAMES + reconciliation; the chain never
   strands a save.
10. **Text plumbing complete**: JSON overlay, RUNTIME registry for any
    new log key, `audit_story_text` green, extract-tool id list updated.

## Current state ("The Incident", mil_q1→q6)

Fiction: the cover-up angle. The militia found door material during
the Incident, buried the requisition, and now rebuilds a breach charge
off the books — scrubbed serials, deniable paperwork, containment
thinking. Distinct stance from the other chains (Lab studies the door;
Merchants take it apart where it's weak; Militia forces it and
contains what's inside).

| Step | Type | Where | Gates next by | Story |
|---|---|---|---|---|
| q1 report | talk | Earth | 60d — clearance | sign on to the private books |
| q2 cache | delve | Mercury | — | recover the hidden requisition cache |
| q3 inspection | smuggle | Luyten blockade | 80d — inspection | run the package through the blockade |
| q4 demolitions | visit | Epsilon Eridani b | 120d — charge tuning | recruit the expert |
| q5 livefire | bounty | Cygni | 80d — final assembly | live-fire test vs pirate captains |
| q6 charge | talk | Earth | — | collect the breach charge → `prologue_open` |

Route: Earth → Mercury → Luyten → Eri b → Cygni → Earth (good spread,
one leg per jump). All text exists (`05_militia.json`), both waits
have flavor + ready pairs, blockade_officer is a planet-authored
resident, demolitions_expert seats via `npc_presence` (tested).

## Gap analysis (initial scan)

1. ~~**Cadence is heavy**: 340 gate-days~~ SETTLED + LANDED (user
   ruling 2026-09-04): 60/0/40/70/50 = 220 gate-days — clearance is
   slow bureaucracy, the inspection report routes in 40, the expert's
   charge tuning is the long job (70), final assembly 50.
2. ~~**Cargo arithmetic**~~ SETTLED + LANDED (user ruling): quest cargo
   is MISSION CARGO, never market goods — the recorder pattern
   (`calibration_data`: one named quest good for both the dungeon
   pickup and the delivery crate; lab's `alien_device` /
   `reference_recorder` already follow it). Militia now carries ONE
   `sealed_requisition` (cataloged, rarity 0.1) from the Mercury cache
   to the blockade. Merchants had the same violation and is converted
   (`escrow_ore` for the claim/smelt legs, `smelted_alloy` for the
   handover — the old `rare_earth_metals` pickups are gone). Bar's
   `machine_parts`/`electronics` crate is a known remaining violation,
   left for the bar pass. Enforced by
   `test_quest_cargo_is_quest_goods_not_market_goods`.
3. ~~**The live-fire squad is a stat wall**~~ STRUCK (user ruling): the
   five pirate captains are INTENTIONAL — the player carries the
   overpowered `breach_charge_test` prototype (weapons/breach.py: 200
   dmg, range 12, mounted only during the Cygni fight) and the fight
   is tuned around it. Do not "rebalance" the squad.
4. **Prose red flags** (rewrite in the text pass; playtest confirms):
   - q5 captain intro: "do not mistake a successful detonation for a
     successful containment plan" — clever-clever abstraction.
   - q6 captain intro: "That is the order. The door is not." —
     clipped negation punchline (same family as the cutter line the
     user flagged).
   - q4 expert intro: "structures that resist ordinary physics" —
     writer's word, not the character's.
   - q5 description: "whether opening the door is wiser than leaving
     it sealed" — grandiose decision-drama beat.
   - q1 completion flavor's trailing "for a very long time" —
     mysticism padding.
   - KEEP (allowed register): the captain's off-the-books deadpan and
     the blockade officer's bureaucratic clipped lines.
5. **Q states unverified per-state**: no mil step defines an
   `active_description`; verify during playtest whether any state's
   Q text names a stale route leg (the mer_q5 lesson).
6. **Heat**: no `heat=` on any mil step. The route fiction says
   "crosses pirate space" — decide ambient-only (default, assumed) vs
   explicit pirate heat on q3/q5.

## Phased implementation

### Phase 1 — audit — HEADLESS PASS DONE 2026-09-04 (user playtest pending)
- [x] Headless verification: prototype mounts only for militia +
      mil_q5 live + Cygni system, dismounts after combat
      (`_encounter._mount_breach_charge`); q3 crate auto-loads when
      the cache is secured (`_maybe_auto_trigger_next_smuggle` — the
      captain's q3 dialogue is flavor-only by design, the officer is
      the receiver row); Mercury cache lands inside an authored
      landmark (mercury_vault.layout — plated strong room behind its
      own vault door, mirroring wolf_camp) guarded by 1x sentry_drone
      (user ruling: the assault_drone spike is pulled like wolf_b;
      the delve lands almost immediately after the Mars caves)
- [ ] Fresh playthrough with `SPACEHACK_SEED` pinned; log every
      dialogue beat, Q state at each step, gate durations, combat feel
      of the five-captain fight

### Phase 2 — structure
- [x] Waits rebalanced to 60/0/40/70/50 (no id changes — no migration)
- [x] Quest cargo: `sealed_requisition` (cataloged quest good) for the
      q2 cache pickup and the q3 crate; merchants converted the same
      way (`escrow_ore`, `smelted_alloy`)
- [x] Live-fire squad + prototype weapon confirmed intentional (ruling)
- [x] Regression tests: mil escorts tombstone (mirroring
      test_quest_guard_respawn's mer case)

### Phase 3 — dialogue + questlog polish — LANDED 2026-09-04
- [x] Flagged prose rewritten: q1 flavor's "for a very long time"
      trailing mysticism → "since the Incident"; q4 flavor's muddled
      "target that can survive the first failure" → "a target nobody
      will miss"; q4 intro's "structures that resist ordinary physics"
      → "I cut open things that were built to stay shut - vaults,
      hulls, reactor shielding"; q5 description drops the
      "wiser than leaving it sealed" drama beat; q5 intro's
      "do not mistake a successful detonation for a successful
      containment plan" → "Fire it at the captains, record what it
      does to their hulls, and come back."; q6 intro drops the broken
      "That is the order. The door is not." zinger. KEPT: "the charge
      couples to the alien material" (real blasting vocabulary, the
      assay precedent) and all off-the-books deadpan.
- [x] Q sweep: test_militia_breadcrumb_names_each_leg pins Earth /
      Luyten / Cygni legs + the gated "Awaiting word from the
      Militia…" state carrying q2's flavor

### Phase 4 — closeout
- [ ] Fresh full run to the Mars door (user playtest)
- [x] Corpus audit + `make check` (audit_story_text green, only the
      pre-existing mer_q4 option_label removable note)
- [ ] Ask user: move doc to complete?

System change (user ruling): landmarks no longer limited to one door
— the explicit LANDMARK_ENTRANCE marker (`e`, city-interior/deep-cell
precedent) is the single link point to the proc-gen'd dungeon, and
`d` doors are free for interior use. Without the marker, the old
exactly-one-door rule holds (wolf_camp unchanged). mercury_vault
dogfoods it: lit threshold marker + a real strong-room door. NOTE: `P`
is the layout parser's player-spawn glyph — use `e` for entrance
markers in dungeon landmarks.

## READY FOR PLAYTEST (2026-09-04)

What landed: 220-day cadence, sealed-requisition mission cargo, prose
pass, tombstone + breadcrumb tests, the mercury_vault landmark
(strong-room cache site) with the assault-drone guardian pulled. What the playtest should judge:
the five-captain fight WITH the mounted prototype (ruling: it is the
fun fight — verify the mount log line fires at Cygni and dismounts
after), the mercury_vault landmark read (does the strong room pay off
"someone has been protecting it"?), each
wait's fiction earning its days (60/40/70/50), Q at every state, and
whether the off-the-books voice holds up over a full arc.

## Acceptance criteria

- Every item on the ten-point standard reads true for this chain.
- The cover-up fiction survives a logic audit (what the requisition
  is, why the blockade signs off, why the expert tunes for 70–120
  days, what the live-fire test proves).
- `make check` green; changes stay in step data + text unless a
  settled proposal demands mechanics.

## Open questions

1. Heat — none on militia steps; route fiction says "crosses pirate
   space". Ambient-only (assumed) vs explicit pirate heat on q3/q5?
