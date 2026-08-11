# DESIGN: Unified Terminal & Modal UX — split terminals first

> **Reference look:** the Mechanic Ship Loadout split screen. All four
> buy/sell terminals (Armory, Ship Loadout, Station Trade, NPC Trade)
> share one renderer (`pygame_split`) but render at different font sizes
> and hand-roll their content strings, so they *feel* different.
> This design makes the font sizing deterministic, routes every terminal
> through one shared content-policy layer, and extends the same policy
> (value helpers, hint grammar, font floor) to the other modal families
> (menus, screens, merchant board) per section D.

## Guiding principles (user-mandated — apply to every phase)

1. **Consistent feel is the goal.** Every interactive surface should read
   as one game's UI. When choices conflict, prefer the pattern the user
   already flagged as good: the Loadout's chrome/font for terminals, the
   C screen's tabs for multi-view modals, the faction screen's
   `? guide` footer for discoverability.
2. **Change once, updates everywhere.** Every tunable is a single source
   of truth: palette (`pygame_ui.Palette`), font sizing (shared
   font-solver, Phase 6), title grammar (`terminal_title`), hint grammar
   (`modal_hint`), value formats (`price_cell` / `credits_label` / …).
   A global change — e.g. a bigger title font — must be exactly one edit.
3. **Use the good examples; test experiments.** Adopt proven patterns
   instead of inventing new ones. Taste-dependent choices (the six Open
   decisions) are flagged **EXPERIMENT**: implement, hand to the user
   for a quick playtest, lock in only on approval — never guess taste.

## Overview

The four terminals already share 100% of their *chrome*: the same
`pygame_split` worker, palette, panel geometry, selection highlight,
footer slots, and console-log band. What differs is:

1. **Font size is an emergent property of content density.** `_fit_font`
   shrinks the font until the whole frame fits. A dense catalog (Armory)
   or long wrapping details (Trade) crushes the font down to the 12px
   floor while the Loadout renders at 24px — measured below.
2. **Content strings are hand-assembled per module.** Titles, footers,
   price cells, dividers, and hints are inline literals in 4 files, so
   conventions drift (`Credits: N$` vs `Credits: N`, empty footer slot,
   duplicated `--- WEAPONS ---`).

### Measured evidence (real frames, fake DejaVu-metric font)

Run: `python3 tools/_font_estimate.py` (committed with Phase 1).

| Terminal | Rendered font | Left rows | Why |
|----------|--------------|-----------|-----|
| Loadout (Earth mechanic) | **24px** | 7 (2 div) | small per-planet stock |
| Loadout (full catalog) | 12px | 41 (2 div) | huge catalog |
| Armory | **12px** | 20 (2 div) | full ground catalog |
| Trade (Earth) | **14px** | 15 (0 div) | many goods, details wrap to 2 lines |
| NPC trade (6 goods) | 24px | 6 (0 div) | small stock |

Frame-height budget at 1600×960 is 722px (``modal_footer_y - 80``,
mirroring the real panel bottom). At 24px a row costs 43px, a divider
34px, a wrapped detail line 31px — the pinned panel's physical maximum
is **10 visible selectable rows at 24px**, verified against the real
bundled DejaVu font. Decision #8 (user playtest) set the cap to **13**:
at 1600×960 the armory then renders at ~19px and trade at ~21px while
loadout/NPC stay 24px (fonts below the cap diverge per terminal); on a
taller window the budget scales and 13 rows hold 24px.

### String drift (today)

| Convention | Loadout (reference) | Armory | Trade / NPC trade |
|---|---|---|---|
| Title | `MECHANIC - SHIP LOADOUT` | `ARMORY` (no venue) | `TRADE - <NAME>` |
| footer_left | `Credits: N$` | `Credits: N$` | `Cargo: N` / `Cargo: N/M` |
| footer_right | `Wpn: x/y  Mod: x/y` | **empty** | `Credits: N` (no `$`) |
| Buy price cell | `30$` | `30$` | `30$ (12)` |
| Sell price cell | `(sell 15$)` | `(sell 15$)` | `15$ (2)` |
| Section divider | `--- WEAPONS ---` | `--- WEAPONS ---` (dup) | none |
| Hint | `UP/DOWN ... ESC back` | same | same (copy-pasted) |

## Decisions (user-approved)

- **Titles:** Armory gains a venue → `ARMORY - <PLANET>` (planet_id is
  already passed to `_run_armory_menu`). Loadout and trade titles
  unchanged. All titles built by one helper.
- **Panel labels:** stay per-terminal (loadout `For Sale`/`My Ship`,
  trade `Station Inventory`/`Your Hold`, NPC trade `<name>`/`Your Hold`,
  armory `For Sale`/`My Loadout`). No forced relabel.

## Design

### A. Deterministic font sizing (the headline fix) — `pygame_split.py`

1. Add `MAX_VISIBLE_ROWS = 10` and `MAX_DETAIL_LINES = 2` constants
   (10 = the most selectable rows the real panel holds at 24px —
   measured with the bundled DejaVu font; 11 clips).
