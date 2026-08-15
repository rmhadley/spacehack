"""Act 0 prologue steps: signal, Mars gate, door, seek-help fork, open.

Design doc: docs/design/in_progress/07_DESIGN_MAIN_QUEST.md
"""

from __future__ import annotations

from . import MainQuestStep, QuestDialogue

_ASK_LABEL = "Ask about the Mars door"

STEPS: tuple[MainQuestStep, ...] = (
    MainQuestStep(
        id="prologue_signal",
        title="The Signal",
        # Auto-completes in the same instant it triggers (first jump out
        # of Sol), so the quest-log breadcrumb never renders it — the
        # beat is carried by the transmission overlay + log lines, and
        # the quest-log description is intentionally empty.
        description="",
        trigger_planet_id="mars",
        trigger_system_id="sol",
    ),
    MainQuestStep(
        id="prologue_mars_unlocked",
        title="Mars",
        description=(
            "The coordinates point to a remote stretch of Mars beyond the "
            "settlements. Something could be there. Worth taking a look at "
            "least."
        ),
        trigger_planet_id="mars",
        trigger_system_id="sol",
        requires_step="prologue_signal",
    ),
    MainQuestStep(
        id="prologue_mars_entrance",
        title="The Door",
        description=(
            "The martian rock merges with high tech metal machinery. You see "
            "a wall that undulates before you as you examine it. An alien "
            "console stands before it, still with power. But a mystery you "
            "can't solve alone."
        ),
        trigger_planet_id="mars",
        trigger_system_id="sol",
        requires_step="prologue_mars_unlocked",
    ),
    MainQuestStep(
        id="prologue_seek_help",
        title="Seek Help",
        description=(
            "No human tool can make the door acknowledge you. Ask the people "
            "who have the most to lose if this place is opened: the bar "
            "knows the old routes, the Guild knows how to buy a way through, "
            "the Militia knows what it is hiding, and the Lab knows when a "
            "discovery is too important to leave alone. Choose who puts "
            "their hands on the lock. They will remember what you do with "
            "what comes after."
        ),
        requires_step="prologue_mars_entrance",
        dialogues={
            "barkeep": QuestDialogue(
                npc_id="barkeep",
                trigger_on_talk=True,
                intro=(
                    "Heard about the thing in the dust? Then you heard the wrong story. "
                    "The militia calls it a sealed site. The old routes call "
                    "it a door that took a hand and gave nothing back. One "
                    "man got close to opening it. He has spent the years "
                    "since pretending he never did. I can put you in the "
                    "same room with him."
                ),
                complete=(
                    "Then we have an understanding. I will send you to the old hand. "
                    "Do not ask him what was behind the door until he decides "
                    "you are ready to hear it. If you come back, the bar will "
                    "keep your glass full while you tell the story."
                ),
                locked=(
                    "You chose another road in. Fine. Just remember that official reports "
                    "are written by the people who survive them. If you come "
                    "back, tell the bar what the reports leave out."
                ),
                option_label=_ASK_LABEL,
                backing_faction="bar",
                locks_chain=True,
            ),
            "guild_master": QuestDialogue(
                npc_id="guild_master",
                trigger_on_talk=True,
                intro=(
                    "Alien infrastructure on Mars is not a curiosity. It is an asset with "
                    "no owner, no patent, and no surviving claimant. Sign the "
                    "contract and the Guild will put a cutter in your hands "
                    "that can read the door's material stress. First rights "
                    "to whatever is recovered. We can decide what it is worth "
                    "after we know how much of the future it contains."
                ),
                complete=(
                    "The contract is filed. Build the cutter, open the door, and bring us "
                    "something no one else can value yet. That is where the "
                    "best margins begin."
                ),
                locked=(
                    "Another party is funding the operation. An unfortunate choice, but "
                    "not an irreversible one. If you recover anything the Guild "
                    "can refine, transport, or sell, our office remains open."
                ),
                option_label=_ASK_LABEL,
                backing_faction="merchants",
                locks_chain=True,
            ),
            "militia_captain": QuestDialogue(
                npc_id="militia_captain",
                trigger_on_talk=True,
                intro=(
                    "There is no door. That is the official answer, and you will repeat it "
                    "if anyone asks. ...Off the books: a patrol found the same "
                    "material during the Incident. We lost people, buried the "
                    "report, and learned that some doors are built to keep "
                    "something in. I can give you a breach package. You can "
                    "give me one thing in return: silence until we know what "
                    "we are dealing with."
                ),
                complete=(
                    "The paperwork is moving. When the package is ready, you will hear "
                    "from me through a channel that officially does not exist. "
                    "Until then, forget the coordinates."
                ),
                locked=(
                    "You chose another sponsor. Then keep the operation away from the "
                    "patrol. We have enough old mistakes on the books already."
                ),
                option_label=_ASK_LABEL,
                backing_faction="militia",
                locks_chain=True,
            ),
            "research_officer": QuestDialogue(
                npc_id="research_officer",
                trigger_on_talk=True,
                intro=(
                    "A structure this old should not be broadcasting anything. Bring me a "
                    "sample from the door and I can compare its resonance to "
                    "the transmission. If the two are related, the key will not "
                    "force the lock; it will demonstrate that the lock has "
                    "already recognized us."
                ),
                complete=(
                    "Then the work begins. Take a controlled sample from Mars and bring it "
                    "back. We will publish the evidence when we know what it "
                    "means, not before. The difference may keep people alive."
                ),
                locked=(
                    "You found another method. If you recover evidence, send it to the "
                    "station. We will study it before we decide whether it is a "
                    "warning, a weapon, or something that has no human category."
                ),
                option_label=_ASK_LABEL,
                backing_faction="lab",
                locks_chain=True,
            ),
            # The Science Port lab slot hosts the xenolinguist (Act 0
            # lab-chain expert) — the lab seek-help lead keys off the
            # expert id so it still surfaces at Alpha Centauri.
            "xenolinguist": QuestDialogue(
                npc_id="xenolinguist",
                trigger_on_talk=True,
                intro=(
                    "The signal is not a message in any human sense. It is a pattern with "
                    "coordinates embedded inside it, and the door may be made "
                    "of the same impossible material. Bring me a sample. We "
                    "may be able to make the lock answer without teaching "
                    "ourselves what it was built to contain."
                ),
                complete=(
                    "Then the work begins. Take a controlled sample from Mars and bring it "
                    "back. We will publish the evidence when we know what it "
                    "means, not before. The difference may keep people alive."
                ),
                locked=(
                    "You found another method. If you recover evidence, send it to the "
                    "station. We will study it before we decide whether it is a "
                    "warning, a weapon, or something that has no human category."
                ),
                option_label=_ASK_LABEL,
                backing_faction="lab",
                locks_chain=True,
            ),
        },
        rewards_xp=20,
    ),
    MainQuestStep(
        id="prologue_open",
        title="The Door Opens",
        description=(
            "Return to Mars with the method your allies assembled. The door is "
            "not the end of the signal; it is the first threshold. Beyond "
            "it, the coordinates may finally explain what called you there."
        ),
        trigger_planet_id="mars",
        trigger_system_id="sol",
        rewards_xp=30,
        # Act 0 ends with the door; Act 1 begins with the descent.
        unlocks_step="act1_prison",
    ),
)

__all__ = ["STEPS"]
