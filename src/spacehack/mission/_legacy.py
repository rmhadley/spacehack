"""Mission runtime layer: lifecycle state + accept/deliver/complete/abort.

Missions live in two layers:

  * :mod:`spacehack.data.missions` - the static catalog (the
    :class:`MissionSpec` dataclass + per-faction ``MISSIONS`` tuples
    + :func:`find_mission` / :func:`missions_offered_by` lookup
    helpers). Adding a new mission is a one-file edit there.
  * Here - board management and procedural mission generation. Lifecycle
    mutations live in :mod:`spacehack.mission._lifecycle`.

This module re-exports :class:`MissionSpec`, :func:`find_mission`,
and :func:`missions_offered_by` from :mod:`spacehack.data.missions`
so the dispatcher's ``mission_module.MissionSpec`` references keep
working without a second import line.
"""

from __future__ import annotations

from ..data.missions import MissionSpec, find_mission, list_missions, missions_offered_by
from ._models import ActiveMission, MissionStatus, MAX_ACTIVE_MISSIONS
from ._proc_delivery import generate_delivery_mission
from ._proc_bounty import generate_bounty_mission
from ._proc_bar import generate_bar_mission
from ._proc_shared import _planet_npc_ids, _planet_to_system
from ._board import (
    board_offerings,
    board_remove,
    board_return_static,
    ensure_board,
    fill_empty_slots,
    refresh_all_boards,
)
from ._lifecycle import (
    abort_mission,
    commit_accept_mission,
    complete_mission,
    release_mission_cargo,
    try_accept_mission,
)
from ._helpers import (
    active_is_deliverable_at,
    board_key,
    destination_system_name,
    find_board_for_mission,
    find_deliverable,
    find_deliverable_missions,
    is_deliverable_at,
    system_display_name,
    system_name_for_planet,
)











































# ---------------------------------------------------------------------------
# Procedural delivery mission generator
# ---------------------------------------------------------------------------

















# ---------------------------------------------------------------------------
# Procedural bounty mission generator
# ---------------------------------------------------------------------------


















# ---------------------------------------------------------------------------
# Procedural bar mission generator
# ---------------------------------------------------------------------------

# Heist goods pool — trade good IDs used as intercept loot / salvage components.

# Merchant ship pool by tier (intercept targets).

# Pirate patrol pool by tier (salvage guards).

# Wreck + layout by tier (salvage boarding).

# Hop-range tables for bar mission types.# Dispatch table for bar mission type -> sub-generator.
















# Re-exports so consumers can keep using ``mission_module.MissionSpec``
# etc. without a second import line.
__all__ = [
    "ActiveMission",
    "MissionSpec",
    "MissionStatus",
    "MAX_ACTIVE_MISSIONS",
    "release_mission_cargo",
    "abort_mission",
    "active_is_deliverable_at",
    "commit_accept_mission",
    "complete_mission",
    "find_mission",
    "find_deliverable",
    "find_deliverable_missions",
    "is_deliverable_at",
    "list_missions",
    "missions_offered_by",
    "try_accept_mission",
    "ensure_board",
    "board_key",
    "find_board_for_mission",
    "board_offerings",
    "fill_empty_slots",
    "board_remove",
    "board_return_static",
    "refresh_all_boards",
    "generate_delivery_mission",
    "generate_bounty_mission",
    "generate_bar_mission",
    "_planet_npc_ids",
    "_planet_to_system",
    "system_display_name",
    "system_name_for_planet",
    "destination_system_name",
]
