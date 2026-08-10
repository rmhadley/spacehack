"""Tests for the optional Pygame presentation migration seam."""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack import (
    pygame_batch,
    pygame_menu,
    pygame_merchant,
    pygame_quest_log,
    pygame_ship_buy,
    pygame_ui,
    pygame_world,
)
from src.spacehack.menus import _missions, _planet, _ship_menu
from src.spacehack import navigation, npc


class _FakeFont:
    """Monospace metric fake for pure layout tests."""

    def size(self, text: str) -> tuple[int, int]:
        return len(text) * 10, 24

    def get_linesize(self) -> int:
        return 24


def test_fit_text_uses_renderer_metrics_and_ascii_ellipsis():
    font = _FakeFont()

    assert pygame_ui.fit_text("short", 60, lambda text: font.size(text)[0]) == "short"
    assert pygame_ui.fit_text("long mission title", 100, lambda text: font.size(text)[0]) == "long mi..."
    assert pygame_ui.fit_text("long", 20, lambda text: font.size(text)[0]) == "..."
    assert pygame_ui.fit_text("long", 0, lambda text: font.size(text)[0]) == ""


def test_wrap_text_uses_font_width_and_preserves_paragraph_breaks():
    font = _FakeFont()
    measure = lambda text: font.size(text)[0]

    assert pygame_ui.wrap_text("one two three", 80, measure) == ("one two", "three")
    assert pygame_ui.wrap_text("one\n\ntwo", 100, measure) == ("one", "", "two")
    assert pygame_ui.wrap_text("abcdefgh", 30, measure) == ("abc", "def", "gh")
    assert pygame_ui.wrap_text("", 100, measure) == ()


def test_merchant_frame_uses_live_content_and_selected_details():
    offerings = (
        SimpleNamespace(
            title="Deliver to Mars",
            description="Food crates for Mars.",
            reward_credits=100,
            reward_xp=20,
            recommended_class_id="merchant",
            recommended_ship_min_cargo=5,
        ),
        SimpleNamespace(
            title="Deliver to Sirius",
            description="Medical supplies for Sirius.",
            reward_credits=400,
            reward_xp=50,
            recommended_class_id=None,
            recommended_ship_min_cargo=0,
        ),
    )
    npc = SimpleNamespace(name="Guild Master")

    frame = pygame_merchant._frame_for(
        npc,
        offerings,
        3,
        lambda mission: f"[Delivery] {mission.title} @ Sol ({mission.reward_credits}$)",
        lambda class_id: "Merchant",
    )

    assert frame.title == "Guild Master - available work"
    assert frame.options == (
        "[Delivery] Deliver to Mars @ Sol (100$)",
        "[Delivery] Deliver to Sirius @ Sol (400$)",
    )
    assert frame.selected == 1
    assert frame.description == "Medical supplies for Sirius."
    assert frame.hints == (
        "ARROW KEYS / j,k navigate - ENTER accept - ESC walk away.",
        "Reward: 400$ + 50xp",
    )


def test_default_merchant_window_matches_game_canvas():
    assert pygame_merchant._default_screen_size() == (1600, 960)


def test_merchant_layout_matches_game_canvas_and_keeps_content_inside_panel():
    layout = pygame_merchant._merchant_layout(1600, 960, 34)

    assert layout.panel == pygame_ui.Rect(40, 32, 1520, 896)
    assert layout.content.x == layout.panel.x + 34
    assert layout.content.y > layout.rule_y
    assert layout.content.x + layout.content.width < layout.panel.x + layout.panel.width
    assert layout.content.y + layout.content.height < layout.panel.y + layout.panel.height


def test_font_fit_uses_each_candidate_font_metrics(monkeypatch):
    class FakePygame:
        class font:
            @staticmethod
            def Font(_path, size):
                return SimpleNamespace(
                    get_linesize=lambda: size + 20,
                    size=lambda text: (len(text) * size, size),
                )

    frame = pygame_merchant.MerchantFrame(
        "title",
        ("row",),
        "description",
        ("hint",),
        0,
    )
    font = pygame_merchant._fit_font(
        FakePygame,
        None,
        24,
        (frame,),
        1600,
        960,
    )

    assert font.get_linesize() == 44


def test_worker_payload_carries_display_configuration():
    frame = pygame_merchant.MerchantFrame("title", ("row",), "desc", ("hint",), 0)

    payload = pygame_merchant._worker_payload((frame,), (1600, 960), 24, True)

    assert payload["screen_size"] == (1600, 960)
    assert payload["font_size"] == 24
    assert payload["antialias"] is True
    assert payload["frames"][0]["options"] == ("row",)


