# DESIGN: The Transponder / ID Layer (sandbox-wide)

**Status: DESIGN IN PROGRESS — for review with the user before any
build.** The first of doc 39's four feature docs, forked in the
agreed order (transponder → the Line → lore/rumor → far side).

Companion: `39_DESIGN_ACT1_BLOCKADE.md` (the act that needs it);
the ghost run (method 3) is its first quest consumer; the Line
(checkpoint sweep) is its first systemic consumer.

## The ruling this doc serves (user, 2026-09-06)

> A full sandbox feature, not a quest mechanic. Why limit it to
> this quest? A player might alter their ID to pose as a pirate
> while shipping a big haul through Ross. Identity is universal.

## First-pass shape (for review)

**Every ship broadcasts.** An ID is a ship's public identity —
what scanners, patrols, checkpoints, and other ships read at range.
The player's ship has a registration; NPC ships broadcast theirs.
Space already tracks ships by position and detect radius; identity
is the layer that says WHO, not just WHERE.

**Three broadcast states** (the ghost run's language, generalized):
- **Live** — your true ID. You are who you say.
- **Dark** — no broadcast. You don't appear on scanners; patrols
  that physically spot an unregistered hull treat it as suspicious.
  Suppresses auto-hail (today's proximity hail keys on broadcast).
- **Spoofed** — a chosen ID broadcasts in your place: a scrubbed
  civilian identity, a cloned ship, a captured militia callsign.
  What reads you reacts to who you PRETEND to be — until the
  pretense fails a check (registry mismatch, the real ship sighted,
  a dead rotation code).

**Who reads IDs (consumers):**
- Militia cargo scans (today's scan flow gains an identity read:
  the log records WHO was scanned)
- Patrols' auto-hail and detect behavior (a militia ID hailed by
  militia = routine; a dark hull = challenge; a known-pirate ID =
  hostile, maybe)
- The Line's checkpoint sweep (doc 41's primary reader)
- Faction response generally: pose as a pirate through Ross and
  pirates wave you through; pose as a pirate through Sol and the
  patrols react (user's exact scenario)
- Merchants/comms contacts: hail behavior flavored by what you
  appear to be

**Changing state** (how identity is worked on):
- Equipment is the lean: a transponder as a real thing aboard —
  modes selectable; scrubbable at outlaw ports; clone-capable with
  the right tools/service. The heist, Deadfall, and Whisper become
  the identity economy's storefronts.
- A service tier: the hacker/Docker NPCs sell state changes, fresh
  scrubs, cloned IDs — reputation-gated like everything else.

**Persistence and consequence (the lifestyle price):**
- Your broadcast state persists until changed — flying a false face
  through EVERY scan, not just crossings.
- Actions attach to the ID you wore: crimes committed dark are
  unsolved; crimes committed spoofed attach to the SPOOFED id
  (frame someone? a militia ID committing piracy is a diplomatic
  incident — huge design space, park for v2).
- Factions may eventually KNOW registrations: repeat contact builds
  recognition (v2+; parked).

## SETTLED (Q1, user rulings 2026-09-06): the ID model

**The system already exists — it's just always in live mode.**
Ships detect us, identify us, pull faction ratings, behave
accordingly: that IS a broadcast resolving to relations. An ID is
*an identifier that maps to current relations.* The transponder
layer is not a new identity system — it's a choice of which key
the reader resolves:

| Broadcast | Reader resolves | Behavior |
|---|---|---|
| Live (today's default) | true ID → actual faction ratings | the game as it stands — zero new behavior |
| Dark | no ID → nothing | unknown-vessel protocol: challenge, suspicion, the Line's hail |
| Spoofed | the chosen ID → the relations that ID implies | readers react to who you appear to be |

**Spoof sources (exactly three — each ID carries its own rep
sheet; the source determines how the sheet is made):**
- SCRUBBED → literally a sheet of 0's across the board: all
  factions neutral. A tramp hull with
  no history; every reader's default-civilian posture. The
  cheapest lie — "I'm no one."
- CLONED → the sheet is ROLLED from the source at capture (one
  roll per source, quality-weighted): a Ross pirate's ID carries
  pirate-allied values; a militia patrol's ID carries militia
  standing. The ID holds real values of its own.
- FABRICATED RANK → an authored sheet (act-1 quest content): a
  command callsign carries whatever standing the content grants
  it.

Registration/class/port are PRESENTATION surface (what a scan
displays and verifies), not the functional model.

**Explicit IDs (ruled for the RP flavor):** the player's ship
carries a visible registration string. Scans can SHOW it; scrubs
visibly replace it. One persisted field.

**The F — faction screen is the identity hub (user idea):** the
ID wires into the faction view — flavor for immersion (your
registration, your broadcast state) and the screen used to CYCLE
THROUGH ILLEGAL IDs COLLECTED. Identity and reputation live on one
screen because an ID maps to relations: manage what you wear where
you see what it resolves to.

## SETTLED (Q2, user ruling 2026-09-06)

**Intrinsic transponders** — every ship has one; it's law
equipment, not a module slot. Mode changes are worked via services
and tools (the outlaw ports are the identity economy's storefronts).

**Identity rides the player across LAWFUL ship purchases** — the
registry transfers you, the owner, to the new hull. Buying through
legitimate channels is NOT a scrub: your record follows you.
Corollary (implied, for ruling confirmation): the ship-swap scrub
exists only through UNLAWFUL acquisition — a hull bought
no-questions-asked comes unregistered (or wearing whatever face it
died in). Disappearing means going where the registry doesn't look.
(Note: unlawful ship sales are currently content that doesn't
exist — a black-market ship market becomes a design note.)

**The mask cuts both ways (follows from Q1's model):** a scrubed ID
resolves to BLANK — readers don't see your true ratings, which
means friends don't recognize you either. Merchants won't wave a
guildmate through a mask; militia won't honor an allied record.
Wearing a face trades your real standing for the face's — always.

## SETTLED (Q3 + Q4, user rulings 2026-09-06)

**Q3 — dark's counter set is COMPLETE as: eyes + the Line's
density.** Patrols' detect radius (physical spotting → the warning
hail, per doc 41) and the edge-to-edge sensor line. No scanner
upgrades, no station approach logs in v1. Dark beats electronics,
not eyeballs, and the Line is where the eyeballs live. (User note:
dark mode is welcome as a REUSABLE option — other encounters and
future content may key on it.)

**Q4 — the true ID IS the faction ratings; nothing new is built.**
True ID resolves to ctx.faction_reputation (decay applies — the
monthly decay toward neutral already exists in faction.py).
**THE TWIST (user ruling): doing things with a fake ID cannot
alter your true ID.** Consequences route to the ID you WORE:

- Live: rep deltas (gain and loss) move your true ratings. To
  build standing, you must be seen being yourself.
- Masked, DARK ONLY: rep deltas are DISCARDED — nothing records
  (crimes committed dark are unsolved). Hiding is safe.
- Masked, SPOOFED (re-ruled 2026-09-06 — the first-pass shape was
  right): deltas land on the WORN ID's sheet. "If I put on a fake
  ID and go terrorize some merchants, merchants will distrust that
  ID." A fake builds its own record — hot after piracy, welcome
  where its sheet is liked. Your true ratings are only ever touched
  while ID 1 broadcasts, or by time decay (time, not behavior).

(The frame mechanic — crimes attached to a CLONED id blaming the
clone's source — follows from Q1's mapping and is parked as the
natural v2 depth; v1 routes masked consequences nowhere.)

## SETTLED (Q5 + Q6, user rulings 2026-09-06 — REVIEW COMPLETE)

**Q5 — nothing breaks a complete spoof in v1.** Electronic
identity is as strong as its kit; the counter-play is physical and
behavioral (eyes, the Line's density, wearing the wrong face in
the wrong system). FUTURE HOOK (user, parked): the sci-fi boarding
trope — circumstances force a local military to board/investigate,
and the broadcast ID doesn't match who you physically are. In-person
inspection as a spoof-breaker lives in future design space.

**Q6 — NPCs broadcast, integrated into comms.** Every ship in
space resolves an identity; the comms system shows who you're
hailing (and what they claim to be). The world becomes legible at
range, and the player's mask is meaningful by symmetry.

**Cloning is RARE and DIFFICULT (user ruling):** in a real
universe, if cloning anyone were trivial, there'd be chaos. Getting
an illegal ID must be an expensive, involved PROCESS — not a
button. Reading broadcasts is free; CAPTURING a cloneable ID is a
pipeline (tools, services, opportunity, risk). The aspirational
sandbox depth (user): a player who goes through the whole process
to clone a pirate warlord and operate in Ross under his face has
earned that power.

## SETTLED (dark's price, user ruling 2026-09-06)

**Scrubbed and dark are different contracts.** A scrubbed ID is
talking while saying nothing: the transponder answers every query
with blank paper, and blank paper complies — to any reader you're
one of thousands of nobodies. Dark refuses the conversation, and in
patrolled space silence is loud: every system that expects a
transponder treats an unresolved contact as an incident. The
6,000cr buys anonymity WITH compliance; dark buys anonymity at
cost. (Before this ruling the two states were nearly identical in
play — both froze rep and masked the F screen; nothing else read
the difference.)

Two consequences, DARK ONLY (never scrubbed):

1. **Dark berths only at pirate-run ports.** The refusal is not
   militia law — it's the port's own skin: a hull that won't say
   its name leaves nothing to log, no one to bill for the pad, no
   recourse when the berth is stripped. So EVERY lawful port
   refuses (Earth, Vega, anything militia-patrolled) and so do
   neutral ports with no militia in sight — trust is the gate, not
   patrols. The exceptions are a handful of clearly pirate-run
   ports that don't ask (today: Deadfall and Whisper in Lalande,
   Ember in Ross 154, Wolf 359 b — an explicit whitelist; additions
   are deliberate content, not system growth). Those doors are what
   keep dark usable for its purpose (ghost-running, the far side).
   MECHANISM (user ruling): the whitelist is DATA, on the city
   config itself — a ``dark_berth`` opt-in field on ``PlanetSpec``
   (default False), set True in each pirate-run planet module. The
   whitelist is the sum of the data opt-ins — grep-visible, no id
   table in code; adding a port is a one-field content edit. The
   dock gate reads the spec of the port being landed on.

2. **Patrol challenge hails.** A militia ship that detects a dark
   contact hails the PLAYER (NPC-initiated comms): identify or
   open fire — TWO OPTIONS ONLY (user ruling 2026-09-06: no RUN —
   the game has no run mechanic; if one is ever designed, its doc
   collects every interaction of this kind). IDENTIFY is the moment
   of truth — flip live or wear a face, and what resolves is what
   gets judged: a scrubbed hull is waved through, the true ID gets
   its record's due, a wrong face gets that face's trouble.
   ATTACK escalates — guns, heat; pressure, never a guaranteed
   kill. The ghost run keys on dark, so its tools (a ready face,
   the lure call) answer this hail through IDENTIFY — tuning
   deferred to doc 39 when that method is built (user: figure the
   ghost-run details later; make this make sense first). Pirates
   never challenge; silence in Ross reads as business as usual.

## SETTLED (phase 4+ re-cut, user rulings 2026-09-06): one current reputation + dark's price of entry

**One primitive — no custom code.** The broadcasting ID's rep sheet
IS your current reputation; every reader resolves the same sheet
(dark → neutral). The Ross pose is the mechanic working, not a Ross
special-case — "if Ross right now auto-attacks everyone no matter
what, that's incorrect" (user ruling). Every spawn reader —
static/territorial, bounty, procedural — runs the SAME gate: engage
only when the RESOLVED attitude is disliked/enemy.

Consequences (all follow from the one gate):
- In-group ID: a pirate clone's sheet resolves Allied with
  pirates — the crown stands down.
- Blank paper (scrubbed) resolves default-civilian neutral: nothing
  auto-attacks a nobody — but nobody helps a nobody either (no
  in-group recognition; militia scans at neutral rates). The scrub
  buys compliance, not friendship; allied is what the clone ladder
  buys.
- Dark resolves nothing: pirates' silence-reads-as-business-as-usual
  (settled above) — no auto-attack; militia that physically spot the
  hull run the challenge (3b, built).
- Live unchanged: the true record resolves as always.
- The charged-cell heat aggro (Act 0) is a HEAT response, not an
  identity read — it ignores the broadcast (flagged to the user
  2026-09-06; unchanged unless vetoed).

**Dark's price of entry (user ruling): cut-out service.** Going
dark is NOT a free toggle on a legal hull. A one-time transponder
cut-out must be installed at a pirate-run port (priced below the
scrub — silence is cheaper than paper). STOREFRONT SPLIT
(superseded same-day ruling, 2026-09-07): NOT the same storefronts
— the scrub stays at Deadfall's Registry Broker; the cut-out
installs at Ember's tech in Ross 154 (see the placement SETTLED
section).
Until installed, the F-screen D is inert. This matches Q2's "mode
changes are worked via services" and gives the identity economy its
second product; the early outlaw-port errand is dark's on-ramp. The
lifestyle price (refused docks, challenge hails, the Line) stacks
on top. The scrub keeps its niche: anonymity WITH compliance.

## SETTLED (capture + clone quality, user rulings 2026-09-06)

**The sheet IS the standings — not a parallel track.** Phase 4 does
not build a new reputation system beside the real one — the
broadcasting ID's own sheet is what the game already reads, and
every existing consumer (spawn gates, scan tables, trade, comms
attitudes) keeps its exact logic, pointed at the sheet. We have
faction standings; they already have meaning; the worn ID's sheet
supplies them and the game reacts through machinery that already
exists. Reads resolve the broadcasting ID; writes land on the
broadcasting ID's sheet — dark records nothing (Q4, re-ruled
2026-09-06).

