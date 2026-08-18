#!/usr/bin/env python3
"""Validate the reusable main-quest data contract.

The pure validator accepts explicit catalog inputs so tests can exercise bad
edits without modifying the shipped quest data. The command-line entry point
loads the production catalogs and reports every actionable data error.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.spacehack.data.main_quest import (  # noqa: E402
    MainQuestStep,
    list_raw_main_quest_steps,
)
from src.spacehack.main_quest._heat import registered_heat_tags  # noqa: E402
from src.spacehack.main_quest.handlers import (  # noqa: E402
    registered_objective_types,
)
from src.spacehack.main_quest._scenes import registered_scene_ids  # noqa: E402
from src.spacehack.text import overlay  # noqa: E402


def _missing_story_keys(
    step: MainQuestStep,
    story_values: Mapping[str, str],
) -> tuple[str, ...]:
    """Return required title/description keys missing from the overlay."""
    _keys = [f"step.{step.id}.title"]
    if step.description_required:
        _keys.append(f"step.{step.id}.description")
    return tuple(
        _key for _key in _keys
        if not story_values.get(_key, "")
    )


def validate_main_quest_data(
    steps: Sequence[MainQuestStep] | Iterable[MainQuestStep],
    *,
    objective_types: Iterable[str],
    heat_tags: Iterable[str],
    scene_ids: Iterable[str],
    story_values: Mapping[str, str],
) -> tuple[str, ...]:
    """Return clear errors for invalid reusable quest data.

    This function is pure: it performs no imports, file access, mutation, or
    logging. It intentionally validates only the minimal Phase 5 contract:
    objective handlers, prerequisite/unlock references, heat tags, scene
    registrations, and required step story text. Chain termination and reward
    balance remain deliberately outside this validator.
    """
    _steps = tuple(steps)
    _ids = {step.id for step in _steps}
    _objective_types = set(objective_types)
    _heat_tags = set(heat_tags)
    _scene_ids = set(scene_ids)
    _errors: list[str] = []

    for _step in _steps:
        if _step.objective_type not in _objective_types:
            _errors.append(
                f"step {_step.id!r} uses unknown objective_type "
                f"{_step.objective_type!r} (no handler)."
            )
        if _step.requires_step and _step.requires_step not in _ids:
            _errors.append(
                f"step {_step.id!r} requires unknown step "
                f"{_step.requires_step!r}."
            )
        if _step.unlocks_step and _step.unlocks_step not in _ids:
            _errors.append(
                f"step {_step.id!r} unlocks unknown step "
                f"{_step.unlocks_step!r}."
            )
        for _tag in _step.heat:
            if _tag not in _heat_tags:
                _errors.append(
                    f"step {_step.id!r} uses unknown heat tag {_tag!r}."
                )
        if _step.scene and _step.scene not in _scene_ids:
            _errors.append(
                f"step {_step.id!r} references unregistered scene "
                f"{_step.scene!r}."
            )
        for _key in _missing_story_keys(_step, story_values):
            _errors.append(
                f"step {_step.id!r} is missing required story text key "
                f"{_key!r}."
            )
    return tuple(_errors)


def main() -> int:
    """Validate the production main-quest catalogs."""
    _errors = validate_main_quest_data(
        list_raw_main_quest_steps(),
        objective_types=registered_objective_types(),
        heat_tags=registered_heat_tags(),
        scene_ids=registered_scene_ids(),
        story_values=overlay(),
    )
    if _errors:
        for _error in _errors:
            print(f"FAIL: {_error}", file=sys.stderr)
        print(
            f"FAIL: {len(_errors)} main-quest data error(s).",
            file=sys.stderr,
        )
        return 1
    print("PASS: Main quest data check OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
