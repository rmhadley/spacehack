# DESIGN: The Lore & Rumor System — Knowledge as Currency

**Status: DESIGN IN PROGRESS — no implementation until the user
explicitly requests it.** Third of doc 39's four feature docs.

Companions: `39_DESIGN_ACT1_BLOCKADE.md` (discovery vectors the
methods depend on); the Qud-inspired seed notes live there.

## The ruling this doc serves (user, 2026-09-06)

> This is huge. NPCs, comms — a system that lets the player
> explore more of the lore and RP with the universe to find
> solutions and unlock options. Loot that teaches; finds that send
> you somewhere; deep dives yield legendary loot AND/OR info; info
> trades for info throughout the world.

## First-pass shape (for review)

**The insight:** rumors unlock questions, and questions unlock
rumors. Knowledge is a keyring; the world is the lock collection.

**A data-defined lore catalog** (like every catalog in this
codebase): entries with an id, a chain, their text, delivery
vectors, and what knowing them unlocks. Player state: a persistent
known-lore set (the keyring, saved like traits).

**Delivery vectors** (all existing gameplay surfaces):
- Bar talk: the rumor economy's trading floor — bought rounds,
  guild-known regulars, frontier drunks who saw something
- City NPC small talk: bump-and-talk flavor becomes occasionally
  load-bearing (WHO they are gates WHAT they know)
- Comms scuttlebutt: hail a convoy, hear gossip between trade
  options; patrol chatter
- Finds: loot that TEACHES — the rotation schedule on a warrant
  target, data pads in derelicts; a find that SENDS you somewhere
  (a map fragment pointing at a site)
- Deep dives: dungeon sites whose payoff is legendary loot AND/OR
  info (Qud pattern)

**The question loop (the RP layer):** hearing a rumor unlocks
"ask about it" on NPCs who'd know more. Chains tier: myth →
shape → witness → procedure (the bribe's chain is the first
authored instance of a universal pattern).

**Info trades for info (the economy):** knowledge as currency —
trade the vault's location for the wall's man. NPCs who deal in
info: brokers, bartenders, archives. What do they take in
exchange? Info, credits, services?

**Option-unlocking:** dialogue/interaction options gated on the
known-lore set (the false backup call, the heist entry steps, the
Commandant's procedure). The game never labels "this is the
ghost-run step" — comprehension is the puzzle.

**Shape amendments (user, 2026-09-10, before the refine):**

1. **Authored like quest dialogue, 100% outside code.** Not just
   data-defined — the quest-dialogue design is the model: rumor
   text and organization live in authored data (step-spec style:
   easily found, easily altered, never a code change to reword or
   reorganize). The lore catalog inherits the quest system's
   content-lives-on-the-spec discipline.
2. **A per-run proc/RNG aspect.** No static loop — "talk to NPC X,
   ask about Y, X sends you to Z" must NOT play identically every
   run. Some of the system varies with the run seed: which chains
   surface, who knows what, where finds point. Authored chains
   stay authored; the ROUTING through the world is what the seed
   shuffles (the seed-pinning machinery — SPACEHACK_SEED,
   engine.RNG rebinds, derived seeds — is the existing substrate).
3. **The rumor UI is a reusable SUB-MENU of the main chat
   options** — one "ask around" style entry on the chat screen
   that opens the SAME look/feel no matter who you're talking to
   (barkeep, broker, patrol, city NPC). One interaction pattern
   to learn, everywhere.

## Open questions (the review agenda)

1. Display: does known lore show anywhere (a journal/leads tab) or
   stay purely diegetic ("keep it in your head")?
2. Gating: heard-set alone, or also rep/guild (a Militia sergeant
   won't gossip with a pirate)?
3. Can rumors be WRONG — deliberate lies that mislead? (The best
   lore systems sometimes lie.)
4. The exchange: how is an info-for-info trade structured
   (inventory of tradeable secrets? NPC-specific wants?)
5. How much is data (catalog entries) vs. authored scenes?
6. Relationship to quest steps: are rumor chains invisible quest
   steps riding the existing status machinery, or a new state
   space?
7. What exactly does the seed vary (amendment 2): chain
   availability per run, NPC-to-rumor assignments, find locations
   — and what stays FIXED because it's authored? Where do the
   per-run rolls live so save/load stays consistent?
8. The sub-menu's shape (amendment 3): does it apply to BOTH the
   space comms modal and the city/bump NPC talk (one pattern, two
   hosts), and what's its option surface — a list of askable
   topics built from the known-lore keyring?
