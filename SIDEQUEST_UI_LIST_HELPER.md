# Sidequest: Centralize list rendering in `ui.py`

## Motivation

Every selectable-list menu in the game re-implements the same render pattern:

```python
console.print(x=centered_x(title, SCREEN_WIDTH), y=Y, string=title, fg=cyan)
for i, item in enumerate(items):
    marker_open = '> ' if i == selected else '  '
    marker_close = ' <' if i == selected else '  '
    console.print(x=COL_X, y=Y + i*3, string=f"{marker_open}{item.name}{marker_close}", fg=fg)
    console.print(x=COL_X+2, y=Y + i*3+1, string=f'"{item.desc}"', fg=dim)
console.print(x=centered_x(hint, SCREEN_WIDTH), y=bottom, string=hint, fg=grey)
```

This repetition caused a **layout jitter bug** in `comms.py` (fixed in `9a8c5bb`) — per-line `centered_x()` with inconsistent marker widths shifted text horizontally on scroll. A central helper would eliminate this bug class entirely.

## What to build

Add a `render_selectable_list()` function to `src/spacehack/ui.py` that handles the common case:

```python
def render_selectable_list(
    console,
    title: str,
    items: list[tuple[str, str]],       # (name, description)
    selected: int,
    *,
    col_x: int | None = None,           # default: SCREEN_WIDTH // 4
    title_fg=(130, 220, 255),
    item_fg_selected=(255, 255, 255),
    item_fg_normal=(200, 200, 220),
    desc_fg_selected=(175, 170, 210),
    desc_fg_normal=(150, 150, 150),
    hint_fg=(110, 130, 175),
    hint: str = "UP/DOWN navigate - ENTER select - ESC back",
) -> None:
```

**Fixed column**, consistent markers, proper spacing — every menu gets it for free.

## Modals that would benefit

Survey needed, but at minimum:

- `comms.py` — `_render_comms_panel`, `_render_interaction_modal` (both already converted to fixed-column in the bugfix — could be simplified further)
- `__main__.py` — `_render_aoi_panel`, `_render_planet_menu`, ship menu, etc.
- `trade.py` — buy/sell list panels
- `cargo.py` — cargo management list

**Custom render functions** like the combat HUD or space map wouldn't use it — they have completely different layout needs.

## Acceptance criteria

- [x] Function exists in `ui.py` with a clear docstring
- [ ] All existing list menus use it (or have a comment explaining why they don't)
- [x] Scrolling never shifts text horizontally (fixed-column by default)
- [x] Smoke + audit pass

### Wired so far

- `render_menu()` in `ui.py` — delegates to `render_selectable_list` (covers character creation: species + class menus)
- `_run_goto()` in `__main__.py` — the GO TO / auto-nav destination picker

### Not yet wired (won't fit without API extension)

- `render_ship_menu()` in `__main__.py` — has ship description + fuel line between title and options. Would need a pre-content callback or the ability to inject extra lines above the list.
- `_render_interaction_modal()` in `comms.py` — has variable-height flavor text above the options. Same constraint.

## Estimated effort

Small — one function, ~30 lines. Wiring into existing modals is mechanical (replace ~10 lines per modal with a single call).


## Other UI consolidation tasks

These are smaller tasks uncovered during the trade v1 DRY review. They're bundled here because they affect the same "how do UI modals render" cross-cutting concern, even though their mechanics differ from the list-renderer above.

### Task B: Split-screen trade modal (rec #1 from trade DRY)

**Problem**: `open_trade()` and `open_npc_trade()` in `trade.py` duplicate ~150 lines of split-screen layout scaffolding:

- Title rendering with focused-panel highlighting
- Column headers that switch between `"│ Active"` (focused) and `"  Inactive "` (unfocused) style
- Vertical separator (`│`) drawn between the two panels
- Left panel iterating a list of goods with pricing
- Right panel iterating player inventory
- Footer with cargo + credits
- Tab-switching logic, focus-aware up/down navigation, Enter to transact

The per-row formatting (`_format_trade_line`) was extracted in the DRY pass, but the container scaffolding remains duplicated.

**What to build**: Extract a shared `_render_split_panel(ctx, left_goods, left_label, left_pricer, left_stock_fn, right_filter_fn)` that encapsulates the split-screen layout. The two call sites pass different data sources (economy_state vs ephemeral NPC stock) and different pricing models (`_unit_price` vs fixed multiplier), which means the helper needs to accept callables for price computation.

**Candidate which panels would benefit**:

- `open_trade` in `trade.py` (station terminal) — already proven this pattern works
- `open_npc_trade` in `trade.py` (comms hail) — the duplicate

**Estimated effort**: Moderate. ~50 lines of helper function + updating two call sites. The main complexity is designing the right function signature to accommodate the differences (pricing model, stock source, contraband handling).


### Task C: Centered-text modal helper (rec #7 from trade DRY)

**Problem**: Several small modals render simple centered-text layouts with the same pattern — title on one row, body text below, hint at the bottom. `open_loot_pickup` and `_run_quantity_prompt` each reimplement this differently:

- `_run_quantity_prompt` has a local `paint(row, text, *, fg)` that wraps `ui.centered_x()`
- `open_loot_pickup` uses `console.print(x=ui.centered_x(...), ...)` directly on each line

Neither is wrong, but they're two different solutions to the same problem. A shared `_render_centered_modal(console, lines: list[tuple[str, fg]]) -> None` could eliminate this.

**Candidate modals**:

- `open_loot_pickup` in `trade.py` — the immediate beneficiary
- `_run_quantity_prompt` in `trade.py` — already has its own helper, could switch
- Any future simple confirm/notice modal

**Estimated effort**: Trivial. ~10 lines for the helper, ~5 lines per call site.
