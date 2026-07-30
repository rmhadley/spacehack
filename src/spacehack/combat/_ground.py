"""Ground combat loop — turn-based on-foot combat.

Mirrors :mod:`combat._loop` but adapted for ground:
  - AP per turn = 4 (brisker pace)
  - No shields, no power pool — armor provides flat DR
  - Hit chance uses REFLEXES, damage uses STRENGTH for melee
  - Weapon selection (1/2 keys toggle, [f] fires all active)
  - Tab to cycle targets
  - Laser shot animation + explosion on kill
  - Target highlight + range-colored indicator line
  - Per-weapon hit % in HUD
  - Enemy death → loot drop at position (no explosion)
  - Player death → ctx.player_dead = True
"""

from __future__ import annotations

from typing import Any

import tcod.console
import tcod.event

from .. import ui
from .. import world
from .. import message_log as _ml
from ..engine import RNG, SCREEN_WIDTH, SCREEN_HEIGHT, make_console
from ..data.ground_weapons import find_ground_weapon as _find_gw
from ..data.npc_chars import find_npc_char as _find_nc
from ..data.ground_armor import find_ground_armor as _find_ga
from ..data.trade_goods import find_trade_good as _find_good
from ._actions import _remove_dead_entity as _rde
from ._stats import _distance
from ._animations import (
    _bresenham_line,
    _responsive_sleep,
    _paint_target_highlight,
    _draw_range_colored_line,
)


# ---------------------------------------------------------------------------
# Formulas
# ---------------------------------------------------------------------------

def _ground_hp_from_stamina(stamina: int) -> int:
    """Player max HP derived from stamina."""
    return 20 + stamina * 2


def _total_armor_defense(ctx) -> int:
    """Sum defense from all equipped armor pieces."""
    _total = 0
    for _slot, _aid in ctx.equipped_ground_armor.items():
        if _aid:
            try:
                _armor = _find_ga(_aid)
                _total += _armor.defense
            except KeyError:
                pass
    return _total


def _ground_hit_chance(
    weapon_id: str,
    attacker_reflexes: int,
    target_reflexes: int,
) -> int:
    """Hit chance for ground combat.

    Clamped 5-95.  Each point of reflexes adds 3% accuracy and
    2% dodge (subtracted from incoming).
    """
    _ws = _find_gw(weapon_id)
    _dodge = target_reflexes * 2
    _chance = _ws.accuracy + attacker_reflexes * 3 - _dodge
    return max(5, min(95, _chance))


def _ground_damage(
    weapon_id: str,
    strength: int,
    armor_defense: int,
) -> int:
    """Damage after armor reduction. STR bonus applies to melee only."""
    _ws = _find_gw(weapon_id)
    _str_bonus = strength // 4 if _ws.damage_type == 'melee' else 0
    _raw = _ws.damage + _str_bonus
    return max(1, _raw - armor_defense)


def _all_hit_chances(
    weapon_ids: list[str],
    attacker_reflexes: int,
    target_reflexes: int,
) -> dict[str, int]:
    """Return {weapon_id: hit_chance} for all weapon_ids."""
    _result: dict[str, int] = {}
    for _wid in weapon_ids:
        _result[_wid] = _ground_hit_chance(_wid, attacker_reflexes, target_reflexes)
    return _result


# ---------------------------------------------------------------------------
# Ground combat HUD
# ---------------------------------------------------------------------------

_COLOR_GROUND_TITLE: tuple[int, int, int] = (255, 200, 100)    # gold
_COLOR_GROUND_PLAYER: tuple[int, int, int] = (100, 220, 255)   # cyan
_COLOR_GROUND_ENEMY: tuple[int, int, int] = (255, 100, 100)    # red
_COLOR_GROUND_WEAPON: tuple[int, int, int] = (255, 200, 100)   # gold
_COLOR_GROUND_WEAPON_DIM: tuple[int, int, int] = (120, 100, 60)  # dimmed
_COLOR_GROUND_ACTION: tuple[int, int, int] = (180, 220, 255)   # light blue
_COLOR_GROUND_MODE: tuple[int, int, int] = (255, 255, 150)     # yellow


