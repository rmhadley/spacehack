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
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from . import world

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


def delete_save() -> None:
    """Remove the autosave file (roguelike: save-on-quit, delete-on-load)."""
    _path = _autosave_path()
    try:
        _path.unlink()
    except FileNotFoundError:
        pass


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
    """Serialize only the fields that survive a save/load cycle.

    Returns a flat dict — callers add mode / position / synced-spawn
    fields before writing to disk.
    """
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
        "generated_missions": _d(ctx.generated_missions),
        "economy_state": _d(ctx.economy_state),
        "militia_scanned": sorted(ctx.militia_scanned),
        "ground_stats": _d(ctx.ground_stats),
        "equipped_ground_weapons": list(ctx.equipped_ground_weapons),
        "equipped_ground_armor": _d(ctx.equipped_ground_armor),
        "ground_hp": ctx.ground_hp,
        "ground_max_hp": ctx.ground_max_hp,
    }


def _save_loot(game_map) -> list[dict]:
    """Serialize all loot entities on the map."""
    _result: list[dict] = []
    for _e in getattr(game_map, 'entities', []):
        if getattr(_e, 'loot_data', None) is not None:
            _result.append({
                'x': _e.pos.x, 'y': _e.pos.y,
                'loot_data': _e.loot_data,
                'heist_mission': bool(getattr(_e, 'heist_mission', False)),
                'heist_mission_id': getattr(_e, 'heist_mission_id', None),
            })
    return _result


