"""Tests for the refreshed Pygame faction standings screen."""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack import pygame_faction, pygame_ui


def test_faction_frame_contains_bright_semantic_rows_and_safe_bars():
    frame = pygame_faction.frame_for(
        SimpleNamespace(
            faction_reputation={
                "pirate": -100,
                "merchant": 0,
                "civilian": 45,
                "militia": 100,
            },
        ),
    )

    assert frame.title == "FACTION STANDINGS"
    assert [row.label for row in frame.rows] == ["Pirate", "Merchant", "Civilian", "Militia"]
    assert frame.rows[0].attitude == "Enemy"
    assert frame.rows[-1].attitude == "Allied"
    assert all(len(row.bar) == 31 for row in frame.rows)
    assert all(all(ord(char) < 128 for char in row.bar) for row in frame.rows)


def test_faction_frame_round_trips_payload():
    frame = pygame_faction.frame_for(SimpleNamespace(faction_reputation={}))

    assert pygame_faction._frame_from_payload(
        pygame_faction._frame_payload(frame),
    ) == frame


def test_faction_key_mapping_preserves_close_guide_and_quit():
    class FakePygame:
        QUIT = 1
        KEYDOWN = 2
        K_ESCAPE = 10
        K_RETURN = 11
        K_KP_ENTER = 12
        K_QUESTION = 13

    fake = FakePygame()
    key = lambda value: SimpleNamespace(type=fake.KEYDOWN, key=value)

    assert pygame_faction._handle_key(fake, SimpleNamespace(type=fake.QUIT)) == "QUIT"
    assert pygame_faction._handle_key(fake, key(fake.K_ESCAPE)) == "BACK"
    assert pygame_faction._handle_key(fake, key(fake.K_RETURN)) == "BACK"
    assert pygame_faction._handle_key(fake, key(fake.K_QUESTION)) == "GUIDE"
    assert pygame_faction._handle_key(fake, SimpleNamespace(type=99, key=0)) == "IGNORE"


def test_faction_shared_guide_outcome_is_returned_to_parent(monkeypatch):
    class FakePygame:
        QUIT = 1
        KEYDOWN = 2
        K_ESCAPE = 10
        K_RETURN = 11
        K_KP_ENTER = 12
        K_QUESTION = 13
        event = SimpleNamespace(
            wait=lambda: SimpleNamespace(type=FakePygame.KEYDOWN, key=FakePygame.K_QUESTION),
        )

    class Screen:
        def get_size(self):
            return (1600, 960)

        def fill(self, _color):
            pass

    engine = SimpleNamespace(
        pygame=FakePygame,
        logical_surface=Screen(),
        present=lambda: None,
    )
    context = SimpleNamespace(_runtime=SimpleNamespace(engine=engine))
    ctx = SimpleNamespace(faction_reputation={})
    monkeypatch.setattr(pygame_faction, "_fit_font", lambda *args: object())
    monkeypatch.setattr(pygame_faction, "_draw_frame", lambda *args: None)

    assert pygame_faction.run_shared(context, ctx) == "GUIDE"


def test_faction_runner_uses_semantic_adapter_and_falls_back(monkeypatch):
    ctx = SimpleNamespace(faction_reputation={}, context=object())
    captured = {}
    monkeypatch.setattr(
        pygame_faction,
        "run_for_context",
        lambda context, received: captured.update(context=context, ctx=received) or "BACK",
    )
    monkeypatch.setattr(pygame_faction, "enabled", lambda: True)

    from src.spacehack.menus import _ship_menu
    _ship_menu._run_faction_view(ctx)

    assert captured["ctx"] is ctx


def test_faction_runner_falls_back_when_worker_unavailable(monkeypatch):
    calls = []
    ctx = SimpleNamespace(
        faction_reputation={},
        context=SimpleNamespace(present=lambda _console: calls.append("present")),
    )
    monkeypatch.setattr(pygame_faction, "enabled", lambda: True)
    monkeypatch.setattr(
        pygame_faction,
        "run_for_context",
        lambda *args: (_ for _ in ()).throw(
            pygame_faction.PygameFactionUnavailable("missing"),
        ),
    )

    from src.spacehack.menus import _ship_menu
    monkeypatch.setattr(
        _ship_menu.ui.Modal,
        "run",
        lambda self, render, update: calls.append("fallback") or None,
    )
    _ship_menu._run_faction_view(ctx)

    assert "fallback" in calls
