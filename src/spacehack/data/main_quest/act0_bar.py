"""Act 0 bar chain: "The Old Hand" — brute-force rig (bar_q1 → bar_q6).

Structure only — titles, descriptions, and dialogue text live in
``src/spacehack/data/text/`` (see ``_apply_text_overlay``).

Design doc: docs/design/in_progress/07_DESIGN_MAIN_QUEST.md
"""

from __future__ import annotations

from . import MainQuestStep, QuestDialogue

_BAR_RIG = "bar_brute_rig"

STEPS: tuple[MainQuestStep, ...] = (
    MainQuestStep(
        id="bar_q1_oldhand",
        trigger_planet_id="earth",
        trigger_system_id="sol",
        requires_step="prologue_seek_help",
        chain="bar",
        objective_type="talk",
        wait_days=65,
        dialogues={
            "barkeep": QuestDialogue(
                npc_id="barkeep",
                trigger_on_talk=True,
                backing_faction="bar",
                dialogue_planet_id="earth",
            ),
        },
        rewards_xp=50,
    ),
    MainQuestStep(
        id="bar_q2_proof",
        trigger_planet_id="barnards_b",
        trigger_system_id="barnards_star",
        requires_step="bar_q1_oldhand",
        chain="bar",
        objective_type="smuggle",
        requires_npc_id="old_smuggler",
        smuggle_good_id="weapons_blackmarket",
        smuggle_cargo_size=8,
        heat=("militia_scan",),  # militia scan floor while the proof run is live
        wait_days=85,
        dialogues={
            "barkeep": QuestDialogue(
                npc_id="barkeep",
                trigger_on_talk=True,
                backing_faction="bar",
                dialogue_planet_id="earth",
            ),
            "old_smuggler": QuestDialogue(
                npc_id="old_smuggler",
                trigger_on_talk=True,
                backing_faction="bar",
            ),
        },
        rewards_credits=100,
        rewards_xp=80,
        rewards_rep={"pirate": +2, "merchant": -5, "civilian": -5, "militia": -8},
    ),
    MainQuestStep(
        id="bar_q3_rigparts",
        trigger_planet_id="barnards_b",
        trigger_system_id="barnards_star",
        requires_step="bar_q2_proof",
        chain="bar",
        objective_type="delve",
        delve_good_ids=(("machine_parts", 1), ("electronics", 1)),
        wait_days=0,
        dialogues={
            "old_smuggler": QuestDialogue(
                npc_id="old_smuggler",
                backing_faction="bar",
            ),
        },
        rewards_xp=60,
    ),
    MainQuestStep(
        id="bar_q4_blackmarket",
        trigger_planet_id="wolf_b",
        trigger_system_id="wolf_359",
        requires_step="bar_q3_rigparts",
        chain="bar",
        objective_type="smuggle",
        requires_npc_id="wolf_barkeep",
        smuggle_good_id="power_cell",
        smuggle_cargo_size=5,
        # Scan floor while the cell is en route + auto-aggro in Sol
        # while the crate is actually held (the charged-cell signature).
        heat=("militia_scan", "militia_aggro"),
        wait_days=90,
        dialogues={
            "wolf_barkeep": QuestDialogue(
                npc_id="wolf_barkeep",
                trigger_on_talk=True,
                backing_faction="bar",
            ),
            # Giver recovery: the old smuggler re-issues a lost power
            # cell so a confiscated/abandoned crate never strands the
            # chain (option only surfaces while the crate is NOT in
            # the mission hold).
            "old_smuggler": QuestDialogue(
                npc_id="old_smuggler",
                trigger_on_talk=True,
                backing_faction="bar",
                dialogue_planet_id="barnards_b",
            ),
        },
        rewards_credits=50,
        rewards_xp=60,
    ),
    MainQuestStep(
        id="bar_q5_charged",
        trigger_planet_id="earth",
        trigger_system_id="sol",
        requires_step="bar_q4_blackmarket",
        chain="bar",
        objective_type="smuggle",
        requires_npc_id="barkeep",
        smuggle_good_id="power_cell_charged",
        smuggle_cargo_size=5,
        # Scan floor + auto-aggro while the charged cell is in the hold.
        heat=("militia_scan", "militia_aggro"),
        wait_days=0,
        dialogues={
            "wolf_barkeep": QuestDialogue(
                npc_id="wolf_barkeep",
                trigger_on_talk=True,
                backing_faction="bar",
            ),
            "barkeep": QuestDialogue(
                npc_id="barkeep",
                trigger_on_talk=True,
                backing_faction="bar",
                dialogue_planet_id="earth",
            ),
        },
        rewards_credits=100,
        rewards_xp=80,
    ),
    MainQuestStep(
        id="bar_q6_rig",
        trigger_planet_id="earth",
        trigger_system_id="sol",
        requires_step="bar_q5_charged",
        chain="bar",
        objective_type="talk",
        unlocks_step="prologue_open",
        rewards_item=_BAR_RIG,
        dialogues={
            "barkeep": QuestDialogue(
                npc_id="barkeep",
                trigger_on_talk=True,
                backing_faction="bar",
                dialogue_planet_id="earth",
            ),
        },
        rewards_credits=200,
        rewards_xp=150,
    ),
)

__all__ = ["STEPS"]
