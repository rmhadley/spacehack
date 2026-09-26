"""Space-combat HUD rendering (the right-panel combat screen).

The combat title, PLAYER / ENEMIES / WEAPONS blocks, and ACTIONS
legend that :func:`render_combat_hud` paints — split out of
:mod:`spacehack.hud` (doc 52.3 ratchet) so the shared HUD module
stays within the architecture limit. Shared bar/pair formatting
(``_bar_str``, ``ap_pool_str``, ``volley_costs``, …) stays in
:mod:`spacehack.hud`; ground combat renders from
:mod:`spacehack.combat._ground_render`.
"""

from __future__ import annotations

from .framebuffer import FrameBuffer

from .engine import HUD_WIDTH
from .hud import (
    COLOR_EVADE,
    COLOR_HP_GOOD,
    COLOR_HP_LOW,
    COLOR_LABEL,
    HUD_TEXT_MAX,
    _bar_str,
    _render_action_pairs,
    ap_pool_str,
    range_band_color,
    volley_costs,
)
from .ui import COLOR_DIVIDER, COLOR_VALUE_DIM


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


# Space-combat enemy rows show name + distance on one line; 18 chars keeps


# long names readable without crowding the distance readout off-panel.


_ENEMY_NAME_MAX: int = 18


_UNLIMITED_AMMO_LABEL: str = "INF"


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
    console.print(x=hud_x, y=y, string="-" * HUD_TEXT_MAX, fg=COLOR_DIVIDER)
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
        console.print(x=hud_x, y=y, string=_shd[:HUD_TEXT_MAX], fg=COLOR_SHIELD_BAR)
        # Level indicator (white bg) tracks ONLY the S-key rate, so
        # pressing S moves the highlight 1:1 with the setting.
        for _i in range(min(_rate, len(_bar))):
            console.print(x=hud_x + 5 + _i, y=y, string=_bar[_i], fg=COLOR_SHIELD_BAR, bg=(255, 255, 255))
        y += 1
    console.print(
        x=hud_x, y=y,
        string=f"Hull {_bar_str(phull, pmax_hull)} {phull}/{pmax_hull}",
        fg=hull_color,
    )
    return y + 1


def _render_ap_evade_pow_rows(console, hud_x, y, player_state, evade_bonus) -> int:
    """Paint the player's AP / evade / power rows; return the next row."""
    pap = player_state.get("ap_remaining", 0)
    pap_total = player_state.get("ap_total", 3)
    pap_carry = player_state.get("ap_carry_twentieths", 0)
    console.print(
        x=hud_x, y=y,
        string=f"AP: {pap}/{ap_pool_str(pap_total, pap_carry)}",
        fg=COLOR_AP if pap > 0 else COLOR_HULL_BAR_RED,
    )
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
    _name = enemy.name[:_ENEMY_NAME_MAX] if len(enemy.name) > _ENEMY_NAME_MAX else enemy.name
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
        _shd_bar = _bar_str(enemy.shields, enemy.max_shields, width=5)
        _shd_line = f"  Shd {_shd_bar} {enemy.shields}/{enemy.max_shields}"
        console.print(x=hud_x, y=y, string=_shd_line[:HUD_TEXT_MAX], fg=COLOR_SHIELD_BAR)
        y += 1
    _e_hull_pct = enemy.hull / max(enemy.max_hull, 1)
    _bar = _bar_str(enemy.hull, enemy.max_hull, width=5)
    _hull_line = f"  Hul {_bar} {enemy.hull}/{enemy.max_hull}"
    console.print(x=hud_x, y=y, string=_hull_line[:HUD_TEXT_MAX], fg=_hull_bar_color(_e_hull_pct))
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


def _effective_weapon_ap_cost(ws, player_state=None) -> int:
    """Return a combat HUD weapon cost after trait discounts."""
    player_state = player_state or {}
    discount = (
        player_state.get("plasma_ap_discount", 0)
        if ws.slot_type == "plasma" else 0
    )
    return max(1, ws.ap_cost - discount)


def _render_weapon_row(
    console, hud_x, y, slot, wid, ws, wammo, is_active, hit_chances,
    player_state=None, focus_active=False, weapon_quality: int = 0,
) -> int:
    """Paint one weapon's name / hit / cost rows; return the next row.

    When ``focus_active`` (the Focus trait is live), the doubled AP /
    power / range the shot will actually cost are shown instead of the
    catalog values, so the weapon readout always matches the gate.
    ``weapon_quality`` is the flown instance's tier (doc 48.7) — the
    name row reads the token-prefixed label.
    """
    from .ship import weapon_display_name
    sel_mark = "[x]" if is_active else "[ ]"
    name_str = f"{sel_mark}[{slot+1}] {weapon_display_name(wid, weapon_quality)}"
    fg_wpn = COLOR_COMBAT_WEAPON if is_active else COLOR_COMBAT_WEAPON_DIM
    console.print(x=hud_x, y=y, string=name_str[:HUD_TEXT_MAX], fg=fg_wpn)
    y += 1
    _w_hc = hit_chances.get(wid) if hit_chances else None
    _mult = 2 if focus_active else 1
    _max_range = getattr(ws, "max_range", 0) * _mult
    _rng = (
        f" RNG {getattr(ws, 'min_range', 1) * _mult}-{_max_range}"
        if _max_range > 0 else ""
    )
    if _w_hc is not None:
        stats_line = f"     DMG {ws.damage} HIT {_w_hc}%{_rng}"
    else:
        stats_line = f"     DMG {ws.damage} ACC {ws.accuracy}%{_rng}"
    console.print(x=hud_x, y=y, string=stats_line[:HUD_TEXT_MAX], fg=COLOR_VALUE_DIM)
    y += 1
    _ap_cost = _effective_weapon_ap_cost(ws, player_state) * _mult
    if ws.slot_type in ("energy", "plasma"):
        cost_line = f"     POW {ws.power_cost * _mult} AP {_ap_cost}"
    else:
        ammo_str = f"{wammo}/{ws.ammo_capacity}" if ws.ammo_capacity > 0 else _UNLIMITED_AMMO_LABEL
        cost_line = f"     AMMO {ammo_str} AP {_ap_cost}"
    console.print(x=hud_x, y=y, string=cost_line[:HUD_TEXT_MAX], fg=COLOR_VALUE_DIM)
    return y + 1


