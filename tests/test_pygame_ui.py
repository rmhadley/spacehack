"""Tests for the optional Pygame presentation migration seam."""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack import (
    pygame_batch,
    pygame_screen,
    pygame_menu,
    pygame_merchant,
    pygame_quest_log,
    pygame_ship_buy,
    pygame_story,
    pygame_ui,
    pygame_world,
    pygame_quantity,
    pygame_combat,
)
from src.spacehack.menus import _armory, _missions, _planet, _ship_menu
from src.spacehack import navigation, npc, pygame_split
from src.spacehack.main_quest import _act0


class _FakeFont:
    """Monospace metric fake for pure layout tests."""

    def size(self, text: str) -> tuple[int, int]:
        return len(text) * 10, 24

    def get_linesize(self) -> int:
        return 24


def test_combat_key_mapping_returns_opaque_actions():
    class FakePygame:
        QUIT = 1
        KEYDOWN = 2
        K_ESCAPE = 10
        K_TAB = 11
        K_UP = 12
        K_DOWN = 13
        K_LEFT = 14
        K_RIGHT = 15

        class key:
            @staticmethod
            def name(value):
                return {20: "f", 21: "1", 22: "?", 23: "period"}.get(value, "")

    fake = FakePygame()
    key = lambda value: SimpleNamespace(type=fake.KEYDOWN, key=value, unicode="")

    assert pygame_combat._action_for_key(fake, SimpleNamespace(type=fake.QUIT)) == "QUIT"
    assert pygame_combat._action_for_key(fake, key(fake.K_ESCAPE)) == "FLEE"
    assert pygame_combat._action_for_key(fake, key(fake.K_TAB)) == "TARGET"
    assert pygame_combat._action_for_key(fake, key(fake.K_UP)) == "MOVE:up"
    assert pygame_combat._action_for_key(fake, key(20)) == "FIRE"
    assert pygame_combat._action_for_key(fake, key(21)) == "WEAPON:0"
    assert pygame_combat._action_for_key(fake, key(23)) == "WAIT"

    from src.spacehack.combat import _loop
    assert _loop._tcod_action(SimpleNamespace(sym=SimpleNamespace(name="period"))) == "WAIT"


def test_combat_present_falls_back_and_clears_failed_presenter():
    calls = []

    class FailedPresenter:
        def show(self, *_args, **_kwargs):
            raise pygame_combat.PygameCombatUnavailable("stopped")

        def close(self):
            calls.append("close")

    ctx = SimpleNamespace(
        _pygame_combat_presenter=FailedPresenter(),
        context=SimpleNamespace(present=lambda _console: calls.append("tcod")),
    )

    pygame_combat.present(ctx, SimpleNamespace(commands=[]))

    assert calls == ["close", "tcod"]
    assert ctx._pygame_combat_presenter is None


def test_invalid_combat_console_falls_back_to_tcod():
    calls = []

    class Presenter:
        def show(self, console, **_kwargs):
            pygame_combat._frame_payload(console, interactive=False)

        def close(self):
            calls.append("close")

    ctx = SimpleNamespace(
        _pygame_combat_presenter=Presenter(),
        context=SimpleNamespace(present=lambda _console: calls.append("tcod")),
    )

    pygame_combat.present(ctx, SimpleNamespace(commands=[SimpleNamespace(x=0)]))

    assert calls == ["close", "tcod"]
    assert ctx._pygame_combat_presenter is None


def test_combat_action_falls_back_when_presenter_stops():
    class UnavailablePresenter:
        def show(self, *_args, **_kwargs):
            raise pygame_combat.PygameCombatUnavailable("stopped")

        def wait_action(self):
            raise AssertionError("wait_action must not run after show fails")

    assert pygame_combat.PygameCombatUnavailable.__name__ == "PygameCombatUnavailable"
    from src.spacehack.combat import _loop

    assert _loop._combat_action(
        SimpleNamespace(), SimpleNamespace(), presenter=UnavailablePresenter(),
    ) == "UNAVAILABLE"


def test_combat_action_ignores_triggering_key_release_before_next_action(monkeypatch):
    from src.spacehack.combat import _loop
    import tcod.event

    key_up = tcod.event.KeyUp(
        scancode=tcod.event.Scancode.UNKNOWN,
        sym=tcod.event.KeySym.RIGHT,
        mod=0,
    )
    key_down = tcod.event.KeyDown(
        scancode=tcod.event.Scancode.UNKNOWN,
        sym=tcod.event.KeySym.PERIOD,
        mod=0,
    )
    waits = iter(((key_up,), (key_down,)))
    monkeypatch.setattr(_loop.tcod.event, "wait", lambda: next(waits))

    assert _loop._combat_action(SimpleNamespace(), SimpleNamespace(), presenter=None) == "WAIT"

    unknown_key = tcod.event.KeyDown(
        scancode=tcod.event.Scancode.UNKNOWN,
        sym=tcod.event.KeySym.A,
        mod=0,
    )
    waits = iter(((unknown_key,), (key_down,)))
    monkeypatch.setattr(_loop.tcod.event, "wait", lambda: next(waits))
    assert _loop._combat_action(SimpleNamespace(), SimpleNamespace(), presenter=None) == ""

    monkeypatch.setattr(
        _loop.tcod.event,
        "wait",
        lambda: (tcod.event.Quit(),),
    )
    assert _loop._combat_action(SimpleNamespace(), SimpleNamespace(), presenter=None) == "QUIT"


def test_combat_frame_payload_preserves_commands_and_mode():
    console = SimpleNamespace(commands=[SimpleNamespace(x=1, y=2, char="@", fg=(1, 2, 3), bg=None)])

    payload = pygame_combat._frame_payload(console, interactive=True)

    assert payload["logical_size"] == (1600, 960)
    assert payload["interactive"] is True
    assert payload["commands"][0]["char"] == "@"


