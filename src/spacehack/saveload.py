"""Save / load — JSON serialization of GameContext.

Single autosave file at ``~/.spacehack/saves/autosave.json``.
Serialization converts GameContext fields to a JSON-safe dict,
skipping non-serializable runtime context, game_map, and entities.
On load, game_map is regenerated from saved position + system info.

Design doc: ``docs/design/in_progress/03_DESIGN_GAME_INFRASTRUCTURE.md``
"""

from __future__ import annotations

import dataclasses
import json
from enum import Enum
from pathlib import Path

from . import world
from .game_context import GameContext
from .pygame_runtime import PygameContext
from .saveload_maps import _dungeon_from_dict, _dungeon_to_dict  # noqa: F401  # re-exported for tests/tools
from .saveload_maps import rebuild_game_map


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


def _stored_equipment_from_dict(raw: object):
    """Parse one stored ship-equipment save entry, ignoring malformed records."""
    if not isinstance(raw, dict):
        return None
    item_type = raw.get("item_type")
    item_id = raw.get("item_id")
    if item_type not in {"weapon", "module"} or not isinstance(item_id, str) or not item_id:
        return None
    try:
        if item_type == "weapon":
            from .data.weapons import find_weapon
            find_weapon(item_id)
        else:
            from .data.modules import find_module
            find_module(item_id)
    except (ImportError, KeyError):
        return None
    ammo_raw = raw.get("ammo")
    if ammo_raw is None:
        ammo = None
    else:
        try:
            ammo = int(ammo_raw)
        except (TypeError, ValueError):
            return None
    from . import ship as ship_module
    return ship_module.StoredEquipment(item_type, item_id, ammo)


def _ground_equipment_from_dict(raw: object):
    """Parse one stored ground-equipment entry, ignoring malformed records."""
    if not isinstance(raw, dict):
        return None
    item_type = raw.get("item_type")
    item_id = raw.get("item_id")
    if item_type not in {"weapon", "armor"} or not isinstance(item_id, str) or not item_id:
        return None
    try:
        if item_type == "weapon":
            from .data.ground_weapons import find_ground_weapon
            find_ground_weapon(item_id)
        else:
            from .data.ground_armor import find_ground_armor
            find_ground_armor(item_id)
    except (ImportError, KeyError):
        return None
    from .ground_equipment import StoredGroundEquipment
    return StoredGroundEquipment(item_type, item_id)


def _core_fields(ctx: GameContext) -> dict:
    """Serialize character, ship, mission, economy, and clock fields."""
    return {
        "character_info": _d(ctx.character_info),
        "message_history": [
            {"text": entry.text, "fg": list(entry.fg)}
            for entry in ctx.log.history()
        ],
        "stats": {
            "hp": ctx.stats.hp,
            "max_hp": ctx.stats.max_hp,
            "credits": ctx.stats.credits,
            "gunnery": ctx.stats.gunnery,
            "piloting": ctx.stats.piloting,
            "engineering": ctx.stats.engineering,
        },
        "player_owned_ship": _d(ctx.player_owned_ship),
        "ship_storage": _d(ctx.ship_storage),
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
    }


def _ground_fields(ctx: GameContext) -> dict:
    """Serialize ground combat and equipment fields."""
    return {
        "ground_stats": _d(ctx.ground_stats),
        "equipped_ground_weapons": _d(ctx.equipped_ground_weapons),
        "equipped_ground_armor": _d(ctx.equipped_ground_armor),
        "ground_armory_storage": _d(ctx.ground_armory_storage),
        "ground_expedition_inventory": _d(ctx.ground_expedition_inventory),
        "ground_armory_items": _d(ctx.ground_armory_items),
        "ground_expedition_items": _d(ctx.ground_expedition_items),
        "ground_hp": ctx.ground_hp,
        "ground_max_hp": ctx.ground_max_hp,
    }