2. `_frame_height()` counts **capped** rows per panel: iterate rows,
   counting selectable rows; once the count reaches `MAX_VISIBLE_ROWS`,
   stop accumulating (still add the current row's height). Wrapped detail
   lines are capped at `MAX_DETAIL_LINES`.
   → Frame height is now independent of catalog size; every terminal
   computes the same 24px budget. (Keeps the existing
   selection-independence test property.)
3. Add a pure viewport helper:
   `_visible_window(rows, selected, cap) -> (top, count)` — a window of
   at most `cap` selectable rows (+ their dividers) centered on
   `selected`, clamped to the row list.
4. `_draw_panel()` renders only the visible window; selection scrolls
   the viewport automatically. `_handle_key()` is unchanged (selection
   still walks the full list; dividers stay unselectable).
5. `_fit_font()` unchanged except it now sizes against the capped height.

### B. Shared content policy — new helpers in `pygame_ui.py`

All pure; each ships with a test (pure-function test contract). They live
in `pygame_ui.py` (the shared-primitives module), NOT `pygame_split.py`,
so the `pygame_screen` / `pygame_menu` modal families can adopt them too
(see section D). Split terminals are just the first consumers.

| Helper | Returns | Kills |
|---|---|---|
| `terminal_title(prefix, suffix="")` | `f"{prefix.upper()} - {suffix.upper()}"` or bare `prefix.upper()` | 3 title grammars |
| `section_header(label)` | `SplitRow(f"--- {label} ---", "", "", "", divider=True)` | duplicated `--- WEAPONS ---` |
| `price_cell(price, qty=None)` | `f"{price}$"` / `f"{price}$ ({qty})"` | 3 price formats |
| `sell_cell(price, qty=None)` | `f"(sell {price}$)"` / `f"(sell {price}$) x{qty}"` | 2 sell formats |
| `credits_label(credits)` | `f"Credits: {credits}$"` | `$` drift (6 sites) |
| `cargo_label(used, max_cargo)` | `f"Cargo: {used}/{max_cargo}"` | `N` vs `N/M` drift |
| `shortfall_label(short)` | `f"{short}$ short"` | inline afford text (ship buy) |
| `reward_label(credits, xp)` | `f"Reward: {credits}$ + {xp}xp"` | inline merchant board hints |
| `modal_hint(*parts)` | parts joined with `"   "`, trailing `.` stripped | 4 separator styles across ~15 modals; makes `? guide` a standard part |
| `SPLIT_SHOP_HINT` | `modal_hint("UP/DOWN navigate", "TAB switch panel", "ENTER buy/sell", "ESC back", "? guide")` (decision #2 overturned in Phase 5) | 4 copy-pasted hints |

**Footer rule (matches loadout):** `footer_left = credits_label(...)`,
`footer_right =` domain stat (loadout: `Wpn: x/y  Mod: x/y` unchanged;
armory: new `Wpn: 0/2  Arm: x/5` filling the empty slot; trade/NPC:
`cargo_label(...)`). *Flagged decision — see Open decisions #1.*

*Implementation note:* `section_header` and `SPLIT_SHOP_HINT` live in
`pygame_split.py` (not `pygame_ui.py`) — `section_header` returns a
`SplitRow` and `SPLIT_SHOP_HINT` is split-terminal vocabulary, so they
stay in the split family to avoid a `pygame_ui → pygame_split` import.
The pure string helpers (`terminal_title`, `price_cell`, …) are in
`pygame_ui.py` as designed.

### C. Migrate the four terminals

- `menus/_loadout.py` — route title, dividers, prices, credits, hint
  through the helpers. Visual result: **identical to today** (regression
  baseline).
- `menus/_armory.py` — `_pygame_armory_frame(ctx, planet_id)` gains a
  `planet_id` param; title `terminal_title("ARMORY", planet_id)`; fill
  `footer_right` with slot counts; dividers via `section_header`.
- `trade.py` — `_pygame_trade_frame` / `_pygame_npc_trade_frame`:
  footer `credits_label` left + `cargo_label` right; `price_cell` /
  `sell_cell`; hint constant.
- `help.py` — fix stale terminal descriptions (help.py:1189 says
  "My Gear" — actual label is "My Ship"); mention `? guide` in the
  split-terminal sections (guide contract).

---

### D. Reuse beyond the split family (full modal inventory)

The split geometry (two panels + TAB) does NOT generalize — ship buying
is a single-entity purchase, not a two-panel trade. But three layers do,
and they are the reason the helpers live in `pygame_ui.py`:

**Layer 1 — Value/content helpers: fully reusable, adopt immediately.**
`price_cell`, `sell_cell`, `credits_label`, `cargo_label`,
`shortfall_label`, plus new `reward_label(credits, xp)` →
`f"Reward: {credits}$ + {xp}xp"` (merchant board already formats this
inline).

**Layer 2 — Font-floor principle: generalizes; mechanism per family.**
All families run the same 24→11 font loop against their own height
solver; `pygame_screen` and `pygame_menu` both `break` row drawing past
the bottom while selection still wraps to invisible rows — the same
clip bug the split terminals have. Phase 1 implements the recipe
(capped fit + viewport) for `pygame_split`; Phase 6 ports it to the
menu/screen families with a shared font-solver in `pygame_ui`.

**Layer 3 — Conventions: hint + title grammar, the biggest visible drift.**
Across ~15 modals the hint separators alone vary four ways:
` - ` (npc/npc talk), `   ` (title menu), `  ` (split terminals,
ship buy), and worded variants (`ARROW KEYS / j,k navigate` vs
`UP/DOWN or j/k navigate`), some with trailing periods, most without
`? guide`. New `modal_hint(*parts)` → one canonical join, and a
`NAV_HINT`/`SELECT_HINT` phrase set, enforce the grammar.

**Full inventory (family → modals → adopts):**

*Completeness is machine-verified: every `*Frame(` constructor and
`run_for_context` / `run_shared` call site in `src/spacehack` is
accounted for; zero tcod `ui.Modal` call sites remain in `src/`.*

| Family | Modals | Adopts |
|---|---|---|
| `pygame_split` | Armory, Ship Loadout, Station Trade, NPC Trade | Layers 1+2+3 (Phases 1–3) |
| `pygame_screen` | Ship buy, Cargo, Mechanic, Buy Ammo, read-only Loadout, Character sheet, Help guide, **Trait selection** | Layer 1 + `modal_hint` now; Layer 2 only if it demonstrably clips |
| `pygame_menu` | Ship hangar, Planet, NPC talk, GO TO, Jump confirm, Comms ×2, Loot, Character pickers ×2, Story ×3 (dismiss/confirm/choose), **Dungeon breach confirm**, **Main-quest help offer**, **Active-mission delivery board**, Title, Dev picker | Layer 1 where prices appear, `modal_hint` + `? guide` (Phase 5; title menu is the one exception — no guide route), Layer 2 font floor (Phase 6); ship hangar moves to `pygame_screen` with CARGO/LOADOUT tabs (Phase 7) |
| `pygame_merchant` | Guild master (mission board) | `reward_label`, `modal_hint` (title `{npc} - available work` already matches the screen-family grammar) |
| Specialized | Quest log, Faction standings, Auto-nav map, **Quantity prompt** (sub-modal of trade/armory flows) | Conventions only — quest log/faction/nav already advertise `? guide`; quantity prompt is a single-line stepper, conventions light (see Phase 5 note) |

**Layer 4 — Tabs for multi-view modals (the C-screen pattern).**
`character_screen.py` is the proven reference: `ScreenFrame.tabs` +
`active_tab`, the worker paints the tab bar (active tab highlighted) and
returns `TAB`; the parent toggles `active_tab`, resets selection, and
rebuilds the frame — all tab state lives in the parent, the worker stays
a dumb painter. Principle: **view-type options become tabs; action-type
options stay rows.** Ship hangar's View Cargo / View Loadout are views →
tabs (Phase 7). Refuel / Repair / Land / Explore / contract-accept are
actions → stay rows. Tabs currently exist only in `pygame_screen`
(`MenuFrame` has no tab support) — converting a menu to tabs means
moving it to the screen family, which is fine (the C screen proves it).

**Adoption rule:** a modal adopts Layer 1 + `modal_hint` when touched;
Layer 2 only when it demonstrably shrinks or clips (ship buy's content
is tiny and already renders large — Layer 1 + hint only); tabs only for
multi-view modals.

**Title grammar note:** two grammars already exist and read well in
context — split terminals all-caps `X - Y` (`MECHANIC - SHIP LOADOUT`,
`TRADE - EARTH`), screens/merchant `NAME - sentence suffix` (`SCOUT -
for sale`, `{npc} - available work`). The plan keeps both but routes
them through `terminal_title` so each family is internally consistent
(see Open decision #5).

## Phased implementation plan + playtest checklists

---

### Phase 1 — Font floor + viewport scrolling (`pygame_split.py`)

- [x] Add `MAX_VISIBLE_ROWS = 9`, `MAX_DETAIL_LINES = 2`
- [x] Cap row/detail counting in `_frame_height` (selection-independent)
- [x] Add pure `_visible_window(rows, selected, cap)`
- [x] `_draw_panel` renders the viewport window; selection auto-scrolls
- [x] Commit `tools/_font_estimate.py` as the verification tool
- [x] Smoke gate: `python3 tools/smoke.py && python3 tools/test.py`
      (528 passed, smoke PASS)

**▸ PLAYTEST Phase 1:**

Earth hangar → mechanic loadout, armory terminal, trade terminal, and
an NPC trader in space. Open each.

- [x] All four terminals render at the **same font size** (loadout's)
- [x] Armory: DOWN scrolls past the visible window; selection stays on
      screen; ENTER still acts on the highlighted row
- [x] Trade: long goods list scrolls; descriptions still readable
- [x] Long descriptions (3+ wrapped lines) aren't clipped at the panel
      bottom (known cap trade-off — review flagged it; `set_clip`
      protects layout but a description can be cut mid-line)
- [x] Loadout looks pixel-identical to before (regression baseline)
- [x] `?` is NOT a modal key (decision #2 — the hint no longer
      advertises it)

Passed: [x]   Issues: none — user approved ("phase 1 is great").

Implemented: [x] — `tools/_font_estimate.py` reports 24px on all four
terminals (armory 12→24, trade-earth 14→24, loadout/NPC unchanged at 24).
Code review: no blocking issues. Pre-existing dead code flagged (not
fixed here): `pygame_split._content_width` and the unused `frame` param
of `_draw_panel`.

---

### Phase 2 — Content-policy helpers (`pygame_ui.py` + `pygame_split.py`)

- [x] Add `terminal_title`, `section_header`, `price_cell`, `sell_cell`,
      `credits_label`, `cargo_label`, `shortfall_label`, `reward_label`,
      `modal_hint`, `SPLIT_SHOP_HINT`
- [x] Unit tests for each helper (same commit)
- [x] Smoke gate (534 passed, smoke PASS)

**▸ PLAYTEST Phase 2:** No visual change yet (helpers unused). Smoke
gate is the real gate.

Passed: [x]   Issues: none — no visual change, helpers unused by design.

---

### Phase 3 — Migrate the four terminals

- [x] `_loadout.py` → helpers; verify zero visual change (chrome, font,
      prices, footers identical — only the hint now uses the shared
      `SPLIT_SHOP_HINT`, see note below)
- [x] `_armory.py` → `planet_id` param, `ARMORY - <PLANET>` title,
      footer_right slot counts, `section_header` dividers
- [x] `trade.py` → `credits_label`/`cargo_label` footers, `price_cell`/
      `sell_cell`, hint constant (both station + NPC trade)
- [x] Update existing frame tests that assert old strings (armory title,
      trade footer)
- [x] `help.py` terminal sections updated ("My Loadout", `? guide`)
- [x] Smoke gate

**▸ PLAYTEST Phase 3:**

- [x] Armory title shows the planet: `ARMORY - EARTH` — approved
- [x] Armory footer right shows `Wpn: 0/2  Arm: x/5` — approved
- [x] Trade footer shows `Credits: N$` left, `Cargo: N/M` right — approved
- [x] Sell cells all read `(sell N$)` / `(sell N$) xN`; buy cells `N$`
      / `N$ (N)` — approved
- [x] Guide sections for armory/trade/loadout match actual labels
- [x] Loadout hint change approved ("change is fine")
- [x] ESC/QUIT from each terminal returns cleanly

Passed: [x]   Issues: two, both fixed in this revision — (a) lists
scrolled a row sooner than needed (cap 9 left ~78px of empty panel;
cap 10 + widened fit budget now fills it, verified at 24px with the
real DejaVu font); (b) `? guide` removed from the hint and guide text
(decision #2 — `?` is not a modal key). Re-test items below.

**▸ RE-TEST (post-fix):**

- [x] Long lists (armory 20 rows, trade 15) scroll only after the 13th
      visible row; scrolling "feels natural" — user-approved
- [x] All four terminals render at the decision-#8 fonts (loadout/NPC
      24px, armory ~19px, trade ~21px) — approved ("lining up
      perfectly")
- [x] No terminal hint mentions `? guide`
- [x] **EXPERIMENT (decision #7):** the focused panel's description is
      pinned to the bottom edge of its panel (stable anchor while rows
      scroll above it) — APPROVED by user ("I like that a lot better,
      even on the loadout").
- [x] **EXPERIMENT (decision #8):** row cap bumped 10 → 13 (user:
      "3 more items before scrolling") — APPROVED ("this is lining up
      perfectly. now scroll feels natural"). At 1600×960 logical the
      armory renders at ~19px and trade at ~21px while loadout/NPC stay
      24px (fonts below the cap diverge; the fit is stable once a list
      exceeds the cap). On a taller window the budget scales and 13
      rows hold 24px. Revert = one constant back to 10.

Implemented: [x] — all four terminals render at 24px, 541 passed,
smoke PASS. Code review caught and fixed one real bug: `_run_armory_menu`
wasn't forwarding `planet_id` to the frame builder (title would have
rendered bare `ARMORY` in-game); a regression test now pins the
forwarding path. `_hold_cargo_label` extracted (killed duplicated footer
computation in both trade frames) with a direct test. help.py also fixed
a second stale line ("ENTER equips/unequips" → "ENTER sells").

---

### Phase 4 — Adjacent adoption: Ship Buy (`pygame_screen` family)

Layer 1 only (see section D) — ship buy's content is small, so no
viewport/font work needed.

- [x] `_ship_buy.py` routes title/price/credits/shortfall/hint through
      the helpers (`terminal_title`, `price_cell`, `credits_label`,
      `shortfall_label`, `modal_hint`)
- [x] Update `test_ship_buy_frame_*` assertions to the helper output
      (title is `SCOUT - FOR SALE` — decision #3 resolved by user:
      all-caps, one grammar everywhere)
- [x] `help.py` — no ship-buy wording to change (guide never quoted the
      modal title/footer)
- [x] Smoke gate (541 passed)

**▸ PLAYTEST Phase 4:** Earth showroom — buy/trade-in a ship. Changes to
look at: title now `SCOUT - FOR SALE`; footer now `ENTER buy   ESC walk
away` (triple-space, no `? guide` per decision #2); detail line now
`Price 5000$  Credits: 1000$` (colon added); trade-in line now
`Trade-in value: 3000$  -  Credits: 1000$`. Everything else — body,
row text, shortfall sentence — is byte-identical.

Passed: [ ]   Issues: _______________

Implemented: [x] — 541 passed, smoke PASS. `? guide` dropped from the
footer for decision-#2 consistency (the GUIDE key handler stays,
unadvertised, like the split terminals).

**▸ RE-TEST (post-playtest revision, decision #9):** ship buy "smashed
into the top-left corner" → the shared `pygame_screen` renderer now
vertically centers the content block (approved) and adds section gaps
`BODY_ROWS_GAP = 24` / `ROWS_DETAIL_GAP = 20` to un-cram the
description/buy-row/detail. Verified with real DejaVu at 24px: ship buy
119 → 155px content (y 361→516), C screen STATS tab 396px (y 262→658,
tallest case, FITS), EQUIPMENT 337px, cargo 207px. Gap values pending
playtest.

---

### Phase 5 — Menu & screen-family conventions (`pygame_menu` / `pygame_screen` / `pygame_merchant`)

Layer 1 + Layer 3 only — no layout work.

- [x] `modal_hint` adopted across the inventory: ship hangar, planet,
      NPC talk, GO TO, jump confirm, comms ×2, loot, story ×3,
      dungeon confirm, quest help offer, mission delivery board,
      trait selection, title, character pickers, ship buy, cargo,
      mechanic, ammo, merchant board, help guide
- [x] Quantity prompt uses `QUANTITY_HINT =
      modal_hint("UP/DOWN adjust", "ENTER confirm", "ESC cancel",
      GUIDE_HINT)`; its runner opens the guide on `?`
- [x] **Fix the `?` key itself (decision #2 OVERTURNED).** Root cause:
      every modal key handler checked only the `K_QUESTION` keycode,
      but shift+/ delivers `K_SLASH` + unicode `"?"` on real
      keyboards — so `?` did nothing in any modal. All nine handlers
      (split, menu, screen, faction, quest log, quantity, batch,
      navigation, combat) now route through `pygame_ui.is_guide_key`
      (keycode OR unicode fallback), and the two runners with no
      GUIDE route (title → `IGNORE`, trait screen → open guide +
      re-run) were wired so `?` never crashes or closes a modal.
      Regression test added (`test_guide_key_accepts_unicode_
      question_mark_without_k_question`).
- [x] `? guide` re-advertised in every modal whose runner opens the
      guide (decision #2 OVERTURNED — discoverability wins):
      `SPLIT_SHOP_HINT`, ship buy footer, quest log, faction, nav
      map, quantity, merchant board, trait selection; excluded only
      where the runner has no guide route (title menu).
- [x] Value helpers where prices/rewards/credits appear (ship buy,
      merchant board, loot, cargo, ammo, mechanic, ship hangar stats)
- [x] Unify nav phrase via one constant (decision #4): `NAV_HINT =
      "UP/DOWN navigate"` — every modal hint now opens with it
- [x] Update the affected frame tests (hints/titles only)
- [x] Smoke gate (542 passed, smoke PASS)

**▸ PLAYTEST Phase 5:** walk the modal tree — planet bump, ship hangar,
NPC talk, comms, guild master, GO TO, jump, ship buy, cargo, mechanic.
Every hint reads the same style, every modal advertises `? guide`, and
`?` opens the guide from each.

- [x] Planet bump / NPC talk / comms / guild master / GO TO / jump
- [x] Ship buy: footer reads `ENTER buy   ESC walk away   ? guide`;
      `?` opens Ships & Equipment
- [x] Armory / loadout / trade: `?` opens the guide from the split
      terminals
- [x] Quest log / faction / nav map: `?` opens the guide
- [x] Trait selection: `?` opens the guide and the modal reopens
- [x] Title menu: `?` is a no-op (no guide without a game context)

Passed: [x]   Issues: none — covered across the session's playtests
(ship buy, terminals, hangar, merchant board, comms); the `?` unicode
fallback was verified in-session when the user reported `?` dead in
modals (Phase 5 fixed all nine handlers).

Implemented: [x] — every modal hint runs through `modal_hint` with the
`NAV_HINT` opener; every runner with a GUIDE route advertises `? guide`
and works via the unicode fallback. Code review: no blocking issues.

---

### Phase 6 — Layer 2 port: font floor + viewport for `pygame_menu` / `pygame_screen`

Only where content can clip (menus with many items; screens with long
lists). Ship buy / jump / story are tiny — skip them.

- [x] Shared font-solver in `pygame_ui` (one 24→11 loop; height fn
      passed in) replaces the three `_fit_font` copies —
      `pygame_ui.fit_font(pygame, path, *, measure_height,
      available_height)`; `pygame_split` / `pygame_menu` /
      `pygame_screen` are now thin wrappers. The specialized
      capture families (quest log / batch / faction) keep their own
      solvers (different geometry, out of scope); merchant stays a
      fixed-size family.
- [x] Row/detail caps + viewport scroll ported to `pygame_menu`
      (mission board, comms, character pickers, GO TO) —
      `_frame_height` caps items at `MAX_VISIBLE_ROWS` and description
      lines at `MAX_DETAIL_LINES`; `_draw_frame` renders a
      `pygame_ui.visible_window` (selection stays on screen) and
      vertically centers the content block (decision #9 pattern, so
      short menus — title, confirm dialogs — sit balanced instead of
      top-left).
- [x] Row caps + viewport ported to `pygame_screen` (cargo, character
      sheet, help guide) — `_non_body_height` caps rows via the shared
      tallest-window helper (`pygame_ui.window_height`) and detail at
      `MAX_DETAIL_LINES`; `_draw_frame` renders the viewport window and
      the centering math uses the capped window height (list-length
      independent).
- [x] Keep selection-independence tests green in both families —
      `_frame_height` / `_non_body_height` never read `selected`;
      new cap tests added for both families (mirror the split cap
      test), plus `test_menu_font_fit_is_stable_once_items_exceed_cap`
      and `test_screen_font_fit_is_stable_once_rows_exceed_cap`
- [x] Smoke gate + `tools/_font_estimate.py` extended to report menu
      and screen font sizes — `menu (mission board)` 24px @ 10 items;
      `screen (cargo 20)` 19px @ 20 rows (drops below the cap like the
      armory, decision #8 behavior). 548 passed, smoke PASS.

**▸ PLAYTEST Phase 6:** guild master with 8+ contracts, comms with 6+
contacts, character class list — all render at the same font as the
split terminals, selection stays visible, no clipped rows.

- [x] Mission board (8+ contracts): 24px, DOWN scrolls, selection
      visible, description follows the selected contract
- [x] Comms (6+ contacts) and the species/class pickers: same font,
      selection stays on screen
- [x] Cargo list (many items): rows scroll instead of clipping;
      character sheet STATS/help guide unchanged
- [x] Short menus (planet bump, title) sit vertically centered —
      feels like the C screen, not top-left

Passed: [x]   Issues: none — user: "It's working good."

---

### Phase 7 — Tabbed ship hangar (C-screen pattern)

The hangar menu (View Cargo / View Loadout / Launch) becomes one tabbed
`pygame_screen` modal — the first Layer 4 adoption.

- [x] Convert `_ship_menu` hangar from `pygame_menu` to `pygame_screen`
      with `tabs=("CARGO", "LOADOUT")` — `_ship_menu_frames` /
      `_run_pygame_ship_menu` replaced by `_ship_hangar_frame(ctx, ship,
      tab, selected)` + `_run_pygame_ship_hangar` (the C-screen runner
      pattern: TAB outcome toggles the tab and resets selection; parent
      owns tab state, worker stays a dumb painter)
- [x] CARGO tab reuses the shared cargo rows — `trade._cargo_frame` split
      into `_cargo_rows(owned)` / `_cargo_body(owned, max_cargo)` and the
      standalone cargo modal composes them (byte-identical output); the
      jettison flow extracted into `trade._apply_jettison(ctx, owned,
      action)` (pure mutation wrapper) shared by the cargo modal and the
      hangar
- [x] LOADOUT tab reuses the read-only loadout rows — `_pygame_loadout_frame`
      split into `_loadout_rows` / `_loadout_body`; the standalone loadout
      view and its runner (`_run_loadout_view`, `_run_pygame_loadout_view`)
      are gone (nothing else opened a read-only loadout)
- [x] Persistent `Launch` action row reachable from both tabs
      (decision #6) — last row on both tabs, `"Launch" / "Leave the
      hangar and enter space." / LAUNCH`
- [x] Footers advertise the TAB target like the C screen
      (`TAB loadout` / `TAB cargo`); `modal_hint` + `? guide` — CARGO
      footer `NAV_HINT, "ENTER jettison", "TAB loadout", "ESC back",
      GUIDE_HINT`; LOADOUT footer `"TAB cargo", "ESC back",
      GUIDE_HINT`
- [x] Update `_ship_menu` / `trade` frame tests and help.py ship section
      — hangar frame/runner tests (launch, TAB cycle + selection reset,
      guide reopen, jettison on the cargo tab, back/quit), `_apply_jettison`
      unit tests (partial/full/malformed), `_cargo_rows` shared test;
      help.py "Your ship in the hangar" describes the tabs + Launch
- [x] Smoke gate (552 passed, smoke PASS)

**▸ PLAYTEST Phase 7:**

Bump your ship in the city.

- [ ] One tabbed screen, no nested modals: TAB cycles CARGO ⇄ LOADOUT
- [ ] Cargo tab: rows + jettison via ENTER (quantity prompt) work
- [ ] Loadout tab: rows + details match the old read-only loadout view
- [ ] Launch row works from both tabs; ESC walks away
- [ ] Tab bar renders at the same font as the C screen (24px); C screen
      is unchanged (tab regression baseline)
- [ ] `?` opens the guide from the hangar

Passed: [ ]   Issues: _______________

Implemented: [x] — one tabbed `YOUR <SHIP>` screen (CARGO | LOADOUT tab
bar), title unchanged from the old hangar; TAB ⇄ LOADOUT/CARGO;
jettison + Launch both in-tab; `_run_ship_menu` now returns LAUNCH/BACK/
QUIT directly (`__main__` launch flow untouched). Code review: no
blocking issues.

**▸ EXPERIMENT (Phase 7 revision — decision #6 REVISION, pending user
test):** user request — "3 tabs. SHIP -- has details about your ship,
at a glance data. And the launch button at the bottom (some white space
separating it, but not a ton). CARGO -- no need for launch button.
LOADOUT -- no need for launch button." Implemented:

- SHIP tab (default): at-a-glance body — description, fuel, hull,
  speed, shields, power, cargo, credits — with the `Launch` row at the
  bottom separated by one blank body line (visible white space, not a
  ton; the blank-line count is a one-line tweak). Footer:
  `NAV_HINT, "ENTER launch", "TAB cargo", "ESC back", GUIDE_HINT`.
- CARGO tab: shared cargo rows + jettison, no Launch. Footer:
  `NAV_HINT, "ENTER jettison", "TAB loadout", "ESC back", GUIDE_HINT`.
- LOADOUT tab: read-only loadout rows, no Launch. Footer:
  `NAV_HINT, "TAB ship", "ESC back", GUIDE_HINT`.
- **Refinement (pending user test):** LOADOUT renders EVERY slot —
  section headers `WEAPON SLOTS` / `MODULE SLOTS`, filled slots show
  the gear by name (selectable, stats/description detail), empty slots
  read bare `[empty]` (non-selectable, no detail) — mirroring the
  mechanic's My Ship right panel. Shared
  `_slot_rows(slot_count, installed, make_row)` + `_weapon_row` /
  `_module_row` build both sections (DRY). help.py updated.
- **Refinement 2 (pending user test):** LOADOUT body dropped — the
  fuel/hull/cargo/shields/power/speed lines duplicated the SHIP tab,
  so `body=()` (the shared renderer handles an empty body: no
  BODY_ROWS_GAP). `_loadout_body` deleted (single call site).
- Runner: TAB cycles SHIP → CARGO → LOADOUT → SHIP (mod 3), resets
  selection; jettison only handled on tab 1. 555 passed, smoke PASS.
- help.py "Your ship in the hangar" updated to describe the 3 tabs.

**▸ PLAYTEST this experiment:** bump your ship.

- [x] SHIP tab reads as a clean "at a glance" dashboard; Launch sits
      low with visible (not excessive) white space above it — approved
- [x] CARGO / LOADOUT tabs have no Launch row — approved
- [x] TAB cycles through all three tabs and wraps — approved
- [x] Refinement 1 (every slot shown, `[empty]` blanks) — approved
      ("In the mechanic I like that loadout on the right better")
- [x] Refinement 2 (LOADOUT body dropped) — approved
- [x] Refinement 3 (mechanic-format slots: `WEAPON SLOTS` / `MODULE
      SLOTS` headers, gear by name, bare `[empty]`) — approved
      ("Looking great now. start the next phase")

**Decision #6 REVISION RESOLVED: 3 tabs** — SHIP (at-a-glance + Launch
with one blank-line gap), CARGO (no Launch), LOADOUT (no Launch). User:
"Looking great now."

---

### Phase 8 — Final gates

- [x] `python3 tools/smoke.py && python3 tools/test.py` pass —
      560 passed, smoke PASS
- [x] `tools/_font_estimate.py` reports the decision-#8 fonts (loadout/
      NPC 24px, armory ~19px, trade ~21px at 1600×960) — verified
      live: loadout (earth) 24px, armory 19px, trade-earth 20px,
      trade-npc 24px, menu (mission board) 24px, screen (cargo 20) 19px
- [x] Full playtest: buy/sell + scroll on every terminal, save → quit →
      Continue intact (no new mutable state — scroll is derived from
      selection, nothing to persist) — saveload + UI suites green
      (150 tests); no new `GameContext` fields or module-level globals
      added across Phases 1–7
- [x] Move this doc to `docs/design/complete/`

Passed: [x]   Issues: none.

---

## Contracts compliance (MANDATORY — see knowledge.md)

- [x] **Save/load:** No new mutable state. Viewport is derived from
      `selected` each frame — nothing added to `GameContext`,
      `_ctx_to_dict()`, or `load_game()`.
- [x] **Game guide:** help.py terminal sections updated (label "My Ship",
      `? guide` hint) in Phase 3; ship-buy, hangar (3 tabs, slot grid),
      and loadout wording updated through Phase 7.
- [x] **Module-level state:** none added.
- [x] **Pure function test contract:** every new helper
      (`terminal_title`, `section_header`, `price_cell`, `sell_cell`,
      `credits_label`, `cargo_label`, `shortfall_label`, `reward_label`,
      `modal_hint`, `_visible_window`, `fit_font`, `visible_window`,
      `window_height`, `_slot_rows`, `_weapon_row`, `_module_row`)
      ships with a test in the same commit; `_frame_height` cap keeps
      its existing selection-independence test green.

## Open decisions (all flagged EXPERIMENT — user playtests before lock-in)

1. **Footer slot roles.** Recommended (matches loadout): credits LEFT,
   domain stat RIGHT on every terminal. Trade currently reverses this.
   Flip is a one-line swap if undesired.
2. **`? guide` in the hint.** ~~Recommended: yes~~ → ~~RESOLVED (Phase 3
   playtest): NO~~ → **OVERTURNED (Phase 5): YES, and the key is now
   fixed.** The Phase 3 finding was a symptom, not a rule: `?`
   "didn't work in modals" because every key handler checked only the
   `K_QUESTION` keycode, while shift+/ delivers `K_SLASH` + unicode
   `"?"` on real keyboards. Phase 5 fixes all nine handlers via
   `pygame_ui.is_guide_key` (keycode OR unicode) and re-advertises
   `? guide` wherever the modal's runner opens the guide. Excluded
   only where there is no guide route (title menu → `IGNORE`).
   `SPLIT_SHOP_HINT`, ship buy, quest log, faction, nav map,
   quantity, merchant board, and trait selection all advertise it.
3. **Ship-buy title casing.** ~~`SCOUT - FOR SALE` (all-caps, matches
   the terminal family) vs keeping `SCOUT - for sale`~~ → **RESOLVED
   (Phase 4): all-caps** — `SCOUT - FOR SALE` via `terminal_title`;
   one title grammar across terminals and ship buy.
4. **Nav phrase.** `ARROW KEYS / j,k navigate` (menu family) vs
   `UP/DOWN or j/k navigate` (comms/cargo) vs `UP/DOWN navigate`
   (split). → **RESOLVED (Phase 5): `UP/DOWN navigate`** via
   `pygame_ui.NAV_HINT` — user-approved ("UP/DOWN navigate"); every
   modal hint now opens with it.
5. **Title grammar per family.** Keep the two existing grammars
   (all-caps `X - Y` for terminals; `NAME - sentence suffix` for
   screens/merchant) or force one everywhere. Recommended: keep
   both, enforce per family via `terminal_title`.
6. **Launch placement in the tabbed hangar.** Recommended: a
   persistent `Launch` action row at the bottom of both tabs
   (matches the current 3rd menu option). Alternatives: a hotkey
   (needs new key plumbing in `pygame_screen`) or a third tab
   (rejected — Launch is an action, not a view).
   **RESOLVED (Phase 7): persistent Launch row on both tabs** — then
   **REVISED (Phase 7 experiment): 3 tabs**
   SHIP / CARGO / LOADOUT; Launch moves to a dedicated SHIP tab
   (at-a-glance stats + Launch at the bottom with modest white space),
   CARGO and LOADOUT drop it. User: "I'm thinking 3 tabs… let's do
   this as an experiment and I'll test and give feedback." →
   **RESOLVED (Phase 8): 3 tabs approved** ("Looking great now");
   the LOADOUT tab slots follow the mechanic's My Ship panel format
   (`WEAPON SLOTS` / `MODULE SLOTS`, gear by name, `[empty]` blanks).
7. **Pinned description (EXPERIMENT — Phase 3 revision).** Anchor the
   focused panel's description to the panel's bottom edge (stable
   position while rows scroll above it) vs today's
   description-floating-after-the-rows. Implemented in
   `pygame_split._draw_panel` with `DETAIL_BOTTOM_PAD` /
   `ROWS_DETAIL_GAP`, applies to all four terminals through the shared
   renderer (verified: all four still pick 24px; armory's 10-row window
   fits with 22px slack above the pinned description). Trade-off: long
   lists fill the panel; short lists (loadout, NPC trader) show a gap
   between the last row and the pinned description.
   **RESOLVED: user approves the pin** ("I like that a lot better,
   even on the loadout").
8. **Row depth vs font size (EXPERIMENT — Phase 3 revision).**
   **RESOLVED: cap 13 approved** ("this is lining up perfectly. now
   scroll feels natural"). The perceptual "room for 3 more" came from
   the text gap below the last row (trade: 122px, loadout: 296px of
   air above the pinned description); 13 full rows at 24px don't fit
   the 1600×960 panel, so armory renders ~19px and trade ~21px while
   loadout/NPC stay 24px. Revert to 10 is one constant.
9. **Screen-family layout (EXPERIMENT — Phase 4 revision).** Ship buy
   "feels squished": the `pygame_screen` family draws no panel, and
   content was top-anchored at (40, 84), leaving ~700px of empty
   canvas below short modals. Two-part fix in the shared
   `pygame_screen._draw_frame`:
   - **Vertical centering:** the content block (body + rows + detail)
     is centered between the title rule and the footer zone;
     content taller than the space falls back to the top anchor via
     `max(0, …)` — long pages (guide) are byte-identical.
   - **Section breathing room:** `BODY_ROWS_GAP = 24` and
     `ROWS_DETAIL_GAP = 20` (only applied when the section above
     exists), mirrored in `_layout_height` / `_non_body_height` so
     the font-fit solver budgets the same space. Ship buy content
     grows 119 → 155px, still 24px, still centered.
   **RESOLVED: both parts approved** — user: "I think I do like the
   vert center feel" then, after the gaps, "Much better. commit".

**Where each decision lands (implementation stops for a user playtest):**
#1→Phase 3 (approved: credits-left/cargo-right) · #2→Phase 3 (resolved:
NO `? guide` in hints) then **OVERTURNED in Phase 5 (fix `?` + advertise)**
· #3→Phase 4 · #4→Phase 5 (RESOLVED: `UP/DOWN navigate`) · #5→Phase 5 · #6→Phase 7
(RESOLVED: persistent Launch row on both tabs) then **REVISED & RESOLVED
in Phase 7–8: 3 tabs SHIP/CARGO/LOADOUT, Launch on SHIP only**
· #7→Phase 3 revision (RESOLVED: pin approved) · #8→Phase 3 revision
(RESOLVED: cap 13 approved)· #9→Phase 4 revision (RESOLVED: centering + gaps approved)

## Pre-implementation audit

### Existing modules to extend or reuse

- `src/spacehack/pygame_split.py` — `SplitFrame`/`SplitRow` dataclasses,
  `_fit_font`, `_frame_height`, `_draw_panel`, `_draw_frame`,
  `run_shared`/`run_interactive` — the entire change surface.
- `src/spacehack/pygame_ui.py` — `max_wrapped_lines`, `fit_text`,
  `measure_font`, `modal_footer_y` (already used by `_fit_font`).
- `src/spacehack/menus/_loadout.py`, `_armory.py`, `src/spacehack/trade.py`
  — the four frame builders to migrate.
- `src/spacehack/pygame_menu.py`, `pygame_screen.py`, `pygame_merchant.py`,
  `pygame_navigation.py` — the other frame families for Phases 5–6.
- `src/spacehack/menus/_planet.py`, `_ship_menu.py`, `npc.py`,
  `navigation.py`, `comms.py`, `pygame_story.py`, `input_helpers.py`,
  `character_screen.py` — modal builders adopting `modal_hint` + value
  helpers in Phase 5.
- `character_screen.py` — the tab-pattern reference (`ScreenFrame.tabs`,
  `active_tab`, TAB-outcome handling in the runner) for Phase 7.
- `trait_screen.py`, `menus/_missions.py`, `main_quest/_act0.py`
  (help-offer modal), `pygame_quantity.py` — modal builders found in the
  completeness sweep, adopting `modal_hint`/helpers in Phase 5.
- `trade.py._cargo_frame` + `_ship_menu._pygame_loadout_frame` — the two
  existing frames merged into the tabbed hangar (Phase 7).
- `src/spacehack/ui.py` — precedent for the shared layer on the tcod
  path (`render_split_frame`, `format_split_row`, `screen_header`).
- `src/spacehack/help.py` — guide sections to update.
- `tests/test_pygame_ui.py` — existing split/armory/loadout/trade tests.

### Duplication hotspots

1. Four inline `SplitFrame(...)` constructions (armory, loadout, trade
   ×2) — each re-formats prices/credits/hints/footers.
2. `"--- WEAPONS ---"` divider literal duplicated in `_armory.py:64` and
   `_loadout.py:66`.
3. `f"Credits: {ctx.stats.credits}$"` vs bare `Credits: N` across 6
   sites (trade.py:632,820 drop the `$`).
4. The hint string copy-pasted at 4 split construction sites; hint
   separators vary 4 ways across the other ~11 modals (npc.py:238
   ` - `, comms.py:249 ` - `, title `   `, pygame_story ` - `,
   split `  `) and nav wording varies (`ARROW KEYS / j,k` vs
   `UP/DOWN or j/k`).
5. `_frame_height` counting un-capped rows — the root of the font drift.
6. Three `_fit_font` 24→11 loops (split/screen/menu) — collapsed into
   one shared `pygame_ui.fit_font` in Phase 6 (each family passes its own
   height fn + budget). `pygame_batch` / `pygame_merchant` / the capture
   families keep specialized solvers (different geometry).

### DRY strategy

- All content-policy helpers live in `pygame_ui.py` next to the shared
  primitives, so split terminals, `pygame_screen`, and `pygame_menu`
  modals all consume the same policy (mirrors `ui.py` on the tcod
  path, which already hosts the shared split primitives for tcod).
- `_frame_height` reuses `pygame_ui.max_wrapped_lines` with the new
  `MAX_DETAIL_LINES` cap; the viewport reuses the existing row-iteration
  shape in `_draw_panel`.
- Terminal modules become thin: build rows via helpers, call one
  `SplitFrame(...)` constructor — no inline formatting anywhere.

## Acceptance criteria

1. [x] All four split terminals render at the same font size (loadout's)
      — superseded by decision #8 (cap 13): long lists trade uniform
      24px for depth (armory ~19px, trade ~21px, loadout/NPC 24px);
      the fit is stable once a list exceeds the cap
2. [x] Long panels scroll; selection is never off-screen
3. [x] `ARMORY - <PLANET>` title; no empty footer slot anywhere
4. [x] `Credits: N$` / `Cargo: N/M` everywhere they appear
5. [x] One shared hint constant; the four split terminals advertise
      `? guide` (decision #2 overturned in Phase 5 — the key now works
      via the unicode fallback)
6. [x] Zero duplicate string literals across the four builders
7. [x] Loadout renders at the user-approved look: pinned description +
      shared hint (both playtest-approved); its chrome/font/values are
      the regression baseline
8. [x] All tests + smoke pass (541 passed); guide matches implementation
9. [x] Ship buy adopts the Layer 1 helpers (Phase 4): all-caps title,
      helper-formatted prices/credits/shortfall, canonical hint — the
      playtest-approved changes are casing, the colon in the detail
      line, and the footer separators
10. [x] Every modal whose runner opens the guide advertises `? guide`
      and the key works from inside the modal (decision #2 overturned:
      `is_guide_key` unicode fallback fixes the `?` key)
11. [x] One hint grammar (`modal_hint`) across all modal families
12. [x] Menus/screens that can clip render at the same font as terminals
      (Phase 6 — shared `pygame_ui.fit_font` + capped viewport) or are
      explicitly exempt (tiny content: ship buy, jump, story)
13. [x] Ship hangar is a tabbed SHIP/CARGO/LOADOUT screen (C-screen
      pattern) with no nested cargo/loadout modals (Phase 7 — jettison
      stays in-tab on CARGO); Launch on the SHIP tab only; LOADOUT
      slots mirror the mechanic's My Ship panel (decision #6 revision
      approved "Looking great now")
14. [x] Every tunable (palette, fonts, title/hint/value formats, row
      cap, pin geometry) is a single constant/helper — one edit updates
      all modals
15. [x] All Open decisions resolved via user playtest (EXPERIMENT
      workflow), none silently guessed
