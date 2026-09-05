# DESIGN: Act 1 — The Luyten Blockade

**Status: DESIGN IN PROGRESS — no implementation until the user
explicitly requests it.** The rulings below are settled; the method
table is the v0 BASE and will be tweaked one-by-one with the user
before any build begins.

Companions: `07_DESIGN_MAIN_QUEST.md` (narrative canon: faction
first-readings table, three-path blockade history, the archive's four
layers); `complete/38_DESIGN_MARS_EPILOGUE.md` (the disposition
branch and perk rewards this act inherits);
`future/37_DESIGN_POST_ACT0_CAMPAIGN.md` (the roadmap: this is item
2; the derelict intermission is item 3).

## The act's shape (settled rulings)

- **Open world, non-guided.** One standing objective for most of the
  act: *"Investigate what's past Luyten's Star."* The investigation
  IS the gameplay: research, talk, explore, plan.
- **No time gates** — with ONE exception: the opening's
  data-processing wait (below). The player has proven they understand
  sandbox + main quest pacing; from here they choose their own tempo.
- **Reward clever gameplay.** The player should be able to devise a
  plan, research it, prepare it, and watch it work — and invent plans
  we never authored.
- **Faction rewards are head starts, never keys.** The epilogue perks
  (warrants, credentials, the hold, the 12,000cr) make some paths
  easier; none is required for any path.

## How Act 1 begins (settled)

The player holds the archive — a copy was given away only if they
delivered. Either way **the player's own copy is being processed by
their ship**, and the act opens with the ONE gate in the act:

1. **The processing wait.** Post-epilogue, the ship chews on the
   archive for [DURATION — open]. This is the act's only time gate.
2. **The findings arrive: the ship's systems light up.** Not a
   summons, not a faction messenger — the player's own console. The
   reading is legible enough on one point: the archive's waymarks
   cross known space and keep going, off every chart, past Luyten's
   Star. Something is on the other end of this road — and it is in
   the player's best interest to reach it before anyone else does
   [exact framing TBD].
3. **Delivered players get a second reading alongside:** their
   faction's biased interpretation (doc 07's table — quarantine /
   route / infrastructure / score). The kept player's reading is
   entirely their own — and their copy is the only copy they answer
   to.

Why the player keeps going (the motivational spine, from doc 07 +
the epilogue): the player's own investigation has been ANSWERING the
network — the intercept, the descent, the reading. The door is
humming. Whatever transmitted isn't done transmitting. "I started
this; how does it end?"

### The standing objective

The quest log carries *"Investigate what's past Luyten's Star"* as a
held objective — not a chain of steps. Discovered leads append as
[dig content — presentation TBD: quest-log lead lines? a leads panel?
or purely diegetic?]. Nothing expires; nothing nags.

## The Line today (tested 2026-09-05) + the floor ruling

**Test findings (code-level):** reaching the Line is trivial (a plain
wolf_359 <-> luyten_star jump pair, any level). The picket is four
static militia_blockade cruisers (60 hull each, heavy laser + light
missiles, one shared squad) at x=150, y=25/55/85/115, detect radius
7 — a wall with geometric GAPS (y 33-47, 63-77, 93-107, plus y<18
and y>122 open; the map is 140 tall). The restricted-sector marker
at (183, 62) is reachable clean through the middle gap at any level.
The contact is warning-only comms. And there is no "past": luyten's
only jump connects back; no far-side system exists.

**FLOOR RULING (user, 2026-09-05, clarified same day):** FIGHTING
your way through is a significant feat at level 30 and IMPOSSIBLE
below 30. Level 30 = 12,760 XP; the Act 0 epilogue lands ~12-18.
The hard floor belongs to the combat door only — the other methods
carry their own requirements, tuned per-method in the Phase 0 walk
(a clever sub-30 player crossing by papers, toll, gate, or quiet run
is the game working as intended: the fight is the brute-force door,
and brute force has a price of admission).

**Combat-door guarantee (lean):** the interdiction encounter — the
picket squad plus converged patrols — must be mathematically
unwinnable for the best realistic sub-30 fit (verify against
min-maxed skill spreads and tier-appropriate gear at 25-29), and a
real, costly fight at 30+ where the player has ~145 skill points and
cruiser/frigate-scale hull. Not "very hard" below 30 — PROVABLY
unwinnable; min-maxers find gaps in difficulty curves, so the
encounter math has to close them.

