# DESIGN: Act 0 Bar — "The Old Hand" Polish

## Overview

Bring the Bar Act 0 chain (the underworld courier arc) to the shipped
standard of Lab / Merchants / Militia. User's warning going in: this
one carries the most cringe-worthy dialogue of the four chains.

Companions: `complete/32_DESIGN_ACT0_MERCHANTS.md` and
`complete/35_DESIGN_ACT0_MILITIA.md` (the ten-point standard and its
mechanics: tombstones, `rewards_goods`, migration, prose tells).

## Current state ("The Old Hand", bar_q1→q6)

Fiction: the pirate/underworld angle. The bar knows an old smuggler
who lost a hand to the Mars door decades ago; his rig — brute force,
a stolen Militia power cell, and a black-market recharge — is this
chain's way through. Unique systems the other chains don't have:
militia scan-floor + auto-aggro heat, a giver-recovery option (the
old smuggler re-issues a confiscated cell), and a reputation hit on
the proof run (militia −8).

| Step | Type | Where | Gates next by | Story |
|---|---|---|---|---|
| q1 old hand | talk | Earth | 65d — word travels | the barkeep names the old smuggler |
| q2 proof run | smuggle (hot) | Barnard's b | 85d — he decides | run a hot crate as proof |
| q3 rig parts | delve | Barnard's b | — | recover the rig's power cell from the old dig |
| q4 black market | smuggle (hot) | Wolf 359 b | 90d — recharge | the cell to the only rig that can charge it |
| q5 return run | smuggle (hot) | Earth | — | the charged cell home; Sol scanners aggro |
| q6 the rig | talk | Earth | — | collect the brute rig → `prologue_open` |

Route: Earth → Barnard's ×2 → Wolf 359 → Earth. All waits carry
flavor + ready pairs. No space spawns — nothing to tombstone. NPC
seating tested (old_smuggler across q2–q4). Gate-days: **240** vs the
220/225 target, with the two big waits stacked early.

## Gap analysis (initial scan)

### 1. Prose — the hot list (six-tell scan; the rewrite is the main work)

The chain tells a genuinely good story entirely through
PERSONIFICATION of the door, the cell, and the rig — the exact tell
ruled out in the merchants pass ("the alloy doesn't get fed and it
doesn't need eyes"). Worst offenders:

- **q6 barkeep intro — the headline cringe**: "It does not crack the
  seal so much as convince the power feed to stop pretending it is
  dead." Negation-contrast + convince + pretending — three tells in
  one clause.
- **q4 completion flavor**: "The meter has no scale for what it
  reads." / "It has been waiting in the dark since before the
  Incident." / "why it still remembers the door." — meter mysticism +
  a cell that waits and remembers. Three sentences, three tells.
- **q2 completion flavor**: "surveying the dig site with one hand and
  three decades of regret" — parallel poetry.
- **q2 old_smuggler.active**: "The old job was not a robbery; it was
  an attempt to make the door recognize a human signal." —
  negation-contrast + door personification — AND the chain's best
  plot revelation buried in an aside. Keep the revelation, say it as
  mechanism.
- **q1 barkeep intro**: "He made it answer, and it took his hand for
  the courtesy." — the door answers and charges courtesy.
- **q4 wolf_barkeep.active**: "drawing power in pulses, like it is
  listening for a response" — simile + listening.
- **q5 barkeep.active**: "whether the old rig still knows what it was
  built to do" — the rig knows.
- Clichés: "asks the wrong questions" (q1 desc), "clean enough to be
  dangerous" (q4 intro), "before the past catches up" (q5 intro),
  "the numbers stop behaving" (q4 intro).
- **Survivors worth keeping**: old_smuggler's flavor ("Cost me a hand
  and a good ship."), the wolf barkeep's deadpan threat register
  ("I have warned the Earth Barkeep, and I have not warned the
  Militia."), and possibly "Welcome to the family, friend." as the
  pirate-warm closer (settle in playtest).

### 2. Data/fiction break — the delve yields the wrong loot

Every text says q3 recovers **the power cell**; the data hands out
`machine_parts` + `electronics` (real market goods — the known
quest-cargo violation). Fix both at once: `delve_good_ids =
(("power_cell", 1),)` — the recovered cell IS the q4 crate, the
texts stay true, and the violation dies. Then reconcile the crate
sizes: q4/q5 carry `power_cell`/`power_cell_charged` ×5 but every
line says "the cell", singular — sizes should be 1.

### 3. The proof crate is a cataloged contraband good

q2 smuggles `weapons_blackmarket` — a real market good (contraband,
base price 250). Mission-hold means it can't be sold, but the
standard says quest cargo is named quest cargo. Settle: dedicated
quest good (e.g. "proof crate") vs keep — contraband running IS this
chain's fiction. (Doc leans dedicated: consistency with the enforced
standard; real contraband stays in the free-trading sandbox.)

### 4. Option label voicing

q2's give row is labeled "You asked to see me?" — the only
player-speech label in the game. Every other chain uses verb labels
("Hand over the crate").

### 5. Cadence

240 gate-days with 150 of them stacked before the delve (65 + 85).
Propose ~205–215 with no wait over 75 (e.g. 60/70/0/70): word
travels, the old man decides, the recharge. Settle first.

### 6. Structure checks that already pass

Atomic steps ✓ (each run is one beat); the crate flows auto-load at
the right moments (the recovered cell loads straight into the q4
run); giver-recovery prevents stranding; Q gates have flavor + ready.

## Phased implementation

### Phase 1 — audit (user playtest; no code changes)
- [ ] Fresh run with `SPACEHACK_SEED` pinned; log every dialogue
      beat, Q state, scan/aggro feel, the delve site
- [ ] Confirm/adjust the gap analysis; rule on the open questions

### Phase 2 — structure
- [ ] q3 delve yields `power_cell` ×1; q4/q5 crate sizes → 1
- [ ] Proof crate settled (dedicated quest good vs kept contraband)
- [ ] Cadence rebalance per ruling; verb label for q2's give row
- [ ] Remove bar's exclusion from the quest-cargo standard test

### Phase 3 — the prose rewrite (the main work)
- [ ] Rewrite every flagged line as mechanism, not mysticism: the rig
      brute-forces the power feed (say what it DOES); the cell holds
      a charge with a Militia serial (facts, no waiting/remembering);
      the old job's revelation said plainly
- [ ] Keep the smuggler/barkeep registers; sweep the clichés

### Phase 4 — closeout
- [ ] Fresh full run to the Mars door
- [ ] Corpus audit + `make check`
- [ ] Ask user: move doc to complete?

## Acceptance criteria

- Every item on the ten-point standard reads true for this chain.
- The fiction survives a logic audit: what the proof proves, why the
  cell matters, what the recharge does, what the rig actually does to
  the door.
- `make check` green; changes stay in step data + text unless a
  ruling demands mechanics.

## Open questions

1. Proof crate: dedicated quest good (lean) or keep
   `weapons_blackmarket` because contraband running is the fiction?
2. Cadence target: ~205–215 (e.g. 60/70/0/70) — or keep any of the
   three waits long as a deliberate beat?
3. "Welcome to the family, friend." — pirate-warm closer worth
   keeping, or cut with the rest of the cringe?
4. The old job's revelation (the door and a human signal) — keep as
   the chain's story hook, restated mechanically? (Lean yes: it is
   the best idea in the chain and it currently hides in an aside.)
