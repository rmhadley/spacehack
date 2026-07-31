"""Space combat rules — flavor module for the unified combat loop.

All state and behavior that differs between space and ground combat
lives here. The unified loop in :mod:`._loop` calls these functions
by name — same call shape whether the rules module is
``_rules_space`` or ``_rules_ground``.

**Module-level state** is scoped to a single combat encounter:
initialised by :func:`init`, read by all accessors, cleared when
combat ends. This is NOT game-session state — it's combat-session
state that lives for the duration of one :func:`run_combat` call.
"""

from __future__ import annotations

from typing import Any

from .. import world
from .. import hud as _hud
from .. import message_log as _ml
from ..engine import RNG, SCREEN_WIDTH, SCREEN_HEIGHT

from ._types import EnemyInstance, CombatResult
from ._stats import (
    init_combat_state,
    calc_hit_chance as _space_hit_chance,
    calc_flee_chance as _space_flee_chance,
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
    _paint_target_highlight,
    _paint_range_line,
    _resolve_target,
)


# ---------------------------------------------------------------------------
# Module-level combat session state (scoped to one encounter)
# ---------------------------------------------------------------------------

_player_state: dict = {}
_enemy_insts: list[EnemyInstance] = []
_enemy_specs: list = []
_enemy_ents: dict[int, Any] = {}
_player_ent: Any = None
_weapons_list: list[str] = []
_active_weapons: list[bool] = []
_target_idx: int = 0
_view_w: int = 80
_view_h: int = 54
_ctx: Any = None
_console: Any = None
_game_map: Any = None
_log: Any = None
_flee_attempts: int = 0
_cr: CombatResult | None = None


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
    """Set up module-level state for a space combat encounter."""
    global _player_state, _enemy_insts, _enemy_specs, _enemy_ents
    global _player_ent, _weapons_list, _active_weapons, _target_idx
    global _view_w, _view_h, _ctx, _console, _game_map, _log
    global _flee_attempts, _cr

    _ctx = ctx
    _console = console
    _game_map = game_map
    _log = log
    _flee_attempts = 0
    _target_idx = 0
    _view_w = 80
    _view_h = 54

    if not enemy_specs or not enemy_positions:
        return

    # Build initial combat state(s)
    _enemy_insts = []
    _enemy_specs = list(enemy_specs)
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

    # Weapons
    _weapons_list = list(getattr(player_owned_ship, 'weapons', ()) or ())
    _active_weapons = [True] * max(1, len(_weapons_list))

    # Find player entity on map
    _player_ent = None
    for _e in game_map.entities:
        if getattr(_e, 'owned', False):
            _player_ent = _e
            break

    # Build enemy-entity mapping
    _enemy_ents = {}
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

    _cr = CombatResult()
    start_player_turn(_player_state)


# ---------------------------------------------------------------------------
# State accessors
# ---------------------------------------------------------------------------

def player_hp(ctx) -> int:
    return _player_state.get("hull", 100)


def player_max_hp(ctx) -> int:
    return _player_state.get("max_hull", 100)


def player_ap(ctx) -> int:
    return _player_state.get("ap_remaining", 0)


def player_ap_total(ctx) -> int:
    return _player_state.get("ap_total", 3)


def player_weapons(ctx) -> list[str]:
    return list(_weapons_list)


def active_weapons(ctx) -> list[bool]:
    return list(_active_weapons)


def set_active_weapons(ctx, active: list[bool]) -> None:
    global _active_weapons
    _active_weapons = list(active)


# ---------------------------------------------------------------------------
# Enemy accessors
# ---------------------------------------------------------------------------

def get_enemies(ctx) -> list[EnemyInstance]:
    return [e for e in _enemy_insts if e.alive]


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
    _dist = _distance(_player_state["pos"], enemy.pos)
    _dodge = _calc_dodge_bonus(
        enemy.cells_moved_this_turn,
        int(enemy.pilot_piloting * 0.5),
    )
    return _space_hit_chance(
        weapon_id, _player_state["gunnery"], _dist, _dodge,
    )


