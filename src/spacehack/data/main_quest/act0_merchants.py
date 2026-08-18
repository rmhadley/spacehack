"""Act 0 merchants chain: "The Contract" — alien-alloy cutter (mer_q1 → mer_q5).

Structure only — titles, descriptions, and dialogue text live in
``src/spacehack/data/text/`` (see ``_apply_text_overlay``).

Design doc: docs/design/in_progress/07_DESIGN_MAIN_QUEST.md
"""

from __future__ import annotations

from . import MainQuestStep, QuestDialogue

_MERCHANT_CUTTER = "merchant_cutter"

STEPS: tuple[MainQuestStep, ...] = (
    MainQuestStep(
        id="mer_q1_contract",
        trigger_planet_id="earth",
        trigger_system_id="sol",
        requires_step="prologue_seek_help",
        chain="merchants",
        objective_type="talk",
        wait_days=60,
        dialogues={
            "guild_master": QuestDialogue(
                npc_id="guild_master",
                trigger_on_talk=True,
                backing_faction="merchants",
                dialogue_planet_id="earth",
            ),
        },
        rewards_xp=50,
    ),
    MainQuestStep(
        id="mer_q2_strike",
        trigger_planet_id="wolf_b",
        trigger_system_id="wolf_359",
        requires_step="mer_q1_contract",
        chain="merchants",
        objective_type="delve",
        delve_good_ids=(("rare_earth_metals", 3),),
        wait_days=0,
        dialogues={
            "guild_master": QuestDialogue(
                npc_id="guild_master",
                backing_faction="merchants",
            ),
        },
        rewards_credits=100,
        rewards_xp=80,
    ),
    MainQuestStep(
        id="mer_q3_transport",
        trigger_planet_id="tc_b",
        trigger_system_id="tau_ceti",
        requires_step="mer_q2_strike",
        chain="merchants",
        objective_type="smuggle",
        requires_npc_id="salvage_specialist",
        smuggle_good_id="rare_earth_metals",
        smuggle_cargo_size=3,
        smuggle_hot=False,  # ore — never confiscatable (consortium heat is pirates, not scans)
        heat=("consortium",),  # consortium pirates hunt the ore en route
        wait_days=130,
        dialogues={
            "salvage_specialist": QuestDialogue(
                npc_id="salvage_specialist",
                trigger_on_talk=True,
                backing_faction="merchants",
            ),
        },
        rewards_credits=100,
        rewards_xp=90,
    ),
    MainQuestStep(
        id="mer_q4_calibrate",
        trigger_system_id="vega",
        requires_step="mer_q3_transport",
        chain="merchants",
        objective_type="salvage",
        requires_spawn_id="mer_consortium_leader",
        bounty_enemy_id="pirate_captain",
        bounty_escort_ids=("pirate_raider", "pirate_raider"),
        salvage_wreck_enemy_id="derelict_scout",
        salvage_layout_id="scout_a",
        delve_good_ids=(("calibration_data", 1),),
        smuggle_good_id="rare_earth_metals",
        smuggle_cargo_size=3,
        heat=("consortium",),  # consortium blockade guards the wreck
        wait_days=0,
        dialogues={
            "salvage_specialist": QuestDialogue(
                npc_id="salvage_specialist",
                trigger_on_talk=True,
                backing_faction="merchants",
            ),
        },
        rewards_credits=150,
        rewards_xp=120,
    ),
    MainQuestStep(
        id="mer_q5_cutter",
        trigger_planet_id="earth",
        trigger_system_id="sol",
        requires_step="mer_q4_calibrate",
        chain="merchants",
        objective_type="talk",
        unlocks_step="prologue_open",
        rewards_item=_MERCHANT_CUTTER,
        dialogues={
            "guild_master": QuestDialogue(
                npc_id="guild_master",
                trigger_on_talk=True,
                backing_faction="merchants",
                dialogue_planet_id="earth",
            ),
        },
        rewards_credits=200,
        rewards_xp=150,
    ),
)

__all__ = ["STEPS"]
