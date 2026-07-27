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
- [x] All existing list menus that fit the API use it (or have a comment explaining why they don't)
- [x] Scrolling never shifts text horizontally (fixed-column by default)
- [x] Smoke + audit pass

### Wired so far

- `render_menu()` in `ui.py` — delegates to `render_selectable_list` (covers character creation: species + class menus)
- `_run_goto()` in `__main__.py` — the GO TO / auto-nav destination picker

### Wired (with pre-content pattern)

These menus have variable-height pre-content (stats or flavor text) above the options — we render the pre-content directly via `console.print()` and call `render_selectable_list` with only the options and an empty title at the correct Y offset:

- `render_ship_menu()` in `__main__.py` — ship stats above View Cargo / Launch options
- `_run_mech_menu()` in `__main__.py` — ship stats above Refuel / Repair options
- `_render_interaction_modal()` in `comms.py` — flavor text above interaction options

### Wired (single-action dialogs, also using the pre-content pattern)

These single-action bump dialogs were unified after the main sidequest work. They use the same pre-content + single-item `render_selectable_list` pattern:

- `render_planet_menu()` in `__main__.py` — planet name + description, then `Land` option (or `No port` text)
- `render_jump_menu()` in `__main__.py` — title + description + fuel info, then `Jump to <system>` option
- `open_loot_pickup()` in `trade.py` — cargo info lines, then `Take` option

### All wired

Every selectable list menu now uses `render_selectable_list` either directly or via the pre-content pattern. No remaining menus need custom rendering.

## Estimated effort

Small — one function, ~30 lines. Wiring into existing modals is mechanical (replace ~10 lines per modal with a single call).


## Other UI consolidation tasks

These are smaller tasks uncovered during the trade v1 DRY review. They're bundled here because they affect the same "how do UI modals render" cross-cutting concern, even though their mechanics differ from the list-renderer above.

### Task B: Split-screen trade modal (rec #1 from trade DRY)  ✅

**Solved** in `89f0da3`:
- Extracted `_render_trade_frame()` in `trade.py` — handles title, headers, separator, item rows, footer, and hint
- Both `open_trade` and `open_npc_trade` pre-compute their row data as `(name, price_label, suffix, fg)` tuples and delegate to the shared helper
- ~50 lines of scaffolding deduplicated

**Candidate which panels would benefit**:

- `open_trade` in `trade.py` (station terminal) — migrated
- `open_npc_trade` in `trade.py` (comms hail) — migrated


### Task C: Centered-text modal helper (rec #7 from trade DRY)  ✅

**Solved** in `89f0da3`:
- Added `_paint_centered(console, y, text, *, fg)` module-level helper in `trade.py`
- `_run_quantity_prompt`: replaced local `paint()` closure with `_paint_centered` calls
- `open_loot_pickup`: replaced repetitive `console.print(x=ui.centered_x(...))` with `_paint_centered` calls

**Candidate modals**:

- `open_loot_pickup` in `trade.py` — migrated
- `_run_quantity_prompt` in `trade.py` — migrated
