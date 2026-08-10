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

Frame-height budget at 1600×960 is 682px. At 24px a row costs 43px, a
divider 34px, a wrapped detail line 31px. → **9 visible selectable rows
per panel + up to 2 detail lines fits at 24px (667px).** 10 rows already
overflows (710px).

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

1. Add `MAX_VISIBLE_ROWS = 9` and `MAX_DETAIL_LINES = 2` constants.
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
| `SPLIT_SHOP_HINT` | `modal_hint("UP/DOWN navigate", "TAB switch panel", "ENTER buy/sell", "ESC back", "? guide")` | 4 copy-pasted hints |

**Footer rule (matches loadout):** `footer_left = credits_label(...)`,
`footer_right =` domain stat (loadout: `Wpn: x/y  Mod: x/y` unchanged;
armory: new `Wpn: 0/2  Arm: x/5` filling the empty slot; trade/NPC:
`cargo_label(...)`). *Flagged decision — see Open decisions #1.*

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
| `pygame_menu` | Ship hangar, Planet, NPC talk, GO TO, Jump confirm, Comms ×2, Loot, Character pickers ×2, Story ×3 (dismiss/confirm/choose), **Dungeon breach confirm**, **Main-quest help offer**, **Active-mission delivery board**, Title, Dev picker | Layer 1 where prices appear, `modal_hint` + `? guide` (Phase 5), Layer 2 font floor (Phase 6); ship hangar moves to `pygame_screen` with CARGO/LOADOUT tabs (Phase 7) |
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
- [x] `?` opens the guide from a split terminal

Passed: [x]   Issues: none — user approved ("phase 1 is great").

Implemented: [x] — `tools/_font_estimate.py` reports 24px on all four
terminals (armory 12→24, trade-earth 14→24, loadout/NPC unchanged at 24).
Code review: no blocking issues. Pre-existing dead code flagged (not
fixed here): `pygame_split._content_width` and the unused `frame` param
of `_draw_panel`.

---

### Phase 2 — Content-policy helpers (`pygame_ui.py`)

- [ ] Add `terminal_title`, `section_header`, `price_cell`, `sell_cell`,
      `credits_label`, `cargo_label`, `shortfall_label`, `reward_label`,
      `modal_hint`, `SPLIT_SHOP_HINT`
- [ ] Unit tests for each helper (same commit)
- [ ] Smoke gate

**▸ PLAYTEST Phase 2:** No visual change yet (helpers unused). Smoke
gate is the real gate.

Passed: [ ]   Issues: _______________

---

### Phase 3 — Migrate the four terminals

- [ ] `_loadout.py` → helpers; verify zero visual change
- [ ] `_armory.py` → `planet_id` param, `ARMORY - <PLANET>` title,
      footer_right slot counts, `section_header` dividers
- [ ] `trade.py` → `credits_label`/`cargo_label` footers, `price_cell`/
      `sell_cell`, hint constant (both station + NPC trade)
- [ ] Update existing frame tests that assert old strings (armory title,
      trade footer)
- [ ] `help.py` terminal sections updated ("My Ship", `? guide`)
- [ ] Smoke gate

**▸ PLAYTEST Phase 3:**

- [ ] Armory title shows the planet: `ARMORY - EARTH`
- [ ] Armory footer right shows `Wpn: 0/2  Arm: x/5` (no dead space)
- [ ] Trade footer shows `Credits: N$` left, `Cargo: N/M` right
- [ ] Sell cells all read `(sell N$)` / `(sell N$) xN`; buy cells `N$`
      / `N$ (N)` — same style on every terminal
- [ ] Guide sections for armory/trade/loadout match actual labels
- [ ] Loadout unchanged; full buy/sell cycle works on all four terminals
- [ ] ESC/QUIT from each terminal returns cleanly

Passed: [ ]   Issues: _______________

---

### Phase 4 — Adjacent adoption: Ship Buy (`pygame_screen` family)

Layer 1 only (see section D) — ship buy's content is small, so no
viewport/font work needed.