def _quest_fields(ctx: GameContext) -> dict:
    """Serialize main-quest, tutorial, and extension state."""
    return {
        # Main quest state (save/load contract — see
        # docs/design/in_progress/07_DESIGN_MAIN_QUEST.md).
        "main_quest_progress": _d(ctx.main_quest_progress),
        "main_quest_unlocked_items": sorted(ctx.main_quest_unlocked_items),
        "main_quest_path": ctx.main_quest_path,
        "main_quest_backing": sorted(ctx.main_quest_backing),
        "main_quest_chain": ctx.main_quest_chain,
        "main_quest_gate": _d(ctx.main_quest_gate),
        "main_quest_pending_message": ctx.main_quest_pending_message,
        "main_quest_pending_objective": ctx.main_quest_pending_objective,
        "main_quest_complete": ctx.main_quest_complete,
        "main_quest_disclosure": ctx.main_quest_disclosure,
        "post_prison_orbit_seen": ctx.post_prison_orbit_seen,
        "post_prison_orbit_pending": ctx.post_prison_orbit_pending,
        "dungeon_extension": _d(ctx.dungeon_extension),
        # Tutorial mode (design doc 14): resume mid-script on Continue.
        "tutorial_mode": ctx.tutorial_mode,
        "tutorial_steps": sorted(ctx.tutorial_steps),
        "tutorial_complete": ctx.tutorial_complete,
    }


def _ctx_to_dict(ctx: GameContext) -> dict:
    """Serialize only the fields that survive a save/load cycle.

    Returns a flat dict — callers add mode / position / synced-spawn
    fields before writing to disk.
    """
    _data = _core_fields(ctx)
    _data.update(_ground_fields(ctx))
    _data.update(_quest_fields(ctx))
    return _data


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
                # Quest cache / salvage loot — which main-quest step
                # securing it completes (delve/salvage objectives).
                'main_quest_step_id': getattr(_e, 'main_quest_step_id', ''),
            })
    return _result


def _index_npc_entities(ctx: GameContext) -> dict[str, list]:
    """Index current-map entities by npc_ship_id for spawn position sync."""
    by_type: dict[str, list] = {}
    for e in ctx.game_map.entities:
        eid = getattr(e, 'npc_ship_id', '')
        if eid:
            by_type.setdefault(eid, []).append(e)
    return by_type


def _sync_spawn_entry(ctx, ps, by_type, synced_targets, synced_paths):
    """Return ``(pos, mid)`` for one spawn, or None if its entity died."""
    candidates = by_type.get(ps.npc_id, [])
    if not candidates:
        return None
    matched = candidates.pop(0)
    cur_pos, cur_mid = matched.pos, matched.procedural_squad_id
    target = ctx.npc_targets.get(cur_mid)
    if target is not None:
        synced_targets[cur_mid] = [target[0], target[1]]
    path = ctx.npc_paths.get(cur_mid)
    if path:
        synced_paths[cur_mid] = [[x, y] for x, y in path]
    return cur_pos, cur_mid


def _sync_procedural_spawns(ctx: GameContext, system_id: str) -> tuple:
    """Sync procedural spawn positions from live entities on the current map.

    ``move_npcs`` moves entities without updating ``ProceduralSpawn.pos``, so
    the spawn data holds the original spawn position. Entities are indexed by
    ``npc_ship_id`` and popped one-at-a-time so every spawn gets a different
    entity's position (the stacking bug). Returns
    ``(spawns, mids, targets, paths)``.
    """
    from .game_context import ProceduralSpawn

    synced_spawns: dict[str, list] = {}
    synced_mids: dict[str, list] = {}
    synced_targets: dict[str, list[int]] = {}
    synced_paths: dict[str, list] = {}
    for sys_id, spawns in ctx.procedural_spawns.items():
        # Only the current system's map is in ctx.game_map — other systems
        # keep their spawns as-is (no entity data to match).
        by_type = _index_npc_entities(ctx) if sys_id == system_id else {}
        updated: list = []
        mids: list = []
        for ps in spawns:
            if sys_id == system_id:
                synced = _sync_spawn_entry(ctx, ps, by_type, synced_targets, synced_paths)
                if synced is None:
                    continue  # entity was killed — drop its spawn
                cur_pos, cur_mid = synced
            else:
                cur_pos, cur_mid = ps.pos, ""
            updated.append(ProceduralSpawn(
                npc_id=ps.npc_id, pos=cur_pos, squad_id=ps.squad_id,
            ))
            mids.append(cur_mid)
        synced_spawns[sys_id] = updated
        synced_mids[sys_id] = mids
    return synced_spawns, synced_mids, synced_targets, synced_paths


