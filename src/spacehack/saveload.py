"""Save / load — JSON serialization of GameContext.

Single autosave file at ``~/.spacehack/saves/autosave.json``.
Serialization converts GameContext fields to a JSON-safe dict,
skipping non-serializable fields (tcod context, game_map, entities).
On load, game_map is regenerated from saved position + system info.

Design doc: ``docs/design/in_progress/03_DESIGN_GAME_INFRASTRUCTURE.md``
"""

from __future__ import annotations

import dataclasses
import json
import os
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .game_context import GameContext


def _saves_dir() -> Path:
    """Return (and create) ``~/.spacehack/saves/``."""
    _dir = Path.home() / ".spacehack" / "saves"
    _dir.mkdir(parents=True, exist_ok=True)
    return _dir


def _autosave_path() -> Path:
    """Full path to the autosave file."""
    return _saves_dir() / "autosave.json"


def save_exists() -> bool:
    """Return True if an autosave file is on disk."""
    return _autosave_path().is_file()


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def _d(obj) -> object:
    """Recursively convert *obj* to a JSON-safe value.

    Dataclasses → dict, sets → sorted list, enums → name string,
    Position-like objects → [x, y] list.
    """
    if isinstance(obj, Enum):
        return obj.name
    if isinstance(obj, (list, tuple)):
        return [_d(v) for v in obj]
    if isinstance(obj, (set, frozenset)):
        return sorted(_d(v) for v in obj)
    if isinstance(obj, dict):
        return {str(k): _d(v) for k, v in obj.items()}
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        # Position-like dataclasses: serialize as [x, y] for compactness.
        if hasattr(obj, "x") and hasattr(obj, "y"):
            return [_d(obj.x), _d(obj.y)]
        _fields: dict[str, object] = {}
        for _f in dataclasses.fields(obj):
            _fields[_f.name] = _d(getattr(obj, _f.name))
        return _fields
    if hasattr(obj, "x") and hasattr(obj, "y"):
        return [_d(obj.x), _d(obj.y)]
    return obj


def _ctx_to_dict(ctx: GameContext) -> dict:
    """Serialize only the fields that survive a save/load cycle."""
    return {
        "character_info": _d(ctx.character_info),
        "stats": {
            "hp": ctx.stats.hp,
            "max_hp": ctx.stats.max_hp,
            "credits": ctx.stats.credits,
            "gunnery": ctx.stats.gunnery,
            "piloting": ctx.stats.piloting,
            "engineering": ctx.stats.engineering,
        },
        "player_owned_ship": _d(ctx.player_owned_ship),
        "player_active_missions": _d(ctx.player_active_missions),
        "completed_mission_ids": sorted(ctx.completed_mission_ids),
        "mission_boards": _d(ctx.mission_boards),
        "bounty_spawns": _d(ctx.bounty_spawns),
        "faction_reputation": _d(ctx.faction_reputation),
        "player_xp": ctx.player_xp,
        "player_level": ctx.player_level,
        "player_skill_points": ctx.player_skill_points,
        "player_gunnery_bonus": ctx.player_gunnery_bonus,
        "player_piloting_bonus": ctx.player_piloting_bonus,
        "player_engineering_bonus": ctx.player_engineering_bonus,
        "player_traits": list(ctx.player_traits),
        "player_counters": _d(ctx.player_counters),
        "time_day": ctx.time_day,
        "time_month": ctx.time_month,
        "time_year": ctx.time_year,
        "move_counter": ctx.move_counter,
        "current_mode": "city",
        "current_city_id": "earth",
        "current_system_id": "sol",
        "player_pos_x": ctx.player.pos.x,
        "player_pos_y": ctx.player.pos.y,
        "economy_state": _d(ctx.economy_state),
        "generated_missions": _d(ctx.generated_missions),
        "procedural_spawns": _d(ctx.procedural_spawns),
    }


