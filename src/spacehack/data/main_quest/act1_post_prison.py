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
        auto_advance=True,
        wait_days=14,
        ready_message=(
            "The Alpha Centauri processing cluster has completed its first pass. "
            "Return to the Research Officer at the Science Port to review the "
            "initial translation."
        ),
        completion_flavor=(
            "The Research Officer seals the raw archive inside the Alpha Centauri "
            "processing cluster. The first pass will segment the alien signal, "
            "separate coordinate patterns from containment records and warnings, "
            "and test whether the recurring symbols survive translation. It will "
            "take time. Until the cluster finishes, nobody can honestly say whether "
            "the pattern is a route, a warning, or both."
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
                    "The archive is in the processing cluster. We have not translated "
                    "it yet; we are separating the raw layers and checking that the "
                    "alien symbols remain stable outside the prison terminal. The "
                    "first report will come when the cluster has enough evidence to "
                    "say what the coordinate pattern actually means."
                ),
                option_label="Begin the first interpretation",
                dialogue_planet_id="ac_station",
            ),
        },
        rewards_xp=100,
    ),
    MainQuestStep(
        id="research_alpha_report",
        title="The First Translation",
        description=(
            "Return to the Research Officer at Alpha Centauri's Science Port after "
            "the processing cluster completes its first pass. Review what the "
            "coordinate layer means and what remains untranslated."
        ),
        trigger_planet_id="ac_station",
        trigger_system_id="alpha_centauri",
        requires_step="research_alpha",
        objective_type="visit",
        requires_npc_id="research_officer",
        auto_advance=False,
        wait_days=0,
        ready_message=(
            "The Alpha Centauri processing cluster has completed its first pass. "
            "Return to the Research Officer at the Science Port to review the "
            "initial translation."
        ),
        completion_flavor=(
            "The first translation pass is complete. The lab isolates a recurring "
            "coordinate grammar from the containment records and warning markers. "
            "The pattern continues beyond the Luyten blockade into systems no human "
            "survey has mapped. It proves a route exists, but not who built it, who "
            "used it, or what waits at its far end. The warning layer remains only "
            "partially translated."
        ),
        dialogues={
            "research_officer": QuestDialogue(
                npc_id="research_officer",
                trigger_on_talk=True,
                intro=(
                    "The processing cluster has finished its first pass. We can now "
                    "read a recurring coordinate grammar, but only in fragments. "
                    "It points beyond the Luyten blockade into unmapped systems. The "
                    "containment records and warnings are still tangled through it, "
                    "so this is a route hypothesis - not a destination, and not an "
                    "answer about what escaped the prison."
                ),
                active=(
                    "The first translation report is ready for review. We isolated "
                    "the coordinate layer, but the warning symbols resist a stable "
                    "translation. We need to decide what the route is worth before "
                    "we expose more of the archive."
                ),
                complete=(
                    "Now we know the route is real. Beyond Luyten lies a linked chain "
                    "of dead systems, not a single destination. The archive still "
                    "withholds the identity of the prisoner and the meaning of its "
                    "warnings. That is the next question - and the answer may be "
                    "watching for the signal we just sent."
                ),
                option_label="Review the first translation",
                dialogue_planet_id="ac_station",
            ),
        },
        rewards_xp=120,
    ),
)


__all__ = ["STEPS"]
