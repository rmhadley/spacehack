# DESIGN: The unified HUD — one core, four panels

**Status: REFINE PASS UNDERWAY (2026-10-20 — the 12 creation rulings
stand; this pass settled the empty slot, the band-order mock set
with cargo on all four panels, and the ESC label; briefs drafting.
Nothing implemented.**

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
  difference), cargo (ALL FOUR panels — re-added to space combat
  where it informs boarding, and added to ground combat at the mock
  review, item 14: the carry never drops a datum at the fight
  boundary), the status row (FIXED slot everywhere — never
  conditional, never popping, BLANK when empty — item 13), and THE
  FOOTER (ruled 2026-10-20, item 12: the XP row alone,
  bottom-anchored, all four panels — the bar stops vanishing when a
  fight starts; both combat panels GAIN the in-fight XP read).
  "Fixed" means structurally pinned — the DATA is live; the rows,
  their y, and the painter never change.
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
| 12 | **THE FOOTER joins the core, slimmed to one row** (user, 2026-10-20): the XP bar alone, shared and bottom-anchored across all four panels. "bump to interact" DROPS entirely (verified: only the two exploration panels paint a footer today, and neither combat panel paints any bottom rows — so unifying ADDS the XP read to both fights). "ESC to quit" RETIRES as STALE — ESC opens the pause menu, it does not quit — and ESC joins each mode's key-hint block (the help lines exploring, ACTIONS fighting) as `[ESC] Pause` (prose ledger #1, shipped 2026-10-20) |
| 13 | **The empty status slot renders BLANK** (refine pass, 2026-10-20): the reserved row paints nothing when no status is active — combat's shipped doc-103 shape (the closing-gap row) becomes the law on all four panels; no placeholder glyph |
| 14 | **Cargo paints on ALL FOUR panels** (mock review, 2026-10-20): ground combat gains the row too — the frame law's reading ("same rows in every panel", the health meter the only difference) over item 3's space-only note; the walk→fight→walk carry never drops the datum |
| 15 | **The band-order set APPROVED as mocked** (mock review, 2026-10-20): the mocks below are the layout contract. Inside it: the PLAYER label moves WITH the health meter (it names the meter block, not the band); the slim weapon rows keep combat's volley checkbox as a combat-only mark before the name — the row shape (name + magazine) is what goes identical |

## The approved mocks (2026-10-20, item 15 — the layout contract)