def test_combat_frame_payload_accepts_native_tcod_console():
    import tcod.console

    console = tcod.console.Console(2, 1, order="C")
    console.print(x=0, y=0, string="@A", fg=(1, 2, 3), bg=(4, 5, 6))

    payload = pygame_combat._frame_payload(console, interactive=False)

    assert [command["char"] for command in payload["commands"]] == ["@", "A"]
    assert payload["commands"][0]["fg"] == (1, 2, 3)
    assert payload["commands"][0]["bg"] == (4, 5, 6)


def test_combat_migration_is_enabled_by_default_and_rolls_back_globally(monkeypatch):
    monkeypatch.delenv("SPACEHACK_PYGAME_COMBAT", raising=False)
    monkeypatch.delenv("SPACEHACK_TCOD_UI", raising=False)
    assert pygame_combat.enabled()

    monkeypatch.setenv("SPACEHACK_TCOD_UI", "1")
    assert not pygame_combat.enabled()


def test_quantity_key_mapping_clamps_and_confirms():
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
        K_PLUS = 18
        K_EQUALS = 19
        K_MINUS = 20

    fake = FakePygame()
    key = lambda value: SimpleNamespace(type=fake.KEYDOWN, key=value)

    assert pygame_quantity._handle_key(fake, key(fake.K_UP), 1, 2) == ("IGNORE", 2)
    assert pygame_quantity._handle_key(fake, key(fake.K_UP), 2, 2) == ("IGNORE", 2)
    assert pygame_quantity._handle_key(fake, key(fake.K_DOWN), 1, 2) == ("IGNORE", 1)
    assert pygame_quantity._handle_key(fake, key(fake.K_RETURN), 2, 2) == ("CONFIRM", 2)
    assert pygame_quantity._handle_key(fake, key(fake.K_ESCAPE), 1, 2) == ("BACK", 1)
    assert pygame_quantity._handle_key(fake, SimpleNamespace(type=fake.QUIT), 1, 2) == ("QUIT", 1)


def test_quantity_worker_propagates_quit(monkeypatch):
    monkeypatch.setattr(
        pygame_ui,
        "run_json_worker",
        lambda *args, **kwargs: {"outcome": "QUIT", "quantity": 1},
    )

    try:
        pygame_quantity.run(SimpleNamespace(), "Buy", 3, 10)
    except pygame_quantity.PygameQuantityQuit:
        pass
    else:
        raise AssertionError("quantity window close must remain distinct from cancel")


def test_quantity_worker_rejects_invalid_confirmed_amount(monkeypatch):
    monkeypatch.setattr(
        pygame_ui,
        "run_json_worker",
        lambda *args, **kwargs: {"outcome": "CONFIRM", "quantity": 8},
    )

    try:
        pygame_quantity.run(SimpleNamespace(), "Buy", 3, 10)
    except pygame_quantity.PygameQuantityUnavailable as exc:
        assert "invalid quantity" in str(exc)
    else:
        raise AssertionError("quantity worker must reject out-of-range values")


def test_goto_menu_pygame_maps_destination_index(monkeypatch):
    from src.spacehack import navigation, pygame_menu

    destinations = [
        ("Mars", SimpleNamespace(name="Mars", description="Red world.")),
        ("[Gate] Sirius", SimpleNamespace(name="Sirius gate", description="A stable gate.")),
    ]
    captured = {}

    def fake_run(frames, **kwargs):
        captured["frames"] = frames
        return ("SELECT", "DEST:1", 1)

    monkeypatch.setattr(pygame_menu, "run", fake_run)

    assert navigation._run_pygame_goto_menu(SimpleNamespace(), destinations) == (True, 1)
    assert captured["frames"][1].items[1].action == "DEST:1"
    assert captured["frames"][1].items[1].description == "A stable gate."


def test_goto_menu_pygame_back_is_handled_as_cancel(monkeypatch):
    from src.spacehack import navigation, pygame_menu

    monkeypatch.setattr(
        pygame_menu,
        "run",
        lambda *args, **kwargs: ("BACK", "", 0),
    )

    assert navigation._run_pygame_goto_menu(
        SimpleNamespace(), [("Mars", SimpleNamespace(name="Mars"))],
    ) == (True, None)


def test_goto_menu_pygame_unavailable_requests_tcod_fallback(monkeypatch):
    from src.spacehack import navigation, pygame_menu

    monkeypatch.setattr(
        pygame_menu,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            pygame_menu.PygameMenuUnavailable("missing")
        ),
    )

    assert navigation._run_pygame_goto_menu(
        SimpleNamespace(), [("Mars", SimpleNamespace(name="Mars"))],
    ) == (False, None)


def test_jump_menu_pygame_maps_opaque_action(monkeypatch):
    from src.spacehack import navigation, pygame_menu

    jump = SimpleNamespace(name="Gate", description="A stable gate.")
    monkeypatch.setattr(
        pygame_menu,
        "run",
        lambda frames, **kwargs: ("SELECT", "JUMP", 0),
    )
    monkeypatch.setattr(
        navigation.solar_systems_module,
        "find_solar_system",
        lambda _system_id: SimpleNamespace(name="Sirius"),
    )

    assert navigation._run_pygame_jump_menu(
        SimpleNamespace(), jump, "sirius", 20, 30,
    ) is navigation.JumpMenuOutcome.JUMP


def test_npc_trade_frame_uses_opaque_buy_and_sell_actions():
    from src.spacehack import trade

    npc = SimpleNamespace(name="Trader")
    ctx = SimpleNamespace(
        player_owned_ship=SimpleNamespace(
            ship_id="starter", inventory={"food_rations": 2}, cargo_used=2,
        ),
        stats=SimpleNamespace(credits=100),
    )
    frame = trade._pygame_npc_trade_frame(
        ctx, npc, {"food_rations": 3}, 1.2, 0.5,
    )

    assert frame.left_rows[0].action == "BUY_NPC:food_rations"
    assert frame.right_rows[0].action == "SELL_NPC:food_rations"


