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

1. **No docking clearance at lawful ports.** Earth, Vega, any
   militia-patrolled port — the log has nothing to enter, so the
   pad stays locked. Outlaw ports (Deadfall, Whisper) don't ask.
   The outlaw doors staying open is what keeps dark usable for its
   purpose (ghost-running, the far side).

2. **Patrol challenge hails.** A militia ship that detects a dark
   contact hails the PLAYER (NPC-initiated comms): identify, run,
   or open fire. IDENTIFY is the moment of truth — flip live or
   wear a face, and what resolves is what gets judged: a scrubbed
   hull is waved through, the true ID gets its record's due, a
   wrong face gets that face's trouble. RUN and FIRE escalate —
   pursuit, heat, guns. Pressure, never a guaranteed kill: the
   ghost run keys on dark, so its tools (a ready face, speed, the
   lure call) must answer this hail — tuning deferred to doc 39
   when that method is built (user: figure the ghost-run details
   later; make this make sense first). Pirates never challenge;
   silence in Ross reads as business as usual.

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
carries the lifestyle price: lawful ports refuse docking clearance
(nothing to log), and militia patrols that detect a dark hull
challenge it — identify (what resolves is judged), run, or fire,
escalating to pursuit and heat; pirates never challenge. Scrubbed
triggers neither — blank paper complies.

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
- [ ] PHASE 3 (dark consequences — ruled 2026-09-06, not yet
      built): the lawful-port dock gate (docking refused while
      DARK; outlaw ports don't ask) and the militia challenge hail
      (NPC-initiated comms on detect: identify / run / fire;
      escalation is pursuit + heat, never a guaranteed kill;
      ghost-run tuning lives with doc 39 when that method is
      built). Scrubbed triggers neither — that compliance is the
      6,000cr. Tests: dock gate per port class; challenge outcomes
      per broadcast state.
- [ ] Phase 4+: resolved identities feeding the Line's sweep
      (doc 41); capture (shadow/record) as the clone pipeline;
      faction hostility reading apparent_faction (the Ross pose)