def _write_dungeon_and_interiors(ctx, data, mode, space_player_pos) -> None:
    """Serialize the active dungeon and persistent wreck interiors."""
    if mode == "dungeon":
        data["dungeon"] = _dungeon_to_dict(ctx.game_map, space_player_pos)
    # The autosave IS the on-disk cache: every boarded wreck interior is
    # serialized here so crew stay dead, loot stays taken, and fog stays
    # revealed across save/quit/continue.
    if ctx.interiors:
        data["interiors"] = {
            key: _dungeon_to_dict(value, None)
            for key, value in ctx.interiors.items()
        }


def _write_rng_state(data: dict) -> None:
    """Persist the RNG stream state and the run's initial seed."""
    from .engine import INIT_SEED, RNG
    rng_state = RNG.getstate()
    data["rng_state"] = [rng_state[0], list(rng_state[1]), rng_state[2]]
    data["init_seed"] = INIT_SEED


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
    _synced_spawns, _synced_mids, _synced_targets, _synced_paths = (
        _sync_procedural_spawns(ctx, system_id)
    )
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

    _write_dungeon_and_interiors(ctx, _data, mode, space_player_pos)
    _write_rng_state(_data)

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


@dataclasses.dataclass
class _ParsedSave:
    """Parsed save header (everything except the map rebuild)."""

    character_info: object
    stats: object
    owned_ship: object
    active_missions: list
    mission_boards: dict
    bounty_spawns: dict
    proc_spawns: dict
    proc_mid_map: dict
    npc_targets: dict
    npc_paths: dict
    counters: object
    economy_state: dict
    generated_missions: dict
    faction_reputation: dict
    log: object


def _parse_stats(data: dict):
    """Rebuild :class:`hud.HudStats` from the save payload."""
    from . import hud
    s = data["stats"]
    return hud.HudStats(
        hp=s["hp"], max_hp=s["max_hp"], credits=s["credits"],
        gunnery=s.get("gunnery", 0),
        piloting=s.get("piloting", 0),
        engineering=s.get("engineering", 0),
    )


def _parse_owned_ship(data: dict):
    """Rebuild the player's :class:`ship.OwnedShip`, or None."""
    from . import ship as ship_module
    osh = data.get("player_owned_ship")
    if osh is None or not osh.get("ship_id"):
        return None
    # weapon_ammo migration: new saves key ammo by weapon SLOT index
    # (ints serialized as strings by _d). Pre-fix saves keyed it by
    # weapon id (shared magazine bug) — those entries are dropped so
    # __post_init__ seeds each installed launcher a fresh full mag.
    ammo_raw = osh.get("weapon_ammo", {}) or {}
    ammo: dict[int, int] = {}
    for k, v in ammo_raw.items():
        try:
            ammo[int(k)] = int(v)
        except (TypeError, ValueError):
            continue  # legacy weapon-id key — discard
    return ship_module.OwnedShip(
        ship_id=osh["ship_id"],
        display_name=osh.get("display_name"),
        fuel=osh.get("fuel", 0),
        hull_damage_pct=osh.get("hull_damage_pct", 0),
        weapons=tuple(osh.get("weapons", ()) or ()),
        modules=tuple(osh.get("modules", ()) or ()),
        inventory=osh.get("inventory", {}) or {},
        mission_reserved=osh.get("mission_reserved", 0),
        weapon_ammo=ammo,
    )


