"""Mission runtime package.

The package preserves the historical ``spacehack.mission`` API while the
implementation is being split by responsibility. Static mission catalogs
remain in :mod:`spacehack.data.missions`.
"""
from __future__ import annotations

from ._models import ActiveMission, MissionBoard, MissionStatus, MAX_ACTIVE_MISSIONS
from ._helpers import (
    active_is_deliverable_at,
    board_key,
    destination_system_name,
    find_board_for_mission,
    find_deliverable,
    find_deliverable_missions,
    is_deliverable_at,
    mission_spec_from_dict,
    system_display_name,
    system_name_for_planet,
)
from ._proc_shared import _planet_npc_ids, _planet_to_system
from ._proc_delivery import generate_delivery_mission
from ._proc_bounty import generate_bounty_mission
from ._lifecycle import (
    abort_mission,
    commit_accept_mission,
    complete_mission,
    release_mission_cargo,
    try_accept_mission,
)
from ._board import (
    board_offerings,
    board_remove,
    board_return_static,
    ensure_board,
    fill_empty_slots,
    refresh_all_boards,
)
from ._legacy import (
    find_mission,
    generate_bar_mission,
    list_missions,
    missions_offered_by,
)
from ..data.missions import MissionSpec

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
