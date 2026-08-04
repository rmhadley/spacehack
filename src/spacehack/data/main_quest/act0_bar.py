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
            "The Barkeep names the old smuggler who cracked a door "
            "like that once — cost him a hand. He warns the militia "
            "has been sniffing around the old routes since 'the "
            "incident'."
        ),
        trigger_planet_id="earth",
        trigger_system_id="sol",
        requires_step="prologue_seek_help",
        chain="bar",
        objective_type="talk",
        wait_days=65,
        completion_flavor="Word's been sent to Barnard's Star. The old man is cagey — give him time to come around.",
        ready_message=(
            "The old man will see you for the right price. Come by the "
            "bar first — I've got a crate that'll get you in the door. "
            "Then run it to Barnard's Star b."
        ),
        dialogues={
            "barkeep": QuestDialogue(
                npc_id="barkeep",
                trigger_on_talk=True,
                intro=(
                    "The old hand who cracked a door like that once? "
                    "Cost him a hand. He's retired on Barnard's Star b, "
                    "and he don't see just anyone. But he owes the bar "
                    "a favor — I'll send word ahead. Fair warning: the "
                    "militia's been sniffing around the old routes "
                    "since 'the incident'. Keep your head down."
                ),
                active=(
                    "Word's ahead to the old man. Go see him on "
                    "Barnard's Star b — and watch the patrols."
                ),
                complete=(
                    "The old man is cagey — he'll see you for the "
                    "right price."
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
            "The old smuggler won't deal with strangers. See the "
            "Barkeep on Earth — he has a hot crate to get you in the "
            "door. Then run it to Barnard's Star b. Every militia "
            "patrol on the way can scan it."
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
        completion_flavor="The old man needs time to survey the dig site. His hand doesn't work like it used to.",
        ready_message=(
            "He drew the cave where the old job went wrong — the rig's "
            "power cell is still down there. Meet him at the dig on "
            "Barnard's Star b."
        ),
        dialogues={
            "barkeep": QuestDialogue(
                npc_id="barkeep",
                trigger_on_talk=True,
                intro=(
                    "The old man won't deal with strangers — but he "
                    "owes the bar. I've got one crate left: black-market "
                    "weapons, hot as they come. Run it to him at "
                    "Barnard's Star b and he'll draw you the cave."
                ),
                active=(
                    "The crate's in your hold. Get it to the old man "
                    "on Barnard's Star b before a patrol sniffs it."
                ),
                complete=(
                    "He took the crate, then? Good — now he's got to "
                    "draw you the cave. The story's worth a round when "
                    "you're back."
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
                    "Crate's here, good. Now the part you came for: the "
                    "cave where the old job went wrong is up the ridge. "
                    "The rig's power cell is still down there. Fetch it, "
                    "and the bar gets its story."
                ),
                complete=(
                    "Cell's out, then? Good. The militia's got a nose "
                    "for that hardware — don't let them catch you "
                    "carrying it."
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
            "The power cell is decades old and unstable. It needs "
            "a recharge — and there's only one black-market rig "
            "that can handle it: the Wolf 359 listening post."
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
                    "You got it out? Good. That cell's older than "
                    "both of us — it needs a recharge before it'll "
                    "power anything. There's a black-market rig at "
                    "the Wolf 359 listening post. Pirate country — "
                    "no militia, no questions. Run it there."
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
            "The operator hooks the cell up to the rig. 'This "
            "thing's been sitting in the dark since before the "
            "incident. Give me a few months — I'll call when "
            "it's charged.'"
        ),
        ready_message=(
            "The cell's charged and ready. Come pick it up at the "
            "Wolf 359 bar — and be careful on the way back. Every "
            "militia scanner between here and Earth will light up "
            "the moment you jump into Sol."
        ),
        dialogues={
            "wolf_barkeep": QuestDialogue(
                npc_id="wolf_barkeep",
                trigger_on_talk=True,
                intro=(
                    "You got something for me, or are you just "
                    "thirsty? ...That's militia-issue. Old model, "
                    "but the serial's still clean. I can recharge "
                    "it — no questions — but it'll take time."
                ),
                active=(
                    "The cell's on the rig now. Couple months, "
                    "maybe less. I'll send word."
                ),
                complete=(
                    "Cell's charged. Word's ahead — the Earth "
                    "barkeep knows you're coming. Watch the "
                    "militia on the way back."
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
                    "Lost the cell to a patrol? That's militia-issue "
                    "hardware — it never travels quiet. I've got one "
                    "spare casing left from the old job. I'll load "
                    "another for you. Get it to the listening post "
                    "at Wolf 359."
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
            "The cell is charged and hot — every militia scanner "
            "in Sol will hunt you. Return to the Wolf 359 bar, "
            "collect the charged cell, and run it back to the "
            "Barkeep on Earth."
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
                    "There it is — fully charged and hot enough to "
                    "melt a scanner. Take it back to the Earth "
                    "barkeep. And stay sharp in Sol — every militia "
                    "patrol will be on you the moment you jump in."
                ),
                active=(
                    "The cell's in your hold. Run it to Earth — "
                    "the militia won't give you a choice."
                ),
                complete=(
                    "The cell made it. The Earth barkeep will have "
                    "the rig ready."
                ),
                option_label="Take the charged cell",
                backing_faction="bar",
            ),
            "barkeep": QuestDialogue(
                npc_id="barkeep",
                trigger_on_talk=True,
                intro=(
                    "You made it — and you brought the cell. "
                    "Give it here. The rig's half-assembled already."
                ),
                active=(
                    "There she is — the charged cell. Hand it over. "
                    "The rig is waiting."
                ),
                complete=(
                    "Cell's in, rig's on. One more step and that "
                    "door comes open."
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
            "Return to the Barkeep on Earth. The rig is assembled."
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
                    "There she is — the brute-force rig. Cracks the "
                    "seal's power feed, just like the old man's door. "
                    "The militia will be watching you from here on, "
                    "friend. Welcome to the family."
                ),
                active=(
                    "The rig's here when you're ready. After that door "
                    "opens, the story's worth a round."
                ),
                complete=(
                    "Take the rig and open that door. The bar wants "
                    "the story when you're done — and the militia will "
                    "be watching."
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
