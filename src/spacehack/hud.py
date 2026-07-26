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
    |                 | M - Map  |
    |                 | ESC Quit |
    +-----------------+----------+

The HUD paints only into the top portion of the screen so the message
log (drawn separately) owns the bottom rows.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import tcod.console

from .engine import HUD_WIDTH
from .data.weapons import find_weapon as _find_weapon
import math as _math


# Vivid HUD palette: gold title, bright near-white values, blue-tinted
# labels (replaces the old flat greys), saturated green/red for HP
# depending on ratio, and a cool dark-slate divider so the headline
# fields pop.
COLOR_HUD_TITLE: tuple[int, int, int] = (255, 195, 80)            # vivid orange-gold
COLOR_VALUE_WHITE: tuple[int, int, int] = (255, 255, 255)         # pure white (brightest)
COLOR_VALUE_DIM: tuple[int, int, int] = (150, 150, 150)           # neutral silver (de-saturated so it doesn't echo SIDEWALK)
COLOR_LABEL: tuple[int, int, int] = (155, 180, 215)               # muted ice-blue
COLOR_HP_GOOD: tuple[int, int, int] = (100, 235, 115)             # bright grass-green
COLOR_HP_LOW: tuple[int, int, int] = (255, 95, 95)                # bright crimson
COLOR_EVADE: tuple[int, int, int] = (120, 220, 140)               # soft green positive-buff accent
COLOR_DIVIDER: tuple[int, int, int] = (90, 90, 90)                # flat neutral grey (stops the divider from echoing ROAD hue)

# Space-mode HUD palette — cooler, more technical feel.
COLOR_SHIP_NAME: tuple[int, int, int] = (100, 220, 255)           # bright cyan for ship name
COLOR_SHIP_VALUE: tuple[int, int, int] = (255, 255, 255)          # white stat values
COLOR_SHIP_LABEL: tuple[int, int, int] = (140, 180, 215)          # muted ice-blue labels (slightly dimmer than COLOR_LABEL)
COLOR_FUEL_OK: tuple[int, int, int] = (100, 235, 115)            # green when fuel is adequate
COLOR_FUEL_LOW: tuple[int, int, int] = (255, 180, 60)            # amber when fuel is low (< jump cost)
COLOR_HELP_KEY: tuple[int, int, int] = (255, 200, 80)            # gold for key names in help
COLOR_HELP_DESC: tuple[int, int, int] = (180, 180, 180)          # silver for key descriptions


@dataclass
class HudStats:
    """The stats shown in the HUD right now."""
    hp: int
    max_hp: int
    gold: int
    gunnery: int = 0
    piloting: int = 0
    engineering: int = 0