**Capture is live-ship boarding (user ruling — new feature).** The
shadow/record verb is replaced by boarding: meet the requirements
(no shields up, 75% hull damage done, no other ships in the
encounter, player adjacent — BOARD is offered IN COMBAT; user
ruling 2026-09-07), board the LIVE ship — not a powered-down
derelict, a functioning enemy hull with a full crew aboard — fight
your way to the cockpit and the C console, and with the tech
available, clone the ID from there. (Scoping pending: own sibling
doc vs a phase here — the feature is bigger than the capture verb;
boarding derelicts already exists today.)

**Clones roll their sheet (user ruling — iterates faction
profiles).** A clone's sheet is a ROLL within the source faction's
profile: the higher quality the source ship, the better the odds
of a strong roll. RNG + grind behind a powerful perk. The
library consequently needs management — the ability to delete (or
sell!?) transponder codes. Parameters pending: the profile bands,
quality weights, re-clone/re-roll semantics, library cap/sell.

**Roll parameters (user ruling): one roll per source.** Each source
rolls once, ever — a bad roll is a bad ID and no credits re-roll
it; better odds require capturing higher-quality sources. The grind
is the HUNT. Delete exists to clear junk. (Enforced physically
since 2026-09-07: each hull boards ONCE — exit consumes the ship —
so a re-roll requires hunting a new hull, and the entry persists
the rolled sheet.)

**Library (user ruling): capped slots + delete + sell.** Small fixed
library (slot count pinned in the phase 6 brief), delete free at the
F screen, outlaw-port brokers buy codes back for a fraction of
value.

