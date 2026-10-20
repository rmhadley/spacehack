# DESIGN: The unified HUD — one core, four panels

**Status: PHASE 3 BUILT (2026-10-20 — builds 859d5def audit + e3ca92fd,
gate green 3995, reviewer APPROVE; its two mechanical minors applied,
the degenerate-tail minor REPORTED for the playtest per the brief's
surprise rule). Next: the Phase 3 playtest, then the doc's close
(SYSTEMS.md entries + move to complete/).**

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
| 16 | **The boundary dividers are panel chrome, not exploration flavor** (mid-playtest ruling, 2026-10-20 — the user flagged their absence in the fight and ruled them in): every panel closes its A band and its C region with the full-width rule. In ground combat that means the reserved band blank above the PLAYER label (row 5) and the old blank spacing row below the weapons block — both zero row cost, no anchored row moves, the enemies-panel budget untouched. Amends item 15's combat mock (below, updated). The space pair inherits the law in Phase 3 |

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
the Phase 2 slim; dividers per item 16):

```
> GROUND COMBAT <               A  band
AP: 3/4.5                       A
EVA: 35%                        A
STIM (a): READY                 A  (only with a core worn)
-------------------------------
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
-------------------------------
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

- [x] Phase 1 — the skeleton: the shared core blocks + the neutral
      module home; both ground panels painted from them; the status
      row's fixed slot everywhere; the fight boundary stops
      swapping the anchored rows. PLAYTEST: walk into a fight with
      a status active and watch nothing pop.
      LANDED + PLAYTEST PASSED 2026-10-20 (build a10a2d4e, gate
      green, reviewer APPROVE). Mid-playtest fix (2961f6e5): the XP
      footer's bottom pixels clipped on the HUD band's final cell
      row — the overlay paints text at a 4px pad under a 16px line
      font and clips at the panel rect, so that row's glyph box
      overflows by the pad; `xp_footer_row` re-anchored to
      `hud_view_height - 2` (the last row that renders whole) on
      all three panels, with the ACTIONS tail bumped so the fight's
      legend cannot collide. Guide: no edits this phase (deliberate
      no-change, ruled in the brief — `[ESC] Pause` matches the
      guide's existing pause-menu line).

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
- [x] Phase 2 — the slim: the ruled drops land (species/class,
      credits→C with its new C-screen home, skills grid), the
      suffix and marker die, the weapon rows slim. PLAYTEST: the
      panels read at a glance; C carries credits.
      LANDED + PLAYTEST PASSED 2026-10-20 (build 8a30716b, guide
      900b05f6, gate green, reviewer APPROVE; the verdict covers the
      full checklist incl. the two called-out guide edits). MID-PLAYTEST
      RULING 16 + ADDENDUM (72e053ae): the boundary dividers joined
      the fight as panel chrome — see the Frame table; the combat mock
      below is amended; the space pair inherits the law. Audit-bound
      additions that ride the build: the skills-call sweep took
      `_render_ship_stat_rows`' trailing call, so the SPACE exploration
      panel lost its interim skills grid one phase early (item 5's
      drop completing — Phase 3 restructures that panel anyway); the
      combat weapon row's `[N]` slot index died with the slim (the
      checkbox is the only extra mark, item 15); hud_core's
      `regen_suffix` param died with the read. Reviewer minors: the
      pre-existing mangled space-mode docstring diagram (`hud.py`)
      queued into Phase 3's restructure; one redundant absence assert
      left as intent documentation.

### Implementation brief — Phase 2 (APPROVED 2026-10-20)

**Scope (exact files/hook points).**

- `src/spacehack/hud.py` — the ruled drops on the exploration
  panel: `_render_city_identity` loses the species/class rows
  (location/date remain; signature and callers in `render_hud`
  slim with it); the D-band interim rows die — the Credits row out
  of `_render_city_parked_rows`, the skills grid plus
  `_render_skill_line`/`_skill_slot` (and any callerless helpers
  behind them — the dead-code self-audit sweep, which the Phase 1
  reviewer extended to `_render_mission_line`, callerless in the
  touched hud.py). The panel lands
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
- [x] Phase 3 — the space pair: cargo joins space combat; the
      space explore↔fight transition anchors. PLAYTEST: the
      boarding decision reads the bay; the space boundary calms.
      LANDED 2026-10-20 (builds 859d5def audit + e3ca92fd, gate
      green, reviewer APPROVE). The space pair renders the frame:
      five-row A bands (exploration identity/Fuel/Spd; fight
      mode/AP/STIM/Evade/Pow), the core at rows 8-11 — byte-identical
      across the boundary, pinned (hull `25/25`, `Shd 5/5 +1`, cargo,
      the status slot) — the per-loadout C budget
      (`space_weapons_rows` = 1+3n) with both item-16 dividers at the
      same rows on both panels, D at the same row, footer at 52 on
      both. Audit-bound riders that rode the build: the space fight's
      PLAYER label died (the brief's B carries no label row — "the
      same B" as exploration); combat's legacy Shd-above-Hull order
      swapped to Hull-first (the brief and sketch list Hull first
      everywhere); exploration's old ALIGNED hull row died for the
      fight's shape (one painter, one shape); `[ESC] Pause` joined the
      space fight's ACTIONS (prose ledger #1's all-modes sweep
      completing — Phase 1 shipped ground + space help, this brief
      owned the fight's block). Reviewer APPROVE x1; its minors 2-3
      applied in-commit (`_status_segments` twin collapsed; the
      C-budget lockstep pinned so a weapon-row change trips the pin
      first); minor 1 (degenerate 11-12-weapon loadouts strand
      ACTIONS past the footer — same class as the old order's
      off-panel tail, probed empirically) REPORTED on the playtest
      checklist, not fixed unruled.

### Implementation brief — Phase 3 (APPROVED 2026-10-20)

**Scope (exact files/hook points).**

- `src/spacehack/hud_core.py` — gains the space meter painter: the
  Hull + Shield bar rows in hud_combat's shape (`Hull  ####... 9/12`
  / `Shield ####... 4/8`), data-parameterized like the ground core.
  The cargo and status-slot painters from Phase 1 serve as-is.
