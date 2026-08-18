"""Act 0 lab chain (lab_q1 → lab_q7).

Structure only — titles, descriptions, and dialogue text live in
``src/spacehack/data/text/`` (see ``_apply_text_overlay``).

Design doc: docs/design/in_progress/07_DESIGN_MAIN_QUEST.md
"""

from __future__ import annotations

from . import MainQuestStep, QuestDialogue

_LAB_KEY = "lab_resonance_key"

STEPS: tuple[MainQuestStep, ...] = (
    MainQuestStep(
        id="lab_q1_sample",
        trigger_planet_id="mars",
        trigger_system_id="sol",
        requires_step="prologue_seek_help",
        chain="lab",
        objective_type="bump",
        wait_days=0,
        dialogues={
            "research_officer": QuestDialogue(
                npc_id="research_officer",
                backing_faction="lab",
                dialogue_planet_id="mercury",
            ),
        },
        rewards_xp=50,
    ),
    MainQuestStep(
        id="lab_q2_delivery",
        trigger_planet_id="mercury",
        trigger_system_id="sol",
        requires_step="lab_q1_sample",
        chain="lab",
        objective_type="smuggle",
        requires_npc_id="research_officer",
        smuggle_good_id="door_data",
        smuggle_cargo_size=1,
        smuggle_hot=False,  # scientific data — never confiscatable
        wait_days=50,
        dialogues={
            "research_officer": QuestDialogue(
                npc_id="research_officer",
                trigger_on_talk=True,
                backing_faction="lab",
                dialogue_planet_id="mercury",
            ),
        },
        rewards_xp=50,
    ),
    MainQuestStep(
        id="lab_q3_reference",
        trigger_planet_id="proc_planet_2",
        trigger_system_id="procyon",
        requires_step="lab_q2_delivery",
        chain="lab",
        objective_type="delve",
        delve_good_ids=(("alien_device", 1),),
        wait_days=0,
        # Portrait-only entry: the completion readout renders with the
        # Research Officer's portrait. The gate summon is the briefing,
        # so there is no talk intro/active text.
        dialogues={
            "research_officer": QuestDialogue(npc_id="research_officer"),
        },
        rewards_credits=100,
        rewards_xp=80,
    ),
    MainQuestStep(
        id="lab_q4_xenolinguist",
        trigger_planet_id="ac_station",
        trigger_system_id="alpha_centauri",
        requires_step="lab_q3_reference",
        chain="lab",
        objective_type="smuggle",
        requires_npc_id="xenolinguist",
        npc_presence=("xenolinguist",),  # the dataset receiver
        smuggle_good_id="alien_device",
        smuggle_cargo_size=1,
        smuggle_hot=False,  # research data — never confiscatable
        wait_days=95,
        dialogues={
            "xenolinguist": QuestDialogue(
                npc_id="xenolinguist",
                trigger_on_talk=True,
                backing_faction="lab",
            ),
        },
        rewards_xp=60,
    ),
    MainQuestStep(
        id="lab_q5_frequency",
        trigger_system_id="sirius",
        requires_step="lab_q4_xenolinguist",
        chain="lab",
        objective_type="salvage",
        requires_spawn_id="lab_derelict_guardian",
        bounty_enemy_id="pirate_captain",
        bounty_escort_ids=("pirate_raider", "pirate_raider"),
        salvage_wreck_enemy_id="derelict_scout",
        salvage_layout_id="scout_a",
        delve_good_ids=(("reference_recorder", 1),),
        wait_days=0,
        # Portrait-only entry (see lab_q3_reference): the gate summon
        # briefs this salvage, so there is no talk intro/active.
        dialogues={
            "research_officer": QuestDialogue(npc_id="research_officer"),
        },
        rewards_credits=150,
        rewards_xp=120,
    ),
    MainQuestStep(
        id="lab_q6_return",
        trigger_planet_id="mercury",
        trigger_system_id="sol",
        requires_step="lab_q5_frequency",
        chain="lab",
        objective_type="smuggle",
        requires_npc_id="research_officer",
        smuggle_good_id="reference_recorder",
        smuggle_cargo_size=1,
        smuggle_hot=False,  # a scientific instrument — never confiscatable
        wait_days=80,
        dialogues={
            "research_officer": QuestDialogue(
                npc_id="research_officer",
                trigger_on_talk=True,
                backing_faction="lab",
                dialogue_planet_id="mercury",
            ),
        },
        rewards_credits=100,
        rewards_xp=80,
    ),
    MainQuestStep(
        id="lab_q7_key",
        trigger_planet_id="mercury",
        trigger_system_id="sol",
        requires_step="lab_q6_return",
        chain="lab",
        objective_type="talk",
        unlocks_step="prologue_open",
        rewards_item=_LAB_KEY,
        dialogues={
            "research_officer": QuestDialogue(
                npc_id="research_officer",
                trigger_on_talk=True,
                backing_faction="lab",
                dialogue_planet_id="mercury",
            ),
        },
        rewards_credits=200,
        rewards_xp=150,
    ),
)

__all__ = ["STEPS"]