def _active_mission_from_dict(am: dict):
    """Rebuild one active mission from a serialized dict."""
    from . import mission as mission_module
    time_dl = None
    if am.get("time_deadline"):
        td = am["time_deadline"]
        time_dl = (int(td[0]), int(td[1]), int(td[2]))
    return mission_module.ActiveMission(
        mission_id=am["mission_id"],
        is_procedural=am.get("is_procedural", False),
        status=mission_module.MissionStatus[am["status"]]
        if am.get("status") else mission_module.MissionStatus.IN_PROGRESS,
        title=am.get("title", ""),
        required_cargo_size=am.get("required_cargo_size", 0),
        delivery_target_npc_id=am.get("delivery_target_npc_id", ""),
        delivery_target_planet_id=am.get("delivery_target_planet_id", ""),
        deadline_days=am.get("deadline_days", 0),
        accept_day=am.get("accept_day", 1),
        time_deadline=time_dl,
        reward_credits=am.get("reward_credits", 0),
        reward_xp=am.get("reward_xp", 0),
        early_bonus_pct=am.get("early_bonus_pct", 0),
        bounty_spawn_id=am.get("bounty_spawn_id"),
        target_enemy_id=am.get("target_enemy_id"),
        target_system_id=am.get("target_system_id"),
        bounty_target_name=am.get("bounty_target_name"),
        bounty_target_squad_size=am.get("bounty_target_squad_size", 1),
        bounty_target_loadout_pct=am.get("bounty_target_loadout_pct", 0),
        bounty_wingmate_enemy_id=am.get("bounty_wingmate_enemy_id"),
        tier=am.get("tier", 1),
        heist_target_good_id=am.get("heist_target_good_id"),
        heist_good_secured=am.get("heist_good_secured", False),
        salvage_wreck_enemy_id=am.get("salvage_wreck_enemy_id"),
        salvage_layout_id=am.get("salvage_layout_id"),
        salvage_wreck_spawn_id=am.get("salvage_wreck_spawn_id"),
        is_smuggle=am.get("is_smuggle", False),
        smuggle_good_id=am.get("smuggle_good_id"),
        main_quest_step_id=am.get("main_quest_step_id", ""),
    )


def _parse_active_missions(data: dict) -> list:
    """Rebuild the player's active missions."""
    return [
        _active_mission_from_dict(am)
        for am in (data.get("player_active_missions", ()) or ())
    ]


def _parse_mission_boards(data: dict) -> dict:
    """Rebuild mission boards, re-keying legacy npc_id keys automatically."""
    from . import mission as mission_module
    boards: dict[str, mission_module.MissionBoard] = {}
    for npc_id, bd in (data.get("mission_boards", {}) or {}).items():
        board = mission_module.MissionBoard(
            npc_id=bd.get("npc_id", npc_id),
            slots=list(bd.get("slots", []) or []),
            max_slots=bd.get("max_slots", 5),
            planet_id=bd.get("planet_id", ""),
        )
        board.last_refresh_month = bd.get("last_refresh_month", 1)
        boards[mission_module.board_key(board.npc_id, board.planet_id)] = board
    return boards


def _parse_bounty_spawns(data: dict) -> dict:
    """Rebuild bounty spawns from the save payload."""
    from .game_context import BountySpawn
    spawns: dict[str, list] = {}
    for sys_id, raw_spawns in (data.get("bounty_spawns", {}) or {}).items():
        spawns[sys_id] = []
        for bs in (raw_spawns or []):
            px, py = _parse_pos(bs.get("pos", [0, 0]))
            spawns[sys_id].append(BountySpawn(
                spawn_id=bs["spawn_id"],
                enemy_id=bs.get("enemy_id", ""),
                pos=world.Position(px, py),
                bounty_target_name=bs.get("bounty_target_name"),
                squad_size=bs.get("squad_size", 1),
                loadout_pct=bs.get("loadout_pct", 0),
                squad_group_id=bs.get("squad_group_id"),
                comms_warning_range=bs.get("comms_warning_range", 0),
                heist_spawn_id=bs.get("heist_spawn_id"),
                salvage_wreck=bs.get("salvage_wreck", False),
            ))
    return spawns


def _parse_procedural_spawns(data: dict) -> tuple:
    """Rebuild procedural spawns, movement IDs, targets, and paths."""
    from .game_context import ProceduralSpawn
    proc_data = data.get("procedural_spawns", {}) or {}
    proc_mids = data.get("procedural_mids", {}) or {}
    proc_spawns: dict[str, list] = {}
    for sys_id, slist in proc_data.items():
        proc_spawns[sys_id] = []
        for ps in (slist or []):
            px, py = _parse_pos(ps.get("pos", [0, 0]))
            proc_spawns[sys_id].append(ProceduralSpawn(
                npc_id=ps.get("npc_id", ""),
                pos=world.Position(px, py),
                squad_id=ps.get("squad_id"),
            ))
    mid_map: dict[str, list[str]] = {
        sys_id: [str(m) for m in mids] for sys_id, mids in (proc_mids or {}).items()
    }
    targets: dict[str, tuple[int, int]] = {}
    for mid, tgt in (data.get("npc_targets", {}) or {}).items():
        if isinstance(tgt, list) and len(tgt) >= 2:
            targets[str(mid)] = (int(tgt[0]), int(tgt[1]))
    paths: dict[str, list[tuple[int, int]]] = {}
    for mid, pth in (data.get("npc_paths", {}) or {}).items():
        paths[str(mid)] = [
            (int(p[0]), int(p[1])) for p in pth if isinstance(p, list) and len(p) >= 2
        ]
    return proc_spawns, mid_map, targets, paths


