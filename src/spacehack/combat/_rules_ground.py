"""Ground combat rules — flavor module for the unified combat loop.

All state and behavior specific to on-foot ground combat lives here.
The unified loop in :mod:`._loop` calls these functions by name —
same call shape as :mod:`._rules_space`.

**Combat session state** is encapsulated in :class:`GroundCombatState`,
a single module-level dataclass replacing the old scattered globals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .. import world
from .. import ui
from .. import message_log as _ml
from ..engine import RNG, SCREEN_WIDTH, SCREEN_HEIGHT, HUD_WIDTH
from ..data.ground_weapons import find_ground_weapon as _find_gw
from ..data.npc_chars import find_npc_char as _find_nc
from ..data.ground_armor import find_ground_armor as _find_ga
from ..hud import _bar_str

from ._types import CombatResult
from ._stats import _distance
from ._actions import _spawn_loot_at_position as _shared_loot
from ._animations import (
    _bresenham_line,
    _has_los,
    _responsive_sleep,
    _paint_target_highlight,
    _draw_range_colored_line,
)


# ---------------------------------------------------------------------------
# GroundEnemyInstance — per-enemy state during combat
# ---------------------------------------------------------------------------

@dataclass
class GroundEnemyInstance:
    """Per-enemy combat state."""

    entity: world.Entity
    spec: Any
    weapon_id: str = ""
    hp: int = 30
    max_hp: int = 30
    ap: int = 4
    ap_total: int = 4
    cells_moved_this_turn: int = 0

    @property
    def alive(self) -> bool:
        return self.hp > 0

    @property
    def pos(self) -> world.Position:
        return self.entity.pos

    @pos.setter
    def pos(self, value: world.Position) -> None:
        self.entity.pos = value

    @property
    def name(self) -> str:
        return self.spec.name if self.spec else "Unknown"


# ---------------------------------------------------------------------------
# GroundCombatState — all session state in one place
# ---------------------------------------------------------------------------

@dataclass
class GroundCombatState:
    """Encapsulates all mutable state for one ground combat encounter."""

    ctx: Any
    game_map: world.GameMap
    enemies: list[GroundEnemyInstance] = field(default_factory=list)
    player_hp: int = 30
    player_max_hp: int = 30
    player_ap: int = 4
    player_ap_total: int = 4
    armor_defense: int = 0
    cells_moved_this_turn: int = 0
    active_weapon_list: list[bool] = field(default_factory=list)
    target_idx: int = 0
    console: Any = None


_state: GroundCombatState | None = None

# Rendering constants
_RENDER_WIDTH: int = SCREEN_WIDTH - HUD_WIDTH
_RENDER_HEIGHT: int = SCREEN_HEIGHT - 6


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

def init(ctx, enemy_entities: list[world.Entity], game_map: world.GameMap) -> None:
    """Set up combat session state for a ground combat encounter."""
    global _state

    _enemies: list[GroundEnemyInstance] = []
    for _ent in enemy_entities:
        try:
            _spec = _find_nc(_ent.npc_char_id)
        except KeyError:
            continue
        _wid = ""
        if _spec.weapons:
            _wid = _spec.weapons[0]
        elif _spec.weapon_pick:
            _wid = RNG.choice(_spec.weapon_pick)
        _max_hp = _spec.hp + _spec.stamina * 2
        _enemies.append(GroundEnemyInstance(
            entity=_ent, spec=_spec, weapon_id=_wid,
            hp=_max_hp, max_hp=_max_hp, ap=4, ap_total=4,
        ))

    _player_max_hp = 20 + ctx.ground_stats.stamina * 2
    _hp_delta = _player_max_hp - ctx.ground_max_hp
    if _hp_delta > 0:
        ctx.ground_hp += _hp_delta
    _player_hp = min(ctx.ground_hp, _player_max_hp)

    _armor_defense = 0
    for _slot, _aid in ctx.equipped_ground_armor.items():
        if _aid:
            try:
                _armor_defense += _find_ga(_aid).defense
            except KeyError:
                pass

    _weapons = list(ctx.equipped_ground_weapons)
    if not _weapons:
        _weapons = ["fists"]

    _state = GroundCombatState(
        ctx=ctx, game_map=game_map,
        enemies=_enemies,
        player_hp=_player_hp, player_max_hp=_player_max_hp,
        player_ap=4, player_ap_total=4,
        armor_defense=_armor_defense,
        active_weapon_list=[True] * len(_weapons),
    )

    _names = ", ".join(_e.name for _e in _enemies)
    ctx.log.add_colored(
        f"Combat starts! {_names} engage!",
        _ml.COLOR_COMBAT_EVENT,
    )


# ---------------------------------------------------------------------------
# State accessors
# ---------------------------------------------------------------------------

def player_hp(ctx) -> int:
    return _state.player_hp


def player_max_hp(ctx) -> int:
    return _state.player_max_hp


def player_ap(ctx) -> int:
    return _state.player_ap


def player_ap_total(ctx) -> int:
    return _state.player_ap_total


def player_weapons(ctx) -> list[str]:
    _w = list(ctx.equipped_ground_weapons)
    return _w if _w else ["fists"]


def active_weapons(ctx) -> list[bool]:
    return list(_state.active_weapon_list)


def set_active_weapons(ctx, active: list[bool]) -> None:
    _state.active_weapon_list = list(active)


# ---------------------------------------------------------------------------
# Enemy accessors
# ---------------------------------------------------------------------------

def set_target_idx(ctx, idx: int) -> None:
    _state.target_idx = idx


def get_enemies(ctx) -> list[GroundEnemyInstance]:
    return [e for e in _state.enemies if e.alive]


def enemy_pos(enemy: GroundEnemyInstance) -> world.Position:
    return enemy.pos


def enemy_name(enemy: GroundEnemyInstance) -> str:
    return enemy.name


def enemy_hp(enemy: GroundEnemyInstance) -> int:
    return enemy.hp


def enemy_max_hp(enemy: GroundEnemyInstance) -> int:
    return enemy.max_hp


def enemy_alive(enemy: GroundEnemyInstance) -> bool:
    return enemy.alive


# ---------------------------------------------------------------------------
# Combat math
# ---------------------------------------------------------------------------

def _ground_hit_chance_raw(
    weapon_id: str,
    attacker_reflexes: int,
    target_reflexes: int,
    target_dodge_bonus: int = 0,
) -> int:
    """Base hit chance before movement dodge.  New param ``target_dodge_bonus``
    subtracts the target's evade (movement + reflexes) at the end."""
    _ws = _find_gw(weapon_id)
    return max(5, min(95,
        _ws.accuracy + attacker_reflexes * 3 - target_reflexes * 2 - target_dodge_bonus,
    ))


