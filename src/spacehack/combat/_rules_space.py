"""Space combat rules — flavor module for the unified combat loop.

All state and behavior that differs between space and ground combat
lives here. The unified loop in :mod:`._loop` calls these functions
by name — same call shape whether the rules module is
``_rules_space`` or ``_rules_ground``.

**Combat session state** is encapsulated in :class:`SpaceCombatState`,
a single module-level dataclass replacing the old scattered globals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .. import world
from .. import hud as _hud
from .. import message_log as _ml
from ..engine import RNG, SCREEN_WIDTH, SCREEN_HEIGHT

from ._types import EnemyInstance, CombatResult
from ._stats import (
    init_combat_state,
    calc_hit_chance as _space_hit_chance,
    _calc_dodge_bonus,
    _distance,
)
from ._actions import (
    start_player_turn,
    move_entity,
    resolve_damage,
    can_afford_action as _space_can_afford,
    _sync_back_hull,
    _remove_dead_entity,
    _spawn_loot_drops,
)
from ._animations import (
    _animate_laser_shot,
    _animate_explosion,
    _has_los,
    _paint_target_highlight,
    _paint_range_line,
)


# ---------------------------------------------------------------------------
# SpaceCombatState — all session state in one place
# ---------------------------------------------------------------------------

@dataclass
class SpaceCombatState:
    """Encapsulates all mutable state for one space combat encounter."""

    ctx: Any
    console: Any
    game_map: Any
    log: Any
    player_state: dict = field(default_factory=dict)
    enemy_insts: list[EnemyInstance] = field(default_factory=list)
    enemy_specs: list = field(default_factory=list)
    enemy_ents: dict[int, Any] = field(default_factory=dict)
    player_ent: Any = None
    weapons_list: list[str] = field(default_factory=list)
    active_weapons: list[bool] = field(default_factory=list)
    target_idx: int = 0
    view_w: int = 80
    view_h: int = 54
    cr: CombatResult | None = None


_state: SpaceCombatState | None = None


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

def init(
    ctx,
    console,
    player_ship_catalog,
    player_owned_ship,
    player_pos: world.Position,
    player_pilot_skills,
    enemy_specs: list,
    enemy_positions: list[world.Position],
    game_map: world.GameMap,
    log,
) -> None:
    """Set up combat session state for a space combat encounter."""
    global _state

    if not enemy_specs or not enemy_positions:
        return

    _enemy_insts: list[EnemyInstance] = []
    _enemy_specs = list(enemy_specs)
    _player_state: dict = {}

    for _i in range(len(enemy_specs)):
        if _i == 0:
            _ps, _ei = init_combat_state(
                player_ship_catalog, player_owned_ship,
                player_pos, player_pilot_skills,
                enemy_specs[_i], enemy_positions[_i],
            )
            _player_state = _ps
        else:
            _, _ei = init_combat_state(
                player_ship_catalog, player_owned_ship,
                player_pos, player_pilot_skills,
                enemy_specs[_i], enemy_positions[_i],
            )
        _enemy_insts.append(_ei)

    _weapons_list = list(getattr(player_owned_ship, 'weapons', ()) or ())
    _active_weapons = [True] * max(1, len(_weapons_list))

    _player_ent = None
    for _e in game_map.entities:
        if getattr(_e, 'owned', False):
            _player_ent = _e
            break

    _enemy_ents: dict[int, Any] = {}
    _matched: set[int] = set()
    for _i, _inst in enumerate(_enemy_insts):
        for _e in game_map.entities:
            if _e is _player_ent or getattr(_e, 'owned', False):
                continue
            if id(_e) in _matched:
                continue
            if _e.pos.x == _inst.pos.x and _e.pos.y == _inst.pos.y:
                _enemy_ents[_i] = _e
                _matched.add(id(_e))
                break
        _ent = _enemy_ents.get(_i)
        if _ent is not None and getattr(_ent, 'name', ''):
            _inst.name = _ent.name

    # Deduplicate overlapping positions
    _occupied: set[tuple[int, int]] = set()
    for _inst in _enemy_insts:
        _key = (_inst.pos.x, _inst.pos.y)
        if _key in _occupied:
            _placed = False
            for _odx, _ody in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(1,-1),(-1,1),(1,1)]:
                _nk = (_inst.pos.x + _odx, _inst.pos.y + _ody)
                if _nk not in _occupied and game_map.in_bounds(*_nk) and game_map.is_walkable(*_nk):
                    _inst.pos = world.Position(*_nk)
                    _occupied.add(_nk)
                    _placed = True
                    break
            if not _placed:
                _inst.pos = world.Position(_inst.pos.x + 2, _inst.pos.y)
                _attempts = 0
                while (_inst.pos.x, _inst.pos.y) in _occupied and _attempts < 20:
                    _nx = _inst.pos.x + 1
                    if not game_map.in_bounds(_nx, _inst.pos.y):
                        break
                    _inst.pos = world.Position(_nx, _inst.pos.y)
                    _attempts += 1
                _occupied.add((_inst.pos.x, _inst.pos.y))
        else:
            _occupied.add(_key)

    for _i, _ent in _enemy_ents.items():
        if _i < len(_enemy_insts):
            _ent.pos = _enemy_insts[_i].pos

    _cr = CombatResult()
    start_player_turn(_player_state)

    _state = SpaceCombatState(
        ctx=ctx, console=console, game_map=game_map, log=log,
        player_state=_player_state,
        enemy_insts=_enemy_insts, enemy_specs=_enemy_specs,
        enemy_ents=_enemy_ents, player_ent=_player_ent,
        weapons_list=_weapons_list, active_weapons=_active_weapons,
        cr=_cr,
    )


# ---------------------------------------------------------------------------
# State accessors
# ---------------------------------------------------------------------------

def player_hp(ctx) -> int:
    return _state.player_state.get("hull", 100)


def player_max_hp(ctx) -> int:
    return _state.player_state.get("max_hull", 100)


def player_ap(ctx) -> int:
    return _state.player_state.get("ap_remaining", 0)


def player_ap_total(ctx) -> int:
    return _state.player_state.get("ap_total", 3)


def player_weapons(ctx) -> list[str]:
    return list(_state.weapons_list)


def active_weapons(ctx) -> list[bool]:
    return list(_state.active_weapons)


def set_active_weapons(ctx, active: list[bool]) -> None:
    _state.active_weapons = list(active)


# ---------------------------------------------------------------------------
# Enemy accessors
# ---------------------------------------------------------------------------

def set_target_idx(ctx, idx: int) -> None:
    _state.target_idx = idx


def _alive_target():
    _alive = [e for e in _state.enemy_insts if e.alive]
    if 0 <= _state.target_idx < len(_alive):
        return _alive[_state.target_idx]
    return None


def get_enemies(ctx) -> list[EnemyInstance]:
    return [e for e in _state.enemy_insts if e.alive]


def enemy_pos(enemy: EnemyInstance) -> world.Position:
    return enemy.pos


def enemy_name(enemy: EnemyInstance) -> str:
    return enemy.name


def enemy_hp(enemy: EnemyInstance) -> int:
    return enemy.hull


def enemy_max_hp(enemy: EnemyInstance) -> int:
    return enemy.max_hull


def enemy_alive(enemy: EnemyInstance) -> bool:
    return enemy.alive


# ---------------------------------------------------------------------------
# Combat math
# ---------------------------------------------------------------------------

def hit_chance(weapon_id: str, enemy: EnemyInstance, ctx) -> int:
    _dist = _distance(_state.player_state["pos"], enemy.pos)
    _dodge = _calc_dodge_bonus(
        enemy.cells_moved_this_turn,
        int(enemy.pilot_piloting * 0.5),
    )
    return _space_hit_chance(
        weapon_id, _state.player_state["gunnery"], _dist, _dodge,
    )


def damage(weapon_id: str, enemy: EnemyInstance, ctx) -> int:
    _dmg, _sdmg, _fh, _is_glancing = resolve_damage(
        weapon_id, enemy.hull, enemy.shields,
        target_pilot_piloting=enemy.pilot_piloting,
    )
    enemy.shields = max(0, enemy.shields - _sdmg)
    _prev_hull = enemy.hull
    enemy.hull = _fh
    if _fh <= 0:
        enemy.alive = False
    return _prev_hull - enemy.hull


# ---------------------------------------------------------------------------
# Weapon actions
# ---------------------------------------------------------------------------

def can_fire(weapon_id: str, ctx) -> tuple[bool, str]:
    _ok, _reason = _space_can_afford(_state.player_state, weapon_id)
    if not _ok:
        return _ok, _reason
    _target = _alive_target()
    if _target is not None:
        if not _has_los(
            _state.game_map,
            _state.player_state["pos"].x, _state.player_state["pos"].y,
            _target.pos.x, _target.pos.y,
        ):
            return False, "Blocked by obstacle"
    return True, ""


def weapon_ap_cost(weapon_id: str, ctx) -> int:
    from ..data.weapons import find_weapon as _fw
    return _fw(weapon_id).ap_cost


def weapon_name(weapon_id: str, ctx) -> str:
    from ..data.weapons import find_weapon as _fw
    return _fw(weapon_id).name


def consume_shot(weapon_id: str, ctx) -> None:
    from ..data.weapons import find_weapon as _fw
    _ws = _fw(weapon_id)
    if _ws.slot_type in ("energy", "plasma"):
        _state.player_state["power_pool"] -= _ws.power_cost
    elif _ws.slot_type == "missile":
        old = _state.player_state["weapon_ammo"][weapon_id]
        _state.player_state["weapon_ammo"][weapon_id] = old - _ws.ammo_per_shot


# ---------------------------------------------------------------------------
# Player movement
# ---------------------------------------------------------------------------

def try_move(ctx, game_map: world.GameMap, dx: int, dy: int) -> bool:
    new_pos, ok = move_entity(_state.player_state["pos"], dx, dy, game_map)
    if ok:
        _state.player_state["pos"] = new_pos
        _state.player_state["ap_remaining"] -= 1
        _state.player_state["cells_moved_this_turn"] += 1
        if _state.player_ent is not None:
            _state.player_ent.pos = new_pos
    return ok


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _calc_camera():
    _cw = max(0, _state.game_map.width - _state.view_w)
    _ch = max(0, _state.game_map.height - _state.view_h)
    _cx = max(0, min(_state.player_state["pos"].x - _state.view_w // 2, _cw))
    _cy = max(0, min(_state.player_state["pos"].y - _state.view_h // 2, _ch))
    return _cx, _cy


def render_frame(console, ctx, game_map: world.GameMap) -> None:
    console.clear()
    _cam_x, _cam_y = _calc_camera()
    world.render_world_view(
        console, game_map,
        region_x=0, region_y=0,
        region_w=_state.view_w, region_h=_state.view_h,
        camera_x=_cam_x, camera_y=_cam_y,
    )

    # Range line
    _range_wid = None
    if _state.weapons_list and any(_state.active_weapons):
        from ..data.weapons import find_weapon as _fw
        _active_ids = [
            _state.weapons_list[i] for i in range(len(_state.weapons_list))
            if i < len(_state.active_weapons) and _state.active_weapons[i]
        ]
        if _active_ids:
            _range_wid = min(_active_ids, key=lambda wid: _fw(wid).max_range)
    if _range_wid is not None:
        _tgt = _alive_target()
        if _tgt is not None:
            _los_ok = _has_los(
                _state.game_map,
                _state.player_state["pos"].x, _state.player_state["pos"].y,
                _tgt.pos.x, _tgt.pos.y,
            )
            _paint_range_line(
                console,
                _state.player_state["pos"], _tgt.pos,
                _range_wid,
                _cam_x, _cam_y, _state.view_w, _state.view_h, 0, 0,
                color_override=None if _los_ok else (255, 60, 60),
            )

    _tgt = _alive_target()
    if _tgt is not None:
        _paint_target_highlight(
            console, _cam_x, _cam_y, _state.view_w, _state.view_h, 0, 0, _tgt,
        )

    _hit_chances: dict[str, int] = {}
    _tgt_hc = _alive_target()
    if _state.weapons_list and _tgt_hc is not None:
        _dist = _distance(_state.player_state["pos"], _tgt_hc.pos)
        _target_dodge = _calc_dodge_bonus(
            _tgt_hc.cells_moved_this_turn,
            int(_tgt_hc.pilot_piloting * 0.5),
        )
        for _wid in _state.weapons_list:
            try:
                _hit_chances[_wid] = _space_hit_chance(
                    _wid, _state.player_state["gunnery"], _dist, _target_dodge,
                )
            except KeyError:
                pass

    _evade = _calc_dodge_bonus(
        _state.player_state.get("cells_moved_this_turn", 0),
        int(_state.player_state.get("piloting", 0) * 0.5),
    )

    _hud.render_combat_hud(
        console,
        screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT,
        player_state=_state.player_state,
        enemies=_state.enemy_insts,
        target_idx=_state.target_idx,
        player_mode="DEFAULT",
        active_weapons=_state.active_weapons,
        weapon_list=tuple(_state.weapons_list),
        flee_chance=None,
        hit_chances=_hit_chances,
        evade_bonus=_evade,
        range_weapon_id=_range_wid,
    )
    _ml.render_message_log(
        console, _state.log,
        screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT,
    )


def animate_fire(
    console, ctx, game_map: world.GameMap,
    from_pos: world.Position, to_pos: world.Position, is_hit: bool,
) -> None:
    _cam_x, _cam_y = _calc_camera()

    _hit_chances: dict[str, int] = {}
    _tgt_a = _alive_target()
    if _state.weapons_list and _tgt_a is not None:
        _dist = _distance(_state.player_state["pos"], _tgt_a.pos)
        _target_dodge = _calc_dodge_bonus(
            _tgt_a.cells_moved_this_turn,
            int(_tgt_a.pilot_piloting * 0.5),
        )
        for _wid in _state.weapons_list:
            try:
                _hit_chances[_wid] = _space_hit_chance(
                    _wid, _state.player_state["gunnery"], _dist, _target_dodge,
                )
            except KeyError:
                pass

    _evade = _calc_dodge_bonus(
        _state.player_state.get("cells_moved_this_turn", 0),
        int(_state.player_state.get("piloting", 0) * 0.5),
    )

    _animate_laser_shot(
        console, ctx.context, game_map,
        from_pos, to_pos,
        is_hit=is_hit,
        cam_x=_cam_x, cam_y=_cam_y,
        view_w=_state.view_w, view_h=_state.view_h,
        player_state=_state.player_state,
        enemies=_state.enemy_insts,
        target_idx=_state.target_idx,
        log=_state.log,
        weapon_list=tuple(_state.weapons_list),
        active_weapons=_state.active_weapons,
        evade_bonus=_evade,
        hit_chances=_hit_chances,
        flee_chance=None,
    )


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def on_kill(game_map: world.GameMap, enemy: EnemyInstance, ctx) -> None:
    _dead_ent = None
    for _i, _inst in enumerate(_state.enemy_insts):
        if _inst is enemy:
            if _i in _state.enemy_ents:
                _dead_ent = _state.enemy_ents.pop(_i)
            break
    if _dead_ent is not None and _dead_ent in game_map.entities:
        game_map.entities.remove(_dead_ent)

    _cam_x, _cam_y = _calc_camera()

    _hit_chances: dict[str, int] = {}
    if _state.weapons_list:
        for _wid in _state.weapons_list:
            try:
                _hit_chances[_wid] = hit_chance(_wid, enemy, ctx)
            except (KeyError, ValueError):
                pass

    _evade = _calc_dodge_bonus(
        _state.player_state.get("cells_moved_this_turn", 0),
        int(_state.player_state.get("piloting", 0) * 0.5),
    )
    _animate_explosion(
        _state.console, ctx.context, game_map,
        enemy.pos,
        cam_x=_cam_x, cam_y=_cam_y,
        view_w=_state.view_w, view_h=_state.view_h,
        player_state=_state.player_state,
        enemies=_state.enemy_insts,
        target_idx=_state.target_idx,
        log=_state.log,
        weapon_list=tuple(_state.weapons_list),
        active_weapons=_state.active_weapons,
        evade_bonus=_evade,
        hit_chances=_hit_chances,
        flee_chance=None,
    )

    _correct_spec = next(
        (_sp for _sp in _state.enemy_specs if getattr(_sp, 'id', None) == enemy.spec_id),
        _state.enemy_specs[0] if _state.enemy_specs else None,
    )
    if _correct_spec is not None:
        _spawn_loot_drops(game_map, enemy.pos, _correct_spec)

    from ..data.ships import find_ship as _find_ship_cat
    try:
        _sc = _find_ship_cat(enemy.spec_id)
        from ..xp import add_xp as _add_xp
        _add_xp(ctx, _sc.base_hull * 2)
    except (KeyError, ImportError):
        pass

    if hasattr(ctx, 'player_counters'):
        ctx.player_counters.total_kills += 1

    _state.cr.defeated_names.append(enemy.name)
    _state.cr.defeated_spec_ids.append(enemy.spec_id)
    if _dead_ent is not None:
        _bid = getattr(_dead_ent, 'bounty_spawn_id', None)
        if _bid is not None:
            _state.cr.defeated_bounty_ids.append(_bid)

    if _dead_ent is not None:
        _mid = getattr(_dead_ent, 'procedural_squad_id', None)
        _nid = getattr(_dead_ent, 'npc_ship_id', None)
        if _mid and _nid:
            from .. import solar_system as _ss
            _sys_id = _ss.current_solar_system_id
            _spawns = ctx.procedural_spawns.get(_sys_id, [])
            for _i, _sp in enumerate(_spawns):
                if _sp.squad_id == _mid and _sp.npc_id == _nid:
                    _spawns.pop(_i)
                    break


def on_player_death(ctx) -> None:
    ctx.player_dead = True
    from ._encounter import _render_death_screen
    _render_death_screen(_state.console, ctx.context, _state.log)


# ---------------------------------------------------------------------------
# Defense toggle
# ---------------------------------------------------------------------------

def handle_defense(ctx) -> None:
    max_sh = _state.player_state.get("max_shields", 0)
    if max_sh > 0:
        cur = _state.player_state.get("shield_regen_rate", 0)
        next_rate = (cur + 1) % 11
        _state.player_state["shield_regen_rate"] = next_rate
        if next_rate == 0:
            _state.log.add_colored("Shield regen: OFF", _ml.COLOR_PLAYER_ACTION)
        else:
            _state.log.add_colored(
                f"Shield regen rate: {next_rate}/10", _ml.COLOR_PLAYER_ACTION,
            )
    else:
        _state.log.add_colored("No shields installed.", _ml.COLOR_PLAYER_ACTION)


# ---------------------------------------------------------------------------
# Enemy turns
# ---------------------------------------------------------------------------

def run_enemy_turns(ctx, game_map: world.GameMap) -> int:
    from ._ai import _run_enemy_turn as _enemy_ai

    _hit_chances: dict[str, int] = {}
    _tgt_r = _alive_target()
    if _state.weapons_list and _tgt_r is not None:
        _dist = _distance(_state.player_state["pos"], _tgt_r.pos)
        _target_dodge = _calc_dodge_bonus(
            _tgt_r.cells_moved_this_turn,
            int(_tgt_r.pilot_piloting * 0.5),
        )
        for _wid in _state.weapons_list:
            try:
                _hit_chances[_wid] = _space_hit_chance(
                    _wid, _state.player_state["gunnery"], _dist, _target_dodge,
                )
            except KeyError:
                pass

    _evade = _calc_dodge_bonus(
        _state.player_state.get("cells_moved_this_turn", 0),
        int(_state.player_state.get("piloting", 0) * 0.5),
    )

    _result = _enemy_ai(
        _state,
        hit_chances=_hit_chances,
        evade_bonus=_evade,
        flee_attempts=0,
        calc_cam=_calc_camera,
        ctx=ctx,
    )

    if _result == "DEFEAT":
        return 999
    return 0


# ---------------------------------------------------------------------------
# Reinforcements
# ---------------------------------------------------------------------------

def check_reinforcements(ctx, game_map: world.GameMap) -> None:
    from ..npc_ships import move_npcs as _tick_npcs
    from ..navigation import _detect_combat_encounter as _re_detect
    from .. import solar_system as _ss_module

    _tick_npcs(ctx, game_map)

    for _i, _ent in _state.enemy_ents.items():
        if _i < len(_state.enemy_insts) and _state.enemy_insts[_i].alive:
            _state.enemy_insts[_i].pos = _ent.pos

    _new_encounter = _re_detect(ctx, _state.player_state["pos"], _ss_module.current_system())
    if _new_encounter is None:
        return

    _new_specs, _new_positions = _new_encounter
    _existing_entity_ids = {id(_e) for _e in _state.enemy_ents.values()}

    for _ni, (_ns, _np) in enumerate(zip(_new_specs, _new_positions)):
        _found_entity = None
        for _ge in game_map.entities:
            if getattr(_ge, 'owned', False):
                continue
            if getattr(_ge, 'loot_data', None) is not None:
                continue
            if _ge.pos.x == _np.x and _ge.pos.y == _np.y:
                _found_entity = _ge
                break
        if _found_entity is not None and id(_found_entity) in _existing_entity_ids:
            continue
        _already = any(
            _ei.pos.x == _np.x and _ei.pos.y == _np.y
            for _ei in _state.enemy_insts
        )
        if _already:
            continue

        from ..data.ships import find_ship as _fs
        try:
            _ship_cat = _fs(_state.ctx.player_owned_ship.ship_id)
        except (KeyError, AttributeError):
            continue

        from ..data.pilot_skills import PilotSkills
        _pilot = PilotSkills(
            gunnery=_state.player_state.get("gunnery", 30),
            piloting=_state.player_state.get("piloting", 30),
            engineering=_state.player_state.get("engineering", 30),
        )

        _ps_dummy, _new_ei = init_combat_state(
            _ship_cat, _state.ctx.player_owned_ship,
            _state.player_state["pos"], _pilot,
            _ns, _np,
        )
        _state.enemy_insts.append(_new_ei)
        _state.enemy_specs.append(_ns)
        if _found_entity is not None:
            _state.enemy_ents[len(_state.enemy_insts) - 1] = _found_entity
            if getattr(_found_entity, 'name', ''):
                _new_ei.name = _found_entity.name
        _state.log.add_colored(
            f"{getattr(_found_entity, 'name', '') or _ns.name} joins the fight!",
            _ml.COLOR_COMBAT_EVENT,
        )


# ---------------------------------------------------------------------------
# State sync
# ---------------------------------------------------------------------------

def set_player_ap(ctx, ap: int) -> None:
    _state.player_state["ap_remaining"] = ap


def reset_turn(ctx) -> None:
    start_player_turn(_state.player_state)


def sync_state(ctx) -> None:
    _sync_back_hull(_state.player_state, ctx.player_owned_ship)


def get_combat_result() -> CombatResult:
    return _state.cr
