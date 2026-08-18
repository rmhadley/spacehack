"""Bounty / intercept spawn placement and removal.

Extracted from ``navigation.py`` to keep that module under the 1,000-line
architecture limit. Every function here stays under 40 lines.
"""

from __future__ import annotations

from . import main_quest as main_quest_module
from . import message_log
from . import solar_system as solar_system_module
from . import world
from .data.npc_ships import find_npc_ship


def _nearest_body_name(pos: world.Position, system) -> str:
    """Name of the nearest named body (planet, gate, station) to ``pos``."""
    best_name = "unknown location"
    best_dist = 999999
    for p in system.planets:
        cx = p.pos.x + p.width // 2
        cy = p.pos.y + p.height // 2
        d = max(abs(pos.x - cx), abs(pos.y - cy))
        if d < best_dist:
            best_dist = d
            best_name = p.name
    for jp in system.jump_points:
        cx = jp.pos.x + jp.width // 2
        cy = jp.pos.y + jp.height // 2
        d = max(abs(pos.x - cx), abs(pos.y - cy))
        if d < best_dist:
            best_dist = d
            best_name = jp.name
    for st in getattr(system, "stations", ()) or ():
        cx = st.pos.x + st.width // 2
        cy = st.pos.y + st.height // 2
        d = max(abs(pos.x - cx), abs(pos.y - cy))
        if d < best_dist:
            best_dist = d
            best_name = st.name
    return best_name


def _bounty_landmarks(system) -> list[world.Position]:
    """One spawn position per landmark (planet, gate, station) in ``system``,
    ordered by distance from the system centre."""
    _positions: list[world.Position] = []
    for p in system.planets:
        if getattr(p, "sun", False):
            continue
        sx = p.pos.x + p.width + 3
        sy = p.pos.y + p.height // 2
        if 0 <= sx < system.width and 0 <= sy < system.height:
            _positions.append(world.Position(sx, sy))
    for jp in system.jump_points:
        sx = jp.pos.x + jp.width + 6
        sy = jp.pos.y + jp.height // 2
        if 0 <= sx < system.width and 0 <= sy < system.height:
            _positions.append(world.Position(sx, sy))
    for st in getattr(system, "stations", ()) or ():
        sx = st.pos.x + st.width + 3
        sy = st.pos.y + st.height // 2
        if 0 <= sx < system.width and 0 <= sy < system.height:
            _positions.append(world.Position(sx, sy))
    _cx, _cy = system.width // 2, system.height // 2
    _positions.sort(key=lambda p: (p.x - _cx) ** 2 + (p.y - _cy) ** 2)
    return _positions


def _pick_bounty_spawn_pos(
    system,
    *,
    used_positions: frozenset = frozenset(),
) -> world.Position | None:
    """Return a free landmark position for a bounty target, else ``None``."""
    for _pos in _bounty_landmarks(system):
        if (_pos.x, _pos.y) not in used_positions:
            return _pos
    return None


def _bounty_leader_entity(_bs, _espec) -> world.Entity:
    """Build the space entity for a bounty leader/wingmate spawn.

    Shared by :func:`_add_bounty_spawns_to_map` and
    :func:`spacehack.main_quest.ensure_quest_spawns` so quest and
    mission spawns construct identical entities (one place, not two).
    Only the leader (no ``squad_group_id``) gets ``bounty_spawn_id`` /
    ``heist_spawn_id`` — wingmates don't so they can't trigger
    auto-hail or bounty completion on kill. Squad linkage + warning
    range propagate to every member.
    """
    _ent = world.Entity(
        char=_espec.char,
        fg=_espec.fg,
        pos=_bs.pos,
        name=_bs.bounty_target_name or _espec.name,
        width=1, height=1,
        npc_ship_id=_bs.enemy_id,
    )
    if _bs.squad_group_id is None:
        _ent.bounty_spawn_id = _bs.spawn_id
        if _bs.heist_spawn_id is not None:
            _ent.heist_spawn_id = _bs.heist_spawn_id
    _ent.bounty_squad_id = _bs.squad_group_id or _bs.spawn_id
    _ent.bounty_comms_range = _bs.comms_warning_range
    return _ent


