"""The unified HUD core (doc 104) — one painter set, four panels.

The shared, anchored rows every panel serves those moments with: the
mode's health meter, cargo, the FIXED status slot, and the one-row XP
footer. Painters are data-parameterized and pure (print-only); the
module imports nothing from :mod:`spacehack.combat` at module level —
the status-slot painter lazy-imports the segment ink (the bandolier
precedent; segments arrive as a parameter).

Region row budget (the ground pair; the reserved-height law — a band
growing or shrinking can never push the core):

    y=0        title (both panels)
    y=2..5     A: mode band, GROUND_BAND_ROWS reserved
    y=6        the exploration divider / the combat PLAYER label row
    y=7..10    B: the core — HP, Armor, Cargo, the status slot
    y=11..     C: the WEAPONS anchor (GROUND_WEAPONS_Y)
"""
from __future__ import annotations

from .framebuffer import FrameBuffer
from .ui import COLOR_VALUE_WHITE

# The native overlay renders HUD text at roughly half the cell width
# (8px glyphs in 16px cells), so the 20-cell HUD panel fits ~36 characters.
# HUD_TEXT_MAX matches that real glyph capacity for every HUD line (world
# and combat); the cell renderer clips at the screen edge as a final guard.
HUD_TEXT_MAX: int = 36

_BAR_CHAR_FULL: str = "#"   # full marker
_BAR_CHAR_EMPTY: str = "."   # empty marker

# High-contrast HUD palette pair for health state — green while at least
# half, red below (the half-health cue every meter row shares).
COLOR_HP_GOOD: tuple[int, int, int] = (110, 245, 125)             # bright green
COLOR_HP_LOW: tuple[int, int, int] = (255, 110, 110)              # bright red

# The ground pair's reserved-region rows (doc 104 Phase 1).
GROUND_BAND_Y: int = 2        # first A-band row (row 1 stays blank under the title)
GROUND_BAND_ROWS: int = 4     # reserved A height: rows 2-5 on both ground panels
GROUND_CORE_Y: int = GROUND_BAND_Y + GROUND_BAND_ROWS + 1         # 7 — first B row
GROUND_CORE_ROWS: int = 4     # HP, Armor, Cargo, the status slot
GROUND_WEAPONS_Y: int = GROUND_CORE_Y + GROUND_CORE_ROWS          # 11 — the C anchor


def _bar_str(value: int, max_value: int, width: int = 10) -> str:
    """Return a CP437-safe bar string with ``#`` for filled and ``.`` for empty."""
    if max_value <= 0:
        return _BAR_CHAR_EMPTY * width
    full = max(0, min(width, value * width // max_value))
    return _BAR_CHAR_FULL * full + _BAR_CHAR_EMPTY * (width - full)


def paint_hp_armor_rows(
    console: FrameBuffer, hud_x: int, y: int, *,
    hp: int, max_hp: int, armor: int, regen_suffix: str = "",
) -> int:
    """Region B's health meter — the ONE shape (doc 104 item 15): the
    exploration panel's aligned format, label <8 + 10-cell bar <11 +
    cur/max (values land at column 19), HP tinted by the half-health
    cue. ``regen_suffix`` is ground combat's interim ``+N`` read (item
    6 kills it in Phase 2). Returns the next row."""
    _hp_fg = COLOR_HP_GOOD if hp * 2 >= max_hp else COLOR_HP_LOW
    console.print(
        x=hud_x, y=y,
        string=(
            f"{'HP':<8}{_bar_str(hp, max_hp):<11}{hp}/{max_hp}{regen_suffix}"
        )[:HUD_TEXT_MAX],
        fg=_hp_fg,
    )
    console.print(
        x=hud_x, y=y + 1,
        string=f"{'Armor':<8}{armor}"[:HUD_TEXT_MAX],
        fg=COLOR_VALUE_WHITE,
    )
    return y + 2


def paint_cargo_row(
    console: FrameBuffer, hud_x: int, y: int, *, used: int, max_cargo: int,
) -> int:
    """Region B's cargo row (item 14 — every panel carries the datum):
    the same aligned bar shape the meter uses. Returns the next row."""
    console.print(
        x=hud_x, y=y,
        string=f"{'Cargo':<8}{_bar_str(used, max_cargo):<11}{used}/{max_cargo}"[:HUD_TEXT_MAX],
        fg=COLOR_VALUE_WHITE,
    )
    return y + 1


def paint_status_slot(console: FrameBuffer, hud_x: int, y: int, segments) -> int:
    """Region B's FIXED status slot (item 13): segments paint when
    present; the row stays BLANK when empty — no placeholder glyph,
    and the row is ALWAYS consumed (the slot never pops at a mode
    boundary). Returns the next row (always ``y + 1``)."""
    if segments:
        from .combat._statuses import paint_hud_segments

        paint_hud_segments(console, hud_x, y, segments, hud_x + HUD_TEXT_MAX)
    return y + 1


def xp_footer_row(hud_view_height: int) -> int:
    """The one footer row — the panel's bottom row.

    Two rows above the band's last cell, not one: the overlay paints
    text at ``padding_y (4px) + row * 16`` with a 16px-line font and
    clips at the panel rect, so the final cell row's glyph box
    overflows the clip by the padding — its bottom pixels cut off.
    ``hud_view_height - 2`` is the last row that renders whole (the
    old footer's exit line lived there)."""
    return max(3, hud_view_height - 2)


def paint_xp_footer(
    console: FrameBuffer, hud_x: int, hud_view_height: int, *,
    xp_line: str, xp_fg: tuple[int, int, int],
) -> None:
    """The footer joined to the core, slimmed to ONE row (item 12):
    the XP bar alone, bottom-anchored on every panel. The retired
    "bump to interact" / "ESC to quit" rows never return — ESC lives
    in each mode's key-hint block as ``[ESC] Pause``."""
    console.print(
        x=hud_x, y=xp_footer_row(hud_view_height),
        string=xp_line, fg=xp_fg,
    )
