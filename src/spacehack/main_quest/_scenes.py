"""Scene registry: quest data names a scene id; this table maps it to code.

Scenes are bespoke presentations written in code FIRST, then triggered by
quest data via the step's ``scene`` field (:data:`MainQuestStep.scene`). The
registry builds lazily (importing implementation modules on first lookup) so
dispatch modules can import :func:`play_scene` with no import cycle — the
same pattern as the objective-handler registry (``handlers.py``).

A scene id with no registered implementation is invalid data: the smoke gate
rejects it, and :func:`play_scene` raises rather than silently skipping a
narrative beat in-game.
"""

from __future__ import annotations

from ..data.main_quest import find_main_quest_step

_SCENES: dict[str, object] = {}


def _build() -> dict[str, object]:
    """Populate the registry on first use (lazy implementation imports)."""
    if _SCENES:
        return _SCENES
    from . import _act0
    from . import _act1
    _SCENES["prologue_transmission"] = _act0.show_prologue_transmission
    _SCENES["sealed_door_discover"] = (
        lambda ctx, **kw: _act0.show_sealed_door_overlay(ctx, "discover")
    )
    _SCENES["sealed_door_open"] = _act0._play_sealed_door_open
    _SCENES["orbit_disclosure"] = _act1.maybe_show_post_prison_orbit
    return _SCENES


def registered_scene_ids() -> tuple[str, ...]:
    """Every scene id the registry can play (used by smoke + tests)."""
    return tuple(sorted(_build().keys()))


def play_scene(ctx, step_id: str, **kwargs) -> object:
    """Play the scene declared on ``step_id``'s step data, if any.

    Returns the scene's return value (``None`` for fire-and-forget
    cutscenes; the disclosure scene returns whether it played).
    Unknown step ids and steps without a ``scene`` are no-ops.
    Raises :class:`ValueError` when the step names an unregistered
    scene id — that is a data bug, not a runtime condition.
    """
    try:
        _step = find_main_quest_step(step_id)
    except KeyError:
        return None
    _scene_id = _step.scene
    if not _scene_id:
        return None
    _impl = _build().get(_scene_id)
    if _impl is None:
        raise ValueError(
            f"unregistered main quest scene id: {_scene_id!r} (step {step_id!r})"
        )
    return _impl(ctx, **kwargs)


__all__ = ["play_scene", "registered_scene_ids"]
