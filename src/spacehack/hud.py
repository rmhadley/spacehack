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
    |                 | SCOUT    |
    |       MAP       |          |
    |     REGION      | Fuel 90  |
    |                 | Hull  0% |
    |                 | Cargo 0  |
    |                 | Wpn 0/2  |
    |                 | Mod 0/1  |
    |                 | -------- |
    |                 | G - Go To|
    |                 | P - Loot  |
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

import tcod.console

from .engine import HUD_WIDTH
from .ui import COLOR_DIVIDER, COLOR_VALUE_DIM, COLOR_VALUE_WHITE  # shared palette (single source)

if TYPE_CHECKING:
    from .game_context import GameContext


# Vivid HUD palette: gold title, bright near-white values, blue-tinted
# labels (replaces the old flat greys), saturated green/red for HP
# depending on ratio, and a cool dark-slate divider so the headline
# fields pop.  The white/dim/divider colors are imported from ui.py —
# the single source — so a global brightness pass never drifts.
COLOR_HUD_TITLE: tuple[int, int, int] = (255, 195, 80)            # vivid orange-gold
COLOR_LABEL: tuple[int, int, int] = (185, 205, 235)               # ice-blue (brightened for dark-bg pop)
COLOR_HP_GOOD: tuple[int, int, int] = (100, 235, 115)             # bright grass-green
COLOR_HP_LOW: tuple[int, int, int] = (255, 95, 95)                # bright crimson
COLOR_EVADE: tuple[int, int, int] = (120, 220, 140)               # soft green positive-buff accent

# Space-mode HUD palette — cooler, more technical feel.
COLOR_SHIP_NAME: tuple[int, int, int] = (100, 220, 255)           # bright cyan for ship name
COLOR_SHIP_VALUE: tuple[int, int, int] = (255, 255, 255)          # white stat values
COLOR_SHIP_LABEL: tuple[int, int, int] = (170, 195, 230)          # ice-blue labels (brightened; slightly dimmer than COLOR_LABEL)
COLOR_FUEL_OK: tuple[int, int, int] = (100, 235, 115)            # green when fuel is adequate
COLOR_FUEL_LOW: tuple[int, int, int] = (255, 180, 60)            # amber when fuel is low (< jump cost)
COLOR_HELP_DESC: tuple[int, int, int] = (205, 205, 210)          # silver for key descriptions


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


def _render_divider(console: tcod.console.Console, hud_x: int, y: int) -> None:
    """Print a full-width divider line at ``(hud_x, y)``.

    Pure print — caller owns y advancement.
    """
    console.print(x=hud_x, y=y, string="-" * HUD_WIDTH, fg=COLOR_DIVIDER)


def _render_mission_line(
    console: tcod.console.Console, hud_x: int, y: int, title: str,
) -> None:
    """Print the active mission title at ``(hud_x, y)`` with "M: " prefix.

    Truncates to fit HUD_WIDTH. Pure print — caller owns y advancement.
    """
    room = max(0, HUD_WIDTH - len("M: ") - 1)
    console.print(x=hud_x, y=y, string=f"M: {title[:room]}", fg=COLOR_HUD_TITLE)


