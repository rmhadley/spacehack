"""Title-screen and character-creation orchestration."""

from __future__ import annotations


import os
from collections.abc import Awaitable, Callable

from . import pygame_story, pygame_title, ui
from .input_helpers import Outcome, _run_confirm, _run_pick
from .pygame_runtime import PygameContext
from .saveload import delete_save as _delete_save
from .saveload import load_game as _load_game
from .saveload import save_exists as _save_exists


def _fresh_seed(seed_rng: Callable[[int], None]) -> None:
    """Seed a new roguelike run.

    Fresh OS entropy per run — unless ``SPACEHACK_SEED`` pins it for
    multi-seed testing (every New Game in one pinned session then
    replays the same run). Echoed in dev mode so the actual run seed
    is always knowable.
    """

    from .engine import new_game_seed

    seed = new_game_seed()
    seed_rng(seed)
    if os.environ.get("SPACEHACK_DEV"):
        print(
            f"[DEV MODE] Run seed: {seed}"
            f"{' (pinned via SPACEHACK_SEED)' if os.environ.get('SPACEHACK_SEED') else ''}"
        )


async def _run_character_creation(
    context: PygameContext,
    run_game: Callable[..., Awaitable[None]],
    seed_rng: Callable[[int], None],
) -> None:
    """Run character creation, returning to the title menu on cancel."""
    while True:
        outcome, species_id = await _run_pick(context, ui.species_menu())
        if outcome in (Outcome.QUIT, Outcome.BACK):
            return
        outcome, class_id = await _run_pick(context, ui.class_menu())
        if outcome is Outcome.QUIT:
            return
        if outcome is Outcome.BACK:
            continue
        outcome = await _run_confirm(context, species_id, class_id)
        if outcome is Outcome.QUIT:
            return
        if outcome is Outcome.BACK:
            continue
        _fresh_seed(seed_rng)
        await run_game(context, species_id, class_id)
        return


async def _run_title_selection(
    context: PygameContext,
    run_game: Callable[..., Awaitable[None]],
    seed_rng: Callable[[int], None],
) -> bool:
    """Run one title selection and return whether the title flow should stop."""
    save_available = _save_exists()
    outcome, _selected = await pygame_title.run_for_context(context, save_available)
    if outcome is ui.TitleMenuOutcome.EXIT:
        return True
    if outcome is ui.TitleMenuOutcome.TUTORIAL:
        _fresh_seed(seed_rng)
        await run_game(context, "human", "merchant", tutorial=True)
        return False
    if outcome is ui.TitleMenuOutcome.CONTINUE:
        loaded_ctx = _load_game(context)
        if loaded_ctx is not None:
            _delete_save()
            await run_game(context, loaded_ctx=loaded_ctx)
        else:
            await pygame_story.dismiss(
                context,
                title="SAVE ERROR",
                body="Save file corrupted.",
                caption="spacehack - save error",
            )
        return False
    if outcome is ui.TitleMenuOutcome.IGNORE:
        return False
    await _run_character_creation(context, run_game, seed_rng)
    return False


async def run_title_flow(
    context: PygameContext,
    run_game: Callable[..., Awaitable[None]],
    *,
    seed_rng: Callable[[int], None],
) -> None:
    """Run the title menu until the user exits the application."""
    await pygame_title.run_splash_for_context(context)
    while not await _run_title_selection(context, run_game, seed_rng):
        pass