def test_merchant_key_mapping_matches_existing_modal_contract():
    class FakePygame:
        QUIT = 1
        KEYDOWN = 2
        K_ESCAPE = 10
        K_RETURN = 11
        K_KP_ENTER = 12
        K_UP = 13
        K_DOWN = 14
        K_k = 15
        K_j = 16

    fake = FakePygame()
    assert pygame_merchant._handle_key(fake, SimpleNamespace(type=fake.QUIT), 0, 3) == ("BACK", 0)
    assert pygame_merchant._handle_key(fake, SimpleNamespace(type=fake.KEYDOWN, key=fake.K_UP), 0, 3) == ("IGNORE", 2)
    assert pygame_merchant._handle_key(fake, SimpleNamespace(type=fake.KEYDOWN, key=fake.K_DOWN), 2, 3) == ("IGNORE", 0)
    assert pygame_merchant._handle_key(
        fake,
        SimpleNamespace(type=fake.KEYDOWN, key=fake.K_RETURN),
        1,
        3,
    ) == ("ACCEPT", 1)
    assert pygame_merchant._handle_key(fake, SimpleNamespace(type=fake.KEYDOWN, key=fake.K_ESCAPE), 1, 3) == ("BACK", 1)
    assert pygame_merchant._handle_key(fake, SimpleNamespace(type=99, key=0), 1, 3) == ("IGNORE", 1)


def test_json_worker_rejects_nonzero_worker_exit(monkeypatch):
    monkeypatch.setattr(
        pygame_ui.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=2, stdout=""),
    )

    try:
        pygame_ui.run_json_worker(
            ["python"],
            {},
            unavailable_message="unavailable",
        )
    except pygame_ui.PygameWorkerUnavailable as exc:
        assert str(exc) == "unavailable"
    else:
        raise AssertionError("nonzero worker exits must use the fallback path")


