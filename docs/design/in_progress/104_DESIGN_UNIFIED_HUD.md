# DESIGN: The unified HUD — one core, four panels

**Status: RIFFED + FULLY RULED (2026-10-20 — every keep/drop settled
through the question loop, one item per exchange, at doc 103's
playtest verdict). Awaiting the user's review of this doc; nothing
implemented.**

Companions: `in_progress/103_DESIGN_STATUSES.md` (the status row —
the first surface that lives on every panel, whose fight-boundary
"pop" exposed the divergence this doc fixes); `SYSTEMS.md` (the
HUD-adjacent inventory rows); `knowledge.md` (CP437 + glyph-budget
laws, the prose gate).

## The problem (observed at doc 103's verdict, 2026-10-20)

The ground exploration HUD and the ground combat HUD are two panels
from two eras that never met: the exploration panel IS the old city
HUD (`hud.py` — identity block, stats columns, skills grid, with
doc 52.3's weapons block bolted on when doc 53 made streets
hostile), and the combat panel IS the ground-combat docs' panel
(`combat/_ground_render.py` — title, AP/EVA, volley data, enemies,
actions). Each doc added its row to its own panel. Doc 103 shipped
the first row required on BOTH — the status line — and the
divergence gained a face: the same `STAGGERED 2` datum renders at a
different y, with different neighbors, in each mode, and the entire
right panel swaps at every fight boundary.

Three mechanical causes: (1) different section stacks above the
row; (2) the exploration row is CONDITIONAL (an empty container
consumes no row) while the combat row has a fixed slot; (3) nothing
anchors — on combat start cargo/credits/skills/terminals vanish and
AP/EVA/enemies/actions appear, so the eye has no fixed point.

The user's widening ruling (item 3 below): this is not a
ground-pair problem — **if a datum matters in the moments a HUD
serves, it deserves the same home on every panel that serves those
moments.** One core, four panels (ground/space × explore/fight).

## The frame (RULED, item 11)

- **A fixed-slot shared core painted by the same painters at the
  same rows in every panel**: the mode's health meter (HP on the
  ground; hull/shield in space — the core's ONLY space-vs-ground
  difference), cargo (re-added to space combat, where it informs
  boarding), the status row (FIXED slot everywhere — never
  conditional, never popping), and THE FOOTER (ruled 2026-10-20,
  item 12: the XP row alone, bottom-anchored, all four panels —
  the bar stops vanishing when a fight starts; both combat panels
  GAIN the in-fight XP read). "Fixed" means structurally pinned —
  the DATA is live; the rows, their y, and the painter never
  change.
- **Reserved regions, not insertions (the load-bearing geometry,
  clarified at doc review 2026-10-20)**: every panel is four
  regions — `[A: mode band, reserved height]` / `[B: THE CORE,
  fixed rows]` / `[C: theater anchor]` / `[D: mode band, reserved
  height]`. Bands swap; anchors never move; a band growing or
  shrinking can never push the core because the regions are
  reserved. Inserting band rows directly above an anchor (combat's
  AP/EVA/STIM above the status row) would reintroduce the pop —
  reserved heights are the law.
- **The bands are per-MODE, not combat-only** (all four modes have
  one): ground exploration paints location/date (region A) and
  terminals/help (D); ground combat paints header/AP/EVA/STIM (A)
  and enemies/actions (D); the space pair paints its own reads.
  Bands stay with their owning modules (the combat renderer keeps
  enemies/actions; `hud.py` keeps terminals/help) — the
  unification is the core, not a mega-refactor.
- **Ground anchoring on top**: HP/Armor, the status row, and the
  WEAPONS block (region C) pin across the explore↔fight boundary.
  A fight starting or ending swaps only the bands — and nothing
  the carry is about ever moves. The doc 103 promise made visible:
  the status row sits at the same y for the whole walk → fight →
  walk arc.
- **The space pair gets the same treatment** for its own meters
  (hull/shield/AP/pow), so the space explore↔fight transition
  stops being a panel swap too.

Mechanical shape (brief material): the shared ink already lives
engine-side (`combat/_statuses.paint_hud_segments` — a neutral
home). The shared blocks live in a module both renderers can import
(the `hud.py`-cannot-import-combat cycle law stands; a neutral
`ground_hud`-style module or data-parameterized painters in
`hud.py`), with each panel passing its data in. No new prose rides
the skeleton — every surviving row is an existing string.

## The audit — every row ruled (2026-10-20, one per exchange)

### Exploration panel (ground walking)

