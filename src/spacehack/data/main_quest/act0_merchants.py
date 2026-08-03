"""Act 0 merchants chain: "The Contract" — alien-alloy cutter (mer_q1).

Full chain (mer_q2 — mer_q5) will be added per Phase 1f of the design doc.
Design doc: docs/design/in_progress/07_DESIGN_MAIN_QUEST.md
"""

from __future__ import annotations

from . import MainQuestStep, QuestDialogue

STEPS: tuple[MainQuestStep, ...] = (
    MainQuestStep(
        id="mer_q1_contract",
        title="Sign the Contract",
        description=(
            "Sign the contract with the Guild Master on Earth — first "
            "rights to anything inside the door, and the cutter is "
            "yours when the work is done."
        ),
        trigger_planet_id="earth",
        trigger_system_id="sol",
        requires_step="prologue_seek_help",
        chain="merchants",
        dialogues={
            "guild_master": QuestDialogue(
                npc_id="guild_master",
                trigger_on_talk=True,
                intro=(
                    "The contract is simple: the Guild gets first "
                    "rights to anything inside that door — salvage, "
                    "data, whatever it is — and in return the cutter "
                    "is yours when it's ready. Sign, and the first "
                    "clause sends you to escrow ore we've got staked "
                    "out."
                ),
                active=(
                    "The contract's waiting. Sign, and the first "
                    "clause points you at the escrow ore."
                ),
                complete=(
                    "Contract filed. We need time to arrange the "
                    "escrow."
                ),
                option_label="Sign the contract",
                backing_faction="merchants",
            ),
        },
        rewards_xp=50,
    ),
)

__all__ = ["STEPS"]
