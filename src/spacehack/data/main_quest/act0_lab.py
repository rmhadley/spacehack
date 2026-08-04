"""Act 0 lab chain: "The Resonance" — resonance key (lab_q1 → lab_q5).

Physical through-line: door sample → reference dataset → xenolinguist →
derelict frequency → resonance key.  One scientific process, escalating
understanding, moving through frontier research stations.

Design doc: docs/design/in_progress/07_DESIGN_MAIN_QUEST.md
"""

from __future__ import annotations

from . import MainQuestStep, QuestDialogue

_LAB_KEY = "lab_resonance_key"

STEPS: tuple[MainQuestStep, ...] = (
    MainQuestStep(
        id="lab_q1_sample",
        title="The Sample",
        description=(
            "The Research Officer wants a hand-sized fragment of the "
            "door's material. Return to Mars, chip a sample off the "
            "sealed door — it stays sealed — and bring it back for "
            "resonance analysis."
        ),
        trigger_planet_id="mars",
        trigger_system_id="sol",
        requires_step="prologue_seek_help",
        chain="lab",
        objective_type="bump",
        wait_days=0,
        completion_flavor=(
            "Sample chipped — a hand-sized fragment of the door's "
            "material. It's loaded into your mission hold. Deliver "
            "it to the Research Officer on Mercury for analysis."
        ),
        ready_message=(
            "The resonance analysis is complete — and the results point "
            "to Procyon C. A sealed research cache in the ice caves "
            "beneath the outpost holds a reference dataset. Report to "
            "the Research Officer on Mercury — the lab has the details."
        ),
        dialogues={
            "research_officer": QuestDialogue(
                npc_id="research_officer",
                trigger_on_talk=True,
                intro=(
                    "Good — you found the door. Now we need proof of what "
                    "it's made of. Return to Mars and chip a hand-sized "
                    "fragment off its surface. The door itself stays "
                    "sealed. Bring the sample here and I'll run the "
                    "resonance analysis — if the signature is stable, "
                    "we can forge a key."
                ),
                active=(
                    "The sample is still on the door. Return to Mars, "
                    "chip a fragment off the sealed door, and bring it "
                    "to the Mercury lab. The door stays sealed — we "
                    "only need the surface."
                ),
                complete=(
                    "Sample received — remarkable material. The "
                    "resonance analysis is running; give us time. The "
                    "initial results should point us to the next "
                    "phase."
                ),
                option_label="Accept the assignment",
                backing_faction="lab",
                dialogue_planet_id="mercury",
            ),
        },
        rewards_xp=50,
    ),
    MainQuestStep(
        id="lab_q2_delivery",
        title="The Delivery",
        description=(
            "The door sample is in your mission hold. Deliver it to "
            "the Research Officer on Mercury for resonance analysis."
        ),
        trigger_planet_id="mercury",
        trigger_system_id="sol",
        requires_step="lab_q1_sample",
        chain="lab",
        objective_type="smuggle",
        requires_npc_id="research_officer",
        smuggle_good_id="door_sample",
        smuggle_cargo_size=1,
        wait_days=50,
        completion_flavor=(
            "Sample received — the material is unlike anything in the "
            "human catalogue. The Research Officer begins the resonance "
            "analysis. They'll contact you when the first results are "
            "in."
        ),
        ready_message=(
            "The resonance analysis is complete — and the results point "
            "to Procyon C. A sealed research cache in the ice caves "
            "beneath the outpost holds a reference dataset. Report to "
            "the Research Officer on Mercury — the lab has the details."
        ),
        dialogues={
            "research_officer": QuestDialogue(
                npc_id="research_officer",
                trigger_on_talk=True,
                intro=(
                    "You chipped a sample? Good — hand it over and the "
                    "resonance analysis begins. If the signature is "
                    "stable, we can forge a key."
                ),
                active=(
                    "The sample is in your mission hold. Hand it over "
                    "and the analysis begins — it shouldn't take long "
                    "to get the first resonance readings."
                ),
                complete=(
                    "Sample received — remarkable material. The "
                    "resonance analysis is running; give us time. "
                    "The initial results should point us to the "
                    "next phase."
                ),
                option_label="Hand over the sample",
                backing_faction="lab",
                dialogue_planet_id="mercury",
            ),
        },
        rewards_xp=50,
    ),
    MainQuestStep(
        id="lab_q3_reference",
        title="The Reference",
        description=(
            "The resonance analysis points to Procyon C — a sealed "
            "research cache in the ice caves beneath the outpost holds "
            "a reference dataset that will calibrate the resonance "
            "key. Descend into the caves and secure the research data."
        ),
        trigger_planet_id="proc_planet_2",
        trigger_system_id="procyon",
        requires_step="lab_q2_delivery",
        chain="lab",
        objective_type="delve",
        delve_good_ids=(("research_data", 2),),
        wait_days=0,
        completion_flavor=(
            "The reference dataset is secured — decades of ice-core "
            "resonance readings. It's loaded into your mission hold. "
            "The xenolinguist at Alpha Centauri's Science Port is the "
            "only one who can cross-reference it with the signal — "
            "fly there and hand it over."
        ),
        dialogues={
            "research_officer": QuestDialogue(
                npc_id="research_officer",
                intro=(
                    "The resonance analysis is promising — the door's "
                    "material has a frequency we've never seen. To "
                    "calibrate the key, we need a reference dataset "
                    "from Procyon C. A sealed research cache in the "
                    "ice caves beneath the outpost — decades of "
                    "resonance readings. Secure it and bring it back."
                ),
                active=(
                    "The cache is deep in the Procyon C ice caves — "
                    "beneath the research outpost. The dataset is "
                    "decades old but sealed — it should still be "
                    "intact. Retrieve it and the calibration can "
                    "begin."
                ),
                complete=(
                    "The dataset is intact — excellent. The "
                    "xenolinguist at Alpha Centauri's Science Port "
                    "needs to cross-reference it with the signal "
                    "data. I'll send word ahead — report to the "
                    "Science Port when she's ready."
                ),
                backing_faction="lab",
                dialogue_planet_id="mercury",
            ),
        },
        rewards_credits=100,
        rewards_xp=80,
    ),
    MainQuestStep(
        id="lab_q4_xenolinguist",
        title="The Xenolinguist",
        description=(
            "The reference dataset is in your mission hold. Fly to "
            "Alpha Centauri's Science Port and deliver it to the "
            "xenolinguist — she'll cross-reference it with the signal "
            "and map the resonance frequency."
        ),
        trigger_planet_id="ac_station",
        trigger_system_id="alpha_centauri",
        requires_step="lab_q3_reference",
        chain="lab",
        objective_type="smuggle",
        requires_npc_id="xenolinguist",
        smuggle_good_id="research_data",
        smuggle_cargo_size=2,
        wait_days=95,
        completion_flavor=(
            "The xenolinguist cross-references the dataset with the "
            "signal — the resonance pattern matches. One more dataset "
            "is needed to complete the map: a derelict near Sirius "
            "carried a reference-frequency recorder. The Research "
            "Officer will call when the coordinates are triangulated."
        ),
        ready_message=(
            "The derelict's coordinates are triangulated — a scout "
            "vessel near Sirius, lost decades ago. Its reference-"
            "frequency recorder still holds the data we need. Report "
            "to the Research Officer on Mercury for the exact "
            "coordinates — but watch for automated derelict defenses."
        ),
        dialogues={
            "xenolinguist": QuestDialogue(
                npc_id="xenolinguist",
                trigger_on_talk=True,
                intro=(
                    "You brought the reference dataset — good. The "
                    "signal we've been tracking shares a resonance "
                    "pattern with your door sample. If I can cross-"
                    "reference the Procyon data with the signal, I "
                    "can map the frequency — and that's your key. "
                    "Hand it over."
                ),
                active=(
                    "The cross-reference is promising. The resonance "
                    "pattern is clearer than anything we've seen — "
                    "but we need one more dataset to complete the "
                    "map. The Research Officer is triangulating a "
                    "derelict near Sirius."
                ),
                complete=(
                    "The frequency map is complete — mostly. One "
                    "more dataset from a derelict near Sirius and "
                    "the key can be forged. The Research Officer on "
                    "Mercury has the coordinates."
                ),
                option_label="Hand over the dataset",
                backing_faction="lab",
            ),
        },
        rewards_xp=60,
    ),
    MainQuestStep(
        id="lab_q5_frequency",
        title="The Frequency",
        description=(
            "A derelict scout vessel near Sirius carries a reference-"
            "frequency recorder — the final dataset needed to forge "
            "the resonance key. Fight through the pirates guarding "
            "the wreck, board it, and recover the recorder inside."
        ),
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
        wait_days=80,
        completion_flavor=(
            "The reference-frequency recorder is recovered from the "
            "wreck — the final piece of the resonance map slides into "
            "place. The Research Officer will call when the key is "
            "forged."
        ),
        ready_message=(
            "The key is forged — a resonance frequency that matches "
            "the door's material perfectly. Report to the Research "
            "Officer on Mercury. The key is waiting for you."
        ),
        dialogues={
            "research_officer": QuestDialogue(
                npc_id="research_officer",
                intro=(
                    "The xenolinguist's map is nearly complete — one "
                    "more dataset and we can forge the key. A derelict "
                    "scout vessel near Sirius carried a reference-"
                    "frequency recorder — and word is a pirate captain "
                    "and his raiders are already picking it over. "
                    "Fight through them, board the wreck, and recover "
                    "the recorder."
                ),
                active=(
                    "The derelict is near Sirius — a scout vessel lost "
                    "decades ago. A pirate captain and his raiders are "
                    "guarding the wreck. Clear them, board it, and "
                    "recover the frequency recorder from inside."
                ),
                complete=(
                    "The frequency recorder — intact! This is the "
                    "final piece. The resonance map is complete, and "
                    "the key can be forged. Give us time to assemble "
                    "it — the Research Officer will call when it's "
                    "ready."
                ),
                backing_faction="lab",
                dialogue_planet_id="mercury",
            ),
        },
        rewards_credits=150,
        rewards_xp=120,
    ),
    MainQuestStep(
        id="lab_q6_key",
        title="The Key",
        description=(
            "Return to the Research Officer on Mercury. The resonance "
            "key is forged — a frequency tuned to the alien door's "
            "material. Take it to Mars and open the way."
        ),
        trigger_planet_id="mercury",
        trigger_system_id="sol",
        requires_step="lab_q5_frequency",
        chain="lab",
        objective_type="talk",
        unlocks_step="prologue_open",
        rewards_item=_LAB_KEY,
        dialogues={
            "research_officer": QuestDialogue(
                npc_id="research_officer",
                trigger_on_talk=True,
                intro=(
                    "There it is — the resonance key. Forged from "
                    "the door's own material signature, calibrated "
                    "against decades of reference data, cross-"
                    "referenced with the alien signal. Take it to "
                    "Mars — the door will open. The truth deserves "
                    "to be published, not buried."
                ),
                active=(
                    "The key is here when you're ready. After that "
                    "door opens, bring us a specimen from inside — "
                    "the station will study what you find."
                ),
                complete=(
                    "Take the key and open that door. Whatever's "
                    "inside, the truth deserves to be known — and "
                    "you're the one who brought it back."
                ),
                option_label="Collect the key",
                backing_faction="lab",
                dialogue_planet_id="mercury",
            ),
        },
        rewards_credits=200,
        rewards_xp=150,
    ),
)

__all__ = ["STEPS"]
