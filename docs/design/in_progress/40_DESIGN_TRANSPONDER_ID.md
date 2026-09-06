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
- SCRUBBED → blank sheet: all factions neutral. A tramp hull with
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
- Masked (dark or any fake): rep deltas do NOT touch the true
  ratings. The mask cuts both ways, now on both axes — friends
  don't recognize you, and your crimes (and good deeds) don't
  follow you home. Hiding is safe AND stagnant; exposure is risk
  AND growth.

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
cut-out must be installed at a pirate-run port (the same storefronts
as the scrub; priced below it — silence is cheaper than paper).
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
exists. Reads resolve the broadcasting ID; writes still land on ID
1 only while it broadcasts (Q4).

**Capture is live-ship boarding (user ruling — new feature).** The
shadow/record verb is replaced by boarding: meet the requirements
(shields down, adjacent), board the LIVE ship — not a powered-down
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
is the HUNT. Delete exists to clear junk.

**Library (user ruling): capped slots + delete + sell.** Small fixed
library (slot count pinned in the phase 6 brief), delete free at the
F screen, outlaw-port brokers buy codes back for a fraction of
value.

**Boarding is an extension, not a new system (user correction).**
Ship boarding already exists (wreck bump-boarding into dungeon
interiors, ``game_interactions._resolve_npc_ship_blocker``); the
capture phase EXTENDS it to live ships — no sibling doc. V1 calls
(proposed in the phase 6 brief, veto freely): a ship crippled to
shields-down with hull intact becomes boardable (overkill destroys
the prize — no wreck salvage); the interior spawns its crew
(ENEMY markers in the layout); the C console at the cockpit offers
the clone with the tech installed; console taken, the hull powers
down to a derelict (existing loot flows apply). Ship theft parked.

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
  lawful ship purchase; its sheet IS ``ctx.faction_reputation``,
  and it is the only sheet behavior changes (while it broadcasts —
  the Q4 write ruling is unchanged: deltas under any other ID are
  discarded).
- **Scrubbed** → a blank sheet: all neutral. Blank paper, exactly
  as ruled.
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
  read swaps to the sheet (phase 4).
- The F screen renders the broadcasting ID's actual sheet — no more
  "Friendly (Faked)" / "No Data" approximation rows (the broadcast
  block still says which ID and which mode).
- The spawn gate is unchanged (engage only on resolved
  disliked/enemy) — a pirate clone stands the Ross crown down
  because its sheet's VALUES are allied-with-pirates.