- `src/spacehack/hud.py` — `_render_space_hud` restructured to the
  regions: A = ship name/location/date + Fuel/Spd (band rows); B =
  the core via hud_core — hull, shield (NEW on this panel: the
  computed max via `_calc_max_shields(hull, flown modules)`, passed
  in as data — a full bar out of combat, which is true: every fight
  initializes shields to max), cargo, and the NEW status slot
  (fixed, blank-when-empty — the fourth panel gains doc 103's
  surface); C = an empty reserved region of fixed height (the space
  pair's shared WEAPONS budget); D = the space help lines; footer
  unchanged from Phase 1. Fold in the Phase 2 reviewer minor: the
  module docstring's space-mode diagram is mangled (pre-existing) —
  rewrite it to the end-state regions here.
- `src/spacehack/hud_combat.py` — `render_combat_hud`
  restructured: A = the combat header (mode indicator) + the
  AP/Evade/Pow rows out of `_render_player_block`; B = hull/shield
  via hud_core + the NEW cargo row (`_cargo_used_max` — ctx is
  already threaded at both call sites, verified:
  `_rules_space.py:708`, `_animations.py:625`) + the status row
  moving into B's fixed slot; C = WEAPONS; D = ENEMIES/ACTIONS; the
  footer wired (the in-fight XP read — new here, as ground got in
  Phase 1). Both panels carry the item-16 divider law: the A band
  and region C close with the full-width rule (space exploration
  already paints one today; space combat gains both at build).
- No mechanics, no balance, no save/load state — presentation only
  (the shield row displays already-derived state).

**Build order.** hud_core space meter → space exploration
(`hud.py`) → space combat (`hud_combat.py`) → footer wire → tests.

**Binding rulings.** Items 11-15; the approved space sketches (item
15's set); the same-rows law within the theater pair — B's rows
share one y and one row-set across the space explore↔fight
boundary, which is WHY exploration gains the shield row (a hull-only
core would shift B's rows at the boundary — the bug this doc kills,
reintroduced); blank-when-empty; reserved heights; zero new draws.

**Required tests** (`tests/test_hud.py` + the space-combat HUD
tests):
1. The space pin: hull/shield/cargo rows and the status slot paint
   at the same y on both space panels (exploration render vs combat
   render).
2. The cargo row reads in the space-fight core (the boarding read).
3. The shield row paints on exploration and reads full (computed
   max).
4. The XP footer paints at the bottom row of the space fight (new).
5. Blank-when-empty holds on space exploration.
6. `render_combat_hud`'s tests mirror the real callers' full kwarg
   set — both call sites pass `ctx` today and must keep passing it
   (the kwarg-threading law).

**Guide review.** No guide edit expected: no guide sentence pins
the space panels' row order, and "shown on the right-hand panel"
only becomes more true with the status slot landing on the fourth
panel. Recorded as the expected no-change; any surprise found at
build is REPORTED at the playtest checkpoint, never edited unruled.

**Stop point — do NOT start.** No ground-panel rework (Phases 1-2
are law); no mechanic or balance change behind any new row; no
C-screen work; no new prose; the doc's close (SYSTEMS.md entries,
move to complete/) waits for the phase's playtest, not this build.

**Playtest checkpoint.**
1. Fly, then enter a space fight: hull/shield/cargo and the status
   slot hold their y across the boundary — only the bands swap.
2. The boarding decision reads from the fight's core: the cargo bar
   is right there beside the hull.
3. The LV/XP row paints at the panel bottom during the space fight
   (new read).
4. The shield bar reads full on the walk and drains in the fight —
   same row, same y.
5. Land/exit fights repeatedly — no row ever jumps; let any status
   expire — the slot goes blank, rows below hold.

## Pre-implementation audit (2026-10-20, Phase 1)

### Existing modules/helpers to extend or reuse

- `combat/_statuses.paint_hud_segments` + `hud_segments`
  (`src/spacehack/combat/_statuses.py:281-320`) — the shared status ink
  both ground panels already paint with; hud_core's status-slot painter
  lazy-imports `paint_hud_segments` inside the function (segments
  arrive as a parameter; both callers already compute them).
- `hud._bar_str` / `HUD_TEXT_MAX` / `COLOR_HP_GOOD` / `COLOR_HP_LOW`
  (`hud.py`) — the aligned-bar primitives the core meter painter needs.
  They MOVE to hud_core with `hud` re-exporting, because
  `combat/_ground_render.py:24-35` and `hud_combat.py:17-28` import
  them from `hud` today (hud_combat stays untouched until Phase 3).
  This keeps the dependency one-way: `hud` → `hud_core`.
- `hud._cargo_used_max` + `_resolve_ship_catalog` — the one cargo
  capacity read (Merchant trait included); ground combat imports it
  through the existing module-level combat→hud import (brief names
  this pattern).
- `hud._hud_xp_line` — the XP row computation (level, bar, +N PTS
  gold); the combat footer reuses it as-is.
- `hud._render_city_identity` — the Phase 1 A-band rows
  (species/class interim + location/date), unchanged.
- `hud._render_ground_weapons_block` — region C's anchor painter,
  unchanged this phase; `_render_help_lines` / `_render_action_pairs`
  — the pair painters `[ESC] Pause` joins.
- Test scaffolding to mirror: `_ground_fixture` / `_patch_render_deps`
  (`tests/combat/test_rules_ground.py:842-888`), `_ground_weapons_ctx`
  (`tests/test_hud.py:162`), and the glyph-budget law
  (`FrameBuffer(SCREEN_WIDTH + HUD_WIDTH)`). Ground HUD bottom row =
  `SCREEN_HEIGHT - MSG_LOG_HEIGHT - 1` = 53 (MSG_LOG_HEIGHT=6).

### Duplication hotspots and DRY strategy

1. **The meter row strings.** Combat hand-formats its own HP row
   (`HP  {bar} {cur}/{max}` bar width 7-8, panel-cyan) while
   exploration's `_render_city_stat_rows` uses the aligned format
   (`{'HP':<8}{bar:<11}{cur}/{max}`, values at column 19, green/red).
   Copying the exploration format into combat would be exactly the
   drift this doc kills. **Fix:** one `paint_hp_armor_rows` /
   `paint_cargo_row` in hud_core paints both panels; the B-half of
   `_render_city_stat_rows` and combat's hand-format both die.
2. **The status row assembly.** Three sites assemble
   `hud_segments` + `paint_hud_segments` today with different flow
   semantics (exploration: conditional row; ground combat: closing-gap
   row; space combat: bool-return). **Fix:** hud_core's
   `paint_status_slot` — fixed slot, blank-when-empty, always consumes
   the row — replaces the two ground sites; hud_combat's twin stays
   as-is until Phase 3 (its brief owns it).
3. **The footer.** `_render_hud_footer`/`_footer_rows` paint three
   rows on the two exploration panels; the fights need the same XP
   read — a combat-local footer copy is the obvious trap. **Fix:**
   the pair is absorbed into hud_core as `paint_xp_footer` (ONE row,
   bottom-anchored); all three live panels call it (space exploration
   included — the brief's deliberate cross-pair touch).

## Pre-implementation audit (2026-10-20, Phase 2)

### Existing modules/helpers to extend or reuse

- `hud_core.paint_hp_armor_rows` (`hud_core.py:54`) — the meter's
  `regen_suffix` param exists solely for the interim read item 6 kills;
  the param dies with the read (geometry untouched — the regions are
  law). Exploration never passed it; combat's call slims.
- `hud.magazine_indicator` consumer pattern — the walking row shape
  (`_print_ground_weapon_rows` → `display_name` +
  `ground_weapon_ammo.magazine_indicator`, the doc 52.3 one-formatter
  law, `[n/cap]`). Combat's slimmed row joins THAT shape: checkbox +
  the walking row. The approved mock's bare `8/12` is schematic — the
  shipped magazine read is the bracketed helper output, and shape
  identity (item 15) means combat adopts the walking string verbatim.
- `character_screen_stats._stats_header_lines` — the Stats tab's
  non-selectable header-row pattern (`SplitRow(line, …,
  selectable=False)`); the credits row reuses the wrap, not the block
  (prose #3: header band, not stats-only).
- `_character_title` (`character_screen.py:43`) — the one title source
  all three tabs share; the credits row builder sits beside it in
  `character_screen_stats.py` (247 lines; `character_screen.py` sits at
  987 and takes only an import + one prepend — the ratchet stays clear).
- Guide anchors (verified in code, per the ruled-strings law): the
  stim sentence at `data/guide/__init__.py:344-345`; the C enumeration
  at `:493-495` — the edit inserts `credits, ` after `experience, ` and
  leaves the pre-existing sentence otherwise byte-identical (its spaced
  hyphens are the known unswept corpus, not this phase's business).

### Brief clarifications bound from code facts

1. **`_render_skill_line` has a live space caller** the brief's
   dead-code list implies callerless: `_render_ship_stat_rows`
   (`hud.py:404`) paints the skills grid on the SPACE exploration
   panel. The helper cannot die while the call lives, so the sweep
   takes the trailing call with it — the space exploration panel loses
   its interim skills grid THIS phase (one band row; the rows below
   shift up inside the same panel; no geometry, no new ink). This is
   item 5's drop completing its sweep, not new space-pair design:
   Phase 3's brief restructures `_render_space_hud` outright, and its
   region sketch carries no skills row. Called out on the playtest
   checklist so the change is reviewed, not silent.
2. **hud_core's `regen_suffix` param dies** (above) — the only hud_core
   edit this phase; constants and row budgets untouched.
3. **`_print_weapon_name`'s `[N]` slot index dies with the slim**: item
   15's "the volley checkbox its only extra mark" leaves no room for a
   second mark, and the mock's row is `[x] Name`. The `[1-N]` toggle
   stays advertised in ACTIONS.

### Duplication hotspots and DRY strategy

1. **The credits row three times.** The obvious trap is three
   hand-formatted copies (one per tab) drifting on wording or color.
   **Fix:** one `_credits_header_line(ctx)` string builder
   (`character_screen_stats.py`, wording verbatim per prose #3); the
   Stats and Equipment tabs wrap it in the existing non-selectable
   `SplitRow` pattern, the Cargo tab (a text frame) uses the string
   directly — the wrap is presentation, the string is single-sourced.
2. **A combat-local magazine format.** Formatting `n/cap` by hand next
   to the name would drift from the walking rows (and from the C
   screen's member rows — `magazine_indicator`'s two documented
   consumers). **Fix:** the slimmed combat row calls the same helper;
   no new formatter.
3. **Retargeted tests re-deriving old pins.** The regen/AP-marker/
   AMMO-line tests pinned interim shapes; rewriting each as a fresh
   bespoke assertion invites pin-by-pin drift. **Fix:** each retarget
   keeps its fixture and rendering path, flips to the absence pin
   (suffix/marker/reference rows appear NOWHERE on the panel), and the
   magazine presence lands in the one weapon-slim pin
   (`test_weapon_block_ammo_line_drops_the_reserve_suffix`'s home).

## Pre-implementation audit (2026-10-20, Phase 3)

### Existing modules/helpers to extend or reuse

- `hud_core`'s Phase-1 painters — `paint_cargo_row`, `paint_status_slot`,
  `paint_xp_footer` — serve as-is on both space panels (the brief).
- `hud_combat._render_hull_shield_rows` + `_hull_bar_color` + the
  hull/shield palette (`COLOR_HULL_BAR_GREEN/YELLOW/RED`,
  `COLOR_SHIELD_BAR`) — the meter's ink moves to hud_core as the
  data-parameterized `paint_hull_shield_rows`; hud_combat imports the
  palette back for its ENEMY rows (`Hul`/`Shd` are D-band content and
  stay in hud_combat).
- `combat/_stats._calc_max_shields` + `_free_shield_regen` — the
  computed shield max and free regen exploration now reads (lazy
  import, the pygame_overlay precedent — its docstring already calls
  it "same formula the player and the exploration overlay read").
  Every fight inits shields to max with rate 0
  (`_player_state_dict`: `shields = max_shields`,
  `shield_regen_rate = 0`), so exploration passing
  `shields=max, rate=0, free=computed` paints the exact row the
  fight's round 0 shows — same data, same ink, zero drift.
- `hud._cargo_used_max` + `_resolve_ship_catalog` — the fight core's
  cargo read (ctx is threaded at both call sites, verified
  `_rules_space.py:708`, `_animations.py:625`; the ground render's
  exact wiring pattern).
- `hud._hud_xp_line` + `hud_core.paint_xp_footer` — the fight footer;
  ground's `_paint_xp_footer` pattern computes
  `hud_view_height = screen_height - MSG_LOG_HEIGHT` from the already-
  passed `screen_height` (no signature change).
- `hud._render_ship_identity` / `_render_divider` /
  `_render_help_lines` + `_SPACE_HELP_LINES` — the exploration band,
  both dividers, and D, unchanged painters at new reserved rows.
- Test scaffolding to mirror: `_ground_weapons_ctx` (SimpleNamespace
  ctx fixture), `FrameBuffer(SCREEN_WIDTH + HUD_WIDTH)` (the
  glyph-budget law), `xp_footer_row` = `hud_view_height - 2`.

### Brief clarifications bound from code facts

1. **The space region geometry**: both space A bands need exactly 5
   rows (exploration: ship name/location/date/Fuel/Spd; combat:
   mode/AP/STIM/Evade/Pow) → `SPACE_BAND_Y = 2`, `SPACE_BAND_ROWS =
   5` (row 1 blank under the title, matching the ground pair), the
   A-close divider at `SPACE_CORE_Y - 1 = 7` on BOTH panels, core
   rows 8-11, `SPACE_WEAPONS_Y = 12`. No PLAYER label on the space
   core — the brief's B lists hull/shield/cargo/status only, so the
   label dies with `_render_player_block` (both panels' B starts at
   the Hull row).
2. **Hull paints ABOVE Shield** in the shared painter: the brief and
   the doc's space sketch list Hull first everywhere (combat's legacy
   Shd-above-Hull order swaps; parallels the ground core's
   HP-above-Armor). The row format is hud_combat's verbatim — `Hull
   {bar} {cur}/{max}` in the color trio, `Shd  {bar} {cur}/{max} +N`
   with the S-key white indicator — so exploration's old ALIGNED hull
   row dies (one shape, the fight's, per "in hud_combat's shape").
3. **The meter painter always consumes both rows** — the shield row
   stays BLANK when the ship has none (`max_shields == 0`): the
   same-rows law's "one row-set" means B is 4 rows for every ship, so
   the C anchor is a constant and rows below never shift when shield
   modules change at a fitting screen (item 13's blank-when-empty law
   extended to the meter; legacy combat omitted the row, but the
   shieldless case is `starter`-hull common and the omission would
   make SPACE_WEAPONS_Y loadout-dependent). Both panels share the
   condition (data-driven, mode-independent) so the boundary pin
   holds for every ship.
4. **The C budget is per-loadout**: `space_weapons_rows(n) = 1 + 3n`
   (the WEAPONS title + `_render_weapon_row`'s exact 3 rows/weapon),
   read from the ship's flown weapons on exploration and
   `weapon_list` in the fight. Doc 56 SETTLED 18 retired slot counts,
   so no constant max exists to reserve against; per-loadout sizing
   lands the C-close divider and D's start at the SAME y on both
   panels (the fight's block exactly fills its budget) and never
   wastes blank rows. The C-close divider replaces the block's
   trailing spacer row — item 16's ground pattern, zero row cost.
5. **`[ESC] Pause` joins the space fight's ACTIONS** (ledger #1:
   "help lines + ACTIONS pairs, all modes" — Phase 1 shipped the
   ground pair + the space help list; the space fight's ACTIONS was
   left for this brief to wire). Ruled prose completing its sweep,
   appended last as ground carries it; called out on the playtest
   checklist.

### Duplication hotspots and DRY strategy

1. **The shield-max/free-regen computation.** Exploration hand-rolling
   `base_shield_max + module bonuses` would drift from the fight init
   and the shield bubble. **Fix:** lazy-import
   `_calc_max_shields`/`_free_shield_regen` from `combat._stats` (the
   pygame_overlay precedent) — one formula feeds all three surfaces.
2. **The divider span.** Four new divider call sites (A- and C-close
   on both panels) could each hand-roll a rule. **Fix:**
   `hud._render_divider` stays the one divider painter (ground's
   pattern); every close calls it.
3. **The C budget computed twice** (exploration from
   `owned_ship.weapons`, the fight from `weapon_list`) drifting when
   the weapon-row shape changes. **Fix:** one `space_weapons_rows`
   helper in hud_core beside the constants; both panels pass their
   lens on the same loadout.

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
