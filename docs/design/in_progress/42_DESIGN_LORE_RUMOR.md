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
info: brokers, bartenders, archives. (Ruled 2026-09-10: a favor
currency on per-dealer ledgers — SETTLED 6.)

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
   run. Some of the system varies with the run seed: who carries
   what (live-candidate subsets — SETTLED 15; the seed never gates
   a chain itself, SETTLED 14), who knows what, where finds point.
   Authored chains
   stay authored; the ROUTING through the world is what the seed
   shuffles (the seed-pinning machinery — SPACEHACK_SEED,
   engine.RNG rebinds, derived seeds — is the existing substrate).
3. **The rumor UI is a reusable SUB-MENU of the main chat
   options** — one "ask around" style entry on the chat screen
   that opens the SAME look/feel no matter who you're talking to
   (barkeep, broker, patrol, city NPC). One interaction pattern
   to learn, everywhere.

## Settled — the system's shape (refine session, 2026-09-10)

The review agenda cleared in one session — every open question
ruled. These bind all phases.

1. **State model — a new lore catalog + keyring, NOT quest steps.**
   Frozen dataclass rows in `data/lore/` (chain, tier, text keys,
   sources, unlocks) linked inside the catalog; player state is a
   persistent known set on ctx (`known_rumors`, saved like traits).
   Dialogue rows read the keyring. The quest machinery stays
   untouched — boards, wait gates, Q-log steps, rewards, migrations:
   rumors are ambient knowledge, not tasks.