def _salvage_wreck_entity(_bs, _espec) -> world.Entity:
    """Build a non-combatant, boardable mission wreck entity."""
    _ent = world.Entity(
        char=_espec.char,
        fg=_espec.fg,
        pos=_bs.pos,
        name=_espec.name,
        width=1, height=1,
        npc_ship_id=_bs.enemy_id,
    )
    _ent.salvage_wreck_spawn_id = _bs.spawn_id
    return _ent


def _log_sensor_ping(ctx, label: str, _bs, _system) -> None:
    """Log a sensor ping naming the nearest landmark to the spawn."""
    if _system is None:
        return
    _landmark = _nearest_body_name(_bs.pos, _system)
    ctx.log.add_colored(
        f"Sensor ping: {label} detected near {_landmark}.",
        message_log.COLOR_IMPORTANT_EVENT,
    )


def _add_bounty_spawns_to_map(
    ctx, game_map: world.GameMap, system_id: str,
) -> None:
    """Add bounty-target enemy entities from ``ctx.bounty_spawns`` to
    ``game_map.entities`` for system ``system_id``."""
    main_quest_module.ensure_quest_spawns(ctx, system_id)
    _spawns = ctx.bounty_spawns.get(system_id, [])
    if not _spawns:
        return
    _system = getattr(solar_system_module, "current_system", lambda: None)()
    for _bs in _spawns:
        try:
            _espec = find_npc_ship(_bs.enemy_id)
        except (KeyError, ImportError):
            continue
        if _bs.salvage_wreck:
            game_map.entities.append(_salvage_wreck_entity(_bs, _espec))
            _log_sensor_ping(ctx, "derelict wreck", _bs, _system)
            continue
        game_map.entities.append(_bounty_leader_entity(_bs, _espec))
        if _system is not None and _bs.squad_group_id is None:
            _log_sensor_ping(ctx, "bounty target", _bs, _system)


def _remove_map_entities(ctx, system_id: str, positions: list[world.Position]) -> None:
    """Remove non-owned, non-loot entities at ``positions`` from the map."""
    if ctx.game_map is None:
        return
    for _pos in positions:
        _target_entity = None
        for _e in ctx.game_map.entities:
            if getattr(_e, "owned", False):
                continue
            if getattr(_e, "loot_data", None) is not None:
                continue  # don't remove player-lootable salvage
            if _e.pos == _pos:
                _target_entity = _e
                break
        if _target_entity is not None:
            try:
                ctx.game_map.entities.remove(_target_entity)
            except ValueError:
                pass


def _remove_bounty_spawn(ctx, spawn_id: str, system_id: str | None) -> None:
    """Remove the bounty spawn with ``spawn_id`` from
    ``ctx.bounty_spawns[system_id]``, and from the current
    ``ctx.game_map.entities`` if the player is in that system.

    Also removes any wingmate spawns linked to the same squad
    (matching ``squad_group_id``). No-op if the spawn doesn't exist.
    """
    if system_id is None or system_id not in ctx.bounty_spawns:
        return
    _to_remove: set[str] = {spawn_id}
    for _bs in ctx.bounty_spawns[system_id]:
        if _bs.squad_group_id == spawn_id:
            _to_remove.add(_bs.spawn_id)
    _positions_to_remove = [
        _bs.pos for _bs in ctx.bounty_spawns[system_id]
        if _bs.spawn_id in _to_remove
    ]
    ctx.bounty_spawns[system_id] = [
        _bs for _bs in ctx.bounty_spawns[system_id]
        if _bs.spawn_id not in _to_remove
    ]
    if _positions_to_remove:
        _cur_sys = getattr(solar_system_module.current_system(), "id", None)
        if _cur_sys == system_id:
            _remove_map_entities(ctx, system_id, _positions_to_remove)
