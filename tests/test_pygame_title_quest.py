"""Tests for title and Quest Log Pygame presentation seams."""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack import pygame_menu, pygame_quest_log, pygame_title, ui


def test_title_frames_include_start_continue_only_when_save_exists():
    no_save = pygame_title.frames(False)
    with_save = pygame_title.frames(True)

    assert [item.action for item in no_save[0].items] == ["NEW_GAME", "TUTORIAL", "EXIT"]
    assert [item.action for item in with_save[0].items] == ["NEW_GAME", "CONTINUE", "TUTORIAL", "EXIT"]
    assert no_save[0].art
    assert no_save[0].items == no_save[1].items


def test_title_runner_maps_pygame_actions_to_legacy_outcomes(monkeypatch):
    monkeypatch.setattr(
        pygame_menu,
        "run_for_context",
        lambda *args, **kwargs: ("SELECT", "CONTINUE", 1),
    )

    assert pygame_title.run_for_context(SimpleNamespace(), True) == (
        ui.TitleMenuOutcome.CONTINUE,
        1,
    )


def test_title_runner_preserves_close_as_exit(monkeypatch):
    monkeypatch.setattr(
        pygame_menu,
        "run_for_context",
        lambda *args, **kwargs: ("QUIT", "", 0),
    )

    assert pygame_title.run_for_context(SimpleNamespace(), False) == (
        ui.TitleMenuOutcome.EXIT,
        0,
    )


def test_title_runner_falls_back_when_pygame_menu_is_unavailable(monkeypatch):
    monkeypatch.setattr(
        pygame_menu,
        "run_for_context",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            pygame_menu.PygameMenuUnavailable("missing"),
        ),
    )

    assert pygame_title.run_for_context(SimpleNamespace(), False) is None


def test_quest_log_capture_excludes_message_log_and_trailing_blank_rows():
    from src.spacehack.engine import MSG_LOG_HEIGHT, SCREEN_HEIGHT

    capture = SimpleNamespace(
        height=SCREEN_HEIGHT,
        width=10,
        commands=(
            SimpleNamespace(x=0, y=0, char="Q", fg=(255, 255, 255)),
            SimpleNamespace(x=0, y=1, char=" ", fg=(255, 255, 255)),
            SimpleNamespace(
                x=0, y=SCREEN_HEIGHT - MSG_LOG_HEIGHT,
                char="L", fg=(255, 255, 255),
            ),
        ),
    )

    rows = pygame_quest_log._quest_rows(capture)

    assert len(rows) == 1
    assert rows[0][0].text == "Q"


def test_quest_log_confirmation_freezes_selection():
    class FakePygame:
        QUIT = 1
        KEYDOWN = 2
        K_ESCAPE = 10
        K_UP = 11
        K_DOWN = 12
        K_k = 13
        K_j = 14
        K_a = 15
        K_RETURN = 16
        K_KP_ENTER = 17
        K_QUESTION = 18

    event = SimpleNamespace(type=FakePygame.KEYDOWN, key=FakePygame.K_DOWN)

    assert pygame_quest_log._handle_key(
        FakePygame, event, 1, True, 3,
    ) == ("IGNORE", 1, True)


def test_quest_log_worker_draws_panel_and_restores_clip():
    calls = []

    class Screen:
        def get_size(self):
            return (1600, 960)

        def set_clip(self, value):
            calls.append(value)

    class FakePygame:
        class Rect:
            def __init__(self, *args):
                self.args = args

    monkeypatch = SimpleNamespace()
    frame = pygame_quest_log.QuestFrame(
        rows=((pygame_quest_log.QuestSpan("QUEST LOG", (255, 255, 255)),),),
        selected=0,
        confirm_abandon=False,
    )
    font = SimpleNamespace(get_linesize=lambda: 20)
    # Patch drawing primitives locally through the module's shared helper.
    original = {
        name: getattr(pygame_quest_log.pygame_ui, name)
        for name in ("draw_panel", "draw_centered_text", "draw_rule", "draw_text", "measure_font")
    }
    try:
        pygame_quest_log.pygame_ui.draw_panel = lambda *args, **kwargs: None
        pygame_quest_log.pygame_ui.draw_centered_text = lambda *args, **kwargs: None
        pygame_quest_log.pygame_ui.draw_rule = lambda *args, **kwargs: None
        pygame_quest_log.pygame_ui.draw_text = lambda *args, **kwargs: None
        pygame_quest_log.pygame_ui.measure_font = lambda _font, text: len(text) * 8
        pygame_quest_log._draw_rows(FakePygame, Screen(), font, frame)
    finally:
        for name, value in original.items():
            setattr(pygame_quest_log.pygame_ui, name, value)

    assert calls
    assert calls[-1] is None