def _render_ground_combat_hud(
    console: tcod.console.Console,
    *,
    player_hp: int,
    player_max_hp: int,
    enemy_name: str,
    enemy_hp: int,
    enemy_max_hp: int,
    distance: int,
    weapon_list: list[str],
    active_weapons: list[bool],
    hit_chances: dict[str, int],
    ap_remaining: int,
    ap_total: int,
) -> None:
    """Paint the ground combat HUD on the right panel.

    Shows player HP, AP, weapon list with hit %, enemy HP, distance,
    and action keys.
    """
    _hud_x = SCREEN_WIDTH - 25
    y = 0

    console.print(x=_hud_x, y=y, string="> GROUND COMBAT <", fg=_COLOR_GROUND_TITLE)
    y += 2

    # Player block
    console.print(x=_hud_x, y=y, string="PLAYER", fg=_COLOR_GROUND_PLAYER)
    y += 1
    _hp_bar = _bar_str(player_hp, player_max_hp, width=8)
    _hp_pct = player_hp * 100 // max(player_max_hp, 1)
    console.print(x=_hud_x, y=y, string=f"HP  {_hp_bar} {_hp_pct}%", fg=_COLOR_GROUND_PLAYER)
    y += 1
    console.print(x=_hud_x, y=y, string=f"AP: {ap_remaining}/{ap_total}", fg=_COLOR_GROUND_ACTION)
    y += 2

    # Weapon list
    if weapon_list:
        console.print(x=_hud_x, y=y, string="WEAPONS", fg=_COLOR_GROUND_TITLE)
        y += 1
        for _i, _wid in enumerate(weapon_list):
            try:
                _ws = _find_gw(_wid)
            except KeyError:
                continue
            _is_active = active_weapons[_i] if _i < len(active_weapons) else True
            _sel = "[x]" if _is_active else "[ ]"
            _name_fg = _COLOR_GROUND_WEAPON if _is_active else _COLOR_GROUND_WEAPON_DIM
            console.print(x=_hud_x, y=y, string=f"{_sel}[{_i+1}] {_ws.name}"[:24], fg=_name_fg)
            y += 1
            _hc = hit_chances.get(_wid, 0)
            console.print(x=_hud_x, y=y, string=f"     DMG {_ws.damage} HIT {_hc}%", fg=_ml.COLOR_VALUE_DIM)
            y += 1
            _rng = f"{_ws.min_range}-{_ws.max_range}" if _ws.min_range > 0 else f"0-{_ws.max_range}"
            console.print(x=_hud_x, y=y, string=f"     RNG {_rng} AP {_ws.ap_cost}", fg=_ml.COLOR_VALUE_DIM)
            y += 1
        y += 1

    # Enemy block
    console.print(x=_hud_x, y=y, string=f"ENEMY: {enemy_name}", fg=_COLOR_GROUND_ENEMY)
    y += 1
    _e_bar = _bar_str(enemy_hp, enemy_max_hp, width=8)
    _e_pct = enemy_hp * 100 // max(enemy_max_hp, 1)
    console.print(x=_hud_x, y=y, string=f"HP  {_e_bar} {_e_pct}%", fg=_COLOR_GROUND_ENEMY)
    y += 1
    console.print(x=_hud_x, y=y, string=f"Dist: {distance}", fg=_COLOR_GROUND_ENEMY)
    y += 2

    # Actions
    console.print(x=_hud_x, y=y, string="ACTIONS", fg=_COLOR_GROUND_TITLE)
    y += 1
    _actions = [
        ("[Tab]", "Target"),
        ("[m]",   "Move"),
        ("[f]",   "Fire"),
        ("[w]",   "Wait"),
        ("[ESC]", "Flee"),
    ]
    if len(weapon_list) > 1:
        _actions.insert(3, (f"[1-{len(weapon_list)}]", "Toggle Wpn"))
    for key, desc in _actions:
        console.print(x=_hud_x, y=y, string=f"{key} {desc}", fg=_COLOR_GROUND_ACTION)
        y += 1