def _render_volley_header(
    console, hud_x, y, weapon_list, active_weapons, player_state, focus_active,
) -> None:
    """Paint the WEAPONS title row with the armed-volley cost readout.

    ``focus_active`` doubles the armed readout to match the charge."""
    from .data.weapons import find_weapon as _fw
    _mult = 2 if focus_active else 1
    _count, _max_ap, _sum_pow = volley_costs(weapon_list, active_weapons, _fw)
    console.print(x=hud_x, y=y, string="WEAPONS", fg=COLOR_DIVIDER)
    if not _count:
        return
    console.print(x=hud_x + 8, y=y, string=f"[{_count}]", fg=COLOR_VALUE_DIM)
    _active_specs = (
        _fw(_wid) for _i, _wid in enumerate(weapon_list)
        if not active_weapons or active_weapons[_i]
    )
    _max_ap = max(
        (_effective_weapon_ap_cost(_spec, player_state) for _spec in _active_specs),
        default=0,
    ) * _mult
    _ap_fg = COLOR_HP_GOOD if _max_ap <= player_state.get("ap_remaining", 0) else COLOR_HP_LOW
    console.print(x=hud_x + 12, y=y, string=f"{_max_ap}AP", fg=_ap_fg)
    if _sum_pow:
        _pow_ok = _sum_pow * _mult <= player_state.get("power_pool", 0)
        _pow_fg = COLOR_HP_GOOD if _pow_ok else COLOR_HP_LOW
        console.print(x=hud_x + 16, y=y, string=f"{_sum_pow * _mult}POW", fg=_pow_fg)


def _render_weapons_block(
    console, hud_x, y, weapon_list, active_weapons, player_state, hit_chances,
    focus_active=False, weapon_qualities=(),
) -> int:
    """Paint the WEAPONS list + armed-volley cost; return the next row."""
    from .data.weapons import find_weapon as _fw
    _render_volley_header(
        console, hud_x, y, weapon_list, active_weapons, player_state, focus_active,
    )
    y += 1
    for i, wid in enumerate(weapon_list):
        try:
            ws = _fw(wid)
        except KeyError:
            continue
        wammo = player_state.get("weapon_ammo", {}).get(i, 0)
        is_active = active_weapons[i] if active_weapons else True
        y = _render_weapon_row(
            console, hud_x, y, i, wid, ws, wammo, is_active, hit_chances,
            player_state, focus_active=focus_active,
            weapon_quality=weapon_qualities[i] if i < len(weapon_qualities) else 0,
        )
    return y + 1


def _render_combat_actions(console, hud_x, y, weapon_list, can_board=False) -> int:
    """Paint the ACTIONS key hints; return the next row."""
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
    # Same rule for BOARD: advertise it only while the target is
    # actually boardable (doc 40 6a).
    if can_board:
        actions.insert(-1, ("[d]", "Board"))
    return _render_action_pairs(console, hud_x, y, actions, COLOR_COMBAT_ACTION)


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
    hit_chances: dict[str, int] | None = None,  # per-weapon hit % vs current target
    evade_bonus: int | None = None,      # player's current dodge % (movement + piloting)
    range_weapon_id: str | None = None,  # weapon id for coloring distance by range
    focus_active: bool = False,          # Focus trait live (single weapon enabled)
    can_board: bool = False,             # space: current target is boardable ([d] hint)
    weapon_qualities: tuple = (),        # per-slot flown tiers (doc 48.7)
) -> None:
    """Paint the combat HUD replacing the normal space HUD.

    Right panel, top to bottom: COMBAT title, PLAYER block, ENEMIES
    block, WEAPONS list, then ACTIONS key hints.
    """
    hud_x = screen_width - HUD_WIDTH
    y = _render_combat_header(console, hud_x, 0, player_mode)
    y = _render_player_block(console, hud_x, y, player_state, evade_bonus)
    y = _render_enemies_block(console, hud_x, y, enemies, target_idx, screen_height, player_state, range_weapon_id)
    y = _render_weapons_block(
        console, hud_x, y, weapon_list, active_weapons, player_state,
        hit_chances, focus_active=focus_active, weapon_qualities=weapon_qualities,
    )
    _render_combat_actions(console, hud_x, y, weapon_list, can_board)
