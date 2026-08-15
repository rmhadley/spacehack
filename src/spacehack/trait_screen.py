"""Trait selection modal — shown at level 20 and 30 milestones.

Opened by :func:`spacehack.xp.add_xp` when the player reaches a
milestone.  Presents all qualifying traits (filtered by counters
and not-already-chosen) and lets the player pick one with ENTER.

Design doc: ``docs/design/in_progress/02_DESIGN_XP_LEVELING.md``
"""

from __future__ import annotations

from . import message_log
from .game_context import GameContext
from .xp import _qualifying_traits, ground_max_hp_bonus


def _apply_ironclad_hp(ctx: GameContext, trait_id: str) -> None:
    """Apply Ironclad's max-HP increase immediately after selection."""
    if trait_id != "ironclad":
        return
    from .ground_equipment import sum_armor_bonus
    _new_max_hp = (
        20 + ctx.ground_stats.stamina // 3
        + sum_armor_bonus(ctx.equipped_ground_armor.values(), "hp_bonus")
        + ground_max_hp_bonus(ctx)
    )
    _delta = _new_max_hp - ctx.ground_max_hp
    if _delta > 0:
        ctx.ground_hp += _delta
    ctx.ground_max_hp = _new_max_hp
    from .combat import _rules_ground
    _state = _rules_ground._state
    if _state is not None and _state.ctx is ctx:
        _state.player_hp += max(0, _delta)
        _state.player_max_hp = _new_max_hp


def _refresh_faction_boards(ctx: GameContext, trait_id: str) -> None:
    """Refill the matching faction boards when a career trait is earned."""
    if trait_id not in {"hauler", "fixer", "hunter"}:
        return
    from .mission import refresh_all_boards
    refresh_all_boards(ctx, force=True)


def _pick_trait(ctx: GameContext, candidates: list, action: str) -> bool | None:
    """Apply a valid trait action and log the new specialization."""
    trait_id = action.split(":", 1)[1]
    picked = next((trait for trait in candidates if trait.id == trait_id), None)
    if picked is None:
        return None
    ctx.player_traits.append(picked.id)
    _apply_ironclad_hp(ctx, picked.id)
    _refresh_faction_boards(ctx, picked.id)
    ctx.log.add_colored(
        f"Trait gained: {picked.name} - {picked.description}",
        message_log.COLOR_COMBAT_EVENT,
    )
    return True


def _run_pygame_trait_selection(ctx: GameContext, candidates: list) -> bool | None:
    """Run mandatory trait selection through Pygame."""
    from . import pygame_screen, pygame_ui

    frame = pygame_screen.ScreenFrame(
        title=f"TRAIT SELECTION - Level {ctx.player_level}",
        body=("Choose one trait. Selection is required before gameplay resumes.",),
        rows=tuple(
            pygame_screen.ScreenRow(
                text=trait.name,
                detail=trait.description,
                action=f"TRAIT:{trait.id}",
            )
            for trait in candidates
        ),
        footer=(pygame_ui.modal_hint(
            pygame_ui.NAV_HINT, "ENTER choose", pygame_ui.GUIDE_HINT,
        ),),
    )
    while True:
        outcome, action, _selected = pygame_screen.run_for_context(
            ctx.context, frame, caption="spacehack - trait selection",
        )
        if outcome == "GUIDE":
            from .help import _run_help_guide
            _run_help_guide(ctx)
            continue
        if outcome in {"BACK", "TAB"}:
            continue
        if outcome == "QUIT":
            raise SystemExit
        if outcome == "SELECT" and action.startswith("TRAIT:"):
            return _pick_trait(ctx, candidates, action)
        return None

def open_trait_selection(ctx: GameContext) -> None:
    """Open the trait selection modal.

    Lists all traits the player qualifies for (via
    :func:`_qualifying_traits`).  If none qualify, logs a message
    and returns without showing the modal — the player can open the
    Character screen later to pick when they do qualify.
    """
    _candidates = _qualifying_traits(ctx)
    if not _candidates:
        ctx.log.add_colored(
            "No qualifying traits available yet - check the Character screen later.",
            message_log.COLOR_IMPORTANT_EVENT,
        )
        return

    result = _run_pygame_trait_selection(ctx, _candidates)
    if result is None:
        raise RuntimeError("Trait selection returned no outcome")
    return
