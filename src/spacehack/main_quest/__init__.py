"""Main quest runtime: step lifecycle, NPC dialogue, objectives, overlays.

Package split (per knowledge.md ~1,000-line guardrail):
  _core.py       — step lifecycle + smuggle crate mechanics (~210 lines)
  _dialogue.py   — NPC talk integration + quest option resolution (~130 lines)
  _objectives.py — delve / visit / bounty / smuggle delivery hooks (~130 lines)
  _heat.py       — faction-specific heat hooks (~50 lines)
  _gates.py      — time gating + one-way summons (~50 lines)
  _spawns.py     — quest-tagged bounty/salvage spawn management (~50 lines)
  _breadcrumb.py — quest-log objective display (~35 lines)
  _act0.py       — signal trigger, Mars door, full-screen overlays (~350 lines)

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
    maybe_complete_smuggle_delivery,
    fail_smuggle_step,
    show_step_readout,
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
from ._act0 import (
    OfferOutcome,
    maybe_trigger_signal,
    prepare_mars_surface,
    bump_mars_door,
    place_mars_door,
    prepare_delve_site,
    mars_exploration_unlocked,
    delve_site_unlocked,
    surface_exploration_unlocked,
    spawn_quest_npcs,
    maybe_continue_chain,
    show_prologue_transmission,
    show_quest_summon,
    show_quest_readout,
    show_sealed_door_overlay,
    show_help_offer,
    show_gate_popup,
    render_help_offer,
    render_gate_popup,
)