def _ground_damage_raw(
    weapon_id: str, strength: int, armor_defense: int,
) -> int:
    _ws = _find_gw(weapon_id)
    _str_bonus = strength // 4 if _ws.damage_type == 'melee' else 0
    return max(1, _ws.damage + _str_bonus - armor_defense)


def _calc_ground_move_dodge(cells_moved: int) -> int:
    """Movement evade: +5% per cell moved, capped at 30.

    Reflexes are already handled by the ``target_reflexes * 2`` term
    in :func:`_ground_hit_chance_raw` — this helper is movement-only."""
    return min(cells_moved * 5, 30)


def hit_chance(weapon_id: str, enemy: GroundEnemyInstance, ctx) -> int:
    _er = enemy.spec.reflexes if enemy.spec else 10
    _move_dodge = _calc_ground_move_dodge(enemy.cells_moved_this_turn)
    return _ground_hit_chance_raw(
        weapon_id, ctx.ground_stats.reflexes, _er,
        target_dodge_bonus=_move_dodge,
    )


def damage(weapon_id: str, enemy: GroundEnemyInstance, ctx) -> int:
    _ws = _find_gw(weapon_id)
    _str_bonus = ctx.ground_stats.strength // 4 if _ws.damage_type == 'melee' else 0
    _dmg = max(1, _ws.damage + _str_bonus)
    enemy.hp -= _dmg
    return _dmg


# ---------------------------------------------------------------------------
# Weapon actions
# ---------------------------------------------------------------------------

def can_fire(weapon_id: str, ctx) -> tuple[bool, str]:
    _ws = _find_gw(weapon_id)
    _alive = get_enemies(ctx)
    if _state.target_idx >= len(_alive):
        return False, "No valid target"
    _target = _alive[_state.target_idx]
    _dist = int(_distance(ctx.player.pos, _target.pos))
    if _dist > _ws.max_range or _dist < _ws.min_range:
        return False, f"Out of range ({_dist}u, need {_ws.min_range}-{_ws.max_range})"
    if _state.player_ap < _ws.ap_cost:
        return False, f"Need {_ws.ap_cost} AP (have {_state.player_ap})"
    if not _has_los(
        _state.game_map,
        ctx.player.pos.x, ctx.player.pos.y,
        _target.pos.x, _target.pos.y,
    ):
        return False, "Blocked by wall"
    return True, ""


