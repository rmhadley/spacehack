"""Act 1 post-prison research: the first interpretation of the archive.

The Mars-orbit disclosure scene records how much of the recovered archive the
player shared. This step then sends the player to Alpha Centauri's Science Port
for the first human cross-check; it does not translate the deeper warning yet.

Design doc: docs/design/in_progress/07_DESIGN_MAIN_QUEST.md
"""

from __future__ import annotations

from . import MainQuestStep, QuestDialogue


STEPS: tuple[MainQuestStep, ...] = (
    MainQuestStep(
        id="research_alpha",
        title="The First Reading",
        description=(
            "Take the recovered archive to the Research Officer at Alpha Centauri's "
            "Science Port. The archive contains a coordinate sequence, but the "
            "first reading is only a hypothesis: the route appears to continue "
            "past the Luyten blockade. Compare the raw record with an independent "
            "scientific analysis before deciding what the data is asking you to do."
        ),
        trigger_planet_id="ac_station",
        trigger_system_id="alpha_centauri",
        requires_step="act1_prison",
        objective_type="visit",
        requires_npc_id="research_officer",
        auto_advance=False,
        completion_flavor=(
            "The Alpha Centauri instruments separate the archive's first layer from "
            "the noise. It is a route, not a destination: the coordinates pass "
            "beyond the Luyten blockade and continue through systems no human "
            "survey has mapped. The Research Officer refuses to call that proof "
            "of a colony, a weapon, or a rescue path. The next reading will need "
            "more of the archive than anyone can safely expose at once."
        ),
        dialogues={
            "research_officer": QuestDialogue(
                npc_id="research_officer",
                trigger_on_talk=True,
                intro=(
                    "You brought the Mars archive. Before we call it a map, I want to "
                    "know which parts came from the instrument and which parts came "
                    "from the interpretation you received on Mars. Put the raw record "
                    "on the table. We will isolate the coordinate layer first and leave "
                    "the warnings alone until we know how they are encoded."
                ),
                active=(
                    "The first reading is waiting in the lab. We can confirm a route "
                    "beyond Luyten's blockade, but not what travels along it or why "
                    "the archive was preserved. Bring the disclosure record and we "
                    "will compare it against the raw signal."
                ),
                complete=(
                    "The route is real, and it continues beyond Luyten. That is the "
                    "least dangerous conclusion we can defend. The archive's other "
                    "layers are still entangled: network, warning, and something "
                    "that may be an identity. We should separate them before we "
                    "try to make the old system answer."
                ),
                option_label="Begin the first interpretation",
                dialogue_planet_id="ac_station",
            ),
        },
        rewards_xp=100,
    ),
)


__all__ = ["STEPS"]
