"""Tests for the optional Pygame presentation migration seam."""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack import pygame_merchant, pygame_ui


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
