"""Act 0 militia chain: "The Incident" — breach charge (mil_q1 → mil_q6).

Structure only — titles, descriptions, and dialogue text live in
``src/spacehack/data/text/`` (see ``_apply_text_overlay``).

Design doc: docs/design/in_progress/35_DESIGN_ACT0_MILITIA.md
"""

from __future__ import annotations

from . import MainQuestStep, QuestDialogue

_MILITIA_CHARGE = "militia_breach_charge"

STEPS: tuple[MainQuestStep, ...] = (
    MainQuestStep(
        id="mil_q1_report",
        trigger_planet_id="earth",
        trigger_system_id="sol",
        requires_step="prologue_seek_help",
        chain="militia",
        objective_type="talk",
        wait_days=60,
        dialogues={
            "militia_captain": QuestDialogue(
                npc_id="militia_captain",
                trigger_on_talk=True,
                backing_faction="militia",
                dialogue_planet_id="earth",
            ),
        },
        rewards_xp=50,
    ),
    MainQuestStep(
        id="mil_q2_cache",
        trigger_planet_id="mercury",
        trigger_system_id="sol",
        requires_step="mil_q1_report",
        chain="militia",
        objective_type="delve",
        delve_good_ids=(("sealed_requisition", 1),),
        wait_days=0,
        dialogues={
            "militia_captain": QuestDialogue(
                npc_id="militia_captain",
                backing_faction="militia",
                dialogue_planet_id="earth",
            ),
        },
        rewards_credits=100,
        rewards_xp=80,
    ),
    MainQuestStep(
        id="mil_q3_inspection",
        trigger_planet_id="blockade",
        trigger_system_id="luyten_star",
        requires_step="mil_q2_cache",
        chain="militia",
        objective_type="smuggle",
        requires_npc_id="blockade_officer",
        smuggle_good_id="sealed_requisition",
        smuggle_cargo_size=1,
        smuggle_hot=False,  # militia's own requisition — never confiscatable
        wait_days=40,  # inspection report routes; the real work starts at the expert
        dialogues={
            "militia_captain": QuestDialogue(
                npc_id="militia_captain",
                trigger_on_talk=True,
                backing_faction="militia",
                dialogue_planet_id="earth",
            ),
            "blockade_officer": QuestDialogue(
                npc_id="blockade_officer",
                trigger_on_talk=True,
                backing_faction="militia",
            ),
        },
        rewards_xp=60,
    ),
    MainQuestStep(
        id="mil_q4_demolitions",
        trigger_planet_id="eri_b",
        trigger_system_id="epsilon_eridani",
        requires_step="mil_q3_inspection",
        chain="militia",
        objective_type="visit",
        requires_npc_id="demolitions_expert",
        npc_presence=("demolitions_expert",),  # the recruit (visit) target
        wait_days=70,  # the expert tunes the charge to the alien alloy
        dialogues={
            "demolitions_expert": QuestDialogue(
                npc_id="demolitions_expert",
                backing_faction="militia",
            ),
        },
        rewards_xp=60,
    ),
    MainQuestStep(
        id="mil_q5_livefire",
        trigger_system_id="cygni",
        requires_step="mil_q4_demolitions",
        chain="militia",
        objective_type="bounty",
        requires_spawn_id="mil_livefire_test",
        bounty_enemy_id="pirate_captain",
        bounty_escort_ids=("pirate_captain", "pirate_captain", "pirate_captain", "pirate_captain"),
        wait_days=50,  # final package assembly + containment casing
        dialogues={
            "militia_captain": QuestDialogue(
                npc_id="militia_captain",
                backing_faction="militia",
                dialogue_planet_id="earth",
            ),
        },
        rewards_credits=150,
        rewards_xp=120,
    ),
    MainQuestStep(
        id="mil_q6_charge",
        trigger_planet_id="earth",
        trigger_system_id="sol",
        requires_step="mil_q5_livefire",
        chain="militia",
        objective_type="talk",
        unlocks_step="prologue_open",
        rewards_item=_MILITIA_CHARGE,
        dialogues={
            "militia_captain": QuestDialogue(
                npc_id="militia_captain",
                trigger_on_talk=True,
                backing_faction="militia",
                dialogue_planet_id="earth",
            ),
        },
        rewards_credits=200,
        rewards_xp=150,
    ),
)

__all__ = ["STEPS"]