| # | Row | Ruling | Landing spot |
|---|---|---|---|
| 1 | Species / Class | **DROP both** | The C screen owns identity |
| 2 | Location / Date | **KEEP both rows** | — (the clock's only ambient home) |
| 3 | Cargo | **KEEP** | — and ADD to space combat (board-worthiness) |
| 4 | Credits | **DROP** | The C screen GAINS credits in its header |
| 5 | Skills grid (all six) | **DROP** | C's Stats tab (descriptions + bonuses — richer) |
| 10 | HP + Armor, terminal hints, status row, weapons/holster/bandolier, help lines | **KEEP all** | — |

Resulting exploration panel: location/date → HP/Armor → (status
slot) → WEAPONS/holster/bandolier → terminals → help.

### Combat panel (ground fighting)

| # | Row | Ruling | Note |
|---|---|---|---|
| 6 | HP row's `+2` regen suffix | **KILL** | The status row owns regen (supersedes doc 103's keep-the-suffixes ruling) |
| 7 | AP row's gold `+1` temp-AP marker | **KILL** | The status row owns it; the marker was sign-blind (negatives rendered nothing). The guide's "+1 indicator" sentence rewrites through the prose loop at build |
| 8 | `EVA: N%` | **KEEP** | Verified LIVE (the one dodge assembly — moves within the turn); the move-to-dodge tactic's only ambient read; symmetric with space's Evade row |
| 9 | Per-weapon `DMG/HIT/RNG/AP` reference rows | **SLIM fully** | Name + magazine + checkbox — the walking shape; the targeting line and card own the live numbers. This makes the WEAPONS block identical in both modes — the third ground anchor |
| 10 | Header/PLAYER, Armor, AP row, `STIM (a)` ability row, status row, ENEMIES, ACTIONS | **KEEP all** | STIM stays — an ability-cooldown surface (doc 103 q3), deliberately not a status |

### Frame

| # | Ruling |
|---|---|
| 11 | **FULL FRAME confirmed** — four-HUD core + ground anchoring |
| 12 | **THE FOOTER joins the core, slimmed to one row** (user, 2026-10-20): the XP bar alone, shared and bottom-anchored across all four panels. "bump to interact" DROPS entirely (verified: only the two exploration panels paint a footer today, and neither combat panel paints any bottom rows — so unifying ADDS the XP read to both fights). "ESC to quit" RETIRES as STALE — ESC opens the pause menu, it does not quit — and ESC joins each mode's key-hint block (the help lines exploring, ACTIONS fighting) with prose-gated wording |

## Phases (proposed — the refine pass settles briefs)

- [ ] Phase 1 — the skeleton: the shared core blocks + the neutral
      module home; both ground panels painted from them; the status
      row's fixed slot everywhere; the fight boundary stops
      swapping the anchored rows. PLAYTEST: walk into a fight with
      a status active and watch nothing pop.
- [ ] Phase 2 — the slim: the ruled drops land (species/class,
      credits→C with its new C-screen home, skills grid), the
      suffix and marker die, the weapon rows slim. PLAYTEST: the
      panels read at a glance; C carries credits.
- [ ] Phase 3 — the space pair: cargo joins space combat; the
      space explore↔fight transition anchors. PLAYTEST: the
      boarding decision reads the bay; the space boundary calms.

## Acceptance criteria

1. The status row occupies the same slot in all four panels and
   never moves at a mode boundary.
2. HP/Armor, status, and WEAPONS hold their rows across the ground
   fight boundary (screenshot-diffable before/after the swap: only
   the bands change).
3. No ruled-dropped row renders anywhere it was dropped; every
   dropped read has its ruled landing spot (C header credits, C
   stats skills).
4. No duplicated effect surface: regen and the stim bonus each
   render exactly once per panel (the status row).
5. Zero new draws; no behavior change outside presentation; every
   touched module inside the architecture limits.

## Open questions

1. **The empty status slot** — the fixed slot renders when the
   container is empty: a blank gap row, or a faint placeholder
   glyph? (Blank matches the panel's blank-row rhythm; a placeholder
   advertises the surface to new players.)
2. **The guide's stim sentence** — the "+1 indicator" clause
   rewrites when the marker dies (prose loop at build; the sentence
   also carries the exploration-legal teaching that stays).
2a. **The ESC hint's new wording** — "ESC to quit" retires (stale:
   ESC opens the pause menu); its replacement label in the help
   lines and ACTIONS blocks settles through the prose loop at
   build ("ESC Menu" shape). "bump to interact" needs no
   replacement (ruled: gone).
3. **The C-screen credits row's exact shape** — a header line
   (`Credits 1250`) vs a stats-column row; player-facing, settles
   through the prose loop at build.
4. **Band order within each mode** — the exact row order of the
   mode bands (e.g., do terminals sit above or below WEAPONS in the
   city band?) — a mock review at the brief, one option set.
5. **The shared module's home** — neutral `ground_hud` sibling vs
   data-parameterized painters inside `hud.py` (build decision; the
   cycle law decides).
