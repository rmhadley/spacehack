"""Act 1 post-prison research: the first interpretation of the archive.

The Mars-orbit disclosure scene records how much of the recovered archive the
player shared. This step then sends the player to Alpha Centauri's Science Port
for the first human cross-check; it does not translate the deeper warning yet.

Design doc: docs/design/in_progress/07_DESIGN_MAIN_QUEST.md
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from . import MainQuestStep, QuestDialogue

_DISCLOSURE_FIELDS = (
    "label",
    "log_message",
    "followup_message",
    "waiting_title",
    "waiting_description",
    "ready_message",
)


@dataclass(frozen=True)
class ArchiveDisclosure:
    """Static story data for the first post-prison archive decision."""

    key: str
    label: str
    log_message: str
    followup_message: str
    waiting_title: str = ""
    waiting_description: str = ""
    ready_message: str = ""


ARCHIVE_DISCLOSURES: tuple[ArchiveDisclosure, ...] = (
    ArchiveDisclosure(
        key="diagnostic_fragment",
        label="Transmit a diagnostic fragment",
        log_message=(
            "A diagnostic fragment leaves the ship. The remote analysis will take "
            "time, and the result will determine what the lab can safely ask of the "
            "full archive."
        ),
        followup_message=(
            "The handoff requires time. Until the response arrives, the route beyond "
            "Luyten remains only a hypothesis."
        ),
        waiting_title="Awaiting fragment analysis...",
        waiting_description=(
            "A diagnostic fragment is being analyzed remotely. When the review is "
            "complete, take the recovered archive to the Research Officer at Alpha "
            "Centauri's Science Port for an independent reading."
        ),
        ready_message=(
            "The diagnostic fragment has been analyzed. Take the recovered archive "
            "to the Research Officer at Alpha Centauri's Science Port for an "
            "independent reading. The work will wait for you; the signal will not "
            "become clearer on its own."
        ),
    ),
    ArchiveDisclosure(
        key="archive_sealed",
        label="Keep the archive sealed",
        log_message=(
            "The archive remains sealed and under your control. Take the intact "
            "record to the Research Officer at Alpha Centauri's Science Port now; "
            "the lab is the next step."
        ),
        followup_message=(
            "The archive is ready for delivery. Reach Alpha Centauri's Science Port "
            "and begin the independent reading."
        ),
    ),
    ArchiveDisclosure(
        key="safe_destination",
        label="Ask for a safe destination",
        log_message=(
            "You transmit a request for a safe handoff, not the archive. The contact "
            "network will arrange a route that does not broadcast the archive's value."
        ),
        followup_message=(
            "The handoff requires time. Until the response arrives, the route beyond "
            "Luyten remains only a hypothesis."
        ),
        waiting_title="Awaiting a secure handoff...",
        waiting_description=(
            "A secure route for the sealed archive is being arranged. When the "
            "handoff is ready, take it to the Research Officer at Alpha Centauri's "
            "Science Port for an independent reading."
        ),
        ready_message=(
            "A secure handoff route has been arranged. Take the sealed archive to "
            "the Research Officer at Alpha Centauri's Science Port for an independent "
            "reading. The work will wait for you; the signal will not become clearer "
            "on its own."
        ),
    ),
)


_DISCLOSURES_BY_KEY = {spec.key: spec for spec in ARCHIVE_DISCLOSURES}


def find_archive_disclosure(key: str) -> ArchiveDisclosure:
    """Look up one orbit disclosure by its persisted key.

    Applies the runtime text overlay (``disclosure.<key>.<field>``)
    so writer edits in the JSON files are live without code changes.
    """
    try:
        _spec = _DISCLOSURES_BY_KEY[key]
    except KeyError:
        raise KeyError(f"unknown archive disclosure key: {key!r}") from None
    from ...text import overlay as _text_overlay
    _text = _text_overlay()
    _changes: dict[str, str] = {}
    for _field in _DISCLOSURE_FIELDS:
        _overlay_key = f"disclosure.{key}.{_field}"
        if _overlay_key in _text:
            _changes[_field] = _text[_overlay_key]
    return replace(_spec, **_changes) if _changes else _spec


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
                option_label="Review the first translation",
                dialogue_planet_id="ac_station",
            ),
        },
        rewards_xp=120,
    ),
)


__all__ = [
    "ArchiveDisclosure",
    "ARCHIVE_DISCLOSURES",
    "find_archive_disclosure",
    "STEPS",
]