def test_loot_parent_apply_removes_entity_and_grants_inventory():
    from src.spacehack import trade

    entity = SimpleNamespace(loot_data={"good_id": "food_rations", "quantity": 2})
    owned = SimpleNamespace(inventory={}, mission_reserved=0)
    ctx = SimpleNamespace(
        player_owned_ship=owned,
        game_map=SimpleNamespace(entities=[entity]),
        log=SimpleNamespace(add=lambda _message: None),
    )
    good = SimpleNamespace(name="Food")

    trade._apply_loot_pickup(ctx, entity, owned, False, [], "food", 2, good)

    assert owned.inventory == {"food": 2}
    assert entity not in ctx.game_map.entities


def test_screen_frame_payload_round_trips_page_offset_and_rows():
    frame = pygame_screen.ScreenFrame(
        "Guide", ("body",),
        (pygame_screen.ScreenRow("Pick", "Details", "ACTION"),),
        ("ESC close",), 0, 4,
    )

    assert pygame_screen._frame_from_payload(
        pygame_screen._frame_payload(frame),
    ) == frame


def test_screen_key_mapping_supports_tabs_and_paging():
    class FakePygame:
        QUIT = 1
        KEYDOWN = 2
        K_ESCAPE = 10
        K_TAB = 11
        K_PAGEDOWN = 12
        K_PAGEUP = 13
        K_QUESTION = 14
        K_UP = 15
        K_DOWN = 16
        K_k = 17
        K_j = 18
        K_RETURN = 19
        K_KP_ENTER = 20

    fake = FakePygame()
    frame = pygame_screen.ScreenFrame(
        "T", (), (pygame_screen.ScreenRow("row", action="A"),),
    )
    key = lambda value: SimpleNamespace(type=fake.KEYDOWN, key=value)

    assert pygame_screen._handle_key(fake, key(fake.K_TAB), frame) == ("TAB", 0)
    assert pygame_screen._handle_key(fake, key(fake.K_PAGEDOWN), frame) == ("PAGE_DOWN", 0)
    assert pygame_screen._handle_key(fake, key(fake.K_PAGEUP), frame) == ("PAGE_UP", 0)


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
    assert pygame_merchant._handle_key(fake, SimpleNamespace(type=fake.QUIT), 0, 3) == ("QUIT", 0)
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


def test_migrated_workers_are_enabled_by_default_and_support_global_tcod_rollback(monkeypatch):
    monkeypatch.delenv("SPACEHACK_PYGAME_SHIP_BUY", raising=False)
    monkeypatch.delenv("SPACEHACK_TCOD_UI", raising=False)

    from src.spacehack.menus import _ship_buy

    assert _ship_buy._pygame_ship_buy_enabled()
    assert pygame_ui.migration_enabled("SPACEHACK_PYGAME_SHIP_BUY")

    monkeypatch.setenv("SPACEHACK_TCOD_UI", "1")
    assert not _ship_buy._pygame_ship_buy_enabled()
    assert not pygame_menu.enabled()


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


def test_quest_log_worker_is_enabled_by_default(monkeypatch):
    monkeypatch.delenv("SPACEHACK_PYGAME_QUEST_LOG", raising=False)
    monkeypatch.delenv("SPACEHACK_TCOD_UI", raising=False)

    from src.spacehack.menus import _quest_log

    assert _quest_log._pygame_quest_log_enabled()


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


def test_read_only_batch_is_enabled_by_default(monkeypatch):
    monkeypatch.delenv("SPACEHACK_PYGAME_READONLY", raising=False)
    monkeypatch.delenv("SPACEHACK_TCOD_UI", raising=False)

    assert pygame_batch.enabled()
    assert _ship_menu._pygame_readonly_enabled()


def test_split_frame_payload_round_trips_rows_and_selection():
    frame = pygame_split.SplitFrame(
        title="ARMORY",
        left_label="For Sale",
        right_label="My Loadout",
        left_rows=(pygame_split.SplitRow("Laser", "100$", "damage", "BUY:laser"),),
        right_rows=(pygame_split.SplitRow("[empty]", "", "", "", divider=False),),
        footer_left="Credits: 100",
        footer_right="",
        hint="TAB switch",
        focus=0,
        selected=0,
    )

    restored = pygame_split._frame_from_payload(
        pygame_split._frame_payload(frame),
    )

    assert restored == frame


def test_split_key_mapping_switches_panels_and_returns_opaque_action():
    class FakePygame:
        QUIT = 1
        KEYDOWN = 2
        K_ESCAPE = 10
        K_TAB = 11
        K_UP = 12
        K_DOWN = 13
        K_k = 14
        K_j = 15
        K_RETURN = 16
        K_KP_ENTER = 17

    frame = pygame_split.SplitFrame(
        "ARMORY", "Sale", "Owned",
        (pygame_split.SplitRow("Laser", "100$", "", "BUY"),),
        (pygame_split.SplitRow("Armor", "50$", "", "SELL"),),
        "", "", "", 0, 0,
    )
    fake = FakePygame()
    key = lambda value: SimpleNamespace(type=fake.KEYDOWN, key=value)

    assert pygame_split._handle_key(fake, key(fake.K_TAB), frame) == ("IGNORE", 1, 0)
    assert pygame_split._handle_key(fake, key(fake.K_RETURN), frame) == ("SELECT", 0, 0)
    assert pygame_split._handle_key(fake, SimpleNamespace(type=fake.QUIT), frame) == ("QUIT", 0, 0)


def test_split_worker_rejects_unknown_outcomes(monkeypatch):
    monkeypatch.setattr(
        pygame_ui,
        "run_json_worker",
        lambda *args, **kwargs: {"outcome": "MUTATE"},
    )
    frame = pygame_split.SplitFrame("T", "L", "R", (), (), "", "", "")

    try:
        pygame_split.run(frame)
    except pygame_split.PygameSplitUnavailable as exc:
        assert "unknown choice" in str(exc)
    else:
        raise AssertionError("unknown split outcomes must use fallback")