def _parse_counters(data: dict):
    """Rebuild the player counters."""
    from .game_context import PlayerCounters
    pc = data.get("player_counters", {}) or {}
    return PlayerCounters(
        laser_shots=pc.get("laser_shots", 0),
        missile_shots=pc.get("missile_shots", 0),
        plasma_shots=pc.get("plasma_shots", 0),
        merchant_kills=pc.get("merchant_kills", 0),
        total_kills=pc.get("total_kills", 0),
        bounties_completed=pc.get("bounties_completed", 0),
        deliveries_completed=pc.get("deliveries_completed", 0),
        total_damage_taken=pc.get("total_damage_taken", 0),
        combat_flees=pc.get("combat_flees", 0),
    )


def _parse_economy_and_generated(data: dict) -> tuple:
    """Rebuild economy state and generated mission specs."""
    from . import mission as mission_module
    econ = data.get("economy_state", {}) or {}
    generated: dict[str, mission_module.MissionSpec] = {}
    for mid, md in (data.get("generated_missions", {}) or {}).items():
        try:
            generated[mid] = mission_module.mission_spec_from_dict(md)
        except (TypeError, AttributeError):
            continue  # corrupt/stale entry — board_offerings skips it
    return econ, generated


def _parse_log(data: dict):
    """Rebuild the message log from the save payload."""
    from . import message_log
    log = message_log.MessageLog(capacity=6)
    history = []
    for entry in (data.get("message_history", []) or []):
        if not isinstance(entry, dict) or not isinstance(entry.get("text"), str):
            continue
        fg = entry.get("fg", message_log.COLOR_MESSAGE)
        if not isinstance(fg, (list, tuple)) or len(fg) != 3:
            fg = message_log.COLOR_MESSAGE
        try:
            color = tuple(max(0, min(255, int(channel))) for channel in fg)
        except (TypeError, ValueError):
            color = message_log.COLOR_MESSAGE
        history.append(message_log.MessageEntry(entry["text"], color))
    log.load_history(history)
    log.add("Game loaded.")
    return log


def _parse_save_header(data: dict) -> _ParsedSave:
    """Parse everything from the save payload except the map rebuild."""
    proc_spawns, proc_mid_map, npc_targets, npc_paths = _parse_procedural_spawns(data)
    economy_state, generated_missions = _parse_economy_and_generated(data)
    return _ParsedSave(
        character_info=data["character_info"],
        stats=_parse_stats(data),
        owned_ship=_parse_owned_ship(data),
        active_missions=_parse_active_missions(data),
        mission_boards=_parse_mission_boards(data),
        bounty_spawns=_parse_bounty_spawns(data),
        proc_spawns=proc_spawns,
        proc_mid_map=proc_mid_map,
        npc_targets=npc_targets,
        npc_paths=npc_paths,
        counters=_parse_counters(data),
        economy_state=economy_state,
        generated_missions=generated_missions,
        faction_reputation=data.get("faction_reputation", {}) or {},
        log=_parse_log(data),
    )


def _parse_ship_storage(data: dict) -> list:
    """Rebuild ship storage, ignoring malformed records."""
    return [
        stored
        for entry in (data.get("ship_storage", []) or [])
        if (stored := _stored_equipment_from_dict(entry)) is not None
    ]


