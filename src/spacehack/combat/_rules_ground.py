"""Ground combat rules — flavor module for the unified combat loop.

All state and behavior specific to on-foot ground combat lives here.
The unified loop in :mod:`._loop` calls these functions by name —
same call shape as :mod:`._rules_space`.

**Module-level state** is scoped to a single combat encounter.
Initialised by :func:`init`, read by all accessors.

Supports multi-enemy squads — :class:`GroundEnemyInstance` tracks
per-enemy HP, AP, spec, and weapon state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .. import world
from .. import message_log as _ml
from ..engine import RNG, SCREEN_WIDTH, SCREEN_HEIGHT
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
    """Per-enemy combat state.  Lightweight dataclass replacing the old
    singleton globals (``_enemy_hp``, ``_enemy_ap``, etc.)."""

    entity: world.Entity           # the map entity (position, char, etc.)
    spec: Any                      # NpcCharSpec
    weapon_id: str                 # active weapon id (empty if none)
    hp: int = 30
    max_hp: int = 30
    ap: int = 4
    ap_total: int = 4

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
# Module-level combat session state
# ---------------------------------------------------------------------------

_enemies: list[GroundEnemyInstance] = []

_player_hp: int = 30
_player_max_hp: int = 30
_player_ap: int = 4
_player_ap_total: int = 4
_armor_defense: int = 0
_active_weapon_list: list[bool] = []

_target_idx: int = 0  # synced from unified loop via set_target_idx()

_ctx: Any = None
_console: Any = None
_game_map: world.GameMap | None = None

# Rendering constants
_RENDER_WIDTH: int = SCREEN_WIDTH - 25
_RENDER_HEIGHT: int = SCREEN_HEIGHT - 6


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

def init(ctx, enemy_entities: list[world.Entity], game_map: world.GameMap) -> None:
    """Set up module-level state for a ground combat encounter.

    ``enemy_entities`` is a list of :class:`world.Entity` objects with
    ``npc_char_id`` set — typically all squad members within detection
    range.  Single-enemy calls pass a one-element list.
    """
    global _enemies, _target_idx
    global _player_hp, _player_max_hp, _player_ap_total
    global _armor_defense, _active_weapon_list, _ctx, _console, _game_map

    _ctx = ctx
    _console = None
    _game_map = game_map
    _target_idx = 0
    _enemies = []

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
            entity=_ent,
            spec=_spec,
            weapon_id=_wid,
            hp=_max_hp,
            max_hp=_max_hp,
            ap=4,
            ap_total=4,
        ))

    # Player stats
    _player_ap = 4
    _player_ap_total = 4
    _player_max_hp = 20 + ctx.ground_stats.stamina * 2
    _hp_delta = _player_max_hp - ctx.ground_max_hp
    if _hp_delta > 0:
        ctx.ground_hp += _hp_delta
    _player_hp = min(ctx.ground_hp, _player_max_hp)

    # Armor
    _armor_defense = 0
    for _slot, _aid in ctx.equipped_ground_armor.items():
        if _aid:
            try:
                _armor = _find_ga(_aid)
                _armor_defense += _armor.defense
            except KeyError:
                pass

    # Weapons
    _weapons = list(ctx.equipped_ground_weapons)
    if not _weapons:
        _weapons = ["fists"]
    _active_weapon_list = [True] * len(_weapons)

    _names = ", ".join(_e.name for _e in _enemies)
    ctx.log.add_colored(
        f"Combat starts! {_names} engage!",
        _ml.COLOR_COMBAT_EVENT,
    )


# ---------------------------------------------------------------------------
# State accessors
# ---------------------------------------------------------------------------

def player_hp(ctx) -> int:
    return _player_hp


def player_max_hp(ctx) -> int:
    return _player_max_hp


def player_ap(ctx) -> int:
    return _player_ap


def player_ap_total(ctx) -> int:
    return _player_ap_total


def player_weapons(ctx) -> list[str]:
    _w = list(ctx.equipped_ground_weapons)
    return _w if _w else ["fists"]


def active_weapons(ctx) -> list[bool]:
    return list(_active_weapon_list)


def set_active_weapons(ctx, active: list[bool]) -> None:
    global _active_weapon_list
    _active_weapon_list = list(active)


# ---------------------------------------------------------------------------
# Enemy accessors
# ---------------------------------------------------------------------------

def set_target_idx(ctx, idx: int) -> None:
    """Sync target index from the unified loop."""
    global _target_idx
    _target_idx = idx


def get_enemies(ctx) -> list[GroundEnemyInstance]:
    return [e for e in _enemies if e.alive]


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
) -> int:
    """Pure hit-chance formula — used by AI which doesn't go through ctx."""
    _ws = _find_gw(weapon_id)
    _dodge = target_reflexes * 2
    _chance = _ws.accuracy + attacker_reflexes * 3 - _dodge
    return max(5, min(95, _chance))