def _bar_str(value: int, max_value: int, width: int = 10) -> str:
    """CP437-safe bar string."""
    if max_value <= 0:
        return "." * width
    _full = max(0, min(width, value * width // max_value))
    return "#" * _full + "." * (width - _full)


# ---------------------------------------------------------------------------
# Ground range line
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Render offset helpers — world coordinates → screen coordinates
# ---------------------------------------------------------------------------

def _render_offsets(game_map: world.GameMap) -> tuple[int, int]:
    """Return ``(offset_x, offset_y)`` for centering a dungeon map
    in the viewport. ``render_world()`` uses these internally, and
    our drawing calls need the same offset so target highlights,
    range lines, and animations paint at the right screen position."""
    _rw = SCREEN_WIDTH - 25
    _rh = SCREEN_HEIGHT - 6
    _ox = (_rw - game_map.width) // 2
    _oy = (_rh - game_map.height) // 2
    return (_ox, _oy)


def _paint_ground_range_line(
    console,
    player_pos: world.Position,
    target_pos: world.Position,
    weapon_id: str,
    view_w: int,
    view_h: int,
    offset_x: int = 0,
    offset_y: int = 0,
) -> None:
    """Draw a range-colored line using ground weapon ranges.

    ``offset_x/offset_y`` is the centering offset from
    :func:`_render_offsets` — world coordinates are shifted by this
    amount to match ``render_world()``'s position.
    Delegates to the shared :func:`_draw_range_colored_line` primitive.
    """
    try:
        _ws = _find_gw(weapon_id)
    except KeyError:
        return
    _draw_range_colored_line(
        console,
        player_pos, target_pos,
        _ws.max_range, _ws.min_range,
        0, 0, view_w, view_h,
        region_x=offset_x, region_y=offset_y,
    )


# ---------------------------------------------------------------------------
# Ground combat frame renderer
# ---------------------------------------------------------------------------

_RENDER_WIDTH: int = SCREEN_WIDTH - 25
_RENDER_HEIGHT: int = SCREEN_HEIGHT - 6


def _render_ground_combat_frame(
    console: tcod.console.Console,
    ctx,
    game_map: world.GameMap,
    *,
    player_hp: int,
    player_max_hp: int,
    enemy_name: str,
    enemy_hp: int,
    enemy_max_hp: int,
    enemy_pos: world.Position,
    distance: int,
    weapon_list: list[str],
    active_weapons: list[bool],
    hit_chances: dict[str, int],
    ap_remaining: int,
    ap_total: int,
    target_idx: int,
    enemies: list,     # list of world.Entity for target highlighting
    show_range_line: bool = False,
    range_weapon_id: str | None = None,
) -> None:
    """Render the full ground combat view: dungeon map + HUD + message log."""
    console.clear()
    _ox, _oy = _render_offsets(game_map)
    world.render_world(
        console, game_map,
        region_x=0, region_y=0,
        region_w=_RENDER_WIDTH, region_h=_RENDER_HEIGHT,
    )

    # Target highlight (gold recolor of enemy glyph)
    if 0 <= target_idx < len(enemies):
        _paint_target_highlight(
            console, 0, 0, _RENDER_WIDTH, _RENDER_HEIGHT,
            _ox, _oy,  # region_x, region_y = centering offset
            enemies[target_idx],
        )

    # Range line from player to target
    if show_range_line and range_weapon_id and enemies:
        _tgt = enemies[target_idx] if target_idx < len(enemies) else enemies[0]
        _paint_ground_range_line(
            console, ctx.player.pos, _tgt.pos,
            range_weapon_id, _RENDER_WIDTH, _RENDER_HEIGHT,
            offset_x=_ox, offset_y=_oy,
        )

    _render_ground_combat_hud(
        console,
        player_hp=player_hp,
        player_max_hp=player_max_hp,
        enemy_name=enemy_name,
        enemy_hp=enemy_hp,
        enemy_max_hp=enemy_max_hp,
        distance=distance,
        weapon_list=weapon_list,
        active_weapons=active_weapons,
        hit_chances=hit_chances,
        ap_remaining=ap_remaining,
        ap_total=ap_total,
    )
    _ml.render_message_log(
        console, ctx.log,
        screen_width=SCREEN_WIDTH,
        screen_height=SCREEN_HEIGHT,
    )
    ctx.context.present(console)


# ---------------------------------------------------------------------------
# Ground combat animations
# ---------------------------------------------------------------------------

def _animate_ground_laser_shot(
    console: tcod.console.Console,
    ctx,
    game_map: world.GameMap,
    shooter_pos: world.Position,
    target_pos: world.Position,
    is_hit: bool,
    frame_params: dict,
) -> None:
    """Animate a laser beam from shooter to target over 4 frames.

    Renders the ground combat frame, draws a bright line along the
    Bresenham path, then (if hit) two impact-flash frames.
    ``frame_params`` bundles the HUD rendering state (player_hp,
    enemy_hp, etc.) so callers don't pass 15 params.
    """
    _ox, _oy = _render_offsets(game_map)
    cells = list(_bresenham_line(
        shooter_pos.x, shooter_pos.y,
        target_pos.x, target_pos.y,
    ))
    if not cells or cells[-1] != (target_pos.x, target_pos.y):
        cells.append((target_pos.x, target_pos.y))

    # Beam frames: brighten over 4 frames
    for frame in range(4):
        _render_ground_frame(console, ctx, game_map, **frame_params)
        brightness = min(255, 130 + frame * 30)
        color = (brightness, brightness - 20, 100 + frame * 20)
        for i, (bx, by) in enumerate(cells):
            sx = bx + _ox
            sy = by + _oy
            if 0 <= sx < _RENDER_WIDTH and 0 <= sy < _RENDER_HEIGHT:
                if i == len(cells) - 1:
                    char = "*"
                elif i == 0:
                    char = "+"
                else:
                    char = "=" if i % 2 == 0 else "-"
                console.print(x=sx, y=sy, string=char, fg=color)
        ctx.context.present(console)
        _responsive_sleep(0.05)

    # Impact flash (if hit): two quick bright pulses at target
    if is_hit:
        for flash in range(2):
            _render_ground_frame(console, ctx, game_map, **frame_params)
            tx, ty = target_pos.x + _ox, target_pos.y + _oy
            if 0 <= tx < _RENDER_WIDTH and 0 <= ty < _RENDER_HEIGHT:
                fg = (255, 255, 255) if flash == 0 else (255, 200, 100)
                console.print(x=tx, y=ty, string="*", fg=fg)
            ctx.context.present(console)
            _responsive_sleep(0.06)


def _animate_ground_explosion(
    console: tcod.console.Console,
    ctx,
    game_map: world.GameMap,
    center_pos: world.Position,
    frame_params: dict,
) -> None:
    """Animate an expanding explosion at center_pos (5 rings)."""
    _ox, _oy = _render_offsets(game_map)
    _EXPLOSION_RINGS: tuple[tuple[str, tuple[int, int, int]], ...] = (
        ("*", (255, 200, 100)),
        ("+", (255, 255, 150)),
        ("o", (255, 255, 200)),
        ("O", (200, 200, 255)),
        ("#", (180, 180, 255)),
    )
    for rings in range(len(_EXPLOSION_RINGS)):
        _render_ground_frame(console, ctx, game_map, **frame_params)
        for ring_idx in range(min(rings + 1, len(_EXPLOSION_RINGS))):
            r_char, r_fg = _EXPLOSION_RINGS[ring_idx]
            dist = ring_idx + 1
            for dy in range(-dist, dist + 1):
                for dx in range(-dist, dist + 1):
                    if abs(dx) + abs(dy) != dist:
                        continue
                    sx, sy = (center_pos.x + dx) + _ox, (center_pos.y + dy) + _oy
                    if 0 <= sx < _RENDER_WIDTH and 0 <= sy < _RENDER_HEIGHT:
                        console.print(x=sx, y=sy, string=r_char, fg=r_fg)
        ctx.context.present(console)
        _responsive_sleep(0.07)

    # White flash frame
    _render_ground_frame(console, ctx, game_map, **frame_params)
    for dy in range(-4, 5):
        for dx in range(-4, 5):
            sx, sy = (center_pos.x + dx) + _ox, (center_pos.y + dy) + _oy
            if 0 <= sx < _RENDER_WIDTH and 0 <= sy < _RENDER_HEIGHT:
                if abs(dx) + abs(dy) <= 3:
                    console.print(x=sx, y=sy, string=" ", fg=(255, 255, 255), bg=(255, 255, 255))
    ctx.context.present(console)
    _responsive_sleep(0.08)

    # Void settle
    _render_ground_frame(console, ctx, game_map, **frame_params)
    _responsive_sleep(0.04)


# Shorthand: build frame_params and call _render_ground_combat_frame
def _render_ground_frame(
    console: tcod.console.Console,
    ctx,
    game_map: world.GameMap,
    **params,
) -> None:
    """One-frame render of the ground combat view (used during animations)."""
    _render_ground_combat_frame(console, ctx, game_map, **params)


# ---------------------------------------------------------------------------
# Ground combat loop
# ---------------------------------------------------------------------------

def _spawn_ground_loot(
    game_map: world.GameMap,
    pos: world.Position,
    enemy_id: str,
) -> None:
    """Drop loot at the enemy's death position (no explosion)."""
    try:
        _spec = _find_nc(enemy_id)
    except KeyError:
        return
    _pool = _spec.loot_pool
    if not _pool:
        return
    _min, _max = _spec.loot_count
    _count = RNG.randint(_min, _max)
    for _ in range(_count):
        _good_id = RNG.choice(_pool)
        _qty = RNG.randint(1, 2)
        game_map.entities.append(world.Entity(
            char="%",
            fg=(255, 215, 0),
            pos=pos,
            name="Loot", width=1, height=1,
            loot_data={"good_id": _good_id, "quantity": _qty},
        ))


def run_ground_combat(
    console: tcod.console.Console,
    ctx,
    enemy_entity: world.Entity,
    game_map: world.GameMap,
) -> tuple[str, str]:
    """Run a ground combat encounter against one enemy.

    Args:
        enemy_entity: the hostile Entity on the dungeon map.

    Returns:
        ``(outcome, defeated_enemy_id)`` where outcome is
        ``"VICTORY"``, ``"DEFEAT"``, or ``"FLEE"``.
    """
    try:
        _enemy_spec = _find_nc(enemy_entity.npc_char_id)
    except KeyError:
        ctx.log.add("Unknown ground enemy — cannot start combat.")
        return ("FLEE", "")

    # Determine enemy's weapon
    _enemy_weapon_id = ""
    if _enemy_spec.weapons:
        _enemy_weapon_id = _enemy_spec.weapons[0]
    elif _enemy_spec.weapon_pick:
        _enemy_weapon_id = RNG.choice(_enemy_spec.weapon_pick)

    # Compute stats
    _player_ap_total = 4
    _enemy_ap_total = 4

    _player_weapon_ids = list(ctx.equipped_ground_weapons)
    if not _player_weapon_ids:
        _player_weapon_ids = ["fists"]
    try:
        _player_ws = _find_gw(_player_weapon_ids[0])
    except KeyError:
        _player_ws = _find_gw("fists")

    _player_max_hp = _ground_hp_from_stamina(ctx.ground_stats.stamina)
    _player_hp = min(ctx.ground_hp, _player_max_hp)
    _enemy_max_hp = _enemy_spec.hp + _enemy_spec.stamina * 2
    _enemy_hp = _enemy_max_hp

    _player_ap = _player_ap_total
    _enemy_ap = _enemy_ap_total

    _player_pos = ctx.player.pos
    _enemy_pos = enemy_entity.pos

    _armor_defense = _total_armor_defense(ctx)

    # Targeting & weapons
    _enemies: list[world.Entity] = [enemy_entity]
    _target_idx = 0
    _active_weapons = [True] * len(_player_weapon_ids)

    _outcome = "FLEE"
    _defeated_id = ""

    # Helper to build frame_params for animations
    def _frame_params() -> dict:
        _dist = int(_distance(_player_pos, _enemy_pos))
        return {
            "player_hp": _player_hp,
            "player_max_hp": _player_max_hp,
            "enemy_name": _enemy_spec.name,
            "enemy_hp": _enemy_hp,
            "enemy_max_hp": _enemy_max_hp,
            "enemy_pos": _enemy_pos,
            "distance": _dist,
            "weapon_list": _player_weapon_ids,
            "active_weapons": _active_weapons,
            "hit_chances": _all_hit_chances(
                _active_ids(), ctx.ground_stats.reflexes, _enemy_spec.reflexes,
            ),
            "ap_remaining": _player_ap,
            "ap_total": _player_ap_total,
            "target_idx": _target_idx,
            "enemies": _enemies,
            "show_range_line": True,
            "range_weapon_id": _first_active_weapon(),
        }

    def _active_ids() -> list[str]:
        return [
            _player_weapon_ids[i] for i in range(len(_player_weapon_ids))
            if i < len(_active_weapons) and _active_weapons[i]
        ]

    def _first_active_weapon() -> str | None:
        _ids = _active_ids()
        return _ids[0] if _ids else None

    while True:
        _dist = int(_distance(_player_pos, _enemy_pos))

        # ---- Render ----
        _render_ground_combat_frame(
            console, ctx, game_map,
            player_hp=_player_hp,
            player_max_hp=_player_max_hp,
            enemy_name=_enemy_spec.name,
            enemy_hp=_enemy_hp,
            enemy_max_hp=_enemy_max_hp,
            enemy_pos=_enemy_pos,
            distance=_dist,
            weapon_list=_player_weapon_ids,
            active_weapons=_active_weapons,
            hit_chances=_all_hit_chances(
                _player_weapon_ids, ctx.ground_stats.reflexes, _enemy_spec.reflexes,
            ),
            ap_remaining=_player_ap,
            ap_total=_player_ap_total,
            target_idx=_target_idx,
            enemies=_enemies,
            show_range_line=True,
            range_weapon_id=_first_active_weapon(),
        )

        # ---- Auto-end-turn when AP depleted ----
        if _player_ap <= 0:
            # Enemy turn
            if _enemy_weapon_id and _enemy_ap > 0:
                try:
                    _ews = _find_gw(_enemy_weapon_id)
                except KeyError:
                    _ews = None
                if _ews and _dist <= _ews.max_range and _dist >= _ews.min_range:
                    _hit = RNG.randint(1, 100) <= _ground_hit_chance(
                        _enemy_weapon_id, _enemy_spec.reflexes, ctx.ground_stats.reflexes,
                    )
                    if _hit:
                        _dmg = _ground_damage(_enemy_weapon_id, _enemy_spec.strength, _armor_defense)
                        _player_hp -= _dmg
                        ctx.log.add_colored(
                            f"{_enemy_spec.name} hits you for {_dmg}!",
                            _ml.COLOR_ENEMY_ACTION,
                        )
                        if _player_hp <= 0:
                            _outcome = "DEFEAT"
                            break
                    else:
                        ctx.log.add_colored(
                            f"{_enemy_spec.name} fires but misses!",
                            _ml.COLOR_ENEMY_ACTION,
                        )
                _enemy_ap -= _ews.ap_cost if _ews else 1
            _player_ap = _player_ap_total
            _enemy_ap = _enemy_ap_total
            continue

        # ---- Player input ----
        for event in tcod.event.wait():
            if isinstance(event, tcod.event.Quit):
                _outcome = "FLEE"
                break
            if not isinstance(event, tcod.event.KeyDown):
                continue
            _sym_name: str = getattr(event.sym, "name", "").lower()

            # Movement (vim keys)
            _vim_keys = {
                "h": (-1, 0), "j": (0, 1), "k": (0, -1), "l": (1, 0),
                "y": (-1, -1), "u": (1, -1), "b": (-1, 1), "n": (1, 1),
            }
            if _sym_name in _vim_keys and _player_ap > 0:
                _dx, _dy = _vim_keys[_sym_name]
                _nx = _player_pos.x + _dx
                _ny = _player_pos.y + _dy
                if game_map.is_walkable(_nx, _ny):
                    _blocker = game_map.entity_at(_nx, _ny, exclude=ctx.player)
                    if _blocker is None or _blocker is enemy_entity:
                        _player_pos = world.Position(_nx, _ny)
                        ctx.player.pos = _player_pos
                        _player_ap -= 1
                else:
                    ctx.log.add("A wall blocks your path.")
                break

            # [Tab] / [Left] / [Right] -> Cycle target (prep for multi-enemy)
            if _sym_name in ("tab", "left", "right"):
                # Single-enemy: just re-highlight (no-op visually)
                break

            # [1]-[9] -> Toggle weapon on/off
            _num_keys = {
                "n1": 0, "n2": 1, "n3": 2, "n4": 3, "n5": 4,
                "n6": 5, "n7": 6, "n8": 7, "n9": 8,
                "kp_1": 0, "kp_2": 1, "kp_3": 2, "kp_4": 3, "kp_5": 4,
                "kp_6": 5, "kp_7": 6, "kp_8": 7, "kp_9": 8,
            }
            if _sym_name in _num_keys:
                _idx = _num_keys[_sym_name]
                if _idx < len(_active_weapons):
                    _active_weapons[_idx] = not _active_weapons[_idx]
                    _state = "ON" if _active_weapons[_idx] else "OFF"
                    try:
                        _wname = _find_gw(_player_weapon_ids[_idx]).name
                    except KeyError:
                        _wname = _player_weapon_ids[_idx]
                    ctx.log.add(f"Weapon {_idx + 1} ({_wname}): {_state}")
                break

            # [f] -> Fire ALL active weapons
            if _sym_name == "f":
                _fire_ids = _active_ids()
                if not _fire_ids:
                    ctx.log.add("No active weapons to fire.")
                    break

                # Check range against the first active weapon's range band
                _first_wid = _fire_ids[0]
                try:
                    _first_ws = _find_gw(_first_wid)
                except KeyError:
                    _first_ws = None

                if _first_ws is not None and (_dist > _first_ws.max_range or _dist < _first_ws.min_range):
                    ctx.log.add(f"Target out of range ({_dist}u, need {_first_ws.min_range}-{_first_ws.max_range}).")
                    break

                # Fire each active weapon in sequence
                for _fwid in _fire_ids:
                    if _enemy_hp <= 0:
                        break
                    try:
                        _fws = _find_gw(_fwid)
                    except KeyError:
                        continue

                    _hit = RNG.randint(1, 100) <= _ground_hit_chance(
                        _fwid, ctx.ground_stats.reflexes, _enemy_spec.reflexes,
                    )

                    # Animate shot
                    _animate_ground_laser_shot(
                        console, ctx, game_map,
                        _player_pos, _enemy_pos,
                        is_hit=_hit,
                        frame_params=_frame_params(),
                    )

                    if _hit:
                        _dmg = _ground_damage(_fwid, ctx.ground_stats.strength, 0)
                        _enemy_hp -= _dmg
                        ctx.log.add_colored(
                            f"{_fws.name} hits {_enemy_spec.name} for {_dmg}!",
                            _ml.COLOR_PLAYER_ACTION,
                        )
                        if _enemy_hp <= 0:
                            # Enemy death
                            _animate_ground_explosion(
                                console, ctx, game_map,
                                _enemy_pos,
                                frame_params=_frame_params(),
                            )
                            ctx.log.add_colored(
                                f"{_enemy_spec.name} collapses!",
                                _ml.COLOR_COMBAT_EVENT,
                            )
                            _rde(game_map, {0: enemy_entity}, 0)
                            _spawn_ground_loot(game_map, _enemy_pos, enemy_entity.npc_char_id)
                            from ..xp import add_xp as _add_xp
                            _add_xp(ctx, _enemy_spec.xp_reward)
                            if hasattr(ctx, 'player_counters'):
                                ctx.player_counters.total_kills += 1
                            _outcome = "VICTORY"
                            _defeated_id = enemy_entity.npc_char_id
                            break
                    else:
                        ctx.log.add_colored(
                            f"{_fws.name} misses {_enemy_spec.name}!",
                            _ml.COLOR_PLAYER_ACTION,
                        )

                    # Deduct AP (max cost among fired weapons)
                    _player_ap -= _fws.ap_cost

                # If no VICTORY yet and AP is now 0, end turn
                if _outcome == "FLEE" and _player_ap <= 0:
                    _player_ap = 0
                break

            # [w] -> Wait (end turn)
            if _sym_name == "w":
                _player_ap = 0
                break

            # ESC -> Flee
            if event.sym in ui._ESCAPE_SYMS:
                _flee_chance = 60  # flat 60% flee chance for ground
                if RNG.randint(1, 100) <= _flee_chance:
                    ctx.log.add("You break contact and retreat!")
                    _outcome = "FLEE"
                else:
                    ctx.log.add("Failed to flee!")
                    _player_ap = 0
                break

        if _outcome != "FLEE":
            break

    # Save HP back to ctx
    ctx.ground_hp = max(0, _player_hp)
    ctx.ground_max_hp = _player_max_hp

    if _outcome == "DEFEAT":
        ctx.player_dead = True
        ctx.log.add_colored("You collapse from your wounds...", _ml.COLOR_COMBAT_EVENT)

    return (_outcome, _defeated_id)
