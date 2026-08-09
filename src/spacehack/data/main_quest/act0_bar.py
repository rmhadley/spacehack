"""Act 0 bar chain: "The Old Hand" — brute-force rig (bar_q1 → bar_q6).

Design doc: docs/design/in_progress/07_DESIGN_MAIN_QUEST.md
"""

from __future__ import annotations

from . import MainQuestStep, QuestDialogue

_BAR_RIG = "bar_brute_rig"

STEPS: tuple[MainQuestStep, ...] = (
    MainQuestStep(
        id="bar_q1_oldhand",
        title="The Old Hand",
        description=(
            "The Barkeep names an old smuggler who once found a door made of the "
            "same impossible material. It cost him a hand and left him with "
            "a story no one believes. Since the Incident, the Militia has "
            "been watching the old routes for anyone who asks the wrong "
            "questions."
        ),
        trigger_planet_id="earth",
        trigger_system_id="sol",
        requires_step="prologue_seek_help",
        chain="bar",
        objective_type="talk",
        wait_days=65,
        completion_flavor=(
            "Word has gone to Barnard's Star. The old man is deciding whether "
            "you want an answer or merely a door to break. Give him time."
        ),
        ready_message=(
            "The old man will see you for the right price. Come through the bar first; "
            "I have a crate that proves you can carry a secret without opening "
            "it in public. Run it to Barnard's Star b."
        ),
        dialogues={
            "barkeep": QuestDialogue(
                npc_id="barkeep",
                trigger_on_talk=True,
                intro=(
                    "The old hand did not crack that door. He made it answer, and it took his "
                    "hand for the courtesy. He is retired on Barnard's Star b "
                    "now, living where the maps get vague. He owes the bar a "
                    "favor, so I will send word. Keep your head down: since the "
                    "Incident, the Militia has treated old routes like crime "
                    "scenes."
                ),
                active=(
                    "The word is ahead. Go to Barnard's Star b and let the old man decide "
                    "whether your curiosity is worth the risk. Watch the patrols "
                    "on the way."
                ),
                complete=(
                    "The old man will see you. That is not the same as saying he will trust "
                    "you."
                ),
                option_label="Ask about the old smuggler",
                backing_faction="bar",
                dialogue_planet_id="earth",
            ),
        },
        rewards_xp=50,
    ),
    MainQuestStep(
        id="bar_q2_proof",
        title="The Proof Run",
        description=(
            "The old smuggler does not deal in introductions; he deals in proof. "
            "Take the Barkeep's hot crate to Barnard's Star b. Every Militia "
            "patrol on the route can scan it, and every one of them has a "
            "reason to wonder why you are carrying it."
        ),
        trigger_planet_id="barnards_b",
        trigger_system_id="barnards_star",
        requires_step="bar_q1_oldhand",
        chain="bar",
        objective_type="smuggle",
        requires_npc_id="old_smuggler",
        smuggle_good_id="weapons_blackmarket",
        smuggle_cargo_size=8,
        wait_days=85,
        completion_flavor=(
            "The old man is surveying the dig site with one hand and three "
            "decades of regret. Give him time to decide what part of the old "
            "story you are ready to carry."
        ),
        ready_message=(
            "He has marked the cave where the old job went wrong. The rig's power cell "
            "is still below, along with whatever the old door did not take. "
            "Meet him at the dig on Barnard's Star b."
        ),
        dialogues={
            "barkeep": QuestDialogue(
                npc_id="barkeep",
                trigger_on_talk=True,
                intro=(
                    "The old man will not deal with strangers, but he still owes the bar. I "
                    "have one crate left: black-market weapons, hot enough to "
                    "make a patrol curious. Deliver it to Barnard's Star b and "
                    "he will draw the cave on your map."
                ),
                active=(
                    "The crate's in your hold. Get it to the old man "
                    "on Barnard's Star b before a patrol sniffs it."
                ),
                complete=(
                    "He took the crate. Now he has to draw the cave. If you come back with the "
                    "power cell, I will buy the first round and listen to the "
                    "second story."
                ),
                locked=(
                    "Already running that crate, are you? The old man "
                    "is a patient sort. So's the militia."
                ),
                option_label="You asked to see me?",
                backing_faction="bar",
                dialogue_planet_id="earth",
            ),
            "old_smuggler": QuestDialogue(
                npc_id="old_smuggler",
                trigger_on_talk=True,
                intro=(
                    "The bar sent word. You got the crate, or are we "
                    "wasting both our times?"
                ),
                active=(
                    "The crate made it. Then listen carefully. The cave is up the ridge, and "
                    "the power cell is still below. The old job was not a robbery; "
                    "it was an attempt to make the door recognize a human signal. "
                    "Fetch the cell. I will tell you the rest if you come back."
                ),
                complete=(
                    "You brought the cell out. Good. It is old Militia hardware, which means "
                    "someone still has a file on it even if the file says it never "
                    "existed. Keep it away from scanners."
                ),
                option_label="Hand over the crate",
                backing_faction="bar",
            ),
        },
        rewards_credits=100,
        rewards_xp=80,
        rewards_rep={"pirate": +2, "merchant": -5, "civilian": -5, "militia": -8},
    ),
    MainQuestStep(
        id="bar_q3_rigparts",
        title="The Power Cell",
        description=(
            "The old smuggler drew the cave where the old job went "
            "wrong. Descend into the Barnard's Star b surface caves "
            "and recover the rig's power cell — decades-old "
            "militia-issue hardware."
        ),
        trigger_planet_id="barnards_b",
        trigger_system_id="barnards_star",
        requires_step="bar_q2_proof",
        chain="bar",
        objective_type="delve",
        delve_good_ids=(("machine_parts", 1), ("electronics", 1)),
        wait_days=0,
        completion_flavor=(
            "The power cell is decades old, unstable, and still holding a charge that "
            "does not decay like human power cells do. Take it to the only "
            "black-market rig built to handle it at the Wolf 359 listening post."
        ),
        dialogues={
            "old_smuggler": QuestDialogue(
                npc_id="old_smuggler",
                intro=(
                    "The cave's up the ridge, past the old dig markers. "
                    "The cell is down in the dark — watch your step, "
                    "and watch the sky. The militia's been circling."
                ),
                active=(
                    "The cave's up the ridge. The power cell is down "
                    "in the dark — and the militia knows you're "
                    "looking for it."
                ),
                complete=(
                    "You brought it out. That cell is older than both of us, and it needs a "
            "recharge before it will power the rig. Take it to the black-"
            "market station at Wolf 359. Pirate country means no Militia "
                    "questions, not no consequences."
                ),
                backing_faction="bar",
            ),
        },
        rewards_xp=60,
    ),
    MainQuestStep(
        id="bar_q4_blackmarket",
        title="Black-Market Recharge",
        description=(
            "The power cell is in your hold — unstable and hot. "
            "Take it to the Wolf 359 listening post. The black-market "
            "operator there has the only rig that can recharge it."
        ),
        trigger_planet_id="wolf_b",
        trigger_system_id="wolf_359",
        requires_step="bar_q3_rigparts",
        chain="bar",
        objective_type="smuggle",
        requires_npc_id="wolf_barkeep",
        smuggle_good_id="power_cell",
        smuggle_cargo_size=5,
        wait_days=90,
        completion_flavor=(
            "The operator connects the cell and immediately disconnects it again. The "
            "meter has no scale for what it reads. 'It has been waiting in the "
            "dark since before the Incident,' he says. 'Give me time. And do not "
            "let anyone ask why it still remembers the door.'"
        ),
        ready_message=(
            "The cell is charged, though the operator refuses to say what charged it. "
            "Collect it at the Wolf 359 bar and keep it hidden on the return run. "
            "Every Militia scanner between here and Earth will notice the moment "
            "you enter Sol."
        ),
        dialogues={
            "wolf_barkeep": QuestDialogue(
                npc_id="wolf_barkeep",
                trigger_on_talk=True,
                intro=(
                    "You brought something that still has a Militia serial. Old model, clean "
                    "enough to be dangerous. I can recharge it, but I am not going "
                    "to tell you what the meter says when the numbers stop behaving."
                ),
                active=(
                    "The cell is on the rig. It is drawing power in pulses, like it is "
                    "listening for a response. Give me time. I will send word when "
                    "it is safe to move."
                ),
                complete=(
                    "The cell is ready. I have warned the Earth Barkeep, and I have not warned "
                    "the Militia. That is the difference between a delivery and a "
                    "mistake. Watch the patrols."
                ),
                option_label="Hand over the power cell",
                backing_faction="bar",
            ),
            # Giver recovery: the old smuggler re-issues a lost power
            # cell so a confiscated/abandoned crate never strands the
            # chain (option only surfaces while the crate is NOT in
            # the mission hold).
            "old_smuggler": QuestDialogue(
                npc_id="old_smuggler",
                trigger_on_talk=True,
                intro=(
                    "A patrol took the cell? It was never going to travel quietly. I kept one "
                    "spare casing from the old job. I can replace it once; after "
                    "that, the route has to stay yours. Get it to Wolf 359."
                ),
                option_label="Request another power cell",
                backing_faction="bar",
                dialogue_planet_id="barnards_b",
            ),
        },
        rewards_credits=50,
        rewards_xp=60,
    ),
    MainQuestStep(
        id="bar_q5_charged",
        title="The Return Run",
        description=(
            "The charged cell is in the Wolf 359 bar. Collect it and run it back to "
            "the Barkeep on Earth. The Militia scanners in Sol will not merely "
            "see a hot crate; they will recognize an old signature and start "
            "asking why it has returned."
        ),
        trigger_planet_id="earth",
        trigger_system_id="sol",
        requires_step="bar_q4_blackmarket",
        chain="bar",
        objective_type="smuggle",
        requires_npc_id="barkeep",
        smuggle_good_id="power_cell_charged",
        smuggle_cargo_size=5,
        wait_days=0,
        completion_flavor=(
            "The cell is back on Earth. The rig can be assembled now."
        ),
        dialogues={
            "wolf_barkeep": QuestDialogue(
                npc_id="wolf_barkeep",
                trigger_on_talk=True,
                intro=(
                    "There it is. Fully charged, still carrying a signature the Militia "
                    "thought it had erased. Take it to Earth. The moment you enter "
                    "Sol, every patrol will have a reason to look twice."
                ),
                active=(
                    "The cell is in your hold. Run it to Earth before the Militia decides the "
                    "old signature is evidence enough to take you apart."
                ),
                complete=(
                    "The cell made it. The Earth Barkeep has the rig ready, and he has been "
                    "trying not to look at the door since you left."
                ),
                option_label="Take the charged cell",
                backing_faction="bar",
            ),
            "barkeep": QuestDialogue(
                npc_id="barkeep",
                trigger_on_talk=True,
                intro=(
                    "You made it back. Give me the cell before the scanners remember you. The "
                    "rig is waiting, and I would like to finish one job in my life "
                    "before the past catches up."
                ),
                active=(
                    "The cell is here. Hand it over and let us see whether the old rig still "
                    "knows what it was built to do."
                ),
                complete=(
                    "Cell is seated. The rig is awake. One more step and the door will have to "
                    "decide whether it remembers us."
                ),
                option_label="Hand over the charged cell",
                backing_faction="bar",
                dialogue_planet_id="earth",
            ),
        },
        rewards_credits=100,
        rewards_xp=80,
    ),
    MainQuestStep(
        id="bar_q6_rig",
        title="The Rig",
        description=(
            "Return to the Barkeep on Earth. The rig is assembled, but the old hand "
            "never promised it would open the door gently."
        ),
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
                intro=(
                    "There she is — the old rig rebuilt for a door that was never meant to "
                    "open. It does not crack the seal so much as convince the power "
                    "feed to stop pretending it is dead. The Militia will watch you "
                    "from here on. Welcome to the family, friend."
                ),
                active=(
                    "The rig is here when you are ready. After the door opens, come back with "
                    "the part of the story that makes you hesitate."
                ),
                complete=(
                    "Take the rig to Mars. Open the door, then come back if you can. The bar "
                    "will listen to the story, and the Militia will listen for "
                    "the parts you leave out."
                ),
                option_label="Collect the rig",
                backing_faction="bar",
                dialogue_planet_id="earth",
            ),
        },
        rewards_credits=200,
        rewards_xp=150,
    ),
)

__all__ = ["STEPS"]