def _ground_damage_raw(
    weapon_id: str,
    strength: int,
    armor_defense: int,
) -> int:
    """Pure damage formula — used by AI which doesn't go through ctx."""
    _ws = _find_gw(weapon_id)
    _str_bonus = strength // 4 if _ws.damage_type == 'melee' else 0
    _raw = _ws.damage + _str_bonus
    return max(1, _raw - armor_defense)


def hit_chance(weapon_id: str, enemy: GroundEnemyInstance, ctx) -> int:
    _dodge = (enemy.spec.reflexes if enemy.spec else 10) * 2
    return _ground_hit_chance_raw(weapon_id, ctx.ground_stats.reflexes, _dodge // 2)


def damage(weapon_id: str, enemy: GroundEnemyInstance, ctx) -> int:
    """Apply damage to enemy. Returns damage dealt (for log)."""
    _ws = _find_gw(weapon_id)
    _str_bonus = ctx.ground_stats.strength // 4 if _ws.damage_type == 'melee' else 0
    _raw = _ws.damage + _str_bonus
    _dmg = max(1, _raw)
    enemy.hp -= _dmg
    return _dmg


# ---------------------------------------------------------------------------
# Weapon actions
# ---------------------------------------------------------------------------

def can_fire(weapon_id: str, ctx) -> tuple[bool, str]:
    _ws = _find_gw(weapon_id)
    _alive = get_enemies(ctx)
    if _target_idx >= len(_alive):
        return False, "No valid target"
    _target = _alive[_target_idx]
    _dist = int(_distance(ctx.player.pos, _target.pos))
    if _dist > _ws.max_range or _dist < _ws.min_range:
        return False, f"Out of range ({_dist}u, need {_ws.min_range}-{_ws.max_range})"
    if _player_ap < _ws.ap_cost:
        return False, f"Need {_ws.ap_cost} AP (have {_player_ap})"
    if _game_map is not None:
        if not _has_los(
            _game_map,
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
    """Ground weapons have no ammo — no-op."""
    pass


# ---------------------------------------------------------------------------
# Player movement
# ---------------------------------------------------------------------------

def try_move(ctx, game_map: world.GameMap, dx: int, dy: int) -> bool:
    global _player_ap
    _nx = ctx.player.pos.x + dx
    _ny = ctx.player.pos.y + dy
    if not game_map.is_walkable(_nx, _ny):
        return False
    _blocker = game_map.entity_at(_nx, _ny, exclude=ctx.player)
    if _blocker is not None:
        # Only block if the entity is an enemy in this combat
        _enemy_ids = {id(_e.entity) for _e in _enemies if _e.alive}
        if id(_blocker) not in _enemy_ids:
            return False
    ctx.player.pos = world.Position(_nx, _ny)
    _player_ap -= 1
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
_COLOR_VALUE_DIM: tuple[int, int, int] = (150, 150, 150)


def _ground_offsets(game_map: world.GameMap) -> tuple[int, int]:
    _ox = (_RENDER_WIDTH - game_map.width) // 2
    _oy = (_RENDER_HEIGHT - game_map.height) // 2
    return (_ox, _oy)


def _ground_range_line(console, player_pos, target_pos, weapon_id, ox, oy, *, color_override=None):
    try:
        _ws = _find_gw(weapon_id)
    except KeyError:
        return
    _draw_range_colored_line(
        console,
        player_pos, target_pos,
        _ws.max_range, _ws.min_range,
        0, 0, _RENDER_WIDTH, _RENDER_HEIGHT,
        region_x=ox, region_y=oy,
        color_override=color_override,
    )


def render_frame(console, ctx, game_map: world.GameMap) -> None:
    """Draw the full ground combat view: dungeon map + HUD + message log."""
    console.clear()
    _ox, _oy = _ground_offsets(game_map)
    world.render_world(
        console, game_map,
        region_x=0, region_y=0,
        region_w=_RENDER_WIDTH, region_h=_RENDER_HEIGHT,
    )

    # Target highlight — paint the currently targeted alive enemy
    _alive = get_enemies(ctx)
    if _target_idx < len(_alive):
        _paint_target_highlight(
            console, 0, 0, _RENDER_WIDTH, _RENDER_HEIGHT,
            _ox, _oy,
            _alive[_target_idx].entity,
        )

    # Range line — draw from player to current target
    _weapons = list(ctx.equipped_ground_weapons)
    if not _weapons:
        _weapons = ["fists"]
    _active_w = [
        _weapons[i] for i in range(len(_weapons))
        if i < len(_active_weapon_list) and _active_weapon_list[i]
    ]
    if _active_w and _target_idx < len(_alive):
        _tgt = _alive[_target_idx]
        _los_blocked = (
            _game_map is not None
            and not _has_los(
                _game_map,
                ctx.player.pos.x, ctx.player.pos.y,
                _tgt.pos.x, _tgt.pos.y,
            )
        )
        _ground_range_line(
            console, ctx.player.pos, _tgt.pos,
            _active_w[0], _ox, _oy,
            color_override=(255, 60, 60) if _los_blocked else None,
        )

    # HUD
    _hud_x = SCREEN_WIDTH - 25
    y = 0
    console.print(x=_hud_x, y=y, string="> GROUND COMBAT <", fg=_COLOR_GROUND_TITLE)
    y += 2

    # Player block
    console.print(x=_hud_x, y=y, string="PLAYER", fg=_COLOR_GROUND_PLAYER)
    y += 1
    _hp_bar = _bar_str(_player_hp, _player_max_hp, width=8)
    _hp_pct = _player_hp * 100 // max(_player_max_hp, 1)
    console.print(x=_hud_x, y=y, string=f"HP  {_hp_bar} {_hp_pct}%", fg=_COLOR_GROUND_PLAYER)
    y += 1
    console.print(x=_hud_x, y=y, string=f"AP: {_player_ap}/{_player_ap_total}", fg=_COLOR_GROUND_ACTION)
    y += 2

    # Weapons
    if _weapons:
        console.print(x=_hud_x, y=y, string="WEAPONS", fg=_COLOR_GROUND_TITLE)
        y += 1
        for _i, _wid in enumerate(_weapons):
            try:
                _ws = _find_gw(_wid)
            except KeyError:
                continue
            _is_active = _active_weapon_list[_i] if _i < len(_active_weapon_list) else True
            _sel = "[x]" if _is_active else "[ ]"
            _name_fg = _COLOR_GROUND_WEAPON if _is_active else _COLOR_GROUND_WEAPON_DIM
            console.print(x=_hud_x, y=y, string=f"{_sel}[{_i+1}] {_ws.name}"[:24], fg=_name_fg)
            y += 1
            _hc = hit_chance(_wid, _alive[_target_idx], ctx) if _target_idx < len(_alive) else 0
            console.print(x=_hud_x, y=y, string=f"     DMG {_ws.damage} HIT {_hc}%", fg=_COLOR_VALUE_DIM)
            y += 1
            _rng = f"{_ws.min_range}-{_ws.max_range}" if _ws.min_range > 0 else f"0-{_ws.max_range}"
            console.print(x=_hud_x, y=y, string=f"     RNG {_rng} AP {_ws.ap_cost}", fg=_COLOR_VALUE_DIM)
            y += 1
        y += 1

    # Enemy block — alive enemies only (dead removed, matches space combat UX)
    _alive_enemies = [e for e in _enemies if e.alive]
    if _alive_enemies:
        console.print(x=_hud_x, y=y, string="ENEMIES", fg=_COLOR_GROUND_TITLE)
        y += 1
        for _i, _gei in enumerate(_alive_enemies):
            _is_target = _i == _target_idx
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

    # Actions
    console.print(x=_hud_x, y=y, string="ACTIONS", fg=_COLOR_GROUND_TITLE)
    y += 1
    _actions = [
        ("[Tab]", "Target"), ("[m]", "Move"), ("[f]", "Fire"),
        ("[w]", "Wait"),
    ]
    if len(_weapons) > 1:
        _actions.insert(3, (f"[1-{len(_weapons)}]", "Toggle Wpn"))
    for key, desc in _actions:
        console.print(x=_hud_x, y=y, string=f"{key} {desc}", fg=_COLOR_GROUND_ACTION)
        y += 1

    _ml.render_message_log(
        console, ctx.log,
        screen_width=SCREEN_WIDTH,
        screen_height=SCREEN_HEIGHT,
    )


# ---------------------------------------------------------------------------
# Animation
# ---------------------------------------------------------------------------

def animate_fire(
    console, ctx, game_map: world.GameMap,
    from_pos: world.Position, to_pos: world.Position, is_hit: bool,
) -> None:
    """Animate a ground weapon shot (laser beam)."""
    _ox, _oy = _ground_offsets(game_map)
    cells = list(_bresenham_line(from_pos.x, from_pos.y, to_pos.x, to_pos.y))
    if not cells or cells[-1] != (to_pos.x, to_pos.y):
        cells.append((to_pos.x, to_pos.y))

    for frame in range(4):
        render_frame(console, ctx, game_map)
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
    """Handle enemy death: remove entity, drop loot, award XP."""
    _ent = enemy.entity
    if _ent is not None and _ent in game_map.entities:
        game_map.entities.remove(_ent)

    # Loot drop
    if enemy.spec and enemy.spec.loot_pool:
        _min, _max = enemy.spec.loot_count
        _shared_loot(
            game_map, _ent.pos,
            enemy.spec.loot_pool,
            count_range=(_min, _max),
            qty_range=(1, 2),
        )

    # XP
    if enemy.spec:
        from ..xp import add_xp as _add_xp
        _add_xp(ctx, enemy.spec.xp_reward)
        if hasattr(ctx, 'player_counters'):
            ctx.player_counters.total_kills += 1

    enemy.hp = 0


def on_player_death(ctx) -> None:
    """Mark player dead — main loop returns to title."""
    ctx.player_dead = True
    ctx.log.add_colored("You collapse from your wounds...", _ml.COLOR_COMBAT_EVENT)


# ---------------------------------------------------------------------------
# Defense toggle — no-op for ground (armor is passive)
# ---------------------------------------------------------------------------

def handle_defense(ctx) -> None:
    """Ground combat has no active defense toggle."""
    pass


# ---------------------------------------------------------------------------
# Enemy turns
# ---------------------------------------------------------------------------

def run_enemy_turns(ctx, game_map: world.GameMap) -> int:
    """Execute AI turns for all alive enemies. Returns total damage to player."""
    global _player_hp
    from ._ai_ground import run_ground_enemy_turn as _enemy_ai

    _total_dmg = 0
    for _gei in _enemies:
        if not _gei.alive or _gei.ap <= 0 or not _gei.weapon_id:
            continue

        _new_ap, _dmg, _fired = _enemy_ai(
            ctx,
            enemy_weapon_id=_gei.weapon_id,
            enemy_spec=_gei.spec,
            enemy_ap=_gei.ap,
            player_pos=ctx.player.pos,
            enemy_entity=_gei.entity,
            game_map=game_map,
            armor_defense=_armor_defense,
            console=_console,
            render_callback=render_frame,
        )
        _gei.ap = _new_ap

        if _dmg > 0:
            _player_hp -= _dmg
            _total_dmg += _dmg
            if _player_hp <= 0:
                return 999

    return _total_dmg


# ---------------------------------------------------------------------------
# Reinforcements — no-op for ground
# ---------------------------------------------------------------------------

def check_reinforcements(ctx, game_map: world.GameMap) -> None:
    """Ground combat has no mid-fight reinforcements."""
    pass


# ---------------------------------------------------------------------------
# State sync
# ---------------------------------------------------------------------------

def set_player_ap(ctx, ap: int) -> None:
    global _player_ap
    _player_ap = ap


def reset_turn(ctx) -> None:
    """Reset player and all enemy AP for a new turn."""
    global _player_ap
    _player_ap = _player_ap_total
    for _gei in _enemies:
        _gei.ap = _gei.ap_total


def sync_state(ctx) -> None:
    """Persist ground HP back to ctx."""
    ctx.ground_hp = max(0, _player_hp)
    ctx.ground_max_hp = _player_max_hp


def get_combat_result() -> CombatResult:
    _cr = CombatResult()
    for _gei in _enemies:
        if not _gei.alive and _gei.spec:
            _cr.defeated_names.append(_gei.spec.name)
            _cr.defeated_spec_ids.append(_gei.spec.id)
    return _cr