Ground exploration, end-state (Phase 1 keeps the doomed rows as
interim band rows — species/class stay in A, credits/skills park at
D's top — until Phase 2 deletes them):

```
Spacehack
Eri City                        A  band
2160-04-12                      A
-------------------------------
HP    ####...... 18/24          B  CORE (one painter, one shape)
Armor          3                B
Cargo ####...... 12/22          B
                                B  status slot (blank when empty)
WEAPONS                         C  anchor
  M-Laser     8/12              C
  HOLSTER  Cutter, Machete      C
  SL 24/40                      C
-------------------------------
A  Armory                       D  band
=  Trade                        D
[C] Character  [?] Guide        D  help pairs, ESC joining here
LV  3 [##########----]          footer, bottom-anchored, alone
```

Terminals move from today's mid-panel spot (above the status row)
down into D below WEAPONS; the footer slims to the XP row alone.

Ground combat, end-state (the A-band rows keep the regen suffix and
gold AP marker until Phase 2 kills them; weapon rows stay fat until
the Phase 2 slim):

```
> GROUND COMBAT <               A  band
AP: 3/4.5                       A
EVA: 35%                        A
STIM (a): READY                 A  (only with a core worn)
PLAYER                          B  CORE (label moved with the meter)
HP    ####...... 18/24          B
Armor          3                B
Cargo ####...... 12/22          B
                                B  status slot (blank when empty)
WEAPONS [3] 2AP                 C  anchor
[x] M-Laser    8/12             C
[x] Cutter     1/1              C
HOLSTER  Machete                C
SL 24/40                        C
ENEMIES                         D  band
  Bandit  ####.. 4/10           D
ACTIONS                         D
[f] Fire   [m] Move             D
[t] Target [a] Stim             D
LV  3 [##########----]          footer, bottom-anchored, alone
```

Space sketches (Phase 3 pins the details at its brief): exploration
= A ship name/location/date/Fuel/Spd → B Hull/Shield/Cargo/status →
C reserved → D help → footer; combat = A title/AP/Evade/Pow → the
same B → C WEAPONS → D enemies/actions → footer (gains the XP read).

## Phases (proposed — the refine pass settles briefs)

- [ ] Phase 1 — the skeleton: the shared core blocks + the neutral
      module home; both ground panels painted from them; the status
      row's fixed slot everywhere; the fight boundary stops
      swapping the anchored rows. PLAYTEST: walk into a fight with
      a status active and watch nothing pop.

### Implementation brief — Phase 1 (APPROVED 2026-10-20)

**Scope (exact files/hook points).**

- NEW `src/spacehack/hud_core.py` (~150 lines) — the shared core's
  neutral home (open question 5, bound from code facts: combat
  already imports `hud.py` module-level, `hud.py` sits at 848 lines
  near the ratchet, and four panels need one import home).
  Data-parameterized pure painters + the region row-budget
  constants; imports nothing from `combat` at module level (the
  status-slot painter lazy-imports
  `combat._statuses.paint_hud_segments` inside the function — the
  bandolier precedent; segments arrive as a parameter). Hosts: the
  health-meter painter (HP bar + Armor, exploration's aligned
  format `HP    ####...... 18/24` becomes the one shape), the cargo
  row painter, the status slot painter (fixed, blank when empty),
  the footer painter (XP row alone, bottom-anchored; absorbs
  `_render_hud_footer`/`_footer_rows` from `hud.py`, slimmed to one
  row).
- `src/spacehack/hud.py` — `_render_city_hud` restructured to the
  four regions: A keeps species/class/location/date (interim doomed
  rows ride the band), B = the core via hud_core (HP/Armor/Cargo +
  the status slot stops being conditional), C = the WEAPONS block
  unchanged, D = interim credits/skills at D-top, then terminals
  and help (terminals move below WEAPONS per the approved mock),
  `[ESC] Pause` joins the help pairs. Net line change: negative.
- `src/spacehack/combat/_ground_render.py` — `_render_player_panel`
  restructured: A = title + AP (gold marker stays until Phase 2) +
  EVA + STIM; the PLAYER label moves onto B; B = hud_core meter
  (regen suffix stays until Phase 2) + Armor + the NEW cargo row
  (`_cargo_used_max` from `hud` — the existing module-level
  combat→hud pattern) + the status slot; C/D unchanged (WEAPONS
  stays fat; `[ESC] Pause` joins the ACTIONS pairs); the footer
  paints (the in-fight XP read — new).
- One deliberate cross-pair touch: the footer painter is shared, so
  its slim necessarily lands on the space exploration panel too (it
  already paints that footer), and `[ESC] Pause` joins
  `_SPACE_HELP_LINES`. The space pair's core unification stays in
  Phase 3.
- No `data/` changes; no save/load state (presentation only).

**Build order.** hud_core painters + constants → wire exploration
(`hud.py`) → wire ground combat → ESC pairs → tests.

**Binding rulings.** Items 11-15 + prose #1; the approved mocks are
the layout contract; "fixed" = live data, fixed rows/y/painter;
reserved region heights — a band can never push the core (B's rows
share one y across the ground pair; the shorter A-band leaves
reserved blanks above its divider); blank-when-empty slot; the XP
footer alone; `[ESC] Pause` verbatim; one HP/Armor/Cargo format
painted by one painter.

**Required tests** (`tests/test_hud.py` + the ground-render HUD
tests in `tests/test_pygame_ui.py`; FrameBuffer built at
`SCREEN_WIDTH + HUD_WIDTH` — the glyph-budget law):
1. The pin: status segments paint at the same y on both ground
   panels (city render vs combat render, same active status).
2. Blank-when-empty: no ink at the slot row; the row is still
   consumed.
3. The XP footer paints at the bottom row in the fight; "bump to
   interact" and "ESC to quit" appear nowhere.
4. `[ESC] Pause` present in the help pairs and the ACTIONS pairs.
5. The cargo bar reads in the combat core.
6. Existing row pins (divider span, XP span, HP bar layout,
   weapons-header offset, `test_no_suffix_when_no_regen_at_all`)
   keep passing — retarget only the tests that pinned the old
   status-row/footer positions, mirroring the real callers' full
   kwarg set (`render_hud` public entry).

**Guide review.** No guide edit: the guide already teaches "ESC:
pause menu (save & exit, dump char)" and mentions neither retiring
footer string; `[ESC] Pause` matches it. Recorded as the deliberate
no-change (called out on the playtest checklist per the guide
contract).

**Stop point — do NOT start.** No Phase 2 drops (species/class/
credits/skills keep rendering; the regen suffix and gold AP marker
live; weapon rows stay fat); no C-screen work; no space-pair core
work; no prose beyond the ruled `[ESC] Pause`.

**Playtest checkpoint.**
1. Pop a stim or med pack on a walk, then walk into a street fight
   — the status row holds its y across the boundary; nothing in B
   or C moves.
2. End the fight — the same rows hold in reverse.
3. The LV/XP row paints at the panel bottom during the fight (new
   read).
4. "bump to interact" and "ESC to quit" are gone everywhere;
   `[ESC] Pause` reads in the help lines and in ACTIONS.
5. Let every status expire — the slot goes blank and the rows below
   hold.
6. The cargo bar reads in the fight's core.
- [ ] Phase 2 — the slim: the ruled drops land (species/class,
      credits→C with its new C-screen home, skills grid), the
      suffix and marker die, the weapon rows slim. PLAYTEST: the
      panels read at a glance; C carries credits.

### Implementation brief — Phase 2 (APPROVED 2026-10-20)

**Scope (exact files/hook points).**

- `src/spacehack/hud.py` — the ruled drops on the exploration
  panel: `_render_city_identity` loses the species/class rows
  (location/date remain; signature and callers in `render_hud`
  slim with it); the D-band interim rows die — the Credits row out
  of `_render_city_stat_rows`, the skills grid plus
  `_render_skill_line`/`_skill_slot` (and any callerless helpers
  behind them — the dead-code self-audit sweep). The panel lands
  the approved end-state mock.
- `src/spacehack/character_screen.py` — the shared credits row,
  wording verbatim `Credits: {stats.credits}`, under the title on
  ALL three tabs: threaded through `_equipment_frame`,
  `_cargo_character_frame`, and the Stats tab's `_stats_frame`
  (one shared header-row builder if three copies would drift). C
  becomes credits' canonical read (acceptance 3's landing spot).
