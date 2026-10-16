"""Mission and spawn save-parsing (doc 102.4.1 ratchet split).

The parse family rebuilding active missions, mission boards,
bounty spawns, and procedural spawns from a save payload — lifted
from :mod:`saveload` when the chrome save fields crossed the
1000-line ratchet. ``saveload`` re-exports every name; tests and
tools import them there.
"""

from __future__ import annotations

from . import world


def _parse_pos(raw) -> tuple[int, int]:
    """Parse a serialized position from either [x, y] list or {x, y} dict."""
    if isinstance(raw, dict):
        return (raw.get("x", 0), raw.get("y", 0))
    if isinstance(raw, (list, tuple)) and len(raw) >= 2:
        return (raw[0], raw[1])
    return (0, 0)


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
                defeated=bs.get("defeated", False),
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
                flies_dark=bool(ps.get("flies_dark", False)),
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
