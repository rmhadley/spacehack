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
   never reshuffle). The seed varies: which authored chains surface
   this run (seeded subset), which dealer holds which exclusive,
   where finds point (seeded pick among authored candidates).
   Content stays authored. CONTINUE regenerates identical routing
   from the persisted INIT_SEED; SPACEHACK_SEED makes playtests
   reproducible; Shift+S reroll yields a different but equally
   legal routing.
8. **The sub-menu — both hosts, heard-topics only.** One "Ask
   Around" row on the city/bar NPC talk modal AND on the space
   comms matrix for talkable contacts (derelicts and the
   restricted-space blockade keep their End-Transmission-only
   rows). Same look/feel everywhere — one interaction pattern to
   learn. Rows: the topics you've HEARD that this contact could
   know (floors applied), plus offer/ask favor rows on dealers
   (phase 2). Topics they can't help with are never listed —
   greyed lists teach; no row at all when there's nothing to ask.

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
- [x] Hearing on the talk host: source NPCs list rumor rows; taking
      one records verbatim + adds the keyring
- [x] The shared Ask Around sub-menu (city/bar host)
- [x] The verbatim ledger pane in the Q log
- [x] Three authored chains across bar + city sources
- [x] Guide: new Rumors section (ledger + ask-around how-to only)
- [ ] Playtest checkpoint (checklist in the brief)

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
    6. Regression: quest rows, purchase rows (scrub/cutout/rig),
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

### Phase 2 — The favor exchange
- [ ] Dealer spec (`data/lore/`): values, prices, exclusives
- [ ] `ctx.rumor_favor` per-dealer ledgers + save/load
- [ ] Offer/ask rows in the shared sub-menu (dealers only)
- [ ] Exclusive tier gated on favor; once-per-(rumor, dealer)
      earning
- [ ] An authored option-unlock payoff (an exclusive that changes
      an interaction)
- [ ] Playtest checkpoint

### Phase 3 — Seed routing + finds that teach
- [ ] Derived routing module (pure INIT_SEED derivations): chain
      surfacing subset, dealer exclusive scatter, find destinations
- [ ] Loot that teaches: data pads teach keyring entries on pickup
- [ ] Finds that send: map fragments point at seeded candidate
      sites (dig site: info AND/OR legendary loot)
- [ ] Determinism tests (same INIT_SEED → same routing; reroll →
      different legal routing; round-trip stability)
- [ ] Playtest checkpoint

### Phase 4 — The space host + the lie
- [ ] Ask Around on the comms matrix (talkable contacts);
      scuttlebutt vector (patrol chatter as free hearsay)
- [ ] The authored lie: false flag honored, false route, in-world
      reveal
- [ ] Playtest checkpoint

