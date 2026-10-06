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

## How Act 1 begins (settled 2026-10-06; supersedes the 09-05 sketch)

The player holds the archive — a copy was given away only if they
delivered. Either way **the player's own copy is being processed by
their ship**, and the act opens with the ONE gate in the act:

1. **The processing wait — 30 days.** Timer anchors at the prison
   escape (the orbit-modal choice rides the same moment). During
   the wait a ship-status tell exists in the UI: the ship's
   systems are processing the archive extracted from the deep
   prison. Visible, never nagging.
2. **Day 30: the ship pulls a coordinate.** A notification from
   the player's own ship — not a summons, not a faction messenger.
   The payload is a LOCATION ONLY: the Luyten star map (the M map)
   with an X on the east side [exact placement vs the restricted
   square — open]. The X is a persistent, inspectable map layer.
3. **The standing objective slots in** with the finding (below).

**FACTIONS ARE OUT OF THE ACT 1 OPENING (user, 2026-10-06):** the
delivered player's faction gives NO reading — old beat 3 (the
faction's biased interpretation, doc 07's table) is STRUCK. The
epilogue perk is the payoff, full stop; Act 1 is a new adventure on
our own. Whether factions meddle later is parked for later design.
Doc 07's first-readings table remains canon for LATER acts —
connective tissue, not this act's opening.

Why the player keeps going (the motivational spine, unchanged): the
player's own investigation has been ANSWERING the network — the
intercept, the descent, the reading. The door is humming. Whatever
transmitted isn't done transmitting. "I started this; how does it
end?" With no faction reading anywhere, the archive itself is the
only interpreter, for every disposition: sparse ambient decode
beats (a word resolving at a time on the console) are everyone's
clock, and the archive reacts the first time the player jumps into
Luyten holding the X (console line; the X pulses — the compass
beat).

### The standing objective

The quest log carries *"Investigate what's past Luyten's Star"* as a
held objective — not a chain of steps. **The X on the map IS the
lead presentation (settled 2026-10-06):** no quest-log lead lines,
no leads panel. Nothing expires; nothing nags.

### The suggestion layer (how the game says "you want this")

- **The anchor:** the X, always on the map.
- **The live archive:** ambient decodes + the compass pulse (above)
  — the only "reading" in the game now.
