"""Act 0 lab chain: "The Resonance" — resonance key (lab_q1 → lab_q7).

Physical through-line: door sample → reference dataset → xenolinguist →
derelict frequency → recorder return → resonance key.  One scientific
process, escalating understanding, moving through frontier research
stations.

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
            "The Research Officer wants a controlled fragment of the door's material. "
            "Return to Mars and take only what the analysis requires. The seal "
            "must remain intact; a sample is evidence, not permission. Bring it "
            "back for resonance analysis."
        ),
        trigger_planet_id="mars",
        trigger_system_id="sol",
        requires_step="prologue_seek_help",
        chain="lab",
        objective_type="bump",
        wait_days=0,
        completion_flavor=(
            "The fragment is secured. Its surface carries a repeating pattern that "
            "looks less like a manufacture mark than a remembered response. "
            "Deliver it to the Research Officer on Mercury before the pattern "
            "changes again."
        ),
        dialogues={
            "research_officer": QuestDialogue(
                npc_id="research_officer",
                intro=(
                    "Attach the data extractor to the alien console on Mars and "
                    "let it run its diagnostics. Bring the device back to me "
                    "when it's done - a clean reading matters more than a fast one."
                ),
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
            "The door fragment is in your mission hold. Deliver it to the Research "
            "Officer on Mercury before the material's response decays."
        ),
        trigger_planet_id="mercury",
        trigger_system_id="sol",
        requires_step="lab_q1_sample",
        chain="lab",
        objective_type="smuggle",
        requires_npc_id="research_officer",
        smuggle_good_id="door_data",
        smuggle_cargo_size=1,
        smuggle_hot=False,  # a scientific sample — never confiscatable
        wait_days=50,
        completion_flavor=(
            "The sample is unlike anything in the human catalogue, but the resonance is "
            "not random. The Research Officer begins the analysis and warns the "
            "lab not to publish a conclusion before it has earned one."
        ),
        ready_message=(
            "The lab has a working hypothesis: the sample may correspond to older "
            "reference data preserved at Procyon C. Report to the Research Officer "
            "on Mercury; she will explain what the sample still cannot tell us."
        ),
        dialogues={
            "research_officer": QuestDialogue(
                npc_id="research_officer",
                trigger_on_talk=True,
                active=(
                    "The fragment is in your mission hold. Hand it over and let the instruments "
                    "tell us whether the pattern is stable. First readings should "
                    "arrive before the station decides what story to attach to them."
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
            "The analysis points to Procyon C. A sealed cache beneath the outpost holds "
            "reference data from an earlier survey - old enough to predate the "
            "current signal, if the archive is telling the truth. Recover it "
            "from the ice caves so the lab can separate coincidence from a "
            "repeatable route."
        ),
        trigger_planet_id="proc_planet_2",
        trigger_system_id="procyon",
        requires_step="lab_q2_delivery",
        chain="lab",
        objective_type="delve",
        delve_good_ids=(("alien_device", 1),),
        wait_days=0,
        completion_flavor=(
            "The cache contains decades of resonance readings, including a pattern that "
            "predates every human survey in the region. Deliver the dataset to "
            "the xenolinguist at Alpha Centauri's Science Port. She may be able "
            "to tell whether the signal is speaking to us or passing through us."
        ),
        dialogues={
            "research_officer": QuestDialogue(
                npc_id="research_officer",
                intro=(
                    "The material is answering at a frequency no human instrument should "
                    "survive recording. We need the Procyon C reference cache to "
                    "learn whether that frequency belongs to the door, the signal, "
                    "or something farther along the route. Recover the dataset "
                    "intact."
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
            "The reference dataset is in your mission hold. Take it to the xenolinguist "
            "at Alpha Centauri's Science Port. She will compare its older "
            "resonance family with the Mars signal and map the relationship "
            "between them."
        ),
        trigger_planet_id="ac_station",
        trigger_system_id="alpha_centauri",
        requires_step="lab_q3_reference",
        chain="lab",
        objective_type="smuggle",
        requires_npc_id="xenolinguist",
        smuggle_good_id="alien_device",
        smuggle_cargo_size=1,
        smuggle_hot=False,  # research data — never confiscatable
        wait_days=95,
        completion_flavor=(
            "The xenolinguist finds a match, but not a translation. The two patterns "
            "share a route through the same dead frequencies. One more dataset "
            "may complete the map: a derelict near Sirius carried a reference "
            "recorder. The Research Officer will call when the coordinates are "
            "triangulated."
        ),
        ready_message=(
            "The coordinates are triangulated: a scout vessel lost near Sirius, its "
            "reference recorder still broadcasting a narrow pulse. Recover the "
            "recorder and bring it to the Research Officer on Mercury. The wreck "
            "has been quiet for decades; quiet does not mean unguarded."
        ),
        dialogues={
            "xenolinguist": QuestDialogue(
                npc_id="xenolinguist",
                trigger_on_talk=True,
                active=(
                    "The cross-reference gives us a route, not a meaning. One more dataset may "
                    "show where the route terminates. The Research Officer is "
                    "triangulating a derelict near Sirius."
                ),
                option_label="Hand over the dataset",
                backing_faction="lab",
            ),
            # Giver recovery: the Research Officer re-issues a lost
            # dataset copy so a confiscated/abandoned crate never
            # strands the chain (option only surfaces while the
            # crate is NOT in the mission hold).
            "research_officer": QuestDialogue(
                npc_id="research_officer",
                trigger_on_talk=True,
                intro=(
                    "If that dataset copy goes missing, the lab keeps "
                    "a backup of the Procyon reference files - I can "
                    "issue another. Get it straight to the Science "
                    "Port."
                ),
                option_label="Request another copy of the dataset",
                backing_faction="lab",
                dialogue_planet_id="mercury",
            ),
        },
        rewards_xp=60,
    ),
    MainQuestStep(
        id="lab_q5_frequency",
        title="The Frequency",
        description=(
            "A derelict scout vessel near Sirius carries the final reference recorder. "
            "Recover it from the wreck and bring back the evidence intact. The "
            "pirates guarding it may think they are protecting salvage; they may "
            "be protecting the last quiet warning in human space."
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
        wait_days=0,
        completion_flavor=(
            "The recorder is intact. Its last transmission contains a frequency that "
            "answers the Mars sample, then points away from human space. Bring it "
            "to the Research Officer on Mercury before anyone edits the record."
        ),
        dialogues={
            "research_officer": QuestDialogue(
                npc_id="research_officer",
                intro=(
                    "The xenolinguist's route map is nearly complete. A derelict scout vessel "
                    "near Sirius carried a reference-frequency recorder, and a "
                    "pirate captain with raiders is already picking it over. "
                    "Recover the recorder before the last quiet evidence is "
                    "scattered across the system."
                ),
                active=(
                    "The derelict is near Sirius, a scout vessel lost decades ago. A pirate "
                    "captain and his raiders are stripping it now. Clear them, board "
                    "the wreck, and recover the frequency recorder before its final "
                    "signal disappears."
                ),
                backing_faction="lab",
                dialogue_planet_id="mercury",
            ),
        },
        rewards_credits=150,
        rewards_xp=120,
    ),
    MainQuestStep(
        id="lab_q6_return",
        title="The Return",
        description=(
            "The reference recorder is in your mission hold. Return to Mercury and "
            "deliver it to the Research Officer. It completes the route map "
            "leading away from Mars."
        ),
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
        completion_flavor=(
            "The recorder is handed over intact. The route is complete; the meaning is "
            "not. The lab will forge a resonance key and contact you when it is "
            "ready."
        ),
        ready_message=(
            "The resonance key is forged. It matches the door's material so precisely "
            "that the instruments register a reply before anyone activates it. "
            "Report to the Research Officer on Mercury. The key is waiting."
        ),
        dialogues={
            "research_officer": QuestDialogue(
                npc_id="research_officer",
                trigger_on_talk=True,
                active=(
                    "The recorder is in your mission hold. Hand it over and the route map is "
                    "complete. The key can be forged, though the lab still does not "
                    "know what it will wake."
                ),
                option_label="Hand over the recorder",
                backing_faction="lab",
                dialogue_planet_id="mercury",
            ),
        },
        rewards_credits=100,
        rewards_xp=80,
    ),
    MainQuestStep(
        id="lab_q7_key",
        title="The Key",
        description=(
            "Return to the Research Officer on Mercury. The resonance key is forged from "
            "the door's material signature. Take it to Mars and ask the door what "
            "it has been waiting for."
        ),
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
                intro=(
                    "There it is - the resonance key. Forged from the door's own material "
                    "signature and calibrated against data older than human "
                    "contact with this region. Take it to Mars. The door should "
                    "open. What comes after may be a discovery, a warning, or a "
                    "question that has been waiting longer than we have."
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