def test_json_worker_returns_last_json_line_and_uses_supplied_environment(monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return SimpleNamespace(returncode=0, stdout="worker noise\n{\"outcome\": \"BACK\"}\n")

    monkeypatch.setattr(pygame_ui.subprocess, "run", fake_run)

    result = pygame_ui.run_json_worker(
        ["python", "-m", "worker"],
        {"value": 1},
        unavailable_message="unavailable",
        environment={"TEST": "1"},
    )

    assert result == {"outcome": "BACK"}
    assert captured["command"] == ["python", "-m", "worker"]
    assert captured["env"] == {"TEST": "1"}
    assert captured["input"] == '{"value": 1}'


def test_captured_quest_rows_merge_cells_by_color():
    capture = pygame_world.CaptureConsole(6, 1)
    capture.print(x=0, y=0, string="AB", fg=(1, 2, 3))
    capture.print(x=2, y=0, string="CD", fg=(4, 5, 6))

    assert pygame_quest_log._captured_rows(capture) == (
        (
            pygame_quest_log.QuestSpan("AB", (1, 2, 3)),
            pygame_quest_log.QuestSpan("CD", (4, 5, 6)),
        ),
    )


def test_ship_buy_frame_payload_round_trips_text_colors_and_affordability():
    frame = pygame_ship_buy.ShipBuyFrame(
        rows=((pygame_quest_log.QuestSpan("Cost: 100$", (255, 255, 255)),),),
        can_buy=False,
    )

    payload = pygame_ship_buy._worker_payload(frame)
    restored = pygame_ship_buy._frame_from_payload(payload["frame"])

    assert restored == frame
    assert payload["font_size"] == 20


def test_ship_buy_key_mapping_preserves_purchase_contract():
    class FakePygame:
        QUIT = 1
        KEYDOWN = 2
        K_ESCAPE = 10
        K_RETURN = 11
        K_KP_ENTER = 12
        K_QUESTION = 13

    fake = FakePygame()
    key = lambda value: SimpleNamespace(type=fake.KEYDOWN, key=value)

    assert pygame_ship_buy._handle_key(fake, SimpleNamespace(type=fake.QUIT), True) == "QUIT"
    assert pygame_ship_buy._handle_key(fake, key(fake.K_ESCAPE), True) == "BACK"
    assert pygame_ship_buy._handle_key(fake, key(fake.K_RETURN), True) == "BUY"
    assert pygame_ship_buy._handle_key(fake, key(fake.K_RETURN), False) == "TOO_EXPENSIVE"
    assert pygame_ship_buy._handle_key(fake, key(fake.K_QUESTION), True) == "GUIDE"


def test_ship_buy_opt_in_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SPACEHACK_PYGAME_SHIP_BUY", raising=False)

    from src.spacehack.menus import _ship_buy

    assert not _ship_buy._pygame_ship_buy_enabled()


def test_quest_frame_payload_round_trips_text_colors_and_state():
    frame = pygame_quest_log.QuestFrame(
        rows=((pygame_quest_log.QuestSpan("> Mission", (255, 255, 255)),),),
        selected=2,
        confirm_abandon=True,
    )

    payload = pygame_quest_log._worker_payload((frame,))
    restored = pygame_quest_log._frame_from_payload(
        payload["frames"][pygame_quest_log._frame_key(2, True)]
    )

    assert restored == frame


def test_quest_key_mapping_preserves_navigation_and_confirmation_contract():
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

    fake = FakePygame()
    key = lambda value: SimpleNamespace(type=fake.KEYDOWN, key=value)

    assert pygame_quest_log._handle_key(fake, key(fake.K_UP), 0, False, 3) == ("IGNORE", 2, False)
    assert pygame_quest_log._handle_key(fake, key(fake.K_a), 1, False, 3) == ("IGNORE", 1, True)
    assert pygame_quest_log._handle_key(fake, key(fake.K_RETURN), 1, True, 3) == ("ABANDONED", 1, True)
    assert pygame_quest_log._handle_key(fake, key(fake.K_ESCAPE), 1, True, 3) == ("BACK", 1, True)
    assert pygame_quest_log._handle_key(fake, key(fake.K_QUESTION), 1, False, 3) == ("GUIDE", 1, False)
    assert pygame_quest_log._handle_key(fake, SimpleNamespace(type=fake.QUIT), 1, False, 3) == ("QUIT", 1, False)


def test_empty_quest_log_uses_a_non_abandonable_worker_state():
    frame = pygame_quest_log.QuestFrame(rows=((),), selected=-1, confirm_abandon=False)
    payload = pygame_quest_log._worker_payload((frame,))

    assert pygame_quest_log._frame_key(-1, False) in payload["frames"]


def test_quest_log_opt_in_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SPACEHACK_PYGAME_QUEST_LOG", raising=False)

    from src.spacehack.menus import _quest_log

    assert not _quest_log._pygame_quest_log_enabled()


def test_batch_frame_payload_round_trips_text_and_colors():
    frame = pygame_batch.BatchFrame(
        rows=((pygame_quest_log.QuestSpan("NAVIGATION", (1, 2, 3)),),),
        key="readonly",
    )

    restored = pygame_batch._frame_from_payload(
        pygame_batch.frame_payload(frame)["frame"]
    )

    assert restored == frame


def test_batch_key_mapping_preserves_read_only_modal_contract():
    class FakePygame:
        QUIT = 1
        KEYDOWN = 2
        K_ESCAPE = 10
        K_QUESTION = 11

    fake = FakePygame()
    key = lambda value: SimpleNamespace(type=fake.KEYDOWN, key=value)

    assert pygame_batch._handle_key(fake, SimpleNamespace(type=fake.QUIT)) == "QUIT"
    assert pygame_batch._handle_key(fake, key(fake.K_ESCAPE)) == "BACK"
    assert pygame_batch._handle_key(fake, key(fake.K_QUESTION)) == "GUIDE"
    assert pygame_batch._handle_key(fake, SimpleNamespace(type=99, key=0)) == "IGNORE"


def test_batch_rejects_unknown_worker_outcomes(monkeypatch):
    monkeypatch.setattr(
        pygame_ui,
        "run_json_worker",
        lambda *args, **kwargs: {"outcome": "MUTATE"},
    )

    try:
        pygame_batch.run_readonly(lambda console: None)
    except pygame_batch.PygameBatchUnavailable as exc:
        assert "unknown choice" in str(exc)
    else:
        raise AssertionError("unknown worker choices must use the tcod fallback")


def test_read_only_batch_switch_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SPACEHACK_PYGAME_READONLY", raising=False)

    assert not pygame_batch.enabled()
    assert not _ship_menu._pygame_readonly_enabled()


def test_faction_progress_bar_is_cp437_safe_and_centered():
    assert _ship_menu._faction_progress_bar(0) == "---------------|---------------"
    assert _ship_menu._faction_progress_bar(-100) == "###############|---------------"
    assert _ship_menu._faction_progress_bar(100) == "---------------|###############"
    assert all(ord(char) < 128 for char in _ship_menu._faction_progress_bar(-37))


def test_navigation_update_preserves_back_quit_and_ignore_contract():
    import tcod.event

    assert navigation.update_navigation(tcod.event.Quit()) is navigation.NavigationOutcome.QUIT
    assert navigation.update_navigation(
        tcod.event.KeyDown(
            scancode=tcod.event.K_ESCAPE,
            sym=tcod.event.K_ESCAPE,
            mod=0,
        )
    ) is navigation.NavigationOutcome.BACK


def test_selectable_menu_frame_payload_round_trips_actions():
    frame = pygame_menu.MenuFrame(
        title="Mars",
        body="Choose an action.",
        items=(pygame_menu.MenuItem("Land", "Dock", "LAND"),),
        hints=("ESC back",),
        selected=0,
    )

    restored = pygame_menu._frame_from_payload(pygame_menu._frame_payload(frame))

    assert restored == frame


def test_selectable_menu_key_mapping_preserves_navigation_and_actions():
    class FakePygame:
        QUIT = 1
        KEYDOWN = 2
        K_ESCAPE = 10
        K_QUESTION = 11
        K_UP = 12
        K_DOWN = 13
        K_k = 14
        K_j = 15
        K_RETURN = 16
        K_KP_ENTER = 17

    fake = FakePygame()
    key = lambda value: SimpleNamespace(type=fake.KEYDOWN, key=value)

    assert pygame_menu._handle_key(fake, SimpleNamespace(type=fake.QUIT), 0, 2) == ("QUIT", 0)
    assert pygame_menu._handle_key(fake, key(fake.K_ESCAPE), 1, 2) == ("BACK", 1)
    assert pygame_menu._handle_key(fake, key(fake.K_QUESTION), 1, 2) == ("GUIDE", 1)
    assert pygame_menu._handle_key(fake, key(fake.K_UP), 0, 2) == ("IGNORE", 1)
    assert pygame_menu._handle_key(fake, key(fake.K_RETURN), 1, 2) == ("SELECT", 1)


def test_selectable_menu_rejects_unknown_worker_outcomes(monkeypatch):
    monkeypatch.setattr(
        pygame_ui,
        "run_json_worker",
        lambda *args, **kwargs: {"outcome": "MUTATE"},
    )
    frame = pygame_menu.MenuFrame("title", "body", (), (), 0)

    try:
        pygame_menu.run((frame,))
    except pygame_menu.PygameMenuUnavailable as exc:
        assert "unknown choice" in str(exc)
    else:
        raise AssertionError("unknown menu outcomes must use fallback")


def test_interactive_batch_switch_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SPACEHACK_PYGAME_INTERACTIVE", raising=False)

    assert not pygame_menu.enabled()
    assert not _missions._pygame_interactive_enabled()
    assert not _planet._pygame_interactive_enabled()
    assert not npc._pygame_interactive_enabled()


def test_planet_menu_items_keep_domain_outcomes_opaque_to_worker():
    planet = SimpleNamespace(id="mars", name="Mars")

    items = _planet._build_menu_items(planet, True, ["Alien ruins"])

    assert [item[2] for item in items] == [
        _planet.PlanetMenuOutcome.LAND,
        _planet.PlanetMenuOutcome.EXPLORE,
        _planet.PlanetMenuOutcome.BACK,
    ]


def test_npc_pygame_actions_map_back_to_existing_outcomes(monkeypatch):
    mission = SimpleNamespace(title="Deliver supplies")
    npc_obj = SimpleNamespace(name="Guild Master", guild="merchants", flavor_text="Welcome")
    from src.spacehack import pygame_menu

    monkeypatch.setattr(
        pygame_menu,
        "run",
        lambda frames, **kwargs: ("SELECT", "DELIVER:0", 0),
    )

    result = npc._run_pygame_npc_talk(
        SimpleNamespace(), npc_obj, "Welcome", [mission],
    )

    assert result == (npc.TalkOutcome.DELIVER, mission)


def test_pygame_backend_is_opt_in_and_falls_back_when_unavailable(monkeypatch):
    monkeypatch.delenv("SPACEHACK_PYGAME_MERCHANT", raising=False)
    assert not pygame_merchant.PygameMerchantUnavailable.__module__.endswith("ui")

    monkeypatch.setenv("SPACEHACK_PYGAME_MERCHANT", "1")
    monkeypatch.setattr(
        pygame_merchant,
        "_load_pygame",
        lambda: (_ for _ in ()).throw(
            pygame_merchant.PygameMerchantUnavailable("missing")
        ),
    )
    try:
        pygame_merchant._load_pygame()
    except pygame_merchant.PygameMerchantUnavailable:
        pass
    else:
        raise AssertionError("missing Pygame must remain an explicit fallback condition")
