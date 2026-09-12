"""Ledger-pane tests for the rumor system (doc 42 phase 1).

The capture renderer is authoritative: render_quest_log with
pane="rumors" paints the verbatim ledger; the pygame layer threads
pane state and TAB internally.
"""

from types import SimpleNamespace

from src.spacehack.framebuffer import FrameBuffer
from src.spacehack.menus._quest_log import render_quest_log
from src.spacehack import rumor as rumor_module
from src.spacehack import pygame_quest_log
from tests.support.quest_ctx import quest_ctx


def _pane_rows(console) -> list[str]:
    """Captured rows as text lines, trailing blanks trimmed."""
    _rows: dict[int, str] = {}
    for command in console.commands:
        _rows.setdefault(command.y, "")
        _rows[command.y] = _rows[command.y][:command.x] + command.char + \
            _rows[command.y][command.x + 1:]
    lines = [_rows[y].rstrip() for y in sorted(_rows)]
    while lines and not lines[-1]:
        lines.pop()
    return lines


def _render_rumors(ctx):
    console = FrameBuffer(120, 60)
    render_quest_log(
        console, ctx, pane="rumors", screen_width=120, screen_height=60,
    )
    return console


def test_rumors_pane_paints_heard_text_verbatim_in_order():
    console = _render_rumors(quest_ctx(known_rumors=["dark_berth_2", "dark_berth_1"]))
    text = "\n".join(_pane_rows(console))
    assert "RUMORS" in text
    _second = rumor_module.entry_text("dark_berth_2")
    _first = rumor_module.entry_text("dark_berth_1")
    assert _second.split(". ")[0] in text, "first heard line present"
    assert _first.split(". ")[0] in text, "second heard line present"
    assert text.index(_second.split(". ")[0]) < text.index(_first.split(". ")[0]), \
        "heard order preserved in the ledger"


def test_rumors_pane_empty_state():
    console = _render_rumors(quest_ctx())
    assert "(nothing heard yet)" in "\n".join(_pane_rows(console))


def test_rumors_pane_skips_stale_ids():
    console = _render_rumors(quest_ctx(known_rumors=["retired_rumor"]))
    assert "(nothing heard yet)" in "\n".join(_pane_rows(console))


def test_quests_pane_is_the_default():
    console = FrameBuffer(120, 60)
    render_quest_log(console, quest_ctx(), screen_width=120, screen_height=60)
    text = "\n".join(_pane_rows(console))
    assert "LOGS" in text
    assert "(no active missions)" in text


def _fake_pygame():
    class FakePygame:
        QUIT = 0
        KEYDOWN = 1

        K_ESCAPE = 10
        K_TAB = 11
        K_UP = 12
        K_DOWN = 13
        K_k = 14
        K_j = 15
        K_a = 16
        K_RETURN = 17
        K_KP_ENTER = 18
        KMOD_SHIFT = 1

    return FakePygame()


def _key(fake, value):
    return SimpleNamespace(type=fake.KEYDOWN, key=value)


def test_tab_returns_the_shared_sheet_outcomes():
    fake = _fake_pygame()
    _outcome, _sel, _confirm, pane = pygame_quest_log._handle_key(
        fake, _key(fake, fake.K_TAB), 2, False, 3, "quests")
    assert (_outcome, _sel, pane) == ("TAB", 2, "quests")
    _shift = SimpleNamespace(type=fake.KEYDOWN, key=fake.K_TAB, mod=fake.KMOD_SHIFT)
    _outcome, _sel, _confirm, pane = pygame_quest_log._handle_key(
        fake, _shift, 0, False, 3, "rumors")
    assert (_outcome, _sel, pane) == ("SHIFT_TAB", 0, "rumors")




def test_rumors_pane_scrolls_linearly_and_clamps_low():
    fake = _fake_pygame()
    _outcome, sel, _confirm, pane = pygame_quest_log._handle_key(
        fake, _key(fake, fake.K_UP), 0, False, 0, "rumors")
    assert (sel, pane) == (0, "rumors")
    _outcome, sel, _confirm, pane = pygame_quest_log._handle_key(
        fake, _key(fake, fake.K_DOWN), 4, False, 0, "rumors")
    assert (sel, pane) == (5, "rumors")


def test_quests_keys_untouched():
    fake = _fake_pygame()
    _outcome, sel, confirm, pane = pygame_quest_log._handle_key(
        fake, _key(fake, fake.K_DOWN), 0, False, 3, "quests")
    assert (sel, pane) == (1, "quests")
    _outcome, sel, confirm, pane = pygame_quest_log._handle_key(
        fake, _key(fake, fake.K_a), 1, False, 3, "quests")
    assert confirm is True
    _outcome, sel, confirm, pane = pygame_quest_log._handle_key(
        fake, _key(fake, fake.K_RETURN), 1, True, 3, "quests")
    assert _outcome == "ABANDONED"


