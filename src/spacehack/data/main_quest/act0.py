"""Act 0: Prologue — "The Door on Mars".

Story beats (see docs/design/in_progress/07_DESIGN_MAIN_QUEST.md):

    1. ``prologue_signal``     — garbled transmission received while
                                 flying through Sol (first launch).
                                 Auto-triggered by
                                 :func:`spacehack.main_quest.maybe_trigger_signal`.
    2. ``prologue_mars_unlocked`` — checkpoint: Mars surface exploration
                                 unlocks once the signal is received.
                                 Auto-advanced by
                                 :func:`spacehack.main_quest.prepare_mars_surface`.
    3. ``prologue_mars_entrance`` — the player finds the sealed alien
                                 door in the Mars ruins. Completed by
                                 bumping the door (see
                                 :func:`spacehack.main_quest.bump_mars_door`).
    4. ``prologue_seek_help``   — the faction fork seeds here. Each
                                 faction NPC gives a DIFFERENT lead and
                                 offers to open the door their way. The
                                 player's choice plants that faction's
                                 claim early (``backing_faction``) and
                                 unlocks that faction's tool
                                 (``unlock_item``).
    5. ``prologue_open``        — the player returns to Mars with the
                                 tool and opens the door: an empty
                                 ancient alien prison + a data cache
                                 (fuels Act 1).

No time pressure, no fail states. The quest waits forever.
"""

from __future__ import annotations

from . import MainQuestStep, QuestDialogue

# Faction door-opening tools (see the design doc's opening-methods
# table). Unlocked by the corresponding seek_help dialogue entry.
_MILITIA_BREACH = "militia_breach_charge"
_MERCHANT_CUTTER = "merchant_cutter"
_BAR_RIG = "bar_brute_rig"
_LAB_KEY = "lab_resonance_key"

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
                    "You got it open. What was behind it? Tell me "
                    "everything — the bar pays in drinks."
                ),
                option_label=_ASK_LABEL,
                backing_faction="bar",
                unlock_item=_BAR_RIG,
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
                    "You're back from the dust. What did you find in "
                    "there? The guild will pay handsomely for a look."
                ),
                option_label=_ASK_LABEL,
                backing_faction="merchants",
                unlock_item=_MERCHANT_CUTTER,
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
                    "You opened it. What was in the cell? Speak — and "
                    "then we never speak of it again."
                ),
                option_label=_ASK_LABEL,
                backing_faction="militia",
                unlock_item=_MILITIA_BREACH,
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
                    "You recovered data from inside? Extraordinary. "
                    "We must study it — the truth deserves to be "
                    "published, not buried."
                ),
                option_label=_ASK_LABEL,
                backing_faction="lab",
                unlock_item=_LAB_KEY,
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
        requires_step="prologue_seek_help",
        rewards_xp=30,
    ),
)

__all__ = ["STEPS"]
