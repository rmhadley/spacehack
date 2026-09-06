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

**Spoof sources and their mappings (exactly three):**
- SCRUBBED → maps to blank: a tramp hull with no history; every
  reader's default-civilian posture. The cheapest lie — "I'm no
  one."
- CLONED → maps to the source's apparent standing: a Ross pirate's
  ID resolves as one of theirs; a militia patrol's callsign reads
  as rank. The ID borrows someone real's relations.
- FABRICATED RANK → maps to the institution itself: a command
  callsign reads as the Militia, which outranks the reader.

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

## The complete settled design (one statement)

Every ship broadcasts. An ID is an identifier that maps to
relations — the game has lived in live mode since day one (detect,
identify, rate, behave). The layer adds key choice: live (true
ratings — today, nothing new), dark (nothing resolves; countered
only by eyes and the Line's density), spoofed (the face's implied
relations; three sources: scrubed→blank, cloned→source's standing,
fabricated rank→the institution). Explicit registrations for RP
flavor; the F — faction screen is the identity hub (broadcast
state, cycling collected IDs). Intrinsic transponders; services at
the outlaw ports work the modes; identity rides the player across
lawful purchases (the scrub is an unlawful hull). Rep moves only
while live — the mask cuts both ways on both axes. Nothing breaks a
complete spoof in v1 (in-person inspection parked). NPCs broadcast
into comms; cloning is rare, difficult, expensive — a process. Dark
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
- [x] PHASE 3a — the dark dock gate — CODE LANDED 2026-09-06
      (cf26aba + 3466c06; playtest checkpoint PENDING): berthing
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
    map is never built. Wording plain port-side register, per the
    Quest prose standard.
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

- [ ] PHASE 3b — the militia challenge hail (ruled 2026-09-06;
      built after 3a's checkpoint): NPC-initiated comms on detect:
      identify / attack — TWO options, no RUN (no run mechanic
      exists; a future run-mechanic doc would collect all such
      interactions). ATTACK escalates to combat + heat, never a
      guaranteed kill; ghost-run tuning lives with doc 39 when that
      method is built. Scrubbed triggers nothing — blank paper
      complies. Tests: challenge outcomes per broadcast state
      (identify judged per worn face; attack escalation).

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
- [ ] Phase 4+: resolved identities feeding the Line's sweep
      (doc 41); capture (shadow/record) as the clone pipeline;
      faction hostility reading apparent_faction (the Ross pose)
