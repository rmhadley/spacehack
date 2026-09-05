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

## Settled design (user rulings 2026-09-05)

1. **Proof crate**: a DEDICATED quest good in the CONTRABAND category —
   cataloged like `weapons_blackmarket` (category=contraband, rarity
   0.1 so it never generates in markets) but quest-named. Note: the
   bar's procedural smuggle missions currently carry real market
   goods (electronics/machine_parts/luxury_goods/fuel_cells) — the
   main-chain crate establishes the dedicated-contraband pattern;
   converting the procedural crates is optional follow-up.
2. **Cadence**: 60/70/0/70 (~200 gate-days), even weights, no wait
   over 70 — in tune with the other chains. Stated philosophy: the
   player gets sandbox time, then the reminder prompts a keep-going /
   next-leg decision.
3. **"Welcome to the family, friend." KEPT** — earned pirate-cliché.

## SETTLED SPINE (user rulings 2026-09-05, two refinement rounds)

**The four doors doctrine** — each faction has a distinct, tangible
answer to the same door:
1. Merchants exploit WHERE it's weak — the survey says cut here.
2. Militia exploit WHAT it's made of — a charge tuned to the alloy.
3. Lab researches it and essentially hacks it open.
4. **Bar exploits WHAT POWERS it — overload the live lock.**

**The tool: a surge rig.** The door is sealed under power with an
external feed. The chain assembles a one-shot dump: the deep cell
(the battery from the old op, q3), the recharge (the only industrial
charger that can fill it, q4), the hot run home (a full deep cell's
discharge signature trips scanners, q5), and the rebuilt interface
frame (q6) — the old crew's clamps and leads, rewired to dead-short
the feed and empty the whole cell at once instead of cycling matched
voltage. Nobody holds the clamp this time.

**Signal mechanics (corrected):** the PLAYER intercepted a signal and
extracted Mars coordinates from it — the fiction never says the
signal came from Mars. At Mars, the door RECEIVED the same signal,
and receipt kicked it into an active mode it wasn't in before: it is
drawing power, humming. No "broadcasting", no politeness metaphors.

**Why now:** the signal changed the door's state. The old job's
matched-voltage cycling was the correct approach for a dormant
circuit — it is void against a live one, and a surge is only
possible against one. The intercepted signal is the precondition for
the entire plan. The old man is ready because the player's intercept
and readings prove his thirty-year bar tale is real; the player is
the operator because the Militia cannot retry an op that officially
never happened, and the old man has one hand and a file.

**The old job:** decades ago, a covert crew with Militia-issue
hardware matched voltage to cycle the dormant door; it discharged the
frame while his hand was on the clamp; the op was buried and the
cell written out of existence. He answered by turning black-market
smuggler - stubborn, not hiding: thirty years flying the Militia's
patrols out of spite (user ruling; NOT a cover story).
(Replaces the vague "human signal" revelation — the door's new
receiving state is the revelation.)

**The dig (ruling):** the old crew staged from Barnard's Star b, and
when the op was buried the Militia buried the file while the crew
buried the hardware - the cell has sat in that cache for thirty
years, and the old man retired nearby to watch it. The dig is the
cache, not the door site (the door is on Mars).

**Lore seed (free, uncommitted):** a door built to receive was
waiting for that signal. Someone sent it. The chain notices; Act 1
may explain.

## The plot, step by step (pre-rewrite summary — for the shape review)

**Setup**: you need a way through the Mars door. The bar's answer is
an old man who already lost to it.

- **q1 The Old Hand (Earth, 60d)** — the barkeep names a retired
  smuggler on Barnard's b: decades ago he found a door of "the same
  impossible material," and it took his hand; nobody believes his
  story. He owes the bar a favor — word is sent. The Militia has
  treated old routes like crime scenes since the Incident.
- **q2 The Proof Run (hot crate → Barnard's b, 70d)** — the old man
  deals in proof, not introductions: run the barkeep's hot weapons
  crate through scannable patrols. On delivery he marks the dig cave
  and (in an aside) reveals: the old job was not a robbery — it was
  an attempt to make the door recognize a human signal.
- **q3 The Power Cell (delve, Barnard's b, 0d)** — descend the old
  dig; recover the rig's power cell: decades-old MILITIA-issue
  hardware, unstable, holding a charge that doesn't decay like human
  cells. The militia circles the site.
- **q4 Black-Market Recharge (hot cell → Wolf 359, 70d)** — the
  listening-post operator has the only rig that can charge it: "still
  has a Militia serial... clean enough to be dangerous." Meter
  mysticism (to be cut). The old smuggler re-issues a confiscated
  cell if the run goes wrong.
- **q5 The Return Run (charged cell → Earth, 0d)** — the charged cell
  carries a signature the Militia thought erased; entering Sol trips
  auto-aggro. The barkeep wants to "finish one job in my life before
  the past catches up."
- **q6 The Rig (Earth)** — the brute rig, rebuilt. KEPT closer:
  "Welcome to the family, friend."

**Connective lore**: decades ago a crew carrying stolen Militia
hardware tried to make a door respond to a human signal; it failed,
took the old man's hand, and the file says the cell never existed.
Now the bar reassembles the same rig to force the door. The chain's
antagonist is the Militia (scans, serials, auto-aggro) — the mirror
of the merchants' consortium.

**Open shape decisions (ruling 4 pending)**:
- **A. Where was the old door?** The Mars door was only exposed
  recently — a decades-old door encounter needs a home. Lean: the old
  job WAS at the Mars door, before it was sealed — a deniable
  Incident-era Militia op to make the door respond (which makes the
  Militia serial and the nonexistent file load-bearing, and
  recontextualizes the old man: the burial made him an outlaw).
  Alternative: a second door exists (large lore commitment that
  ripples into Act 1+).
- **B. The revelation never pays off.** The signal attempt is dropped
  in an aside and the rig never references it. Keeping it means
  grounding the rig: talking failed and took his hand; the rig is the
  answer to that failure — one line in q4 or q6 closes the loop.
- **C. The cell's mysticism** (waiting / remembering / listening) is
  cut per the standard; what remains is strong without magic: Militia
  serial, erased signature, charge that doesn't decay.

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

1. ~~Proof crate~~ SETTLED: dedicated contraband quest good.
2. ~~Cadence~~ SETTLED: 60/70/0/70.
3. ~~"Welcome to the family, friend."~~ SETTLED: KEPT.
4. ~~The old job's revelation~~ SETTLED: the surge spine above — the
   old job cycled matched voltage on a dormant door; the intercepted
   signal put the door into a receiving, powered state; the surge
   plan exists only because of that change.