- `src/spacehack/combat/_ground_render.py` — the suffix/marker/
  slim: the HP regen suffix dies in `_render_player_panel`
  (`_active_regen_amount` goes with it if callerless); the gold
  `+1` temp-AP marker dies in `_render_ap_row` (`_active_ap_bonus`
  likewise); `_print_weapon_block` slims to checkbox + name +
  magazine indicator — the per-weapon DMG/HIT/RNG/AP reference
  rows die. The WEAPONS title row's `[N] 2AP` read stays; the
  targeting line and target card stay (item 9: they own the live
  numbers).
- Guide — two edits, both ruled verbatim (prose ledger #2, #4): the
  consumables section's stim sentence replacement; the Character &
  Skills enumeration gains "credits". Nothing else in the guide
  references a doomed row or the reference rows (verified by sweep
  2026-10-20) — any surprise found at build is REPORTED at the
  playtest checkpoint, never edited unruled.

**Build order.** Exploration drops → C credits row → combat
suffix/marker → weapon slim → guide edits (own commit, per the
prose gate) → tests.

**Binding rulings.** Items 1, 4, 5, 6, 7, 9 + prose #2/#3/#4;
acceptance 4's single-surface law — regen and the stim bonus each
render exactly once per panel (the status row); the walking
weapon-row shape is name + magazine, combat's checkbox its only
extra mark.

**Required tests** (`tests/test_hud.py`, the ground-render HUD
tests in `tests/test_pygame_ui.py`, and the character-screen
tests):
1. Absence: species/class/credits/skills render nowhere on the
   exploration panel.
2. Presence: `Credits:` row under the title on each of the three C
   tabs; the number tracks `ctx.stats.credits`.
3. Combat HP row never carries a ` +N` suffix; the AP row never
   carries the gold `+N` (`test_no_suffix_when_no_regen_at_all`
   retargets into this absence pin).
4. The combat weapon block paints no DMG/HIT/RNG/AP reference
   rows; checkbox + magazine still paint.
5. The two guide edits render (their sections' shape pins keep
   passing).

**Stop point — do NOT start.** No space-pair work (Phase 3; the
space panels never carried the dropped rows anyway); no hud_core
geometry changes (the regions fixed in Phase 1 are law); no
C-screen redesign beyond the one row; no prose beyond ledger #2 and
#4 verbatim.

**Playtest checklist.**
1. The exploration panel reads at a glance: location/date straight
   into HP/Armor/Cargo — no identity rows, no credits, no skills
   grid.
2. Open C on Equipment, Stats, and Cargo: `Credits: N` sits under
   the title on every tab; spend some and reopen — the number
   moves.
3. Fight with regen and a stim active: no `+2` on the HP row, no
   gold `+1` beside AP — the status row alone reads REGEN/STIM.
4. The fight's WEAPONS rows are name + magazine (+ the checkbox);
   the targeting line and target card still carry the live numbers.
5. Guide review (called out, not silent): the stim sentence now
   reads "While it lasts the effect reads on the right-hand panel
   as `STIM` with its remaining turns." (was: "In combat a blue
   `+1` indicator appears beside the AP readout while it is
   active."); the C enumeration now reads "…your level, experience,
   credits, skills, available points, traits…" (was: no
   "credits").
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

