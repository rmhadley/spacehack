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
    assert no_save[0].initial_selected == 0
    assert with_save[0].initial_selected == 1
    assert pygame_menu._initial_selected(no_save) == 0
    assert pygame_menu._initial_selected(with_save) == 1
    oversized = (
        pygame_menu.MenuFrame(
            title="", body="", items=with_save[0].items,
            hints=(), selected=0, initial_selected=999,
        ),
    )
    assert pygame_menu._initial_selected(oversized) == len(with_save[0].items) - 1


def test_title_splash_layout_and_stars_avoid_art_regions():
    class Font:
        def get_linesize(self):
            return 20

        def size(self, text):
            return (len(text) * 10, 20)

    layout = pygame_title._splash_layout(Font(), 1600, 960)
    positions = pygame_title._splash_star_positions(Font(), 1600, 960)

    assert layout["ship_bottom"] < layout["prompt_y"]
    assert len(positions) == 80
    for x, y in positions:
        assert not (
            layout["title_y"] - 20 <= y < layout["title_y"] + len(pygame_title._TITLE_ART) * 20
        )
        assert not (layout["ship_x"] - 8 <= x < 1600 and layout["ship_y"] - 4 <= y < layout["ship_bottom"] + 4)
        assert not (layout["prompt_y"] - 28 <= y < 960)


def test_title_splash_rejects_surface_too_small():
    class Font:
        def get_linesize(self):
            return 20

        def size(self, text):
            return (len(text) * 10, 20)

    try:
        pygame_title._splash_layout(Font(), 300, 200)
    except ValueError as exc:
        assert "does not fit" in str(exc)
    else:
        raise AssertionError("small splash surface must be rejected")


def test_title_splash_uses_shared_runtime_and_dismisses_on_key(monkeypatch):
    calls = []

    class FakePygame:
        QUIT = 1
        KEYDOWN = 2

    event = SimpleNamespace(type=FakePygame.KEYDOWN)
    screen = SimpleNamespace(get_size=lambda: (1600, 960), fill=lambda *_args: None)
    engine = SimpleNamespace(
        pygame=FakePygame,
        logical_surface=screen,
        present=lambda: calls.append("present"),
    )
    context = SimpleNamespace(_runtime=SimpleNamespace(engine=engine))
    monkeypatch.setattr(
        FakePygame,
        "event",
        SimpleNamespace(wait=lambda: event),
        raising=False,
    )
    monkeypatch.setattr(pygame_title, "_splash_font", lambda *args: SimpleNamespace(get_linesize=lambda: 16))
    monkeypatch.setattr(pygame_title, "_draw_splash", lambda *args: calls.append("draw"))

    pygame_title.run_splash_for_context(context)

    assert calls == ["draw", "present"]


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


def test_title_runner_propagates_missing_shared_runtime(monkeypatch):
    monkeypatch.setattr(
        pygame_menu,
        "run_for_context",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            pygame_menu.PygameMenuUnavailable("missing"),
        ),
    )

    try:
        pygame_title.run_for_context(SimpleNamespace(), False)
    except pygame_menu.PygameMenuUnavailable as exc:
        assert str(exc) == "missing"
    else:
        raise AssertionError("title must not fall back to TCOD")


def test_quest_log_capture_excludes_header_block_message_log_and_trailing_blank_rows():
    from src.spacehack.engine import MSG_LOG_HEIGHT, SCREEN_HEIGHT

    capture = SimpleNamespace(
        height=SCREEN_HEIGHT,
        width=10,
        commands=(
            # Legacy screen_header block (title row 2, divider row 3) must be
            # stripped so the Pygame header is not duplicated.
            SimpleNamespace(x=0, y=2, char="Q", fg=(255, 255, 255)),
            SimpleNamespace(x=0, y=3, char="=", fg=(255, 255, 255)),
            # Real content starts at row 5.
            SimpleNamespace(x=0, y=5, char="M", fg=(255, 255, 255)),
            SimpleNamespace(x=0, y=6, char=" ", fg=(255, 255, 255)),
            SimpleNamespace(
                x=0, y=SCREEN_HEIGHT - MSG_LOG_HEIGHT,
                char="L", fg=(255, 255, 255),
            ),
        ),
    )

    rows = pygame_quest_log._quest_rows(capture)

    assert len(rows) == 1
    assert rows[0][0].text == "M"


def test_quest_log_split_hint_moves_trailing_hint_out_of_content():
    hint_row = (pygame_quest_log.QuestSpan(
        "ARROW KEYS navigate - A abandon - ESC close.", (255, 240, 175),
    ),)
    rows = (
        (pygame_quest_log.QuestSpan("MAIN QUEST", (255, 255, 255)),),
        hint_row,
    )

    content, hint = pygame_quest_log._split_hint(rows)

    assert hint == "ARROW KEYS navigate - A abandon - ESC close."
    assert content == ((pygame_quest_log.QuestSpan("MAIN QUEST", (255, 255, 255)),),)


def test_quest_log_split_hint_keeps_unknown_trailing_rows():
    rows = ((pygame_quest_log.QuestSpan("Reward: 500$", (255, 255, 255)),),)

    content, hint = pygame_quest_log._split_hint(rows)

    assert hint == ""
    assert content == rows


def test_quest_log_frame_payload_round_trips_hint():
    frame = pygame_quest_log.QuestFrame(
        rows=((pygame_quest_log.QuestSpan("MAIN QUEST", (255, 255, 255)),),),
        selected=0,
        confirm_abandon=False,
        hint="Press ESC to close.",
    )

    payload = pygame_quest_log._worker_payload((frame,))
    restored = pygame_quest_log._frame_from_payload(
        payload["frames"][pygame_quest_log._frame_key(0, False)]
    )

    assert restored == frame


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