def save_game(
    ctx: GameContext,
    *,
    mode: str = "city",
    city_id: str = "earth",
    system_id: str = "sol",
) -> None:
    """Save the current game state to the autosave file.

    ``mode``, ``city_id``, and ``system_id`` are passed by the caller
    so save/load doesn't need to reach into ``_run_game``'s closure locals.
    """
    _data = _ctx_to_dict(ctx)
    _data["current_mode"] = mode
    _data["current_city_id"] = city_id
    _data["current_system_id"] = system_id
    _data["player_pos_x"] = ctx.player.pos.x
    _data["player_pos_y"] = ctx.player.pos.y
    ctx.current_city_id = city_id
    _path = _autosave_path()
    _path.write_text(json.dumps(_data, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Deserialization
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> dict | None:
    """Read and parse the autosave JSON. Returns None if not found."""
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, FileNotFoundError):
        return None


def _parse_pos(raw) -> tuple[int, int]:
    """Parse a serialized position from either [x, y] list or {x, y} dict."""
    if isinstance(raw, dict):
        return (raw.get("x", 0), raw.get("y", 0))
    if isinstance(raw, (list, tuple)) and len(raw) >= 2:
        return (raw[0], raw[1])
    return (0, 0)


def load_game(context: "tcod.context.Context") -> GameContext | None:
    """Load the autosave and reconstruct a GameContext.

    Returns None if no save exists or the file is corrupted.
    """
    _data = _load_json(_autosave_path())
    if _data is None:
        return None

    from . import hud, message_log, mission as mission_module
    from . import ship as ship_module, world, solar_system as solar_system_module
    from .game_context import GameContext, PlayerCounters, BountySpawn, ProceduralSpawn

    # --- character_info ---
    _ci = _data["character_info"]

    # --- HudStats ---
    _s = _data["stats"]
    _stats = hud.HudStats(
        hp=_s["hp"], max_hp=_s["max_hp"], credits=_s["credits"],
        gunnery=_s.get("gunnery", 0),
        piloting=_s.get("piloting", 0),
        engineering=_s.get("engineering", 0),
    )

    # --- OwnedShip ---
    _osh = _data.get("player_owned_ship")
    _owned_ship: ship_module.OwnedShip | None = None
    if _osh is not None and _osh.get("ship_id"):
        _owned_ship = ship_module.OwnedShip(
            ship_id=_osh["ship_id"],
            fuel=_osh.get("fuel", 0),
            hull_damage_pct=_osh.get("hull_damage_pct", 0),
            weapons=tuple(_osh.get("weapons", ()) or ()),
            modules=tuple(_osh.get("modules", ()) or ()),
            inventory=_osh.get("inventory", {}) or {},
            mission_reserved=_osh.get("mission_reserved", 0),
        )

    # --- Active missions ---
    _active_missions: list[mission_module.ActiveMission] = []
    for _am in _data.get("player_active_missions", ()) or ():
        _time_dl = None
        if _am.get("time_deadline"):
            _td = _am["time_deadline"]
            _time_dl = (int(_td[0]), int(_td[1]), int(_td[2]))
        _active_missions.append(mission_module.ActiveMission(
            mission_id=_am["mission_id"],
            is_procedural=_am.get("is_procedural", False),
            status=mission_module.MissionStatus[_am["status"]] if _am.get("status") else mission_module.MissionStatus.IN_PROGRESS,
            title=_am.get("title", ""),
            required_cargo_size=_am.get("required_cargo_size", 0),
            delivery_target_npc_id=_am.get("delivery_target_npc_id", ""),
            delivery_target_planet_id=_am.get("delivery_target_planet_id", ""),
            deadline_days=_am.get("deadline_days", 0),
            accept_day=_am.get("accept_day", 1),
            time_deadline=_time_dl,
            reward_credits=_am.get("reward_credits", 0),
            reward_xp=_am.get("reward_xp", 0),
            early_bonus_pct=_am.get("early_bonus_pct", 0),
            bounty_spawn_id=_am.get("bounty_spawn_id"),
            target_enemy_id=_am.get("target_enemy_id"),
            target_system_id=_am.get("target_system_id"),
            bounty_target_name=_am.get("bounty_target_name"),
            bounty_target_squad_size=_am.get("bounty_target_squad_size", 1),
            bounty_target_loadout_pct=_am.get("bounty_target_loadout_pct", 0),
            tier=_am.get("tier", 1),
        ))

    # --- Mission boards ---
    _mission_boards: dict[str, mission_module.MissionBoard] = {}
    for _npc_id, _bd in (_data.get("mission_boards", {}) or {}).items():
        _board = mission_module.MissionBoard(
            npc_id=_npc_id,
            slots=list(_bd.get("slots", []) or []),
            max_slots=_bd.get("max_slots", 5),
            planet_id=_bd.get("planet_id", ""),
        )
        _board.last_refresh_month = _bd.get("last_refresh_month", 1)
        _mission_boards[_npc_id] = _board

    # --- Bounty spawns ---
    _bounty_spawns: dict[str, list] = {}
    for _sys_id, _spawns in (_data.get("bounty_spawns", {}) or {}).items():
        _bounty_spawns[_sys_id] = []
        for _bs in (_spawns or []):
            _px, _py = _parse_pos(_bs.get("pos", [0, 0]))
            _bounty_spawns[_sys_id].append(BountySpawn(
                spawn_id=_bs["spawn_id"],
                enemy_id=_bs.get("enemy_id", ""),
                pos=world.Position(_px, _py),
                bounty_target_name=_bs.get("bounty_target_name"),
                squad_size=_bs.get("squad_size", 1),
                loadout_pct=_bs.get("loadout_pct", 0),
                squad_group_id=_bs.get("squad_group_id"),
            ))

    # --- Procedural spawns ---
    _proc_data = _data.get("procedural_spawns", {}) or {}
    _proc_spawns: dict[str, list] = {}
    for _sys_id, _slist in _proc_data.items():
        _proc_spawns[_sys_id] = []
        for _ps in (_slist or []):
            _px, _py = _parse_pos(_ps.get("pos", [0, 0]))
            _proc_spawns[_sys_id].append(ProceduralSpawn(
                npc_id=_ps.get("npc_id", ""),
                pos=world.Position(_px, _py),
                squad_id=_ps.get("squad_id"),
            ))

    # --- PlayerCounters ---
    _pc_data = _data.get("player_counters", {}) or {}
    _counters = PlayerCounters(
        laser_shots=_pc_data.get("laser_shots", 0),
        missile_shots=_pc_data.get("missile_shots", 0),
        plasma_shots=_pc_data.get("plasma_shots", 0),
        merchant_kills=_pc_data.get("merchant_kills", 0),
        total_kills=_pc_data.get("total_kills", 0),
        bounties_completed=_pc_data.get("bounties_completed", 0),
        deliveries_completed=_pc_data.get("deliveries_completed", 0),
        total_damage_taken=_pc_data.get("total_damage_taken", 0),
        combat_flees=_pc_data.get("combat_flees", 0),
    )

    # --- Economy & generated missions ---
    _econ = _data.get("economy_state", {}) or {}
    _gen = _data.get("generated_missions", {}) or {}
    _rep = _data.get("faction_reputation", {}) or {}

    # --- Log ---
    _log = message_log.MessageLog(capacity=6)
    _log.add("Game loaded.")

    # --- Regenerate map ---
    _pos_x = _data.get("player_pos_x", 13)
    _pos_y = _data.get("player_pos_y", 17)
    _city_id = _data.get("current_city_id", "earth")
    _mode = _data.get("current_mode", "city")
    _system_id = _data.get("current_system_id", "sol")

    if _mode == "space":
        # --- Space mode: rebuild solar system ---
        from .data.solar_systems import find_solar_system as _find_sys
        from .data.npc_ships import find_npc_ship as _find_npc

        try:
            _sys_spec = _find_sys(_system_id)
        except KeyError:
            _log.add(f"Save references unknown system '{_system_id}' — loading Earth city.")
            _mode = "city"
            _city_id = "earth"

        if _mode == "space":
            _game_map = solar_system_module.make_solar_system(system=_sys_spec)
            solar_system_module.current_solar_system_id = _system_id

            # Add bounty NPCs directly from saved spawns.
            for _bs in _bounty_spawns.get(_system_id, []):
                try:
                    _espec = _find_npc(_bs.enemy_id)
                except (KeyError, ImportError):
                    continue
                _display_name = _bs.bounty_target_name or _espec.name
                _ent = world.Entity(
                    char=_espec.char, fg=_espec.fg,
                    pos=_bs.pos, name=_display_name,
                    width=1, height=1,
                    npc_ship_id=_bs.enemy_id,
                )
                if not _bs.squad_group_id:
                    _ent.bounty_spawn_id = _bs.spawn_id
                _game_map.entities.append(_ent)

            # Add procedural NPCs from saved spawns (don't generate new ones).
            for _ps in _proc_spawns.get(_system_id, []):
                try:
                    _espec = _find_npc(_ps.npc_id)
                except (KeyError, ImportError):
                    continue
                _ent = world.Entity(
                    char=_espec.char, fg=_espec.fg,
                    pos=_ps.pos, name=_espec.name,
                    width=1, height=1,
                    npc_ship_id=_ps.npc_id,
                )
                _game_map.entities.append(_ent)

            # Place player ship entity at saved space position.
            if _owned_ship is not None:
                _ship_spec = ship_module.find_ship(_owned_ship.ship_id)
                _player_ent = world.Entity(
                    char=_ship_spec.char, fg=_ship_spec.fg,
                    pos=world.Position(_pos_x, _pos_y),
                    name=f"Your Ship: {_ship_spec.name}",
                    ship_id=_owned_ship.ship_id, owned=True,
                )
            else:
                _player_ent = world.Entity(
                    char='@', fg=(255, 255, 255),
                    pos=world.Position(_pos_x, _pos_y), name='Player',
                )
            _game_map.entities.append(_player_ent)
    else:
        # --- City mode: load planet map ---
        from .data.planets import load_planet as planets_load_planet

        _game_map = planets_load_planet(_city_id)
        _player_ent = world.Entity(
            char='@', fg=(255, 255, 255),
            pos=world.Position(_pos_x, _pos_y), name='Player',
        )
        _game_map.entities.append(_player_ent)

        # Restore hangar ship if owned.
        if _owned_ship is not None:
            _ship_spec = ship_module.find_ship(_owned_ship.ship_id)
            _hangar = world.Entity(
                char=_ship_spec.char, fg=_ship_spec.fg,
                pos=world.HANGAR_ANCHOR,
                name=f"Your Ship: {_ship_spec.name}",
                ship_id=_owned_ship.ship_id, owned=True,
            )
            _game_map.entities.append(_hangar)

    # --- Assemble GameContext ---
    _ctx = GameContext(
        context=context,
        character_info=_ci,
        log=_log,
        game_map=_game_map,
        player=_player_ent,
        stats=_stats,
        player_owned_ship=_owned_ship,
        player_active_missions=_active_missions,
    )
    _ctx.completed_mission_ids = set(_data.get("completed_mission_ids", []) or [])
    _ctx.mission_boards = _mission_boards
    _ctx.bounty_spawns = _bounty_spawns
    _ctx.faction_reputation = _rep
    _ctx.player_xp = _data.get("player_xp", 0)
    _ctx.player_level = _data.get("player_level", 1)
    _ctx.player_skill_points = _data.get("player_skill_points", 0)
    _ctx.player_gunnery_bonus = _data.get("player_gunnery_bonus", 0)
    _ctx.player_piloting_bonus = _data.get("player_piloting_bonus", 0)
    _ctx.player_engineering_bonus = _data.get("player_engineering_bonus", 0)
    _ctx.player_traits = list(_data.get("player_traits", []) or [])
    _ctx.player_counters = _counters
    _ctx.time_day = _data.get("time_day", 1)
    _ctx.time_month = _data.get("time_month", 1)
    _ctx.time_year = _data.get("time_year", 2200)
    _ctx.move_counter = _data.get("move_counter", 0)
    _ctx.economy_state = _econ
    _ctx.generated_missions = _gen
    _ctx.procedural_spawns = _proc_spawns
    _ctx.current_city_id = _city_id
    _ctx._loaded_mode = _mode  # type: ignore[attr-defined]

    return _ctx