- **The rumor asks:** "ask about the blockade" options exist ONLY
  past the convergence gate (see the rumor family) — the visit is
  what makes asking make sense. An earlier lean ("asks unlock at
  X-reveal") was corrected by the user: the visit gates the whole
  ask.
- Ambient frontier myths about the blockade remain what they are:
  flavor, retold by people it happened to.

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
ghost run is the intentional sneak door with its own researched
requirements. Closing the gaps is fairness to the methods, not the
level gate.

**METHOD 5 CLOSED (user, 2026-09-06):** the fight is simply the
outcome of defiance — you ignore the warning when you fly through
and you survive. No bespoke method structure; the work is (a) tune
the convergence difficulty to the contract (provably unwinnable
below 30, significant at it) and (b) close the gaps so undefended
crossing is impossible: the picket must detect any approach (fill
the wall's spacing — the current 4-ship column leaves y 33-47,
63-77, 93-107 and both map edges open), the warning hail fires for
every detected hull, and ignoring it converges the whole blockade.
Survive = through.

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
| 2 | **The gate hack** — hack the Sol-side end of the ordinary Sol–Vega pair with Consortium codes from the Venus tower; one-way to Luyten's east end; the tech burns in the jump; no failure roll | The lab chain: gates work → modifiable → who writes the addressing (the corpo trail) | Raiding the Consortium tower on Venus (the codes); the tower is its own design doc | Kept players hold the node addresses in their own copy |
| 3 | **The ghost run** — CLOSED. DARK (hail-lure a picket with a false backup call — auth codes required — then coast the gap) or IMPERSONATION (wear a captured militia ID; only blockade rank or higher passes). Kit from THE HUNT: board the Blockade Commander | Frontier rumor (the windows chain); the manifest chain's rank fork | The Commander's transponder ID; the auth codes piggyback when the lure rumor is known; live skill for the coast | The smuggler's hold hides cargo; the hack hides the ship — the full ghost kit |
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
    the rumor-broker barkeep at **Whisper (lal_c)** — "The Vault, a
    smuggler moon where nothing is asked and everything is priced"
    (the planet's established fiction is the method's motto).
    PLACEMENT CLOSED 2026-09-05 after comparing candidates against
    the spawn data: Lalande 21185 and Ross 154 are the game's two
    pirate-heavy systems (tied density 7, warlords both; Lalande
    carries the heavier warlord weight, 0.35 vs 0.30); Lalande wins
    on depth — 4 jumps from Sol, one past Groombridge — so the trip
    crosses TWO pirate systems (Groombridge's scouts/raiders, then
    Lalande's warlord roster). Surviving the route is the gate; the
    system IS the prerequisite. Whisper's city map leans into the
    fiction: storage containers of illegal goods stacked in the
    streets (user). His contact "works the registry office" at a
    Line station. The intercept/bounty economy is the pirate-rep
    engine, mirroring the warrant board. Official route pays a
    2,000cr processing fee at signing.
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
  gate hack routes around the checkpoint entirely.

### Method 2: The Gate Hack — SETTLED 2026-10-06 (amends 09-05)

**The user's ruling, near-verbatim (the fiction spine, unchanged):**

> It's an existing gate in Vega, but with the right tech the
> destination changes. It's ONE WAY. High, high risk — you know
> it's taking you somewhere it's not designed to, and you don't
> know how you're getting back. The theory is it drops you past
> the militia blockade in Luyten where they can't see you. How
> you explain yourself if you try to return is unknown. Yet
> another poor choice — the theme of the main story overall: a
> series of poor choices that seemed like good ideas at the time.

**The gate (settled 2026-10-06):** the method hacks **the Sol-side
end of the ordinary Sol–Vega pair** — the commuter gate in the home
system — and it drops the player at the east end of Luyten instead
of Vega. The player never goes near the blockade at all: the
crossing happens from the heart of charted space, invisible by
construction, not by stealth. The retarget medium is **Consortium
gate-modification codes, extracted from the Venus tower** (Branch D
of the rumor family). "Do not restore the road" made literal — the
player perverts a human gate using exactly the knowledge the
archive warns about.

**THE HIDDEN GATE IS SCRUBBED (user, 2026-10-06):** the "hidden Sol
Gate" was snuck into the docs without the user's notice and was
supposed to be scrubbed already. Ordered out ENTIRELY:

- `data/solar_systems/vega.py` — the third JumpPoint row (~100),
  the docstring paragraphs naming it, the "three differently-
  coloured gates" palette note;
- doc 39 — every remaining "hidden gate" reference (method table,
  method interactions, the method-3 comparison, phase-0 checkbox,
  open question 5 — struck in this pass);
- doc 07 — seven spots (the story hook, the M3 mystery row, the
  `research_sirius` step text, the smuggler-path row, two phase
  checkboxes, the navigation note). **M3's whole mystery ("why was
  a supposedly decommissioned gate still active?") was built on
  the stowaway and needs retirement or rework — flagged decision.**

**Method identity — deniability:** the papers cross you ON the
record; the gate crosses you OFF it. Nobody knows you're past the
blockade. That invisibility is the unique payoff, and the price is
the one-way commitment and the unanswered return question —
designed tension, resolved by far-side content, not by this method.

**Closed rulings (2026-09-05 second pass; 2026-10-06 amendments):**

1. **The tech burns up in the jump.** One time, one way, risky —
   the codes/retarget are consumed. With nothing holding the
   retarget, the gate reverts to its Vega service — the poor
   choice leaves no trace, matching the deniability identity.
2. **No failure roll in v1.** The retarget option does not appear
   until the full working path is assembled — no partial attempts,
   no RNG misfire. The gamble/failure variants (black-market wrong
   addresses, random arrivals) stay shelved.
3. **Arrival: the far-east edge of Luyten**, at a
   jump-point-typical position — materializing where a gate would
   sit, with no gate there. (The X on the map points at this side
   of the system.)
4. **The derelict ping: SHELVED** — later phase; what stirs and
   when gets designed with the intermission.

**Method 2 status: CLOSED** — acquisition answered (the Venus
tower, Branch D); the tower itself gets its own design doc (101).

### Method 3: The Ghost Run — mechanics settling 2026-09-05

**TWO variants (user), same philosophy split as the whole act:**
dark is LIVE SKILL PLAY; impersonation is PREPARATION PLAY. Neither
is dice-gated — the act's ruling is preparation-gated, not
roll-gated.

**DARK — the hail-lure loop (user, from existing mechanics):**
you must already be dark to get close enough to hail. Use the
comms/hail system on a blockade picket, deceive them into changing
position (fake distress, false orders — dialogue options), then
stay dark as you coast through the gap you created. The loop:
approach outside detect radius (7-8) → hail one picket → choose
the deception → they move to investigate → coast the gap before
they return.

- The KEPT-exclusive decoy signal (combos table) tiers ABOVE this:
  the archive replay pulls the WHOLE net toward a false contact —
  safe, from range, no dialogue. Anyone with comms can lure one
  picket up close; the kept player moves the Line itself.
- Supporting existing mechanics: patrol movement/waypoints (the
  lure works because they physically reposition), sensor pings
  (the lure's fiction), bought rotation intel (frontier bars sell
  the schedule — narrative kit for knowing the thin watches), the
  smuggler's hold (if a patrol spots you dark and hails for a
  scan, your cargo at least is clean).

**IMPERSONATION — kit-complete, narrative-danger (user ruling):**
no staleness clock, no RNG. "The work is getting the kit complete"
— same shape as the gate hack. The kit: a captured live militia
transponder ID (boarded off the Blockade Commander) plus
presentation. (2026-10-06: the shadow-and-record acquisition is
retired with the hunt ruling.) The danger is NARRATED (codes rotate at 0600, the
badge may already be dead) — the fiction sounds terrifying, the
mechanics are the assembly. Only blockade-patrol rank or higher
gets waved through without papers.

**Closed rulings (2026-09-06, third pass):**

1. **THE LIE (settled):** one deception for v1 — a false backup
   call: *"someone is trying to run the blockade, backup needed."*
   The requirement that makes it work: sending that command on a
   TRUSTED CHANNEL with the RIGHT AUTH CODES. The codes must be
   obtained — which unifies the ghost run's acquisition economy:
   the same militia codes/IDs feed the lure AND the impersonation
   badge.
2. **SPOTTED DARK (settled):** a hail with a warning. The player
   must retreat and try again. Ignoring the warning brings the
   WHOLE BLOCKADE down — identical to running the Line with no
   plan. (Ties dark's failure into the shared interdiction
   response — the Line has one combat behavior, every method
   provokes it the same way.)
3. **THE ACQUISITION — SUPERSEDED 2026-10-06 by THE HUNT:** the
   kit comes from intercepting and boarding **the Blockade
   Commander** — a specific named militia ship, blockade-rank+,
   whose transponder ID is the impersonation badge. The same
   boarding also yields the trusted-channel AUTH CODES (the lure),
   but only if the player already knows the lure rumor (Branch
   B4): you only grab what you know to grab. The 09-06
   militia-building heist below is retired; the Venus tower
   (Branch D) inherits the act's-dungeon slot.

**Method 3 status: CLOSED** (the heist itself is a follow-on
design item — see Phase 0 list).

### The Militia Building Heist — SUPERSEDED 2026-10-06

Retired by THE HUNT (board the Blockade Commander) for the ghost
kit, and by THE VENUS TOWER (doc 101) as the act's dungeon. The
machinery inventory below survives — the Venus tower is its next
customer: multi-floor dungeon extensions (prison pattern), dormant
security that wakes on power events (doc 30), authored landmarks
with in-layout guardians, city building interiors.

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

## Acquisition is gameplay, not fetch (ruling, 2026-09-06)

The user's principle for every method's "you need X from Y" layer:
X and Y are never a fetch quest. Each acquisition uses the full
mechanical vocabulary already built — heists, delves, comms play,
shadowing, trade, rep economies, exploration — and the act's
sandbox is the discovery engine:

- **Any/all methods in parallel.** Nothing locks out anything — a
  player can hold papers, the ghost kit, and gate tech at once and
  choose the door (or keep backups). The only consumable is the
  gate's burned tech.
- **Hints surface through play, unlabeled.** Rotation schedules on
  warrant targets, anomalies in lab contracts, rumors in frontier
  bars — the game never says "this is the ghost-run step"; the
  player pieces together what each find OPENS. Comprehension is
  the puzzle.

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

## The rumor family — the discovery layer (SETTLED 2026-10-06)

Delivery is doc 42's system, already live: chains with tiers,
`sources` tuples (planet-scoped, faction/standing/trait floors),
`triggers` (world events that HEAR entries — `dark_berth` and
`taking_ships` are the two live chains today), the additive
keyring. One new trigger event carries this family.

**NAMING RULING:** player-facing text says "the blockade," never
"The Line" (design shorthand only). One shipped prose spot to
sweep at build time: the Blockade Officer hook ("This is the
line…").

**THE CONVERGENCE GATE:** the family starts only when the player
holds BOTH the X (the archive trait, day 30) AND the hail (the
sweep's turn-back warning flag). Either order; it fires at
whichever comes second, readout at that moment — the
blockade-first player's X-reveal is the stronger beat (the
coordinate lands on the place they were refused). The question the
family answers ("how do I get past") only exists when both facts
are held: the blockade alone is a wall with no reason; the X alone
is a destination with nothing in the way. Askable tiers require
the X trait (the sources' trait field). Retroactive players
(visited during Act 0) have the hail flag already set —
order-agnostic, nothing missable.

```
=======================================================================
 THE BLOCKADE RUMOR FAMILY (approved map, 2026-10-06)
=======================================================================

 THE CONVERGENCE (either order; fires at whichever comes second)

   [ X ON THE MAP ]----------------+
    day 30: the ship pulls          |   grants the archive trait
    a coordinate                    |
                                    v
   [ THE HAIL ]-------------------> T1  NOBODY PASSES
    the sweep's turn-back               trigger-fired readout; carries
    warning (sets the flag)             the hint in the warning's own
                                        words: "unless you're on the
                                        manifest, nobody passes"

 All askable tiers require the X trait (sources' trait field).
 Nothing is exclusive -- keyring additive, hold every branch.

-----------------------------------------------------------------------
 BRANCH A -- "the manifest"             (forks off T1's hint)
-----------------------------------------------------------------------
   A1  a list exists ................. [core tellers, official story]
    |
    +-- A2  two ways onto it
        +-- a) the official door .... [Earth, militia-leaning tellers]
        |       the Captain signs; allied militia + 2,000cr
        +-- b) the back door ........ [frontier run, pirate tellers]
                the Whisper moon; allied pirate + 10,000cr
            both --> TERMINAL: THE PAPERS (trait; waved through)

   A3  rank outranks the list ........ [stations / frontier witnesses]
        +-- the BLOCKADE COMMANDER wears that ID (a specific named
        |   militia ship, blockade-rank+)
        +-- the hunt: where she patrols, how to take her
            --> SET PIECE: intercept + board the Blockade Commander
            --> TERMINAL: THE BADGE (broadcast her transponder ID)
            +-- piggyback: the boarding also yields AUTH CODES
                (only if the lure rumor B4 is already known)

-----------------------------------------------------------------------
 BRANCH B -- "the windows"       (prerequisite: dark_berth, LIVE)
-----------------------------------------------------------------------
   B1  it has been run dark ........... [frontier bars, witnesses]
   B2  the watch thins ................ [bought rotation intel]
       the maintenance week: four ships, real gaps
   B3  the schedule ................... --> TERMINAL: THE GAP RUN
   B4  the lure: a false backup call moves a picket
       requires: AUTH CODES (from the Commander boarding)
       --> TERMINAL: THE LURE RUN

-----------------------------------------------------------------------
 BRANCH C -- "the seller"           (four tiers, ruled 09-06)
-----------------------------------------------------------------------
   C1  everyone out there knows someone ... [frontier myth]
   C2  someone at North ................... [Luyten station bars]
   C3  the Commandant (station NPC) ....... [deeper tellers]
   C4  the ask and the price .............. --> TERMINAL: THE TOLL
                                             (100k/crossing, fiction
                                              ledger)

-----------------------------------------------------------------------
 BRANCH D -- "the gate"     (lab start; the Consortium reveal)
-----------------------------------------------------------------------
   D1  how the gates work ............. [lab stations: officers]
       design, addressing, the old network
   D2  they can be modified ........... [deeper lab tellers, standing]
       the destination is a written thing -- but write access is
       not science, it's licensing
   D3  the corpo trail -- many open doors, one name
       +-- the chrome: who makes the cybernetics? [traders, techs]
       +-- the defector: a researcher who went corporate [labs]
       +-- corpo-flavored rows on the OPEN boards, unlabeled [post-X]
       +-- Venus street talk -- the loudest tellers at the door
       --> all converge: THE CONSORTIUM, the tower on Venus
       --> SET PIECE: THE VENUS TOWER (doc 101; walk-in door,
           hot-on-transgression; fight up; extract the codes)
       --> PAYOFFS: the gate codes + THE CONSORTIUM UNMASKED
           (the hidden faction's rep band revealed)
       --> hack the Sol-side Vega gate with the codes
       --> TERMINAL: THE CROSSING (one-way to Luyten's east end;
           the tech burns; arrival where no gate sits)

-----------------------------------------------------------------------
 BRANCH E -- the fight (no chain, by ruling)
-----------------------------------------------------------------------
   ignore the warning --> survive --> THROUGH
=======================================================================
 CROSS-LINKS: dark_berth (LIVE) gates B entry; taking_ships (LIVE)
 teaches boarding for the hunt; the Commander boarding carries
 B4's auth codes.
 HEAD STARTS (never keys): warrant_license -> militia standing
 (A2a); 12,000cr -> the Whisper fee / toward the toll;
 smugglers_instinct -> dark running (B); lab_credentials -> the lab
 economy (explicitly NOT a discovery gate); kept players hold node
 addresses in their own copy (D).
 EMERGENT (seeded, never authored): transponder spoof / convoy
 rider / decoy signal (kept-only).
=======================================================================
```

**Doctrines (user rulings, 2026-10-06):**

- **Nothing is exclusive.** The keyring is additive; open and
  complete as many chains as you want; all five methods in
  parallel.
- **Discovery is disposition-neutral.** Nothing in Act 1's
  discovery layer may sit behind an Act 0 perk or a locked board —
  D2-via-lab-contract was rejected for exactly this (the lab board
  belongs to lab players). The OPEN boards (bar/station pools
  anyone can take) may carry unlabeled corpo-flavored rows.
- **Unlabeled, always.** Topic labels are diegetic ("the
  manifest," "the maintenance week," "who gets through") — never
  method numbers.
- **The chain buys legibility, never permission.** Every door in
  the act is technically open all game; the price of admission is
  capability, not a plot flag. You can raid the tower blind —
  without D1–D3 you're holding Consortium addressing data you
  can't read, for a gate you never thought to hack.

**THE SECURITY LAW (one law, indoors and out):** presence is
legal; transgression converges the response. The blockade sweeps
crossers; the Venus tower runs hot only when the player does
something they're not allowed to — and it never seals (doc 30's
dormant-security machinery is the indoor version). The player
learns the rule once and it holds everywhere.

**Pre-req fork:** Branch D's chrome trail (D3) needs a
**cybernetics polish pass first** — forked as doc 102 (skeleton
ruled 2026-10-06; numbers/catalog pending there).

## Feature gap analysis (2026-09-06)

**Ruling recorded first:** heist design belongs INSIDE method design
— not one heist doc; each method gets action where it needs it
(delves, salvage runs, heists as required). This analysis asks: per
method, what do we lack a FEATURE for? Much of the act rides
existing machinery (comms/hail, squads, rep/attitudes, boards,
traits/perks, dungeon extensions, city interiors, landmark
guardians, save migrations).

### Per-method gaps

| Method | Rides on (exists) | MISSING |
|---|---|---|
| 1 Papers | rep/attitudes, allied threshold, captain + NPC seats, trait grant, credit payments | the sweep reading manifest/ID (shared: the Line); a new Whisper- class NPC (machinery exists — content, not feature) |
| 2 Gate | Vega gate data, quest-goods/kit assembly patterns | **gate retargeting** (jump connects_to is static); **arbitrary-coordinate arrival** (arrivals pair with gates; east-edge arrival has no gate); kit-gated option (payment gating pattern generalizes — small); the far side |
| 3 Ghost | comms modal + options, bump-to-hail, detect radii, dungeon extensions, dormant security | **the ship transponder/ID layer** (player ID, dark mode, spoof — nothing exists); **auto-hail/detect suppression when dark**; player-initiated hail of a picket (bump works mechanically, but comms options for deception are new); **scanning/observing an NPC ship** (capture broadcasts — no ship-scan interaction exists); **city → multi-floor delve linkage with gated entry** (extensions today enter from planet surfaces, not city buildings) |
| 4 Bribe | NPC + interior seats, big credit payment, dialogue | **the rumor chain** (unlabeled tiered hints surfacing through sandbox play — no rumor/lead feature exists; dialogue variants key off quest state, not "heard rumors"); the crossing event (shared: the Line) |
| 5 Fight | squads/reinforcements, comms warning options, encounter specs | tuning + gap-filling (design work, no new feature); "converge everything" escalation choreography (reinforcement machinery is close) |

**Gap-table amendments (2026-10-06, with the acquisition
redesigns):** the Commander hunt retires the ship-observation gap
(the ID is boarded off the hull, not broadcast-recorded); the
city→gated-delve linkage (row 6) survives with a new first
customer — the Venus tower, whose door is WALK-IN, not gated;
new small feature: the Consortium faction reveal (rep band
unmasked at the tower, riding existing rep machinery).

### The four feature commitments (user rulings, 2026-09-06)

1. **The Line as a system — design it right, rock solid, reusable.**
   Future acts may reuse the checkpoint/quarantine tech.
2. **The transponder/ID layer — a FULL SANDBOX FEATURE, not a
   quest mechanic.** User vision: "why limit it to this quest?
   A player might alter their ID to pose as a pirate while
   shipping a big haul through Ross." Identity is a universal
   RPG-sandbox system: IDs, scans, poses, consequences.
3. **The far side — CONFIRMED:** the red "restricted sector"
   square in Luyten is the placeholder for the anomaly the Militia
   is blocking. The alien tech unveils the act 1 finale THERE: a
   giant derelict alien ship to explore and loot (doc 37's
   intermission, now with a home).
4. **The lore & rumor system — YES, and huge.** A system that
   lets the player explore lore and RP with the universe to find
   solutions and unlock options: NPCs, comms, bars as delivery
   vectors; knowledge as the keyring. Design pass queued.
   Seed notes (user, citing Caves of Qud): loot that SENDS you
   somewhere (a find that points at a dungeon site); diving deep
   yields legendary loot AND/OR info; **info trades for info
   throughout the world** — knowledge as a currency with its own
   economy. Lore isn't just flavor: it's quests, maps, and
   bargaining chips.

Each gets its own design doc (forking as needed); doc 39 remains
the act umbrella.

### Cross-cutting, ranked by how much depends on them

1. **THE LINE AS A SYSTEM** — the checkpoint sweep (detect → warn →
   resolve), the sensor line with no geometric gaps, crossing
   resolution (wave through / turn back / converge), and the far
   side it guards. Every method terminates here. Today the
   blockade is four static ships with warning-only comms; none of
   the resolution logic exists.
2. **SHIP TRANSPOUNDER / ID LAYER** — the player ship's
   registration, NPC ships' broadcast IDs, dark mode (suppress
   auto-hail + checkpoint reads), impersonation (broadcast a
   captured ID). Feeds methods 1, 3 and the checkpoint itself.
   Nothing exists.
3. **THE FAR SIDE** — at least one system beyond the Line, the
   arrival placement, and what crossing unlocks. Nothing exists;
   the doc's standing prerequisite.
4. **RUMOR / LEAD DELIVERY** — unlabeled hints surfacing through
   sandbox play (bar talk, finds, contracts), tiered (myth →
   shape → witness → procedure). Methods 2, 3, 4 all discovery-
   ride on it; today rumor is static flavor text.
5. **GATE RETARGET + PHANTOM ARRIVAL** — method 2's core tech;
   single-method dependency.
6. **CITY → GATED DELVE LINKAGE** — the heist pattern (enter a
   building interior → multi-floor extension, entry gated by
   "the right steps"). Extensions exist but enter from planet
   surfaces; the city-building doorway does not.
7. **SHIP OBSERVATION** — scan/shadow an NPC ship to capture its
   broadcast (impersonation acquisition). Small, single-purpose.
8. Encounter math for the 30 floor — design/tuning; machinery
   exists.

Smaller needs that are content, not features: the Whisper and
Commandant NPCs, the Commandant's procedure dialogue, kit item
catalog entries, disposition no-op perks (machinery ready).

## Phases

### Phase 0 — THIS: the tweak loop
- [x] Opening settled (processing gate → findings light up the ship)
- [x] Method v0 table captured
- [x] Method 1 (the papers): CLOSED — two routes (Captain/Earth,
      allied militia + 2,000cr; Whisper/Lalande barkeep, allied
      pirate + 10,000cr, two pirate systems deep), trait-tracked,
      no aging
- [x] Method 2 (the gate hack): CLOSED — hack the Sol-side Vega
      gate with Consortium codes from the Venus tower; one-way;
      the tech burns; option appears only with the full kit (no
      failure roll); arrival far-east edge at a jump-point
      position; derelict ping shelved to the intermission phase
- [x] Method 3 (the ghost run): CLOSED — dark hail-lure (false
      backup call, auth-code gated) + impersonation (kit-complete,
      narrated danger); acquisition = THE HUNT (board the Blockade
      Commander; auth codes piggyback when the lure rumor is
      known)
- [x] Method 4 (the bribe): CLOSED — flat 100k, per crossing,
      fiction-only ledger, the Commandant of Blockade Station North,
      found via a four-tier unlabeled rumor chain
- [x] Opening SETTLED 2026-10-06: ship-status tell during the
      wait; 30 days; payload = the Luyten M-map X (location only);
      factions OUT (no reading — the perk is the payoff); the X is
      the lead presentation; the archive is everyone's clock
      (ambient decodes + the Luyten compass pulse)
- [x] The rumor family SETTLED 2026-10-06: convergence gate (X +
      hail, either order); T1 trunk; branches A/B/C/D/E as
      mapped; nothing exclusive; disposition-neutral discovery
      (no locked boards — lab-contract D2 rejected)
- [ ] Execute the hidden-gate scrub (vega.py's third gate row +
      docstring; doc 07's seven spots; M3 retirement decision)
- [x] The cybernetics polish doc FORKED as doc 102 (skeleton ruled
      2026-10-06; its numbers/catalog passes tracked there) —
      still the pre-req for Branch D's chrome trail
- [ ] The Venus tower design doc (stub: doc 101; needs gen powers
      beyond current — a delve that climbs, an HQ shape)
- [ ] The interdiction fight (the last method)
- [ ] Settle the open questions below
- [ ] Fork the intermission doc when the crossing is real

### Later phases (sketch — replanned after Phase 0)
- Structure (the Line system, methods, dig leads)
- Prose + playtest
- Closeout

## Open questions

1. ~~The processing gate~~ SETTLED 2026-10-06: 30 days; a
   ship-status tell during; the finding is a ship notification
   whose payload is the M-map X.
2. ~~The pull's framing~~ SETTLED (amended 2026-10-06): factions
   OUT — no faction reading for anyone; the pull is internal (the
   spine: the hum, "how does it end"), carried by the archive's
   ambient decodes and the compass pulse.
3. **The blockade's simulation scope:** fully simulated
   patrols/convoy schedules vs. authored set-pieces with
   simulated skin? (The emergent-combo layer depends on this.)
4. **What crossing mechanically means:** a jump route that's
   blockaded (unlock = the route opens by method), and at least
   one new system past the blockade — how much new space does
   Act 1 ship with the crossing vs. the intermission?
5. **The gate hack's fiction cost:** does the first activation
   carry a felt cost (using the network the archive warned about —
   "do not restore the road")? (The old "keep as the hidden-gate
   method" half is settled: scrubbed; the Sol-side hack stands.)
6. **Consequences after crossing:** papered players are watched
   and owe reporting; loud players are hunted; bribed players are
   in one man's ledger. How much consequence modeling in v1 vs.
   fiction-only?
7. ~~Lead presentation~~ SETTLED 2026-10-06: the persistent X on
   the map IS the lead layer; rumor asks open only past the
   convergence gate.
8. **The X's exact placement** vs the restricted square (on it —
   "your coordinates and their restricted sector are the same
   place" — vs just past it). Lean: dead-on.
9. **The Blockade Officer's shipped hook line** ("This is the
   line…") — player-facing naming is "the blockade" everywhere;
   one-line sweep decision at build time.
10. **M3's retirement/rework** (doc 07) — the mystery was built
    on the scrubbed hidden gate.
11. ~~D's deeper-tier delivery~~ SETTLED 2026-10-06: D1/D2
    askable at the labs (standing-gated; NOT via the lab board —
    locked boards privilege one disposition); D3 = the corpo
    trail (the chrome supply chain / the defector / open-board
    rows / Venus street talk), gated on the cybernetics polish.
