"""Mission runtime package.

The package preserves the historical ``spacehack.mission`` API while the
implementation is being split by responsibility. Static mission catalogs
remain in :mod:`spacehack.data.missions`.
"""
from __future__ import annotations

from ._models import ActiveMission, MissionBoard, MissionStatus, MAX_ACTIVE_MISSIONS
from ._legacy import (
    abort_mission,
    active_is_deliverable_at,
    board_key,
    board_offerings,
    board_remove,
    board_return_static,
    commit_accept_mission,
    complete_mission,
    destination_system_name,
    ensure_board,
    fill_empty_slots,
    find_board_for_mission,
    find_deliverable,
    find_deliverable_missions,
    find_mission,
    generate_bar_mission,
    generate_bounty_mission,
    generate_delivery_mission,
    is_deliverable_at,
    list_missions,
    mission_spec_from_dict,
    missions_offered_by,
    refresh_all_boards,
    release_mission_cargo,
    system_display_name,
    system_name_for_planet,
    try_accept_mission,
    _planet_npc_ids,
    _planet_to_system,
)
from ._legacy import MissionSpec

__all__ = [
    "ActiveMission",
    "MissionBoard",
    "MissionStatus",
    "MAX_ACTIVE_MISSIONS",
    "MissionSpec",
    "find_mission",
    "list_missions",
    "missions_offered_by",
    "try_accept_mission",
    "commit_accept_mission",
    "is_deliverable_at",
    "active_is_deliverable_at",
    "find_deliverable",
    "find_deliverable_missions",
    "release_mission_cargo",
    "abort_mission",
    "complete_mission",
    "board_key",
    "ensure_board",
    "find_board_for_mission",
    "mission_spec_from_dict",
    "board_offerings",
    "fill_empty_slots",
    "board_remove",
    "board_return_static",
    "refresh_all_boards",
    "system_display_name",
    "system_name_for_planet",
    "destination_system_name",
    "generate_delivery_mission",
    "generate_bounty_mission",
    "generate_bar_mission",
    "_planet_npc_ids",
    "_planet_to_system",
]
