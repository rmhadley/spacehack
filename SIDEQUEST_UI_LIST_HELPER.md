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

- [ ] Function exists in `ui.py` with a clear docstring
- [ ] All existing list menus use it (or have a comment explaining why they don't)
- [ ] Scrolling never shifts text horizontally
- [ ] Smoke + audit pass

## Estimated effort

Small — one function, ~30 lines. Wiring into existing modals is mechanical (replace ~10 lines per modal with a single call).