**Boarding is an extension, not a new system (user correction).**
Ship boarding already exists (wreck bump-boarding into dungeon
interiors, ``game_interactions._resolve_npc_ship_blocker``); the
capture phase EXTENDS it to live ships — no sibling doc. V1
(ruled 2026-09-07, supersedes the first-pass calls): BOARD appears
IN COMBAT when the target has no shields up, has taken 75% hull
damage, is the ONLY active enemy in the encounter, and the player
is adjacent (user's in-universe framing: boarding with active
enemies would be risk — the option requires a duel). The interior
spawns its crew (ENEMY markers authored per faction — content,
scout_a precedent); the C console at the cockpit offers the clone
with the rig installed; ON EXIT THE SHIP IS CONSUMED — gone, just
like derelict boarding (user: "you can't reboard a ship after you
board it once") — no map-level crippled state, nothing new to
persist for it. A kill still just kills: overkill destroys the
prize (no wreck salvage). Ship theft parked.

**Phase cut (2026-09-06):** phase 4 = the broadcasting ID's
reputation (originally cut as "apparent standings"; re-cut to
sheets the same day), phase 5 =
dark's cut-out, phase 6 = the capture pipeline. The Line's sweep
remains doc 41's build — doc 40 supplies the states.

## SETTLED (re-cut: IDs carry reputation sheets, user ruling 2026-09-06)

**A transponder ID maps to a set of reputation values — reputation
drives this system 100%.** (User ruling, verbatim: "a transponder
ID is an ID to a set of reputation values... Reputation drives
this system 100%. Your transponder ID is what determines your
current reputation.") There is no spoofed "face" that maps to a
faction — that framing (``apparent_faction``, the F screen's faked
rows, the challenge hail's militia-callsign special case) was a
wrong turn in the earlier phasing and is SUPERSEDED. Each ID in
the library carries its own rep sheet (a ``{faction: int}`` dict):

- **ID 1 — the personal ID.** Rides with the player across every
  lawful ship purchase; its sheet IS ``ctx.faction_reputation``.
  Writes follow the broadcast (re-ruled 2026-09-06): live → ID 1's
  sheet; spoofed → the worn ID's sheet (a fake builds its own
  record); dark → nothing records. Time decay always ages ID 1.
- **Scrubbed** → literally an ID with 0's across the board for
  faction reps (user ruling). Blank paper, exactly as ruled.
- **Cloned** → the sheet is ROLLED from the source at capture (the
  one-roll-per-source, quality-weighted ruling — re-expressed: the
  roll generates the sheet).
- **Fabricated** → an authored sheet (act-1 quest content).

Every reader in the game reads one thing: the sheet of whichever
ID is broadcasting (dark → neutral, unchanged). No faction-mapping
step exists anywhere in the player layer — no read keys on the
face's ``faction`` field. Consequences:

- The challenge hail's special cases collapse into the value read:
  a militia sheet passes because its militia VALUES pass; a hostile
  sheet (pirate clone, bad true record) draws fire. Same outcomes
  as 3b's playtested behavior, one mechanism — the modal, two-option
  set, and one-shot tracking are untouched; only the judgement's
  read swaps to the sheet (phase 4). Caveat (ADVISE review): in
  phase 4 only the scrub exists (all-zero passes — outcomes
  identical); phase 6's roll profiles own the pirate-sheet-passes-
  a-neutral-militia-read case.
- The F screen renders the broadcasting ID's actual sheet — no more
  "Friendly (Faked)" / "No Data" approximation rows (the broadcast
  block still says which ID and which mode).
- The spawn gate is unchanged (engage only on resolved
  disliked/enemy) — a pirate clone stands the Ross crown down
  because its sheet's VALUES are allied-with-pirates.
- Ground reads the same sheet (user ruling: no over-complicating —
  on-foot faction hostility, ``faction.spec_is_hostile``, is the
  same read as the ship's transponder).

**Statics: uniform gate, no exceptions (user ruling 2026-09-06,
verbatim: "Leave it as is right now. If there are other statics
that always engage right now, so be it.")** No territorial /
always-engage exception flag is authored — the rep gate applies to
every static spawn. Known collateral, ACCEPTED: the act-1 Luyten
militia blockade (``luyten_star.py`` static EnemySpawns, faction
militia) stands down for any hull whose resolved militia standing
is not disliked/enemy — a default character (militia +50, liked)
sails past live. If act 1 wants the blockade drama back, re-keying
it is doc 39 content, not doc 40. (ADVISE review verified:
derelicts spawn via ``derelict_spawn_chance``, a separate roll —
they never route through this pass.)
- No save migration: legacy library entries without a ``rep``
  field read as an all-zero sheet (every collectible ID today is
  scrubbed); new scrubs materialize the zeros at purchase.

## SETTLED (phase 5 residuals, user rulings 2026-09-07): cut-out specifics

Four decisions the approved phase 5 brief left open, settled at
refine:

- **The cut-out RIDES THE PLAYER across lawful ship purchases**
  (Q2's frame, extended): it is a player-level flag like the ID
  library and the registration — the registry transfers the owner,
  cut-out included. No purchase-path handling.
- **Installed = the broker row disappears.** The install row is
  offered only while uninstalled — the same conditional mechanism
  as the scrub row. No re-buy path, no refusal prose.
- **Strings pinned verbatim** (user-approved draft): F-screen hint
  while uninstalled ``ENTER / ESC back   D transponder (no
  cut-out)``; D-press refusal ``No cut-out installed.``; broker row
  ``Install a transponder cut-out (2,500cr)``; install log ``Cut-out
  installed.``
- **Load invariant: no cut-out ⇒ never dark.** One uniform guard in
  saveload — a legacy save broadcasting dark resets to live at
  load, logging one line when it fires. Not a special case: it is
  the invariant the new field introduces, applied at the one place
  every legacy save passes through.

## SETTLED (cut-out storefront placement, user ruling 2026-09-07)

**Scatter the identity economy across the universe** (user: "I
want to scatter this across the universe... a different solar
system at a different npc in a different building"). The Registry
Broker at Deadfall keeps the scrub as his only product. The
cut-out tech is a NEW NPC seated in **Ember's depot interior**
(Ross 154) — the warlord's flare-scorched yard at the end of the
arm, reached via Sirius. Placement rides the proven additive
interior-seat pattern (``quest_npc_spots`` — the
Xenolinguist-in-the-lab precedent; Ember already hosts a seated
spot), generalized to an always-on variant (today it is
quest-conditional). The tech's flavor carries the teaching
in-character (the F screen, the D key, what it costs him — docks
included); the guide carries the mechanics. Wolf 359 b was the
runner-up (frontier listening post, Luyten-gate adjacent) —
passed over this pass; a brand-new pirate port remains
deliberate later content. Name/flavor drafted at build,
user-dictatable; offer row and install log stay as pinned above.

## SETTLED (boarding coverage + bounty consume, user rulings 2026-09-07)

- **Every ship you fight is boardable.** Coverage is no longer a
  per-spec opt-in rollout: each battle-capable NpcShipSpec gets a
  crewed capture layout (authored per faction, ship-anatomy
  coherent). The `capture_layout_id` field stays the mechanism —
  it just stops being a two-spec pilot.
- **Consuming a boarded bounty ship completes the bounty.** The
  "can't reboard — the ship is gone" consumption is the boarding
  twin of the kill: for bounty-linked hulls, exit-and-consume
  counts for the bounty goal. (Kill-adjacent bookkeeping — rep
  deltas, XP, the tombstone — is 6c brief material: settle what a
  consumed hull shares with a killed one.)
- **Layout quality bar:** ship interiors follow the ship-layout
  grammar — doors connect (no door to nowhere), the hull envelope
  seals (no interior cell open to space), BFS-validated. The
  layout editor gains these two ship-interior checks, and the
  authoring is collaborative: agent drafts, user walks the deck
  in-game, iterate.
- **Consume = full kill treatment, minus exterior loot (user
  ruling 2026-09-07: "treat it exactly as a kill in all cases,
  not just bounty targets. minus one thing -> no loot dropped.
  you pick the loot up on the ship").** Rep deltas, XP, counters,
  tombstone, bounty/heist bookkeeping — the whole `_record_defeat`
  pass — applies to the consumed hull; only the exterior loot
  scatter is suppressed (heist mission cargo rides INSIDE the
  capture interior via the existing component-good mechanism).
  This supersedes 6a's bounty/heist BOARD exclusion: quest-linked
  ships are boardable, and the quest bookkeeping treats the
  consume as the kill it replaces.
- **The authoring pipeline (agreed 2026-09-07):** the agent
  authors a JSON spec (rooms with names/rects/roles/twins, door
  EDGES, entry breach/spawn/exit, console room, crew markers) —
  "my human brain works great in vim. your brain works better in
  json" — and a compiler renders it to ``.layout``, refusing to
  emit unless the validator passes: door ends live + same
  component, BFS from spawn covers every floor cell, hull seal
  (no floor adjacent to border-connected void). The JSON is the
  authoring intermediary ONLY; ``.layout`` stays the canonical,
  human-readable final format (vim pass is the user's; recompiles
  never clobber hand edits). Reference corpus: FTL doors-view /
  Systems images per hull class, user-curated, stored with source
  URLs (the user's process: reference → tabletop-RPG floor-plan
  concept → ``#``/``.`` structure first → content pass).

## The complete settled design (one statement)

Every ship broadcasts. An ID is an identifier that maps to
relations — the game has lived in live mode since day one (detect,
identify, rate, behave). The layer adds key choice: live (true
ratings — today, nothing new), dark (nothing resolves; countered
only by eyes and the Line's density), spoofed (the worn ID's own
rep sheet; three sources: scrubbed→blank sheet, cloned→rolled from
the source, fabricated→authored). The broadcasting ID's sheet IS
your current reputation — every reader resolves it; one gate for
all spawn readers, engage only on resolved disliked/enemy; the
Ross pose is the mechanic working, no custom code (2026-09-06
re-cut; IDs carry reputation sheets — the face/faction mapping is
superseded). Explicit
registrations for RP flavor; the F — faction screen is the identity
hub (broadcast state, cycling collected IDs). Intrinsic
transponders; services at the outlaw ports work the modes; going
dark requires a one-time cut-out installed by Ember's tech in
Ross 154 while the scrub stays at Deadfall's broker (priced below
the scrub, rides the player across purchases — the
free D toggle is superseded); identity rides the player across
lawful purchases (the scrub is an unlawful hull). Rep writes
follow the broadcast — live moves ID 1's sheet, spoofed moves the
worn ID's sheet, dark records nothing. Nothing breaks a complete spoof in v1 (in-person inspection parked). NPCs broadcast
into comms; cloning is rare, difficult, expensive — a process:
capture is live-ship boarding (cripple, board, fight to the C
console), each source rolls its copy quality once, and the library
is capped, deletable, sellable. Dark requires a cut-out and
carries the lifestyle price: only pirate-run ports berth a dark
hull (a whitelist — Deadfall, Whisper, Ember, Wolf 359 b; neutral
ports refuse too — trust, not patrols), and militia patrols that
detect a dark hull challenge it — identify (what resolves is judged)
or attack, escalating to combat and heat; no RUN option (no run
mechanic exists — user ruling); pirates never
challenge. Scrubbed triggers neither — blank paper complies.

## Phases

- [x] Review with the user — all six questions ruled (2026-09-06)
- [x] PHASE 1 LANDED (2026-09-06): the identity data layer —
      src/spacehack/identity.py (state helpers, registration
      generation, the dark master switch, library cycling),
      GameContext fields + saveload persistence + legacy-save
      migration (a registration appears), the broadcast gate in
      modify_rep (masked deltas discarded; in_person bypass for
      face-to-face events and time decay — decay was caught routing
      through the gate in testing) [write routing SUPERSEDED
      2026-09-06: dark-only discard, spoofed writes the worn
      sheet — reworked in phase 4], and the F-screen identity hub
      (broadcast block + D toggle + TAB cycling). Tests:
      tests/test_identity.py (9).
- [x] PHASE 2 LANDED (2026-09-06): NPCs broadcast into comms (the
      hail modal opens with the contact's Broadcast line); dark
      suppresses auto-hail (nothing to hail — eyes, not
      electronics); the first acquisition vector — the Registry
      Broker at Deadfall's spaceport sells one scrubbed ID for
      6,000cr (SCRUB_BROKERS table, priced row in the NPC talk
      modal; militia/fabricated ids stay act-1 quest content);
      npc_identity/apparent_faction helpers for the Line and faction
      reactions. Tests: +2 (11 total).
- [x] PHASE 3a — the dark dock gate — LANDED + PLAYTEST PASSED
      (2026-09-06; cf26aba + 3466c06): berthing
      refused at every port except the pirate-run whitelist —
      lal_b Deadfall, lal_c Whisper, ross_b Ember, wolf_b Wolf
      359 b; neutral ports refuse too — trust, not patrols; the
      whitelist is the ``dark_berth`` opt-in field on PlanetSpec,
      set in each pirate-run planet module — no id list in code.
      Scrubbed never triggers it — compliance is the 6,000cr.
      Shipped: the gate in ``_resolve_planet_land`` before the
      cargo scan (covers both landing paths; ``land_at_city``
      refuses before its system switch), the landing tail
      extracted to ``_enter_city_landing`` (ratchet), the
      "Identity & Transponder" guide section (phase 1 shipped the
      hub without any guide section), 5 tests.

  Implementation brief (3a):
  - Scope: ``dark_berth: bool = False`` on PlanetSpec
    (``data/planets/__init__.py``); ``dark_berth=True`` in
    ``lal_b.py``, ``lal_c.py``, ``ross_b.py``, ``wolf_b.py``; the
    gate in ``game_interactions._resolve_planet_land`` BEFORE
    ``_run_cargo_scan`` — one gate covers both landing paths
    (``land_at_city`` routes through ``_resolve_planet_land``).

  Pre-implementation audit (3a, 2026-09-06):
  - Reuse: ``identity.broadcast_mode`` (``src/spacehack/identity.py``)
    is the only state read — no new GameContext fields, nothing new
    to persist. The landing funnel is single: both the planet-menu
    LAND outcome and ``land_at_city`` (Shift+T) route through
    ``game_interactions._resolve_planet_land`` (two callers total;
    the other ``load_planet`` callers are interior rebuild + save
    restore and must NOT gate — they don't touch this path). Port
    lookups reuse ``has_landable_port`` (KeyError-safe) and
    ``find_planet_spec``.
  - Duplication hotspots: (1) two landing paths — killed
    structurally: one gate inside ``_resolve_planet_land``, no
    second check in ``land_at_city`` (a refused teleport re-calls
    the same helper BEFORE the system switch — reviewer finding:
    the rejected jump must not leave ``current_solar_system_id``
    pointing at the port that said no); (2) a code-side whitelist id
    list — ruled out, the whitelist IS the ``dark_berth`` opt-ins;
    (3) the portless "no port" message — the gate falls through to
    the existing path for portless ids instead of re-emitting it.
  - DRY strategy: pure helper ``_dark_dock_refusal(ctx, pid) ->
    str | None`` (computation per the pure-function contract, ships
    with tests); the caller logs the message. Guide section appended
    to ``GUIDE_SECTIONS`` (``data/guide/__init__.py``) — ``help.py``
    enumerates the tuple, no extra wiring.
  - Surprise: NO identity guide section exists (phase 1 shipped the
    F-screen hub without one) — 3a creates the section, covering
    both the hub and dark's dock price.
  - Ratchet: ``_resolve_planet_land`` is ~37 lines; the gate lines
    push it over 40, so the landing tail (city-map build + entry)
    extracts to a module-level helper in the same commit.
  - Refusal: log line + stay in space (return 'CONTINUE'); the city
    map is never built. Final wording (user, 2026-09-06):
    ``Docking request denied: transponder not responding.`` — one
    uniform line for every refusing port, no port name; pinned by
    test.
  - Tests (doc-specified): dock gate per port class — whitelisted
    port berths a dark hull, lawful port refuses, neutral port
    refuses; scrubbed and live unaffected; the refusal precedes the
    cargo scan.
  - Guide: dark's dock price is player-facing — extend the identity
    section of the game guide.
  - Stop point: NOTHING from the militia challenge hail (no comms,
    detect, or escalation work in this phase).
  - Playtest checkpoint: numbered in-game checklist — go dark (F
    screen), refused at Earth and at a neutral port, berthed at
    Deadfall and Ember, scrubbed still docks at Earth, save/load
    round-trip across a refusal.

- [x] PHASE 3b — the militia challenge hail — LANDED + PLAYTEST
      PASSED (2026-09-06; 5255c05): NPC-initiated
      comms on detect: identify / attack — TWO options, no RUN (no
      run mechanic exists; a future run-mechanic doc would collect
      all such interactions). ATTACK escalates to combat + heat,
      never a guaranteed kill; ghost-run tuning lives with doc 39
      when that method is built. Scrubbed triggers nothing — blank
      paper complies. Shipped: ``_dark_spot_challenge`` (militia-
      only, detect radius, one-shot per patrol via militia_scanned),
      the challenge modal (ESC = refusing = the patrol fires), the
      identify judgement (``_judge_identification`` pure: blank
      passes, militia callsign stands down, wrong face / hostile
      true record draw fire), ATTACK through the normal escalation
      (rep rides the broadcast gate — unsolved while dark), +7
      tests, guide updated. Playtest round 1 (2026-09-06): the
      challenge body rendered the cargo-inspection comms_lines —
      fixed with a ``challenge_lines`` field on NpcShipSpec
      (authored per militia ship, generic fallback); judgement
      passes unified to one line ("The patrol checks your
      registration and waves you through.") per user ruling — no
      mechanic lectures, the player discovers blank paper's
      equivalence in play.

  Implementation brief (3b) — DRAFTED at 3a's playtest checkpoint
  (2026-09-06; shape may shift with what the gate playtest shows):
  - Scope: the militia challenge hail. Where phase 2 made dark
    SUPPRESS the auto-hail (``navigation_combat``), a militia ship
    that physically spots a dark hull now hails the player instead
    of staying silent (NPC-initiated comms modal): IDENTIFY /
    ATTACK — TWO options only, no RUN (no run mechanic exists —
    user ruling 1add73d; a future run-mechanic doc collects every
    interaction of this kind). Scrubbed/spoofed and live broadcasts
    keep today's behavior (blank paper complies); pirates never
    challenge (faction check on the spotter).
  - IDENTIFY is the moment of truth: the player picks what to
    broadcast (flip live or wear a face) and what resolves is what
    gets judged — a scrubbed hull is waved through; the true ID
    gets its record's due (face-to-face, so ``modify_rep``'s
    ``in_person`` semantics apply — NOT masked); a wrong face gets
    that face's trouble (``apparent_faction``).
  - ATTACK escalates to space combat + heat — pressure, never a
    guaranteed kill (reuse the existing escalation entry points).
  - Build order: the detect branch (who challenges) → the two-option
    modal → IDENTIFY judgement → ATTACK escalation.
  - Tests: challenge outcomes per broadcast state — dark + militia
    spot = challenge; identify judged per worn face (scrubbed
    passes, true ID recorded, wrong face takes the face's trouble);
    attack escalates; scrubbed/live are never challenged; pirates
    never challenge.
  - Stop point: NOTHING from doc 41 (the Line) and no ghost-run
    tooling (lure call, ready-face flow stay with doc 39) — this
    phase is the hail and its two outcomes only.
  - Playtest checkpoint: numbered in-game checklist — challenge
    fires when a militia patrol spots a dark hull; identify with a
    scrubbed face passes; identify live takes the record's due;
    attack escalates; scrubbed broadcast is never challenged;
    save/load across a challenge.

  Pre-implementation audit (3b, 2026-09-06):
  - Reuse: the dark branch lives exactly where phase 2 suppressed
    the hail — ``navigation_combat._auto_hail_entity`` (spec lookup
    moves above it: the challenge needs faction +
    ``detect_radius``, the EYES radius per the Q3 ruling, not the
    electronic ``comms_warning_range``). One-shot tracking reuses
    ``_entity_hail_key`` + ``ctx.militia_scanned`` (persisted in
    saveload; cleared on landing — the existing hail semantics, no
    new state). ATTACK escalation reuses
    ``comms._handle_interaction``'s ATTACK branch verbatim
    (``_unprovoked_attack_rep`` + ``_combat_open_log`` +
    ``_squad_payload``) — the broadcast gate already masks the rep
    for dark/fake faces (the Q4 twist for free). Payload plumbing
    (``(True, payload)`` → ``combat._handle_combat_encounter``) is
    unchanged. Judgement reads ``faction.get_attitude`` for the
    true record; the face library is phase 1's ``collected_ids``.
  - Duplication hotspots: (1) a second escalation path — killed by
    reusing ``_handle_interaction(ATTACK)``, not copying the
    rep/log/payload trio; (2) a second hail-tracking mechanism —
    ``militia_scanned`` only; (3) a second modal framework — the
    existing ``_pygame_interaction_outcome`` gains a dispatch-table
    param (the state-table guardrail), and the face-choice modal is
    a sibling of ``_hail_frames``, not new machinery.
  - DRY strategy: pure ``_judge_identification(ctx, face) ->
    (passed, line)`` (pure-function contract + tests);
    ``resolve_identification`` is the thin mutation wrapper (sets
    the broadcast, logs the judgement); modal runners stay
    choice-collectors (the monkeypatch seam this suite already
    uses).
  - Rulings locked (brief said the shape may shift; these are the
    v1 calls): ESC/backing out of the challenge = refusing to
    answer = the patrol opens fire (TWO options only — ESC must
    not become a run mechanic). IDENTIFY ends dark: the
    transponder comes up broadcasting the answered face and STAYS
    there (the persistence ruling). Judgement [mechanism SUPERSEDED
    2026-09-06 — sheets: the answered ID's militia VALUE decides,
    no faction special cases; outcomes unchanged]: blank (scrubbed)
    passes; a militia-registered face passes (the institution
    outranks the reader — sandbox militia faces stay act-1
    content); any other faction fails; the true ID passes unless
    the true militia record is disliked/enemy. A failed judgement
    or ATTACK starts the existing combat with the patrol's whole
    squad; no new rep deltas on the challenge itself (the
    patrol fires, the player didn't attack unprovoked). Plain
    ``detect_radius`` in v1 (no charged-cell boost).
  - Ratchet: comms.py 447 / navigation_combat.py 341 lines — both
    under limit; new functions stay under 40.
  - Known consequence (reviewer, surfacing to the user — matches the
    locked one-shot ruling, NOT silently accepted): a patrol that
    already ran its electronic scan-hail check on a LIVE player
    (key marked in ``militia_scanned`` at comms_warning_range,
    before the scan roll) can never challenge that visit once the
    player toggles dark inside its range — "fly live into range,
    then go dark" suppresses that patrol's challenge until landing
    clears the set. Fix would be separate keys for hail vs
    challenge; deferred until the playtest says it matters.
- [x] PHASE 4 — the broadcasting ID's reputation — LANDED +
      PLAYTEST PASSED (user-verified 2026-09-07; 66b6e0f..11bbacf). Re-cut
      2026-09-06 from "apparent standings": IDs carry rep sheets,
      not faction mappings — see the sheets SETTLED section. One
      pure resolver — the sheet of whichever ID broadcasts — feeds
      every reader; existing consumers keep their logic (user:
      "reputation drives this system 100%"). Shipped: the resolver
      (fresh dict per state), broadcast write routing in
      ``modify_rep`` (spoofed → worn entry's sheet via
      ``identity.apply_worn_delta``; dark discards; decay direct),
      literal zero scrub sheets, the challenge judgement by sheet
      value (one unified hostile line), the uniform static gate
      (shared ``_gate_engages``, charged-cell bypass), every routed
      reader (spawn passes, scan chance, comms, trade, board, ground),
      the F screen rendering the actual sheet (``_masked_row`` +
      ``apparent_faction`` deleted), guide + module docstrings. REVIEW
      round 1: REQUEST_CHANGES → 1 blocking (gate heat bypass
      untested) + 5 minors, all fixed (5a56268..11bbacf); routing
      verified complete, stop point respected; 1765 tests green.

  Implementation brief (4) — re-cut + APPROVED (user, 2026-09-06;
  supersedes the original apparent-standings brief; amended after
  the ADVISE review the same day — ruling on statics, audit
  section, reviewer mechanics folded in):
  - Scope: ``identity.effective_reputation(ctx) -> dict[str, int]``
    (pure; returns a FRESH dict — never the live one): live → copy
    of ``ctx.faction_reputation`` (ID 1's sheet); spoofed → the
    worn entry's ``rep`` sheet (entries without one read blank);
    dark → ``{}``. Reader call sites swap
    ``ctx.faction_reputation.get(f, 0)`` for
    ``identity.effective_reputation(ctx).get(f, 0)``:
    ``navigation_combat._trigger_bounty_spawns`` /
    ``_trigger_procedural_spawns`` (existing gates),
    ``_trigger_static_spawns`` (gate ADDED: engage only on resolved
    disliked/enemy — NO territorial exceptions, user ruling; ADVISE
    verified derelicts/blockers spawn via ``derelict_spawn_chance``
    and don't route through this pass), ``_militia_scan_chance``,
    ``comms`` contact attitude + hostile hail label, ``trade``
    merchant/npc-faction attitudes (``_merchant_attitude`` reads
    the dict object, not the ``.get`` literal — route it through
    the resolver too), ``mission/_board`` reward
    adjust, ``faction.spec_is_hostile`` ground hostility (shared by
    ``detect_ground_combat``, ``ground_npcs._is_hostile``, AND
    ``city_npcs.is_hostile`` — city NPCs stand down under a neutral
    sheet; the ground read is the SAME sheet, user ruling).
    ``_charged_cell_aggro`` NOT routed; ``faction.py``
    monthly decay keeps the true dict (time, not a reader).
    Superseded face machinery: ``identity.apparent_faction``
    deleted (zero tests, zero code callers — clean delete); F
    screen ``_masked_row`` deleted,
    ``_faction_rows`` renders the resolver's sheet directly;
    ``_judge_identification`` (comms) judges the answered ID's
    sheet militia VALUE — it KEEPS its ``(ctx, face)`` signature
    and reads ``face``'s ``rep`` (face None → the true dict), so
    its lone caller (``resolve_identification``, comms.py:399,
    reached via ``_handle_challenge``:481) needs zero changes —
    faction special cases removed, pass
    line unchanged, hostile outcomes unify to one line ("The
    registration reads hostile: the patrol opens fire!"). Writes
    REWORKED (Q4 re-ruled 2026-09-06 — dark-only discard):
    ``modify_rep`` routes by broadcast — dark → discard (nothing
    records); spoofed → the worn ID's sheet via a new ``identity``
    helper (the ``collected_ids`` entry is the single source of
    truth: look up by worn id, ``setdefault("rep", {})``, delegate
    to ``_apply_rep_delta`` parameterized with ``sheet=None,
    id_label=None`` — ONE copy of the cap/clamp/log math, and worn-
    sheet log lines come out labeled with the worn ID); live →
    ``ctx.faction_reputation``. ``in_person`` param deleted:
    monthly decay writes the true sheet directly (time, not
    behavior); the story-beat caller (``main_quest/_core.py:112``)
    now routes to the broadcasting ID per the ruling — DARK
    discards story ``rewards_rep`` permanently (steps complete
    once; ruled), so update the stale face-to-face comment there in
    the same change. ``buy_scrubbed_id`` materializes the sheet at
    purchase —
    literal 0's for every faction (user ruling: a scrubbed ID IS an
    ID with 0's across the board). Library entries and
    ``broadcast_identity`` already
    persist — no saveload changes. No save migration (legacy
    entries without ``rep`` read all-neutral via the reader's
    ``.get``); no new acquisition content. INVARIANT (ADVISE):
    rep is read and written ONLY via the library entry or
    ``ctx.faction_reputation`` — NEVER via ``ctx.broadcast_identity``
    (post-load the two are separate objects). PERF (amended at
    build, 2026-09-07): the three space spawn passes hoist ONE
    resolver call each; ``spec_is_hostile`` stays self-resolving
    per call — hoisting would plumb a sheet parameter through the
    ``ground_npcs``/``city_npcs``/``_encounter`` wrapper seams for a
    negligible gain (a dict copy + ≤4-entry library scan per NPC).
    Deliberate deviation, recorded per REVIEW minor 3. Guide: the existing
    "reputation freezes while masked" line is now FALSE — update it
    (spoofed rep moves the worn sheet; only dark discards; dark F
    rows render neutral, the mode tag carries the state).
  - Build order: resolver + tests → write routing → judgement swap
    → static-spawn gate → routed readers → F screen sheet display →
    guide touch → ``make check``.
  - Binding rulings: IDs carry sheets, not faction mappings (no
    player-layer read keys on the face's ``faction`` field); writes
    follow the broadcast (live → ID 1; spoofed → worn sheet; dark →
    discard; decay → true sheet always); scrubbed sheet = literal
    0's across the board; dark resolves neutral; statics gate
    uniformly — NO exceptions (blockade stand-down accepted);
    cloned sheets roll
    at capture (6); mask cuts both ways at reads (masked trade
    loses earned attitudes).
  - Required tests: resolver per state (live / worn entry with
    sheet / worn scrub — literal zeros / dark); judgement by sheet
    values (blank passes, positive militia sheet passes, hostile
    sheet draws fire); write routing per state (dark discards;
    spoofed delta lands on
    the worn entry and round-trips save/load; live moves the true
    sheet; decay ages the true sheet while masked); scrubbed
    purchase materializes a literal zero sheet (assert zeros for
    every faction in ``_ALL_FACTIONS``); ground hostility
    reads the sheet incl. the ``city_npcs.is_hostile`` caller
    (masked stand-down, hostile sheet engages);
    static spawns
    stand down on neutral + engage on disliked/enemy;
    scan chance reads the sheet; trade attitude masked → neutral;
    charged-cell still aggros through any ID; F screen renders the
    worn sheet; live unchanged (existing suite). REPLACES (same
    commit, pure-function test contract): the masked-discard /
    in_person gate tests (test_identity.py 87-116) and the
    F-screen "No Data"/"Friendly (Faked)" tests (310-339).
  - Stop point: NO clone capture or rolls (6), no cut-out (5), no
    boarding, no Line work, no new collectible IDs.
  - Playtest checkpoint (numbered): buy the scrub, wear it — the
    Ross crown drifts past; Sol patrol scans at the neutral rate;
    trade prices lose the earned discount; F screen shows the
    scrub's neutral sheet while worn and the true sheet after
    cycling back; terrorize a merchant pilot in the scrub — the
    worn sheet drops on the F screen (the log line names the worn
    ID), flipping live shows the true
    sheet untouched, cycling back shows the scrub still hot;
    save/load keeps the hot scrub; flip live — everything as today
    EXCEPT statics now gate on resolved standing: the Luyten
    blockade stands down for a default (militia-liked) live player
    — EXPECTED, not a bug; go dark — pirate spawns ignore, militia
    challenge still
    fires, a kill under dark moves nothing; on a save where ground
    NPCs (city or wild) of a faction engage your live self,
    wearing the scrub
    stands them down; save/load across all three states.

  Playtest (2026-09-07): PASSED — scrub purchase/wear, Ross crown
  stand-down, neutral-rate scans, lost trade discount, hot-scrub
  write routing (labeled log, true sheet untouched, survives
  save/load), dark stand-down + challenge, live unchanged. Player
  note: neutral always sufficed for spawns to stand down — starting
  pirate rep (-100, enemy) is why raising it "felt" like needing
  more; statics were the pre-phase-4 exception.

  Pre-implementation audit (4, 2026-09-06 — added post-ADVISE):
  - Reuse: ``identity.broadcast_mode`` drives the resolver's
    three-way branch; rep math reuses ``_apply_rep_delta``
    (parameterized — no second copy); the judgement reuses its
    ``(ctx, face)`` signature reading the entry's ``rep``; library
    lookups reuse ``collected_ids`` helpers; NO new GameContext
    fields, NO saveload changes (both structures persist today —
    verified). No new module-level globals.
  - Duplication hotspots: (1) a second cap/clamp/log copy for
    worn-sheet writes — killed by the ``_apply_rep_delta``
    parameterization (also yields the labeled log line);
    (2) dual-source drift between ``ctx.broadcast_identity`` (a
    persisted dict COPY) and the ``collected_ids`` entry — killed
    by the read/write invariant (library entry or true dict only);
    (3) per-NPC resolver churn in hot passes — killed by hoisting
    one resolver call per pass (spawn detect, ``move_ground_npcs``,
    city tick).
  - DRY strategy: the routing is a named-helper mode branch, not a
    conditional ladder; reader swaps are mechanical one-line edits
    (``trade.py:59``'s dict-object shape called out above); ADVISE
    pack (``/tmp/review_pack_40p4.md``) answered the open audit
    questions: reader list COMPLETE, ``in_person`` callers exactly
    two (decay, story beat), ``apparent_faction`` testless and
    uncalled (clean delete), derelicts outside the static pass.

- [x] PHASE 5 — dark's cut-out (the price of entry) — LANDED +
      PLAYTEST PASSED (user-verified 2026-09-07; d1e4b16..c69bdf9,
      5 gated commits + REVIEW round 1 fix + hardening; 1777
      green). Dark
      requires the one-time cut-out; the F-screen D is inert until
      then. Shipped: ``transponder_cutout`` on GameContext
      (persisted; LOAD INVARIANT: a save without a cut-out never
      loads dark — legacy dark saves restore live with a log
      line), the gated ``toggle_dark`` (pinned refusal line), the
      F-screen hint state, ``ember_tech`` ("Transponder Tech")
      seated ALWAYS-ON in Ember's depot interior via
      ``PlanetSpec.service_npc_spots`` + ``_seat_service_npcs``
      (the unconditional sibling of the quest seater), the CUTOUT
      talk row offered only while uninstalled (installed = row
      gone; the tech then has no rows → flavor reply),
      ``buy_transponder_cutout`` (2,500cr, charged once), guide
      updated. REVIEW round 1: REQUEST_CHANGES → 1 BLOCKING (the
      install row never reached the modal: the zero-options check
      ran before priced rows counted — the guild-less tech died at
      ``_no_options_reply``; the scrub twin survives only via its
      broker's guild row) + 5 minors, all fixed (2298113,
      c69bdf9); re-review APPROVE. LESSON (structural fix): the
      built items tuple is the single source of truth for
      row-existence — parallel counts drift.

  Playtest (2026-09-07): PASSED — legacy dark save restored live
  with the invariant line, D inert pre-install (hint + pinned
  refusal), the trip to Ross 154 and the depot tech, 2,500cr
  install, row gone after purchase, D working with dark
  save/load, Deadfall broker regression clean (scrub only, no
  cut-out row). Mid-playtest ruling: the tech's flavor rewritten
  DIEGETICALLY — no interface language in quoted speech (now
  prose tell 15); "I gut the breaker so the transponder can go
  dead quiet whenever you want…"

  Implementation brief (5) — APPROVED (user, 2026-09-06); residuals
  settled + amended (refine session, 2026-09-07 — see the cut-out
  specifics SETTLED section):
  - Scope: ``transponder_cutout: bool`` on GameContext (saveload
    both directions; legacy saves migrate False — dark must be
    earned); ``identity.toggle_dark`` refuses without it — log line
    ``No cut-out installed.`` (verbatim, pinned by test); the
    F-screen hint row reads ``ENTER / ESC back   D transponder
    (no cut-out)`` while uninstalled (unchanged otherwise); the
    install is the cut-out tech's product — a NEW NPC
    (``ember_tech``, name/flavor drafted at build,
    user-dictatable) seated ADDITIVELY inside Ember's depot
    interior (Ross 154; user ruling 2026-09-07: different system,
    different NPC, different building than the scrub) via the
    interior-seat pattern generalized always-on — row
    ``Install a transponder cut-out (2,500cr)`` (silence is
    cheaper than paper), purchase logs ``Cut-out installed.``, and
    the row is OFFERED ONLY WHILE UNINSTALLED — the same
    conditional mechanism as the scrub row; no re-buy path, no
    refusal prose; ``SCRUB_BROKERS`` unchanged (Deadfall keeps
    the scrub only); guide section updated. LOAD INVARIANT
    (uniform, one place in
    saveload): a save without a cut-out never loads dark — a
    legacy ``broadcast_dark=True`` resets to live at load, logging
    one line when it fires.
  - Build order: field + persistence (+ load invariant) → toggle
    gate → F-screen state → tech NPC + additive seat + service
    row → guide.
  - Binding rulings: one-time install, never consumed, RIDES THE
    PLAYER across lawful ship purchases (player-level flag, same
    as the library and registration — the registry transfers the
    owner, Q2's frame); installed = the tech's row disappears (no
    re-buy, no refusal line); the storefront split is deliberate —
    scrub = Deadfall's broker ONLY, cut-out = Ember's tech ONLY;
    Wolf 359 b and any new pirate port selling either are later
    content; the scrub is unaffected.
  - Required tests: D inert without the cut-out (refusal line
    pinned); works after purchase; the tech's row is absent once
    installed (no double charge); the tech seats unconditionally
    at Ember's depot (not quest-gated) and Deadfall's broker shows
    no cut-out row; persistence round-trip; legacy-save migration
    incl. the invariant — a legacy DARK save with no cut-out loads
    live and logs; cut-out + dark round-trips still dark.
  - Stop point: NOTHING from phase 6 — no recorder/rig, no
    boarding.
  - Playtest checkpoint: on a pre-cut-out save D does nothing (a
    DARK one loads LIVE with the reset line) → fly to Ross 154
    (via Sirius), land at Ember, find the tech in the depot → buy
    the install → the row vanishes from the tech → D works →
    save/load keeps both the cut-out and the dark state.

  Pre-implementation audit (5, 2026-09-07):
  - Reuse: ``identity.toggle_dark`` (identity.py:122) has exactly
    one caller — ``pygame_faction._log_transponder_toggle`` — so
    the gate goes inside ``toggle_dark`` (returns bool; the caller
    returns early on refusal; the refusal line lives in identity,
    one copy). Purchase machinery mirrors the scrub pair:
    ``CUTOUT_BROKERS = {"ember_tech": 2500}`` + pure
    ``cutout_price(npc_id)`` + ``buy_transponder_cutout(ctx,
    npc_id)`` beside ``SCRUB_BROKERS``/``buy_scrubbed_id``
    (identity.py:244-270). The talk-modal priced-row seam
    (npc.py ``_npc_pygame_items(scrub_price=...)`` → action
    "SCRUB" → ``_handle_scrub_purchase``) gains the parallel
    ``cutout_price=`` / "CUTOUT" / ``_handle_cutout_purchase`` —
    row built only while ``not ctx.transponder_cutout``, so
    installed = row gone with no new hiding logic. Interior
    seating: the quest seater (``main_quest/_act0.py:451``,
    called from ``city_interiors.py:84``) already delegates seat
    geometry to ``city_interiors._first_interior_npc`` — the new
    always-on seater ``_seat_service_npcs`` lives in
    ``city_interiors.py`` (interior domain, not quest) reading a
    new ``PlanetSpec.service_npc_spots``; zero geometry duplication,
    quest machinery untouched. Persistence: one line each in the
    writer (``saveload.py:132-135`` block) and reader (:883-887);
    the load invariant sits right after the ``broadcast_dark``
    restore; ``GameContext.transponder_cutout`` declared beside the
    other identity fields (game_context.py:388-396).
  - Duplication hotspots: (1) a second seat-geometry copy — killed
    by reusing ``_first_interior_npc``; (2) a second D-key log path
    — killed by the bool return (``_log_transponder_toggle`` stays
    the only toggle logger); (3) quest-gating special cases —
    killed by the separate ``service_npc_spots`` field + seater
    (no always-true conditions threaded through quest code);
    (4) the can't-afford line appears in both purchase handlers
    (one-line literal, accepted; not a shared pattern).
  - Edge behavior: post-install the tech has ZERO menu rows → the
    existing ``_no_options_reply`` path gives his flavor/read-only
    line — intended (the row disappearing IS the ruling). Legacy
    saves without the key read False; the load invariant fires only
    when dark AND no cut-out. ``tests/support/quest_ctx.py`` gains
    ``transponder_cutout=False`` — a fake crossing the gate must
    pin it (MagicMock truthy-trap).
  - Ratchet: saveload.py is 963 lines (+~4 stays under 1000);
    ``_run_npc_talk`` is the one edited function near the 40-line
    limit — recount at edit, extract the option-count prelude if it
    crosses.
  - Strings: the brief's four lines as pinned above; the
    load-invariant line is drafted here (user-dictatable at
    playtest): ``No cut-out installed - transponder restored to
    live.`` Tech NPC draft: id ``ember_tech``, name "Transponder
    Tech", guild "" (no WORK row), flavor teaches in-character
    (what a cut-out does, the F screen's D, the dock price).
  - Tests (doc-specified): mirror the persistence/round-trip
    patterns in tests/test_identity.py; the seat test mirrors
    tests/test_main_quest_npc_presence.py:180; quest_ctx pins the
    new field.
  - Stop point: NOTHING from phase 6 — no recorder/rig, no
    boarding.
  - Playtest checkpoint: the brief's checkpoint above (5 items).

- [x] PHASE 6a — the capture pipeline: BOARD-in-combat + live-ship
      boarding + the clone roll + the rig — LANDED (2026-09-07;
      37543a8..3f80721, 8 commits incl. the ratchet split; 1801
      green). PLAYTEST PENDING. REVIEW: build review (2 dispatches)
      REQUEST_CHANGES → 5 blockers (dead B key under the VIM
      diagonal; unfiltered target index; the transition dying on
      the shim; unstamped serialization; loot-budget semantics) +
      minors, all fixed; re-review round 2 caught two self-
      introduced regressions (orphaned _move_npcs tail; nested
      goto-loop outcome) + the ground key regression — fixed
      (d08068b); round 3 caught the drift tail on the detection-
      loop path + the break-away downgrade — fixed (3f80721),
      prescribed one-liners pinned by tests, no fourth dispatch.
      PLAYTEST-CRITICAL lessons: shared keymaps need table-vs-move
      precedence rules; outcome strings that mutate state need an
      owner for failure paths; every `_run_combat_loop` caller is
      a state-adoption site. Playtest (2026-09-07): PASSED with
      two follow-ups spun into 6c — the authored crew layouts fail
      basic ship logic (doors to nowhere, hull gaps open to space)
      and only 2 of the battle specs are capture targets. Mid-
      playtest additions: dev-mode new games file three maxed-rep
      IDs (ff9a182); the dealer moved inside the market square
      (9a31fc9); flavor + rig-row wording per user (c1b480b,
      ac212a9); Gear line on the C screen (5392ecd); conditional
      [b] Board hint (1e9e986). Re-cut 6 → 6a + 6b
      (user-approved 2026-09-07, per the ADVISE review; 6a is the
      novel-machinery vertical slice). Boarding conditions (user,
      2026-09-07): no shields up, 75% hull damage done, no other
      ships in the encounter, player adjacent — BOARD offered in
      combat; exit consumes the ship ("you can't reboard a ship
      after you board it once").

  Implementation brief (6a) — ADVISE-reviewed + rulings folded
  (2026-09-07):
  - Scope: (1) the BOARD action in space combat
    (``combat/_rules_space.py``) — offered only when the target has
    no shields up, has taken 75% hull damage (threshold tunable at
    playtest), is the ONLY active enemy in the encounter, and the
    player is adjacent; choosing it ends the encounter INTO the
    ship's interior (the wreck-boarding pipeline, entered from
    combat; ``_confirm_boarding`` gets its own live-ship copy —
    today it says "The derelict can be searched"). A kill still
    just kills (``on_kill`` removes the entity — overkill destroys
    the prize, no wreck). NOTE: ``_rules_space.py`` sits at
    998/1000 — the ratchet forces its split in the same commit;
    (2) crewed interiors — ENEMY markers AUTHORED in per-faction
    interior layouts (the directive already parses and scatters;
    ``scout_a.layout`` is the precedent — content, not machinery).
    V1 cloneable targets = specs with authored layouts; more
    layouts are later content. Faction-coherent crews (a militia
    cruiser never spawns pirate markers); (3) the C console —
    rides the existing ``computer_terminal`` entity + bump flow;
    with the clone RIG installed it offers CLONE: the roll
    generates the ``rep`` sheet at capture (quality-skewed by the
    source's hull-class tier — exact bands proposed at build,
    user-tunable; RNG injected per ``generate_registration(rng=)``
    for determinism tests — never a stale ``from .engine import
    RNG`` binding); the entry persists the sheet. ON EXIT THE SHIP
    IS CONSUMED (gone — the existing wreck-exit consumption path;
    no map-level crippled state, nothing new to persist for it);
    (4) the rig — ``transponder_rig``-style GameContext bool
    MIRRORING ``transponder_cutout`` exactly: declared beside the
    identity fields, one writer line + one reader line in
    saveload (969/1000 — tight), pinned in ``quest_ctx``; (5) the
    rig vendor — a NEW stall ``CityNpc`` on Wolf 359 b's
    Smuggler's Row (``wander_radius=0``, civilian char-spec,
    ``npc_id`` → new NPC persona; FIRST user of the ambient-
    vendor→persona talk path — ship its routing test). GATE
    (user ruling): below resolved pirate liked (+26) talking to
    him gets ``Scram.`` (verbatim) and NO menu — a pure
    refusal-or-None helper (``_dark_dock_refusal`` precedent,
    reading ``effective_reputation`` + ``get_attitude``) placed
    before the chat log; a pirate-liked clone wears past it
    (uniform). At/above: his menu offers the rig (priced above
    the cut-out — exact price proposed at build). The BUY row is
    6b, not this phase. RULING (user, mid-playtest 2026-09-07):
    the rig is a ONE-TIME PURCHASE UNLOCK, never a per-capture
    price — the loop's recurring cost is the grind itself (find a
    good target, win the duel, survive the crew, take the roll);
    a 9,000cr repeat would make that grind feel excessive.
    Already how it works (field never consumed, row gone when
    owned — pinned); the menu description now states it.
  - Build order: BOARD conditions + combat exit → boarding
    interior + crew → C console + roll → rig field + persistence →
    vendor + gate → guide.
  - Binding rulings: capture is live-ship boarding only; boarding
    requires a duel (the four conditions are hard gates); boarding
    CONSUMES the ship on exit (one board per hull — the physical
    one-roll-per-source enforcement); sheets settle at capture and
    persist on the entry; ship theft parked; cloning stays RARE
    and DIFFICULT.
  - Required tests: BOARD offered/denied per the four conditions
    (shields, hull band, solo encounter, adjacency); kill =
    destroyed, no boardable ship; crew spawns hostile per faction
    layout; console clone gated on the rig; roll deterministic per
    (source, seed) via injected RNG, persisted on the entry;
    exit consumes the ship (no re-board); rig round-trips
    save/load; below liked the vendor refuses (``Scram.`` pinned,
    no modal), at liked the rig row shows, masked liked sheet
    passes; vendor routing test (ambient npc_id persona reaches
    the talk modal).
  - Stop point: NO library cap/delete/sell (6b), NO ship theft,
    NO frame-job v2, NO fabricated-ID content (act 1 owns it), NO
    Line work. DOC 39 NOTE: its ghost-run verb description (doc
    39, "shadow a patrol, record the broadcast") is superseded by
    this capture ruling — one-line reconciliation owed at doc 39's
    next touch; the ghost run's militia ID stays authored act-1
    content and does NOT wait on this phase.
  - Playtest checkpoint (numbered): buy the rig at the Wolf 359 b
    stall (below pirate liked: ``Scram.``) → jump to a pirate
    system, isolate ONE pirate → hammer its hull to the band →
    close adjacent → BOARD appears → take it → fight the crew to
    the cockpit → clone at the C console → exit — the ship is
    GONE → the new ID sits on the F screen with its rolled sheet →
    wear it in its home faction's space (readers react to the
    ROLLED values) → try to re-board that hull (impossible — it's
    gone) → save/load keeps the rolled sheet.

  Pre-implementation audit (6a, 2026-09-07 — post-ADVISE):
  - Reuse: the BOARD predicate reads ``EnemyInstance`` directly
    (hull/max_hull/shields/pos live on the instance,
    ``combat/_types.py``); the boarded ship's map entity comes from
    ``SpaceCombatState.enemy_ents``; exit rides ``CombatResult``
    (``_types.py:62``) — outcome gains ``"BOARDED"`` + boarded
    spec/entity/squad fields; ``_handle_combat_encounter``
    (``_encounter.py:200``) returns it to the state-bearing caller
    exactly like DEFEAT bubbles. Interior entry reuses the wreck
    pipeline's seams (``_boardable_wreck_layout`` /
    ``_enter_boarding_dungeon``, ``dungeon_layout.load_layout`` —
    ENEMY directives parse and scatter end-to-end, ``scout_a.layout``
    precedent). The C console rides the ``computer_terminal``
    entity + ``_resolve_computer_terminal`` bump flow, branched by
    a ``capture_spec_id`` stamp on the interior map. Consumption
    reuses ``_remove_procedural_squad`` + the kill-path entity pop
    — AT BOARD ENTRY, not exit (save-safe: saves inside the
    interior rebuild a space map whose spawn list lacks the squad).
    Roll RNG injects per ``generate_registration(rng=)``. The
    Scram gate mirrors ``_dark_dock_refusal`` (pure, refusal-or-
    None) placed in ``npc.py`` before the chat log.
  - Split plan (ratchet: ``_rules_space.py`` 998/1000): extract
    the kill/loot chain (``_pop_dead_entity`` … ``on_kill``,
    ~160 lines) to ``combat/_space_kills.py`` — ``on_kill``
    re-exported from ``_rules_space`` (public surface intact);
    BOARD predicate + handler live in new
    ``combat/_space_boarding.py`` (pure predicate + begin). Net:
    ``_rules_space`` ~850 after adding the dispatch hook.
  - V1 scoping: BOARD only on procedural-squad ships (bounty/
    heist-linked ships keep kill-or-die — quest lifecycle
    untouched); capture targets = specs with a new optional
    ``capture_layout_id`` on ``NpcShipSpec`` (data opt-in like
    ``dark_berth``) — authoring ``scout_crew`` + ``cruiser_crew``
    pirate layouts (P spawn, exit, ENEMY crew markers, C console
    at the cockpit); more layouts are later content.
  - Roll: pure ``roll_clone_sheet(source_faction, tier, rng)``;
    tier from ``find_ship(spec.ship_id).base_hull`` bands
    (proposed: ≤150 T1, ≤300 T2, else T3; source-faction values
    scale with tier, other factions roll near-neutral) —
    constants tunable at top of module.
  - Duplication hotspots: third priced row (rig) follows the
    phase-5 ``_priced_rows`` seam — the built items tuple stays
    the row-existence source of truth; consumption vs kill share
    the removal helpers (no second removal path); the talk gate is
    DATA on the NPC spec (``talk_gate = (faction, min_standing,
    refusal_line)``), not a second hardcode.
  - Edge behavior: "no shields up" reads CURRENT shields (hulls
    without a shield module qualify from turn one — intended);
    hull damage fraction = 1 − hull/max_hull ≥ 0.75; adjacency =
    the bump path's cell adjacency; dead encounter-mates don't
    block (the live-enemy list is what counts); QUEST-linked ships
    never offer BOARD. Capture interiors serialize like dungeon
    interiors; the space map rebuilds without the consumed squad.
  - Tests: predicate truth table; consumption (entity + spawn
    record gone); roll determinism + tier scaling + persisted
    sheet; console gate on the rig; Scram gate per standing
    (masked counts); vendor routing (ambient ``npc_id`` persona
    reaches the talk modal — first user of that path).
  - Stop point: 6b only (cap/delete/sell), plus the standing
    6a stop points.

- [x] PHASE 6b — the library economy: cap, delete, sell — LANDED +
      PLAYTEST PASSED (user-verified 2026-09-07; 7153ddd..4e4d245,
      5 gated commits; 1811 green). REVIEW: APPROVE, no blockers — 5 minors
      (QUIT swallowed in the sell sub-menu; sell-path worn
      auto-clear + console full-line test gaps; dual full-line
      literal per house precedent; guide dark-edge precision) —
      4 fixed (4e4d245), the literal follows the accepted
      can't-afford precedent. The uniform half (phase-4/5
      patterns: tables, purchase handlers, F screen). Playtest
      (2026-09-07): PASSED — the merchant-ally grind fills the
      book, both 6/6 refusals share the line, X delete + worn
      auto-clear, the sell flip clears its cost at the Wolf
      dealer, the dark edge and the Scram regression hold,
      save/load round-trips.

- [x] PHASE 6c — the layout pipeline: the JSON→.layout compiler +
      validator, and the cruiser pilot deck authored through it.
      Split 2026-09-07 (user: "keep the pipeline generator tool in
      6c and move the rest to 6d. I want to focus on this tool
      first. The goal is to be able to get generated layouts at
      least to a place where I can go in with vim and tweak minor
      issues by hand. authoring the full layout by hand is very
      tedious for me.")

  Implementation brief (6c) — drafted WITH the user (2026-09-07;
  reference-hunt + two-stage translation + JSON-pipeline sessions):
  - Scope: (1) the compiler/validator tool — ``tools/layout_compile.py``:
    a JSON spec (rooms with name/rect/role/twin, door edges, entry
    breach/spawn/exit, console pos, hull row-spans, crew markers per
    room, loot tables per room) renders to a ``.layout``; the
    compiler REFUSES to emit on: door to nowhere, disconnected
    floors (BFS from spawn), hull leak (floor adjacent to
    border-connected void), twin-rect asymmetry; ``--check`` mode
    validates any existing ``.layout`` (via the real
    ``dungeon_layout`` parse); (2) reference corpus under
    ``docs/design/references/`` — Mantis A Systems (the cruiser
    pilot reference, fetched + viewed), the user's Slug frigate
    note (shipideas.txt); (3) the cruiser pilot: the cruiser JSON
    spec authored from Mantis A → compiled → validator-clean →
    content pass (crew markers, loot tables, console) → replaces
    ``cruiser_crew.layout`` — then HAND-OFF to the user for the
    vim polish pass and the in-game deck walk.
  - Build order: tool + tests → reference corpus → cruiser JSON
    spec → compile + validate → content pass → hand-off.
  - Binding rulings: JSON intermediary, ``.layout`` canonical
    (recompiles never clobber hand edits — the compiler's job ends
    at first emission per layout_id); the compiler refuses bad
    specs at emit time; decks ship only after the user's vim pass
    + in-game walk.
  - Required tests: compiler happy path (spec → parseable layout
    that ``dungeon_layout.load_layout`` accepts); refusal cases
    (dead door, disconnected rooms, hull leak, asymmetric twins);
    validator ``--check`` over the compiled artifact.
  - Stop point: ONLY the cruiser deck is replaced; no other
    layouts, no coverage flip, no consume bookkeeping, no guide —
    that is 6d.
  - Pilot BUILT (2026-09-07; a9a36b5 + d1ccb02): tool + 6 tests;
    Mantis A reference stored; ``cruiser_crew.json`` (11 rooms,
    9 door edges, mirrored wings, 5 crew across 3 markers, 4 loot
    rooms, console at the bow tip) compiled to
    ``cruiser_crew.layout`` — validator-clean on the first
    content-complete compile (after the spec fixes the validator
    itself dictated: spine reaching the breach stack, spans
    covering the wings, single-thickness bow wall). Parser
    semantics learned: interior gaps and empty rows parse as
    FLOOR — void only exists as ragged leading/trailing space, so
    the compiler spans every row. 1817 green. SILHOUETTE PIVOT
    (user, mid-6c: "focus on the silhouette first — what I want
    to see is a silhouette that follows the source the way my
    example did"): the deck work paused; tools/trace_reference.py
    added — crop the reference, level it (the Mantis climbs
    ~14°), downsample onto the character grid, threshold
    ship-vs-space, fill holes, shave spikes, mirror into a
    symmetric hull. The traced cruiser silhouette
    (layout_drafts/cruiser_silhouette_symmetric.txt) carries the
    reference's waist pinch and blade notches; AWAITING THE
    USER'S READ on the shape before rooms resume inside it.
    Then: vim polish of ``cruiser_crew.layout`` → in-game deck
    walk. PROCESS PROVEN (user, 2026-09-07: "beautiful... it
    proves we have a process that can generate a ship shape in
    the in game art style") — the Kestrel trace quantum-
    decomposed into 38 rects (303×96, sealed, symmetric,
    layout_drafts/cruiser_rect_kestrel.txt + .json); the artifact
    is capital-scale, so the cruiser's own deck size and final
    source choice stay open (2x Kestrel, or a smaller reference
    hunt per the class).

  CLOSED 2026-09-09 (user; same-day playtest round PASSED —
  lit capture interiors + clean auto-explore, freightliner and
  frigate decks walked). Every 6c deliverable shipped and the
  pipeline PROVEN at scale — five decks authored through it:
  cruiser_crew (the pilot — superseded the Mantis draft with the
  slug_b lineage: halo-composited source → 200×74 blessed →
  rect → rooms → user polish → varied spawns; user-blessed
  "cruiser w/crew layout ready"), scout_crew (Stealth Cruiser A),
  hauler_crew (user's small_hauler), frigate_crew (Onslaught),
  freightliner_crew (atlas — 6d's freighter deck, also through
  the pipeline). The body's open item ("cruiser deck size and
  final source choice") is moot — slug B chosen and shipped; the
  capital-scale Kestrel option survives as the act-1 derelict
  idea (doc 39 lineage). Tooling: layout_compile.py (emit
  refusals + --check + never-clobber without --force; 9 tests) +
  trace_reference.py + the references/ corpus. SYSTEMS.md
  boarding/identity entries amended at this close. Deck-walk
  confirmations + remaining decks' bookkeeping live in 6d.

- [ ] PHASE 6d — boarding coverage for every battle spec + the
      remaining decks, via the 6c pipeline. Carries: the frigate
      (the user's shipideas.txt art), scout (rework
      ``scout_crew``), hauler and freighter decks — JSON → compile
      → user vim pass → in-game walk each; ``capture_layout_id``
      on EVERY battle spec (13 crewed specs; derelicts stay on the
      wreck path); consume bookkeeping per the SETTLED ruling
      (full kill pass minus exterior loot; heist cargo rides the
      interior via the component-good mechanism; supersedes 6a's
      bounty/heist BOARD exclusion). Brief: this block, rolled
      forward from 6c's original scope — build order follows 6c's
      proven pipeline per class; deck walks gate each layout.
      DECKS SHIPPED so far: cruiser_crew (slug_b), scout_crew
      (Stealth Cruiser A rework + 3-spec wiring), hauler_crew
      (user's small_hauler), frigate_crew (Onslaught), and
      freightliner_crew (2026-09-09 — the user-polished atlas
      superfreighter deck: 51 markers, consortium crew, wired to
      merchant_freighter + merchant_caravan; freightliner_a back
      to pure salvage duty). Coverage flip landed 031e7c9; 13/13
      battle specs wired 2026-09-09. GUIDE RESOLVED (user rulings
      2026-09-09): the guide teaches the CLONE VERB, never the
      strategy — clone quality scaling with the source ship is a
      DISCOVERED mechanic (no text); the one entry owed was the B
      key in the controls list (landed same day). REMAINING for
      6d: consume bookkeeping (freightliner + frigate deck walks
      PASSED 2026-09-09; scout/hauler walked at their shipping
      playtests).

  Implementation brief (6d residual — consume bookkeeping) —
  APPROVED (user, 2026-09-09: "build it!"):
  - Scope: consuming a boarded hull is exactly a kill minus
    exterior loot (the 2026-09-07 ruling, verbatim: "treat it
    exactly as a kill in all cases, not just bounty targets. minus
    one thing -> no loot dropped. you pick the loot up on the
    ship"). (1) `_capture_target`
    (``combat/_space_boarding.py``) flips: bounty/heist/bounty-
    squad ships become boardable (the four hard conditions
    unchanged — the duel requirement already forces wingmates to
    die or board first); the `salvage_wreck_spawn_id` exclusion
    STAYS (non-combatant wrecks never enter combat — class
    documentation). (2) ``begin_capture_boarding``
    (``game_interactions.py``): after a successful interior load,
    the full kill pass — the shared kill-core extracted from
    ``_finalize_kill`` minus ``_spawn_loot_drops`` (XP base_hull×2,
    ``total_kills``, defeated_names/spec_ids, ``_record_defeat``
    verbatim: bounty/heist id append with the intercept
    distinction, squad drop, ``mark_quest_guard_defeated``
    tombstone) + the victory trio from ``_handle_victory``
    (``_apply_kill_reputation``, ``_complete_bounty_missions``,
    ``main_quest.maybe_complete_bounty``, ``_cleanup_heist_
    spawns``) + heist cargo rides the interior: the mission looked
    up by ``heist_spawn_id`` (same match as ``_spawn_heist_loot``)
    feeds ``component_good_id``/``component_mission_id`` into
    ``_load_layout`` — the wreck flow's exact seam. Lookup before
    the load; a break-away books NOTHING.
  - Build order: predicate flip + tests → kill-core extraction
    (kill path unchanged, pinned) → consume wiring + heist branch
    → gate → reviewer.
  - Binding rulings: consume = full kill minus exterior loot; the
    duel conditions unchanged; quest-lifecycle boardable supersedes
    6a's exclusion; intercept-vs-bounty id distinction preserved.
  - Required tests: bounty leader boardable + consume completes
    the mission + spawn removed; wingmate boardable in a duel;
    heist courier → component inside the interior, no exterior
    cargo entity; kill-equivalence (XP/counter/rep identical);
    tombstone across save/load; break-away books nothing; kill
    path regression unchanged.
  - Stop point: no ship theft, no fabricated-ID content, no doc 41
    work, no new decks, no guide changes.
  - Playtest checkpoint: numbered (bounty board-complete, heist
    cargo inside, save-in-interior tombstone, kill regression).

  Pre-implementation audit (6d residual, 2026-09-09):
  - Reuse: the whole kill pass already exists in two files —
    ``_finalize_kill``/``_record_defeat`` (``combat/_space_kills.py``:
    XP base_hull×2, counters, defeated_names/spec_ids, bounty/heist
    id append, squad drop, tombstone) and the victory trio
    (``combat/_encounter.py``: ``_apply_kill_reputation`` — rep
    rides the broadcast gate via ``modify_rep`` —
    ``_complete_bounty_missions``, ``_cleanup_heist_spawns``) +
    ``main_quest.maybe_complete_bounty``. The heist-cargo interior
    seam is ``dungeon_layout.load_layout(component_good_id=,
    component_mission_id=)`` — the wreck flow's
    ``_boardable_wreck_layout`` precedent (game_interactions.py).
    ``_spawn_heist_loot`` holds the mission-match (heist_spawn_id →
    heist_target_good_id). The tombstone keys the entity's
    ``bounty_squad_id``, which leaders AND wingmates carry.
  - Duplication hotspots: (1) a second copy of the XP/counter/name
    math at the consume site — killed by extracting the kill-core
    from ``_finalize_kill`` (loot drops parameterized out); (2) a
    second heist-mission match — extract the lookup from
    ``_spawn_heist_loot`` into a shared helper both callers use;
    (3) the victory trio re-called — direct calls at the consume
    site, bodies untouched (no drift surface).
  - DRY strategy: kill-core + heist-lookup live in
    ``_space_kills.py`` beside their origins; the consume site
    (``begin_capture_boarding``) composes them — no new module, no
    logic copies. Fakes: the boarding tests' SimpleNamespace ctx
    grows the fields the kill pass reads (player_counters,
    player_active_missions via getattr defaults where the real
    helpers already guard).
      RULINGS + LANDED 2026-09-09 (coverage completed):
      militia_patrol → cruiser_crew wired (13/13 battle specs,
      caddde2→8918623); STATICS ARE BOARDABLE (user: "there's no
      reason for them to not be boardable", e9134ac) —
      `_capture_target` gates on the spec's capture layout, not
      the spawn path; a boarded static re-mans its post on
      re-entry exactly like a killed static always has. The
      bounty/heist kill-or-die exclusion STANDS until the consume
      bookkeeping lands (a boarded quest hull would vanish without
      completing or tombstoning the quest) — hardened to the four
      stamp attrs so squad-grouped wingmates can't slip through.
      TUNING RESOLVED (2026-09-09, user-approved): the bands re-cut
      from (150, 300) to **(40, 80)** — the original cut left every
      hull in the catalog tier 1 (base_hulls 25–100). Now:
      scouts/haulers/freighters T1 (source band 0–60), cruisers T2
      (10–80, allied possible at 7%), the frigate elite — captain/
      warlord/patrol_heavy — T3 (25–100, allied 33%). The ladder
      is live in play.
      PLAYTEST ROUND (2026-09-09, user): three findings, all fixed.
      (1) Capture interiors spawned DARK like derelicts with no way
      to light them (the capture C console is the clone console) —
      live ships now enter POWERED (3e76e0e: sight 20 + power_
      restored at entry; legacy pre-fix interior saves stay dark,
      accepted). (2) Auto-explore oscillated forever at pockets
      mouthed by neutral standing crew — the planner's frame-
      dependent blocking ping-ponged (bb990b5): never-fight bodies
      (spec not hostile to the broadcasting sheet — e.g. the
      consortium crew, a PIRATE-faction outfit, under a pirate-liked
      clone) now seal permanently like powered-down security;
      hostiles + vermin keep the reveal-then-fight contract.
      (3) Same day, a user-save repro: a FIXTURE (Engine Terminal)
      behind a doorway toggled the frame every step (doorways cut
      sight by design) — fixtures (no npc_char_id: terminals,
      consoles, sealed doors) seal permanently too (5fabaed);
      reviewer verified no combat-capable entity spawns without
      npc_char_id + no goto target strands. GUIDE: B key added to
      the combat controls list; clone quality stays DISCOVERED by
      ruling.

(The Line's checkpoint sweep reads these states in doc 41 — doc 40
supplies the states, doc 41 owns the consumer.)
