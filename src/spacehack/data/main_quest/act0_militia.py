"""Act 0 militia chain: "The Incident" — breach charge (mil_q1 → mil_q6).

Physical through-line: requisition cache → delivery to blockade
inspector → demolitions expert → live-fire test → breach charge.
One classified operation, escalating clearance, moving from Mercury
all the way to the edge of mapped space.

Design doc: docs/design/in_progress/07_DESIGN_MAIN_QUEST.md
"""

from __future__ import annotations

from . import MainQuestStep, QuestDialogue

_MILITIA_CHARGE = "militia_breach_charge"

STEPS: tuple[MainQuestStep, ...] = (
    MainQuestStep(
        id="mil_q1_report",
        title="Report to the Captain",
        description=(
            "Report to the Militia Captain on Earth. He has an unofficial "
            "explanation for the material on Mars, and an official reason "
            "to deny he ever saw it. A requisition cache on Mercury holds "
            "the parts for a breach package. Prove the cache survived, and "
            "he will decide whether you are useful enough to trust."
        ),
        trigger_planet_id="earth",
        trigger_system_id="sol",
        requires_step="prologue_seek_help",
        chain="militia",
        objective_type="talk",
        wait_days=60,
        completion_flavor=(
            "The requisition disappears into a file that officially does not "
            "exist. When the clearance comes through, search the Mercury "
            "caves beneath the old mining station. If the cache is still "
            "there, someone has been protecting the Incident's secrets "
            "for a very long time."
        ),
        ready_message=(
            "Clearance came through. Go to Mercury and recover the cache beneath "
            "the old mining station. Bring back the ship components and "
            "fuel cells before the next patrol decides to clean up the "
            "evidence for us."
        ),
        dialogues={
            "militia_captain": QuestDialogue(
                npc_id="militia_captain",
                trigger_on_talk=True,
                intro=(
                    "Good. You are on the books now - my private books, which means they "
                    "can be burned. A patrol found this material during the "
                    "Incident. We called it a wreck, then a weapons test, then "
                    "nothing at all. The requisition cache on Mercury is what "
                    "remains of the response. Bring me proof it survived, and "
                    "I will show you how we planned to open the door."
                ),
                option_label="Report to the Captain",
                backing_faction="militia",
                dialogue_planet_id="earth",
            ),
        },
        rewards_xp=50,
    ),
    MainQuestStep(
        id="mil_q2_cache",
        title="The Cache",
        description=(
            "The requisition cache lies beneath the Mercury mining station, in a "
            "cave system absent from every public survey. Recover the sealed "
            "components and fuel cells, then carry them to the Luyten's Star "
            "blockade. The Captain wants the package inspected before it "
            "comes anywhere near the Mars door."
        ),
        trigger_planet_id="mercury",
        trigger_system_id="sol",
        requires_step="mil_q1_report",
        chain="militia",
        objective_type="delve",
        delve_good_ids=(("ship_components", 4), ("fuel_cells", 2)),
        wait_days=0,
        completion_flavor=(
            "The cache contained exactly what the old requisition promised: sealed "
            "components, fuel cells, and no explanation for why they were "
            "hidden. The blockade inspector is expecting your transponder. "
            "Take the package there before the silence around it attracts "
            "the wrong attention."
        ),
        dialogues={
            "militia_captain": QuestDialogue(
                npc_id="militia_captain",
                intro=(
                    "The cache is deep in the Mercury caves - "
                    "a sealed requisition the official logs don't "
                    "show. Ship components, fuel cells, enough to "
                    "build a breach charge that'll crack anything. "
                    "Secure it and bring it back."
                ),
                backing_faction="militia",
                dialogue_planet_id="earth",
            ),
        },
        rewards_credits=100,
        rewards_xp=80,
    ),
    MainQuestStep(
        id="mil_q3_inspection",
        title="The Inspection",
        description=(
            "The components are in your hold under serial numbers that no longer "
            "exist. Deliver them to the blockade inspector at Luyten's Star. "
            "The route crosses pirate space and the edge of the mapped "
            "frontier; every jump is another chance for the package to be "
            "lost, seized, or noticed."
        ),
        trigger_planet_id="blockade",
        trigger_system_id="luyten_star",
        requires_step="mil_q2_cache",
        chain="militia",
        objective_type="smuggle",
        requires_npc_id="blockade_officer",
        smuggle_good_id="ship_components",
        smuggle_cargo_size=6,
        smuggle_hot=False,  # militia's own requisition — never confiscatable
        wait_days=80,
        completion_flavor=(
            "The blockade inspector signs off on every component. The serials are "
            "scrubbed, the seals are intact, and the requisition survives one "
            "more layer of questions. The Captain will contact you when the "
            "demolitions expert is prepared to take responsibility for the "
            "next step."
        ),
        ready_message=(
            "The blockade has verified the package without learning what it is. "
            "Recruit the demolitions expert at Epsilon Eridani b. Use my "
            "name, not the requisition number. He is the last person in the "
            "Militia who still knows how to work on doors that were never "
            "designed to be breached."
        ),
        dialogues={
            "militia_captain": QuestDialogue(
                npc_id="militia_captain",
                trigger_on_talk=True,
                intro=(
                    "The cache survived. Now make the package survive the trip. The "
                    "inspector at Luyten's Star is waiting at the northern "
                    "checkpoint. Five jumps through frontier space, and no "
                    "one outside this chain needs to know what you are carrying."
                ),
                active=(
                    "The blockade inspector is waiting at Luyten's Star's northern checkpoint. "
                    "Hand over the components. He will log them as routine supply "
                    "and keep the package buried under ordinary paperwork."
                ),
                option_label="Take on the delivery",
                backing_faction="militia",
                dialogue_planet_id="earth",
            ),
            "blockade_officer": QuestDialogue(
                npc_id="blockade_officer",
                trigger_on_talk=True,
                intro=(
                    "The Captain sent word. Scratched requisition, "
                    "scrubbed serials - I know the drill. Hand over "
                    "the components. I'll log them as routine supply "
                    "transfer, and no one asks questions. The Captain "
                    "will call when the inspection clears."
                ),
                active=(
                    "Still carrying those components? The Captain's "
                    "inspector is here at the northern checkpoint. "
                    "Hand them over and I'll make the paperwork "
                    "disappear."
                ),
                complete=(
                    "The components check out. The inspection report disappears into a routine "
                    "supply transfer: no flags, no questions, and no record of why "
                    "the Militia needed alien-grade hardware on the frontier. The "
                    "Captain will contact you when the demolitions expert answers."
                ),
                option_label="Hand over the requisition",
                backing_faction="militia",
            ),
        },
        rewards_xp=60,
    ),
    MainQuestStep(
        id="mil_q4_demolitions",
        title="The Expert",
        description=(
            "Recruit the demolitions expert at Epsilon Eridani b. The frontier colony's "
            "Militia building is the last place he still answers calls. Use the "
            "Captain's name; the breach package needs someone willing to admit "
            "what it is for."
        ),
        trigger_planet_id="eri_b",
        trigger_system_id="epsilon_eridani",
        requires_step="mil_q3_inspection",
        chain="militia",
        objective_type="visit",
        requires_npc_id="demolitions_expert",
        wait_days=120,
        completion_flavor=(
            "The demolitions expert signs on. Tuning the charge to alien alloy will take "
            "time, and the test will need a target that can survive the first "
            "failure. The Captain will call when the prototype is ready."
        ),
        ready_message=(
            "The prototype is calibrated. Clear the pirate captains at Cygni b and "
            "bring back the combat data. The Captain wants a live-fire test "
            "before the charge touches the Mars door; the first failure must "
            "happen somewhere we can survive it."
        ),
        dialogues={
            "demolitions_expert": QuestDialogue(
                npc_id="demolitions_expert",
                intro=(
                    "The Captain sent you, which means this job is either important or "
                    "already a mistake. I build charges for structures that "
                    "resist ordinary physics. If the requisition is genuine, "
                    "I can tune one to the Mars door. But understand this: a "
                    "successful breach tells you nothing about what is waiting "
                    "on the other side."
                ),
                complete=(
                    "The charge is ready for a live-fire test. The Captain has chosen a "
                    "target at Cygni b: pirate captains, hard enough to stress "
                    "the package and disposable enough that no official "
                    "report will mourn the test. Ask him for the coordinates."
                ),
                option_label="Ask about the breach charge",
                backing_faction="militia",
            ),
        },
        rewards_xp=60,
    ),
    MainQuestStep(
        id="mil_q5_livefire",
        title="Live-Fire Test",
        description=(
            "The breach charge is built, but a laboratory result is not proof. Take the "
            "prototype to Cygni b and put it through a live-fire test against "
            "five pirate captains. If it fails there, it fails on Mars. If it "
            "works, we still have to decide whether opening the door is wiser "
            "than leaving it sealed."
        ),
        trigger_system_id="cygni",
        requires_step="mil_q4_demolitions",
        chain="militia",
        objective_type="bounty",
        requires_spawn_id="mil_livefire_test",
        bounty_enemy_id="pirate_captain",
        bounty_escort_ids=("pirate_captain", "pirate_captain", "pirate_captain", "pirate_captain"),
        wait_days=80,
        completion_flavor=(
            "The prototype held under fire. The test report contains one useful "
            "answer and several new questions: the charge couples to the "
            "alien material instead of simply breaking it. The Captain is "
            "assembling the final package."

        ),
        ready_message=(
            "The final breach package is assembled. Report to the Captain on Earth. "
            "Once it is in your hands, the Militia can no longer pretend this "
            "is only an investigation."
        ),
        dialogues={
            "militia_captain": QuestDialogue(
                npc_id="militia_captain",
                intro=(
                    "The charge needs a real stress-test before it touches Mars. Five "
                    "pirate captains at Cygni b will serve as the target. We "
                    "are mounting the prototype to your ship; fire it, record "
                    "the result, and do not mistake a successful detonation "
                    "for a successful containment plan."
                ),
                backing_faction="militia",
                dialogue_planet_id="earth",
            ),
        },
        rewards_credits=150,
        rewards_xp=120,
    ),
    MainQuestStep(
        id="mil_q6_charge",
        title="The Charge",
        description=(
            "Return to the Militia Captain on Earth. The breach package is tuned, "
            "tested, and ready to open the alien seal on Mars. The Captain "
            "wants the operation contained from the first jump to the last."
        ),
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
                intro=(
                    "There it is. Tuned to the same material that ended the Incident. Take "
                    "it to Mars and open the door. We contain whatever is "
                    "inside, we preserve what can be learned, and we tell no "
                    "one until we know which of those tasks is still possible. "
                    "That is the order. The door is not."
                ),
                option_label="Collect the charge",
                backing_faction="militia",
                dialogue_planet_id="earth",
            ),
        },
        rewards_credits=200,
        rewards_xp=150,
    ),
)

__all__ = ["STEPS"]