def test_split_interactive_preserves_initial_focus_and_selection(monkeypatch):
    frame = pygame_split.SplitFrame(
        "Terminal", "Buy", "Sell", (), (), "", "", "hint", 1, 3,
    )
    seen = []
    monkeypatch.setattr(
        pygame_split,
        "run",
        lambda current, **kwargs: seen.append(current) or ("BACK", "", 1, 3),
    )

    assert pygame_split.run_interactive(
        SimpleNamespace(), lambda: frame, lambda *args: True, caption="test",
    ) == "BACK"
    assert seen[0].focus == 1
    assert seen[0].selected == 3


def test_split_interactive_preserves_focus_and_selection_after_action(monkeypatch):
    frame = pygame_split.SplitFrame(
        "Terminal", "Buy", "Sell", (), (), "", "", "hint",
    )
    seen = []
    outcomes = iter((("SELECT", "BUY:item", 1, 3), ("BACK", "", 1, 3)))

    def fake_run(current, **kwargs):
        seen.append(current)
        return next(outcomes)

    monkeypatch.setattr(pygame_split, "run", fake_run)
    applied = []

    result = pygame_split.run_interactive(
        SimpleNamespace(),
        lambda: frame,
        lambda action, focus, selected: applied.append(
            (action, focus, selected)
        ) or True,
        caption="test",
    )

    assert result == "BACK"
    assert applied == [("BUY:item", 1, 3)]
    assert seen[1].focus == 1
    assert seen[1].selected == 3


def test_armory_pygame_frame_builds_ground_weapon_details():
    ctx = SimpleNamespace(
        equipped_ground_weapons=[],
        equipped_ground_armor={},
        stats=SimpleNamespace(credits=1000),
    )

    frame = _armory._pygame_armory_frame(ctx)
    actions = [row.action for row in frame.left_rows if not row.divider]

    assert actions
    assert "BUY_WEAPON:laser_pistol" in actions
    assert all("Accuracy:" in row.detail for row in frame.left_rows if row.action.startswith("BUY_WEAPON:"))


def test_armory_pygame_empty_slot_action_is_noop():
    ctx = SimpleNamespace(
        equipped_ground_weapons=[],
        equipped_ground_armor={},
        stats=SimpleNamespace(credits=1000),
        log=SimpleNamespace(add=lambda _message: None),
    )

    assert _armory._apply_pygame_armory_action(ctx, "", 1, 1) is True
    assert ctx.stats.credits == 1000


def test_armory_pygame_rejects_unknown_action():
    ctx = SimpleNamespace(
        equipped_ground_weapons=[],
        equipped_ground_armor={},
        stats=SimpleNamespace(credits=1000),
        log=SimpleNamespace(add=lambda _message: None),
    )

    try:
        _armory._apply_pygame_armory_action(ctx, "BROKEN", 0, 0)
    except ValueError as exc:
        assert "Unknown armory action" in str(exc)
    else:
        raise AssertionError("unknown Armory actions must trigger fallback")


def test_armory_pygame_action_returns_keep_open_after_buy():
    messages = []
    ctx = SimpleNamespace(
        equipped_ground_weapons=[],
        equipped_ground_armor={},
        stats=SimpleNamespace(credits=1000),
        log=SimpleNamespace(add=messages.append),
    )

    keep_open = _armory._apply_pygame_armory_action(
        ctx, "BUY_WEAPON:laser_pistol", 0, 1,
    )

    assert keep_open is True
    assert ctx.equipped_ground_weapons == ["laser_pistol"]
    assert ctx.stats.credits < 1000
    assert messages


def test_loadout_pygame_frame_uses_parent_inventory_snapshot():
    from src.spacehack.ship import OwnedShip

    ctx = SimpleNamespace(
        player_owned_ship=OwnedShip(ship_id="starter"),
        stats=SimpleNamespace(credits=1000),
    )

    frame = __import__(
        "src.spacehack.menus._loadout", fromlist=["_pygame_loadout_frame"]
    )._pygame_loadout_frame(
        ctx,
        "earth",
        ("light_missile",),
        ("armor_plating",),
    )

    actions = [row.action for row in frame.left_rows if not row.divider]
    assert actions == ["BUY_WEAPON:light_missile", "BUY_MODULE:armor_plating"]


def test_loadout_sell_action_targets_selected_duplicate_slot():
    from src.spacehack.menus import _loadout
    from src.spacehack.ship import OwnedShip

    ctx = SimpleNamespace(
        player_owned_ship=OwnedShip(
            ship_id="starter",
            weapons=("light_laser", "light_laser"),
        ),
        stats=SimpleNamespace(credits=0),
        log=SimpleNamespace(add=lambda _message: None),
    )
    original = ctx.player_owned_ship.weapons

    assert _loadout._apply_pygame_loadout_action(
        ctx, "SELL_WEAPON_SLOT:1", 1, 2, "earth",
    )
    assert original == ("light_laser", "light_laser")
    assert ctx.player_owned_ship.weapons == ("light_laser",)


def test_split_interactive_frame_build_failure_returns_to_fallback():
    assert pygame_split.run_interactive(
        SimpleNamespace(),
        lambda: (_ for _ in ()).throw(KeyError("bad inventory")),
        lambda *args: True,
        caption="test",
    ) is None


def test_split_interactive_malformed_action_returns_to_fallback(monkeypatch):
    frame = pygame_split.SplitFrame("Terminal", "Buy", "Sell", (), (), "", "", "hint")
    monkeypatch.setattr(
        pygame_split,
        "run",
        lambda *args, **kwargs: ("SELECT", "BROKEN:action", 0, 0),
    )

    assert pygame_split.run_interactive(
        SimpleNamespace(), lambda: frame,
        lambda action, focus, selected: int(action.split(":", 1)[1]),
        caption="test",
    ) is None