def weapon_ap_cost(weapon_id: str, ctx) -> int:
    return _find_gw(weapon_id).ap_cost


def weapon_name(weapon_id: str, ctx) -> str:
    return _find_gw(weapon_id).name


def consume_shot(weapon_id: str, ctx) -> None:
    pass


# ---------------------------------------------------------------------------
# Player movement
# ---------------------------------------------------------------------------

def try_move(ctx, game_map: world.GameMap, dx: int, dy: int) -> bool:
    _nx = ctx.player.pos.x + dx
    _ny = ctx.player.pos.y + dy
    if not game_map.is_walkable(_nx, _ny):
        return False
    _blocker = game_map.entity_at(_nx, _ny, exclude=ctx.player)
    if _blocker is not None:
        _enemy_ids = {id(_e.entity) for _e in _state.enemies if _e.alive}
        if id(_blocker) not in _enemy_ids:
            return False
    ctx.player.pos = world.Position(_nx, _ny)
    _state.player_ap -= 1
    _state.cells_moved_this_turn += 1
    from ..dungeon import reveal_around as _reveal_around
    _reveal_around(game_map, ctx.player.pos, radius=game_map.sight_radius)
    return True


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

_COLOR_GROUND_TITLE: tuple[int, int, int] = (255, 200, 100)
_COLOR_GROUND_PLAYER: tuple[int, int, int] = (100, 220, 255)
_COLOR_GROUND_ENEMY: tuple[int, int, int] = (255, 100, 100)
_COLOR_GROUND_ENEMY_TARGET: tuple[int, int, int] = (255, 220, 100)
_COLOR_GROUND_WEAPON: tuple[int, int, int] = (255, 200, 100)
_COLOR_GROUND_WEAPON_DIM: tuple[int, int, int] = (120, 100, 60)
_COLOR_GROUND_ACTION: tuple[int, int, int] = (180, 220, 255)


