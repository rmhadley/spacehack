"""Right-side HUD: character name, species, class, and core stats.

Layout (assumes ``screen_width = SCREEN_WIDTH`` and
``hud_view_height = SCREEN_HEIGHT - MSG_LOG_HEIGHT``):

City mode (default):
    +-----------------+----------+
    |                 | Spacehack|
    |                 | HUMAN    |
    |       MAP       | PIRATE   |
    |     REGION      |          |
    |                 | -------- |
    |                 | HP 10/10 |
    |                 | Cargo 0/0|
    |                 | $   100  |
    |                 |          |
    |                 | ..       |
    +-----------------+----------+

Space mode (when ``owned_ship`` is provided):
    +-----------------+----------+
    |                 | Spacehack|
    |                 | SCOUT    |    |       MAP     |          |
    |     REGION     | Fuel 90  |
    |                 | Hull 100%|
    |                 | Cargo 0  |
    |                 | Wpn 0/2  |
    |                 | Mod 0/1  |
    |                 | -------- |
    |                 | G - Go To|
    |                 | P - Pickup|
    |                 | M - Map  |
    |                 | ESC Quit |
    +-----------------+----------+

The HUD paints only into the top portion of the screen so the message
log (drawn separately) owns the bottom rows.

**API:** Callers pass ``ctx`` (the single source of truth) plus only the
few layout-or-mode params that aren't on GameContext: ``screen_width``,
``hud_view_height``, ``location``, and the terminal flags. Everything else
(the stats, XP, ground stats, ship state, date) is pulled from ``ctx``
internally, so adding a new HUD-displayed field to ``GameContext`` never
requires updating call sites.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .framebuffer import FrameBuffer

from .engine import HUD_WIDTH
from .ui import COLOR_DIVIDER, COLOR_VALUE_DIM, COLOR_VALUE_WHITE  # shared palette (single source)

if TYPE_CHECKING:
    from .game_context import GameContext


# High-contrast HUD palette: neutral labels and values carry the reading
# load, while saturated colors communicate health and resource state.
# The shared white/dim/divider colors come from ui.py so brightness stays
# consistent across menus and gameplay.
COLOR_HUD_TITLE: tuple[int, int, int] = (255, 205, 95)             # vivid gold
COLOR_LABEL: tuple[int, int, int] = (245, 245, 235)                # near-white label
COLOR_HP_GOOD: tuple[int, int, int] = (110, 245, 125)               # bright green
COLOR_HP_LOW: tuple[int, int, int] = (255, 110, 110)                # bright red
COLOR_EVADE: tuple[int, int, int] = (135, 235, 150)                # green positive-buff accent

# Space-mode HUD palette — cyan is reserved for the ship identity.
COLOR_SHIP_NAME: tuple[int, int, int] = (150, 235, 255)             # bright cyan
COLOR_SHIP_VALUE: tuple[int, int, int] = (255, 255, 255)            # white stat values
COLOR_SHIP_LABEL: tuple[int, int, int] = (240, 240, 230)            # near-white labels
COLOR_FUEL_OK: tuple[int, int, int] = (110, 245, 125)               # green when fuel is adequate
COLOR_FUEL_LOW: tuple[int, int, int] = (255, 190, 75)               # amber when fuel is low (< jump cost)
COLOR_HELP_DESC: tuple[int, int, int] = (240, 240, 230)             # near-white key descriptions
CONSOLE_LOG_KEY = "\\"
CONSOLE_LOG_LABEL = "Console"

# Combat range-band colors — SINGLE SOURCE shared by the targeting line
# (combat/_animations), the enemy-distance readout below, and the target
# cards' HIT % (combat/_card_presentation). Keep them defined here only.
COLOR_RANGE_GREEN: tuple[int, int, int] = (100, 235, 115)     # close-bonus zone (max_range // 2)
COLOR_RANGE_YELLOW: tuple[int, int, int] = (255, 220, 80)     # within max range
COLOR_RANGE_ORANGE: tuple[int, int, int] = (255, 160, 60)     # inside min range (too close)
COLOR_RANGE_RED: tuple[int, int, int] = (255, 80, 80)         # beyond max range


def range_band_color(
    dist: float,
    weapon_max_range: int,
    weapon_min_range: int = 0,
) -> tuple[int, int, int]:
    """Color for a combat distance, matching the targeting-line bands.

    Green within the close-bonus zone (``max_range // 2``), yellow
    within ``max_range``, orange inside ``min_range`` when one exists,
    red beyond ``max_range``.
    """
    if dist <= weapon_max_range // 2:
        return COLOR_RANGE_GREEN
    if dist <= weapon_max_range:
        return COLOR_RANGE_YELLOW
    if weapon_min_range > 0 and dist <= weapon_min_range:
        return COLOR_RANGE_ORANGE
    return COLOR_RANGE_RED


@dataclass
class HudStats:
    """The stats shown in the HUD right now."""
    hp: int
    max_hp: int
    credits: int
    gunnery: int = 0
    piloting: int = 0
    engineering: int = 0


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _render_divider(console: FrameBuffer, hud_x: int, y: int) -> None:
    """Print a full-width divider line at ``(hud_x, y)``.

    Pure print — caller owns y advancement.
    """
    console.print(x=hud_x, y=y, string="-" * HUD_WIDTH, fg=COLOR_DIVIDER)


def _render_mission_line(
    console: FrameBuffer, hud_x: int, y: int, title: str,
) -> None:
    """Print the active mission title at ``(hud_x, y)`` with "M: " prefix.

    Truncates to fit HUD_WIDTH. Pure print — caller owns y advancement.
    """
    room = max(0, HUD_WIDTH - len("M: ") - 1)
    console.print(x=hud_x, y=y, string=f"M: {title[:room]}", fg=COLOR_HUD_TITLE)


def _render_skill_line(
    console: FrameBuffer, hud_x: int, y: int, stats: HudStats,
) -> None:
    """Print the GUN/PIL/ENG skill line at ``(hud_x, y)``.

    Pure print — caller owns y advancement.
    """
    console.print(
        x=hud_x, y=y,
        string=f"GUN:{stats.gunnery} PIL:{stats.piloting} ENG:{stats.engineering}"[:HUD_WIDTH],
        fg=COLOR_SHIP_LABEL,
    )


def _cargo_used_max(owned_ship, ship_catalog) -> tuple[int, int]:
    """Return ``(cargo_used, max_cargo)`` for the player's ship.

    ``cargo_used`` comes from the owned-ship state (includes mission
    cargo); ``max_cargo`` is the hull's base capacity plus any module
    bonuses via :func:`ship.effective_max_cargo`. Safe when either
    argument is ``None`` (returns zeroed values).

    Shared by the space and city HUD branches so the capacity math
    can never drift between them.
    """
    cargo_used = getattr(owned_ship, 'cargo_used', 0)
    max_cargo = getattr(ship_catalog, 'max_cargo', 0)
    if owned_ship is not None and ship_catalog is not None:
        from . import ship as _ship_mod
        max_cargo = _ship_mod.effective_max_cargo(ship_catalog, owned_ship)
    return cargo_used, max_cargo


def _render_ground_stat_line(
    console: FrameBuffer, hud_x: int, y: int, ground_stats,
) -> None:
    """Print the REF/STR/STA ground stat line at ``(hud_x, y)``.

    Pure print — caller owns y advancement.
    """
    console.print(
        x=hud_x, y=y,
        string=(
            f"REF:{ground_stats.reflexes} "
            f"STR:{ground_stats.strength} "
            f"STA:{ground_stats.stamina}"
        )[:HUD_WIDTH],
        fg=COLOR_SHIP_LABEL,
    )


def _footer_rows(hud_view_height: int) -> tuple[int, int, int]:
    """Return safe XP, interaction, and exit rows inside the HUD panel."""
    bottom = max(3, hud_view_height - 1)
    return bottom - 3, bottom - 2, bottom - 1


def _render_help_lines(
    console: FrameBuffer,
    hud_x: int,
    start_y: int,
    help_lines: list[tuple[str, str]],
) -> int:
    """Render a list of ``(key_label, description)`` pairs into
    ``console`` starting at column ``hud_x``, row ``start_y``.

    Each line is formatted as ``{key:<9} {desc}`` with the whole
    line in ``COLOR_HELP_DESC``. Returns the next available ``y``
    row so the caller can continue painting below the block.
    """
    y = start_y
    for key, desc in help_lines:
        line = f"{key:<9} {desc}"
        console.print(x=hud_x, y=y, string=line, fg=COLOR_HELP_DESC)
        y += 1
    return y


def _resolve_ship_catalog(owned_ship):
    """Resolve the owned ship's catalog spec, or None when unknown."""
    if owned_ship is None:
        return None
    from . import ship as _ship_cat_mod
    try:
        return _ship_cat_mod.find_ship(owned_ship.ship_id)
    except KeyError:
        return None


def _hud_xp_line(player_level: int, player_xp: int, ctx) -> tuple[str, tuple[int, int, int]]:
    """Return ``(line, fg)`` for the HUD XP progress row."""
    from .xp import xp_for_level as _xp_for_level, _xp_to_next as _xp_to_next
    _xp_total = _xp_for_level(player_level) if player_level > 1 else 0
    _xp_into = max(0, player_xp - _xp_total)
    return _xp_hud_line(
        player_level, _xp_into, _xp_to_next(player_level),
        getattr(ctx, 'player_skill_points', 0),
    )


def _render_hud_footer(console, hud_x, hud_view_height, *, xp_line, xp_fg) -> None:
    """Paint the XP bar + bottom hints anchored to the panel's bottom edge."""
    _xp_y, _bump_y, _exit_y = _footer_rows(hud_view_height)
    console.print(x=hud_x, y=_xp_y, string=xp_line, fg=xp_fg)
    console.print(x=hud_x, y=_bump_y, string="bump to interact", fg=COLOR_VALUE_DIM)
    console.print(x=hud_x, y=_exit_y, string="ESC to quit", fg=COLOR_VALUE_DIM)


def _render_ship_identity(console, hud_x, y, *, ship_name, location, date_str) -> int:
    """Paint the ship name / location / date rows; return the next row."""
    console.print(x=hud_x, y=y, string=ship_name.upper(), fg=COLOR_SHIP_NAME)
    y += 1
    if location:
        console.print(x=hud_x, y=y, string=location.upper(), fg=COLOR_VALUE_DIM)
    y += 1
    if date_str:
        console.print(x=hud_x, y=y, string=date_str, fg=COLOR_VALUE_DIM)
    return y + 1


def _render_ship_stat_rows(console, hud_x, y, *, fuel, max_fuel, hull_pct, cargo_used, max_cargo, weapons_n, weapon_slots, modules_n, module_slots, eff_spd, stats, ground_stats) -> int:
    """Paint the space-mode stat rows (fuel…speed + skills); return next row."""
    console.print(x=hud_x, y=y, string="Fuel", fg=COLOR_SHIP_LABEL)
    console.print(x=hud_x + 5, y=y, string=f"{fuel}/{max_fuel}", fg=COLOR_FUEL_OK if fuel >= 10 else COLOR_FUEL_LOW)
    y += 1
    console.print(x=hud_x, y=y, string="Hull", fg=COLOR_SHIP_LABEL)
    console.print(x=hud_x + 5, y=y, string=f"{hull_pct}%", fg=COLOR_HP_GOOD if hull_pct >= 50 else COLOR_HP_LOW)
    y += 1
    console.print(x=hud_x, y=y, string="Cargo", fg=COLOR_SHIP_LABEL)
    console.print(x=hud_x + 6, y=y, string=f"{cargo_used}/{max_cargo}", fg=COLOR_SHIP_VALUE)
    y += 1
    console.print(x=hud_x, y=y, string="Wpn", fg=COLOR_SHIP_LABEL)
    console.print(x=hud_x + 5, y=y, string=f"{weapons_n}/{weapon_slots}", fg=COLOR_SHIP_VALUE)
    y += 1
    console.print(x=hud_x, y=y, string="Mod", fg=COLOR_SHIP_LABEL)
    console.print(x=hud_x + 5, y=y, string=f"{modules_n}/{module_slots}", fg=COLOR_SHIP_VALUE)
    y += 1
    console.print(x=hud_x, y=y, string="Spd", fg=COLOR_SHIP_LABEL)
    console.print(x=hud_x + 5, y=y, string=str(eff_spd), fg=COLOR_SHIP_VALUE)
    y += 3
    _render_skill_line(console, hud_x, y, stats)
    y += 1
    if ground_stats is not None:
        _render_ground_stat_line(console, hud_x, y, ground_stats)
        y += 1
    return y


def _render_space_hud(console, hud_x, ctx, *, ship_catalog, location, date_str, hud_view_height, xp_line, xp_fg) -> None:
    """Paint the space-mode HUD body below the title."""
    from . import ship as _ship_mod
    owned_ship = ctx.player_owned_ship
    stats = ctx.stats
    ground_stats = ctx.ground_stats
    ship_name = _ship_mod.ship_display_name(owned_ship)
    hull_pct = _ship_mod.hull_integrity_pct(owned_ship)
    cargo_used, max_cargo = _cargo_used_max(owned_ship, ship_catalog)
    eff_spd = _ship_mod.effective_speed(ship_catalog, owned_ship)
    weapons_n = len(getattr(owned_ship, 'weapons', ()) or ())
    modules_n = len(getattr(owned_ship, 'modules', ()) or ())
    y = _render_ship_identity(console, hud_x, 2, ship_name=ship_name, location=location, date_str=date_str)
    y = _render_ship_stat_rows(
        console, hud_x, y,
        fuel=getattr(owned_ship, 'fuel', 0),
        max_fuel=getattr(ship_catalog, 'max_fuel', 1),
        hull_pct=hull_pct,
        cargo_used=cargo_used, max_cargo=max_cargo,
        weapons_n=weapons_n, weapon_slots=getattr(ship_catalog, 'weapon_slots', 0),
        modules_n=modules_n, module_slots=getattr(ship_catalog, 'module_slots', 0),
        eff_spd=eff_spd, stats=stats, ground_stats=ground_stats,
    )
    y += 1
    _render_divider(console, hud_x, y)
    y += 3
    _render_help_lines(console, hud_x, y, [
        ("G", "Go To"), ("P", "Pickup"), ("M", "Map"), ("I", "Cargo"),
        ("T", "Comms"), ("C", "Character"), ("F", "Factions"),
        (CONSOLE_LOG_KEY, CONSOLE_LOG_LABEL), ("?", "Guide"), ("numpad", "Move"),
    ])
    _render_hud_footer(console, hud_x, hud_view_height, xp_line=xp_line, xp_fg=xp_fg)


def _render_city_identity(console, hud_x, y, *, species_name, class_name, location, date_str) -> int:
    """Paint the species / class / location / date rows; return next row."""
    if species_name:
        console.print(x=hud_x, y=y, string=species_name.title(), fg=COLOR_VALUE_WHITE)
    y += 1
    if class_name:
        console.print(x=hud_x, y=y, string=class_name.title(), fg=COLOR_VALUE_WHITE)
    y += 1
    if location:
        console.print(x=hud_x, y=y, string=location, fg=COLOR_VALUE_DIM)
    y += 1
    if date_str:
        console.print(x=hud_x, y=y, string=date_str, fg=COLOR_VALUE_DIM)
    return y + 1


def _render_city_stat_rows(console, hud_x, y, *, ctx, stats, owned_ship, ship_catalog, ground_stats) -> int:
    """Paint HP / cargo / credits / skill rows; return the next row."""
    console.print(x=hud_x, y=y, string="HP", fg=COLOR_LABEL)
    hp = max(0, ctx.ground_hp)
    max_hp = max(1, ctx.ground_max_hp)
    console.print(x=hud_x + 3, y=y, string=f"{hp}/{max_hp}", fg=COLOR_HP_GOOD if hp * 2 >= max_hp else COLOR_HP_LOW)
    y += 1
    console.print(x=hud_x, y=y, string="Cargo", fg=COLOR_LABEL)
    cargo_used, max_cargo = _cargo_used_max(owned_ship, ship_catalog)
    console.print(x=hud_x + 6, y=y, string=f"{cargo_used}/{max_cargo}", fg=COLOR_VALUE_WHITE)
    y += 1
    console.print(x=hud_x, y=y, string="$", fg=COLOR_LABEL)
    console.print(x=hud_x + 2, y=y, string=str(stats.credits), fg=COLOR_VALUE_WHITE)
    y += 3
    _render_skill_line(console, hud_x, y, stats)
    y += 1
    if ground_stats is not None:
        _render_ground_stat_line(console, hud_x, y, ground_stats)
        y += 1
    return y


def _render_city_terminals(console, hud_x, y, *, has_armory_terminal, has_mech_terminal, has_trade_terminal) -> int:
    """Paint the terminal indicator rows; return the next row."""
    if has_armory_terminal:
        console.print(x=hud_x, y=y, string="A  Armory", fg=COLOR_LABEL)
        y += 1
    if has_mech_terminal:
        console.print(x=hud_x, y=y, string="%  Mechanic", fg=COLOR_LABEL)
        y += 1
    if has_trade_terminal:
        console.print(x=hud_x, y=y, string="=  Trade", fg=COLOR_LABEL)
    return y


def _render_city_help_lines(console, hud_x, y, mode) -> int:
    """Paint the movement key hints; return the next row."""
    _help_lines = [
        ("Q", "Quest Log"), ("I", "Cargo"), ("C", "Character"),
        ("F", "Factions"), (CONSOLE_LOG_KEY, CONSOLE_LOG_LABEL),
        ("?", "Guide"), ("numpad", "Move"),
    ]
    if mode == "dungeon":
        _help_lines[0:0] = [("P", "Pickup"), ("O", "Explore"), ("G", "Go To")]
    return _render_help_lines(console, hud_x, y, _help_lines)


def _render_city_hud(console, hud_x, ctx, *, ship_catalog, location, date_str, mode, hud_view_height, xp_line, xp_fg, has_trade_terminal, has_mech_terminal, has_armory_terminal) -> None:
    """Paint the city/dungeon-mode HUD body below the title."""
    character = ctx.character_info
    y = _render_city_identity(
        console, hud_x, 2,
        species_name=character.get("species_name", ""),
        class_name=character.get("class_name", ""),
        location=location, date_str=date_str,
    )
    _render_divider(console, hud_x, y)
    y += 2
    y = _render_city_stat_rows(
        console, hud_x, y,
        ctx=ctx, stats=ctx.stats,
        owned_ship=ctx.player_owned_ship, ship_catalog=ship_catalog,
        ground_stats=ctx.ground_stats,
    )
    y += 1
    _render_divider(console, hud_x, y)
    y += 1
    y = _render_city_terminals(
        console, hud_x, y,
        has_armory_terminal=has_armory_terminal,
        has_mech_terminal=has_mech_terminal,
        has_trade_terminal=has_trade_terminal,
    )
    y += 1
    _render_divider(console, hud_x, y)
    y += 2
    _render_city_help_lines(console, hud_x, y, mode)
    _render_hud_footer(console, hud_x, hud_view_height, xp_line=xp_line, xp_fg=xp_fg)


def render_hud(
    console: FrameBuffer,
    ctx: GameContext,
    *,
    screen_width: int,
    hud_view_height: int,
    location: str | None = None,
    mode: str = "city",
    has_trade_terminal: bool = False,    # city mode: show = terminal hint
    has_mech_terminal: bool = False,     # city mode: show % terminal hint
    has_armory_terminal: bool = False,    # city mode: show A terminal hint
) -> None:
    """Paint the right-side HUD; everything except layout comes from ``ctx``."""
    from .time import format_date as _format_date
    date_str = _format_date(ctx)
    hud_x = screen_width - HUD_WIDTH
    _xp_line, _xp_fg = _hud_xp_line(ctx.player_level, ctx.player_xp, ctx)
    console.print(x=hud_x, y=0, string="Spacehack", fg=COLOR_HUD_TITLE)
    _ship_catalog = _resolve_ship_catalog(ctx.player_owned_ship)
    if mode == "space" and ctx.player_owned_ship is not None and _ship_catalog is not None:
        _render_space_hud(
            console, hud_x, ctx,
            ship_catalog=_ship_catalog,
            location=location, date_str=date_str,
            hud_view_height=hud_view_height,
            xp_line=_xp_line, xp_fg=_xp_fg,
        )
    else:
        _render_city_hud(
            console, hud_x, ctx,
            ship_catalog=_ship_catalog,
            location=location, date_str=date_str, mode=mode,
            hud_view_height=hud_view_height,
            xp_line=_xp_line, xp_fg=_xp_fg,
            has_trade_terminal=has_trade_terminal,
            has_mech_terminal=has_mech_terminal,
            has_armory_terminal=has_armory_terminal,
        )


# ---------------------------------------------------------------------------
# Combat HUD
# ---------------------------------------------------------------------------

# Combat HUD palette
COLOR_COMBAT_TITLE: tuple[int, int, int] = (255, 80, 80)           # red combat title
COLOR_HULL_BAR_GREEN: tuple[int, int, int] = (100, 235, 115)       # bright green
COLOR_HULL_BAR_YELLOW: tuple[int, int, int] = (255, 220, 80)       # amber
COLOR_HULL_BAR_RED: tuple[int, int, int] = (255, 80, 80)           # red
COLOR_SHIELD_BAR: tuple[int, int, int] = (175, 230, 255)           # bright cyan
COLOR_AP: tuple[int, int, int] = (255, 220, 80)                    # gold
COLOR_POWER: tuple[int, int, int] = (225, 240, 255)                # near-white blue
COLOR_COMBAT_WEAPON: tuple[int, int, int] = (255, 200, 100)        # gold
COLOR_COMBAT_WEAPON_DIM: tuple[int, int, int] = (205, 190, 145)     # readable inactive state
COLOR_COMBAT_LOG: tuple[int, int, int] = (235, 235, 230)           # bright silver
COLOR_COMBAT_ACTION: tuple[int, int, int] = (245, 250, 235)        # near-white action text
COLOR_COMBAT_MODE: tuple[int, int, int] = (255, 255, 150)          # yellow for mode indicator

# The native overlay renders HUD text at roughly half the cell width, so
# each combat line has room for ~40 characters; the cell renderer clips
# at the screen edge. Truncate generously instead of at HUD_WIDTH (20).
_COMBAT_TEXT_MAX: int = 40


_BAR_CHAR_FULL: str = "#"   # full marker
_BAR_CHAR_EMPTY: str = "."   # empty marker
_UNLIMITED_AMMO_LABEL: str = "INF"


def _bar_str(value: int, max_value: int, width: int = 10) -> str:
    """Return a CP437-safe bar string with ``#`` for filled and ``.`` for empty.

    Exported so ground combat can import the same function.
    """
    if max_value <= 0:
        return _BAR_CHAR_EMPTY * width
    full = max(0, min(width, value * width // max_value))
    return _BAR_CHAR_FULL * full + _BAR_CHAR_EMPTY * (width - full)


def _render_xp_bar(current: int, needed: int, width: int = 10) -> str:
    """Return a compact XP progress bar using CP437-safe chars.

    ``#`` = filled, ``-`` = empty.  ``current`` is XP earned into
    the current level; ``needed`` is total XP to reach the next level.

    Shared between HUD and Character screen.
    """
    if needed <= 0:
        return "#" * width
    filled = max(0, min(width, current * width // needed))
    return "#" * filled + "-" * (width - filled)


def _xp_hud_line(
    player_level: int,
    xp_into: int,
    xp_needed: int,
    points: int,
) -> tuple[str, tuple[int, int, int]]:
    """Return ``(line, fg)`` for the HUD XP row.

    When ``points > 0`` (unspent skill points) the row renders in
    gold and appends the count (``LV 3 [####-] +9 PTS``) so the
    player remembers to open the Character screen (C) and spend
    them. The bar shrinks to 5 cells to fit within ``HUD_WIDTH``.
    """
    if points > 0:
        # Shrink the bar so the full "+N PTS" suffix always fits within
        # HUD_WIDTH, even for 2-3 digit point counts (9/level adds up).
        _base = f"LV {player_level:>2} ["
        _suffix = f" +{points} PTS"
        _bar_width = max(1, HUD_WIDTH - len(_base) - len("]") - len(_suffix))
        _bar = _render_xp_bar(xp_into, xp_needed, width=_bar_width)
        return (f"{_base}{_bar}]{_suffix}")[:HUD_WIDTH], COLOR_HUD_TITLE
    _bar = _render_xp_bar(xp_into, xp_needed)
    return f"LV {player_level:>2} [{_bar}]"[:HUD_WIDTH], COLOR_VALUE_DIM


def _hull_bar_color(pct: float) -> tuple[int, int, int]:
    if pct >= 0.5:
        return COLOR_HULL_BAR_GREEN
    if pct >= 0.25:
        return COLOR_HULL_BAR_YELLOW
    return COLOR_HULL_BAR_RED


def _render_combat_header(console, hud_x, y, player_mode) -> int:
    """Paint the combat title, mode indicator, and divider; return next row."""
    console.print(x=hud_x, y=y, string="> COMBAT <", fg=COLOR_COMBAT_TITLE)
    y += 1
    console.print(x=hud_x, y=y, string=f"[{player_mode}]", fg=COLOR_COMBAT_MODE)
    y += 2
    console.print(x=hud_x, y=y, string="-" * HUD_WIDTH, fg=COLOR_DIVIDER)
    return y + 1


def _render_hull_shield_rows(console, hud_x, y, player_state) -> int:
    """Paint the player's hull + shield bars; return the next row."""
    phull = player_state.get("hull", 100)
    pmax_hull = player_state.get("max_hull", 100)
    pshields = player_state.get("shields", 0)
    pmax_shields = player_state.get("max_shields", 0)
    hull_pct = phull / max(pmax_hull, 1)
    hull_color = _hull_bar_color(hull_pct)
    if pmax_shields > 0:
        # Same 10-cell bar as Hull below; the regen suffix is in POINTS so
        # "+N" can't be misread as percentage points (12/20 +4 fills the
        # bar toward 16/20 next turn).
        _rate = player_state.get("shield_regen_rate", 0)   # S-key setting (paid)
        _free = player_state.get("shield_recharge_bonus", 0)  # ship base + modules
        _total = _rate + _free
        _bar = _bar_str(pshields, pmax_shields, width=10)
        _shd = f"Shd  {_bar} {pshields}/{pmax_shields}"
        if _total > 0:
            _shd += f" +{_total}"
        console.print(x=hud_x, y=y, string=_shd[:_COMBAT_TEXT_MAX], fg=COLOR_SHIELD_BAR)
        # Level indicator (white bg) tracks ONLY the S-key rate, so
        # pressing S moves the highlight 1:1 with the setting.
        for _i in range(min(_rate, len(_bar))):
            console.print(x=hud_x + 5 + _i, y=y, string=_bar[_i], fg=COLOR_SHIELD_BAR, bg=(255, 255, 255))
        y += 1
    console.print(x=hud_x, y=y, string=f"Hull {_bar_str(phull, pmax_hull)} {int(hull_pct * 100)}%", fg=hull_color)
    return y + 1


def _render_ap_evade_pow_rows(console, hud_x, y, player_state, evade_bonus) -> int:
    """Paint the player's AP / evade / power rows; return the next row."""
    pap = player_state.get("ap_remaining", 0)
    pap_total = player_state.get("ap_total", 3)
    console.print(x=hud_x, y=y, string=f"AP: {pap}/{pap_total}", fg=COLOR_AP if pap > 0 else COLOR_HULL_BAR_RED)
    y += 1
    if evade_bonus is not None:
        # No colon so the row aligns with the bar-style Hull/Shd rows;
        # green when movement has stacked any dodge bonus.
        evade_color = COLOR_EVADE if evade_bonus > 0 else COLOR_VALUE_DIM
        console.print(x=hud_x, y=y, string=f"Evade +{evade_bonus}%", fg=evade_color)
        y += 1
    ppow = player_state.get("power_pool", 0)
    ppow_max = player_state.get("max_power", 10)
    ppow_gen = player_state.get("power_gen", 0)
    console.print(x=hud_x, y=y, string=f"Pow: {ppow}/{ppow_max} (+{ppow_gen})", fg=COLOR_POWER)
    return y + 2


def _render_player_block(console, hud_x, y, player_state, evade_bonus) -> int:
    """Paint the PLAYER block (hull/shield/AP/evade/power); return next row."""
    console.print(x=hud_x, y=y, string="PLAYER", fg=COLOR_LABEL)
    y += 1
    y = _render_hull_shield_rows(console, hud_x, y, player_state)
    return _render_ap_evade_pow_rows(console, hud_x, y, player_state, evade_bonus)


def _enemy_distance_color(dist: int, range_weapon_id: str):
    """Range-band color for an enemy's distance, or None when unknown."""
    from .data.weapons import find_weapon as _fw
    try:
        _ws = _fw(range_weapon_id)
    except KeyError:
        return None
    return range_band_color(dist, _ws.max_range, _ws.min_range)


def _render_enemy_row(console, hud_x, y, enemy, is_target, ppos, range_weapon_id) -> int:
    """Paint one enemy's name + distance + bars; return the next row."""
    marker = ">" if is_target else " "
    _name = enemy.name[:9] if len(enemy.name) > 9 else enemy.name
    _name_str = f"{marker}{_name}"
    _name_fg = COLOR_COMBAT_TITLE if is_target else COLOR_VALUE_DIM
    console.print(x=hud_x, y=y, string=_name_str, fg=_name_fg)
    if ppos is not None and hasattr(enemy, 'pos'):
        import math as _m
        _dist = int(_m.hypot(ppos.x - enemy.pos.x, ppos.y - enemy.pos.y))
        if range_weapon_id is not None:
            _dc = _enemy_distance_color(_dist, range_weapon_id)
            if _dc is not None:
                console.print(x=hud_x + len(_name_str) + 2, y=y, string=str(_dist), fg=_dc)
        else:
            console.print(x=hud_x + len(_name_str) + 2, y=y, string=str(_dist), fg=COLOR_VALUE_DIM)
    y += 1
    if enemy.max_shields > 0:
        _e_shd_pct = enemy.shields / max(enemy.max_shields, 1)
        _shd_bar = _bar_str(enemy.shields, enemy.max_shields, width=5)
        _shd_line = f"  Shd {_shd_bar} {int(_e_shd_pct * 100)}%"
        console.print(x=hud_x, y=y, string=_shd_line[:HUD_WIDTH], fg=COLOR_SHIELD_BAR)
        y += 1
    _e_hull_pct = enemy.hull / max(enemy.max_hull, 1)
    _bar = _bar_str(enemy.hull, enemy.max_hull, width=5)
    _hull_line = f"  Hul {_bar} {int(_e_hull_pct * 100)}%"
    console.print(x=hud_x, y=y, string=_hull_line[:HUD_WIDTH], fg=_hull_bar_color(_e_hull_pct))
    return y + 1


def _render_enemies_block(console, hud_x, y, enemies, target_idx, screen_height, player_state, range_weapon_id) -> int:
    """Paint the ENEMIES list with name + distance + bars; return next row."""
    console.print(x=hud_x, y=y, string="ENEMIES", fg=COLOR_DIVIDER)
    y += 1
    ppos = player_state.get("pos")
    _alive_count = 0
    for _ei, _e in enumerate(enemies):
        if y > screen_height - 20:
            break
        if not getattr(_e, 'alive', True):
            continue
        is_target = _alive_count == target_idx
        _alive_count += 1
        y = _render_enemy_row(console, hud_x, y, _e, is_target, ppos, range_weapon_id)
    return y + 1


def _render_weapon_row(console, hud_x, y, slot, wid, ws, wammo, is_active, hit_chances) -> int:
    """Paint one weapon's name / hit / cost rows; return the next row."""
    sel_mark = "[x]" if is_active else "[ ]"
    name_str = f"{sel_mark}[{slot+1}] {ws.name}"
    fg_wpn = COLOR_COMBAT_WEAPON if is_active else COLOR_COMBAT_WEAPON_DIM
    console.print(x=hud_x, y=y, string=name_str[:_COMBAT_TEXT_MAX], fg=fg_wpn)
    y += 1
    _w_hc = hit_chances.get(wid) if hit_chances else None
    if _w_hc is not None:
        stats_line = f"     DMG {ws.damage} HIT {_w_hc}%"
    else:
        stats_line = f"     DMG {ws.damage} ACC {ws.accuracy}%"
    console.print(x=hud_x, y=y, string=stats_line[:_COMBAT_TEXT_MAX], fg=COLOR_VALUE_DIM)
    y += 1
    if ws.slot_type in ("energy", "plasma"):
        cost_line = f"     POW {ws.power_cost} AP {ws.ap_cost}"
    else:
        ammo_str = f"{wammo}/{ws.ammo_capacity}" if ws.ammo_capacity > 0 else _UNLIMITED_AMMO_LABEL
        cost_line = f"     AMMO {ammo_str} AP {ws.ap_cost}"
    console.print(x=hud_x, y=y, string=cost_line[:_COMBAT_TEXT_MAX], fg=COLOR_VALUE_DIM)
    return y + 1


def volley_costs(weapon_list, active_weapons, find_weapon) -> tuple[int, int, int]:
    """Return ``(count, max_ap, sum_pow)`` for the armed volley's active weapons.

    Burst AP is charged once as the highest per-weapon AP cost; power is
    charged per energy/plasma weapon (so it sums). ``find_weapon`` is the
    domain weapon catalog lookup (space or ground).
    """
    _count = 0
    _max_ap = 0
    _sum_pow = 0
    for i, wid in enumerate(weapon_list):
        is_active = active_weapons[i] if active_weapons else True
        if not is_active:
            continue
        try:
            ws = find_weapon(wid)
        except KeyError:
            continue
        _count += 1
        _max_ap = max(_max_ap, ws.ap_cost)
        if getattr(ws, "slot_type", "") in ("energy", "plasma"):
            _sum_pow += getattr(ws, "power_cost", 0)
    return _count, _max_ap, _sum_pow


def _render_weapons_block(console, hud_x, y, weapon_list, active_weapons, player_state, hit_chances) -> int:
    """Paint the WEAPONS list + armed-volley cost; return the next row."""
    from .data.weapons import find_weapon as _fw
    _count, _max_ap, _sum_pow = volley_costs(weapon_list, active_weapons, _fw)
    console.print(x=hud_x, y=y, string="WEAPONS", fg=COLOR_DIVIDER)
    if _count:
        console.print(x=hud_x + 8, y=y, string=f"[{_count}]", fg=COLOR_VALUE_DIM)
        _ap_fg = COLOR_HP_GOOD if _max_ap <= player_state.get("ap_remaining", 0) else COLOR_HP_LOW
        console.print(x=hud_x + 12, y=y, string=f"{_max_ap}AP", fg=_ap_fg)
        if _sum_pow:
            _pow_fg = COLOR_HP_GOOD if _sum_pow <= player_state.get("power_pool", 0) else COLOR_HP_LOW
            console.print(x=hud_x + 16, y=y, string=f"{_sum_pow}POW", fg=_pow_fg)
    y += 1
    for i, wid in enumerate(weapon_list):
        try:
            ws = _fw(wid)
        except KeyError:
            continue
        wammo = player_state.get("weapon_ammo", {}).get(i, 0)
        is_active = active_weapons[i] if active_weapons else True
        y = _render_weapon_row(console, hud_x, y, i, wid, ws, wammo, is_active, hit_chances)
    return y + 1


def _render_combat_actions(console, hud_x, y, weapon_list) -> int:
    """Paint the ACTIONS key list; return the next row."""
    console.print(x=hud_x, y=y, string="ACTIONS", fg=COLOR_DIVIDER)
    y += 1
    actions = [
        ("[Tab]", "Target"),
        ("[m]", "Move"),
        ("[f]", "Fire"),
        ("[s]", "Shields"),
        ("[w]", "Wait"),
    ]
    # Only advertise the digit-swap affordance when there is something
    # to swap between; the label embeds the real weapon count so the
    # player doesn't expect digit 4..9 to work with 3 weapons mounted.
    if len(weapon_list) > 1:
        actions.insert(3, (f"[1-{len(weapon_list)}]", "Toggle Wpn"))
    for key, desc in actions:
        console.print(x=hud_x, y=y, string=f"{key} {desc}"[:HUD_WIDTH-1], fg=COLOR_COMBAT_ACTION)
        y += 1
    return y


def render_combat_hud(
    console: FrameBuffer,
    *,
    screen_width: int,
    screen_height: int,
    player_state: dict,
    enemies: list = (),                  # list[EnemyInstance]
    target_idx: int = 0,
    player_mode: str = "DEFAULT",       # "DEFAULT", "MOVING", "FIRING"
    active_weapons: list[bool] | None = None,
    weapon_list: tuple[str, ...] = (),
    flee_chance: int | None = None,
    hit_chances: dict[str, int] | None = None,  # per-weapon hit % vs current target
    evade_bonus: int | None = None,      # player's current dodge % (movement + piloting)
    range_weapon_id: str | None = None,  # weapon id for coloring distance by range
) -> None:
    """Paint the combat HUD replacing the normal space HUD.

    Right panel, top to bottom: COMBAT title, PLAYER block, ENEMIES
    block, WEAPONS list, then ACTIONS key hints.
    """
    hud_x = screen_width - HUD_WIDTH
    y = _render_combat_header(console, hud_x, 0, player_mode)
    y = _render_player_block(console, hud_x, y, player_state, evade_bonus)
    y = _render_enemies_block(console, hud_x, y, enemies, target_idx, screen_height, player_state, range_weapon_id)
    y = _render_weapons_block(console, hud_x, y, weapon_list, active_weapons, player_state, hit_chances)
    _render_combat_actions(console, hud_x, y, weapon_list)