def test_frames_for_splits_panes_for_font_fitting():
    # The ledger scrolls, so rumors frames constrain font WIDTH only;
    # quests frames drive both. (REVIEW round 2.)
    quests, rumors = pygame_quest_log._frames_for(
        quest_ctx(known_rumors=["dark_berth_1"])
    )
    assert len(quests) == 2  # no missions: (-1,) selections x two confirms
    assert all(frame.tabs == ("QUESTS", "RUMORS") and frame.active_tab == 0
               for frame in quests)
    assert len(rumors) == 1
    assert rumors[0].active_tab == 1


# --- playtest round: pane alignment + the phantom scrollbar -----------------


def _first_content_row(frame) -> int:
    for i, row in enumerate(frame.rows):
        if any(span.text.strip() for span in row):
            return i
    return -1


def test_empty_states_share_the_first_content_row():
    """Tabbing must not jump text: '(nothing heard yet)' and '(no
    active missions)' land on the same captured row."""
    from src.spacehack import pygame_quest_log as pql

    rumors = pql._capture_frame(quest_ctx(), 0, False, "rumors")
    quests = pql._capture_frame(quest_ctx(), -1, False, "quests")
    assert _first_content_row(rumors) == _first_content_row(quests)


def test_fitting_ledger_carries_no_scrollbar_rows():
    """The phantom scrollbar: trailing blanks (and the fixed-position
    hint row) were counted as content, so every ledger 'needed'
    scrolling. The frame now ends at its last text row."""
    from src.spacehack import pygame_quest_log as pql

    empty = pql._capture_frame(quest_ctx(), 0, False, "rumors")
    assert len(empty.rows) <= 2  # blank + '(nothing heard yet)'
    assert empty.hint.startswith("UP/DOWN")
    heard = pql._capture_frame(
        quest_ctx(known_rumors=["dark_berth_1", "dark_berth_2"]), 0, False,
        "rumors",
    )
    assert any(span.text.strip() for span in heard.rows[-1])
    assert heard.hint.startswith("UP/DOWN")


# --- dig-site pointer lines (doc 42 phase 4, SETTLED 37) -------------------


def test_rumors_pane_renders_site_pointer_lines_after_keyring():
    _sites = [
        {"id": "s1", "planet": "mars", "name": "Sunken Vault"},
        {"id": "s2", "planet": "venus", "name": "Rusted Warren"},
    ]
    console = _render_rumors(quest_ctx(
        known_rumors=["dark_berth_1"], discovered_sites=_sites,
    ))
    text = "\n".join(_pane_rows(console))
    assert "Charts a buried site: Sunken Vault, on Mars." in text
    assert "Charts a buried site: Rusted Warren, on Venus." in text
    _keyring = rumor_module.entry_text("dark_berth_1").split(". ")[0]
    assert text.index(_keyring) < text.index("Sunken Vault"), \
        "keyring entries before site pointers"


def test_rumors_pane_shows_sites_without_calling_them_heard():
    console = _render_rumors(quest_ctx(discovered_sites=[
        {"id": "s1", "planet": "mars", "name": "Sunken Vault"},
    ]))
    text = "\n".join(_pane_rows(console))
    assert "Sunken Vault" in text
    assert "(nothing heard yet)" not in text


def test_rumors_pane_pointer_lines_keep_reveal_order():
    _sites = [
        {"id": "s5", "planet": "venus", "name": "Alpha Find"},
        {"id": "s2", "planet": "mars", "name": "Beta Find"},
    ]
    console = _render_rumors(quest_ctx(discovered_sites=_sites))
    text = "\n".join(_pane_rows(console))
    assert text.index("Alpha Find") < text.index("Beta Find"), \
        "reveal order preserved"


def test_pointer_lines_skip_stale_planets(monkeypatch):
    from src.spacehack import digs as digs_module

    monkeypatch.setattr(
        digs_module, "find_planet_spec",
        lambda pid: (_ for _ in ()).throw(KeyError(pid))
        if pid == "venus" else type("S", (), {"name": "Mars"}),
    )
    lines = digs_module.pointer_lines(SimpleNamespace(discovered_sites=[
        {"id": "s1", "planet": "mars", "name": "Sunken Vault"},
        {"id": "s2", "planet": "venus", "name": "Rusted Warren"},
    ]))
    assert lines == ["Charts a buried site: Sunken Vault, on Mars."]


def test_pointer_lines_empty_for_no_sites():
    from src.spacehack import digs as digs_module
    assert digs_module.pointer_lines(
        SimpleNamespace(discovered_sites=[]),
    ) == []
