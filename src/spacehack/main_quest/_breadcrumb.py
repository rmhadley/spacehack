"""Main quest breadcrumb: quest-log objective display."""

from __future__ import annotations

from ..data.main_quest import find_main_quest_step
from ..data.main_quest.act1_post_prison import find_archive_disclosure
from ._core import STATUS_ACTIVE, STATUS_AVAILABLE, _iter_known_steps, step_status
from ._gates import _gating_step_for


_FALLBACK_HANDOFF_OBJECTIVE = (
    "Awaiting archive handoff...",
    "The archive handoff is being prepared. Take the recovered archive to "
    "the Research Officer at Alpha Centauri's Science Port for an "
    "independent reading when the summons arrives.",
)


def _sealed_archive_objective(ctx) -> tuple[str, str] | None:
    """Return the immediate delivery objective for an intact archive."""
    if (
        ctx.main_quest_disclosure == "archive_sealed"
        and step_status(ctx, "research_alpha") in (STATUS_AVAILABLE, STATUS_ACTIVE)
    ):
        return (
            "Deliver the sealed archive",
            "Take the intact recovered archive to the Research Officer at Alpha "
            "Centauri's Science Port for its first independent reading.",
        )
    return None


def _active_step_objective(ctx) -> tuple[str, str] | None:
    """Return the first available or active catalog step objective."""
    for _step_id, _status, _step in _iter_known_steps(ctx):
        if _status in (STATUS_AVAILABLE, STATUS_ACTIVE):
            return (_step.title, _step.description)
    return None


def _research_report_objective() -> tuple[str, str]:
    """Return the breadcrumb shown while the first translation is processing."""
    return (
        "Awaiting the first translation...",
        "The Alpha Centauri processing cluster is separating and translating "
        "the alien archive's layers. Return to the Research Officer when the "
        "first report is ready; the work has no deadline.",
    )


def _research_handoff_objective(ctx) -> tuple[str, str]:
    """Return the choice-aware breadcrumb while a research handoff is gated."""
    try:
        _disclosure = find_archive_disclosure(ctx.main_quest_disclosure)
    except KeyError:
        return _FALLBACK_HANDOFF_OBJECTIVE
    if not _disclosure.waiting_title or not _disclosure.waiting_description:
        return _FALLBACK_HANDOFF_OBJECTIVE
    return (_disclosure.waiting_title, _disclosure.waiting_description)


def _gated_objective(ctx) -> tuple[str, str] | None:
    """Return the breadcrumb for the first pending time-gated step."""
    if not ctx.main_quest_gate:
        return None
    _next_id = next(iter(ctx.main_quest_gate))
    try:
        _next = find_main_quest_step(_next_id)
    except KeyError:
        return None
    if _next_id == "research_alpha_report":
        return _research_report_objective()
    if _next_id == "research_alpha":
        return _research_handoff_objective(ctx)
    _fac = _next.chain or ctx.main_quest_chain or "faction"
    _gating = _gating_step_for(ctx, _next_id)
    _description = (
        _gating.completion_flavor
        if _gating is not None and _gating.completion_flavor
        else "The faction will contact you when they're ready."
    )
    return (f"Awaiting word from the {_fac.capitalize()}...", _description)


def _departure_objective(ctx) -> tuple[str, str] | None:
    """Return the required Mars departure objective before the orbit scene."""
    if (
        ctx.main_quest_progress.get("act1_prison") == "completed"
        and not getattr(ctx, "post_prison_orbit_seen", False)
        and not getattr(ctx, "main_quest_complete", False)
    ):
        return (
            "Leave Mars",
            "Return to your ship and launch from Mars. The recovered archive "
            "is waiting for its first reading.",
        )
    return None


def current_main_quest_objective(ctx) -> tuple[str, str] | None:
    """Return (title, description) of the current breadcrumb step."""
    _sealed = _sealed_archive_objective(ctx)
    if _sealed is not None:
        return _sealed
    _active = _active_step_objective(ctx)
    if _active is not None:
        return _active
    _gated = _gated_objective(ctx)
    if _gated is not None:
        return _gated
    return _departure_objective(ctx)
