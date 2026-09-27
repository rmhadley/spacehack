# spacehack — Rumor content ledger

A living inventory of authored rumor CONTENT: every catalog entry's
settled prose, source pool, delivery doors, value, and build status,
tracked as content is added. This is not a design doc —

- system design, rulings, process: `in_progress/42_DESIGN_LORE_RUMOR.md`
- mechanics as built: the Rumors entry in `SYSTEMS.md`
- shipped strings, single source of truth post-build:
  `src/spacehack/data/text/08_rumors.json` + `src/spacehack/data/lore/chains.py`

The ledger records wording for review and history: when shipped prose
changes, the json and the ledger change in one commit.

## Ledger rules

- An entry lands here when its prose is settled in discussion (the
  prose gate — no player-facing string reaches a data file before the
  user has seen, edited, or approved it; knowledge.md "Quest prose
  standard").
- Status: **QUEUED** (settled, not yet in data) → **SHIPPED** (in
  chains.py + 08_rumors.json, gate green).
- Wording is recorded VERBATIM — obvious typos fixed + flagged.
- Mechanic and tuning rulings still route through doc 42's ruling
  loop; open notes here are content tuning only (pools, values,
  prose).
- Only catalog entries are tracked. Derivations and economy mechanics
  (dark-hull shares, favor rules, the ask surface) live in SYSTEMS.md.

## Entries

### dark ports — chain `dark_berth` — SHIPPED (doc 42 phases 1-3)

Topic label: "dark ports". Economy: t1+t3 sale (1+3) funds the t4
exclusive at 4 favor exactly; t2 unsellable (every dealer authors it
as a source — co-teller refusal).

| id | tier | value | requires | delivery |
|----|------|-------|----------|----------|
| `dark_berth_1` | 1 | 1 | — | triggers `dock_dark_port` + `dark_hail`; pads on pirate_raider + derelict_freighter |
| `dark_berth_2` | 2 | 2 | t1 | seeded city carriers, picks 2 of 5: wolf_barkeep/wolf_b, deadfall_scrubber/lal_b, ember_tech/ross_b, research_officer/mercury, barkeep/lal_c |
| `dark_berth_3` | 3 | 3 | t2 | trigger `dark_hail` (comms testimony) |
| `dark_berth_4` | 4 | 2 → 0 (queued) | t3 | dealer exclusive — all three dealers @ 4 (`EXCLUSIVE_CANDIDATES`); value-0 edit rides the 42.5 build (doc 42 SETTLED 47) |

Prose (verbatim, `08_rumors.json`):

- t1 — "Some ships don't broadcast an ID and some ports don't care
  who you are. How do they disable their transponder? Those dark ships
  and ports don't like to share much. Finding someone to speak with
  will need patience and connections. I should ask around."
- t2 — "I know of a few ports that don't check your creds... Deadfall,
  Whisper, Ember, and Wolf 359 b come to mind. Lots of black-market
  goods pass through those ports. Obviously, these are pirates using
  them."
- t3 — "Yeah, I'm not going to broadcast my name to all. They track
  everything! They don't need to know that I frequent Wolf 359 b. You
  want to be free too? Ask around on Whisper."
- t4 — "I know the guy, yeah. You're giving me good info, I can trust
  you. You can find him right here on Whisper. He hangs around by the
  containers south of the bounty office sometimes. Tell him The Hush
  sent you."

### taking ships — chain `taking_ships` — QUEUED (settled 2026-09-27)

One entry, one lesson: teaches the four conditions for boarding in
space combat (D) diegetically — a lone target, hull her until she
can't run, shields down, pull alongside. The guide keeps the reference
version; this is the discovery layer. Free to hear (no favor anywhere
in the ask path).

- id: `taking_ships_1` (proposed — save-facing)
- tier 1, no requires, no triggers, no pads — Ask Around only; the
  topic row shows only for live carriers and vanishes once heard
- topic: "Pirates have been boarding and raiding ships mid flight."
- text: "Have you heard? Pirates have been finding lone ships flying
  their routes. They shoot them up until they're nearly dead, shields
  down, can't run... then they fly next to them and breach their hull.
  Strip the cargo and gear, and leave no one alive."
- source pool: TIER-WEIGHTED COMPOSITION — rows per planet ∝ mission
  tier (T1: 1 row, the barkeep seat; T2: 2; T3+: 3), picks ≈ pool/3.
  The routing's uniform sample turns pool share into per-planet
  carrier odds (a ~1:2:3 gradient); exact rows and picks are pinned at
  build time against the real seat + tier map.
- value: 1 (open: 1 vs 0; lean 1 — it is sellable news, and tellers
  refuse buy-back via the co-teller rule)
- open: build home (rides the 42.5 build or stands alone); pool rows;
  value.

## Queue ahead

- The lost-convoy chain + the lie (doc 42 phase 5, spine drafted,
  prose unsettled) — lands here as its prose settles.