def render_hud(
    console: tcod.console.Console,
    *,
    screen_width: int,
    hud_view_height: int,
    character: dict,
    stats: HudStats,
    active_mission: str | None = None,
    location: str | None = None,
    owned_ship: Any = None,              # ship_module.OwnedShip when in space
    ship_catalog: Any = None,            # ship_module.Ship catalog entry
) -> None:
    """Paint the right-side HUD into the top ``hud_view_height`` rows.

    ``hud_view_height`` should be ``SCREEN_HEIGHT - MSG_LOG_HEIGHT`` so
    we never paint into the message-log rows at the bottom.

    ``location`` is the current location name — the planet name in
    city mode (e.g. "Earth", "Mars") or the solar system name in
    space mode (e.g. "Sol", "Alpha Centauri"). Shown below the
    title in both modes so the player always knows where they are.

    When ``owned_ship`` and ``ship_catalog`` are provided (space mode),
    the HUD shows ship stats (fuel, hull, cargo, weapons, modules)
    and a keybinding-help panel instead of character species/class/HP.

    ``active_mission`` is the pre-resolved mission title (without
    the "MISSION: " prefix) drawn between the title and the divider,
    or ``None`` if the player has no active mission. The caller
    (``_run_game`` in :mod:`spacehack.__main__`) looks the title up
    once per frame so the HUD module doesn't have to know the mission
    catalog exists.
    """
    hud_x = screen_width - HUD_WIDTH

    # Title — always at row 0
    console.print(
        x=hud_x,
        y=0,
        string="Spacehack",
        fg=COLOR_HUD_TITLE,
    )

    if owned_ship is not None and ship_catalog is not None:
        # ---- Space mode: ship stats + keybinding help ----
        ship_name = getattr(ship_catalog, 'name', 'Ship')
        fuel = getattr(owned_ship, 'fuel', 0)
        max_fuel = getattr(ship_catalog, 'max_fuel', 1)
        hull_damage = getattr(owned_ship, 'hull_damage_pct', 0)
        hull_pct = 100 - hull_damage
        cargo_used = getattr(owned_ship, 'cargo_used', 0)
        max_cargo = getattr(ship_catalog, 'max_cargo', 0)
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

        # Pilot skills (compact one-liner)
        y += 1
        skill_line = f"G:{stats.gunnery} P:{stats.piloting} E:{stats.engineering}"
        console.print(x=hud_x, y=y, string=skill_line[:HUD_WIDTH], fg=COLOR_SHIP_LABEL)

        # Active mission (inline, no extra divider)
        if active_mission:
            y += 1
            mission_room = max(0, HUD_WIDTH - len("M: ") - 1)
            mission_line = f"M: {active_mission[:mission_room]}"
            console.print(x=hud_x, y=y, string=mission_line, fg=COLOR_HUD_TITLE)

        # Divider
        y += 2
        console.print(x=hud_x, y=y, string="-" * HUD_WIDTH, fg=COLOR_DIVIDER)
        y += 2

        # Keybinding help
        help_lines: list[tuple[str, str, tuple[int, int, int]]] = [
            ("G", "Go To",  COLOR_HELP_KEY),
            ("M", "Map",    COLOR_HELP_KEY),
            ("h/j/k/l", "Move",    COLOR_HELP_KEY),
            ("y/u/b/n", "Diag",    COLOR_HELP_KEY),
        ]
        for key, desc, key_color in help_lines:
            line = f"{key:<9} {desc}"
            console.print(x=hud_x, y=y, string=line, fg=COLOR_HELP_DESC)
            y += 1

        # Bottom hint — ESC behaviour varies by mode (quit in city,
        # dispatch menu in space); we show a generic hint here.
        y = hud_view_height - 2
        console.print(x=hud_x, y=y, string="bump to land / interact", fg=COLOR_VALUE_DIM)
        console.print(x=hud_x, y=y + 1, string="ESC - menu / quit", fg=COLOR_VALUE_DIM)

    else:
        # ---- City mode: character stats ----
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
        y += 1

        # Active mission (between class/location and divider)
        if active_mission:
            mission_room = max(0, HUD_WIDTH - len("MISSION: ") - 1)
            mission_line = f"MISSION: {active_mission[:mission_room]}"
            console.print(
                x=hud_x,
                y=y,
                string=mission_line,
                fg=COLOR_HUD_TITLE,
            )
            y += 1

        # Divider
        y += 1
        console.print(
            x=hud_x,
            y=y,
            string="-" * HUD_WIDTH,
            fg=COLOR_DIVIDER,
        )

        # HP (color depends on ratio)
        y += 2
        console.print(x=hud_x, y=y, string="HP", fg=COLOR_LABEL)
        hp = max(0, stats.hp)
        max_hp = max(1, stats.max_hp)
        hp_str = f"{hp}/{max_hp}"
        hp_fg = COLOR_HP_GOOD if hp * 2 >= max_hp else COLOR_HP_LOW
        console.print(
            x=hud_x + 3,
            y=y,
            string=hp_str,
            fg=hp_fg,
        )

        # Gold
        y += 1
        console.print(x=hud_x, y=y, string="$", fg=COLOR_LABEL)
        console.print(
            x=hud_x + 2,
            y=y,
            string=str(stats.gold),
            fg=COLOR_VALUE_WHITE,
        )

        # Pilot skills (compact one-liner, below gold)
        y += 1
        skill_line = f"G:{stats.gunnery} P:{stats.piloting} E:{stats.engineering}"
        console.print(x=hud_x, y=y, string=skill_line[:HUD_WIDTH], fg=COLOR_SHIP_LABEL)

        # Footer hint at the bottom of the HUD
        y = hud_view_height - 2
        console.print(
            x=hud_x,
            y=y,
            string="ESC to quit",
            fg=COLOR_VALUE_DIM,
        )


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


