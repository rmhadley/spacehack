"""Tests for the minimal reusable main-quest data validator."""

from __future__ import annotations

from dataclasses import replace

from tools.check_main_quest import validate_main_quest_data
from src.spacehack.data.main_quest import MainQuestStep, list_raw_main_quest_steps
from src.spacehack.main_quest._heat import registered_heat_tags
from src.spacehack.main_quest._scenes import registered_scene_ids
from src.spacehack.main_quest.handlers import registered_objective_types
from src.spacehack.text import overlay


_VALID_STORY = {
    "step.example.title": "Example",
    "step.example.description": "Do the example.",
}


def _step() -> MainQuestStep:
    """Return a minimal structurally valid test step."""
    return MainQuestStep(id="example")


def _errors(step: MainQuestStep, story_values=None) -> tuple[str, ...]:
    return validate_main_quest_data(
        (step,),
        objective_types=("talk",),
        heat_tags=("known_heat",),
        scene_ids=("known_scene",),
        story_values=_VALID_STORY if story_values is None else story_values,
    )


def test_production_main_quest_data_passes_minimal_validator():
    assert validate_main_quest_data(
        list_raw_main_quest_steps(),
        objective_types=registered_objective_types(),
        heat_tags=registered_heat_tags(),
        scene_ids=registered_scene_ids(),
        story_values=overlay(),
    ) == ()


def test_unknown_objective_type_is_reported():
    _errors_found = _errors(replace(_step(), objective_type="not_real"))

    assert _errors_found == (
        "step 'example' uses unknown objective_type 'not_real' (no handler).",
    )


def test_dangling_requires_and_unlocks_are_reported():
    _errors_found = _errors(replace(
        _step(),
        requires_step="missing prerequisite",
        unlocks_step="missing unlock",
    ))

    assert _errors_found == (
        "step 'example' requires unknown step 'missing prerequisite'.",
        "step 'example' unlocks unknown step 'missing unlock'.",
    )


def test_unknown_heat_tag_is_reported():
    _errors_found = _errors(replace(_step(), heat=("unknown_heat",)))

    assert _errors_found == (
        "step 'example' uses unknown heat tag 'unknown_heat'.",
    )


def test_unregistered_scene_is_reported():
    _errors_found = _errors(replace(_step(), scene="missing_scene"))

    assert _errors_found == (
        "step 'example' references unregistered scene 'missing_scene'.",
    )


def test_missing_required_story_text_is_reported():
    _errors_found = _errors(_step(), story_values={})

    assert _errors_found == (
        "step 'example' is missing required story text key 'step.example.title'.",
        "step 'example' is missing required story text key 'step.example.description'.",
    )


def test_descriptionless_steps_only_require_a_title():
    _descriptionless = replace(_step(), description_required=False)

    assert _errors(_descriptionless, {"step.example.title": "Example"}) == ()
