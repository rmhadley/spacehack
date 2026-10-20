"""Right-side HUD: the unified core plus per-mode bands (doc 104).

Layout (assumes ``screen_width = SCREEN_WIDTH`` and
``hud_view_height = SCREEN_HEIGHT - MSG_LOG_HEIGHT``):

City mode (default; doc 104's reserved regions — the bands swap, the
core and the WEAPONS anchor never move):
    +-----------------+----------+
    |                 | Spacehack|
    |                 | Eri City |  A band (location/date)
    |       MAP       | 2160-04-12|  A
    |     REGION      | -------- |
    |                 | HP 10/10 |  B core (hud_core)
    |                 | Armor  0 |  B
    |                 | Cargo 0/0|  B
    |                 |          |  B status slot (blank when empty)
    |                 | WEAPONS  |  C anchor
    |                 | ..       |  D band (terminals, help)
    +-----------------+----------+

Space mode (when ``owned_ship`` is provided; doc 104 Phase 3 — the
space pair mirrors the ground pair's regions, and the core shares one
y with the space-fight core so the explore↔fight boundary never moves
it):
    +-----------------+----------+
    |                 | Spacehack|
    |                 | SCOUT    |  A band (ship name/location/date)
    |       MAP       | 2160-04-12| A
    |     REGION      | Fuel 90/100| A
    |                 | Spd 5     |  A
    |                 | -------- |  A-close divider
    |                 | Hull ###..|  B core (hud_core)
    |                 | Shd  ##...|  B (blank without shields)
    |                 | Cargo 0/10|  B
    |                 |          |  B status slot (blank when empty)
    |                 |          |  C reserved (the fight's WEAPONS
    |                 |          |  budget, empty exploring)
    |                 | -------- |  C-close divider
    |                 | [G] GoTo…|  D band (help lines)
    |                 | LV 3 [#-]|  footer (XP row, bottom-anchored)
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
from .hud_core import (
    COLOR_HP_GOOD as COLOR_HP_GOOD,   # re-exported for the combat importers
    COLOR_HP_LOW as COLOR_HP_LOW,     # (hud_core owns the pair, Phase 1)
    GROUND_BAND_Y,
    GROUND_CORE_Y,
    GROUND_WEAPONS_Y,
    HUD_TEXT_MAX,
    SPACE_BAND_Y,
    SPACE_CORE_Y,
    SPACE_WEAPONS_Y,
    _bar_str,
    paint_cargo_row,
    paint_hull_shield_rows,
    paint_hp_armor_rows,
    paint_status_slot,
    paint_xp_footer,
    space_weapons_rows,
)
from .ui import COLOR_DIVIDER, COLOR_VALUE_DIM, COLOR_VALUE_WHITE  # shared palette (single source)

if TYPE_CHECKING:
    from .game_context import GameContext


# High-contrast HUD palette: neutral labels and values carry the reading
# load, while saturated colors communicate health and resource state.
# The shared white/dim/divider colors come from ui.py so brightness stays
# consistent across menus and gameplay. The HP good/low pair lives in
# hud_core (the unified core's meter painter owns it) and is re-exported
# here for the combat importers.
COLOR_HUD_TITLE: tuple[int, int, int] = (255, 205, 95)             # vivid gold
COLOR_LABEL: tuple[int, int, int] = (245, 245, 235)                # near-white label
COLOR_EVADE: tuple[int, int, int] = (135, 235, 150)                # green, positive-buff accent

# Player glyph health zones — the on-map character mirrors the ground
# HP bar: the SPECIES color while healthy (doc 49 — passed in by the
# caller as the healthy state), amber below half, red below a quarter,
# so a wounded run signals "heal now" without checking the HUD panel.
# Shared by the frame presenter (game_loop) and the ground combat
# renderer so every on-foot view stays in sync.
COLOR_PLAYER_HEALTHY: tuple[int, int, int] = (255, 255, 255)        # human default
COLOR_PLAYER_WOUNDED: tuple[int, int, int] = (255, 200, 80)         # < half — amber
COLOR_PLAYER_CRITICAL: tuple[int, int, int] = (255, 80, 80)          # < quarter — red

# Space-mode HUD palette — cyan is reserved for the ship identity.
COLOR_SHIP_NAME: tuple[int, int, int] = (150, 235, 255)             # bright cyan
COLOR_SHIP_VALUE: tuple[int, int, int] = (255, 255, 255)            # white stat values
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
COLOR_RANGE_FLOOR: tuple[int, int, int] = (255, 100, 255)     # inside a missile's hard floor (doc 57) — will not fire


def ground_player_fg(
    hp: int, max_hp: int,
    healthy_color: tuple[int, int, int] = COLOR_PLAYER_HEALTHY,
) -> tuple[int, int, int]:
    """Return the fg color for the player's on-map glyph from ground HP.

    The species color while at half health and above (doc 49 — the
    healthy state is the species' identity; callers pass
    :func:`spacehack.character.species_appearance_for`), amber while
    at half down to a quarter, red below a quarter — the same
    half-health cue the HUD bar uses, with one extra warning stage
    below it. Wounded/critical are universal regardless of species.
    Pure: callers assign the result to the player entity's ``fg``
    before rendering.
    """
    if max_hp <= 0:
        return healthy_color
    if hp * 4 < max_hp:
        return COLOR_PLAYER_CRITICAL
    if hp * 2 < max_hp:
        return COLOR_PLAYER_WOUNDED
    return healthy_color


def range_band_color(
    dist: float,
    weapon_max_range: int,
    weapon_min_range: int = 0,
    *,
    hard_floor: bool = False,
) -> tuple[int, int, int]:
    """Color for a combat distance, matching the targeting-line bands.

    Orange strictly inside ``min_range`` when one exists (the
    point-blank penalty zone — checked first so a min band inside the
    close zone stays visible), green within the close-bonus zone
    (``max_range // 2``), yellow within ``max_range``, red beyond.
    ``hard_floor`` (doc 57 SETTLED 2) swaps the orange for the
    distinct magenta refusal read — a flight missile inside its floor
    will not fire at all, a different state than a penalty.
    """
    if weapon_min_range > 0 and dist < weapon_min_range:
        return COLOR_RANGE_FLOOR if hard_floor else COLOR_RANGE_ORANGE
    if dist <= weapon_max_range // 2:
        return COLOR_RANGE_GREEN
    if dist <= weapon_max_range:
        return COLOR_RANGE_YELLOW
    return COLOR_RANGE_RED


@dataclass
class HudStats:
    """The stats shown in the HUD right now.

    Hull HP is deliberately absent (doc 49 SETTLED 5): hull points
    are ship + modules (:func:`ship.hull_cur_max`), never a character
    stat.
    """
    credits: int
    gunnery: int = 0
    piloting: int = 0
    engineering: int = 0


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _render_divider(console: FrameBuffer, hud_x: int, y: int) -> None:
    """Print a full-width divider line at ``(hud_x, y)``.

    Spans the panel's real glyph capacity (HUD_TEXT_MAX half-width
    characters). Pure print — caller owns y advancement.
    """
    console.print(x=hud_x, y=y, string="-" * HUD_TEXT_MAX, fg=COLOR_DIVIDER)


def _cargo_used_max(owned_ship, ship_catalog, ctx=None) -> tuple[int, int]:
    """Return ``(cargo_used, max_cargo)`` for the player's ship.

    ``cargo_used`` comes from the owned-ship state (includes mission
    cargo); ``max_cargo`` is the hull's base capacity plus module
    bonuses and the Merchant trait's +10 via
    :func:`ship.effective_max_cargo`. Safe when either argument is
    ``None`` (returns zeroed values).

    Shared by the space and city HUD branches so the capacity math
    can never drift between them.
    """
    cargo_used = getattr(owned_ship, 'cargo_used', 0)
    max_cargo = getattr(ship_catalog, 'max_cargo', 0)
    if owned_ship is not None and ship_catalog is not None:
        from . import ship as _ship_mod
        max_cargo = _ship_mod.effective_max_cargo(
            ship_catalog, owned_ship, ctx,
        )
    return cargo_used, max_cargo


def ground_holster_names(ctx) -> str:
    """Comma-joined holstered-set weapon names ('' when the set is empty).

    One holster-names source for the combat weapons panel and the
    dungeon HUD block (doc 52.3).
    """
    from .ground_equipment import display_name

    return ", ".join(
        display_name("weapon", _inst.weapon_id, _inst.quality)
        for _inst in getattr(ctx, "holstered_ground_weapons", None) or []
    )


def bandolier_hud_lines(ctx) -> list[str]:
    """``CODE cur/max`` per carried caliber — the combat + dungeon ammo lines.

    Calibers are the active+holstered union in catalog order (doc 52.3's
    folded default); current reads the bandolier dict, max is
    ``effective_cap`` (the phase-4 gear seam), never the raw catalog cap.
    """
    from . import bandolier as _bandolier

    weapons = (
        list(getattr(ctx, "equipped_ground_weapons", None) or [])
        + list(getattr(ctx, "holstered_ground_weapons", None) or [])
    )
    pool = getattr(ctx, "bandolier", None) or {}
    return [
        f"{_bandolier.HUD_CODES[ammo_type]} "
        f"{pool.get(ammo_type, 0)}/{_bandolier.effective_cap(ammo_type)}"
        for ammo_type in _bandolier.carried_ammo_types(weapons)
    ]


def _render_help_lines(
    console: FrameBuffer,
    hud_x: int,
    start_y: int,
    help_lines: list[tuple[str, str]],
) -> int:
    """Render ``(key_label, description)`` pairs, two per row.

    Each row holds two hints so the
    block uses the panel's full width and roughly half its height.
    Keys render unpadded; a long key like ``numpad`` simply sticks out
    on its own row instead of padding every other key to match.
    Returns the next available ``y`` row.
    """
    y = start_y
    for i in range(0, len(help_lines), 2):
        _key, _desc = help_lines[i]
        left = f"[{_key}] {_desc:<12}"
        if i + 1 < len(help_lines):
            _key2, _desc2 = help_lines[i + 1]
            line = f"{left}[{_key2}] {_desc2}"
        else:
            line = left
        console.print(x=hud_x, y=y, string=line[:HUD_TEXT_MAX], fg=COLOR_HELP_DESC)
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


def _render_ship_identity(console, hud_x, y, *, ship_name, location, date_str) -> int:
    """Paint the ship name / location / date rows; return the next row."""
    console.print(x=hud_x, y=y, string=ship_name.upper()[:HUD_TEXT_MAX], fg=COLOR_SHIP_NAME)
    y += 1
    if location:
        console.print(x=hud_x, y=y, string=location.upper()[:HUD_TEXT_MAX], fg=COLOR_VALUE_DIM)
    y += 1
    if date_str:
        console.print(x=hud_x, y=y, string=date_str[:HUD_TEXT_MAX], fg=COLOR_VALUE_DIM)
    return y + 1


def _render_fuel_spd_rows(console, hud_x, y, *, fuel, max_fuel, eff_spd) -> int:
    """Paint the space A band's Fuel + Spd rows; return next row.

    Fuel keeps its 10-cell bar and cur/max read (green while
    adequate, amber when low). The slot-count summaries retired with
    doc 56 SETTLED 18 — the line keeps Spd only; power detail lives
    on the fitting screen. Hull/Shield/Cargo left the band for the
    shared core (doc 104 Phase 3 — hud_core paints them).
    """
    _fuel_fg = COLOR_FUEL_OK if fuel >= 10 else COLOR_FUEL_LOW
    console.print(
        x=hud_x, y=y,
        string=f"{'Fuel':<8}{_bar_str(fuel, max_fuel):<11}{fuel}/{max_fuel}"[:HUD_TEXT_MAX],
        fg=_fuel_fg,
    )
    console.print(
        x=hud_x, y=y + 1,
        string=f"Spd {eff_spd}"[:HUD_TEXT_MAX],
        fg=COLOR_SHIP_VALUE,
    )
    return y + 2


_SPACE_HELP_LINES = [
    ("G", "Go To"), ("P", "Pickup"), ("M", "Map"),
    ("T", "Comms"), ("C", "Character"), ("F", "Factions"),
    (CONSOLE_LOG_KEY, CONSOLE_LOG_LABEL), ("?", "Guide"), ("numpad", "Move"),
    ("ESC", "Pause"),
]


def _space_shield_reads(ship_catalog, owned_ship) -> tuple[int, int]:
    """``(max_shields, free_regen)`` for the exploration shield row —
    the one shield formula's out-of-combat read (lazy import, the
    pygame_overlay precedent): every fight initializes shields to max
    with rate 0, so passing these in paints the exact row the fight's
    round 0 shows."""
    from .combat._stats import _calc_max_shields, _free_shield_regen
    _modules = getattr(owned_ship, "modules", ()) or ()
    return (
        _calc_max_shields(ship_catalog, _modules),
        _free_shield_regen(ship_catalog, _modules),
    )


def _render_space_hud(console, hud_x, ctx, *, ship_catalog, location, date_str, hud_view_height, xp_line, xp_fg) -> None:
    """Paint the space-mode HUD body below the title, doc 104's
    reserved regions: A = ship name/location/date + Fuel/Spd, B = the
    shared core via hud_core (Hull, Shield, Cargo, the FIXED status
    slot — one painter, one y with the space-fight core), C = the
    empty reserved WEAPONS budget closed by the C divider (the fight's
    weapons land exactly inside it), D = the space help lines, then
    the footer. The band rows can change freely — the core's rows and
    y never move."""
    from . import ship as _ship_mod
    owned_ship = ctx.player_owned_ship
    ship_name = _ship_mod.ship_display_name(owned_ship)
    hull_cur, hull_max = _ship_mod.hull_cur_max(owned_ship, ship_catalog)
    cargo_used, max_cargo = _cargo_used_max(owned_ship, ship_catalog, ctx)
    _max_shields, _free_regen = _space_shield_reads(ship_catalog, owned_ship)
    _render_ship_identity(
        console, hud_x, SPACE_BAND_Y,
        ship_name=ship_name, location=location, date_str=date_str,
    )
    _render_fuel_spd_rows(
        console, hud_x, SPACE_BAND_Y + 3,
        fuel=getattr(owned_ship, 'fuel', 0),
        max_fuel=getattr(ship_catalog, 'max_fuel', 1),
        eff_spd=_ship_mod.effective_speed(ship_catalog, owned_ship),
    )
    _render_divider(console, hud_x, SPACE_CORE_Y - 1)
    y = paint_hull_shield_rows(
        console, hud_x, SPACE_CORE_Y,
        hull=hull_cur, max_hull=hull_max,
        shields=_max_shields, max_shields=_max_shields,
        shield_recharge_bonus=_free_regen,
    )
    y = paint_cargo_row(console, hud_x, y, used=cargo_used, max_cargo=max_cargo)
    paint_status_slot(console, hud_x, y, _status_segments(ctx))
    _weapons_budget = space_weapons_rows(len(getattr(owned_ship, "weapons", ()) or ()))
    _render_divider(console, hud_x, SPACE_WEAPONS_Y + _weapons_budget)
    _render_help_lines(
        console, hud_x, SPACE_WEAPONS_Y + _weapons_budget + 1, _SPACE_HELP_LINES,
    )
    paint_xp_footer(console, hud_x, hud_view_height, xp_line=xp_line, xp_fg=xp_fg)


def _render_city_identity(console, hud_x, y, *, location, date_str) -> int:
    """Paint the location / date band rows (doc 104 item 1: identity
    lives on the C screen — species/class retired with Phase 2);
    return next row."""
    if location:
        console.print(x=hud_x, y=y, string=location[:HUD_TEXT_MAX], fg=COLOR_VALUE_DIM)
    y += 1
    if date_str:
        console.print(x=hud_x, y=y, string=date_str[:HUD_TEXT_MAX], fg=COLOR_VALUE_DIM)
    return y + 1


def _render_city_core(console, hud_x, ctx, *, ship_catalog) -> int:
    """Region B — the shared core (doc 104): the health meter, cargo,
    and the FIXED status slot, painted by hud_core at the reserved
    rows — one painter, one y with the ground-combat core."""
    from .ground_equipment import sum_armor_defense as _sum_armor_defense
    hp = max(0, ctx.ground_hp)
    max_hp = max(1, ctx.ground_max_hp)
    y = paint_hp_armor_rows(
        console, hud_x, GROUND_CORE_Y,
        hp=hp, max_hp=max_hp,
        armor=_sum_armor_defense(
            getattr(ctx, "equipped_ground_armor", {}).values(),
        ),
    )
    cargo_used, max_cargo = _cargo_used_max(ctx.player_owned_ship, ship_catalog, ctx)
    y = paint_cargo_row(console, hud_x, y, used=cargo_used, max_cargo=max_cargo)
    return paint_status_slot(console, hud_x, y, _status_segments(ctx))


def _render_city_terminals(
    console, hud_x, y, *, has_armory_terminal, has_mech_terminal,
    has_trade_terminal, has_kiosk=False,
) -> int:
    """Paint the terminal indicator rows; return the next row."""
    if has_armory_terminal:
        console.print(x=hud_x, y=y, string="A  Armory", fg=COLOR_LABEL)
        y += 1
    if has_mech_terminal:
        console.print(x=hud_x, y=y, string="%  Mechanic", fg=COLOR_LABEL)
        y += 1
    if has_trade_terminal:
        console.print(x=hud_x, y=y, string="=  Trade", fg=COLOR_LABEL)
        y += 1
    if has_kiosk:
        console.print(x=hud_x, y=y, string="$  Terminus Tech", fg=COLOR_LABEL)
        y += 1
    return y


def _render_city_help_lines(console, hud_x, y, mode) -> int:
    """Paint the movement key hints; return the next row."""
    _help_lines = [
        ("Q", "Quest Log"), ("C", "Character"), ("F", "Factions"), (CONSOLE_LOG_KEY, CONSOLE_LOG_LABEL),
        ("X", "Swap Sets"), ("?", "Guide"), ("numpad", "Move"),
        ("ESC", "Pause"),
    ]
    if mode == "dungeon":
        _help_lines[0:0] = [
            ("P", "Pickup"), ("O", "Explore"),
            ("G", "Go To"), ("R", "Reload"), ("V", "Status"),
        ]
    elif mode == "city":
        # Streets are hostile-capable since doc 53 — reload is live here too.
        _help_lines[0:0] = [("R", "Reload"), ("V", "Status")]
    return _render_help_lines(console, hud_x, y, _help_lines)


def _print_ground_weapon_rows(console, hud_x: int, y: int, equipped) -> int:
    """One row per active-set weapon: name + magazine cur/cap (doc 52.3)."""
    from .data.quality import effective_weapon_spec, quality_color
    from .ground_equipment import display_name
    from .ground_weapon_ammo import magazine_indicator

    for _inst in equipped:
        try:
            ws = effective_weapon_spec(_inst.weapon_id, _inst.quality)
        except KeyError:
            continue
        console.print(
            x=hud_x, y=y,
            string=(
                f"{display_name('weapon', _inst.weapon_id, _inst.quality)}"
                f"{magazine_indicator(ws, _inst)}"
            )[:HUD_TEXT_MAX],
            fg=quality_color(_inst.quality) or COLOR_VALUE_WHITE,
        )
        y += 1
    return y


def _render_ground_weapons_block(console, hud_x: int, y: int, ctx) -> int:
    """Paint the ground weapons block (doc 52.3): active-set rows with
    magazine state, the dim holster names, and the shared caliber lines.

    Rendered on every ground screen — dungeon and city both (cities
    joined when doc 53 made streets hostile-capable).

    No volley checkboxes, DMG/HIT, or RNG rows — there is no target
    outside combat. The fists floor stays silent (doc 51 SETTLED 2):
    the block renders only when some weapon is actually carried.
    """
    _equipped = list(getattr(ctx, "equipped_ground_weapons", None) or [])
    if not _equipped and not (getattr(ctx, "holstered_ground_weapons", None) or []):
        return y
    console.print(x=hud_x, y=y, string="WEAPONS", fg=COLOR_HUD_TITLE)
    y = _print_ground_weapon_rows(console, hud_x, y + 1, _equipped)
    _holster = ground_holster_names(ctx)
    if _holster:
        console.print(
            x=hud_x, y=y, string=f"HOLSTER  {_holster}"[:HUD_TEXT_MAX],
            fg=COLOR_VALUE_DIM,
        )
        y += 1
    for line in bandolier_hud_lines(ctx):
        console.print(x=hud_x, y=y, string=line[:HUD_TEXT_MAX], fg=COLOR_VALUE_DIM)
        y += 1
    return y


def _status_segments(ctx):
    """The player's status segments (doc 103 q7) for the core's FIXED
    slot (doc 104 item 13) — computed here (lazy combat import, the
    bandolier precedent) so hud_core's painter stays combat-free:
    segments in, ink out. Carried rows read on city streets too
    (frozen outside status time, honestly)."""
    from .combat._statuses import hud_segments

    return hud_segments(getattr(ctx, "active_statuses", None) or {})


def _render_city_hud(console, hud_x, ctx, *, ship_catalog, location, date_str, mode, hud_view_height, xp_line, xp_fg, has_trade_terminal, has_mech_terminal, has_armory_terminal, has_kiosk=False) -> None:
    """Paint the city/dungeon-mode HUD body below the title, doc 104's
    reserved regions: A = the location/date band, B = the shared core
    via hud_core, C = the WEAPONS anchor, D = the terminals + help
    band. The band rows can change freely — the core's rows and y
    never move."""
    _render_city_identity(
        console, hud_x, GROUND_BAND_Y,
        location=location, date_str=date_str,
    )
    _render_divider(console, hud_x, GROUND_CORE_Y - 1)
    _render_city_core(console, hud_x, ctx, ship_catalog=ship_catalog)
    y = _render_ground_weapons_block(console, hud_x, GROUND_WEAPONS_Y, ctx)
    _render_divider(console, hud_x, y)
    y = _render_city_terminals(
        console, hud_x, y + 1,
        has_armory_terminal=has_armory_terminal,
        has_mech_terminal=has_mech_terminal,
        has_trade_terminal=has_trade_terminal,
        has_kiosk=has_kiosk,
    )
    _render_city_help_lines(console, hud_x, y, mode)
    paint_xp_footer(console, hud_x, hud_view_height, xp_line=xp_line, xp_fg=xp_fg)


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
    has_kiosk: bool = False,             # city mode: show $ terminal hint
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
            has_kiosk=has_kiosk,
        )


# ---------------------------------------------------------------------------
# Shared combat-format helpers (city, space, and ground combat HUDs)
# ---------------------------------------------------------------------------

# HUD_TEXT_MAX, _bar_str, and the bar glyphs live in hud_core (the
# unified core's primitives) and are re-exported above for the combat
# importers and the space rows.


def ap_pool_str(available: int, carry_twentieths: int = 0) -> str:
    """Format a combat AP pool that may carry a fractional twentieths credit.

    ``available`` is the spendable integer AP this round and
    ``carry_twentieths`` (0-19) is the banked fraction of the pool
    that rolls into the next round. Returns ``"4"``, ``"4.25"`` or
    ``"4.5"`` so the HUD reads ``AP: 3/4.5`` — the fraction is the
    small indicator that the pilot's real speed exceeds the spendable
    integer.
    """
    if not carry_twentieths:
        return str(available)
    # carry/20 expressed in hundredths (carry * 5), trailing zero
    # trimmed so 5 -> .25, 10 -> .5, 15 -> .75, 1 -> .05.
    hundredths = carry_twentieths * 5
    frac = f"{hundredths:02d}".rstrip("0") or "0"
    return f"{available}.{frac}"


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
    them. The bar shrinks so the full suffix fits within
    ``HUD_TEXT_MAX`` (the panel's real half-width glyph capacity).
    """
    _base = f"LV {player_level:>2} ["
    if points > 0:
        # Shrink the bar so the full "+N PTS" suffix always fits within
        # HUD_TEXT_MAX, even for 2-3 digit point counts (5/level adds up).
        _suffix = f" +{points} PTS"
        _bar_width = max(1, HUD_TEXT_MAX - len(_base) - len("]") - len(_suffix))
        _bar = _render_xp_bar(xp_into, xp_needed, width=_bar_width)
        return f"{_base}{_bar}]{_suffix}", COLOR_HUD_TITLE
    _bar_width = max(1, HUD_TEXT_MAX - len(_base) - len("]"))
    _bar = _render_xp_bar(xp_into, xp_needed, width=_bar_width)
    return f"{_base}{_bar}]", COLOR_VALUE_DIM


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


def _render_action_pairs(console, hud_x, y, actions, fg) -> int:
    """Paint combat key-hint pairs, two per row; return the next row.

    Shared by space and ground combat so the ACTIONS block layout stays
    consistent and uses the panel's full width.
    """
    for i in range(0, len(actions), 2):
        _k1, _d1 = actions[i]
        left = f"{_k1:<6} {_d1:<12}"
        if i + 1 < len(actions):
            _k2, _d2 = actions[i + 1]
            console.print(x=hud_x, y=y, string=f"{left}{_k2} {_d2}"[:HUD_TEXT_MAX], fg=fg)
        else:
            console.print(x=hud_x, y=y, string=left[:HUD_TEXT_MAX], fg=fg)
        y += 1
    return y


