"""Tests for the persistent full-run console log."""

from types import SimpleNamespace

from src.spacehack import console_log, input_helpers, message_log, pygame_engine


def test_message_log_keeps_full_history_but_recent_keeps_hud_capacity():
    log = message_log.MessageLog(capacity=2)
    log.add("first")
    log.add_colored("second", (1, 2, 3))
    log.add("third")

    assert [entry.text for entry in log.recent()] == ["second", "third"]
    assert [entry.text for entry in log.history()] == ["first", "second", "third"]
    assert log.history()[1].fg == (1, 2, 3)


def test_repeat_messages_coalesce_with_count_suffix():
    log = message_log.MessageLog()
    log.add("A wall blocks your path.")
    log.add("A wall blocks your path.")
    log.add("A wall blocks your path.")

    assert [entry.text for entry in log.history()] == ["A wall blocks your path. x3"]


def test_repeat_coalescing_does_not_merge_across_colors():
    log = message_log.MessageLog()
    log.add("A wall blocks your path.")
    log.add_colored("A wall blocks your path.", message_log.COLOR_IMPORTANT_EVENT)
    log.add_colored("A wall blocks your path.", message_log.COLOR_IMPORTANT_EVENT)

    assert [entry.text for entry in log.history()] == [
        "A wall blocks your path.",
        "A wall blocks your path. x2",
    ]
    assert [entry.fg for entry in log.history()] == [
        message_log.COLOR_MESSAGE,
        message_log.COLOR_IMPORTANT_EVENT,
    ]


def test_new_message_after_repeat_appends_fresh_entry():
    log = message_log.MessageLog()
    log.add("A wall blocks your path.")
    log.add("A wall blocks your path.")
    log.add("You move onward.")

    assert [entry.text for entry in log.history()] == [
        "A wall blocks your path. x2",
        "You move onward.",
    ]


def test_repeat_parts_splits_suffix_and_plain_text():
    assert message_log._repeat_parts("A wall blocks your path. x10") == (
        "A wall blocks your path.",
        10,
    )
    assert message_log._repeat_parts("A wall blocks your path.") == (
        "A wall blocks your path.",
        1,
    )


def test_message_log_load_history_replaces_entries():
    log = message_log.MessageLog()
    log.add("old")
    log.load_history([
        message_log.MessageEntry("restored", (4, 5, 6)),
    ])

    assert [entry.text for entry in log.history()] == ["restored"]
    assert log.history()[0].fg == (4, 5, 6)


def test_console_log_frame_formats_oldest_first_and_is_scrollable():
    log = message_log.MessageLog()
    log.add("departed Earth")
    log.add_colored("enemy sighted", message_log.COLOR_IMPORTANT_EVENT)
    ctx = SimpleNamespace(log=log)

    frame = console_log._frame(ctx)

    assert frame.title == "CONSOLE LOG"
    assert frame.body == ("> departed Earth", "> enemy sighted")
    assert frame.rows == ()
    assert frame.scrollable is True
    assert frame.start_at_end is True
    assert "ESC close" in frame.footer[0]
    assert "PAGE UP/DOWN" not in frame.footer[0]


def test_backslash_input_accepts_normalized_name_and_rejects_other_events():
    assert input_helpers._is_backslash_press(
        pygame_engine.PygameInputEvent(kind="keydown", key_name="backslash"),
    )
    assert input_helpers._is_backslash_press(
        pygame_engine.PygameInputEvent(kind="keydown", key_name="\\"),
    )
    assert input_helpers._is_backslash_press(
        pygame_engine.PygameInputEvent(kind="keydown", key_name="nonusbackslash"),
    )
    assert not input_helpers._is_backslash_press(
        pygame_engine.PygameInputEvent(kind="keyup", key_name="backslash"),
    )
    assert not input_helpers._is_backslash_press(
        pygame_engine.PygameInputEvent(kind="keydown", key_name="slash"),
    )


def test_backslash_key_name_normalizes_to_action_name():
    assert pygame_engine.normalize_key_name("\\") == "backslash"
    assert pygame_engine.normalize_key_name("nonusbackslash") == "backslash"


def test_console_modal_propagates_quit(monkeypatch):
    ctx = SimpleNamespace(context=object(), log=message_log.MessageLog())
    monkeypatch.setattr(
        console_log.pygame_screen,
        "run_for_context",
        lambda *_args, **_kwargs: ("QUIT", "", 0),
    )

    assert console_log.open_console_log(ctx) == "QUIT"
