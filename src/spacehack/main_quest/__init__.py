"""Main quest runtime: step lifecycle, NPC dialogue, objectives, overlays.

Package split (per knowledge.md ~1,000-line guardrail):
  handlers.py    — objective-type handler registry (dispatch table)
  _scenes.py     — scene registry (step.scene id → cutscene implementation)
  _core.py       — step lifecycle + smuggle crate mechanics (~250 lines)
  _dialogue.py   — NPC talk integration + quest option resolution (~180 lines)
  _objectives.py — delve / visit / bounty / salvage delivery hooks (~200 lines)
  _heat.py       — faction-specific heat hooks (~60 lines)
  _gates.py      — time gating + one-way summons (~45 lines)
  _spawns.py     — quest-tagged bounty/salvage spawn management (~95 lines)
  _breadcrumb.py — quest-log objective display (~35 lines)
  _act0.py       — signal trigger, Mars door, full-screen overlays (~720 lines)
  _act1.py       — post-prison Mars-orbit disclosure scene

All well under the 1,000-line threshold.
"""

from ._core import (
    STATUS_AVAILABLE,
    STATUS_ACTIVE,
    STATUS_COMPLETED,
    step_status,
    start_step,
    complete_step,
)
from ._dialogue import (
    resolve_npc_dialogue,
    quest_option_for,
    trigger_dialogue,
)
from ._objectives import (
    secure_quest_loot,
    maybe_complete_visit,
    maybe_complete_bounty,
    find_salvage_step_for_spawn,
    fail_smuggle_step,
    show_step_readout,
    complete_step_by_type,
)
from ._heat import (
    charged_cell_in_sol,
    bar_heat_active,
    consortium_heat_active,
)
from ._gates import (
    check_quest_gates,
)
from ._spawns import (
    ensure_quest_spawns,
)
from ._breadcrumb import (
    current_main_quest_objective,
)
from ._scenes import (
    play_scene,
    registered_scene_ids,
)
from ._act0 import (
    OfferOutcome,
    maybe_trigger_signal,
    prepare_mars_surface,
    bump_mars_door,
    start_prison_objective,
    prepare_delve_site,
    mars_exploration_unlocked,
    delve_site_unlocked,
    surface_exploration_unlocked,
    seat_quest_npcs_in_interior,
    maybe_continue_chain,
    show_prologue_transmission,
    show_quest_summon,
    show_quest_readout,
    show_sealed_door_overlay,
    show_help_offer,
    show_gate_popup,
)
from ._act1 import (
    OrbitDisclosure,
    maybe_show_post_prison_orbit,
)
