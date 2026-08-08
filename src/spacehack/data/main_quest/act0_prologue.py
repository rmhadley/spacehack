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
        description=(
            "A garbled transmission broke through the static — a burst "
            "of coordinates, then silence. They resolve to somewhere on "
            "Mars."
        ),
        trigger_planet_id="mars",
        trigger_system_id="sol",
    ),
    MainQuestStep(
        id="prologue_mars_unlocked",
        title="Mars",
        description=(
            "The transmission's coordinates point to a location on "
            "Mars. The surface is explorable — see what's out there."
        ),
        trigger_planet_id="mars",
        trigger_system_id="sol",
        requires_step="prologue_signal",
    ),
    MainQuestStep(
        id="prologue_mars_entrance",
        title="The Door",
        description=(
            "Among the red-dust ruins you find a sealed door of alien "
            "make. No visible mechanism, older than the colony. It will "
            "not open with any human tool."
        ),
        trigger_planet_id="mars",
        trigger_system_id="sol",
        requires_step="prologue_mars_unlocked",
    ),
    MainQuestStep(
        id="prologue_seek_help",
        title="Seek Help",
        description=(
            "The door won't open with any human tool. Ask around — the "
            "factions each have their own way in. Choose who helps you; "
            "that choice will echo."
        ),
        requires_step="prologue_mars_entrance",
        dialogues={
            "barkeep": QuestDialogue(
                npc_id="barkeep",
                trigger_on_talk=True,
                intro=(
                    "Heard about the thing in the dust? The militia "
                    "sealed it — or someone did. There was a guy got a "
                    "door like that open once. Cost him a hand. Here's "
                    "how he did it."
                ),
                active=(
                    "Still stuck on that door? The rig's yours when "
                    "you want it — a cut of whatever's inside, and the "
                    "story for the bar."
                ),
                complete=(
                    "So we've got a deal? Good. The old hand who "
                    "cracked that door — I'll make the introduction. "
                    "Come back with the story, and the bar pays in "
                    "drinks."
                ),
                locked=(
                    "You've already got a way in, friend. The bar "
                    "still wants the story when you're done."
                ),
                option_label=_ASK_LABEL,
                backing_faction="bar",
                locks_chain=True,
            ),
            "guild_master": QuestDialogue(
                npc_id="guild_master",
                trigger_on_talk=True,
                intro=(
                    "Alien tech on Mars? That's the most valuable "
                    "cargo in history. A salvager's cutter tuned to "
                    "alien alloys — sign the contract and it's yours. "
                    "First rights to what's inside."
                ),
                active=(
                    "The cutter's waiting. Sign here — first look at "
                    "anything inside, and the tool's yours."
                ),
                complete=(
                    "Contract signed, then. The cutter comes when the "
                    "work's done — first rights to what's inside, "
                    "remember."
                ),
                locked=(
                    "You've found another way in, then. A pity — the "
                    "guild pays handsomely for a look."
                ),
                option_label=_ASK_LABEL,
                backing_faction="merchants",
                locks_chain=True,
            ),
            "militia_captain": QuestDialogue(
                npc_id="militia_captain",
                trigger_on_talk=True,
                intro=(
                    "There is no door. Whatever you saw out there, "
                    "forget it. ...Quietly, off the books, the patrol "
                    "has seen this tech before. The 'incident'. We have "
                    "schematics and a breach charge that will open it. "
                    "You say nothing. Understood?"
                ),
                active=(
                    "The schematics are ready. One condition: this "
                    "never happened. Bring back proof of what's behind "
                    "it, and the patrol remembers nothing."
                ),
                complete=(
                    "Understood. The work has begun — report when "
                    "it's done, and we never speak of this again."
                ),
                locked=(
                    "You've made your choice, then. Keep it off the "
                    "books — the patrol has no part in this."
                ),
                option_label=_ASK_LABEL,
                backing_faction="militia",
                locks_chain=True,
            ),
            "research_officer": QuestDialogue(
                npc_id="research_officer",
                trigger_on_talk=True,
                intro=(
                    "A sealed structure on Mars? I need to study it. "
                    "Bring me a sample of the door's material — we'll "
                    "analyze it, and the resonance key it unlocks will "
                    "open the way."
                ),
                active=(
                    "The material analysis is promising. Bring the "
                    "sample back and the key is yours — we want a "
                    "specimen from inside for study."
                ),
                complete=(
                    "The work has begun, then. Return to Mars and chip "
                    "a sample off the door — we'll take it from there. "
                    "The truth deserves to be published, not buried."
                ),
                locked=(
                    "You've found other help. Very well — if you "
                    "recover anything, the station will study it."
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
                    "A sealed structure on Mars? The signal isn't "
                    "human — and that door may be the same make. Bring "
                    "me a sample of its material. A resonance key "
                    "from the analysis would open it."
                ),
                active=(
                    "The material analysis is promising. Bring the "
                    "sample back and the key is yours — we want a "
                    "specimen from inside for study."
                ),
                complete=(
                    "The work has begun, then. Return to Mars and chip "
                    "a sample off the door — we'll take it from there. "
                    "The truth deserves to be published, not buried."
                ),
                locked=(
                    "You've found other help. Very well — if you "
                    "recover anything, the station will study it."
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
            "Return to Mars with the means to open the door. The "
            "coordinates still hold a secret."
        ),
        trigger_planet_id="mars",
        trigger_system_id="sol",
        rewards_xp=30,
        # Act 0 ends with the door; Act 1 begins with the descent.
        unlocks_step="act1_prison",
    ),
)

__all__ = ["STEPS"]
