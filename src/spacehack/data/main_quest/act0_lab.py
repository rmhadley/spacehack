"""Act 0 lab chain: "The Resonance" — resonance key (lab_q1).

Full chain (lab_q2 — lab_q5) will be added per Phase 1h of the design doc.
Design doc: docs/design/in_progress/07_DESIGN_MAIN_QUEST.md
"""

from __future__ import annotations

from . import MainQuestStep, QuestDialogue

STEPS: tuple[MainQuestStep, ...] = (
    MainQuestStep(
        id="lab_q1_sample",
        title="The Sample",
        description=(
            "Return to Mars and chip a material sample off the door's "
            "surface — the door stays sealed. Bring the sample to the "
            "Research Officer."
        ),
        trigger_planet_id="mars",
        trigger_system_id="sol",
        requires_step="prologue_seek_help",
        chain="lab",
        objective_type="bump",
        dialogues={
            "research_officer": QuestDialogue(
                npc_id="research_officer",
                intro=(
                    "Return to Mars and chip a hand-sized fragment off "
                    "the door's material. The door itself stays sealed "
                    "— we only need the surface."
                ),
                active=(
                    "A hand-sized fragment of the door's material is "
                    "all we need. The door stays sealed."
                ),
                complete=(
                    "Sample received. We need time to analyze it."
                ),
                backing_faction="lab",
            ),
        },
        rewards_xp=50,
    ),
)

__all__ = ["STEPS"]