**Gap-closure still matters — but as the Line system, not the
floor:** free passage through geometric gaps should not exist; the
quiet run is the intentional sneak door with its own researched
requirements. Closing the gaps is fairness to the methods, not the
level gate.

**Prerequisite:** the far side needs at least one real system before
"past" means anything.

## The Line (design ambition)

**The blockade is a system, not a menu.** The crossing methods below
are ways through a simulated place, not dialogue options:

- **Patrol patterns** the player can observe (and learn the gaps in)
- **A scan checkpoint** at the jump gate, with rules the player can
  learn (transponder state, manifest, cargo)
- **Convoy traffic** — scheduled, boarded, scannable-by-association
- **An officer with signatures to give** and a price for each

The player's loop: **discover** a method exists (talk, rumor, intel,
faction reading) → **research** how it works (watch patrols, buy
intel, read the archive) → **prepare** (rep, credits, gear, ship) →
**execute** and see it work (or fail, learningly).

Scope ambition is an open question (see Open Questions #3): how
simulated vs. how authored each piece is.

## Methods past the Line (v0 BASE — tweak one-by-one with the user)

| # | Method | Discovered via | What it takes | Head start (never a key) |
|---|---|---|---|---|
| 1 | **The papers** — clearance through the checkpoint. SETTLED (below): two acquisition routes, allied standing either way, trait-tracked | The Line's warning hints a list exists; rumor fills in the rest | Allied standing — militia (official) OR pirate (back channel) — plus credits | Warrant-license players start on first-name terms |
| 2 | **The hidden gate** — the old network node inside known space that bypasses the Line entirely | Rumors at the edge; lab analysis contracts; deep-reading the archive | Finding it, then using unmaintained alien hardware | Lab credentials feed analysis work; KEPT players can research it from their own copy |
| 3 | **The quiet run** — a gap in the patrol net; a debris-field lane | Bar-side NPCs at the Line stations; bought intel | A ship that makes the run; nav through hazards; surviving a spot-check | The hold covers cargo if a scan catches you anyway |
| 4 | **The toll** — someone at the Line sells passage | Everyone at the Line knows someone | Credits and/or standing — with strings (a favor owed?) | Merchants' 12,000cr is exactly this kind of option |
| 5 | **The loud way** — punch through a patrol | No research needed | Surviving it; living with militia hostility after | Nobody — that's the point |

### Method 1: The Papers — SETTLED 2026-09-05

- **Discovery:** the Line's comms warning gains the hint — *"unless
  you're on the manifest, nobody passes"* — nothing more. Rumor and
  NPCs fill in how one gets on the list.
- **TWO acquisition routes** (the papers are not faction-locked):
  - **Official:** allied MILITIA standing + the right officer. The
    Captain at Earth signs (his desk is beside the warrant board —
    the grind and the signature share a room); the Blockade Officer
    at the Line honors it at the sweep.
  - **Back channel:** allied PIRATE standing + 10,000cr + finding
    the rumor-broker barkeep at Groombridge (groom_b — outskirts T3;
    Ross 154 is T4 pirate turf where a low-level outsider is asking
    to die) whose contact "works the registry office" at a Line
    station. The intercept/bounty economy is the pirate-rep engine,
    mirroring the warrant board. Official route pays a 2,000cr
    processing fee at signing.
- **Threshold: ALLIED (76+), both routes.** A real campaign; the
  Line is the Militia's most sensitive post and the back channel
  prices the same trust in a different currency.
- **Failure:** a refusal, never a firefight — the Line only fights
  those who ignore the warning to turn back. Asking is free.
- **Cost:** official 2,000cr; back channel 10,000cr. No
  standing-gated validity — getting ON the manifest is the whole
  gate. AGING: ruled OUT for v1 (the credential is permanent;
  crossing is not farmable).
- **Tracking — the trait system, per user ruling:** a
  `blockade_manifest` trait granted at acquisition — persisted in
  `player_traits`, checked by `has_trait` at the sweep, registered
  alongside QUEST_PERKS so milestone screens never offer it. No new
  system; the checkpoint reads one trait.
- **Method interactions:** the sweep checks transponder against the
  manifest registry — the papers DEFINE the checkpoint's rules. The
  spoofed transponder fakes what the papers are; the convoy manifest
  borrows what they grant; the decoy signal skips the sweep; the
  hidden gate routes around the checkpoint entirely.

### Systemic combos (emergent, not authored paths)

Plans that emerge from the Line's systems stacking — the
"reward thinking" layer:

- **Transponder spoof:** buy a scrubbed transponder + clean cargo =
  the checkpoint reads a tramp hauler with a clean record.
- **Convoy rider:** buy onto a merchant convoy's manifest — guild
  traffic doesn't get the full scan.
- **The decoy signal (KEPT exclusive):** replay the archive's signal
  to pull the patrol net toward a false contact, then cross quiet.
  The data the kept player refused to share becomes a tool no
  faction player has — doc 37's promised twist, arriving exactly here.

These are NOT scripted quest paths: they fall out of transponder
state + manifest + cargo + patrol position interacting. A clever
player invents a plan we never authored; the game just has to honor
it.

## Dig content (optional, reframing)

*Why is there a blockade at the ass end of charted space?* The
curious player can dig: bar rumor, classified militia files (rep- or
warrant-gated), trade records, lab chatter. The scandal they can
assemble: **the Militia detected something out there** (they won't
know the word "derelict" yet). The Line isn't keeping people in;
it's keeping what's out there quiet. Learning this is never required
to cross — but it reframes every method, and it's the intermission's
setup.

## Disposition flags (agreed, to implement with the act)

Merchants and solo dispositions also record perks on epilogue
completion — no-ops today, hooks Act 1+ reads (working names
`guild_dividend`, `lone_hand`). Every disposition lands a flag; no
special-casing "delivered merchants" or "kept" later. The decoy
signal is the first `lone_hand` payoff.

## After the crossing (placeholder — designed after methods settle)

Doc 37 item 3: use the Mars-prison knowledge to unmask the giant
alien derelict past the Line — the thing the Militia scanners
detected when the Line went up. Dive it (prison pattern), emerge
with the alien jump drive → Act 2. Outline only; we design it once
the crossing is real.

## Phases

### Phase 0 — THIS: the tweak loop
- [x] Opening settled (processing gate → findings light up the ship)
- [x] Method v0 table captured
- [x] Method 1 (the papers): CLOSED — two routes (Captain/Earth,
      allied militia + 2,000cr; Groombridge barkeep, allied pirate +
      10,000cr), trait-tracked, no aging
- [ ] Walk each remaining method one-by-one (suggested order:
      hidden gate → quiet run → toll → interdiction fight)
- [ ] Settle the open questions below
- [ ] Fork the intermission doc when the crossing is real

### Later phases (sketch — replanned after Phase 0)
- Structure (the Line system, methods, dig leads)
- Prose + playtest
- Closeout

## Open questions

1. **The processing gate:** duration? Presentation when it clears —
   popup, log line, or a diegetic console screen?
2. **The pull's framing:** "best interest" — competitive (someone
   else may reach it first), ominous (the network is waking), greedy
   (what's out there is valuable), or a blend the player's faction
   reading tilts?
3. **The Line's simulation scope:** fully simulated patrols/convoy
   schedules vs. authored set-pieces with simulated skin? (The
   emergent-combo layer depends on this.)
4. **What crossing mechanically means:** a jump route that's
   blockaded (unlock = the route opens by method), and at least one
   new system past the Line — how much new space does Act 1 ship
   with the crossing vs. the intermission?
5. **The Vega gate:** keep as the hidden-gate method (long-seeded),
   and does its first activation carry fiction cost (using the
   network the archive warned about — "do not restore the road")?
6. **Consequences after crossing:** papered players are watched and
   owe reporting; loud players are hunted; toll players owe a favor.
   How much consequence modeling in v1 vs. fiction-only?
7. **Lead presentation** for the standing objective: quest-log lead
   lines, a leads panel, or purely diegetic discovery?