def test_ship_menu_frames_keep_actions_opaque_and_stats_in_parent_snapshot(monkeypatch):
    monkeypatch.setattr(
        _ship_menu.ship_module,
        "ship_display_name",
        lambda owned: "Scout A",
    )
    monkeypatch.setattr(
        _ship_menu.ship_module,
        "effective_speed",
        lambda ship, owned: 9,
    )
    ship = SimpleNamespace(description="Fast courier", max_fuel=20)
    ctx = SimpleNamespace(
        player_owned_ship=SimpleNamespace(
            fuel=12,
            hull_damage_pct=5,
        ),
        stats=SimpleNamespace(credits=321),
    )
    frames = _ship_menu._ship_menu_frames(ctx, ship)

    assert [item.action for item in frames[0].items] == ["VIEW", "LOADOUT", "LAUNCH"]
    assert "Fuel: 12 / 20" in frames[0].body
    assert "Credits: 321$" in frames[0].body


def test_ship_menu_pygame_maps_terminal_actions(monkeypatch):
    ship = SimpleNamespace(description="Fast courier", max_fuel=20)
    ctx = SimpleNamespace(
        player_owned_ship=SimpleNamespace(fuel=12, hull_damage_pct=5),
        stats=SimpleNamespace(credits=321),
    )
    monkeypatch.setattr(
        pygame_menu,
        "run",
        lambda frames, **kwargs: ("SELECT", "LAUNCH", 2),
    )
    monkeypatch.setattr(
        _ship_menu.ship_module,
        "ship_display_name",
        lambda owned: "Scout A",
    )
    monkeypatch.setattr(
        _ship_menu.ship_module,
        "effective_speed",
        lambda ship, owned: 9,
    )

    assert _ship_menu._run_pygame_ship_menu(ctx, ship) is _ship_menu.ShipMenuAction.LAUNCH


def test_ship_menu_pygame_guide_reopens_and_unavailable_falls_back(monkeypatch):
    ship = SimpleNamespace(description="Fast courier", max_fuel=20)
    ctx = SimpleNamespace(
        player_owned_ship=SimpleNamespace(fuel=12, hull_damage_pct=5),
        stats=SimpleNamespace(credits=321),
    )
    outcomes = iter((("GUIDE", "", 0), ("BACK", "", 0)))
    monkeypatch.setattr(pygame_menu, "run", lambda *args, **kwargs: next(outcomes))
    monkeypatch.setattr(
        _ship_menu.ship_module,
        "ship_display_name",
        lambda owned: "Scout A",
    )
    monkeypatch.setattr(
        _ship_menu.ship_module,
        "effective_speed",
        lambda ship, owned: 9,
    )
    monkeypatch.setattr("src.spacehack.menus._ship_menu._try_open_guide", lambda *args: None)
    monkeypatch.setattr("src.spacehack.help._run_help_guide", lambda _ctx: None)

    assert _ship_menu._run_pygame_ship_menu(ctx, ship) is _ship_menu.ShipMenuAction.BACK


def test_ship_menu_pygame_is_enabled_by_default(monkeypatch):
    monkeypatch.delenv("SPACEHACK_PYGAME_INTERACTIVE", raising=False)
    monkeypatch.delenv("SPACEHACK_TCOD_UI", raising=False)

    assert _ship_menu._pygame_ship_menu_enabled()


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


def test_selectable_menu_wraps_long_mission_text_without_tiny_font():
    class FakeFont:
        def __init__(self, size):
            self.point_size = size

        def get_linesize(self):
            return self.point_size + 6

        def size(self, text):
            return len(text) * self.point_size // 2, self.point_size

    class FakePygame:
        class font:
            @staticmethod
            def match_font(_family):
                return None

            @staticmethod
            def Font(_path, size):
                return FakeFont(size)

    long_description = "Cargo and deadline details. " * 30
    frame = pygame_menu.MenuFrame(
        title="Guild Master - available work",
        body="Select a contract to review its details.",
        items=(pygame_menu.MenuItem("Deliver supplies", long_description, "0"),),
        hints=("ARROW KEYS / j,k navigate - ENTER accept - ESC walk away.",),
        selected=0,
    )

    font = pygame_menu._fit_font(FakePygame, (frame,), 1600, 960)

    assert font.point_size == 24
    assert pygame_menu._frame_height(
        font, frame, pygame_menu._content_width(1600),
    ) <= 828


def test_selectable_menu_frame_payload_round_trips_actions_and_ascii_art():
    frame = pygame_menu.MenuFrame(
        title="Mars",
        body="Choose an action.",
        items=(pygame_menu.MenuItem("Land", "Dock", "LAND"),),
        hints=("ESC back",),
        selected=0,
        art=("~=~=~", "=+=+=",),
        art_color=(150, 95, 255),
        art_colors=((150, 95, 255), (140, 80, 255)),
    )

    restored = pygame_menu._frame_from_payload(pygame_menu._frame_payload(frame))

    assert restored == frame


def test_ascii_art_increases_selectable_frame_height():
    class FakeFont:
        def get_linesize(self):
            return 24

        def size(self, text):
            return len(text) * 10, 24

    plain = pygame_menu.MenuFrame("title", "body", (), (), 0)
    decorated = pygame_menu.MenuFrame(
        "title", "body", (), (), 0, art=("rune", "door",),
    )

    assert pygame_menu._frame_height(
        FakeFont(), decorated, 600,
    ) > pygame_menu._frame_height(FakeFont(), plain, 600)


def test_screen_font_fit_accounts_for_long_detail_on_any_selection():
    class FakeFont:
        def __init__(self, size):
            self.point_size = size

        def get_linesize(self):
            return self.point_size + 6

        def size(self, text):
            return len(text) * self.point_size // 2, self.point_size

    class FakePygame:
        class font:
            @staticmethod
            def match_font(_family):
                return None

            @staticmethod
            def Font(_path, size):
                return FakeFont(size)

    frame = pygame_screen.ScreenFrame(
        "Terminal",
        ("Choose an option",),
        (
            pygame_screen.ScreenRow("Short", "brief", "SHORT"),
            pygame_screen.ScreenRow("Long", "details " * 80, "LONG"),
        ),
        ("ESC back",),
        selected=0,
    )

    font = pygame_screen._fit_font(FakePygame, frame, 640, 480)

    assert pygame_screen._layout_height(font, frame, 560) <= 396