- [ ] `_ship_buy.py` routes title/price/credits/shortfall through the
      helpers
- [ ] Update `test_ship_buy_frame_*` assertions to the helper output
      (title becomes `SCOUT - FOR SALE` unless the helper is given an
      explicit title-case suffix — decision #3)
- [ ] `help.py` ship-buy section matches the new wording
- [ ] Smoke gate

**▸ PLAYTEST Phase 4:** Earth showroom — buy/trade-in a ship; modal looks
and reads identically except for consistent casing/format; `? guide`
still opens the guide.

Passed: [ ]   Issues: _______________

---

### Phase 5 — Menu & screen-family conventions (`pygame_menu` / `pygame_screen` / `pygame_merchant`)

Layer 1 + Layer 3 only — no layout work.

- [ ] `modal_hint` adopted across the inventory: ship hangar, planet,
      NPC talk, GO TO, jump confirm, comms ×2, loot, story ×3,
      dungeon confirm, quest help offer, mission delivery board,
      trait selection, title, character pickers, ship buy, cargo,
      mechanic, ammo, merchant board, help guide
- [ ] Quantity prompt: verify its hint/label style matches
      (`UP/DOWN adjust   ENTER confirm   ESC cancel`), add `? guide`
      only if it doesn't crowd the line
- [ ] `? guide` added to every interactive modal hint
- [ ] Value helpers where prices/rewards/credits appear (ship buy,
      merchant board, loot, cargo, ammo, mechanic, ship hangar stats)
- [ ] Unify nav phrase (`ARROW KEYS / j,k` vs `UP/DOWN or j/k`) via
      one constant (decision #4)
- [ ] Update the affected frame tests (hints/titles only)
- [ ] Smoke gate

**▸ PLAYTEST Phase 5:** walk the modal tree — planet bump, ship hangar,
NPC talk, comms, guild master, GO TO, jump, ship buy, cargo, mechanic.
Every hint reads the same style, every modal advertises `? guide`, and
`?` opens the guide from each.

Passed: [ ]   Issues: _______________

---

### Phase 6 — Layer 2 port: font floor + viewport for `pygame_menu` / `pygame_screen`

Only where content can clip (menus with many items; screens with long
lists). Ship buy / jump / story are tiny — skip them.

- [ ] Shared font-solver in `pygame_ui` (one 24→11 loop; height fn
      passed in) replaces the three `_fit_font` copies
- [ ] Row/detail caps + viewport scroll ported to `pygame_menu`
      (mission board, comms, character pickers, GO TO)
- [ ] Row caps + viewport ported to `pygame_screen` (cargo, character
      sheet, help guide)
- [ ] Keep selection-independence tests green in both families
- [ ] Smoke gate + `tools/_font_estimate.py` extended to report menu
      and screen font sizes

**▸ PLAYTEST Phase 6:** guild master with 8+ contracts, comms with 6+
contacts, character class list — all render at the same font as the
split terminals, selection stays visible, no clipped rows.

Passed: [ ]   Issues: _______________

---

### Phase 7 — Tabbed ship hangar (C-screen pattern)

The hangar menu (View Cargo / View Loadout / Launch) becomes one tabbed
`pygame_screen` modal — the first Layer 4 adoption.

- [ ] Convert `_ship_menu` hangar from `pygame_menu` to `pygame_screen`
      with `tabs=("CARGO", "LOADOUT")`
- [ ] CARGO tab reuses `_cargo_frame` rows (jettison actions preserved);
      LOADOUT tab reuses the read-only loadout rows
- [ ] Persistent `Launch` action row reachable from both tabs
      (decision #6)
- [ ] Footers advertise the TAB target like the C screen
      (`TAB loadout` / `TAB cargo`); `modal_hint` + `? guide`
- [ ] Update `_ship_menu` / `trade` frame tests and help.py ship section
- [ ] Smoke gate

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

---

### Phase 8 — Final gates

- [ ] `python3 tools/smoke.py && python3 tools/test.py` pass
- [ ] `tools/_font_estimate.py` reports 24px on all four terminals
- [ ] Full playtest: buy/sell + scroll on every terminal, save → quit →
      Continue intact (no new mutable state — scroll is derived from
      selection, nothing to persist)
- [ ] Move this doc to `docs/design/complete/`

Passed: [ ]   Issues: _______________

---

## Contracts compliance (MANDATORY — see knowledge.md)

- [ ] **Save/load:** No new mutable state. Viewport is derived from
      `selected` each frame — nothing added to `GameContext`,
      `_ctx_to_dict()`, or `load_game()`.
- [ ] **Game guide:** help.py terminal sections updated (label "My Ship",
      `? guide` hint) in Phase 3.
- [ ] **Module-level state:** none added.
- [ ] **Pure function test contract:** every new helper
      (`terminal_title`, `section_header`, `price_cell`, `sell_cell`,
      `credits_label`, `cargo_label`, `shortfall_label`, `reward_label`,
      `modal_hint`, `_visible_window`) ships with a test in the same
      commit; `_frame_height` cap keeps its existing
      selection-independence test green.

## Open decisions (all flagged EXPERIMENT — user playtests before lock-in)

1. **Footer slot roles.** Recommended (matches loadout): credits LEFT,
   domain stat RIGHT on every terminal. Trade currently reverses this.
   Flip is a one-line swap if undesired.
2. **`? guide` in the hint.** Recommended: yes — the renderer already
   handles the key; hiding it violates discoverability.
3. **Ship-buy title casing.** `SCOUT - FOR SALE` (all-caps, matches the
   terminal family) vs keeping `SCOUT - for sale`. Recommended:
   all-caps via `terminal_title`.
4. **Nav phrase.** `ARROW KEYS / j,k navigate` (menu family) vs
   `UP/DOWN or j/k navigate` (comms/cargo) vs `UP/DOWN navigate`
   (split). Recommended: one canonical phrase via `NAV_HINT`.
5. **Title grammar per family.** Keep the two existing grammars
   (all-caps `X - Y` for terminals; `NAME - sentence suffix` for
   screens/merchant) or force one everywhere. Recommended: keep
   both, enforce per family via `terminal_title`.
6. **Launch placement in the tabbed hangar.** Recommended: a
   persistent `Launch` action row at the bottom of both tabs
   (matches the current 3rd menu option). Alternatives: a hotkey
   (needs new key plumbing in `pygame_screen`) or a third tab
   (rejected — Launch is an action, not a view).

**Where each decision lands (implementation stops for a user playtest):**
#1→Phase 3 · #2→Phase 3 · #3→Phase 4 · #4→Phase 5 · #5→Phase 5 · #6→Phase 7

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
6. Three `_fit_font` 24→11 loops (split/screen/menu) + one in
   `pygame_batch` + one in `pygame_merchant` — five font solvers.

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

1. [ ] All four split terminals render at the same font size (loadout's)
2. [ ] Long panels scroll; selection is never off-screen
3. [ ] `ARMORY - <PLANET>` title; no empty footer slot anywhere
4. [ ] `Credits: N$` / `Cargo: N/M` everywhere they appear
5. [ ] One shared hint constant; `? guide` works and is advertised
6. [ ] Zero duplicate string literals across the four builders
7. [ ] Loadout is visually unchanged (regression baseline)
8. [ ] All tests + smoke pass; guide matches implementation
9. [ ] Ship buy adopts the Layer 1 helpers (Phase 4) with no visual
      regression
10. [ ] Every interactive modal advertises `? guide` and it works
11. [ ] One hint grammar (`modal_hint`) across all modal families
12. [ ] Menus/screens that can clip render at the same font as terminals
      (Phase 6) or are explicitly exempt (tiny content)
13. [ ] Ship hangar is a tabbed CARGO/LOADOUT screen (C-screen pattern)
      with Launch still reachable; no nested cargo/loadout modals
14. [ ] Every tunable (palette, fonts, title/hint/value formats) is a
      single constant/helper — one edit updates all modals
15. [ ] All six Open decisions resolved via user playtest (EXPERIMENT
      workflow), none silently guessed