def save_game(
    ctx: GameContext,
    *,
    mode: str = "city",
    city_id: str = "earth",
    system_id: str = "sol",
    space_player_pos: tuple[int, int] | None = None,
) -> None:
    """Save the current game state to the autosave file.

    ``mode``, ``city_id``, and ``system_id`` are passed by the caller
    so save/load doesn't need to reach into ``_run_game``'s closure locals.

    ``space_player_pos`` is required when ``mode == "dungeon"`` — the
    player's ship position in the space map, needed to reconstruct the
    space side on load.
    """
    # Sync procedural spawn positions from actual entity positions on
    # the map.  move_npcs() moves entities but doesn't update the
    # ProceduralSpawn.pos in ctx.procedural_spawns, so the spawn data
    # holds the original spawn position.
    #
    # Entities are indexed by npc_ship_id and popped one-at-a-time
    # per spawn so every spawn gets a *different* entity's position.
    # Without pop()-based dedup, two solo spawns of the same type
    # would both match the first entity found — the stacking bug.
    from .game_context import ProceduralSpawn
    _synced_spawns: dict[str, list] = {}               # sys_id → [synced ProceduralSpawn]
    _synced_mids: dict[str, list] = {}                 # sys_id → [movement_id per spawn]
    _synced_targets: dict[str, list[int]] = {}          # movement_id → [tx, ty]
    _synced_paths: dict[str, list] = {}                 # movement_id → [[x,y],...]
    for _sys_id, _spawns in ctx.procedural_spawns.items():
        # Only the current system's map is in ctx.game_map — for other
        # systems we keep all spawns as-is (no entity data to match).
        _is_current = (_sys_id == system_id)

        if _is_current:
            # Build candidate list keyed by npc_ship_id.  Any entity with
            # npc_ship_id is a candidate — including derelicts (which
            # have npc_ship_id but NOT procedural_squad_id because
            # their base_speed=0 omits squad registration).  pop(0) on
            # match gives each spawn a different entity (prevents stacking).
            _by_type: dict[str, list] = {}
            for _e in ctx.game_map.entities:
                _eid = getattr(_e, 'npc_ship_id', '')
                if _eid:
                    _by_type.setdefault(_eid, []).append(_e)

        _updated: list = []
        _mids: list = []
        for _ps in _spawns:
            _cur_pos = _ps.pos
            _cur_mid = ""
            if _is_current:
                _candidates = _by_type.get(_ps.npc_id, [])
                if _candidates:
                    _matched = _candidates.pop(0)
                    _cur_pos = _matched.pos
                    _cur_mid = _matched.procedural_squad_id
                else:
                    # Entity was killed — remove its spawn so it doesn't
                    # respawn on the next load.
                    continue
            else:
                # For other systems preserve all spawns at their last
                # recorded position (best-effort — no entity data).
                pass
            _updated.append(ProceduralSpawn(
                npc_id=_ps.npc_id, pos=_cur_pos, squad_id=_ps.squad_id,
            ))
            _mids.append(_cur_mid)
            # Capture the entity's current target and path.
            if _cur_mid:
                _tgt = ctx.npc_targets.get(_cur_mid)
                if _tgt is not None:
                    _synced_targets[_cur_mid] = [_tgt[0], _tgt[1]]
                _pth = ctx.npc_paths.get(_cur_mid)
                if _pth:
                    _synced_paths[_cur_mid] = [[x, y] for x, y in _pth]
        _synced_spawns[_sys_id] = _updated
        _synced_mids[_sys_id] = _mids

    _data = _ctx_to_dict(ctx)
    _data["map_loot"] = _save_loot(ctx.game_map)
    _data["procedural_spawns"] = _d(_synced_spawns)
    _data["procedural_mids"] = _synced_mids
    _data["npc_targets"] = _synced_targets
    _data["npc_paths"] = _synced_paths
    _data["current_mode"] = mode
    _data["current_city_id"] = city_id
    _data["current_system_id"] = system_id
    _data["player_pos_x"] = ctx.player.pos.x
    _data["player_pos_y"] = ctx.player.pos.y
    ctx.current_city_id = city_id

    # --- Dungeon mode: serialize dungeon map + space player position ---
    if mode == "dungeon":
        _data["dungeon"] = _dungeon_to_dict(ctx.game_map, space_player_pos)

    # --- Persistent wreck interiors (salvage missions) ---
    # The autosave IS the on-disk cache: every boarded wreck interior is
    # serialized here and restored on load so crew stay dead, loot stays
    # taken, and fog stays revealed across save/quit/continue.
    if ctx.interiors:
        _data["interiors"] = {
            _k: _dungeon_to_dict(_v, None) for _k, _v in ctx.interiors.items()
        }

    # --- Save RNG state so Continue restores the exact same stream ---
    from .engine import RNG
    _rng_state = RNG.getstate()
    _data["rng_state"] = [_rng_state[0], list(_rng_state[1]), _rng_state[2]]

    _path = _autosave_path()
    _path.write_text(json.dumps(_data, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Shared dungeon serialization (active dungeon + persistent interiors)
# ---------------------------------------------------------------------------


def _dungeon_to_dict(gm, space_player_pos: tuple[int, int] | None) -> dict:
    """Serialize a dungeon :class:`world.GameMap` to a JSON-safe dict.

    Shared by the active-dungeon save block AND the
    ``ctx.interiors`` cache (salvage wrecks). ``space_player_pos`` is
    only meaningful for the active dungeon (the player's ship position
    in space while boarded); interiors pass ``None``.
    """
    return {
        "width": gm.width,
        "height": gm.height,
        "tiles": [[{"kind": c.kind, "char": c.char, "walkable": c.walkable, "fg": list(c.fg), "bg": list(c.bg)} for c in row] for row in gm.tiles],
        "entities": [
            {
                "char": e.char,
                "fg_r": e.fg[0], "fg_g": e.fg[1], "fg_b": e.fg[2],
                "x": e.pos.x, "y": e.pos.y,
                "name": e.name,
                "loot_data": e.loot_data,
                "computer_terminal": e.computer_terminal,
                "npc_char_id": e.npc_char_id,
                "squad_id": getattr(e, 'squad_id', ''),
                "heist_mission": bool(getattr(e, 'heist_mission', False)),
                "heist_mission_id": getattr(e, 'heist_mission_id', None),
            }
            for e in gm.entities if e.char != '@'
        ],
        "seen": gm.seen,
        "sight_radius": gm.sight_radius,
        "power_restored": getattr(gm, 'power_restored', False),
        "space_player_x": space_player_pos[0] if space_player_pos else 0,
        "space_player_y": space_player_pos[1] if space_player_pos else 0,
        "location_name": getattr(gm, 'location_name', ''),
        # Salvage-wreck interior anchors: the wreck's BountySpawn id
        # (cache key + lifecycle) and the interior's entry spawn, so
        # re-boarding a restored interior places the player correctly.
        "wreck_spawn_id": getattr(gm, 'wreck_spawn_id', None),
        "entry_spawn": (
            [gm.entry_spawn.x, gm.entry_spawn.y]
            if getattr(gm, 'entry_spawn', None) is not None else None
        ),
    }


def _dungeon_from_dict(dd: dict) -> tuple:
    """Rebuild a dungeon :class:`world.GameMap` from a serialized dict.

    Returns ``(game_map, space_player_pos)``. The player entity is NOT
    included (the caller appends a fresh ``@`` at the saved position).
    """
    # Backward-compat fallback for old saves that stored kind strings.
    _TILE_FROM_KIND: dict[str, world.Tile] = {
        "dungeon_wall": world.DUNGEON_WALL,
        "dungeon_floor": world.DUNGEON_FLOOR,
        "dungeon_door": world.DUNGEON_DOOR,
        "void": world.VOID,
        "airlock": world.AIRLOCK,
        "breach": world.BREACH,
        "cockpit": world.COCKPIT,
        "engine": world.ENGINE_TILE,
        "debris": world.DEBRIS,
        "exit": world.EXIT,
        "hull_wall": world.HULL_WALL,
    }
    _dw = dd.get("width", 1)
    _dh = dd.get("height", 1)
    _raw_tiles = dd.get("tiles", [["void"]])
    _dungeon_tiles: list[list[world.Tile]] = []
    for row in _raw_tiles:
        _tile_row: list[world.Tile] = []
        for t in row:
            if isinstance(t, str):
                # Old save format: kind string → lookup default Tile.
                _tile_row.append(_TILE_FROM_KIND.get(t, world.VOID))
            else:
                # New format: full tile dict with fg/bg preserved.
                _tile_row.append(world.Tile(
                    kind=t.get("kind", "void"),
                    char=t.get("char", " "),
                    walkable=t.get("walkable", False),
                    fg=tuple(t.get("fg", [0, 0, 0])),
                    bg=tuple(t.get("bg", [0, 0, 0])),
                ))
        _dungeon_tiles.append(_tile_row)
    _dungeon_entities: list[world.Entity] = []
    for _ed in dd.get("entities", []):
        _e = world.Entity(
            char=_ed.get("char", "?"),
            fg=(_ed.get("fg_r", 255), _ed.get("fg_g", 255), _ed.get("fg_b", 255)),
            pos=world.Position(_ed.get("x", 0), _ed.get("y", 0)),
            name=_ed.get("name", ""),
            width=1, height=1,
            loot_data=_ed.get("loot_data"),
            computer_terminal=_ed.get("computer_terminal", False),
            npc_char_id=_ed.get("npc_char_id", ""),
            squad_id=_ed.get("squad_id", ""),
        )
        if _ed.get("heist_mission", False):
            _e.heist_mission = True
        _hmid = _ed.get("heist_mission_id")
        if _hmid:
            _e.heist_mission_id = _hmid
        _dungeon_entities.append(_e)

    _dungeon_map = world.GameMap(
        width=_dw, height=_dh,
        tiles=_dungeon_tiles,
        entities=_dungeon_entities,
    )
    _dungeon_map.seen = dd.get("seen")
    _dungeon_map.sight_radius = dd.get("sight_radius", 4)
    _dungeon_map.location_name = dd.get("location_name", "")
    if dd.get("power_restored", False):
        _dungeon_map.power_restored = True
    _wsid = dd.get("wreck_spawn_id")
    if _wsid:
        _dungeon_map.wreck_spawn_id = _wsid
    _es = dd.get("entry_spawn")
    if isinstance(_es, (list, tuple)) and len(_es) >= 2:
        _dungeon_map.entry_spawn = world.Position(int(_es[0]), int(_es[1]))
    _space_pos = (dd.get("space_player_x", 0), dd.get("space_player_y", 0))
    return _dungeon_map, _space_pos


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
            display_name=_osh.get("display_name"),
            fuel=_osh.get("fuel", 0),
            hull_damage_pct=_osh.get("hull_damage_pct", 0),
            weapons=tuple(_osh.get("weapons", ()) or ()),
            modules=tuple(_osh.get("modules", ()) or ()),
            inventory=_osh.get("inventory", {}) or {},
            mission_reserved=_osh.get("mission_reserved", 0),
            # weapon_ammo round-trips through the dataclass field; old
            # saves lack it and get a full magazine seeded by __post_init__.
            weapon_ammo=_osh.get("weapon_ammo", {}) or {},
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
            bounty_wingmate_enemy_id=_am.get("bounty_wingmate_enemy_id"),
            tier=_am.get("tier", 1),
            heist_target_good_id=_am.get("heist_target_good_id"),
            heist_good_secured=_am.get("heist_good_secured", False),
            salvage_wreck_enemy_id=_am.get("salvage_wreck_enemy_id"),
            salvage_layout_id=_am.get("salvage_layout_id"),
            salvage_wreck_spawn_id=_am.get("salvage_wreck_spawn_id"),
            is_smuggle=_am.get("is_smuggle", False),
            smuggle_good_id=_am.get("smuggle_good_id"),
        ))

    # --- Mission boards ---
    # Boards are keyed by (npc_id, planet_id) so every city keeps its
    # own mission list. Old saves stored plain npc_id keys — re-key from
    # each board's own fields so pre-fix saves upgrade automatically.
    _mission_boards: dict[str, mission_module.MissionBoard] = {}
    for _npc_id, _bd in (_data.get("mission_boards", {}) or {}).items():
        _board = mission_module.MissionBoard(
            npc_id=_bd.get("npc_id", _npc_id),
            slots=list(_bd.get("slots", []) or []),
            max_slots=_bd.get("max_slots", 5),
            planet_id=_bd.get("planet_id", ""),
        )
        _board.last_refresh_month = _bd.get("last_refresh_month", 1)
        _mission_boards[mission_module.board_key(
            _board.npc_id, _board.planet_id,
        )] = _board

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
                comms_warning_range=_bs.get("comms_warning_range", 0),
                heist_spawn_id=_bs.get("heist_spawn_id"),
                salvage_wreck=_bs.get("salvage_wreck", False),
            ))

    # --- Procedural spawns ---
    _proc_data = _data.get("procedural_spawns", {}) or {}
    _proc_mids = _data.get("procedural_mids", {}) or {}
    _proc_spawns: dict[str, list] = {}
    for _sys_id, _slist in _proc_data.items():
        _proc_spawns[_sys_id] = []
        for _i, _ps in enumerate(_slist or []):
            _px, _py = _parse_pos(_ps.get("pos", [0, 0]))
            _proc_spawns[_sys_id].append(ProceduralSpawn(
                npc_id=_ps.get("npc_id", ""),
                pos=world.Position(_px, _py),
                squad_id=_ps.get("squad_id"),
            ))
    # Load saved movement IDs for each spawn (keyed by system, then index).
    _proc_mid_map: dict[str, list[str]] = {}
    for _sys_id, _mids in (_proc_mids or {}).items():
        _proc_mid_map[_sys_id] = [str(m) for m in _mids]
    # Load saved NPC targets and paths (keyed by movement_id).
    _npc_targets: dict[str, tuple[int, int]] = {}
    for _mid, _tgt in (_data.get("npc_targets", {}) or {}).items():
        if isinstance(_tgt, list) and len(_tgt) >= 2:
            _npc_targets[str(_mid)] = (int(_tgt[0]), int(_tgt[1]))
    _npc_paths: dict[str, list[tuple[int, int]]] = {}
    for _mid, _pth in (_data.get("npc_paths", {}) or {}).items():
        _npc_paths[str(_mid)] = [
            (int(p[0]), int(p[1])) for p in _pth if isinstance(p, list) and len(p) >= 2
        ]

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
    # Rebuild procedural MissionSpec objects — save/load flattens them
    # into plain dicts, and the mission-board renderer reads fields like
    # .salvage_wreck_enemy_id directly (crash without reconstruction).
    _gen_restored: dict[str, mission_module.MissionSpec] = {}
    for _mid, _md in _gen.items():
        try:
            _gen_restored[_mid] = mission_module.mission_spec_from_dict(_md)
        except (TypeError, AttributeError):
            continue  # corrupt/stale entry — board_offerings skips it
    _gen = _gen_restored
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
                if _bs.salvage_wreck:
                    # Non-combatant mission wreck: boardable, persists until
                    # the component is secured. Tagged with its spawn id so
                    # the boarding flow finds the mission + interior cache.
                    # No bounty_spawn_id — it must never auto-complete.
                    _ent.salvage_wreck_spawn_id = _bs.spawn_id
                    _game_map.entities.append(_ent)
                    continue
                if not _bs.squad_group_id:
                    _ent.bounty_spawn_id = _bs.spawn_id
                    # Restore intercept linkage so on_kill still drops the
                    # mission loot after a save/quit/continue (mirrors
                    # navigation._add_bounty_spawns_to_map).
                    if _bs.heist_spawn_id is not None:
                        _ent.heist_spawn_id = _bs.heist_spawn_id
                # Squad linkage for comms Attack (mirrors navigation.py).
                _ent.bounty_squad_id = _bs.squad_group_id or _bs.spawn_id
                # Restore auto-hail range on all members too (mirrors
                # navigation.py) so post-load behavior matches fresh spawn.
                _ent.bounty_comms_range = _bs.comms_warning_range
                _game_map.entities.append(_ent)

            # Add procedural NPCs from saved spawns (don't generate new ones).
            for _i, _ps in enumerate(_proc_spawns.get(_system_id, [])):
                try:
                    _espec = _find_npc(_ps.npc_id)
                except (KeyError, ImportError):
                    continue
                # Use the saved movement ID if available, otherwise generate one.
                _saved_mids = _proc_mid_map.get(_system_id, [])
                _mid = (_saved_mids[_i] if _i < len(_saved_mids) and _saved_mids[_i]
                        else _ps.squad_id
                        or f"proc_loaded_{_system_id}_{_ps.npc_id}_{_i}")
                _ent = world.Entity(
                    char=_espec.char, fg=_espec.fg,
                    pos=_ps.pos, name=_espec.name,
                    width=1, height=1,
                    npc_ship_id=_ps.npc_id,
                )
                # Stationary ships (base_speed=0, e.g. derelicts) don't get
                # procedural_squad_id so move_npcs ignores them.
                if getattr(_espec, 'base_speed', 0) > 0:
                    _ent.procedural_squad_id = _mid
                _game_map.entities.append(_ent)

            # Place player ship entity at saved space position.
            if _owned_ship is not None:
                _ship_spec = ship_module.find_ship(_owned_ship.ship_id)
                _player_ent = world.Entity(
                    char=_ship_spec.char, fg=_ship_spec.fg,
                    pos=world.Position(_pos_x, _pos_y),
                    name=f"Your Ship: {ship_module.ship_display_name(_owned_ship)}",
                    ship_id=_owned_ship.ship_id, owned=True,
                )
            else:
                _player_ent = world.Entity(
                    char='@', fg=(255, 255, 255),
                    pos=world.Position(_pos_x, _pos_y), name='Player',
                )
            _game_map.entities.append(_player_ent)

    elif _mode == "dungeon":
        # --- Dungeon mode: rebuild space map first, then dungeon map ---
        from .data.solar_systems import find_solar_system as _find_sys
        from .data.npc_ships import find_npc_ship as _find_npc

        _dd = _data.get("dungeon", {})
        if not _dd:
            _log.add("Dungeon save data missing — loading Earth city.")
            _mode = "city"
            _city_id = "earth"
        else:
            try:
                _sys_spec = _find_sys(_system_id)
            except KeyError:
                _log.add(f"Save references unknown system '{_system_id}' — loading Earth city.")
                _mode = "city"
                _city_id = "earth"

        if _mode == "dungeon":
            # 1. Build space map (same layout as space mode).
            _space_map = solar_system_module.make_solar_system(system=_sys_spec)
            solar_system_module.current_solar_system_id = _system_id

            # Add bounty NPCs.
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
                if _bs.salvage_wreck:
                    # Non-combatant mission wreck: boardable, persists until
                    # the component is secured. Tagged with its spawn id so
                    # the boarding flow finds the mission + interior cache.
                    # No bounty_spawn_id — it must never auto-complete.
                    _ent.salvage_wreck_spawn_id = _bs.spawn_id
                    _space_map.entities.append(_ent)
                    continue
                if not _bs.squad_group_id:
                    _ent.bounty_spawn_id = _bs.spawn_id
                    # Restore intercept linkage so on_kill still drops the
                    # mission loot after a save/quit/continue (mirrors
                    # navigation._add_bounty_spawns_to_map).
                    if _bs.heist_spawn_id is not None:
                        _ent.heist_spawn_id = _bs.heist_spawn_id
                # Squad linkage for comms Attack (mirrors navigation.py).
                _ent.bounty_squad_id = _bs.squad_group_id or _bs.spawn_id
                # Restore auto-hail range on all members too (mirrors
                # navigation.py) so post-load behavior matches fresh spawn.
                _ent.bounty_comms_range = _bs.comms_warning_range
                _space_map.entities.append(_ent)

            # Add procedural NPCs.
            for _i, _ps in enumerate(_proc_spawns.get(_system_id, [])):
                try:
                    _espec = _find_npc(_ps.npc_id)
                except (KeyError, ImportError):
                    continue
                _saved_mids = _proc_mid_map.get(_system_id, [])
                _mid = (_saved_mids[_i] if _i < len(_saved_mids) and _saved_mids[_i]
                        else _ps.squad_id
                        or f"proc_loaded_{_system_id}_{_ps.npc_id}_{_i}")
                _ent = world.Entity(
                    char=_espec.char, fg=_espec.fg,
                    pos=_ps.pos, name=_espec.name,
                    width=1, height=1,
                    npc_ship_id=_ps.npc_id,
                )
                if getattr(_espec, 'base_speed', 0) > 0:
                    _ent.procedural_squad_id = _mid
                _space_map.entities.append(_ent)

            # Place the player's SHIP at the saved space position.
            _space_px = _dd.get("space_player_x", _pos_x)
            _space_py = _dd.get("space_player_y", _pos_y)
            if _owned_ship is not None:
                _ship_spec = ship_module.find_ship(_owned_ship.ship_id)
                _space_player_ent = world.Entity(
                    char=_ship_spec.char, fg=_ship_spec.fg,
                    pos=world.Position(_space_px, _space_py),
                    name=f"Your Ship: {ship_module.ship_display_name(_owned_ship)}",
                    ship_id=_owned_ship.ship_id, owned=True,
                )
            else:
                _space_player_ent = world.Entity(
                    char='@', fg=(255, 255, 255),
                    pos=world.Position(_space_px, _space_py), name='Player',
                )
            _space_map.entities.append(_space_player_ent)

            # 2. Rebuild dungeon map from saved data (shared helper —
            #    preserves ground-combat squads, heist loot, wreck anchors).
            _dungeon_map, _ = _dungeon_from_dict(_dd)

            # 3. Create dungeon player entity at saved position.
            _dungeon_player = world.Entity(
                char='@', fg=(255, 255, 255),
                pos=world.Position(_pos_x, _pos_y),
                name='Player',
            )
            _dungeon_map.entities.append(_dungeon_player)

            # 4. Set up return values.
            _game_map = _dungeon_map
            _player_ent = _dungeon_player
            # Store space map/player for ctx assembly later.
            _saved_space_map = _space_map
            _saved_space_player = _space_player_ent

    else:
        # --- City mode: load planet map ---
        from .data.planets import load_planet as planets_load_planet, hangar_anchor as _planet_anchor

        _game_map = planets_load_planet(_city_id)
        _player_ent = world.Entity(
            char='@', fg=(255, 255, 255),
            pos=world.Position(_pos_x, _pos_y), name='Player',
        )
        _game_map.entities.append(_player_ent)

        # Restore hangar ship at the planet's correct anchor position.
        if _owned_ship is not None:
            _ship_spec = ship_module.find_ship(_owned_ship.ship_id)
            _hangar = world.Entity(
                char=_ship_spec.char, fg=_ship_spec.fg,
                pos=_planet_anchor(_city_id),
                name=f"Your Ship: {ship_module.ship_display_name(_owned_ship)}",
                ship_id=_owned_ship.ship_id, owned=True,
            )
            _game_map.entities.append(_hangar)

    # --- Restore loot entities (space or city) ---
    # Skip for dungeon mode: dungeon entities (including loot) are already
    # restored from dungeon.entities above — appending map_loot too would
    # duplicate each loot entity on every save/load cycle.
    if _mode != "dungeon":
        for _ld in _data.get("map_loot", []) or []:
            _lx = _ld.get("x", 0)
            _ly = _ld.get("y", 0)
            _loot_e = world.Entity(
                char='%', fg=(255, 215, 0),
                pos=world.Position(_lx, _ly),
                name='Loot', width=1, height=1,
                loot_data=_ld.get("loot_data"),
            )
            if _ld.get("heist_mission", False):
                _loot_e.heist_mission = True
            _lmid = _ld.get("heist_mission_id")
            if _lmid:
                _loot_e.heist_mission_id = _lmid
            _game_map.entities.append(_loot_e)

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
    _ctx.militia_scanned = set(_data.get("militia_scanned", []) or [])
    # Ground stats: backward-compatible default of 10/10/10 (0-100 scale,
    # matching the ship-skill base of 10).
    _gsd = _data.get("ground_stats", {}) or {}
    from .character import GroundStats
    _ctx.ground_stats = GroundStats(
        reflexes=_gsd.get("reflexes", 10),
        strength=_gsd.get("strength", 10),
        stamina=_gsd.get("stamina", 10),
    )
    _ctx.equipped_ground_weapons = list(_data.get("equipped_ground_weapons", []) or [])
    _ctx.equipped_ground_armor = dict(_data.get("equipped_ground_armor", {}) or {})
    _ctx.ground_hp = _data.get("ground_hp", 23)
    _ctx.ground_max_hp = _data.get("ground_max_hp", 23)
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
    _ctx.npc_targets = _npc_targets
    _ctx.npc_paths = _npc_paths
    _ctx.current_city_id = _city_id
    _ctx._loaded_mode = _mode  # type: ignore[attr-defined]
    if _mode == "dungeon":
        _ctx._space_game_map = _saved_space_map  # type: ignore[attr-defined]
        _ctx._space_player = _saved_space_player  # type: ignore[attr-defined]

    # --- Restore persistent wreck interiors (salvage missions) ---
    # Each serialized interior carries its wreck's spawn id + entry spawn.
    for _k, _idict in (_data.get("interiors", {}) or {}).items():
        _imap, _ = _dungeon_from_dict(_idict)
        _ctx.interiors[str(_k)] = _imap
    # If the player is INSIDE a wreck (mode=dungeon), the active dungeon
    # map is the authoritative copy — overwrite the restored cache entry
    # with it so re-boarding after exit sees post-load progress (crew
    # killed, loot taken), not a stale deserialized twin of the same map.
    _cur_wsid = getattr(_game_map, 'wreck_spawn_id', None)
    if _cur_wsid is not None:
        _ctx.interiors[_cur_wsid] = _game_map

    # --- Restore RNG state ---
    _rng_state = _data.get("rng_state")
    if _rng_state is not None:
        from .engine import RNG
        RNG.setstate((_rng_state[0], tuple(_rng_state[1]), _rng_state[2]))

    return _ctx