def test_pygame_trade_valid_actions_keep_terminal_open(monkeypatch):
    from src.spacehack import trade

    class Good:
        name = "Food"
        volume = 1

    calls = []
    monkeypatch.setattr(trade, "find_trade_good", lambda _good_id: Good())
    monkeypatch.setattr(trade, "_unit_price", lambda *_args: 10)
    monkeypatch.setattr(trade, "_sell_price", lambda *_args: 7)
    monkeypatch.setattr(trade, "_free_cargo", lambda _owned: 5)
    monkeypatch.setattr(trade, "_run_quantity_prompt", lambda *_args: 1)
    monkeypatch.setattr(trade, "_buy_good", lambda *args: calls.append(("BUY", args)) or True)
    monkeypatch.setattr(trade, "_sell_good", lambda *args: calls.append(("SELL", args)) or True)

    ctx = SimpleNamespace(
        player_owned_ship=SimpleNamespace(inventory={"food": 2}),
        economy_state={"earth": {"food": 3}},
        stats=SimpleNamespace(credits=100),
    )

    assert trade._apply_pygame_trade_action(ctx, "earth", "BUY:food") is True
    assert trade._apply_pygame_trade_action(ctx, "earth", "SELL:food") is True
    assert [kind for kind, _args in calls] == ["BUY", "SELL"]


def test_screen_body_budget_reserves_rows_and_footer():
    class Font:
        def get_linesize(self):
            return 20

        def size(self, text):
            return len(text) * 8, 20

    frame = pygame_screen.ScreenFrame(
        "Guide",
        ("body " * 20,),
        (pygame_screen.ScreenRow("Choice", "details", "CHOICE"),),
        ("ESC close",),
    )

    budget = pygame_screen._body_budget(Font(), frame, 500, 480, 84)

    assert budget > 0
    assert budget * (20 + 3) + pygame_screen._non_body_height(Font(), frame, 500) <= 480 - 70 - 84 - 8


def test_screen_worker_rejects_unknown_outcome(monkeypatch):
    monkeypatch.setattr(
        pygame_ui,
        "run_json_worker",
        lambda *args, **kwargs: {"outcome": "MUTATE"},
    )
    frame = pygame_screen.ScreenFrame("T", (), ())

    try:
        pygame_screen.run(frame)
    except pygame_screen.PygameScreenUnavailable as exc:
        assert "unknown choice" in str(exc)
    else:
        raise AssertionError("unknown text-screen outcomes must use fallback")


def test_story_menu_dismisses_with_enter_without_items():
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
    key = lambda value: SimpleNamespace(type=fake.KEYDOWN, key=value)

    assert pygame_menu._handle_key(fake, key(fake.K_RETURN), 0, 0) == ("DISMISS", 0)
    assert pygame_menu._handle_key(fake, key(fake.K_ESCAPE), 0, 0) == ("BACK", 0)


def test_story_confirm_maps_confirm_and_back(monkeypatch):
    outcomes = iter((("SELECT", "CONFIRM", 0), ("BACK", "", 0)))
    monkeypatch.setattr(pygame_menu, "run", lambda *args, **kwargs: next(outcomes))

    assert pygame_story.confirm(
        SimpleNamespace(),
        title="Computer",
        body="Restore power?",
        accept_label="Activate",
        cancel_label="Leave",
        caption="test",
    ) == "CONFIRM"
    assert pygame_story.confirm(
        SimpleNamespace(),
        title="Computer",
        body="Restore power?",
        accept_label="Activate",
        cancel_label="Leave",
        caption="test",
    ) == "BACK"


def test_story_confirm_preserves_quit(monkeypatch):
    monkeypatch.setattr(
        pygame_menu,
        "run",
        lambda *args, **kwargs: ("QUIT", "", 0),
    )

    assert pygame_story.confirm(
        SimpleNamespace(),
        title="Board",
        body="Board the wreck?",
        accept_label="Board",
        cancel_label="Fly past",
        caption="test",
    ) == "QUIT"


def test_story_dismiss_attaches_ascii_art_to_worker_frame(monkeypatch):
    captured = {}

    def fake_run(frames, **kwargs):
        captured["frame"] = frames[0]
        return "DISMISS", "", 0

    monkeypatch.setattr(pygame_menu, "run", fake_run)
    result = pygame_story.dismiss(
        SimpleNamespace(),
        title="Transmission",
        body="Body",
        caption="test",
        art=("STATIC",),
        art_color=(90, 150, 90),
    )

    assert result == "DISMISS"
    assert captured["frame"].art == ("STATIC",)
    assert captured["frame"].art_color == (90, 150, 90)


def test_main_quest_story_art_preserves_transmission_and_door_flavor(monkeypatch):
    captured = []

    monkeypatch.setattr(_act0, "_pygame_story_enabled", lambda: True)
    monkeypatch.setattr(
        "src.spacehack.pygame_story.dismiss",
        lambda _ctx, **kwargs: captured.append(kwargs) or "DISMISS",
    )

    _act0.show_prologue_transmission(SimpleNamespace())
    _act0.show_sealed_door_overlay(SimpleNamespace(), "discover")

    assert captured[0]["art"] == _act0._SIGNAL_ART
    assert captured[0]["art_color"] == _act0._SIGNAL_TRACE_FG
    assert captured[0]["art_colors"] == _act0._SIGNAL_ART_COLORS
    assert captured[1]["art"] == tuple(
        ("MAKE: ALIEN    MECHANISM: NONE VISIBLE    AGE: UNKNOWN", "", *_act0._DOOR_RUNES, *_act0._DOOR_ART_SEALED)
    )
    assert captured[1]["art_color"] == _act0._DOOR_ART_FG
    assert captured[1]["art_colors"] == (
        _act0.ui.COLOR_VALUE_DIM,
        _act0.ui.COLOR_VALUE_DIM,
        *(_act0._DOOR_RUNE_FG for _ in _act0._DOOR_RUNES),
        *(_act0._DOOR_ART_FG for _ in _act0._DOOR_ART_SEALED),
    )