def _restore_loot_entities(data: dict, game_map) -> None:
    """Restore map loot entities (dungeon loot is already restored)."""
    for ld in data.get("map_loot", []) or []:
        loot = world.Entity(
            char='%', fg=(255, 215, 0),
            pos=world.Position(ld.get("x", 0), ld.get("y", 0)),
            name='Loot', width=1, height=1,
            loot_data=ld.get("loot_data"),
        )
        if ld.get("heist_mission", False):
            loot.heist_mission = True
        lmid = ld.get("heist_mission_id")
        if lmid:
            loot.heist_mission_id = lmid
        qsid = ld.get("main_quest_step_id")
        if qsid:
            loot.main_quest_step_id = qsid
        game_map.entities.append(loot)


def _restore_core_fields(ctx: GameContext, data: dict, parsed: _ParsedSave, rebuilt) -> None:
    """Restore the mission/economy/clock scalar fields onto ``ctx``."""
    ctx.ship_storage = _parse_ship_storage(data)
    ctx.completed_mission_ids = set(data.get("completed_mission_ids", []) or [])
    ctx.mission_boards = parsed.mission_boards
    ctx.bounty_spawns = parsed.bounty_spawns
    ctx.faction_reputation = parsed.faction_reputation
    ctx.militia_scanned = set(data.get("militia_scanned", []) or [])
    ctx.player_counters = parsed.counters
    ctx.economy_state = parsed.economy_state
    ctx.generated_missions = parsed.generated_missions
    ctx.procedural_spawns = parsed.proc_spawns
    ctx.npc_targets = parsed.npc_targets
    ctx.npc_paths = parsed.npc_paths
    ctx.current_city_id = rebuilt.city_id


def _restore_ground_fields(ctx: GameContext, data: dict) -> None:
    """Restore ground combat and equipment fields."""
    from .character import GroundStats
    gsd = data.get("ground_stats", {}) or {}
    ctx.ground_stats = GroundStats(
        reflexes=gsd.get("reflexes", 10),
        strength=gsd.get("strength", 10),
        stamina=gsd.get("stamina", 10),
    )
    ctx.equipped_ground_weapons = _parse_equipped_ground_weapons(
        data.get("equipped_ground_weapons"),
    )
    ctx.equipped_ground_armor = dict(data.get("equipped_ground_armor", {}) or {})
    legacy_storage = data.get("ground_equipment_storage", []) or []
    armory_raw = data.get("ground_armory_storage", legacy_storage) or []
    ctx.ground_armory_storage = [
        stored
        for entry in armory_raw
        if (stored := _ground_equipment_from_dict(entry)) is not None
    ]
    ctx.ground_expedition_inventory = [
        stored
        for entry in (data.get("ground_expedition_inventory", []) or [])
        if (stored := _ground_equipment_from_dict(entry)) is not None
    ]
    ctx.ground_armory_items = _parse_ground_item_stacks(
        data.get("ground_armory_items"),
    )
    ctx.ground_expedition_items = _parse_ground_item_stacks(
        data.get("ground_expedition_items"),
    )
    ctx.ground_hp = data.get("ground_hp", 23)
    ctx.ground_max_hp = data.get("ground_max_hp", 23)


def _parse_ground_item_stacks(raw) -> list:
    """Rebuild field-item stacks, ignoring malformed records."""
    from .ground_equipment import parse_item_stack

    return [
        stack
        for entry in (raw or [])
        if (stack := parse_item_stack(entry)) is not None
    ]


def _parse_equipped_ground_weapons(raw) -> list:
    """Rebuild active weapon instances, migrating legacy string ids."""
    from .ground_equipment import parse_weapon_instance

    return [
        instance
        for entry in (raw or [])
        if (instance := parse_weapon_instance(entry)) is not None
    ]


def _restore_progression_fields(ctx: GameContext, data: dict) -> None:
    """Restore XP, skills, traits, and the game clock."""
    ctx.player_xp = data.get("player_xp", 0)
    ctx.player_level = data.get("player_level", 1)
    ctx.player_skill_points = data.get("player_skill_points", 0)
    ctx.player_gunnery_bonus = data.get("player_gunnery_bonus", 0)
    ctx.player_piloting_bonus = data.get("player_piloting_bonus", 0)
    ctx.player_engineering_bonus = data.get("player_engineering_bonus", 0)
    ctx.player_traits = list(data.get("player_traits", []) or [])
    ctx.time_day = data.get("time_day", 1)
    ctx.time_month = data.get("time_month", 1)
    ctx.time_year = data.get("time_year", 2200)
    ctx.move_counter = data.get("move_counter", 0)


