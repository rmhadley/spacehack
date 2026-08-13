"""Tests for title-screen flow orchestration."""

from types import SimpleNamespace

from src.spacehack import __main__ as game_main
from src.spacehack import title_flow, ui
from src.spacehack.input_helpers import Outcome


def test_tutorial_selection_reseeds_and_starts_forced_run(monkeypatch):
    seeds = []
    runs = []
    monkeypatch.setattr(
        title_flow.pygame_title,
        "run_for_context",
        lambda *_args: (ui.TitleMenuOutcome.TUTORIAL, 0),
    )
    monkeypatch.setattr(title_flow, "_fresh_seed", lambda seed: seeds.append(seed))

    result = title_flow._run_title_selection(
        object(),
        lambda *args, **kwargs: runs.append((args, kwargs)),
        object(),
    )

    assert result is False
    assert len(seeds) == 1
    assert runs[0][0][0] is not None
    assert runs[0][0][1:] == ("human", "merchant")
    assert runs[0][1] == {"tutorial": True}


def test_run_seeds_once_before_delegating_title_flow(monkeypatch):
    seeds = []
    calls = []
    monkeypatch.setattr(game_main, "seed_rng", lambda seed: seeds.append(seed))
    monkeypatch.setattr(
        title_flow,
        "run_title_flow",
        lambda context, run_game, *, seed_rng: calls.append((context, run_game, seed_rng)),
    )

    context = object()
    game_main.run(context)

    assert len(seeds) == 1
    assert calls[0][0] is context
    assert calls[0][1] is game_main._run_game
    assert calls[0][2] is game_main.seed_rng


def test_ignore_selection_returns_to_title_without_starting_game(monkeypatch):
    runs = []
    monkeypatch.setattr(
        title_flow.pygame_title,
        "run_for_context",
        lambda *_args: (ui.TitleMenuOutcome.IGNORE, 0),
    )

    assert title_flow._run_title_selection(
        object(),
        lambda *args, **kwargs: runs.append((args, kwargs)),
        object(),
    ) is False
    assert runs == []


def test_continue_deletes_save_only_after_successful_load(monkeypatch):
    calls = []
    context = object()
    loaded = SimpleNamespace()
    monkeypatch.setattr(
        title_flow.pygame_title,
        "run_for_context",
        lambda *_args: (ui.TitleMenuOutcome.CONTINUE, 0),
    )
    monkeypatch.setattr(title_flow, "_save_exists", lambda: True)
    monkeypatch.setattr(title_flow, "_load_game", lambda value: calls.append(("load", value)) or loaded)
    monkeypatch.setattr(title_flow, "_delete_save", lambda: calls.append(("delete",)))
    runs = []

    assert title_flow._run_title_selection(context, lambda *args, **kwargs: runs.append((args, kwargs)), object()) is False
    assert calls == [("load", context), ("delete",)]
    assert runs[0][1] == {"loaded_ctx": loaded}


def test_corrupt_continue_shows_error_without_starting_game(monkeypatch):
    context = object()
    dismissed = []
    monkeypatch.setattr(
        title_flow.pygame_title,
        "run_for_context",
        lambda *_args: (ui.TitleMenuOutcome.CONTINUE, 0),
    )
    monkeypatch.setattr(title_flow, "_load_game", lambda _context: None)
    monkeypatch.setattr(
        title_flow.pygame_story,
        "dismiss",
        lambda *args, **kwargs: dismissed.append((args, kwargs)),
    )
    runs = []

    assert title_flow._run_title_selection(context, lambda *args, **kwargs: runs.append(True), object()) is False
    assert runs == []
    assert dismissed[0][1]["title"] == "SAVE ERROR"


def test_character_creation_retries_back_and_seeds_before_start(monkeypatch):
    context = object()
    picks = iter(((Outcome.CONFIRM, "human"), (Outcome.BACK, None), (Outcome.CONFIRM, "human"), (Outcome.CONFIRM, "merchant")))
    confirms = iter((Outcome.CONFIRM,))
    seeds = []
    runs = []
    monkeypatch.setattr(title_flow, "_run_pick", lambda *_args: next(picks))
    monkeypatch.setattr(title_flow, "_run_confirm", lambda *_args: next(confirms))
    monkeypatch.setattr(title_flow, "_fresh_seed", lambda seed: seeds.append(seed))

    title_flow._run_character_creation(
        context,
        lambda *args, **kwargs: runs.append((args, kwargs)),
        object(),
    )

    assert len(seeds) == 1
    assert runs[0][0][1:] == ("human", "merchant")
    assert runs[0][1] == {}
