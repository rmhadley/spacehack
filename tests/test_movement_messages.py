"""Regression tests for exploration movement feedback."""

from src.spacehack import __main__ as game_main


def test_space_obstacle_message_describes_solar_objects():
    assert game_main._space_obstacle_message("sun") == "The sun blocks your path."
    assert game_main._space_obstacle_message("planet") == "The planet blocks your path."
    assert game_main._space_obstacle_message("jump_point") == "The jump point blocks your path."
    assert game_main._space_obstacle_message("station") == "The station blocks your path."


def test_space_obstacle_message_keeps_true_wall_fallback():
    assert game_main._space_obstacle_message("wall") == "A wall blocks your path."
    assert game_main._space_obstacle_message(None) == "A wall blocks your path."