def _restore_dungeon_extension(ctx: GameContext, data: dict) -> None:
    """Restore the dungeon extension state, if present."""
    from .game_context import DungeonExtensionState
    extension_data = data.get("dungeon_extension")
    if not (isinstance(extension_data, dict) and extension_data.get("extension_id")):
        return
    parent_position = extension_data.get("parent_position")
    parent_pos = None
    if isinstance(parent_position, (list, tuple)) and len(parent_position) >= 2:
        parent_pos = world.Position(int(parent_position[0]), int(parent_position[1]))
    power_restored = bool(extension_data.get("power_restored", False))
    state_flags = set(extension_data.get("state_flags", []) or [])
    if power_restored:
        state_flags.add("engineering_power")
    ctx.dungeon_extension = DungeonExtensionState(
        extension_id=str(extension_data["extension_id"]),
        current_floor=int(extension_data.get("current_floor", 1)),
        active=bool(extension_data.get("active", False)),
        parent_map_key=str(extension_data.get("parent_map_key", "")),
        parent_position=parent_pos,
        activated_events=set(extension_data.get("activated_events", []) or []),
        event_positions={
            str(event_id): [int(point[0]), int(point[1])]
            for event_id, point in (extension_data.get("event_positions", {}) or {}).items()
            if isinstance(point, (list, tuple)) and len(point) >= 2
        },
        power_restored=power_restored,
        state_flags=state_flags,
    )


def _restore_quest_and_tutorial(ctx: GameContext, data: dict) -> None:
    """Restore main-quest, tutorial, and dungeon-extension state."""
    ctx.main_quest_progress = dict(data.get("main_quest_progress", {}) or {})
    ctx.main_quest_unlocked_items = set(data.get("main_quest_unlocked_items", []) or [])
    ctx.main_quest_path = data.get("main_quest_path", "")
    ctx.main_quest_backing = set(data.get("main_quest_backing", []) or [])
    ctx.main_quest_chain = data.get("main_quest_chain", "")
    gate_raw = data.get("main_quest_gate", {}) or {}
    ctx.main_quest_gate = {
        str(k): tuple(int(v) for v in v)
        for k, v in gate_raw.items()
        if isinstance(v, (list, tuple)) and len(v) == 3
    }
    ctx.main_quest_pending_message = data.get("main_quest_pending_message", "")
    ctx.main_quest_pending_objective = data.get("main_quest_pending_objective", "")
    ctx.main_quest_complete = data.get("main_quest_complete", False)
    ctx.main_quest_disclosure = data.get("main_quest_disclosure", "")
    ctx.post_prison_orbit_seen = bool(data.get("post_prison_orbit_seen", False))
    ctx.post_prison_orbit_pending = bool(data.get("post_prison_orbit_pending", False))
    ctx.tutorial_mode = bool(data.get("tutorial_mode", False))
    ctx.tutorial_steps = set(data.get("tutorial_steps", []) or [])
    ctx.tutorial_complete = bool(data.get("tutorial_complete", False))
    _restore_dungeon_extension(ctx, data)


def _active_interior_key(ctx: GameContext, rebuilt) -> str:
    """Resolve the interior cache key for the active dungeon map."""
    game_map = rebuilt.game_map
    active_key = getattr(game_map, "interior_cache_key", "")
    if not active_key and getattr(game_map, "wreck_spawn_id", None) is not None:
        active_key = game_map.wreck_spawn_id
    if not active_key and (
        ctx.dungeon_extension is not None and ctx.dungeon_extension.active
    ):
        from .dungeon_extensions import floor_key as _extension_floor_key
        active_key = _extension_floor_key(
            ctx.dungeon_extension.extension_id, ctx.dungeon_extension.current_floor,
        )
    # Legacy planet-surface saves predate interior_cache_key. Restrict
    # migration to maps carrying an unambiguous extension marker; a normal
    # derelict has neither marker and is never rebound to a surface.
    if not active_key and (
        getattr(game_map, "extension_entry_id", "")
        or getattr(game_map, "mars_stairs_pos", None) is not None
    ):
        active_key = f"surface:{rebuilt.city_id}"
    return active_key