def damage(weapon_id: str, enemy: EnemyInstance, ctx) -> int:
    """Apply damage to enemy. Returns hull damage dealt (for log)."""
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


def flee_chance(ctx) -> int:
    _alive = [e for e in _enemy_insts if e.alive]
    if not _alive:
        return 95
    _closest = min(_alive, key=lambda e: _distance(_player_state["pos"], e.pos))
    return _space_flee_chance(
        _player_state["piloting"],
        _closest.pilot_piloting,
        _player_state["hull"] / max(_player_state["max_hull"], 1),
        _distance(_player_state["pos"], _closest.pos),
        _flee_attempts,
    )


# ---------------------------------------------------------------------------
# Weapon actions
# ---------------------------------------------------------------------------

def can_fire(weapon_id: str, ctx) -> tuple[bool, str]:
    return _space_can_afford(_player_state, weapon_id)


def consume_shot(weapon_id: str, ctx) -> None:
    """Deduct AP, power, and/or ammo for firing weapon_id."""
    from ..data.weapons import find_weapon as _fw
    _ws = _fw(weapon_id)
    _player_state["ap_remaining"] -= _ws.ap_cost
    if _ws.slot_type in ("energy", "plasma"):
        _player_state["power_pool"] -= _ws.power_cost
    elif _ws.slot_type == "missile":
        old = _player_state["weapon_ammo"][weapon_id]
        _player_state["weapon_ammo"][weapon_id] = old - _ws.ammo_per_shot


# ---------------------------------------------------------------------------
# Player movement
# ---------------------------------------------------------------------------