def _render_skill_line(
    console: tcod.console.Console, hud_x: int, y: int, stats: HudStats,
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
    console: tcod.console.Console, hud_x: int, y: int, ground_stats,
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


def _render_help_lines(
    console: tcod.console.Console,
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


def render_hud(
    console: tcod.console.Console,
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
    """Paint the right-side HUD into the top ``hud_view_height`` rows.

    ``hud_view_height`` should be ``SCREEN_HEIGHT - MSG_LOG_HEIGHT`` so
    we never paint into the message-log rows at the bottom.

    ``location`` is the current location name — the planet name in
    city mode (e.g. "Earth", "Mars") or the solar system name in
    space mode (e.g. "Sol", "Alpha Centauri"). Shown below the
    title in both modes so the player always knows where they are.

    **Pull-from-ctx contract.** Everything except ``screen_width``,
    ``hud_view_height``, ``location``, and the terminal flags is
    extracted from ``ctx`` internally::

        character      ->  ctx.character_info
        stats          ->  ctx.stats
        owned_ship     ->  ctx.player_owned_ship
        ship_catalog   ->  resolved from ctx.player_owned_ship
        date_str       ->  format_date(ctx)
        player_xp      ->  ctx.player_xp
        player_level   ->  ctx.player_level
        ground_stats   ->  ctx.ground_stats

    This means adding a new field to GameContext that the HUD should
    display never requires updating call sites.
    """
    # ---- Extract all state from ctx ----
    character = ctx.character_info
    stats = ctx.stats
    owned_ship = ctx.player_owned_ship
    player_xp = ctx.player_xp
    player_level = ctx.player_level
    ground_stats = ctx.ground_stats
    ship_catalog = None
    if owned_ship is not None:
        from . import ship as _ship_cat_mod
        try:
            ship_catalog = _ship_cat_mod.find_ship(owned_ship.ship_id)
        except KeyError:
            pass
    from .time import format_date as _format_date
    date_str = _format_date(ctx)

    hud_x = screen_width - HUD_WIDTH
    # Compute XP progress for both city and space modes.
    from .xp import xp_for_level as _xp_for_level, _xp_to_next as _xp_to_next
    _xp_total_for_level = _xp_for_level(player_level) if player_level > 1 else 0
    _xp_into_level = max(0, player_xp - _xp_total_for_level)
    _xp_needed = _xp_to_next(player_level)
    _xp_line, _xp_fg = _xp_hud_line(
        player_level, _xp_into_level, _xp_needed,
        getattr(ctx, 'player_skill_points', 0),
    )

    # Title — always at row 0
    console.print(
        x=hud_x,
        y=0,
        string="Spacehack",
        fg=COLOR_HUD_TITLE,
    )

    if mode == "space" and owned_ship is not None and ship_catalog is not None:
        # ---- Space mode: ship stats + keybinding help ----
        ship_name = _ship_cat_mod.ship_display_name(owned_ship)
        fuel = getattr(owned_ship, 'fuel', 0)
        max_fuel = getattr(ship_catalog, 'max_fuel', 1)
        hull_damage = getattr(owned_ship, 'hull_damage_pct', 0)
        hull_pct = 100 - hull_damage
        cargo_used, max_cargo = _cargo_used_max(owned_ship, ship_catalog)
        weapons_n = len(getattr(owned_ship, 'weapons', ()) or ())
        weapon_slots = getattr(ship_catalog, 'weapon_slots', 0)
        modules_n = len(getattr(owned_ship, 'modules', ()) or ())
        module_slots = getattr(ship_catalog, 'module_slots', 0)

        y = 2
        # Ship name (bright cyan)
        console.print(x=hud_x, y=y, string=ship_name.upper(), fg=COLOR_SHIP_NAME)
        # Location (silver, below ship name)
        y += 1
        if location:
            console.print(x=hud_x, y=y, string=location.upper(), fg=COLOR_VALUE_DIM)
        # Date (silver, below location)
        y += 1
        if date_str:
            console.print(x=hud_x, y=y, string=date_str, fg=COLOR_VALUE_DIM)
        y += 1

        # Fuel
        console.print(x=hud_x, y=y, string="Fuel", fg=COLOR_SHIP_LABEL)
        fuel_str = f"{fuel}/{max_fuel}"
        fuel_color = COLOR_FUEL_OK if fuel >= 10 else COLOR_FUEL_LOW
        console.print(x=hud_x + 5, y=y, string=fuel_str, fg=fuel_color)
        y += 1

        # Hull
        console.print(x=hud_x, y=y, string="Hull", fg=COLOR_SHIP_LABEL)
        hull_color = COLOR_HP_GOOD if hull_pct >= 50 else COLOR_HP_LOW
        console.print(x=hud_x + 5, y=y, string=f"{hull_pct}%", fg=hull_color)
        y += 1

        # Cargo
        console.print(x=hud_x, y=y, string="Cargo", fg=COLOR_SHIP_LABEL)
        console.print(x=hud_x + 6, y=y, string=f"{cargo_used}/{max_cargo}", fg=COLOR_SHIP_VALUE)
        y += 1

        # Weapons
        console.print(x=hud_x, y=y, string="Wpn", fg=COLOR_SHIP_LABEL)
        console.print(x=hud_x + 5, y=y, string=f"{weapons_n}/{weapon_slots}", fg=COLOR_SHIP_VALUE)
        y += 1

        # Modules
        console.print(x=hud_x, y=y, string="Mod", fg=COLOR_SHIP_LABEL)
        console.print(x=hud_x + 5, y=y, string=f"{modules_n}/{module_slots}", fg=COLOR_SHIP_VALUE)
        y += 1

        # Speed (base + module bonuses)
        from . import ship as _ship_mod
        _eff_spd = _ship_mod.effective_speed(ship_catalog, owned_ship)
        console.print(x=hud_x, y=y, string="Spd", fg=COLOR_SHIP_LABEL)
        console.print(x=hud_x + 5, y=y, string=str(_eff_spd), fg=COLOR_SHIP_VALUE)
        y += 2

        # Pilot skills (compact one-liner)
        y += 1
        _render_skill_line(console, hud_x, y, stats)
        y += 1
        # Ground stats (second line)
        if ground_stats is not None:
            _render_ground_stat_line(console, hud_x, y, ground_stats)
            y += 1

        # Divider
        y += 1
        _render_divider(console, hud_x, y)
        y += 2

        # Blank line before keybinding help.
        y += 1

        # Keybinding help
        y = _render_help_lines(console, hud_x, y, [
            ("G", "Go To"),
            ("P", "Loot"),
            ("M", "Map"),
            ("I", "Cargo"),
            ("T", "Comms"),
            ("C", "Character"),
            ("F", "Factions"),
            ("?", "Guide"),
            ("Arrows", "Move"),
            ("h/j/k/l", "Move"),
            ("numpad", "Move"),
        ])

        # XP progress bar — between key hints and footer.
        console.print(x=hud_x, y=hud_view_height - 3, string=_xp_line, fg=_xp_fg)

        # Bottom hint.
        y = hud_view_height - 2
        console.print(x=hud_x, y=y, string="bump to interact", fg=COLOR_VALUE_DIM)
        console.print(x=hud_x, y=y + 1, string="ESC to quit", fg=COLOR_VALUE_DIM)

    else:
        # ---- City / dungeon mode: character stats ----
        # Species + class (two-line block)
        species_name = character.get("species_name", "")
        class_name = character.get("class_name", "")
        y = 2
        if species_name:
            console.print(x=hud_x, y=y, string=species_name.title(), fg=COLOR_VALUE_WHITE)
        y += 1
        if class_name:
            console.print(x=hud_x, y=y, string=class_name.title(), fg=COLOR_VALUE_WHITE)
        # Location (silver, below class)
        y += 1
        if location:
            console.print(x=hud_x, y=y, string=location, fg=COLOR_VALUE_DIM)
        # Date (silver, below location)
        y += 1
        if date_str:
            console.print(x=hud_x, y=y, string=date_str, fg=COLOR_VALUE_DIM)
        y += 1

        # Divider — separates identity from stats
        y += 1
        _render_divider(console, hud_x, y)

        # HP (color depends on ratio) — ground HP is the LIVE value in
        # city/dungeon: ground combat's sync_state writes damage back to
        # ctx.ground_hp / ctx.ground_max_hp, while HudStats.hp is the
        # character-creation snapshot and never updates. GameContext
        # always defines these (defaults 23/23), so read them directly.
        y += 2
        console.print(x=hud_x, y=y, string="HP", fg=COLOR_LABEL)
        hp = max(0, ctx.ground_hp)
        max_hp = max(1, ctx.ground_max_hp)
        hp_str = f"{hp}/{max_hp}"
        hp_fg = COLOR_HP_GOOD if hp * 2 >= max_hp else COLOR_HP_LOW
        console.print(x=hud_x + 3, y=y, string=hp_str, fg=hp_fg)

        # Cargo (used/max — handy while shopping at trade terminals)
        y += 1
        console.print(x=hud_x, y=y, string="Cargo", fg=COLOR_LABEL)
        cargo_used, max_cargo = _cargo_used_max(owned_ship, ship_catalog)
        console.print(x=hud_x + 6, y=y, string=f"{cargo_used}/{max_cargo}", fg=COLOR_VALUE_WHITE)

        # Credits
        y += 1
        console.print(x=hud_x, y=y, string="$", fg=COLOR_LABEL)
        console.print(x=hud_x + 2, y=y, string=str(stats.credits), fg=COLOR_VALUE_WHITE)

        # Blank line — separates the headline stats from the skills block.
        y += 1

        # Pilot skills (compact one-liner)
        y += 1
        _render_skill_line(console, hud_x, y, stats)
        y += 1
        # Ground stats (second line)
        if ground_stats is not None:
            _render_ground_stat_line(console, hud_x, y, ground_stats)
            y += 1

        # Divider — separates stats from terminals
        y += 1
        _render_divider(console, hud_x, y)

        # Terminal indicators (each on its own line)
        y += 1
        if has_armory_terminal:
            console.print(x=hud_x, y=y, string="A  Armory", fg=COLOR_LABEL)
            y += 1
        if has_mech_terminal:
            console.print(x=hud_x, y=y, string="%  Mechanic", fg=COLOR_LABEL)
            y += 1
        if has_trade_terminal:
            console.print(x=hud_x, y=y, string="=  Trade", fg=COLOR_LABEL)

        # Divider — separates terminals from keybinding help
        y += 1
        _render_divider(console, hud_x, y)

        # Movement key hints (below terminals, above footer)
        y += 2
        _help_lines = [
            ("Q", "Quest Log"),
            ("C", "Character"),
            ("F", "Factions"),
            ("?", "Guide"),
            ("Arrows", "Move"),
            ("h/j/k/l", "Move"),
            ("numpad", "Move"),
        ]
        if mode == "dungeon":
            _help_lines.insert(0, ("P", "Loot"))
        y = _render_help_lines(console, hud_x, y, _help_lines)

        # XP progress bar — between key hints and footer.
        console.print(x=hud_x, y=hud_view_height - 3, string=_xp_line, fg=_xp_fg)

        # Footer hint at the bottom of the HUD
        y = hud_view_height - 2
        console.print(x=hud_x, y=y, string="bump to interact", fg=COLOR_VALUE_DIM)
        console.print(x=hud_x, y=y + 1, string="ESC to quit", fg=COLOR_VALUE_DIM)


# ---------------------------------------------------------------------------
# Combat HUD
# ---------------------------------------------------------------------------

# Combat HUD palette
COLOR_COMBAT_TITLE: tuple[int, int, int] = (255, 80, 80)           # red combat title
COLOR_HULL_BAR_GREEN: tuple[int, int, int] = (100, 235, 115)       # bright green
COLOR_HULL_BAR_YELLOW: tuple[int, int, int] = (255, 220, 80)       # amber
COLOR_HULL_BAR_RED: tuple[int, int, int] = (255, 80, 80)           # red
COLOR_SHIELD_BAR: tuple[int, int, int] = (100, 200, 255)           # cyan
COLOR_AP: tuple[int, int, int] = (255, 220, 80)                    # gold
COLOR_POWER: tuple[int, int, int] = (150, 200, 255)                # blue-white
COLOR_COMBAT_WEAPON: tuple[int, int, int] = (255, 200, 100)        # gold
COLOR_COMBAT_WEAPON_DIM: tuple[int, int, int] = (120, 100, 60)     # dimmed
COLOR_COMBAT_LOG: tuple[int, int, int] = (200, 200, 200)           # silver
COLOR_COMBAT_ACTION: tuple[int, int, int] = (180, 220, 255)        # light blue
COLOR_COMBAT_MODE: tuple[int, int, int] = (255, 255, 150)          # yellow for mode indicator


_BAR_CHAR_FULL: str = "#"   # full marker
_BAR_CHAR_EMPTY: str = "."   # empty marker


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


def render_combat_hud(
    console: tcod.console.Console,
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

    Layout (right panel, top to bottom):
      COMBAT title (red)
      Turn / mode line
      ---
      PLAYER block
      Hull bar + %
      Shield bar + %
      AP / Power
      ---
      ENEMY block (target)
      Hull bar + %
      Shield bar + %
      Distance
      ---
      WEAPONS list (numbered 1-N)
      ---
      ACTIONS
      [w] Wait
      [ESC] Flee
      ---
      Combat log (1-2 lines)
    """
    hud_x = screen_width - HUD_WIDTH
    y = 0

    # Title
    console.print(x=hud_x, y=y, string="> COMBAT <", fg=COLOR_COMBAT_TITLE)
    y += 1

    # Mode indicator
    mode_str = f"[{player_mode}]"
    console.print(x=hud_x, y=y, string=mode_str, fg=COLOR_COMBAT_MODE)
    y += 2

    # Divider
    console.print(x=hud_x, y=y, string="-" * HUD_WIDTH, fg=COLOR_DIVIDER)
    y += 1

    # --- PLAYER block ---
    console.print(x=hud_x, y=y, string="PLAYER", fg=COLOR_LABEL)
    y += 1
    phull = player_state.get("hull", 100)
    pmax_hull = player_state.get("max_hull", 100)
    pshields = player_state.get("shields", 0)
    pmax_shields = player_state.get("max_shields", 0)
    pap = player_state.get("ap_remaining", 0)
    pap_total = player_state.get("ap_total", 3)
    ppow = player_state.get("power_pool", 0)
    ppow_max = player_state.get("max_power", 10)

    hull_pct = phull / max(pmax_hull, 1)
    hull_color = _hull_bar_color(hull_pct)
    hull_pct_display = int(hull_pct * 100)

    # Shield bar + regen rate (above hull, when shields exist)
    if pmax_shields > 0:
        shields_pct = pshields / max(pmax_shields, 1)
        _bar = _bar_str(pshields, pmax_shields)
        shield_line = f"Shd  {_bar} {int(shields_pct * 100)}%"
        console.print(x=hud_x, y=y, string=shield_line, fg=COLOR_SHIELD_BAR)
        # Regen rate fill: N leftmost cells get a white bg (0-10 cells),
        # regardless of whether the shield is currently full (#) or empty (.).
        _regen_rate = player_state.get("shield_regen_rate", 0)
        if _regen_rate > 0:
            _fill = min(_regen_rate, len(_bar))
            for _i in range(_fill):
                console.print(
                    x=hud_x + 5 + _i, y=y,
                    string=_bar[_i],
                    fg=COLOR_SHIELD_BAR,
                    bg=(255, 255, 255),
                )
        y += 1

    # Hull bar
    hull_line = f"Hull {_bar_str(phull, pmax_hull)} {hull_pct_display}%"
    console.print(x=hud_x, y=y, string=hull_line, fg=hull_color)
    y += 1

    ap_line = f"AP: {pap}/{pap_total}"
    console.print(x=hud_x, y=y, string=ap_line, fg=COLOR_AP if pap > 0 else COLOR_HULL_BAR_RED)
    y += 1
    # Player's current evade bonus: increases by +5% per cell moved
    # (capped) plus a half-rate contribution from pilot piloting.
    # Color signals when movement has actually paid off — gray when 0
    # so the player reads "no dodge stacked yet", positive green
    # accent when any bonus is in play.
    if evade_bonus is not None:
        # No colon so the row aligns with the bar-style Hull/Shd
        # rows above it ("Hull ...", "Shd  ..."). Color flips
        # positive-on-positive so the player sees movement paying
        # off — the +X% value climbs with each move so the impact
        # of spending AP on repositioning is visible at a glance.
        evade_color = COLOR_EVADE if evade_bonus > 0 else COLOR_VALUE_DIM
        evade_line = f"Evade +{evade_bonus}%"
        console.print(x=hud_x, y=y, string=evade_line, fg=evade_color)
        y += 1
    ppow_gen = player_state.get("power_gen", 0)
    pow_line = f"Pow: {ppow}/{ppow_max} (+{ppow_gen})"
    console.print(x=hud_x, y=y, string=pow_line, fg=COLOR_POWER)
    y += 2

    # --- ENEMIES block ---
    if enemies:
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
            marker = ">" if is_target else " "
            # Short name (trim to 9 chars at most)
            _name = _e.name[:9] if len(_e.name) > 9 else _e.name
            _dist_str = ""
            if ppos and hasattr(_e, 'pos'):
                import math as _m
                _dist_str = f"{int(_m.hypot(ppos.x - _e.pos.x, ppos.y - _e.pos.y))}"
            # Name line with distance
            _name_str = f"{marker}{_name}"
            _name_fg = COLOR_COMBAT_TITLE if is_target else COLOR_VALUE_DIM
            # Render name + distance with separate colors for the distance
            # number, matching the targeting-line range colors.
            console.print(x=hud_x, y=y, string=_name_str, fg=_name_fg)
            if _dist_str and range_weapon_id is not None:
                from .data.weapons import find_weapon as _fw
                try:
                    _ws = _fw(range_weapon_id)
                    _dist_val = int(_dist_str)
                    _half = _ws.max_range // 2
                    if _dist_val <= _half:
                        _dc = (100, 235, 115)  # green
                    elif _dist_val <= _ws.max_range:
                        _dc = (255, 220, 80)   # yellow
                    elif _ws.min_range > 0 and _dist_val <= _ws.min_range:
                        _dc = (255, 160, 60)   # orange
                    else:
                        _dc = (255, 80, 80)    # red
                    console.print(
                        x=hud_x + len(_name_str) + 2, y=y,
                        string=_dist_str, fg=_dc,
                    )
                except KeyError:
                    pass
            elif _dist_str:
                # No range info available — print distance in default color
                console.print(
                    x=hud_x + len(_name_str) + 2, y=y,
                    string=_dist_str, fg=COLOR_VALUE_DIM,
                )
            y += 1
            # Shield bar (above hull when shields exist)
            if _e.max_shields > 0:
                _e_shd_pct = _e.shields / max(_e.max_shields, 1)
                _shd_bar = _bar_str(_e.shields, _e.max_shields, width=5)
                _shd_line = f"  Shd {_shd_bar} {int(_e_shd_pct * 100)}%"
                console.print(x=hud_x, y=y, string=_shd_line[:HUD_WIDTH], fg=COLOR_SHIELD_BAR)
                y += 1
            # Hull bar (below shields)
            _e_hull_pct = _e.hull / max(_e.max_hull, 1)
            _e_pct_display = int(_e_hull_pct * 100)
            _bar = _bar_str(_e.hull, _e.max_hull, width=5)
            _hull_line = f"  Hul {_bar} {_e_pct_display}%"
            console.print(x=hud_x, y=y, string=_hull_line[:HUD_WIDTH], fg=_hull_bar_color(_e_hull_pct))
            y += 1
        y += 1

    # --- WEAPONS list ---
    if weapon_list:
        console.print(x=hud_x, y=y, string="WEAPONS", fg=COLOR_DIVIDER)
        y += 1
        for i, wid in enumerate(weapon_list):
            from .data.weapons import find_weapon as _fw
            try:
                ws = _fw(wid)
            except KeyError:
                continue
            # Check if can fire — ammo is keyed by weapon SLOT index so
            # two launchers of the same type show independent magazines.
            wammo = player_state.get("weapon_ammo", {}).get(i, 0)
            ap_req = ws.ap_cost
            pow_req = ws.power_cost if ws.slot_type in ("energy", "plasma") else 0
            has_ap = pap >= ap_req
            has_pow = ppow >= pow_req
            has_ammo = wammo > 0 or ws.ammo_capacity <= 0
            can_fire = has_ap and has_pow and has_ammo

            fg_w = COLOR_COMBAT_WEAPON if can_fire else COLOR_COMBAT_WEAPON_DIM
            is_active = active_weapons[i] if active_weapons else True
            sel_mark = "[x]" if is_active else "[ ]"
            name_str = f"{sel_mark}[{i+1}] {ws.name}"
            fg_wpn = COLOR_COMBAT_WEAPON if is_active else COLOR_COMBAT_WEAPON_DIM
            console.print(x=hud_x, y=y, string=name_str[:HUD_WIDTH-1], fg=fg_wpn)
            y += 1

            # Show effective hit chance (includes gunnery + distance + target
            # dodge) for every weapon against the current target. Falls back
            # to base weapon accuracy when no target is selected.
            _w_hc = hit_chances.get(wid) if hit_chances else None
            if _w_hc is not None:
                stats_line = f"     DMG {ws.damage} HIT {_w_hc}%"
            else:
                stats_line = f"     DMG {ws.damage} ACC {ws.accuracy}%"
            console.print(x=hud_x, y=y, string=stats_line[:HUD_WIDTH-1], fg=COLOR_VALUE_DIM)
            y += 1

            if ws.slot_type in ("energy", "plasma"):
                cost_line = f"     POW {ws.power_cost} AP {ws.ap_cost}"
            else:
                ammo_str = f"{wammo}/{ws.ammo_capacity}" if ws.ammo_capacity > 0 else "∞"
                cost_line = f"     AMMO {ammo_str} AP {ws.ap_cost}"
            console.print(x=hud_x, y=y, string=cost_line[:HUD_WIDTH-1], fg=COLOR_VALUE_DIM)
            y += 1

    y += 1

    # --- ACTIONS ---
    console.print(x=hud_x, y=y, string="ACTIONS", fg=COLOR_DIVIDER)
    y += 1
    actions = [
        ("[Tab]", "Target"),
        ("[m]", "Move"),
        ("[f]", "Fire"),
        ("[s]", "Shields"),
        ("[w]", "Wait"),
    ]
    # Only advertise the digit-swap affordance when there is
    # actually something to swap between; a single-weapon player
    # has nothing to cycle through. The label embeds the real
    # weapon count so the player doesn't expect digit 4..9 to
    # work when they only have 3 weapons mounted (the previous
    # hard-coded [1-N] lied about the upper bound). Sits
    # between [f] Fire and [w] Wait so weapon actions group
    # visually.
    if len(weapon_list) > 1:
        actions.insert(3, (f"[1-{len(weapon_list)}]", "Toggle Wpn"))
    for key, desc in actions:
        line = f"{key} {desc}"
        console.print(x=hud_x, y=y, string=line[:HUD_WIDTH-1], fg=COLOR_COMBAT_ACTION)
        y += 1