def _restore_interiors(ctx: GameContext, data: dict, rebuilt) -> None:
    """Restore persistent wreck interiors and rebind the active cache entry."""
    for key, idict in (data.get("interiors", {}) or {}).items():
        imap, _ = _dungeon_from_dict(idict)
        ctx.interiors[str(key)] = imap
    # The active dungeon is authoritative when Continue resumes inside a
    # cached interior. Rebind the corresponding cache key to that exact
    # object so identity-based transition lookup works after deserialization.
    if rebuilt.mode == "dungeon":
        active_key = _active_interior_key(ctx, rebuilt)
        if active_key:
            ctx.interiors[active_key] = rebuilt.game_map
    cur_wsid = getattr(rebuilt.game_map, 'wreck_spawn_id', None)
    if cur_wsid is not None:
        ctx.interiors[cur_wsid] = rebuilt.game_map
    extension_state = ctx.dungeon_extension
    if extension_state is not None and extension_state.active:
        from .dungeon_extensions import (
            _ensure_floor_connections,
            floor_key as _extension_floor_key,
        )
        _ensure_floor_connections(
            rebuilt.game_map, extension_state.extension_id, extension_state.current_floor,
        )
        if extension_state.power_restored:
            rebuilt.game_map.power_restored = True
        ctx.interiors[_extension_floor_key(
            extension_state.extension_id, extension_state.current_floor,
        )] = rebuilt.game_map


def _restore_quest_npcs(ctx: GameContext, rebuilt) -> None:
    """Spawn quest-conditional NPCs onto the rebuilt map."""
    from . import main_quest as _mq
    _mq.spawn_quest_npcs(ctx, rebuilt.game_map, rebuilt.city_id)


def _restore_rng_and_seed(data: dict) -> None:
    """Restore the RNG stream and the run's initial seed."""
    from .engine import RNG, set_init_seed
    rng_state = data.get("rng_state")
    if rng_state is not None:
        RNG.setstate((rng_state[0], tuple(rng_state[1]), rng_state[2]))
    init_seed = data.get("init_seed")
    if init_seed is not None:
        set_init_seed(int(init_seed))


def _assemble_context(context, data: dict, parsed: _ParsedSave, rebuilt) -> GameContext:
    """Build and fully restore a :class:`GameContext` from parsed save data."""
    ctx = GameContext(
        context=context,
        character_info=parsed.character_info,
        log=parsed.log,
        game_map=rebuilt.game_map,
        player=rebuilt.player_ent,
        stats=parsed.stats,
        player_owned_ship=parsed.owned_ship,
        player_active_missions=parsed.active_missions,
    )
    if rebuilt.mode != "dungeon":
        _restore_loot_entities(data, rebuilt.game_map)
    _restore_core_fields(ctx, data, parsed, rebuilt)
    _restore_ground_fields(ctx, data)
    _restore_progression_fields(ctx, data)
    _restore_quest_and_tutorial(ctx, data)
    ctx._loaded_mode = rebuilt.mode  # type: ignore[attr-defined]
    if rebuilt.mode == "dungeon":
        ctx._space_game_map = rebuilt.space_map  # type: ignore[attr-defined]
        ctx._space_player = rebuilt.space_player  # type: ignore[attr-defined]
    _restore_interiors(ctx, data, rebuilt)
    _restore_quest_npcs(ctx, rebuilt)
    _restore_rng_and_seed(data)
    return ctx


def load_game(context: PygameContext) -> GameContext | None:
    """Load the autosave and reconstruct a GameContext.

    Returns None if no save exists or the file is corrupted.
    """
    data = _load_json(_autosave_path())
    if data is None:
        return None

    parsed = _parse_save_header(data)
    rebuilt = rebuild_game_map(
        data,
        owned_ship=parsed.owned_ship,
        log=parsed.log,
        pos_x=data.get("player_pos_x", 13),
        pos_y=data.get("player_pos_y", 17),
        mode=data.get("current_mode", "city"),
        city_id=data.get("current_city_id", "earth"),
        system_id=data.get("current_system_id", "sol"),
        bounty_spawns=parsed.bounty_spawns,
        proc_spawns=parsed.proc_spawns,
        proc_mid_map=parsed.proc_mid_map,
    )
    return _assemble_context(context, data, parsed, rebuilt)
