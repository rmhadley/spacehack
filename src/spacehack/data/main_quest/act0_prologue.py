"""Act 0 prologue steps: signal, Mars gate, door, seek-help fork, open.

Structure only — titles, descriptions, and dialogue text live in
``src/spacehack/data/text/`` (see ``_apply_text_overlay``).

Design doc: docs/design/in_progress/07_DESIGN_MAIN_QUEST.md
"""

from __future__ import annotations

from . import MainQuestStep, QuestDialogue


STEPS: tuple[MainQuestStep, ...] = (
    MainQuestStep(
        id="prologue_signal",
        # Auto-completes in the same instant it triggers (first jump out
        # of Sol), so the quest-log breadcrumb never renders it — the
        # beat is carried by the transmission overlay + log lines, and
        # the description is intentionally absent.
        description_required=False,
        trigger_planet_id="mars",
        trigger_system_id="sol",
        scene="prologue_transmission",  # incoming-comms overlay on the first jump out
    ),
    MainQuestStep(
        id="prologue_mars_unlocked",
        trigger_planet_id="mars",
        trigger_system_id="sol",
        requires_step="prologue_signal",
    ),
    MainQuestStep(
        id="prologue_mars_entrance",
        trigger_planet_id="mars",
        trigger_system_id="sol",
        requires_step="prologue_mars_unlocked",
        scene="sealed_door_discover",  # the sealed-door discover overlay on bump
    ),
    MainQuestStep(
        id="prologue_seek_help",
        requires_step="prologue_mars_entrance",
        dialogues={
            "barkeep": QuestDialogue(
                npc_id="barkeep",
                trigger_on_talk=True,
                backing_faction="bar",
                locks_chain=True,
            ),
            "guild_master": QuestDialogue(
                npc_id="guild_master",
                trigger_on_talk=True,
                backing_faction="merchants",
                locks_chain=True,
            ),
            "militia_captain": QuestDialogue(
                npc_id="militia_captain",
                trigger_on_talk=True,
                backing_faction="militia",
                locks_chain=True,
            ),
            # The lab seek-help lead keys off the regular research
            # officer — the xenolinguist (lab-chain expert) only
            # appears once her chain step is live.
            "research_officer": QuestDialogue(
                npc_id="research_officer",
                trigger_on_talk=True,
                backing_faction="lab",
                locks_chain=True,
            ),
        },
        rewards_xp=20,
    ),
    MainQuestStep(
        id="prologue_open",
        trigger_planet_id="mars",
        trigger_system_id="sol",
        rewards_xp=30,
        scene="sealed_door_open",  # door-opening animation + overlay on bump
        # Act 0 ends with the door; Act 1 begins with the descent.
        unlocks_step="act1_prison",
    ),
)

__all__ = ["STEPS"]