def _ground_offsets(game_map: world.GameMap) -> tuple[int, int]:
    return ((_RENDER_WIDTH - game_map.width) // 2, (_RENDER_HEIGHT - game_map.height) // 2)


def _ground_range_line(console, player_pos, target_pos, weapon_id, ox, oy, *, color_override=None):
    try:
        _ws = _find_gw(weapon_id)
    except KeyError:
        return
    _draw_range_colored_line(
        console, player_pos, target_pos,
        _ws.max_range, _ws.min_range,
        0, 0, _RENDER_WIDTH, _RENDER_HEIGHT,
        region_x=ox, region_y=oy,
        color_override=color_override,
    )


def render_frame(console, ctx, game_map: world.GameMap) -> None:
    console.clear()
    _ox, _oy = _ground_offsets(game_map)
    world.render_world(
        console, game_map,
        region_x=0, region_y=0,
        region_w=_RENDER_WIDTH, region_h=_RENDER_HEIGHT,
    )

    _alive = get_enemies(ctx)
    if _state.target_idx < len(_alive):
        _paint_target_highlight(
            console, 0, 0, _RENDER_WIDTH, _RENDER_HEIGHT, _ox, _oy,
            _alive[_state.target_idx].entity,
        )

    _weapons = list(ctx.equipped_ground_weapons)
    if not _weapons:
        _weapons = ["fists"]
    _active_w = [
        _weapons[i] for i in range(len(_weapons))
        if i < len(_state.active_weapon_list) and _state.active_weapon_list[i]
    ]
    if _active_w and _state.target_idx < len(_alive):
        _tgt = _alive[_state.target_idx]
        _los_blocked = not _has_los(
            game_map,
            ctx.player.pos.x, ctx.player.pos.y,
            _tgt.pos.x, _tgt.pos.y,
        )
        _ground_range_line(
            console, ctx.player.pos, _tgt.pos,
            _active_w[0], _ox, _oy,
            color_override=(255, 60, 60) if _los_blocked else None,
        )

    _hud_x = SCREEN_WIDTH - HUD_WIDTH
    y = 0
    console.print(x=_hud_x, y=y, string="> GROUND COMBAT <", fg=_COLOR_GROUND_TITLE)
    y += 2

    console.print(x=_hud_x, y=y, string="PLAYER", fg=_COLOR_GROUND_PLAYER)
    y += 1
    _hp_bar = _bar_str(_state.player_hp, _state.player_max_hp, width=8)
    _hp_pct = _state.player_hp * 100 // max(_state.player_max_hp, 1)
    console.print(x=_hud_x, y=y, string=f"HP  {_hp_bar} {_hp_pct}%", fg=_COLOR_GROUND_PLAYER)
    y += 1
    console.print(x=_hud_x, y=y, string=f"AP: {_state.player_ap}/{_state.player_ap_total}", fg=_COLOR_GROUND_ACTION)
    y += 1
    _eva = _calc_ground_move_dodge(_state.cells_moved_this_turn)
    console.print(x=_hud_x, y=y, string=f"EVA: {_eva}%", fg=_COLOR_GROUND_ACTION)
    y += 2

    if _weapons:
        console.print(x=_hud_x, y=y, string="WEAPONS", fg=_COLOR_GROUND_TITLE)
        y += 1
        for _i, _wid in enumerate(_weapons):
            try:
                _ws = _find_gw(_wid)
            except KeyError:
                continue
            _is_active = _state.active_weapon_list[_i] if _i < len(_state.active_weapon_list) else True
            _sel = "[x]" if _is_active else "[ ]"
            _name_fg = _COLOR_GROUND_WEAPON if _is_active else _COLOR_GROUND_WEAPON_DIM
            console.print(x=_hud_x, y=y, string=f"{_sel}[{_i+1}] {_ws.name}"[:24], fg=_name_fg)
            y += 1
            _hc = hit_chance(_wid, _alive[_state.target_idx], ctx) if _state.target_idx < len(_alive) else 0
            console.print(x=_hud_x, y=y, string=f"     DMG {_ws.damage} HIT {_hc}%", fg=ui.COLOR_VALUE_DIM)
            y += 1
            _rng = f"{_ws.min_range}-{_ws.max_range}" if _ws.min_range > 0 else f"0-{_ws.max_range}"
            console.print(x=_hud_x, y=y, string=f"     RNG {_rng} AP {_ws.ap_cost}", fg=ui.COLOR_VALUE_DIM)
            y += 1
        y += 1

    _alive_enemies = [e for e in _state.enemies if e.alive]
    if _alive_enemies:
        console.print(x=_hud_x, y=y, string="ENEMIES", fg=_COLOR_GROUND_TITLE)
        y += 1
        for _i, _gei in enumerate(_alive_enemies):
            _is_target = _i == _state.target_idx
            _name_fg = _COLOR_GROUND_ENEMY_TARGET if _is_target else _COLOR_GROUND_ENEMY
            _marker = ">" if _is_target else " "
            console.print(x=_hud_x, y=y, string=f"{_marker}{_gei.name}"[:24], fg=_name_fg)
            y += 1
            _e_bar = _bar_str(_gei.hp, _gei.max_hp, width=8)
            _e_pct = _gei.hp * 100 // max(_gei.max_hp, 1)
            _dist = int(_distance(ctx.player.pos, _gei.pos))
            console.print(x=_hud_x, y=y, string=f"  HP {_e_bar} {_e_pct}%  {_dist}u", fg=_name_fg)
            y += 1
    y += 1

    console.print(x=_hud_x, y=y, string="ACTIONS", fg=_COLOR_GROUND_TITLE)
    y += 1
    _actions = [
        ("[Tab]", "Target"), ("[m]", "Move"), ("[f]", "Fire"), ("[w]", "Wait"),
    ]
    if len(_weapons) > 1:
        _actions.insert(3, (f"[1-{len(_weapons)}]", "Toggle Wpn"))
    for key, desc in _actions:
        console.print(x=_hud_x, y=y, string=f"{key} {desc}", fg=_COLOR_GROUND_ACTION)
        y += 1

    _ml.render_message_log(
        console, ctx.log,
        screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT,
    )


# ---------------------------------------------------------------------------
# Animation
# ---------------------------------------------------------------------------

def animate_fire(
    console, ctx, game_map: world.GameMap,
    from_pos: world.Position, to_pos: world.Position, is_hit: bool,
) -> None:
    _ox, _oy = _ground_offsets(game_map)
    cells = list(_bresenham_line(from_pos.x, from_pos.y, to_pos.x, to_pos.y))
    if not cells or cells[-1] != (to_pos.x, to_pos.y):
        cells.append((to_pos.x, to_pos.y))

    for frame in range(4):
        render_frame(console, ctx, game_map)
        brightness = min(255, 130 + frame * 30)
        color = (brightness, brightness - 20, 100 + frame * 20)
        for i, (bx, by) in enumerate(cells):
            sx, sy = bx + _ox, by + _oy
            if 0 <= sx < _RENDER_WIDTH and 0 <= sy < _RENDER_HEIGHT:
                char = "*" if i == len(cells) - 1 else ("+" if i == 0 else ("=" if i % 2 == 0 else "-"))
                console.print(x=sx, y=sy, string=char, fg=color)
        ctx.context.present(console)
        _responsive_sleep(0.05)

    if is_hit:
        for flash in range(2):
            render_frame(console, ctx, game_map)
            tx, ty = to_pos.x + _ox, to_pos.y + _oy
            if 0 <= tx < _RENDER_WIDTH and 0 <= ty < _RENDER_HEIGHT:
                fg = (255, 255, 255) if flash == 0 else (255, 200, 100)
                console.print(x=tx, y=ty, string="*", fg=fg)
            ctx.context.present(console)
            _responsive_sleep(0.06)


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def on_kill(game_map: world.GameMap, enemy: GroundEnemyInstance, ctx) -> None:
    _ent = enemy.entity
    if _ent is not None and _ent in game_map.entities:
        game_map.entities.remove(_ent)

    if enemy.spec and enemy.spec.loot_pool:
        _min, _max = enemy.spec.loot_count
        _shared_loot(
            game_map, _ent.pos, enemy.spec.loot_pool,
            count_range=(_min, _max), qty_range=(1, 2),
        )

    if enemy.spec:
        from ..xp import add_xp as _add_xp
        _add_xp(ctx, enemy.spec.xp_reward)
        if hasattr(ctx, 'player_counters'):
            ctx.player_counters.total_kills += 1

    enemy.hp = 0


def on_player_death(ctx) -> None:
    ctx.player_dead = True
    ctx.log.add_colored("You collapse from your wounds...", _ml.COLOR_COMBAT_EVENT)


def handle_defense(ctx) -> None:
    pass


# ---------------------------------------------------------------------------
# Enemy turns
# ---------------------------------------------------------------------------

def run_enemy_turns(ctx, game_map: world.GameMap) -> int:
    from ._ai_ground import run_ground_enemy_turn as _enemy_ai

    _player_dodge = _calc_ground_move_dodge(_state.cells_moved_this_turn)

    _total_dmg = 0
    for _gei in _state.enemies:
        if not _gei.alive or _gei.ap <= 0 or not _gei.weapon_id:
            continue

        _ap_before = _gei.ap
        _new_ap, _dmg, _fired = _enemy_ai(
            ctx,
            enemy_weapon_id=_gei.weapon_id,
            enemy_spec=_gei.spec,
            enemy_ap=_gei.ap,
            player_pos=ctx.player.pos,
            enemy_entity=_gei.entity,
            game_map=game_map,
            armor_defense=_state.armor_defense,
            console=_state.console,
            render_callback=render_frame,
            player_dodge=_player_dodge,
        )
        _ap_spent = _ap_before - _new_ap
        if _fired:
            try:
                _weapon_ap = _find_gw(_gei.weapon_id).ap_cost
            except KeyError:
                _weapon_ap = 1
            _gei.cells_moved_this_turn += max(0, _ap_spent - _weapon_ap)
        else:
            _gei.cells_moved_this_turn += _ap_spent
        _gei.ap = _new_ap

        if _dmg > 0:
            _state.player_hp -= _dmg
            _total_dmg += _dmg
            if _state.player_hp <= 0:
                return 999

    return _total_dmg


def check_reinforcements(ctx, game_map: world.GameMap) -> None:
    pass


# ---------------------------------------------------------------------------
# State sync
# ---------------------------------------------------------------------------

def set_player_ap(ctx, ap: int) -> None:
    _state.player_ap = ap


def reset_turn(ctx) -> None:
    _state.player_ap = _state.player_ap_total
    _state.cells_moved_this_turn = 0
    for _gei in _state.enemies:
        _gei.ap = _gei.ap_total
        _gei.cells_moved_this_turn = 0


def sync_state(ctx) -> None:
    ctx.ground_hp = max(0, _state.player_hp)
    ctx.ground_max_hp = _state.player_max_hp


def get_combat_result() -> CombatResult:
    _cr = CombatResult()
    for _gei in _state.enemies:
        if not _gei.alive and _gei.spec:
            _cr.defeated_names.append(_gei.spec.name)
            _cr.defeated_spec_ids.append(_gei.spec.id)
    return _cr