1. ~~The empty status slot~~ — **SETTLED 2026-10-20, item 13**:
   blank row.
2. ~~The guide's stim sentence~~ — **SETTLED 2026-10-20, prose
   ledger #2**.
2a. ~~The ESC hint's new wording~~ — **SETTLED 2026-10-20, prose
   ledger #1**: `[ESC] Pause`.
3. ~~The C-screen credits row's exact shape~~ — **SETTLED
   2026-10-20, prose ledger #3**: shared row under the title, all
   three tabs.
4. ~~Band order within each mode~~ — **SETTLED 2026-10-20, item 15**:
   the approved mocks are the layout contract.
5. ~~The shared module's home~~ — **SETTLED 2026-10-20, bound in
   Phase 1's brief from code facts**: the neutral `hud_core`
   sibling (combat already imports `hud.py` module-level, `hud.py`
   sits at 848 lines near the ratchet, and four panels need one
   import home).

All open questions settled; every phase's brief approved. The doc
awaits `/implement-phase 104.1`.

## Prose ledger

1. `[ESC] Pause` — the ESC key-hint label, help lines + ACTIONS
   pairs, all modes; replaces the retired "ESC to quit" footer line.
   **SHIPPED verbatim 2026-10-20.** (Consistent with the guide's
   existing "ESC: pause menu (save & exit, dump char)" line — no
   guide edit rides the label.)
2. Guide, consumables section, the combat-stim sentence's final
   clause — replacement **SHIPPED verbatim 2026-10-20**: "While it
   lasts the effect reads on the right-hand panel as `STIM` with
   its remaining turns." (was: "In combat a blue `+1` indicator
   appears beside the AP readout while it is active." — dies with
   the marker, item 7; the STIM status segment already exists).
3. The C-screen credits row — **SHIPPED verbatim 2026-10-20**:
   shared row under the title on ALL three tabs, wording
   `Credits: {value}` (mock: `Credits: 1250`); joins the screen's
   header band, not the stats-only block.
4. Guide, Character & Skills section, the C-screen enumeration —
   **SHIPPED verbatim 2026-10-20**: "It shows your level,
   experience, credits, skills, available points, traits, and -
   when you are exploring on foot - your carried equipment." (was:
   no "credits").