def _bar_str(value: int, max_value: int, width: int = 8) -> str:
    """Return an 8-char bar string like '████░░░░'."""
    if max_value <= 0:
        return _BAR_CHAR_EMPTY * width
    full = max(0, min(width, value * width // max_value))
    return _BAR_CHAR_FULL * full + _BAR_CHAR_EMPTY * (width - full)


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
    selected_weapon_idx: int = 0,
    weapon_list: tuple[str, ...] = (),
    flee_chance: int | None = None,
    hit_chances: dict[str, int] | None = None,  # per-weapon hit % vs current target
    evade_bonus: int | None = None,      # player's current dodge % (movement + piloting)
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
    # Hull bar with shield background overlay: blue bg on bar cells
    # proportional to shield %. When both are full, the bar shows green #
    # on blue. When only shields remain, blue . cells show through.
    _bar_str_8 = _bar_str(phull, pmax_hull)
    _regen_rate = player_state.get("shield_regen_rate", 0)
    regen_suffix = f" R{_regen_rate}" if (pmax_shields > 0 and _regen_rate > 0) else ""
    hull_line = f"Hull {_bar_str_8} {hull_pct_display}%{regen_suffix}"
    console.print(x=hud_x, y=y, string=hull_line, fg=hull_color)
    if pmax_shields > 0:
        shield_bar = _bar_str(pshields, pmax_shields)
        for _i in range(8):
            if shield_bar[_i] == _BAR_CHAR_FULL:
                console.print(
                    x=hud_x + 5 + _i, y=y,
                    string=_bar_str_8[_i],
                    fg=hull_color,
                    bg=COLOR_SHIELD_BAR,
                )
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
    pow_line = f"Pow: {ppow}/{ppow_max}"
    console.print(x=hud_x, y=y, string=pow_line, fg=COLOR_POWER)
    y += 2

    # --- ENEMIES block ---
    if enemies:
        console.print(x=hud_x, y=y, string="ENEMIES", fg=COLOR_DIVIDER)
        y += 1
        ppos = player_state.get("pos")
        for _ei, _e in enumerate(enemies):
            if y > screen_height - 20:
                break
            is_target = _ei == target_idx
            marker = ">" if is_target else " "
            # Short name (trim to 9 chars at most)
            _name = _e.name[:9] if len(_e.name) > 9 else _e.name
            _e_hull_pct = _e.hull / max(_e.max_hull, 1)
            _e_hull_color = _hull_bar_color(_e_hull_pct)
            _e_pct_display = int(_e_hull_pct * 100)
            _bar = _bar_str(_e.hull, _e.max_hull, width=5)
            _dist_str = ""
            if ppos and hasattr(_e, 'pos'):
                import math as _m
                _dist_str = f" {int(_m.hypot(ppos.x - _e.pos.x, ppos.y - _e.pos.y))}"
            # Layout: > NAME ##.. 70% D5
            _line = f"{marker}{_name} {_bar} {_e_pct_display}%"
            # Trim to HUD_WIDTH
            _line = _line[:HUD_WIDTH]
            fg = COLOR_COMBAT_TITLE if is_target else COLOR_VALUE_DIM
            console.print(x=hud_x, y=y, string=_line, fg=fg)
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
            # Check if can fire
            wammo = player_state.get("weapon_ammo", {}).get(wid, 0)
            ap_req = ws.ap_cost
            pow_req = ws.power_cost if ws.slot_type == "energy" else 0
            has_ap = pap >= ap_req
            has_pow = ppow >= pow_req
            has_ammo = wammo > 0 or ws.ammo_capacity <= 0
            can_fire = has_ap and has_pow and has_ammo

            fg_w = COLOR_COMBAT_WEAPON if can_fire else COLOR_COMBAT_WEAPON_DIM
            sel_mark = "> " if i == selected_weapon_idx else "  "
            name_str = f"{sel_mark}[{i+1}] {ws.name}"
            console.print(x=hud_x, y=y, string=name_str[:HUD_WIDTH-1], fg=fg_w)
            y += 1

            # Show effective hit chance (includes gunnery + distance + target
            # dodge) for every weapon against the current target. Falls back
            # to base weapon accuracy when no target is selected.
            _w_hc = hit_chances.get(wid) if hit_chances else None
            if _w_hc is not None:
                stats_line = f"     DMG {ws.damage}  HIT {_w_hc}%"
            else:
                stats_line = f"     DMG {ws.damage}  ACC {ws.accuracy}%"
            console.print(x=hud_x, y=y, string=stats_line[:HUD_WIDTH-1], fg=COLOR_VALUE_DIM)
            y += 1

            if ws.slot_type == "energy":
                cost_line = f"     POW {ws.power_cost}  AP {ws.ap_cost}"
            else:
                ammo_str = f"{wammo}" if wammo >= 0 else "∞"
                cost_line = f"     AMMO {ammo_str}  AP {ws.ap_cost}"
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
        ("[ESC]", "Flee"),
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
        actions.insert(3, (f"[1-{len(weapon_list)}]", "Swap Wpn"))
    for key, desc in actions:
        line = f"{key} {desc}"
        console.print(x=hud_x, y=y, string=line[:HUD_WIDTH-1], fg=COLOR_COMBAT_ACTION)
        y += 1

    # Flee chance if shown
    if flee_chance is not None:
        y += 1
        flee_line = f"Flee: {flee_chance}%"
        fc = COLOR_HP_GOOD if flee_chance >= 50 else COLOR_HP_LOW
        console.print(x=hud_x, y=y, string=flee_line, fg=fc)
