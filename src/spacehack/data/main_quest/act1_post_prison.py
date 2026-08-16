"""Act 1 post-prison research: the first interpretation of the archive.

The Mars-orbit disclosure scene records how much of the recovered archive the
player shared. This step then sends the player to Alpha Centauri's Science Port
for the first human cross-check; it does not translate the deeper warning yet.

Step prose (titles, descriptions, dialogue) lives in
``src/spacehack/data/text/`` — the ``MainQuestStep`` entries below are
structural only. ``ArchiveDisclosure`` keeps its prose in Python + the
JSON overlay (``disclosure.<key>.<field>``), matching the NPC / good /
runtime catalogs.

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
        trigger_planet_id="ac_station",
        trigger_system_id="alpha_centauri",
        requires_step="act1_prison",
        objective_type="visit",
        requires_npc_id="research_officer",
        auto_advance=True,
        wait_days=14,
        dialogues={
            "research_officer": QuestDialogue(
                npc_id="research_officer",
                trigger_on_talk=True,
                dialogue_planet_id="ac_station",
            ),
        },
        rewards_xp=100,
    ),
    MainQuestStep(
        id="research_alpha_report",
        trigger_planet_id="ac_station",
        trigger_system_id="alpha_centauri",
        requires_step="research_alpha",
        objective_type="visit",
        requires_npc_id="research_officer",
        auto_advance=False,
        wait_days=0,
        dialogues={
            "research_officer": QuestDialogue(
                npc_id="research_officer",
                trigger_on_talk=True,
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