def test_story_frames_preserve_opaque_archive_choices(monkeypatch):
    captured = {}

    def fake_run(frames, **kwargs):
        captured["frames"] = frames
        return "SELECT", "archive_sealed", 1

    monkeypatch.setattr(pygame_menu, "run", fake_run)
    result = pygame_story.choose(
        SimpleNamespace(),
        title="THE FIRST READING",
        body="Archive body",
        options=(("Share fragment", "diagnostic_fragment"), ("Keep sealed", "archive_sealed")),
        caption="test",
    )

    assert result == "archive_sealed"
    assert captured["frames"][1].items[1].action == "archive_sealed"


def test_story_choice_rejects_unknown_worker_action(monkeypatch):
    monkeypatch.setattr(
        pygame_menu,
        "run",
        lambda *args, **kwargs: ("SELECT", "mutate_quest", 0),
    )

    assert pygame_story.choose(
        SimpleNamespace(),
        title="THE FIRST READING",
        body="Archive body",
        options=(("Keep sealed", "archive_sealed"),),
        caption="test",
    ) is None


def test_story_dismiss_falls_back_when_worker_unavailable(monkeypatch):
    monkeypatch.setattr(
        pygame_menu,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            pygame_menu.PygameMenuUnavailable("missing")
        ),
    )

    assert pygame_story.dismiss(
        SimpleNamespace(), title="Message", body="Body", caption="test",
    ) is None


def test_story_dismiss_preserves_worker_quit_outcome(monkeypatch):
    monkeypatch.setattr(
        pygame_menu,
        "run",
        lambda *args, **kwargs: ("QUIT", "", 0),
    )

    assert pygame_story.dismiss(
        SimpleNamespace(), title="Message", body="Body", caption="test",
    ) == "QUIT"


def test_story_dismiss_propagates_quit_to_act0(monkeypatch):
    from src.spacehack.main_quest import _act0

    monkeypatch.setenv("SPACEHACK_PYGAME_INTERACTIVE", "1")
    monkeypatch.setattr(
        pygame_story,
        "dismiss",
        lambda *args, **kwargs: "QUIT",
    )

    try:
        _act0._show_pygame_dismiss(
            SimpleNamespace(), title="Message", body="Body", caption="test",
        )
    except SystemExit:
        pass
    else:
        raise AssertionError("story worker QUIT must propagate to Act 0")


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


def test_interactive_batch_is_enabled_by_default(monkeypatch):
    monkeypatch.delenv("SPACEHACK_PYGAME_INTERACTIVE", raising=False)
    monkeypatch.delenv("SPACEHACK_TCOD_UI", raising=False)

    assert pygame_menu.enabled()
    assert _missions._pygame_interactive_enabled()
    assert _planet._pygame_interactive_enabled()
    assert npc._pygame_interactive_enabled()


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


def test_shared_menu_runner_uses_existing_engine_and_returns_action(monkeypatch):
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
        K_QUESTION = 17
        event = SimpleNamespace(
            wait=lambda: SimpleNamespace(type=FakePygame.KEYDOWN, key=FakePygame.K_RETURN),
        )

    class Surface:
        def get_size(self):
            return (1600, 960)

        def fill(self, _color):
            pass

    engine = SimpleNamespace(
        pygame=FakePygame,
        logical_surface=Surface(),
        present=lambda: None,
    )
    context = SimpleNamespace(_runtime=SimpleNamespace(engine=engine))
    frame = pygame_menu.MenuFrame(
        "Merchant", "Choose", (pygame_menu.MenuItem("Work", "Details", "WORK"),), (), 0,
    )
    monkeypatch.setattr(pygame_menu, "_fit_font", lambda *args: object())
    monkeypatch.setattr(pygame_menu, "_draw_frame", lambda *args: None)

    assert pygame_menu.run_shared(context, (frame,), caption="test") == (
        "SELECT", "WORK", 0,
    )


def test_mission_menu_routes_to_shared_window_without_worker(monkeypatch):
    monkeypatch.setenv("SPACEHACK_PYGAME_SHARED", "1")
    captured = {}

    def fake_shared(context, frames, **kwargs):
        captured["context"] = context
        captured["frames"] = frames
        return "BACK", "", 0

    monkeypatch.setattr(pygame_menu, "run_shared", fake_shared)
    monkeypatch.setattr(
        pygame_menu,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("shared menus must not start a worker")
        ),
    )
    ctx = SimpleNamespace(context=object())
    npc_obj = SimpleNamespace(name="Guild Master")

    result = _missions._run_pygame_interactive_missions(ctx, npc_obj, ())

    assert result == (_missions.MissionOutcome.BACK, None)
    assert captured["context"] is ctx.context
    assert captured["frames"][0].title == "Guild Master - available work"


def test_npc_talk_routes_to_shared_window_without_worker(monkeypatch):
    monkeypatch.setenv("SPACEHACK_PYGAME_SHARED", "1")
    captured = {}

    monkeypatch.setattr(
        pygame_menu,
        "run_shared",
        lambda context, frames, **kwargs: captured.update(
            context=context, frames=frames,
        ) or ("SELECT", "WORK", 0),
    )
    monkeypatch.setattr(
        pygame_menu,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("shared NPC talk must not start a worker")
        ),
    )
    ctx = SimpleNamespace(context=object())
    npc_obj = SimpleNamespace(name="Guild Master", guild="merchants", flavor_text="Welcome")

    result = npc._run_pygame_npc_talk(ctx, npc_obj, "Welcome", [])

    assert result == (npc.TalkOutcome.WORK, None)
    assert captured["context"] is ctx.context
    assert captured["frames"][0].items[0].action == "WORK"