2. **Display — a verbatim ledger.** Heard text is recorded verbatim
   in a browsable pane reachable from the Q log alongside quests —
   a true pane inside the Q-log modal (pinned at the ADVISE round,
   2026-09-10), presented with the shared multi-pane tab treatment
   the C screen already uses (user, 2026-09-11: "The Q screen needs
   the multi-pane tab treatment the rest of the UI already uses.
   C screen uses it. No need create a new way to do this.").
   No objectives, no labels, no "ask X about Y" — the notebook
   never teaches; comprehension stays the puzzle. Solves the real
   hole: dialogue modals vanish on close, so today a lead named
   once is lost.
3. **Scenes — catalog-only.** Every rumor is a catalog row; all
   depth comes through the ask sub-menu (topic row → tier text →
   newly unlocked topics). Per-NPC specificity is data on the row
   (witness text keyed by npc id, generic fallback) — the bar
   chain's dialogue-variant shape generalized. No scene machinery.
4. **Gating — attitude floors on SOURCES; the keyring never
   gates.** Once heard, known forever. Who can be asked is data:
   catalog rows carry floors per source, read off the resolved
   sheet — the one-read resolver. Floors are the talk-gate family
   (`npc._talk_refusal` refuses below a resolved standing): the
   "pay, not access" ruling governs the market economy (board
   pay, trade prices), not whether an NPC will gossip. DARK reads
   neutral like every other resolver reader — common gossip stays
   askable, liked/allied floors refuse (ruled 2026-09-10: no
   special case). Authored rows may also demand traits/perks where
   the fiction wants it (warrant-license style).
5. **Lies — authored only.** Specific entries flagged false route
   you somewhere the author chose (an ambush; a dead end whose
   search reveals the lie) — never a random roll, always
   discoverable in-world. The flag and its machinery land in the
   phase that ships the first lie.
6. **The exchange — a favor currency, per-dealer ledgers.** (user:
   "You offer a rumor, you gain favor. You ask for a rumor, you
   lose favor." — explicitly not faction rep: "I don't immediately
   believe that it lives well in our faction/rep system (especially
   with fake transponder ids)... maybe we can have some kind of
   rumor/favor currency that you can build and spend?") Each
   info-dealer keeps their own book on you: `rumor_favor` on ctx, a
   dict keyed by dealer id, saved like the keyring, ID-agnostic —
   the worn face never touches the book (floors follow the face;
   favor follows the person). Offer = +the rumor's authored value,
   once per (rumor, dealer); ask an exclusive = −its price; floor
   at zero — earn before you spend. V1 line: only seated dealers
   (barkeeps, brokers, archivists) trade; comms scuttlebutt and
   patrol chatter are free hearsay.
7. **Seed — routing derived from INIT_SEED, nothing serialized.**
   Every per-run variation is a pure function of INIT_SEED +
   stable keys (the city-NPC-route precedent: keyed derivations
   never reshuffle). The seed varies the ROUTING: which candidates
   are live (SETTLED 15), which dealer holds which exclusive
   (SETTLED 17), where finds point (seeded pick among authored
   candidates). AMENDED (phase-3 refine, 2026-09-11): the seed
   NEVER gates a chain — the "seeded subset of chains" first
   written here is superseded by SETTLED 14–16; every authored
   chain is completable every run. Content stays authored.
   CONTINUE regenerates identical routing from the persisted
   INIT_SEED; SPACEHACK_SEED makes playtests reproducible; Shift+S
   reroll yields a different but equally legal routing.
8. **The sub-menu — both hosts, one row, everything askable
   inside.** One "Ask Around" row on the city/bar NPC talk modal AND
   on the space comms matrix for talkable contacts (derelicts and
   the restricted-space blockade keep their End-Transmission-only
   rows). Same look/feel everywhere — one interaction pattern to
   learn. AMENDED (user, 2026-09-11: "'Ask about X' and 'Ask about
   Y' are going to move in to a sub menu and not be right there in
   the main NPC menu next to 'View available work'?"): the main
   menu carries exactly ONE Ask Around row — shown whenever the
   contact holds anything (an unheard opener they can deliver OR a
   heard chain they can extend; ruling 10 adds a dealer's trade) —
   and the sub-menu lists BOTH kinds
   of rows; no opener rows on the main menu. Topics they can't help
   with are never listed — greyed lists teach; no row at all when
   there's nothing to ask.

## Settled — phase 2, the favor exchange (refine session, 2026-09-11)

9. **Dealers — existing seats, role-keyed books.** The phase-2
   dealers are authored seats, no new NPCs: `barkeep`, `wolf_barkeep`,
   `research_officer` (the archivist shape; three systems, three
   ledgers). Generic ids seat many bars — the ledger keys the ROLE
   id, so any seat of that id honors the same book: the grapevine,
   uniform with every other npc-id-keyed table.
10. **The buy side — uniform, one value per rumor.** Any dealer buys
    any heard rumor they haven't already bought from you, at the
    rumor's authored value — one number per rumor, on the catalog
    row (SETTLED 6's "the rumor's authored value"). No specialist
    buy lists. The main-menu Ask Around row shows for a dealer even
    with no askable topics — their trade lives in the sub-menu.
    AMENDED (phase-2 playtest round 1, 2026-09-11): a dealer won't
    buy an entry they are an authored source of — the teller knows
    their own rumor (round note below).
11. **Priced rows — hidden until affordable.** A dealer's exclusive
    lists only when the player's favor with THAT dealer covers its
    price; the sub-menu body line states the balance ("Favor: N")
    and offer rows caption what they earn. Extends SETTLED 8's
    no-greyed-rows ruling to the priced surface.
12. **The option-unlock payoff — the hidden vendor.** An authored
    exclusive (`dark_berth_4`, tier 4 of the dark-berth chain, never
    free-asked — empty sources) is held by `wolf_barkeep` this
    phase. Knowing it unlocks a cut-out install at Whisper — one new
    single-seat NPC (the berth's keeper; identity tables stay
    npc-id-keyed), the knowledge the only key, uniform data-gated
    rows. (The bribe was ruled here first, then re-ruled: doc 39's
    bribe is a CLOSED RULING with no built interaction — the
    Commandant, the 100k payment, and the four-tier chain exist in
    no code, so the payoff could not anchor there.)
13. **Earned-set home — one field.** `rumor_favor[dealer_id]` values
    are `{"favor": int, "earned": [rumor ids]}`; no third ctx field.
    The once-per-(rumor, dealer) set lives in `earned`.

## Settled — phase 3, the routing model (refine session, 2026-09-11)

14. **The seed shuffles routing, never availability.** (user:
    "Authored chains need a way for them to be discovered and all
    authored chains should be discoverable. No authored chain should
    be blocked because of RNG seed. And no authored chain should
    START discovered." + "the RNG changes where the next steps take
    you. which npc's you need to find on which planets in which
    solar systems.") Every authored chain is completable in every
    run — no chain is seed-blocked, no chain is seed-gated to a
    subset of runs. What varies is WHERE the next step lives: which
    NPC seats carry each entry this run. Still pure INIT_SEED
    derivations per SETTLED 7 (deterministic, CONTINUE-stable,
    SPACEHACK_SEED-pinnable, Shift+S reroll → different legal
    routing).
15. **Sources become planet-scoped candidate pools with authored
    width.** A candidate teller is `(npc_id, planet)` — if the seed
    makes the candidate live, ANY seat of that role on that planet
    delivers (user picked npc+planet over planet+building;
    buildings stay the seat data's business). The entry lists its
    possible NPCs; the derivation picks the live subset; width is
    authored per entry (user: "The rumor chains can list the
    possible NPCs that the RNG chooses. Some steps - narrow. Other
    steps - very wide. all up to the data.") — narrow = pick 1 of
    the pool, wide = most/all of it. Floors and traits stay
    per-candidate in the data, unchanged on top of routing
    (user: "yes, this doesn't change those settings that also
    should live in the data") — a seeded witness behind a militia
    floor is also a rep puzzle. Completability: the derivation
    always leaves ≥1 route per non-exclusive entry; the catalog
    test asserts non-empty pools.
16. **Discovery is an authored route, not a default.** No chain is
    askable at New Game: an opener enters the keyring only through
    routes its row authors — a world-event TRIGGER, a find pad,
    comms hearsay (phase 4), or finding a seeded carrier. Triggers
    are first-class (user: "There needs to be other ways besides
    talking through rumors to discover a chain. The blockade chain
    should be discovered once you discover the blockade. Have you
    been warned to turn back? Yes: discovered. We need to support
    triggers like this.") — the entry authors trigger ids; the
    owning system fires the event and the opener is delivered
    through the hearing idiom (keyring + ledger, readout modal).
    The phase-1 chains get re-authored under this rule: today's
    everywhere-seats (`barkeep` in every bar) are why two chains
    are askable at spawn.
17. **Exclusive holders: candidates + pick.** Each exclusive
    authors candidate `(dealer, price)` pairs; the seed picks one
    live holder per run (same derivation idiom as SETTLED 15).
    Proposed content, tunable: `dark_berth_4` candidates = all
    three dealers at price 4. A dealer who is a candidate but not
    live this run holds nothing — no Buy row, same as any
    empty-handed dealer.
18. **Mid-chain pointers are authored witness text.** Each
    candidate's `witness.<npc_id>` override may point onward — the
    precision (names the planet / names the role / names nothing)
    is the author's call, per candidate. The ledger keeps canonical
    text (the phase-1 pin stands). No procedural hint line, no
    greyed rows — the sub-menu still never lists what a contact
    can't deliver.

## Settled — phase 3, the finds (refine session, 2026-09-11)

19. **Pads teach on pickup.** A data pad is a find that, on pickup,
    records its authored entry on the keyring + ledger and presents
    the readout — knowledge IS the item; nothing goes to the hold,
    nothing sellable (the quest-cargo spirit). Phase-3 pad
    surfaces, user-picked: **boarded-ship and derelict loot**
    (authored pad table beside the goods those drops already
    carry). Dungeon loot joins as a pad surface when the dungeon
    system lands (phase 4).
20. **Dig sites are 100% procedurally generated layouts.** (The
    LAYOUT is proc-gen; authored landmark ROOMS may sprinkle in —
    AMENDED 2026-09-12, SETTLED 25.)
    (user: "Procedurally generated dungeons entirely. Nothing
    authored. We have lots of planets. We expose a dungeon option
    on that planet if you've 'discovered' it. Can be revisited once
    discovered. 100% procedural generated — can be multi level.
    Each planet already has a theme concept, we might need to
    expand that to include proc gen dungeon theme too.") A fragment
    discovers a planet's dungeon: the option is exposed on that
    planet once discovered, revisitable thereafter; floors are
    proc-gen, possibly multi-level, themed off the planet's theme
    concept (extended to dungeon themes). Big enough to be its own
    phase — the phase list below is restructured (new phase 4; the
    lie moves to phase 5).
21. **Legendary loot is out of this doc's phases.** (user: "Let's
    just focus on the system. The legendary loot will be a new
    phase or even a new design doc. I'm thinking like: multi-purpose
    ship modules. A shield generator AND cargo space all in one
    module slot?") The dig payoff question is deferred; multi-purpose
    modules are the seed note for that future doc. Dungeons ship
    with ordinary loot (+ pads as info) until then.
22. **Fragments point at planets, seeded among candidates.** A
    fragment is a find (the pad pickup machinery) whose row authors
    candidate planets; the seed picks the live destination this run
    (SETTLED 7's "seeded pick among authored candidates" — the
    candidate set is every planet, SETTLED 25). Rendering per
    SETTLED 37: the ledger line stands, from the discovered-sites
    state.

## Settled — phase 4, the dig dungeons (refine session, 2026-09-11)

23. **The gate is discovery; authored dungeons are untouched.**
    Existing explorables (mercury, wolf_b, barnards_b, procyon_c,
    the mars signal site) keep today's unconditional Explore option
    — quest flows and playtested sites untouched. The option is
    HIDDEN until the site is discovered (user: "We expose a dungeon
    option on that planet if you've 'discovered' it"), shown and
    revisitable thereafter; the discovered-set is player state like
    the keyring (saved, New Game clears). AMENDED (2026-09-12,
    SETTLED 25): RNG sites are NOT a new authored planet set —
    every planet can carry them.
24. **Depth-capable on the shipped machinery.** Phase 4 wires
    discovery gating and dig generation on the existing BSP
    generator + ``ctx.interiors`` revisit cache — extended with a
    generated stairs-down and per-floor persistence (the mars
    prison extension's floor idiom; SETTLED 38). The fragment's
    seeded destination pick (SETTLED 22) varies WHERE the dig is;
    depth is the planet spec's (SETTLED 38).

## Ruling — one chain (user, 2026-09-11)

The catalog narrows to ``dark_berth`` alone: ``derelict_line`` and
``thin_month`` are retired (rows + prose; shipped in phase 1, dropped
before phase 3). Pre-ruling keeps saves safe: stale ids on the
keyring and in earned sets fade through the stale-id skip, no
migration. The gate contracts the dropped chain's data carried
(militia floors, the captain's trait gate) stay pinned on a fixture
registry in test support. Phase-3 brief content that named the
dropped chains — the derelict-line opener candidates, the
``line_warned`` trigger instance, the pad contents — falls with
them; the trigger MACHINERY (SETTLED 16) stands and the brief
re-proposes its content against the one chain before approval.
dark_berth is the refinement target.

## Settled — phase 4, the dig dungeons (refine session, 2026-09-12)

25. **Universal sites — every planet, no roster.** (user: "I want
    every planet in the game to be available. it's a lot but it's
    worth it. I want the proc gen rumor dungeons to be built in a
    way that works with any and all planets in the game now and any
    future ones we add too.") AMENDS SETTLED 23 — the discovery
    gate is NOT scoped to new dig planets: any planet, existing or
    future, can carry RNG dig sites; a planet can have several.
    Authored quest dungeons (the mars caves/prison, mercury, wolf_b,
    barnards_b, procyon_c surfaces) stay exactly what they are,
    quest-gated; Mars can have the caves AND an RNG site. AMENDS
    SETTLED 20's "nothing authored": the LAYOUT is 100% proc-gen,
    but landmark rooms — authored special-room pieces — may sprinkle
    in (user: "Not every dungeon needs a landmark, but finding a
    special room here and there can add some interesting detail").
26. **The spec feeds the generator.** (user: "a planet spec that
    seeds the rng dungeon builder with custom settings to produce a
    dungeon simply... nothing hardcoded in the generator per site.
    the site feeds the generator a config.") No new generator: the
    BSP builder is config-driven — size, difficulty, theme.
    Difficulty and loot quality scale by the planet's tier;
    tiles/colors come from the planet's spec theme; planets without
    an authored dig config derive one from theme + tier, so future
    planets work automatically.
27. **Discovery: three RNG-rare doors.** (user: "datapads dropped
    from humanoid enemies. datapads found as loot on derelicts.
    accessing the C on a boarded ship. all rng based, not
    guaranteed. rare enough to feel special when you find one.")
    None guaranteed; rarity-tuned. The rumor-system tie-in is
    DEFERRED to its own future doc (user: "rumor system will
    definitely be a thing... but let's just keep rumor system in
    mind as we design this and we'll do a design doc to extend
    rumor system another day") — narrowed by SETTLED 37: no
    rumor-CHAIN integration now, but the pointer LINE does land in
    the rumors ledger (rendered from the discovered-sites state).
28. **The discovered-sites context.** (user: "we need a context
    somewhere that records what random sites you've found and where
    they are. and then there will be explore options on the planet
    menu based on what you've found. the name of the explore site
    should be procedurally generated. allllll rng.") Saved player
    state like the keyring; the planet menu carries one Explore row
    per discovered site on that planet, hidden until found; site
    names generate from seeded word pools.
29. **Revisit = persisted maps and state, "like the martian
    caves"** — the ``ctx.interiors`` cache idiom; cleared stays
    cleared, revisitable forever after discovery.
30. **Dungeon loot is a placeholder pending its own doc.** (user:
    "I think we're going to need a whole design doc for this. right
    now we need some placeholder that we can expand another day
    with a whole design doc.") V1 ships a minimal tier-scaled
    placeholder; the pad surface INSIDE dungeons defers to that doc
    (supersedes SETTLED 19's "dungeon loot joins as a pad surface"
    for this phase).

## Settled — phase 4, refine round 2 (2026-09-12)

31. **Site stacking confirmed.** Each reveal is a new, distinct
    site — planet seeded among all planets, site identity seeded;
    no cap; rarity keeps counts low in practice.
32. **Three landmark pieces at first; agent drafts, user
    iterates.** (user: "just 3 landmarks at first, you author
    first, then we iterate together to refine/polish them.") The
    prose gate applies to my drafts.
33. **Site names: prefix/suffix pools ON THE PLANET SPEC.** (user:
    "I like the idea of the prefix/suffix being configured at the
    planet spec!") Two-part generated names; each planet authors
    its own word pools, with a derived default for planets (and
    future planets) that don't.
34. **The reveal idiom = the dark-port discovery.** (user:
    "datapad pickup consumes and you get a rumor unlocked, just
    like discovering the dark port rumor from previous phase.")
    Consume-on-pickup, readout modal, permanent record — the same
    idiom as a hearing.
35. **Placeholder loot is a pluggable config, not a hardcoded
    pile.** (user: "as long as there's a system that we can plug in
    to later when we design better loot") — the site's cache loot
    spawns through a per-site loot spec the future loot doc
    expands in place.
36. **Rarity: three flat rolls, one authored rates table** (opening
    guesses 1-in-12 / 1-in-8 / 1-in-6), tuned at playtest.

## Settled — phase 4, refine round 3 (2026-09-12)

37. **Site pointers land in the RUMORS tab (user: "A -- rumors
    tab").** The reveal is a full hearing: readout modal, a verbatim
    pointer line in Q → RUMORS rendered from the discovered-sites
    state (template + injected site name + planet — SETTLED 22's
    original rendering, RESTORED; round 1's ledger deferral is
    narrowed to: no rumor-CHAIN integration — fragments teach no
    chain entries; pointer lines only). The structured
    discovered-sites state stays the source of truth for the planet
    menu and the map cache; the ledger line is its presentation
    twin. SETTLED 27's amendment note is superseded by this ruling.

## Settled — phase 4, refine round 4 (2026-09-12)

38. **Depth ships now; the planet spec defines min/max floors.**
    (user: "Depth capable with planet spec defining min/max
    floors." — answering the agent's depth question; "I definitely
    want multiple floors in the end".) Sites are floor-native from
    day one: each site's depth rolls seeded within its planet's
    ``dig_min_floors``/``dig_max_floors`` at reveal; the BSP pass
    generates a stairs-down per non-bottom floor (stairs are
    terminals — the shipped idiom); every floor persists under the
    site's cache; difficulty and placeholder loot scale with
    tier + floor. Planets without authored bounds derive the
    default range 1-2 (tunable data) — every planet is depth-capable
    out of the box, the spec tightens or widens per theme. AMENDS
    SETTLED 24 (rewritten above).

## Phase 2.5 — the dark-ports chain (design 2026-09-11; implements with phase 3)

The one-chain ruling made ``dark_berth`` the refinement target; the
back-and-forth re-took the chain's spine. The user (2026-09-11,
verbatim, typos fixed):

> 1. You discover a port that doesn't check transponder ids (most
>    obvious way: by docking in one).
> 2. This needs an event tied to it. Something even as simple as a
>    message log: "This port didn't verify any credentials."
> 3. This unlocks a rumor chain — "ask about dark ports".
> 4. This leads the conversation through RNG NPCs on RNG planets —
>    following a rumor, learning about dark ports and the ships
>    that use them.
> 5. In the end you learn about an NPC that will install the
>    cut-out.

The earlier credits-trail spine ("who pays for the quiet") is
dropped — it failed the user's logic audit (nobody pays the
player's docking fee, and no docking fee exists). The chain is now
experiential: observe, ask, meet someone living it, buy the tool.

### Verified ground it stands on (all shipped, doc 40)

- The ``dark_berth`` PlanetSpec flag is set on exactly the four
  ports the chain names: lal_b, lal_c, ross_b, wolf_b. A DARK hull
  is refused everywhere else ("Docking request denied: transponder
  not responding") — the differential is real mechanics, not
  flavor.
- Landing cargo scans run only where a militia building exists;
  the four dark ports scan nothing.
- Every NPC hull broadcasts — "Broadcast: <id> - <faction>" opens
  the hail window; ``identity.npc_identity`` is the one read, and
  None means silent.

### The discovery doors (SETTLED 16's first authored instances)

1. **The dock (primary).** Landing at a ``dark_berth`` port logs
   "This port didn't verify any credentials." (user verbatim) on
   EVERY landing — the militia-scan cadence — and fires the dock
   trigger once, idempotent. Data-driven off the PlanetSpec flag: a
   future dark port joins automatically, no special case.
2. **The silent hail.** Some pirate spawns fly dark this run: a
   spawn-time INIT_SEED derivation (SETTLED 7 — deterministic,
   CONTINUE-stable, reroll-legal) marks an authored share of pirate
   spawns with a guaranteed minimum live (SETTLED 14 — the chain
   cannot be seed-blocked). A dark hull broadcasts nothing: the
   broadcast line is simply absent. Hailing one fires the hail
   trigger.
3. **The pad.** Pirate-boarding and derelict loot can carry a pad
   that teaches the opener (SETTLED 19 — knowledge is the item;
   nothing held, nothing sellable).

All three doors deliver tier 1 through the hearing idiom (readout
modal + verbatim ledger); the keyring is idempotent about which came
first. No tier is askable at spawn.

### The tiers — one of every delivery vector; the template chain

| tier | id | content | delivery vector |
|---|---|---|---|
| 1 | ``dark_berth_1`` | the observation | dock / hail / pad triggers |
| 2 | ``dark_berth_2`` | the four ports + the ships that use them | seeded city carriers (SETTLED 15) |
| 3 | ``dark_berth_3`` | testimony from someone living dark | the hail trigger (requires tier 2) |
| 4 | ``dark_berth_4`` | the name, the place, the passphrase | dealer exclusive (SETTLED 17) |

- One event — hailed a dark hull — authors on BOTH tier 1 and
  tier 3: early it is discovery, after tier 2 it is the testimony.
  ``requires`` ordering keeps the sequence honest.
- The pointers are CANONICAL text (SETTLED 18): tier 2 names pirate
  space, tier 3 names the Hush. No per-candidate pointer text is
  needed; witness overrides stay available for voice.
- Values and prices unchanged (1/2/3; exclusive at 4 favor). The
  favor economy, hidden-until-affordable, holder scatter, and
  no-selling-back all stand.
- The payoff is shipped (phase 2) and lives outdoors (user note):
  the fitter stands on Whisper's city map — by the cargo containers
  south-east of the bounty office. PLAYTEST RULING (user,
  2026-09-12, at checklist item 7): "he is always there" —
  knowledge gates the ACCESS, not the existence; the phase-3
  spawn gate is retired. Talking to him plays his intro ("I don't
  know you, take off.") and THE PASSPHRASE — "The Hush sent me."
  — is the response option once tier 4 is heard (the row is
  keyring-gated; before that he is a locked door, correctly read).
  Taking it opens the 2000cr cut-out install. "The Hush" is the
  name of Whisper's bar. The differential feeds back: lawful ports
  then refuse the player's dark hull, and the four ports still
  take it.

### Binding rules

- Topic becomes "dark ports" (user). Ids stay ``dark_berth_*`` —
  save-facing, and settled rulings reference them.
- The dock log fires on every landing (user: "just like the risk of
  militia scan happens every time you land"); the trigger hears
  once.
- Hailing a dark hull is otherwise a normal hail — no new pirate
  behavior, no bespoke dialogue path. Tier 3 arrives as a readout,
  the same idiom as every hearing.
- PROSE GATE: every player-facing string below is a DRAFT for
  discussion. Nothing lands in data until the user approves the
  wording; prose settles before ``/implement-phase 42.3`` runs.

### Prose — SETTLED (user-authored 2026-09-11, verbatim; obvious
typos fixed and flagged in chat)

- topic: ``dark ports``
- Tier 1: "Some ships don't broadcast an ID and some ports don't
  care who you are. How do they disable their transponder? Those
  dark ships and ports don't like to share much. Finding someone to
  speak with will need patience and connections. I should ask
  around." (RE-AUTHORED by the user at the phase-3 playtest,
  2026-09-12 — one line now covers both discovery doors, ships and
  ports, and closes on the ask loop; verbatim)
- Tier 2: "I know of a few ports that don't check your creds...
  Deadfall, Whisper, Ember, and Wolf 359 b come to mind. Lots of
  black-market goods pass through those ports. Obviously, these are
  pirates using them." ("blackmarket" → "black-market")
- Tier 3: "Yeah, I'm not going to broadcast my name to all. They
  track everything! They don't need to know that I frequent Wolf
  359 b. You want to be free too? Ask around on Whisper."
- Tier 4: "I know the guy, yeah. You're giving me good info, I can
  trust you. You can find him right here on Whisper. He hangs
  around by the containers south of the bounty office sometimes.
  Tell him The Hush sent you." ("You've giving" → "You're giving")
- Dock log line: "This port didn't verify any credentials."
- Shady Tech intro: "I don't know you, take off."
- Passphrase response option: "The Hush sent me."

### Phase-3 brief amendments (this section's scope)

- The brief's chain content (derelict candidates, the
  ``line_warned`` instance, the derelict pad — already fallen with
  the one-chain ruling) is replaced by this chain.
- Trigger exemplars: the dock fire site (landing path, gated on
  ``spec.dark_berth``) and the hail fire site (comms, on a
  dark-hull contact).
- New: the dark-hull spawn derivation (INIT_SEED, guaranteed
  minimum) and the broadcast-line suppression that reads it.
- New: the dock credential log line.
- Pad content: the pirate-boarding/derelict pad teaching
  ``dark_berth_1``.
- The vendor move: the fitter's bar seat retires from lal_c's
  ``service_npc_spots``; he is a plain population citizen on the
  city map by the containers (ALWAYS present — playtest ruling
  2026-09-12; the phase-3 gated-spawn machinery is retired). Id
  renamed ``berth_keeper`` → ``shady_tech``; display name "Shady
  Tech". His talk modal is the intro line plus the passphrase
  response option once tier 4 is heard (the row is keyring-gated);
  taking the option opens the 2000cr install
  (``CUTOUT_BROKERS``).
- Playtest checklist: re-authored for the one chain, plus the prose
  read-through item.
- Shift+R: the live-routes readout includes the dark-spawn set.
- Guide: the discovery sentence stands (how-to only, no
  telegraphing).

### Open

- The authored share of dark pirate spawns (guaranteed minimum +
  share; tuned at playtest).
- Confirm tier 3's "broadcast my name to all" is as intended — kept
  verbatim (reads as "to everyone", not a typo for "at all").

## Phases

Build queue — unchecked in order; `/implement-phase 42.<p>` works
top-down. The SETTLED rulings bind every phase; each phase's brief
binds its build.

### Phase 1 — The keyring and the ask loop
- [x] `RumorEntry` catalog + registry (`data/lore/`), chains linked
      inside the catalog
- [x] Rumor prose JSON-single-source (`rumor.*` keys in
      `08_rumors.json`) + data test for missing/orphan keys
- [x] `ctx.known_rumors` + save/load round-trip
- [x] Pure topic resolver (heard ∩ contact's sources, floors
      applied)
- [x] Hearing on the talk host: one Ask Around row opens the
      sub-menu; picking an entry records it verbatim + adds the
      keyring (amended at playtest round 1 — openers moved inside)
- [x] The shared Ask Around sub-menu (city/bar host)
- [x] The verbatim ledger pane in the Q log
- [x] Three authored chains across bar + city sources
- [x] Guide: new Rumors section (ledger + ask-around how-to only)
- [x] Playtest checkpoint (checklist in the brief) — PASSED
      (user, 2026-09-11)

  Implementation brief (1) — APPROVED (refine session 2026-09-10;
  amended per the ADVISE reviewer round, same day — 3 blockers
  folded; user invoked ``/implement-phase 42.1``):

  - **Scope.** Data: `data/lore/__init__.py` — frozen `RumorEntry`
    (id, chain, tier, `requires` tuple of heard ids, text keys,
    `sources` tuple of `(npc_id, faction | None,
    min_standing | None, trait | None)` in the shipped
    `talk_gate` shape — a floor reads the NAMED faction's
    resolved standing) + `_BY_ID` / `find_rumor(id)`;
    `data/lore/chains.py` authors the first three chains. Prose:
    `data/text/08_rumors.json` — `rumor.<id>.text`,
    `rumor.<id>.witness.<npc_id>` + a fallback key; JSON
    single-source like `step.*` (rows carry keys, never prose);
    the catalog-integrity data test fails on missing keys and
    flags orphans (quest_lint style, in tests/). State:
    `ctx.known_rumors: list[str]` (heard order) on `GameContext`,
    round-tripped in `saveload.py` both directions — saveload.py
    sits at exactly 1000/1000, so build step (2) carries the
    forced same-commit refactor: the restore side splits into
    per-domain `_restore_*` helpers mirroring the serialize
    side's `_identity_fields` / `_progression_fields` (headroom
    for phase 2's `rumor_favor` too). Code: a new
    `rumor.py` domain module — pure resolvers (`askable_topics`,
    `witness_text`) + the `hear` mutation wrapper + the shared
    sub-menu frames builder. Host: `npc.py` — rumor rows beside
    `_quest_rows` in the existing talk modal; an "Ask Around"
    entry opens the sub-menu in the sell-menu idiom (stays open
    until ESC); no parallel modal. Ledger: a true Rumors pane
    inside the Q-log modal (ruled at the ADVISE round) — scope is
    BOTH files on the live path: `pygame_quest_log.py` (the
    capture loop gains the pane switch; the read-only pane
    renders) and `menus/_quest_log.py` (pane content); verbatim
    heard text, no objectives. Guide: one new section in
    `data/guide/__init__.py` (ledger + ask-around only), plus the
    `rumor.*` namespace documented in text.py's key-map docstring
    and `data/text/README.md`.
  - **Build order.** (1) `RumorEntry` + registry + the three
    chains + JSON + the key-coverage test; (2)
    `ctx.known_rumors` + saveload round-trip + tests; (3) pure
    resolvers + tests; (4) talk-host hearing + Ask Around
    sub-menu + tests; (5) ledger pane + tests; (6) guide section;
    (7) playtest checkpoint.
  - **Binding rulings.** SETTLED 1–5 and 8. The quest machinery
    stays untouched; prose JSON-single-source; the keyring never
    gates (sources carry the floors, read off the resolved
    sheet); heard-topics-only sub-menu, no greyed rows; verbatim
    ledger with no interpretation; floors follow the face
    (resolved sheet), so a worn ID clears a floor; DARK reads
    neutral (no special case); hearing is presented as a readout
    modal (the quest-readout idiom — completion-class state
    changes are modals, never log lines).
  - **Required tests.** Catalog integrity (requires resolvable;
    sources are real npc ids with valid factions; every text key
    present; no orphans; every `rumor.*` key lives in
    `08_rumors.json` exactly once — the merged overlay lets a
    later file silently win); saveload round-trip (heard order
    preserved; New Game clears); resolver floors (below-floor
    source hidden; trait gate honored; empty when nothing
    askable; SPOOFED: a worn sheet clears a floor the true sheet
    doesn't — pins the one-read resolver; DARK: reads neutral —
    a floored source refuses, a floorless source serves);
    `hear` idempotent (re-hear is a no-op, no duplicate ledger
    entry); talk-modal rows (source shows the rumor row pre-hear;
    non-source never does; Ask Around appears only post-hear);
    ledger pane = verbatim text in heard order.
  - **Carried to later phases.** `askable_topics` takes the
    routing decision as an explicit pure input from day one so
    phase 3 composes instead of rewrites; the phase-2 brief pins
    the earned-set home (`rumor_favor` values become
    `{favor, earned}` vs a third ctx field); the phase-3 brief
    flags the mid-run wrinkle (an exclusive earned at a phase-2
    authored dealer may compute to a different dealer once
    routing lands — ledgers survive keyed by dealer, the
    once-per-earned set can disagree); phase close amends
    SYSTEMS.md (guide section count, Q-log entries).
  - **Stop point.** NO favor (no offer/ask-spend rows, no
    `rumor_favor`), no comms host, no seed routing (all authored
    chains live in phase 1), no finds/loot-that-teaches, no lies,
    no quest-step or option-unlock integration, no doc-43
    content.
  - **Playtest checkpoint** (numbered; SPACEHACK_DEV run):
    1. Talk to the authored barkeep: the rumor row appears; take
       it — the ledger (Q → Rumors) records the text verbatim.
    2. Re-open the talk: Ask Around offers the heard topic; ask
       it — tier-2 text arrives; the new entry lands in the
       ledger.
    3. Walk the chain to its final tier; the ledger shows every
       entry in heard order.
    4. Witness variants: the chain's other-city source opens its
       witness text; a non-source NPC shows no Ask Around row at
       all.
    5. Attitude floor: below the floor the floored source's topic
       is absent; wear a face that clears it (TAB) and the topic
       appears — same physical NPC. Go dark (D): the floored
       source refuses (dark reads neutral); the floorless source
       still serves.
    7. Regression: quest rows, purchase rows (scrub/cutout/rig),
       missions, the sell sub-menu, and plain flavor all behave
       exactly as before on the same modal.
    7. Save → quit → Continue: ledger + keyring intact; asking
       resumes where it left off. New Game: keyring empty.
  8. Guide diff: the new Rumors section quoted (before/after) —
     ledger + ask-around only, no chain telegraphing.

### Playtest round 1 (2026-09-11) — presentation ruling: shared tabs

The bespoke TAB-toggle (pane state threaded inside
``pygame_quest_log``, title swap) replaced by the shared treatment:
``QuestFrame`` carries ``tabs``/``active_tab`` mirroring
``ScreenFrame``; the tab bar is pygame_screen's ``draw_tab_bar``
(extracted from its header painter — one drawing implementation);
``_handle_key`` returns the shared ``TAB``/``SHIFT_TAB`` outcomes and
``_advance_quest_log`` flips the sheet in the host loop (the
character screen's ``_advance_character_screen`` shape). Checklist
item 2's ledger interaction is unchanged in kind: Q opens, TAB (or
SHIFT-TAB) flips between the QUESTS and RUMORS tab bar sheets.

Follow-up (same round): the fixed-origin tab bar clipped the Q
screen's title and divider (the two panels start at different y).
``draw_tab_bar`` now takes its origin y — pygame_screen passes 72 as
before, the Q log lays the bar below its own rule — and the header
renames to "LOGS" (user: "Let's change that title to just 'Logs'
since it stays up there no matter which tab you're on.").

Second ruling (same round): the main-menu "Ask about X" opener rows
MERGE into the Ask Around sub-menu — the main talk menu carries one
"Ask around" row whenever the contact holds anything (unheard opener
OR heard extension), and the sub-menu lists both kinds.
``hearing_rows`` and the RUMOR: action are retired;
``askable_topics`` is the one ask surface. Supersedes review-round
1's opener/extension split (its double-row concern dissolves — one
menu cannot double-list). Checklist items 1–2 change shape: no rumor
rows next to "View available work" any more.

Playtest complete (user, 2026-09-11) — the amended checklist passed;
phase 1 closed.

## Pre-implementation audit — phase 1 (2026-09-10)

1. **Existing classes / modules to extend or reuse.**
   - `npc.py` row machinery: `_npc_pygame_items` builds every row;
     `QUEST:`/`DELIVER:` prefix parsing in `_map_pygame_npc_result`;
     handler dispatch in `_resolve_talk_result`; the sell sub-menu
     (`_run_sell_menu` / `_handle_sell_ids`) is the stays-open-until-
     ESC loop the Ask Around sub-menu mirrors. Rumor rows ride as
     `RUMOR:<id>` items + one `ASKAROUND` item — no parallel modal.
   - Readout idiom: `pygame_story.dismiss` (the `_show_pygame_dismiss`
     shape) presents heard text; `rumor.py` owns its thin wrapper.
   - Floors: the shipped `talk_gate` tuple shape `(faction,
     min_standing, line)` is the gate shape — source floors use
     `(npc_id, faction | None, min_standing | None, trait | None)`
     with the same `standing >= min_standing` comparison over
     `identity.effective_reputation(ctx)` (dark → {} → neutral).
   - Save/load: per-domain field families (`_identity_fields` /
     `_progression_fields` + `_restore_*`) — the lore fields join as
     `_lore_fields` / `_restore_lore_fields`.
   - Q pane: the capture architecture is authoritative —
     `menus/_quest_log.render_quest_log` paints, `pygame_quest_log`
     captures + handles keys; the pane rides both (render grows a
     `pane` param; `_handle_key` grows TAB; hint strings must keep
     the `_HINT_PREFIXES` startswith contract).
   - Catalogs: `data/missions/__init__.py` is the spec-in-`__init__`,
     rows-in-sibling precedent; `data/lore/` mirrors it. Guide
     sections are `GuideSection(title, body)` tuples. NPC ids
     resolve via `data.npcs.find_npc`.
2. **Duplication hotspots.**
   - Floor comparison vs `npc._talk_refusal` (same `>=` over the
     same resolver) — one comparison idiom, reused, not re-derived.
   - Sub-menu loop vs `_run_sell_menu` — two stays-open loops;
     extract one `_run_choice_submenu(ctx, *, title, body, items,
     caption)` in `npc.py` and put both on it.
   - Rumor text resolution — the readout AND the ledger must both go
     through `rumor.py`'s resolvers; hosts never call `text.get`
     with `rumor.*` keys directly.
3. **DRY strategy.** As above: one gate shape, one extracted
   sub-menu runner, one text resolver module, `routing` as an
   explicit pure predicate input (default `routing_all`) so phase 3
   composes instead of rewrites.
4. **Ratchet payment (saveload.py at exactly 1000/1000).** The
   ground save/load family (`_ground_fields`, `_ground_equipment_
   from_dict`, `_safe_ground_int`, `_parse_equipped_ground_armor`,
   `_restore_ground_stats`, `_restore_ground_hp`,
   `_restore_ground_fields`, `_parse_ground_item_stacks`,
   `_parse_equipped_ground_weapons` — all internal to saveload, no
   external importers) moves to a cohesive sibling
   `saveload_ground.py` (the navigation-split precedent);
   `ground_equipment.py` can't take it (929 lines). saveload then
   adds the lore twins with real headroom. Refactor commits before
   the field commit; behavior-preserving.
5. **Pinned consequence — ledger text.** `ctx.known_rumors` stores
   rumor ids in heard order; the pane renders each entry's canonical
   `rumor.<id>.text`. The `witness.<npc_id>` override is
   conversation-delivery flavor in the readout modal only — the
   notebook keeps one line per entry, so no per-hearing text twin.
6. **Pinned consequence — multiple sources.** Tier-1 entries author
   two sources where the knowledge genuinely circulates (bar + a
   second teller), exercising the fallback/override paths with live
   data instead of dead keys.

## Pre-implementation audit — phase 2 (2026-09-11)

1. **Existing classes / modules to extend or reuse.**
   - `RumorEntry` (`data/lore/__init__.py`) gains `value: int = 0` —
     a frozen-row edit; `data/lore/dealers.py` mirrors the catalog's
     registry shape in one self-contained sibling module
     (`DealerSpec`, `DEALERS`, `find_dealer`, `is_dealer`).
   - `rumor.py`: pure resolvers beside `askable_topics`
     (`favor_for`, `offerable_rumors`, `exclusive_offers`) and
     mutation wrappers beside `hear` (`offer_rumor`, `buy_exclusive`)
     — the same pure/mutation split; hosts keep reading through the
     rumor facade.
   - Host: `npc.py` `_handle_ask_around` gains dealer rows inside its
     existing stays-open loop, rebuilt per pass with the
     `_run_sell_menu` idiom so the Favor line stays live;
     `_run_choice_submenu` remains the one sub-menu runner (it gains
     the `max(1, len(items))` frames guard `_npc_pygame_frames`
     already has, so a balance-only dealer pass renders);
     `_offers_rumors` extends with `is_dealer`; a buy presents
     through the existing `_show_rumor_readout`.
   - State: `ctx.rumor_favor` beside `known_rumors`
     (`game_context.py`); `_lore_fields` / `_restore_lore_fields`
     (saveload.py at 874/1000 — the phase-1 split left the
     headroom); New Game clears via fresh `GameContext` (the
     `known_rumors` precedent — no reset block needed).
   - Vendor: the `service_npc_spots` seater
     (`city_interiors._seat_service_npcs` — the
     ember_tech/ross_b precedent) seats a new single-row NPC
     (`data/npcs/guilds.py`) in lal_c's bar interior;
     `identity.CUTOUT_BROKERS` gains him at 2000; a knowledge-gate
     table beside it is read in `npc._priced_rows` so his rows
     exist only while `dark_berth_4` is heard.
   - Guide: the Rumors section (`data/guide/__init__.py`) gains the
     favor paragraph; the vendor stays untelegraphed.

2. **Duplication hotspots.**
   - Affordability/spend arithmetic vs the identity purchase
     wrappers — ALL ledger arithmetic lives in `rumor.py`'s
     wrappers; hosts never touch `rumor_favor` directly.
   - Row construction: hear/Sell/Buy rows build in one items
     builder; no second sub-menu loop, no second readout path.
   - The earned-set check ("already bought from you") lives inside
     `offerable_rumors` — never re-derived in the host.
   - `rumor_favor` joins the existing `_lore_fields` family — no
     parallel save-field family.

3. **DRY strategy.** One ledger accessor pair (`favor_for` + the
   earned read), one sub-menu items builder, one readout modal, and
   catalog-test extensions cover `value` + the exclusive shape once.

4. **Pinned consequences.**
   - Dealers always open the sub-menu (ruling 10): a balance-only
     pass is real content, so `_run_choice_submenu` gains the
     `max(1, ·)` frames guard; non-dealers keep the
     nothing-askable-closes rule.
   - `dark_berth_4` breaks the catalog test's
     every-entry-needs-sources assertion by design — the test gains
     the exclusive-held exception.
   - A buy presents canonical `entry_text` — bought knowledge has
     one text; no witness key is authored for `dark_berth_4`.
   - The Buy action string carries its price (`BUY:<id>:<price>`) so
     the holding a row came from stays the single source at pick
     time, not just render time — the phase-3 routing seam holds.

5. **Ratchet.** Every touched module sits well under the limits
   (npc 580, saveload 874, game_context 427, rumor 151, identity
   456); the grandfathered backlog (comms.py) is untouched.

### Phase 2 — The favor exchange
- [x] Dealer spec (`data/lore/`): exclusives + prices; rumor rows
      gain their offer values (ruling 10)
- [x] `ctx.rumor_favor` per-dealer ledgers + save/load
- [x] Offer/ask rows in the shared sub-menu (dealers only)
- [x] Exclusive tier gated on favor; once-per-(rumor, dealer)
      earning
- [x] An authored option-unlock payoff (an exclusive that changes
      an interaction)
- [x] Playtest checkpoint (passed — user, 2026-09-11; round-1
      rulings above: no-selling-back + the Shift+B dev instrument)

  Implementation brief (2) — APPROVED (refine session 2026-09-11):

  - **Scope.** Data: `RumorEntry` gains `value: int = 0` (the offer
    value — a number, not prose; the catalog stays structural). New
    `data/lore/dealers.py`: frozen `DealerSpec(dealer_npc_id,
    exclusives)` + `DEALERS` / `is_dealer` — rows for `barkeep`,
    `wolf_barkeep`, `research_officer` (ruling 9); `wolf_barkeep`
    holds `(("dark_berth_4", 4),)`. `chains.py` gains `dark_berth_4`
    (tier 4, requires `dark_berth_3`, empty sources — never
    free-asks, value 2). Prose keys `rumor.dark_berth_4.{topic,
    text}` (no witness — bought knowledge has one canonical text).
    Calibration authored in data, tunable: tier 1/2/3 values 1/2/3.
    State: `ctx.rumor_favor: dict[str, dict]` beside `known_rumors`
    on `GameContext`; round-tripped in `_lore_fields` /
    `_restore_lore_fields` (the phase-1 split left headroom); New
    Game clears. Resolvers (`rumor.py`, pure): `is_dealer`,
    `favor_for`, `offerable_rumors` (heard ∧ not earned at this
    dealer ∧ value > 0), `exclusive_offers` (requires met ∧
    unheard ∧ favor ≥ price — the hidden-until-affordable gate);
    mutation wrappers `offer_rumor` (+value, earned-record,
    idempotent) and `buy_exclusive` (floor-guarded spend, then
    `hear`). Exclusive holding reads through the spec as an
    explicit pure input — the phase-3 routing seam. Host
    (`npc.py`): `_handle_ask_around` gains dealer rows — offer rows
    labeled `Sell: <topic>` (caption "Earn N favor."), exclusive
    rows by topic (caption "Costs N favor."); the body line becomes
    `Favor: N` for dealers, kept live by the loop's per-iteration
    recompute (sell-menu idiom — no per-transaction modal); a buy
    presents the exclusive's text via the existing readout modal.
    `_offers_rumors` extends to `is_dealer`. Non-dealer sub-menus
    unchanged. Vendor: one new single-seat NPC authored in
    `data/npcs/guilds.py`, seated in Whisper's bar interior (lal_c
    placement) — `CUTOUT_BROKERS` gains him at 2000; the knowledge
    gate is a small data table read in `npc._priced_rows` (rows
    exist only when `dark_berth_4` is heard); `ember_tech`'s rows
    untouched. Guide: the Rumors section gains the favor paragraph
    (offers earn, exclusives cost, balance in the ask menu); the
    vendor stays untelegraphed.
  - **Build order.** (1) value field + DealerSpec + `dark_berth_4` +
    prose + catalog-test extensions; (2) `rumor_favor` + round-trip
    + New Game + tests; (3) resolvers + wrappers + tests; (4)
    dealer rows + Favor line + `_offers_rumors` + tests; (5)
    vendor + gate + tests; (6) guide paragraph; (7) playtest
    checkpoint.
  - **Binding rulings.** SETTLED 6, 8 (as amended), 9–13. Favor is
    ID-agnostic (floors follow the face, favor follows the person);
    the keyring never gates; floor at zero; once per
    (rumor, dealer); quest machinery untouched; no faction-rep
    coupling.
  - **Required tests.** Dealer-spec integrity (real npc ids,
    exclusives reference real rumor ids, positive ints); catalog
    test covers `value` + `dark_berth_4` keys; favor round-trip
    (save/load, New Game, earned sets survive); offer (+value once
    per (rumor, dealer); unheard unofferable; sold row vanishes);
    buy (never below zero; requires-unmet hides the row even when
    rich; hidden until affordable; hear-on-buy); host (dealer rows
    + Favor line; non-dealer unchanged); vendor gate (rows absent
    without the exclusive, present with it, ember_tech unaffected);
    routing seam (holding as pure input — a fake predicate
    composes, the phase-1 `routing_all` precedent).
  - **Stop point.** No comms host, no seed routing (holdings static
    this phase), no finds/loot-that-teaches, no lies, no chains
    beyond `dark_berth_4`, no favor display outside the ask
    sub-menu, no doc-39 content (no Commandant, no crossing
    payment), no SYSTEMS.md close work.
  - **Playtest checkpoint** (numbered; SPACEHACK_DEV run):
    1. Walk the dark_berth chain to tier 3 (wolf_barkeep →
       deadfall_scrubber → ember_tech); each entry lands in the
       ledger verbatim.
    2. At a dealer: heard-but-unsold rumors they don't already know
       show `Sell:` rows captioned +N (rumors they told you show no
       Sell row — no selling back, round-1 ruling); selling updates
       the Favor line in-menu; the sold row vanishes; favor
       unchanged on re-check.
    3. Two dealers, two books: sell the same rumor to wolf_barkeep
       and research_officer — each counts it separately.
    4. Requires gate: Favor ≥ 4 from OTHER chains but `dark_berth_3`
       unheard — no Buy row at wolf_barkeep; hear tier 3 and the
       row appears ("Costs 4 favor.").
    5. Affordability: fresh book (Favor: 0) — no Buy row; sell up
       to 4 — the row appears; buy — the readout presents the berth
       text, favor drops to 0, the ledger records it verbatim;
       save/quit/Continue preserves book + earned sets + keyring;
       New Game clears all.
    6. Payoff: before the exclusive, no cut-out rows at Whisper;
       after, the berth keeper offers the cut-out (2000cr) and it
       installs; ember_tech unchanged throughout. (Dev saves
       PRE-INSTALL the cut-out — Shift+B revokes/restores it so the
       row can show; found at playtest round 1, item first failed
       because the owner's storefront correctly hides.)
    7. Regression: non-dealers (deadfall_scrubber, blockade_officer)
       show no Sell/Buy rows and no Favor line; quest/purchase/
       ID-buyer rows as before; Q → Rumors unchanged.
    8. Guide diff: the favor paragraph quoted before/after; no
       vendor or chain telegraphing.

### Playtest round 1, phase 2 (2026-09-11) — ruling: no selling back

User: "I shouldn't be able to sell a rumor back to the npc I just
got a rumor from." Amends ruling 10's uniform buy side:
``offerable_rumors`` — and the ``offer_rumor`` wrapper, self-
defending like ``buy_exclusive`` — excludes any heard entry the
dealer is an authored source of. The rule reads the CATALOG's
sources; who told you is not tracked on the keyring, and co-tellers
know the rumor too (heard from the wolf or not, deadfall_scrubber
won't buy dark_berth_1). Tiers a dealer doesn't hold stay buyable —
the wolf buys your thin-month entries; research_officer, no
authored sources, buys anything heard. Checklist item 2 amended
below.

Playtest complete (user, 2026-09-11) — the amended checklist passed
(sell-back fix verified in play; item 6 needed the Shift+B dev
toggle: dev saves pre-install the cut-out, so the owner's empty
storefront is correct). Phase 2 closed; SYSTEMS.md rumors entry
amended with the favor exchange.

## Pre-implementation audit — phase 3 (2026-09-12)

1. **Existing classes / modules to extend or reuse.**
   - Derivation substrate: ``engine.seeded_rng(seed, *parts)`` +
     ``INIT_SEED`` / ``set_init_seed`` — the city-NPC-route
     precedent; ``init_seed`` already round-trips
     (``saveload data["init_seed"]``), so routing is
     Continue-stable with nothing new serialized.
   - Dark hulls: ``npc_ships._spawn_table_groups`` /
     ``_spawn_one_type`` spawn the ambient pirate groups;
     ``rumor_routing.choose_dark_groups(system_id, movement_ids)``
     (count ``max(1, groups // DARK_GROUP_SHARE)``, seeded sample)
     picks the dark set at batch time; ``_make_npc_entity`` stamps
     ``entity.flies_dark``. ``ProceduralSpawn`` (game_context)
     gains ``flies_dark: bool = False``;
     ``saveload_maps._add_procedural_npcs`` restores it — the
     spawn/load twins both tested ([[parallel-paths-drift]]).
   - Broadcast: ``identity.npc_identity`` returns ``None`` for
     ``flies_dark`` hulls — ``_contact_broadcast_line`` is already
     absent for ``None`` (zero new presentation; wordless read).
   - Comms fire site: ``_run_interaction_modal`` (comms.py) —
     ``fire_trigger(ctx, "dark_hail")`` before the hail frames when
     the contact flies dark; readout first, then the normal hail.
   - Dock fire site: ``game_interactions._resolve_planet_land`` —
     after the dark-dock refusal gate, ``spec.dark_berth`` logs the
     credential line EVERY landing + fires ``dock_dark_port``
     (idempotent). Module at 961/1000; ~6 lines, headroom holds.
   - Pads: ``combat/_actions._spawn_loot_drops`` is the shared
     ship+ground kill-loot path — ``loot.maybe_spawn_pad(ctx, map,
     pos, enemy_spec.id)`` rides beside it (both callers), spawning
     only while the entry is unheard;
     ``loot._open_single_loot_pickup`` gains the ``{"teaches": id}``
     branch — hear + present + entity removed, nothing to hold.
   - Host: ``npc._handle_ask_around`` derives the live map once per
     pass (``ctx.current_city_id`` scopes delivery);
     ``_show_rumor_readout`` hoists to ``rumor.present_hearing`` —
     hosts, triggers, and pads present through one path.
   - Vendor move: ``CityNpc`` gains ``requires_rumor`` —
     ``place_city_npcs`` skips unheard templates (ctx threaded from
     ``city_builder._finalize_city``);
     ``city_interiors.exit_city_interior`` runs the ensure pass
     (all three dealers seat inside interiors — the exit is the
     one same-visit transition). ``CUTOUT_BROKERS`` berth_keeper →
     shady_tech @2000; ``KNOWLEDGE_GATES`` retires (the spawn is
     the gate); ``_append_priced_items`` reads a per-NPC row-label
     table — the passphrase row.
   - Anchor: lal_c's bounty office x73-87/y52-62 (door 80,61); the
     lower east loop is walkable at y≈65 (population anchors
     (60,65) and (91,65) bracket it); the final anchor is verified
     walkable by a data test over the built city.
2. **Duplication hotspots.** The dark stamp (spawn) vs restore
   (load) — one field, two writers, both tested; the readout — one
   wrapper after the hoist; the city spawn gate — place + ensure
   share the predicate; the pad check — one helper beside both
   kill paths.
3. **DRY strategy.** One routing module (``rumor_routing.py``); the
   live map as one explicit input shape through resolvers + host;
   ``fire_trigger`` as the single hearing door for dock / hail /
   pad.
4. **Ratchet.** game_interactions 961 (+6, holds), npc_ships 955
   (+~8, holds), game_loop 925 (+~8, holds), comms 624,
   city_builder 195 — all under; no grandfathered module is
   touched.
5. **Pinned consequences.**
   - The source shape ``(npc, planet, faction, floor, trait)``
     re-pins every live-data test; the fixture registry mirrors it.
   - t1/t3 sources are EMPTY (trigger-delivered) and t4 EMPTY
     (exclusive) — the catalog test's empty-sources exception
     widens to trigger-or-exclusive entries; the ≥1-live-route
     assertion covers source-carried entries only.
   - t2 is the only source-carried tier: the seeded city carriers,
     planet-scoped candidates with authored width (verified seats:
     wolf_barkeep→wolf_b, deadfall_scrubber→lal_b, ember_tech→
     ross_b, research_officer→mercury/procyon_c/sirius_station/
     ac_planet_2, barkeep→anywhere-seat; exact pool reviewed at
     playtest).
   - ``DEALERS``' static exclusives retire into
     ``EXCLUSIVE_CANDIDATES`` (all three dealers @4); the phase-2
     wrinkle stands (earned sets may disagree with the live
     holder; no migration).
   - Deviation: the brief's Shift+R is TAKEN (dungeon fog,
     game_loop) — the routing readout takes **Shift+N**; flagged
     on the checklist.
   - New player-facing string beyond the settled prose: the pad's
     loot label "Data Pad" — carried on the checklist for approval
     (prose gate).
   - The t4 sell-back edge stays unruled (2.5 Open) — net-negative
     to the player, not blocked this phase.

### Phase 3 — Seed routing + discovery (re-scoped 2026-09-11)
- [x] Derived routing module (pure INIT_SEED derivations):
      live-candidate subsets per entry (npc+planet candidates,
      authored width — SETTLED 15), exclusive holder picks
      (SETTLED 17)
- [x] Authored discovery triggers: openers enter via trigger / pad
      / carrier (SETTLED 16); the phase-1 chains re-authored so no
      chain is askable at spawn
- [x] Loot that teaches: pads on boarded-ship + derelict loot,
      teach-on-pickup (SETTLED 19)
- [x] Determinism tests (same INIT_SEED → same routing; reroll →
      different legal routing; round-trip stability)
- [x] Playtest checkpoint — PASSED (user, 2026-09-12)

  LANDED 2026-09-12 (builds 51a4846 → 7697f43, seven steps + the
  review round; gate green ~2260 tests). Build deviations from the
  brief, all flagged in the audit or the review round: the
  instrument key is **Shift+N** (the brief's Shift+R is taken by
  dungeon-fog reveal); the review round fixed the Continue-rebuild
  gap (a saved city-NPC position row is the gate proof) and put the
  tick spawner on the same dark share (a seeded per-group coin);
  the PLAYTEST RULING at item 7 then retired the gated spawn
  entirely — the shady tech is a plain always-present citizen and
  the passphrase ROW carries the keyring gate.

  **Re-authored playtest checkpoint** (numbered; SPACEHACK_DEV run;
  supersedes the brief's checklist, which still names the retired
  chains):
  1. Fresh dev run: land at the starting city — NO rumor topics
     anywhere and no Ask around row on any non-dealer (the chain is
     not askable at spawn); a dealer's Ask around opens with
     Favor: 0 and no rows.
  2. Shift+N: the routing readout lists the t2 carrier planets this
     run + the live exclusive holder + any dark hulls in-system.
     Dock at Deadfall (lal_b): the log shows "This port didn't
     verify any credentials." on EVERY landing (re-land to see it
     repeat), and the first landing delivers t1 as a readout; the
     ledger (Q → TAB) records it verbatim; a re-landing does not
     duplicate.
  3. Travel to a live t2 carrier planet (Shift+N names them); Ask
     Around delivers t2 ("I know of a few ports that don't check
     your creds..."); a carrier on a NON-live pair or the wrong
     planet shows nothing.
  4. The silent hail: find a dark hull (Shift+N names live ones —
     the hail window opens with NO Broadcast line); hailing it
     delivers t3 as a readout (the pirate's testimony). Honest
     hulls still broadcast.
  5. Pads: kill a pirate raider — a "Data Pad" drops with the loot
     ONLY while t1 is unheard (dock first at a lawful port run to
     check: kill one first, take the pad, then no more pads);
     pickup teaches t1 (readout + ledger), nothing enters the
     hold, the pad is consumed.
  6. Holder scatter: Shift+N names the live holder of dark_berth_4;
     sell t1 (1) + t3 (3) to any dealer — t2 is every dealer's own
     telling and never sells (no-selling-back); at 4 favor the Buy
     row appears at the live holder only ("Costs 4 favor."); buy —
     the readout names the man by the containers.
  7. The payoff: on Whisper, the Shady Tech is ALWAYS by the
     containers south-east of the bounty office (check pre-t4 too:
     he tells you to take off, no install row — a locked door);
     after the buy his talk modal is "I don't know you, take off."
     with the install row "The Hush sent me." — take it: 2000cr,
     cut-out installed (Shift+B revokes for re-tests).
  8. Determinism: save → quit → Continue — Shift+N shows identical
     routing; the Shady Tech survives the reload if spawned; Shift+S
     reroll → different legal routing (items 2-3 repeat against the
     new routes).
  9. Regression: phase-1/2 behaviors (Q tabs, favor economy,
     hidden-until-affordable, quest/purchase/ID rows, the sell
     sub-menu); lawful ports still refuse a DARK hull; ember_tech
     still sells the 2500cr cut-out.
  10. Prose read-through (prose gate): all chain text is the
      user's verbatim 2.5 wording; TWO strings landed flagged for
      approval: the pad's loot label/name **"Data Pad"** and the
      guide's discovery sentence (item 11) — approve or red-line.
  11. Guide diff (before/after quoted at handoff): the Rumors
      section's first paragraph gained one sentence — "New
      subjects reach you in play - by what you see, what you find -
      not only by asking." No chain telegraphing.

### Playtest round (2026-09-12) — PASSED; four findings, all landed

1. **Jump-time crash** (e31ae48): the dark stamp grew the spawn
   rows to 4-tuples and ``_register_table_batch`` still unpacked 3 —
   a real-path ``spawn_npcs`` regression test now pins the batch
   shape (no test had covered it).
2. **The shady tech is ALWAYS there** (32eab39, the item-7 ruling):
   knowledge gates the passphrase row, not his existence; the
   gated-spawn machinery retired in full (see 2.5's payoff bullet).
3. **Q-screen polish** (5ed1cef, 990514d): the rumors pane's first
   line shares the quests pane's row (no TAB jump); the ledger
   strips trailing blanks AFTER the hint split (the phantom
   scrollbar); the quests-tab empty footer matches the tab idiom
   ("TAB rumors" / "ESC close").
4. **T1 re-authored** (8a03475, user verbatim): one line now covers
   both discovery doors — ships and ports — and closes on the ask
   loop; see the Prose section.

  Implementation brief (3) — PROPOSED (refine session 2026-09-11):

  AMENDED (2026-09-11, phase 2.5): chain content = the dark-ports
  chain (see Phase 2.5 above) — the four tiers' sources/triggers/
  pads, the dock + hail fire sites, the dark-hull spawn derivation,
  the dock credential log line, and the vendor move to the
  container-side spawn with the passphrase gate. The brief's
  derelict candidates, the ``line_warned`` instance, the derelict
  pad content, and wolf_barkeep's static exclusive entry fall.
  Everything else stands: routing module, resolver seam, the
  EXCLUSIVE_CANDIDATES table, determinism tests, Shift+R, guide
  sentence, and the checklist's shape (items re-authored for the
  one chain + the prose read-through).

  - **Scope.** Data: `RumorEntry.sources` become planet-scoped
    candidates — `(npc_id, planet, faction | None, min_standing |
    None, trait | None)` (uniform extension of the talk-gate shape;
    no legacy unscoped form) — plus two frozen fields: `picks:
    int | None = None` (authored width — the derivation picks this
    many live candidates per run; None = every candidate live) and
    `triggers: tuple[str, ...] = ()` (authored discovery events).
    `data/lore/chains.py` re-authors all three chains (SETTLED 16):
    openers narrow (`picks=1` — e.g. `derelict_line_1` candidates
    `(("barkeep", "cygni_b"), ("depot_attendant", "groom_b"))`;
    `dark_berth_1` `(("wolf_barkeep", "wolf_b"),
    ("deadfall_scrubber", "lal_b"))`; verified seats: `ember_tech`
    → ross_b, `research_officer` → mercury/procyon_c/
    sirius_station/ac_planet_2; exact candidate planets are
    content, reviewed at playtest); mid-chain witness pointer text
    added where a step narrows (SETTLED 18;
    `data/text/08_rumors.json`); `thin_month_1` gains the
    `line_warned` trigger (the founding example: warned by the
    Line = discovered). New `data/lore/finds.py`: the pad table —
    authored `(enemy_id, taught_rumor_id)` rows for boarded-ship /
    derelict loot (SETTLED 19; content proposal: a derelict pad
    teaching `derelict_line_1`, a pirate-boarding pad teaching
    `dark_berth_1`). `data/lore/dealers.py` gains the authored
    candidate table `EXCLUSIVE_CANDIDATES` (rumor_id →
    `((dealer_id, price), ...)`; content: `dark_berth_4` → all
    three dealers at price 4; wolf_barkeep's static exclusives
    entry retires into it). New `rumor_routing.py`: the pure
    INIT_SEED derivations — `live_routes(seed)` → per-entry live
    candidate sets (`seeded_rng(seed, "rumor_route", entry.id)`,
    picks ≥ 1) and `live_holdings(seed)` → per-dealer exclusive
    holdings folded from the candidate table (SETTLED 17).
    `rumor.py`: `askable_topics` / `_delivers` take the live-route
    map as an explicit pure input (the phase-1 `routing` entry-gate
    predicate retires); `exclusive_offers` holdings come from
    `live_holdings`; new `fire_trigger(ctx, event_id)` — hears
    every entry authored with that trigger, idempotent, readout on
    each new hearing (the readout wrapper hoists from `npc.py` to
    `rumor.py` so hosts and loot present through the one path).
    Host: `npc.py` `_handle_ask_around` resolves the current
    planet id (the `current_city_id` slot) and derives live routes
    once per sub-menu pass. Loot: `loot.py` `_apply_loot_pickup`
    gains the `teaches` branch — hear + readout + entity removed,
    nothing to the hold; pad loot entities spawn (in the
    boarded/derelict loot construction) only while their entry is
    unheard at spawn time. Trigger fire site: the Line's warning
    emission (the doc-41 hail path) calls
    `fire_trigger(ctx, "line_warned")` — the build session's audit
    locates the exact site; if it sits in grandfathered code the
    ratchet is paid in-commit. Dev instrument: Shift+R logs the
    run's live routing (carriers per chain + the live exclusive
    holder). Guide: the Rumors section gains a discovery sentence
    (chains reach you by asking around, finds, and events; no
    chain list, no telegraphing).
  - **Build order.** (1) source-shape fields + chain re-authoring
    + pointer text + catalog-test extensions; (2) `rumor_routing.py`
    + tests; (3) resolver seam (live map, `live_holdings`, holder
    scatter) + host wiring + tests; (4) trigger machinery +
    `line_warned` fire site + tests; (5) pads (`finds.py`, loot
    branch, spawn-time unheard check) + tests; (6) Shift+R
    instrument; (7) guide sentence; (8) playtest checkpoint.
  - **Binding rulings.** SETTLED 7 (as amended), 14–19, 22. The
    seed never gates a chain; every non-exclusive entry keeps ≥1
    live route; floors/traits stay per-candidate off the resolved
    sheet, unchanged on top of routing; nothing serialized
    (INIT_SEED-derived routing; no new ctx fields this phase);
    pads teach on pickup, nothing held, nothing sellable; ledgers
    follow the live holder (the carried phase-2 wrinkle: a
    pre-phase-3 save's earned set can disagree with the newly
    derived holder — accepted, no migration; the buy-side
    requires-gate is unaffected).
  - **Required tests.** Routing determinism (same INIT_SEED → same
    live routes/holdings; a rerolled seed → a different but legal
    derivation — ≥1 live route per entry, exactly `picks` live
    candidates); catalog integrity (sources are real npc ids on
    real planets with valid factions; `picks` ≤ pool size;
    triggers reference the registry; no unscoped sources anywhere);
    resolver (a non-live candidate's topic absent, a live one
    present, floors still applied on top; DARK reads neutral
    through the live map); holder scatter (only the live dealer
    shows the Buy row; non-live candidates show nothing);
    `fire_trigger` (hears authored entries; idempotent on refire);
    pads (teach-on-pickup records verbatim + keyring; re-pickup
    no-op; pad absent when the entry is already heard; non-pad
    loot unchanged; loot_data round-trip); host (sub-menu rows
    honor the live map; the current planet scopes delivery);
    Continue stability (init_seed already round-trips — routing
    identical after load).
  - **Stop point.** No comms host or scuttlebutt (phase 5), no
    fragments / discovered-sites state / dig dungeons (phase 4),
    no lie (phase 5), no legendary loot (deferred, SETTLED 21), no
    dungeon-loot pad surface (phase 4), no SYSTEMS.md close work
    (phase close).
  - **Playtest checkpoint** (numbered; SPACEHACK_DEV run):
    1. Fresh dev run: talk to the starting-city barkeep — no
       rumor topics anywhere (no chain askable at spawn); the
       dealer sub-menu opens with Favor: 0 and no rows.
    2. Shift+R: the live-routes readout lists each chain's
       carrier planets this run. Travel to a live opener carrier;
       Ask Around delivers tier 1 (readout + ledger verbatim).
    3. Walk the chain: witness pointer text names where to look
       next; the next tier's live carrier delivers; floors still
       refuse below their standing (the thin_month militia
       floors).
    4. Trigger: approach the Line and take the warning —
       `thin_month_1` arrives without asking (readout + ledger);
       a re-warn does not duplicate.
    5. Pads: board/loot the authored pad carriers — the pad
       teaches on pickup (readout, ledger, nothing to the hold);
       the same source re-killed carries no pad.
    6. Holder scatter: Shift+R names the live holder of
       `dark_berth_4`; only that dealer shows the Buy row; the
       Whisper vendor still gates on the keyring regardless of
       holder.
    7. Determinism: save → quit → Continue — Shift+R shows the
       identical routing; Shift+S reroll → different legal
       routing (item 2 repeats against the new routes).
    8. Regression: phase-1/2 behaviors intact (Q tabs, favor
       economy, no-selling-back, vendor gate, quest/purchase
       rows); non-source NPCs show no Ask Around row.
    9. Guide diff: the discovery sentence quoted before/after; no
       chain telegraphing.

## Pre-implementation audit — phase 4 (2026-09-12)

1. **Existing classes / modules to extend or reuse.**
   - Generator: ``dungeon_bsp.generate_dungeon(DungeonParams)`` (dungeon_bsp.py:9; ``DungeonParams`` at dungeon_params.py:10-34 — theming is the two ``world.Tile`` fields ``tile_wall``/``tile_floor``). The BSP generates NO stairs — one EXIT at the spawn wall (dungeon_bsp.py:195-223). Stairs idioms live in dungeon_extensions.py: the EXIT→STAIRS_UP overwrite (:345-353) and the farthest-free-cell pick (:53-67).
   - Population: ``populate_dungeon(map, params, spawn, tier=)`` (dungeon_population.py:181) — tier scaling built in (clamped 1-3); scatter already excludes stairs/footprints, ≥5 from spawn.
   - Landmarks: ``landmark.stamp_landmark(map, landmark_map, spawn)`` (:384) + ``choose_weighted_variant`` (:40) + ``load_landmark`` (:57, data/landmarks/); a layout needs one ``landmark_entrance`` (glyph ``e``) or exactly one door, and ≤1 arrival/console/stairs_down (landmark.py:93-131) — dig landmarks author none of those.
   - Entry idiom: ``_enter_planet_surface`` (game_interactions.py:154-176) — its fog/reveal/player/mode/return-pair block extracts into a shared ``_install_dungeon_entry`` helper that the authored path and the dig path both call. EXIT bump → ``_handle_dungeon_exit_tile`` (game_flow.py:763) returns to space — so floor 1 KEEPS the BSP EXIT; floors >1 overwrite it with STAIRS_UP.
   - Stairs handling: game_loop ``_handle_stairs_down``/``_handle_stairs_up`` (:604/:632) gain a thin dig branch keyed off the map's ``interior_cache_key`` prefix ``dig:`` — NO new map attributes: the key is already persisted (saveload_maps.py:157) and parsing yields planet/site/floor, so no ``_optional_map_fields``/``_apply_extension_attributes`` twins. Arrival position scans the target map for the opposite stair (the extension idiom), no stored positions.
   - Menu: ``menus/_planet.py`` ``_build_menu_items`` (:19-34) appends one "Explore <site>" row per discovered site on the planet; ``_run_planet_menu`` (:74-97) resolves the picked site; ``_resolve_planet_wall`` (game_interactions.py:105-116) dispatches to ``digs.enter_dig_site``. Authored-row gating (``has_explorable_sites``, main-quest unlock) untouched.
   - Doors: ground hook = one line beside the three pool drops in ``combat/_rules_ground.on_kill`` (:740-758); derelict pad = the generic wreck-board branch of ``_boardable_wreck_layout`` (the :701 derelict path — mission salvage and the main-quest wreck excluded); C-terminal roll = the non-capture branch of ``_resolve_computer_terminal`` (:538-550), rolled once at first power-restoration. Pickup: ``loot._open_single_loot_pickup`` (:589) gains a ``reveals_site`` branch beside ``teaches`` (:591-593) → ``digs.reveal_site``.
   - Ledger: ``_render_rumors_pane`` (menus/_quest_log.py:123-157) appends pointer lines after the keyring loop (:152).
   - State: ``ctx.discovered_sites`` beside ``interiors`` (game_context.py:265); ``_dig_fields``/``_restore_dig_fields`` in saveload.py beside the lore family (:142-153, wired at :187/:829); New Game clears via fresh GameContext (game_loop.py:884).
   - Dev: Shift+M is free (_DEV_SHIFT_KEYS, game_loop.py:361-373; matcher in input_helpers.py; grant in dev_mode.py — the ``log_rumor_routing`` shape).
   - Text: ``data/text/09_digs.json`` auto-registers via the glob (text.py:186); call sites ``.format()`` placeholders (text.py:207; game_interactions.py:419 precedent).
   - Registry: ``list_planet_specs()`` (data/planets/__init__.py:191) = every planet; PlanetSpec gains the dig fields near ``dungeon_params`` (:106).

2. **Duplication hotspots.**
   - Dig floor generation vs extension floor generation (BSP + stairs + populate) — digs.py MIRRORS the idiom but shares no extension machinery (no DungeonExtensionSpec); shared primitives are the BSP generator, the farthest-free-cell pick, ``stamp_landmark``, ``populate_dungeon``.
   - The entry-install block (fog/reveal/player/mode/return-pair) — ONE extracted helper in game_interactions used by both authored surface entry and dig entry.
   - Extension stairs branch vs dig stairs branch in game_loop — both thin delegates; all dig logic in digs.py.
   - Pad spawn — ground and derelict doors roll through one ``digs`` helper (rate lookup inside), the shape of ``loot.maybe_spawn_pad``.
   - Readout + ledger pointer both resolve their templates through data/text — hosts never inline dig prose.

3. **DRY strategy.** One ``digs.py`` facade (reveal / derive / generate / enter / transition / doors); one entry helper; one pad helper; the cache-key parser as the single dig-floor identity source; loot through the pluggable spec in ``data/digs/``.

4. **Ratchet.** Tight modules: combat/_rules_ground 996 (+2 — import + one call; if it crosses, the hook moves beside ``_spawn_loot_drops``'s callers), game_interactions 978 (+~12), game_loop 932 (+~12), saveload 878 (+~12), loot 611 (+~8), _quest_log 598 (+~12), input_helpers 467 (+~6), dev_mode 518 (+~10), game_context 433 (+3), planets/__init__ 432 (+6), menus/_planet 97 (+~15). New: digs.py ~350, data/digs/__init__.py ~80.

5. **Pinned consequences.**
   - Depth is NOT stored: sites are ``{id, planet, name}`` (brief scope); depth derives pure from ``seeded_rng(INIT_SEED, "dig_depth", site_id)`` within the spec's bounds at every read — Continue-stable, and the list is the only new round-trip.
   - Site ids sequential ``s<n>`` at reveal; cache keys ``dig:<planet>:<id>:<floor>``; floor 1 keeps EXIT, deeper floors STAIRS_UP; arrive at the opposite stair.
   - Door rolls ride engine.RNG (runtime, save-pinned RNG state); the reveal derivation (planet/name/depth) rides INIT_SEED (SETTLED 7/28).
   - The humanoid pad-dropper set excludes ``civillian_bystander`` (combatants only; data-authored, tunable).
   - Dig Explore rows ignore the main-quest surface gate — discovery is the gate.
   - Placeholder loot: planet ``produces`` goods in tier+floor-scaled quantities via the pluggable loot spec in data/digs (SETTLED 35).
   - Landmark sprinkle chance seeded per site+floor; landmarks author no stairs/console/arrival markers.
   - PROSE GATE: the reveal template, pointer line, default name pools, landmark names/flavor, and the guide sentence are DRAFTS, quoted for approval at the playtest checkpoint (brief item 8).

### Phase 4 — Procedural dig-site dungeons (inserted 2026-09-11; re-scoped 2026-09-12)
- [ ] Discovered-sites player state + the three RNG-rare discovery
      doors (humanoid-enemy datapads, derelict datapads, the
      boarded ship's C terminal) — SETTLED 25, 27, 28
- [ ] Planet-menu Explore rows per discovered site, proc-generated
      site names; config-driven BSP generation (spec-fed: theme,
      tier-scaled difficulty/loot; landmark-room sprinkle) —
      SETTLED 25, 26, 28
- [ ] Persisted revisitable interiors (the martian-caves idiom);
      placeholder tier-scaled loot — SETTLED 29, 30
- [ ] Playtest checkpoint

  (Rulings SETTLED 20-24 + 25-37; legendary loot is deferred per
  SETTLED 21.)

  Implementation brief (4) — PROPOSED (refine session 2026-09-12):

  - **Scope.** State: ``ctx.discovered_sites: list[dict]`` —
    ``{id, planet, name}`` in reveal order — round-tripped in a new
    ``_dig_fields``/``_restore_dig_fields`` family beside the lore
    fields; New Game clears via fresh GameContext. Domain: new
    ``digs.py`` — ``reveal_site(ctx)`` (the seeded derivation:
    ``seeded_rng(INIT_SEED, "dig_reveal", len(discovered_sites))``
    picks the planet among ALL planets, the site index on it, and
    the name from the planet's pools; records the site, presents
    through ``rumor.present_hearing``), ``derive_dig_params(spec)``
    (theme + ``mission_tier`` → ``DungeonParams``; the spec's
    ``dig_params`` overrides — SETTLED 26) plus the depth bounds
    (``dig_min_floors``/``dig_max_floors``, derived default 1-2 —
    SETTLED 38), ``generate_dig(ctx,
    site, floor)`` (the existing BSP generator + populate at
    tier + floor; the generated stairs-down on non-bottom floors —
    stairs are terminals, the prison-extension idiom; the landmark
    sprinkle; the placeholder cache), ``site_depth(spec, site)``
    (seeded within the spec's ``dig_min_floors``/``dig_max_floors``
    at reveal, default 1-2), and
    ``site_loot_rows(spec, tier)`` (the pluggable loot spec,
    SETTLED 35). Data: ``data/digs/`` — the authored rates table
    (1-in-12 humanoid pad / 1-in-8 derelict pad / 1-in-6 C-terminal,
    SETTLED 36), the default name pools, the humanoid pad-dropper
    id set (NpcCharSpec ids), and three landmark room stamps
    (agent-drafted, prose gate; SETTLED 32). PlanetSpec:
    ``dig_prefixes`` / ``dig_suffixes`` (empty = the default pools)
    and ``dig_params`` (None = derived). Doors: humanoid ground
    kills roll the pad beside ``_rules_ground.on_kill`` loot
    (loot_data ``{"reveals_site": True}`` — pickup calls
    ``reveal_site``); derelict wreck interior loot spawns roll the
    pad (``dungeon_layout`` loot construction); the ship-computer
    terminal (``game_interactions._resolve_computer_terminal``, the
    non-capture branch) rolls the reveal on access. Menu:
    ``menus/_planet.py`` — one "Explore <site name>" row per
    discovered site on the planet, hidden until found, each opening
    the cached-or-fresh dig floor (cache keys
    ``dig:<planet>:<id>:<floor>`` in ``ctx.interiors`` — every
    floor persisted, SETTLED 29/38). Ledger: the RUMORS
    pane renders keyring entries, then the site pointer lines from
    ``ctx.discovered_sites`` (SETTLED 37; template + injected name
    + planet). Dev: Shift+M force-reveals a site (checklist
    instrument).
  - **Build order.** (1) state + round-trip + the
    ``digs.reveal_site`` derivation (planet, name, DEPTH) + name
    pools (+ PlanetSpec fields, depth bounds) + tests; (2)
    ``derive_dig_params`` + ``generate_dig`` + the stairs-down +
    floor transitions + the landmark stamps + tests; (3) the
    three doors + the pad pickup + tests; (4) planet-menu rows +
    the per-floor interiors cache + depth-scaled populate/loot +
    tests; (5) the ledger pointer lines + tests; (6) Shift+M;
    (7) playtest checkpoint.
  - **Binding rulings.** SETTLED 20-24 as amended, 25-37. Every
    planet, no roster; nothing hardcoded per site; the spec feeds
    the generator; three RNG-rare doors, never guaranteed;
    discovered-sites state is the source of truth (menu + cache),
    the ledger line is its presentation twin; persisted revisits
    (cleared stays cleared); placeholder loot through the pluggable
    spec; no rumor-chain integration (pointer lines only).
  - **Required tests.** Reveal determinism (same INIT_SEED → same
    planet/name; reroll → different legal reveal); state
    round-trip (order preserved; New Game clears); doors (each
    rolls its rate; the pad consumes + reveals once; a second pad
    reveals a NEW site — stacking, SETTLED 31); name pools (spec
    prefixes/suffixes; default fallback; both parts present);
    params derivation (theme tiles; tier scaling; ``dig_params``
    override wins); landmark sprinkle (pastes legally, walkable,
    seeded); loot spec (planet goods, tier-scaled quantity; the
    pluggable shape; floor-scaled); menu rows (hidden until found;
    one per site; the authored Explore row unchanged); depth (the
    seeded roll lands within the spec's bounds; the derived
    default 1-2; stairs walkable terminals on non-bottom floors;
    floor transitions + per-floor persistence; tier+floor
    population scaling); revisit (the cache keys persist; cleared
    stays cleared on every floor); ledger (pointer lines after
    keyring entries, verbatim template); regression (the five
    authored dungeon planets unchanged; the dark-ports chain
    surfaces untouched).
  - **Stop point.** No rumor-chain integration (fragments teach no
    chain entries), no multi-level floors, no legendary/rich loot
    (the placeholder spec only), no world-map site pins (menu rows
    only), no derelict-site crossover content, no doc-43 content,
    no SYSTEMS.md close work (phase close).
  - **Playtest checkpoint** (numbered; SPACEHACK_DEV run):
    1. Shift+M: a site reveals — the readout plays; Q → RUMORS
       shows the pointer line ("...names a site: <name> on
       <planet>"); the planet menu for that planet shows "Explore
       <name>"; other planets show nothing new.
    2. Fly there, explore: a themed, tier-scaled single-level
       dungeon generates (planet theme tiles; monsters at the
       planet's tier); the placeholder cache carries the planet's
       goods.
    3. Landmark: Shift+S reroll + Shift+M reveals across several
       sites — a landmark room appears here and there (not every
       dungeon), its pieces paste cleanly.
    4. Depth: a multi-floor site (Shift+M until one reveals, or a
       spec-authored deep planet) — descend the generated stairs;
       deeper floors are harder and the placeholder cache richer;
       every floor is a persisted map.
    5. Revisit: leave and return — the SAME maps (cleared stays
       cleared, looted stays looted, on every floor); save → quit →
       Continue — sites, ledger lines, depths, and the cached
       floors all survive.
    6. Doors: kill humanoid enemies — a Data Pad drops rarely;
       derelict wrecks' loot and the boarded ship's C terminal
       reveal rarely. Numbers feel special, not grindy.
    7. Regression: the authored explorables (mars caves, mercury,
       wolf_b, barnards_b, procyon_c) explore exactly as before;
       the dark-ports chain end-to-end (dock line, carriers,
       passphrase row) is untouched.
    8. Prose read-through (prose gate): the reveal template, the
       three landmark pieces' names/flavor, and the default name
       pools — all drafted by the agent, quoted for approval.

### Phase 5 — The space host + the lie (was phase 4)
- [ ] Ask Around on the comms matrix (talkable contacts);
      scuttlebutt vector (patrol chatter as free hearsay)
- [ ] The authored lie: false flag honored, false route, in-world
      reveal
- [ ] Playtest checkpoint