def try_move(ctx, game_map: world.GameMap, dx: int, dy: int) -> bool:
    """Try to move the player. Returns True if moved, False if blocked."""
    new_pos, ok = move_entity(_player_state["pos"], dx, dy, game_map)
    if ok:
        _player_state["pos"] = new_pos
        _player_state["ap_remaining"] -= 1
        _player_state["cells_moved_this_turn"] += 1
        # Sync entity position
        if _player_ent is not None:
            _player_ent.pos = new_pos
    return ok


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _calc_camera():
    """Compute camera centred on player for the scrolling viewport."""
    _cw = max(0, _game_map.width - _view_w)
    _ch = max(0, _game_map.height - _view_h)
    _cx = max(0, min(_player_state["pos"].x - _view_w // 2, _cw))
    _cy = max(0, min(_player_state["pos"].y - _view_h // 2, _ch))
    return _cx, _cy


def render_frame(console, ctx, game_map: world.GameMap) -> None:
    """Draw the full space combat view: scrolling map + HUD + message log."""
    _cam_x, _cam_y = _calc_camera()
    world.render_world_view(
        console, game_map,
        region_x=0, region_y=0,
        region_w=_view_w, region_h=_view_h,
        camera_x=_cam_x, camera_y=_cam_y,
    )

    # Range line
    _range_wid = None
    if _weapons_list and any(_active_weapons):
        from ..data.weapons import find_weapon as _fw
        _active_ids = [
            _weapons_list[i] for i in range(len(_weapons_list))
            if i < len(_active_weapons) and _active_weapons[i]
        ]
        if _active_ids:
            _range_wid = min(_active_ids, key=lambda wid: _fw(wid).max_range)
    if _range_wid is not None:
        _tgt = _resolve_target(_enemy_insts, _target_idx)
        if _tgt is not None:
            _paint_range_line(
                console,
                _player_state["pos"], _tgt.pos,
                _range_wid,
                _cam_x, _cam_y, _view_w, _view_h, 0, 0,
            )

    # Target highlight
    _tgt = _resolve_target(_enemy_insts, _target_idx)
    if _tgt is not None:
        _paint_target_highlight(
            console, _cam_x, _cam_y, _view_w, _view_h, 0, 0, _tgt,
        )

    # Compute hit chances for HUD
    _hit_chances: dict[str, int] = {}
    if _weapons_list and _target_idx < len(_enemy_insts):
        _target_e = _enemy_insts[_target_idx]
        _dist = _distance(_player_state["pos"], _target_e.pos)
        _target_dodge = _calc_dodge_bonus(
            _target_e.cells_moved_this_turn,
            int(_target_e.pilot_piloting * 0.5),
        )
        for _wid in _weapons_list:
            try:
                _hit_chances[_wid] = _space_hit_chance(
                    _wid, _player_state["gunnery"], _dist, _target_dodge,
                )
            except KeyError:
                pass

    # Evade bonus
    _evade = _calc_dodge_bonus(
        _player_state.get("cells_moved_this_turn", 0),
        int(_player_state.get("piloting", 0) * 0.5),
    )

    # Closest enemy for flee
    _alive = [e for e in _enemy_insts if e.alive]
    _closest = min(_alive, key=lambda e: _distance(_player_state["pos"], e.pos))
    _fc = _space_flee_chance(
        _player_state["piloting"],
        _closest.pilot_piloting,
        _player_state["hull"] / max(_player_state["max_hull"], 1),
        _distance(_player_state["pos"], _closest.pos),
        _flee_attempts,
    )

    _hud.render_combat_hud(
        console,
        screen_width=SCREEN_WIDTH,
        screen_height=SCREEN_HEIGHT,
        player_state=_player_state,
        enemies=_enemy_insts,
        target_idx=_target_idx,
        player_mode="DEFAULT",
        active_weapons=_active_weapons,
        weapon_list=tuple(_weapons_list),
        flee_chance=_fc,
        hit_chances=_hit_chances,
        evade_bonus=_evade,
        range_weapon_id=_range_wid,
    )
    _ml.render_message_log(
        console, _log,
        screen_width=SCREEN_WIDTH,
        screen_height=SCREEN_HEIGHT,
    )


def animate_fire(
    console, ctx, game_map: world.GameMap,
    from_pos: world.Position, to_pos: world.Position, is_hit: bool,
) -> None:
    """Animate a laser shot from from_pos to to_pos."""
    _cam_x, _cam_y = _calc_camera()

    # Compute HUD state for animation frames
    _hit_chances: dict[str, int] = {}
    if _weapons_list and _target_idx < len(_enemy_insts):
        _target_e = _enemy_insts[_target_idx]
        _dist = _distance(_player_state["pos"], _target_e.pos)
        _target_dodge = _calc_dodge_bonus(
            _target_e.cells_moved_this_turn,
            int(_target_e.pilot_piloting * 0.5),
        )
        for _wid in _weapons_list:
            try:
                _hit_chances[_wid] = _space_hit_chance(
                    _wid, _player_state["gunnery"], _dist, _target_dodge,
                )
            except KeyError:
                pass

    _evade = _calc_dodge_bonus(
        _player_state.get("cells_moved_this_turn", 0),
        int(_player_state.get("piloting", 0) * 0.5),
    )

    _alive = [e for e in _enemy_insts if e.alive]
    _closest = min(_alive, key=lambda e: _distance(_player_state["pos"], e.pos))
    _fc = _space_flee_chance(
        _player_state["piloting"],
        _closest.pilot_piloting,
        _player_state["hull"] / max(_player_state["max_hull"], 1),
        _distance(_player_state["pos"], _closest.pos),
        _flee_attempts,
    )

    _animate_laser_shot(
        console, ctx.context, game_map,
        from_pos, to_pos,
        is_hit=is_hit,
        cam_x=_cam_x, cam_y=_cam_y,
        view_w=_view_w, view_h=_view_h,
        player_state=_player_state,
        enemies=_enemy_insts,
        target_idx=_target_idx,
        log=_log,
        weapon_list=tuple(_weapons_list),
        active_weapons=_active_weapons,
        evade_bonus=_evade,
        hit_chances=_hit_chances,
        flee_chance=_fc,
    )


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def on_kill(game_map: world.GameMap, enemy: EnemyInstance, ctx) -> None:
    """Handle enemy death: remove entity, explosion, loot, XP, counters."""
    # Find entity by matching enemy instance
    _dead_ent = None
    for _i, _inst in enumerate(_enemy_insts):
        if _inst is enemy:
            if _i in _enemy_ents:
                _dead_ent = _enemy_ents.pop(_i)
            break
    if _dead_ent is not None and _dead_ent in game_map.entities:
        game_map.entities.remove(_dead_ent)

    # Explosion animation
    _cam_x, _cam_y = _calc_camera()

    # HUD params for explosion animation frames
    _hit_chances: dict[str, int] = {}
    if _weapons_list:
        for _wid in _weapons_list:
            try:
                _hit_chances[_wid] = hit_chance(_wid, enemy, ctx)
            except (KeyError, ValueError):
                pass

    _evade = _calc_dodge_bonus(
        _player_state.get("cells_moved_this_turn", 0),
        int(_player_state.get("piloting", 0) * 0.5),
    )
    _alive_all = [e for e in _enemy_insts if e.alive]
    _fc = 50
    if _alive_all:
        _closest = min(_alive_all, key=lambda e: _distance(_player_state["pos"], e.pos))
        _fc = _space_flee_chance(
            _player_state["piloting"],
            _closest.pilot_piloting,
            _player_state["hull"] / max(_player_state["max_hull"], 1),
            _distance(_player_state["pos"], _closest.pos),
            _flee_attempts,
        )

    _animate_explosion(
        _console, ctx.context, game_map,
        enemy.pos,
        cam_x=_cam_x, cam_y=_cam_y,
        view_w=_view_w, view_h=_view_h,
        player_state=_player_state,
        enemies=_enemy_insts,
        target_idx=_target_idx,
        log=_log,
        weapon_list=tuple(_weapons_list),
        active_weapons=_active_weapons,
        evade_bonus=_evade,
        hit_chances=_hit_chances,
        flee_chance=_fc,
    )

    _correct_spec = next(
        (_sp for _sp in _enemy_specs if getattr(_sp, 'id', None) == enemy.spec_id),
        _enemy_specs[0] if _enemy_specs else None,
    )
    if _correct_spec is not None:
        _spawn_loot_drops(game_map, enemy.pos, _correct_spec)

    # XP
    from ..data.ships import find_ship as _find_ship_cat
    try:
        _sc = _find_ship_cat(enemy.spec_id)
        from ..xp import add_xp as _add_xp
        _add_xp(ctx, _sc.base_hull * 2)
    except (KeyError, ImportError):
        pass

    # Counters
    if hasattr(ctx, 'player_counters'):
        ctx.player_counters.total_kills += 1

    # Track defeated
    _cr.defeated_names.append(enemy.name)
    _cr.defeated_spec_ids.append(enemy.spec_id)
    if _dead_ent is not None:
        _bid = getattr(_dead_ent, 'bounty_spawn_id', None)
        if _bid is not None:
            _cr.defeated_bounty_ids.append(_bid)

    # Clean up procedural spawn matching
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
    """Mark the player as dead and show the death screen."""
    ctx.player_dead = True
    from ._encounter import _render_death_screen
    _render_death_screen(_console, ctx.context, _log)


# ---------------------------------------------------------------------------
# Defense toggle
# ---------------------------------------------------------------------------

def handle_defense(ctx) -> None:
    """Cycle shield regen rate 0-10. No-op if no shields."""
    max_sh = _player_state.get("max_shields", 0)
    if max_sh > 0:
        cur = _player_state.get("shield_regen_rate", 0)
        next_rate = (cur + 1) % 11
        _player_state["shield_regen_rate"] = next_rate
        if next_rate == 0:
            _log.add_colored("Shield regen: OFF", _ml.COLOR_PLAYER_ACTION)
        else:
            _log.add_colored(
                f"Shield regen rate: {next_rate}/10",
                _ml.COLOR_PLAYER_ACTION,
            )
    else:
        _log.add_colored("No shields installed.", _ml.COLOR_PLAYER_ACTION)


# ---------------------------------------------------------------------------
# Enemy turns
# ---------------------------------------------------------------------------

def run_enemy_turns(ctx, game_map: world.GameMap) -> int:
    """Execute AI turns for all alive enemies. Returns total damage to player."""
    from ._ai import _run_enemy_turn as _enemy_ai

    _hit_chances: dict[str, int] = {}
    if _weapons_list and _target_idx < len(_enemy_insts):
        _target_e = _enemy_insts[_target_idx]
        if _target_e.alive:
            _dist = _distance(_player_state["pos"], _target_e.pos)
            _target_dodge = _calc_dodge_bonus(
                _target_e.cells_moved_this_turn,
                int(_target_e.pilot_piloting * 0.5),
            )
            for _wid in _weapons_list:
                try:
                    _hit_chances[_wid] = _space_hit_chance(
                        _wid, _player_state["gunnery"], _dist, _target_dodge,
                    )
                except KeyError:
                    pass

    _evade = _calc_dodge_bonus(
        _player_state.get("cells_moved_this_turn", 0),
        int(_player_state.get("piloting", 0) * 0.5),
    )

    _result = _enemy_ai(
        _console, ctx.context,
        game_map,
        _player_state, _enemy_insts, _enemy_specs,
        _enemy_ents, _target_idx, _log,
        _weapons_list, _active_weapons,
        _hit_chances, _evade,
        _flee_attempts, _view_w, _view_h,
        _calc_camera,
        ctx=ctx,
    )

    if _result == "DEFEAT":
        return 999  # signal player death
    return 0  # no damage to player tracked here (AI applies directly)


# ---------------------------------------------------------------------------
# Reinforcements
# ---------------------------------------------------------------------------

def check_reinforcements(ctx, game_map: world.GameMap) -> None:
    """Detect and add new combatants mid-fight."""
    from ..npc_ships import move_npcs as _tick_npcs
    from ..navigation import _detect_combat_encounter as _re_detect
    from .. import solar_system as _ss_module

    _tick_npcs(ctx, game_map)

    _new_encounter = _re_detect(ctx, _player_state["pos"], _ss_module.current_system())
    if _new_encounter is None:
        return

    _new_specs, _new_positions = _new_encounter
    _existing_entity_ids = {id(_e) for _e in _enemy_ents.values()}

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
            for _ei in _enemy_insts
        )
        if _already:
            continue

        # Build new enemy instance
        from ..data.ships import find_ship as _fs
        try:
            _ship_cat = _fs(_ctx.player_owned_ship.ship_id)
        except (KeyError, AttributeError):
            continue

        from ..data.pilot_skills import PilotSkills
        _pilot = PilotSkills(
            gunnery=_player_state.get("gunnery", 30),
            piloting=_player_state.get("piloting", 30),
            engineering=_player_state.get("engineering", 30),
        )

        _ps_dummy, _new_ei = init_combat_state(
            _ship_cat, _ctx.player_owned_ship,
            _player_state["pos"], _pilot,
            _ns, _np,
        )
        _enemy_insts.append(_new_ei)
        _enemy_specs.append(_ns)
        if _found_entity is not None:
            _enemy_ents[len(_enemy_insts) - 1] = _found_entity
            if getattr(_found_entity, 'name', ''):
                _new_ei.name = _found_entity.name
        _log.add_colored(
            f"{getattr(_found_entity, 'name', '') or _ns.name} joins the fight!",
            _ml.COLOR_COMBAT_EVENT,
        )


# ---------------------------------------------------------------------------
# State sync
# ---------------------------------------------------------------------------

def set_player_ap(ctx, ap: int) -> None:
    """Set the player's AP to a specific value (used by flee-on-failure)."""
    _player_state["ap_remaining"] = ap


def reset_turn(ctx) -> None:
    """Reset player AP and per-turn state for a new turn."""
    start_player_turn(_player_state)


def sync_state(ctx) -> None:
    """Persist hull damage back to OwnedShip."""
    _sync_back_hull(_player_state, ctx.player_owned_ship)


def get_combat_result() -> CombatResult:
    """Return the CombatResult built during this encounter."""
    return _cr