def test_all_shared_adapters_bypass_workers(monkeypatch):
    monkeypatch.setenv("SPACEHACK_PYGAME_SHARED", "1")

    menu_frame = pygame_menu.MenuFrame(
        "Menu", "", (pygame_menu.MenuItem("Go", "", "GO"),), (), 0,
    )
    screen_frame = pygame_screen.ScreenFrame(
        "Screen", (), (pygame_screen.ScreenRow("Go", action="GO"),),
    )
    split_frame = pygame_split.SplitFrame(
        "Split", "Left", "Right",
        (pygame_split.SplitRow("Go", "", "", "GO"),), (),
        "", "", "", 0, 0,
    )
    context = object()
    game_ctx = SimpleNamespace(context=context)
    calls = []

    monkeypatch.setattr(
        pygame_menu, "run_shared",
        lambda *args, **kwargs: calls.append("menu") or ("BACK", "", 0),
    )
    monkeypatch.setattr(
        pygame_screen, "run_shared",
        lambda *args, **kwargs: calls.append("screen") or ("BACK", "", 0),
    )
    monkeypatch.setattr(
        pygame_batch, "run_shared",
        lambda *args, **kwargs: calls.append("batch") or "BACK",
    )
    monkeypatch.setattr(
        pygame_split, "run_shared",
        lambda *args, **kwargs: calls.append("split") or ("BACK", "", 0, 0),
    )
    monkeypatch.setattr(
        pygame_quantity, "run_shared",
        lambda *args, **kwargs: calls.append("quantity") or None,
    )
    monkeypatch.setattr(
        pygame_ship_buy, "run_shared",
        lambda *args, **kwargs: calls.append("ship_buy") or "BACK",
    )
    monkeypatch.setattr(
        pygame_quest_log, "run_shared",
        lambda *args, **kwargs: calls.append("quest_log") or ("BACK", 0),
    )

    for module in (
        pygame_menu, pygame_screen, pygame_split,
        pygame_quantity, pygame_ship_buy, pygame_quest_log,
    ):
        monkeypatch.setattr(
            module, "run", lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError(f"{module.__name__} started a worker")
            ),
        )
    monkeypatch.setattr(
        pygame_batch, "run_readonly", lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("pygame_batch started a worker")
        ),
    )

    assert pygame_menu.run_for_context(context, (menu_frame,))[0] == "BACK"
    assert pygame_screen.run_for_context(context, screen_frame)[0] == "BACK"
    assert pygame_batch.run_for_context(context, lambda _console: None) == "BACK"
    assert pygame_quantity.run_for_context(context, game_ctx, "Buy", 1) is None
    assert pygame_ship_buy.run_for_context(context, game_ctx, SimpleNamespace()) == "BACK"
    assert pygame_quest_log.run_for_context(game_ctx)[0] == "BACK"

    assert pygame_split.run_interactive(
        game_ctx, lambda: split_frame, lambda *_args: True, caption="test",
    ) == "BACK"
    assert calls == [
        "menu", "screen", "batch", "quantity", "ship_buy", "quest_log", "split",
    ]


def test_story_adapters_use_the_shared_menu_runner(monkeypatch):
    monkeypatch.setenv("SPACEHACK_PYGAME_SHARED", "1")
    captured = []
    monkeypatch.setattr(
        pygame_menu,
        "run_for_context",
        lambda context, frames, **kwargs: captured.append(
            (context, frames),
        ) or ("DISMISS", "", 0),
    )
    monkeypatch.setattr(
        pygame_menu,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("shared story adapters must not start a worker")
        ),
    )
    ctx = SimpleNamespace(context=object())

    assert pygame_story.dismiss(
        ctx, title="Signal", body="Message", caption="test",
    ) == "DISMISS"
    assert captured[0][0] is ctx.context
    assert captured[0][1][0].title == "Signal"


def test_quest_log_guide_reopens_the_same_shared_modal(monkeypatch):
    from src.spacehack.menus import _quest_log

    monkeypatch.setenv("SPACEHACK_PYGAME_SHARED", "1")
    outcomes = iter((("GUIDE", 2, True), ("BACK", 2, True)))
    calls = []
    states = []
    monkeypatch.setattr(
        "src.spacehack.help._run_help_guide",
        lambda ctx: calls.append(ctx),
    )
    monkeypatch.setattr(
        "src.spacehack.pygame_quest_log.run_for_context",
        lambda ctx, selected=0, confirm=False: states.append(
            (selected, confirm),
        ) or next(outcomes),
    )
    ctx = SimpleNamespace()

    assert _quest_log._run_pygame_quest_log(ctx) == (_quest_log.QuestLogOutcome.BACK, None)
    assert calls == [ctx]
    assert states == [(0, False), (2, True)]


def test_cargo_screen_uses_context_adapter_when_fixture_has_no_context(monkeypatch):
    from src.spacehack import trade

    captured = {}
    monkeypatch.setattr(
        pygame_screen,
        "run_for_context",
        lambda context, frame, **kwargs: captured.update(
            context=context, frame=frame,
        ) or ("BACK", "", frame.selected),
    )
    monkeypatch.setattr(trade, "_pygame_cargo_enabled", lambda: True)
    owned = SimpleNamespace(
        ship_id="starter",
        inventory={},
        cargo_used=0,
        mission_reserved=0,
        cargo_ammo=0,
        hull_damage_pct=0,
    )
    ctx = SimpleNamespace(
        player_owned_ship=owned,
        stats=SimpleNamespace(credits=0),
    )

    result = trade._run_pygame_cargo(ctx, owned, "Scout", 10)

    assert result is True
    assert captured["context"] is ctx