- No save migration: library entries without a ``rep`` field read
  as a blank sheet (every collectible ID today is scrubbed).

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
dark requires a one-time cut-out installed at a pirate-run port
(priced below the scrub — the free D toggle is superseded); identity rides the player across
lawful purchases (the scrub is an unlawful hull). Rep moves only
while live — the mask cuts both ways on both axes. Nothing breaks a
complete spoof in v1 (in-person inspection parked). NPCs broadcast
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
      through the gate in testing), and the F-screen identity hub
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
- [ ] PHASE 4 — the broadcasting ID's reputation (re-cut
      2026-09-06 from "apparent standings": IDs carry rep sheets,
      not faction mappings — see the sheets SETTLED section). One
      pure resolver — the sheet of whichever ID broadcasts — feeds
      every reader; existing consumers keep their logic (user:
      "reputation drives this system 100%").

  Implementation brief (4) — re-cut 2026-09-06, PENDING approval
  (supersedes the approved apparent-standings brief):
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
    disliked/enemy — audit first that derelict/blocker entities
    don't route through this pass), ``_militia_scan_chance``,
    ``comms`` contact attitude + hostile hail label, ``trade``
    merchant/npc-faction attitudes, ``mission/_board`` reward
    adjust. ``_charged_cell_aggro`` NOT routed; ``faction.py``
    monthly decay keeps the true dict (time, not a reader).
    Superseded face machinery: ``identity.apparent_faction``
    deleted (with its tests); F screen ``_masked_row`` deleted,
    ``_faction_rows`` renders the resolver's sheet directly;
    ``_judge_identification`` (comms) judges the broadcasting
    sheet's militia VALUE — faction special cases removed, pass
    line unchanged, hostile outcomes unify to one line ("The
    registration reads hostile: the patrol opens fire!"); callers
    comms.py ``_run``/``resolve_identification`` path adjust
    (identify sets the broadcast, the judgement reads it). Writes
    untouched (modify_rep broadcast gate, Q4). No save migration
    (missing ``rep`` = blank); no new acquisition content.
  - Build order: resolver + tests → judgement swap → static-spawn
    gate → routed readers → F screen sheet display → guide touch →
    ``make check``.
  - Binding rulings: IDs carry sheets, not faction mappings (no
    player-layer read keys on the face's ``faction`` field); only
    ID 1's sheet changes from behavior; scrubbed sheet = blank;
    dark resolves neutral; cloned sheets roll at capture (6);
    mask cuts both ways at reads (masked trade loses earned
    attitudes).
  - Required tests: resolver per state (live / worn entry with
    sheet / worn blank-sheet scrub / dark); judgement by sheet
    values (blank passes, positive militia sheet passes, hostile
    sheet draws fire — replaces the faction-special-case tests);
    static spawns stand down on neutral + engage on disliked/enemy;
    scan chance reads the sheet; trade attitude masked → neutral;
    charged-cell still aggros through any ID; F screen renders the
    worn sheet; live unchanged (existing suite).
  - Stop point: NO clone capture or rolls (6), no cut-out (5), no
    boarding, no Line work, no new collectible IDs.
  - Playtest checkpoint (numbered): buy the scrub, wear it — the
    Ross crown drifts past; Sol patrol scans at the neutral rate;
    trade prices lose the earned discount; F screen shows the
    scrub's neutral sheet while worn and the true sheet after
    cycling back; flip live — everything as today; go dark —
    pirate spawns ignore, militia challenge still fires; save/load
    across all three states.

- [ ] PHASE 5 — dark's cut-out (the price of entry). Dark requires
      a one-time transponder cut-out installed at a pirate-run
      port; the F-screen D is inert until then.

  Implementation brief (5) — APPROVED (user, 2026-09-06):
  - Scope: ``transponder_cutout: bool`` on GameContext (saveload
    both directions; legacy saves migrate False — dark must be
    earned); ``identity.toggle_dark`` refuses without it (plain log
    line); the F-screen dark row shows the un-installed state; the
    install is a second priced row on Deadfall's scrubber
    (``deadfall_scrubber``) alongside the 6,000cr scrub — 2,500cr
    (silence is cheaper than paper); guide section updated.
  - Build order: field + persistence → toggle gate → F-screen state
    → service row → guide.
  - Binding rulings: one-time install, never consumed; other pirate
    ports selling it are deliberate later content, not system
    growth; the scrub is unaffected.
  - Required tests: D inert without the cut-out; works after
    purchase; no double charge; persistence round-trip; legacy-save
    migration.
  - Stop point: NOTHING from phase 6 — no recorder/rig, no
    boarding.
  - Playtest checkpoint: D does nothing on a pre-cut-out save →
    buy the install at Deadfall → D works → save/load keeps both
    the cut-out and the dark state.

- [ ] PHASE 6 — the capture pipeline: live-ship boarding + the
      clone economy. Ruled above (capture + clone quality section,
      2026-09-06); the brief is drafted at phase 5's playtest
      checkpoint (3b precedent — shape may shift with what the
      phase 4 playtest shows). Carries: the crippled-ship
      boarding extension (shields down + hull intact boardable;
      overkill destroys the prize), crewed interiors (ENEMY
      markers), the C console clone (rig-gated, sheet rolled by
      the source's quality tier — one roll per source, persisted),
      library cap/delete/sell.

(The Line's checkpoint sweep reads these states in doc 41 — doc 40
supplies the states, doc 41 owns the consumer.)
