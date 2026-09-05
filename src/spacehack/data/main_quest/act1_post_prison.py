"""Main quest epilogue: the deliver-or-keep branch (doc 38, complete).

The orbit choice after the Mars escape picks a disposition; the
delivered branch unlocks this catalog's chain-keyed reward step
(return to the faction, share the archive, collect). The kept branch
carries no step - the data stays yours alone (Act 1 finds its own
way past the Line).
"""

from __future__ import annotations

from . import MainQuestStep, QuestDialogue

STEPS: tuple[MainQuestStep, ...] = (
    MainQuestStep(
        id="epilogue_reward_merchants",
        trigger_planet_id="earth",
        trigger_system_id="sol",
        requires_step="act1_prison",
        chain="merchants",
        objective_type="talk",
        rewards_credits=12000,  # the 8,000cr bond pays out, with its return
        dialogues={
            "guild_master": QuestDialogue(
                npc_id="guild_master",
                trigger_on_talk=True,
                backing_faction="merchants",
                dialogue_planet_id="earth",
            ),
        },
        rewards_xp=150,
    ),
    MainQuestStep(
        id="epilogue_reward_militia",
        trigger_planet_id="earth",
        trigger_system_id="sol",
        requires_step="act1_prison",
        chain="militia",
        objective_type="talk",
        rewards_trait="warrant_license",  # the Militia board posts warrants (doc 38, complete)
        dialogues={
            "militia_captain": QuestDialogue(
                npc_id="militia_captain",
                trigger_on_talk=True,
                backing_faction="militia",
                dialogue_planet_id="earth",
            ),
        },
        rewards_xp=150,
    ),
    MainQuestStep(
        id="epilogue_reward_bar",
        trigger_planet_id="earth",
        trigger_system_id="sol",
        requires_step="act1_prison",
        chain="bar",
        objective_type="talk",
        rewards_trait="smugglers_instinct",  # 10% of every hull concealed, forever
        dialogues={
            "barkeep": QuestDialogue(
                npc_id="barkeep",
                trigger_on_talk=True,
                backing_faction="bar",
                dialogue_planet_id="earth",
            ),
        },
        rewards_xp=150,
    ),
    MainQuestStep(
        id="epilogue_reward_lab",
        trigger_planet_id="mercury",
        trigger_system_id="sol",
        requires_step="act1_prison",
        chain="lab",
        objective_type="talk",
        rewards_trait="lab_credentials",  # the lab board posts contracts
        dialogues={
            "research_officer": QuestDialogue(
                npc_id="research_officer",
                trigger_on_talk=True,
                backing_faction="lab",
                dialogue_planet_id="mercury",
            ),
        },
        rewards_xp=150,
    ),
)

__all__ = ["STEPS"]
