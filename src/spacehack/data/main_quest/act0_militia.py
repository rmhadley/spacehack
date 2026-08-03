"""Act 0 militia chain: "The Incident" — breach charge (mil_q1).

Full chain (mil_q2 — mil_q5) will be added per Phase 1e of the design doc.
Design doc: docs/design/in_progress/07_DESIGN_MAIN_QUEST.md
"""

from __future__ import annotations

from . import MainQuestStep, QuestDialogue

STEPS: tuple[MainQuestStep, ...] = (
    MainQuestStep(
        id="mil_q1_report",
        title="Report to the Captain",
        description=(
            "Report to the Militia Captain on Earth — off the books, "
            "he admits the patrol saw 'the incident' tech before. The "
            "requisition is buried in a scrubbed cache."
        ),
        trigger_planet_id="earth",
        trigger_system_id="sol",
        requires_step="prologue_seek_help",
        chain="militia",
        dialogues={
            "militia_captain": QuestDialogue(
                npc_id="militia_captain",
                trigger_on_talk=True,
                intro=(
                    "Good. Now you're on the books — my books, which "
                    "is to say no one's. The patrol saw this tech "
                    "before. 'The incident'. The requisition that gets "
                    "you the charge is buried in a scrubbed cache. "
                    "Bring me proof it's intact, and the schematics "
                    "are yours."
                ),
                active=(
                    "The scrubbed cache isn't going anywhere. Bring me "
                    "proof the requisition is intact."
                ),
                complete=(
                    "The requisition is secured. We'll be in touch — "
                    "it takes time to clear."
                ),
                option_label="Report to the Captain",
                backing_faction="militia",
            ),
        },
        rewards_xp=50,
    ),
)

__all__ = ["STEPS"]
