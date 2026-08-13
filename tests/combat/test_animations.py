"""Tests for combat animation classification and floating damage text.

Covers the deterministic parts of the combat presentation layer: popup
label building (hits, EMP strips, glances, zero-damage), weapon-family
classification, and the native floating-text geometry. The pygame
drawing itself is covered by the overlay tests.
"""

from __future__ import annotations

from src.spacehack import world
from src.spacehack.combat import _animations, _shot_animations


# ---------------------------------------------------------------------------
# _damage_popup_for
# ---------------------------------------------------------------------------

def test_damage_popup_shows_hull_total_in_orange() -> None:
    assert _animations._damage_popup_for(6, 0, False) == ("-6", (255, 140, 70))


def test_damage_popup_shows_shield_strip_in_cyan() -> None:
    assert _animations._damage_popup_for(0, 20, True) == ("-20", (120, 220, 255))


def test_damage_popup_includes_absorbed_shields_in_total() -> None:
    # 4 hull + 3 shields absorbed = the log reports 7 total damage.
    assert _animations._damage_popup_for(4, 3, False) == ("-7", (255, 140, 70))


def test_damage_popup_glance_prefixes_pale_gold_label() -> None:
    assert _animations._damage_popup_for(
        3, 0, False, glancing=True,
    ) == ("GLANCE -3", (235, 205, 150))


def test_damage_popup_zero_damage_is_none() -> None:
    assert _animations._damage_popup_for(0, 0, False) is None
    # An EMP against a shieldless target strips nothing -> no popup.
    assert _animations._damage_popup_for(0, 0, True) is None


def test_miss_popup_is_detected_by_label_text() -> None:
    miss = _animations._MISS_POPUP
    assert _animations._is_miss(miss) is True
    assert _animations._is_miss(("-6", (255, 140, 70))) is False
    assert _animations._is_miss(None) is False


# ---------------------------------------------------------------------------
# _shot_family — weapon-appropriate animation classification
# ---------------------------------------------------------------------------

def test_shot_family_classifies_ship_weapons_by_slot_type() -> None:
    assert _shot_animations._shot_family("light_laser") == "laser"
    assert _shot_animations._shot_family("heavy_laser") == "laser"
    assert _shot_animations._shot_family("plasma_cannon") == "plasma"
    assert _shot_animations._shot_family("light_missile") == "missile"
    assert _shot_animations._shot_family("emp_missile") == "missile"


def test_shot_family_classifies_ground_weapons_by_damage_type() -> None:
    assert _shot_animations._shot_family("fists", ground=True) == "melee"
    assert _shot_animations._shot_family("combat_knife", ground=True) == "melee"
    assert _shot_animations._shot_family("kinetic_pistol", ground=True) == "kinetic"
    assert _shot_animations._shot_family("laser_rifle", ground=True) == "laser"
    assert _shot_animations._shot_family("plasma_pistol", ground=True) == "plasma"


def test_shot_family_falls_back_to_laser_on_unknown_id() -> None:
    assert _shot_animations._shot_family("not_a_weapon") == "laser"
    assert _shot_animations._shot_family("not_a_weapon", ground=True) == "laser"


# ---------------------------------------------------------------------------
# Native floating-text queue
# ---------------------------------------------------------------------------

def _clean_effects(monkeypatch) -> None:
    monkeypatch.setattr(_animations, "_effects", None)


def test_active_floaters_consumes_queued_text(monkeypatch) -> None:
    _clean_effects(monkeypatch)
    from src.spacehack.pygame_overlay import FloatingText

    _animations._set_floaters([
        FloatingText("-6", 10, 8, (255, 140, 70), 1, 8),
    ])

    assert _animations.active_floaters() == (
        FloatingText("-6", 10, 8, (255, 140, 70), 1, 8),
    )
    # Consume-on-read: a second read draws nothing stale.
    assert _animations.active_floaters() == ()


def test_active_floaters_empty_without_effects(monkeypatch) -> None:
    _clean_effects(monkeypatch)
    assert _animations.active_floaters() == ()


def test_floater_for_places_text_one_row_above_target(monkeypatch) -> None:
    _clean_effects(monkeypatch)
    from src.spacehack.pygame_overlay import FloatingText

    floater = _animations._floater_for(
        world.Position(12, 9), ("-6", (255, 140, 70)), age=1, lifetime=8,
        cam_x=2, cam_y=3, view_w=80, view_h=54,
    )

    assert floater == FloatingText(
        "-6", 10, 5, (255, 140, 70), 1, 8,
    )


def test_floater_for_offscreen_target_is_none(monkeypatch) -> None:
    _clean_effects(monkeypatch)
    assert _animations._floater_for(
        world.Position(200, 9), ("-6", (255, 140, 70)), age=0, lifetime=8,
        cam_x=2, cam_y=3, view_w=80, view_h=54,
    ) is None
    assert _animations._floater_for(
        world.Position(12, 9), None, age=0, lifetime=8,
        cam_x=2, cam_y=3, view_w=80, view_h=54,
    ) is None


def test_set_frame_floater_queues_only_in_viewport(monkeypatch) -> None:
    _clean_effects(monkeypatch)
    _animations._set_frame_floater(
        world.Position(12, 9), ("-6", (255, 140, 70)), age=0, lifetime=8,
        cam_x=2, cam_y=3, view_w=80, view_h=54,
    )
    assert len(_animations.active_floaters()) == 1

    _animations._set_frame_floater(
        world.Position(200, 9), ("-6", (255, 140, 70)), age=0, lifetime=8,
        cam_x=2, cam_y=3, view_w=80, view_h=54,
    )
    assert _animations.active_floaters() == ()
