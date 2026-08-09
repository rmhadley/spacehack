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
            "The Alpha Centauri instruments finish their first pass over the raw "
            "archive. They isolate a recurring coordinate grammar from the prison "
            "records, warning markers, and unresolved signal buried around it. The "
            "pattern continues beyond the Luyten blockade through systems no human "
            "survey has mapped. It is evidence of a route, not an explanation of "
            "where the route ends or what used it. The deeper layers will require "
            "more processing - and more of the archive than anyone can safely expose "
            "at once."
        ),
        dialogues={
            "research_officer": QuestDialogue(
                npc_id="research_officer",
                trigger_on_talk=True,
                intro=(
                    "You brought the recovered Mars data. Good. Do not call it a map "
                    "yet. The terminal did not give us a picture; it gave us a layered "
                    "signal with several systems speaking over one another. I can see "
                    "repeated structures - coordinate patterns, machine-state records, "
                    "and warning markers - but I cannot tell which layer belongs to the "
                    "prison, which describes a route, or which is a response to something "
                    "else. We will preserve the raw transfer, clean the signal, and "
                    "translate the simplest recurring symbols first. Only then can we "
                    "ask where any of it leads."
                ),
                active=(
                    "The first processing pass is underway. We are not translating "
                    "sentences yet; we are separating recurring symbols from the "
                    "archive's other layers and checking that the patterns survive "
                    "without the prison terminal's distortion. So far the coordinate "
                    "sequence remains intact. It reaches beyond the Luyten blockade, "
                    "but we do not know whether it marks a destination, a transit route, "
                    "or a warning about what lies along it."
                ),
                complete=(
                    "The first translation pass is complete. We isolated a coordinate "
                    "grammar from the containment records and warning markers. The "
                    "pattern continues beyond Luyten into systems no human survey has "
                    "mapped. That proves a route exists; it does not tell us who built "
                    "it, who used it, or why the prison archive preserved it. The next "
                    "pass will have to translate the warnings without allowing the "
                    "coordinate layer to contaminate the result."
                ),
                option_label="Begin the first interpretation",
                dialogue_planet_id="ac_station",
            ),
        },
        rewards_xp=100,
    ),
)


__all__ = ["STEPS"]
