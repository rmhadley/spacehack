"""The unified HUD core (doc 104) — one painter set, four panels.

The shared, anchored rows every panel serves those moments with: the
mode's health meter, cargo, the FIXED status slot, and the one-row XP
footer. Painters are data-parameterized and pure (print-only); the
module imports nothing from :mod:`spacehack.combat` at module level —
the status-slot painter lazy-imports the segment ink (the bandolier
precedent; segments arrive as a parameter).

Region row budget (the reserved-height law — a band growing or
shrinking can never push the core). The ground pair:

    y=0        title (both panels)
    y=2..5     A: mode band, GROUND_BAND_ROWS reserved (combat closes
               the band with the divider on its last reserved row —
               doc 104 item 16; every panel closes A and C with the
               rule)
    y=6        the exploration divider / the combat PLAYER label row
    y=7..10    B: the core — HP, Armor, Cargo, the status slot
    y=11..     C: the WEAPONS anchor (GROUND_WEAPONS_Y)

The space pair (Phase 3) — five reserved A rows, no label row on the
core, so the A-close divider sits at the same row on both panels:

    y=0        title (both panels)
    y=2..6     A: mode band, SPACE_BAND_ROWS reserved
    y=7        the A-close divider (both panels)
    y=8..11    B: the core — Hull, Shield, Cargo, the status slot
    y=12..     C: the WEAPONS anchor (SPACE_WEAPONS_Y) — the fight's
               weapons block; exploration reserves the same per-loadout
               budget empty, so the C-close divider and D hold their y
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

# The space pair's reserved-region rows (doc 104 Phase 3): both A bands
# need five rows (exploration: ship name/location/date + Fuel/Spd; the
# fight: mode + AP/STIM/Evade/Pow).
SPACE_BAND_Y: int = 2         # first A-band row (row 1 stays blank under the title)
SPACE_BAND_ROWS: int = 5      # reserved A height: rows 2-6 on both space panels
SPACE_CORE_Y: int = SPACE_BAND_Y + SPACE_BAND_ROWS + 1            # 8 — first B row
SPACE_CORE_ROWS: int = 4      # Hull, Shield, Cargo, the status slot
SPACE_WEAPONS_Y: int = SPACE_CORE_Y + SPACE_CORE_ROWS             # 12 — the C anchor

# Space-meter palette (moved from hud_combat with the meter painter,
# Phase 3): the hull trio carries the damage stages; cyan is shields.
COLOR_HULL_BAR_GREEN: tuple[int, int, int] = (100, 235, 115)       # bright green
COLOR_HULL_BAR_YELLOW: tuple[int, int, int] = (255, 220, 80)       # amber
COLOR_HULL_BAR_RED: tuple[int, int, int] = (255, 80, 80)           # red
COLOR_SHIELD_BAR: tuple[int, int, int] = (175, 230, 255)           # bright cyan


def space_weapons_rows(weapon_count: int) -> int:
    """The space pair's shared C budget (doc 104 Phase 3): the rows the
    fight's WEAPONS block consumes — its title plus three rows per
    weapon (name / stats / cost). Exploration reserves exactly this
    many rows empty, so the C-close divider and the D band start at the
    same y on both panels; sized per-loadout because doc 56 SETTLED 18
    retired fixed slot counts."""
    return 1 + 3 * weapon_count


def _bar_str(value: int, max_value: int, width: int = 10) -> str:
    """Return a CP437-safe bar string with ``#`` for filled and ``.`` for empty."""
    if max_value <= 0:
        return _BAR_CHAR_EMPTY * width
    full = max(0, min(width, value * width // max_value))
    return _BAR_CHAR_FULL * full + _BAR_CHAR_EMPTY * (width - full)


def _aligned_row(label: str, bar: str, value: str) -> str:
    """The core's one-column law (doc 104 items 15 + 18): label <8 +
    bar <11 + value — every meter row's bars land at column 8 and its
    values at column 19, truncated to the panel's real glyph capacity.
    ONE site owns the widths so no meter row can drift off the column."""
    return f"{label:<8}{bar:<11}{value}"[:HUD_TEXT_MAX]


def paint_hp_armor_rows(
    console: FrameBuffer, hud_x: int, y: int, *,
    hp: int, max_hp: int, armor: int,
) -> int:
    """Region B's health meter — the ONE shape (doc 104 item 15): the
    exploration panel's aligned format, label <8 + 10-cell bar <11 +
    cur/max (values land at column 19), HP tinted by the half-health
    cue. Returns the next row."""
    _hp_fg = COLOR_HP_GOOD if hp * 2 >= max_hp else COLOR_HP_LOW
    console.print(
        x=hud_x, y=y,
        string=_aligned_row("HP", _bar_str(hp, max_hp), f"{hp}/{max_hp}"),
        fg=_hp_fg,
    )
    console.print(
        x=hud_x, y=y + 1,
        string=f"{'Armor':<8}{armor}"[:HUD_TEXT_MAX],
        fg=COLOR_VALUE_WHITE,
    )
    return y + 2


def _hull_bar_color(pct: float) -> tuple[int, int, int]:
    """The hull row's damage-stage tint: green at half, amber at a
    quarter, red below (one stage finer than the HP pair — hull damage
    accumulates across a whole flight, not one fight)."""
    if pct >= 0.5:
        return COLOR_HULL_BAR_GREEN
    if pct >= 0.25:
        return COLOR_HULL_BAR_YELLOW
    return COLOR_HULL_BAR_RED


def paint_hull_shield_rows(
    console: FrameBuffer, hud_x: int, y: int, *,
    hull: int, max_hull: int,
    shields: int, max_shields: int,
    shield_regen_rate: int = 0, shield_recharge_bonus: int = 0,
) -> int:
    """Region B's space meter (doc 104 Phase 3 + the mid-playtest
    ruling 2026-10-20: ``Shield`` spelled out, the bars lining up with
    Cargo) — the core's aligned shape, label <8 + 10-cell bar <11 +
    cur/max, values at column 19, Hull above Shield (the health row
    first, like the ground core's HP-above-Armor). The shield row
    carries its regen suffix in POINTS (``+N`` is next turn's gain,
    never percent) and the white-fill level indicator tracks ONLY
    ``shield_regen_rate`` (the S-key setting) so the highlight moves
    1:1 with the key. Always consumes both rows — a ship without
    shields (max 0) keeps the row BLANK, so B stays four rows and the
    rows below never shift. Returns the next row (always ``y + 2``)."""
    console.print(
        x=hud_x, y=y,
        string=_aligned_row("Hull", _bar_str(hull, max_hull), f"{hull}/{max_hull}"),
        fg=_hull_bar_color(hull / max(max_hull, 1)),
    )
    if max_shields > 0:
        _total = shield_regen_rate + shield_recharge_bonus
        _bar = _bar_str(shields, max_shields, width=10)
        _shd = f"{shields}/{max_shields}"
        if _total > 0:
            _shd += f" +{_total}"
        console.print(
            x=hud_x, y=y + 1,
            string=_aligned_row("Shield", _bar, _shd),
            fg=COLOR_SHIELD_BAR,
        )
        for _i in range(min(shield_regen_rate, len(_bar))):
            console.print(x=hud_x + 8 + _i, y=y + 1, string=_bar[_i], fg=COLOR_SHIELD_BAR, bg=(255, 255, 255))
    return y + 2


def paint_cargo_row(
    console: FrameBuffer, hud_x: int, y: int, *, used: int, max_cargo: int,
) -> int:
    """Region B's cargo row (item 14 — every panel carries the datum):
    the same aligned bar shape the meter uses. Returns the next row."""
    console.print(
        x=hud_x, y=y,
        string=_aligned_row("Cargo", _bar_str(used, max_cargo), f"{used}/{max_cargo}"),
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
