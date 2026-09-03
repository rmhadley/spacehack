"""Main quest objective handler registry.

Each objective type (``talk``, ``delve``, ``smuggle``, ...) is described by
one :class:`ObjectiveHandler` — a frozen dataclass of optional hook callables
that the generic dispatch sites call instead of chained if/elif branches.
Adding a new objective type is one handler entry in the registry table; the
dispatch sites never grow new branches.

The registry is built lazily (importing the implementation modules only on
first lookup) so the dispatch modules can import :func:`handler_for` at module
level without creating an import cycle — the implementation modules never
import this one at module level.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from ..data.main_quest import MainQuestStep
    from ..game_context import GameContext


@dataclass(frozen=True)
class ObjectiveHandler:
    """One objective type's runtime behavior, as optional hook callables.

    A hook of ``None`` means the type does not support that lifecycle event;
    dispatch sites fall back to the default (e.g. ``complete_step`` for
    ``on_trigger``).
    """

    name: str
    # Trigger path (NPC quest-option select). None = fall through to
    # complete_step (the "talk" behaviour).
    on_trigger: Callable[["GameContext", "MainQuestStep"], bool] | None = None
    # Post-completion side effects (e.g. salvage wreck cleanup).
    on_complete: Callable[["GameContext", "MainQuestStep"], None] | None = None
    # True = steps of this type yield quest-tagged loot that
    # secure_quest_loot handles (delve / salvage).
    secures_quest_loot: bool = False
    # Create quest-tagged space spawns for a live step in a system
    # (bounty / salvage).
    ensure_spawns: Callable[["GameContext", "MainQuestStep", str], bool] | None = None
    # Quest-option visibility gate (giver/receiver gating, e.g. smuggle).
    # True = the option row is shown / the trigger is allowed.
    option_gating: Callable[["GameContext", "MainQuestStep", str], bool] | None = None


# ---------------------------------------------------------------------------
# Type-specific hook implementations — thin orchestrators over the low-level
# mechanics in _core / _dialogue / _objectives / _spawns. The imports are
# lazy so this module never pulls the dispatch modules in at import time.
# ---------------------------------------------------------------------------


def _smuggle_trigger(ctx, step) -> bool:
    """Load the crate (available) or hand it over (active) on trigger."""
    from ._core import (
        STATUS_ACTIVE,
        _complete_smuggle_handover,
        _trigger_smuggle_crate,
        step_status,
    )
    if step_status(ctx, step.id) == STATUS_ACTIVE:
        return _complete_smuggle_handover(ctx, step)
    return _trigger_smuggle_crate(ctx, step)


def _salvage_trigger(ctx, step) -> bool:
    """Start a salvage step from NPC talk (loads the cargo into the hold)."""
    from ._dialogue import _start_salvage_step
    return _start_salvage_step(ctx, step)


def _visit_trigger(ctx, step) -> bool:
    """Complete the visit step when the player talks to the expert NPC."""
    from ._objectives import maybe_complete_visit
    return maybe_complete_visit(ctx, step.requires_npc_id)


def _bump_trigger(ctx, step) -> bool:
    """Bump objectives complete on the door bump, not the talk path."""
    return True


def _payment_option_gating(ctx, step, npc_id) -> bool:
    """Payment steps offer their row only when the player can afford it.

    The cost is open-ended fundraising: trade, bounties, contracts —
    any income counts, and the quest log carries the shortfall until
    the option appears.
    """
    return ctx.stats.credits >= step.payment_credits


def _payment_trigger(ctx, step) -> bool:
    """Consume the payment, then complete the step."""
    from ._core import complete_step

    if ctx.stats.credits < step.payment_credits:
        return False
    ctx.stats.credits -= step.payment_credits
    return complete_step(ctx, step.id)


def _smuggle_option_gating(ctx, step, npc_id) -> bool:
    """Smuggle giver/receiver gating: show the row only at the right end.

    The giver offers while the crate is NOT held; the receiver offers while
    it IS held. Returns True = the option row is shown / the trigger allowed.
    """
    from ._core import _smuggle_crate_held
    _held = _smuggle_crate_held(ctx, step.id)
    _is_receiver = step.requires_npc_id == npc_id
    return (_held and _is_receiver) or (not _held and not _is_receiver)


def _salvage_wreck_cleanup(ctx, step) -> None:
    """Remove the derelict wreck + guard spawns after a salvage completes."""
    from ._objectives import _cleanup_salvage_wreck
    _cleanup_salvage_wreck(ctx, step)


_HANDLERS: dict[str, ObjectiveHandler] | None = None


def _build_handlers() -> dict[str, ObjectiveHandler]:
    """Build the registry, importing implementation modules lazily.

    The lazy imports break the import cycle: the dispatch modules import
    :func:`handler_for` at module level, so this module must not import them
    until the first lookup.
    """
    from ._spawns import _ensure_bounty_spawns, _ensure_salvage_spawns
    return {
        "talk": ObjectiveHandler("talk"),
        "payment": ObjectiveHandler(
            "payment",
            on_trigger=_payment_trigger,
            option_gating=_payment_option_gating,
        ),
        "goods": ObjectiveHandler("goods"),
        "smuggle": ObjectiveHandler(
            "smuggle",
            on_trigger=_smuggle_trigger,
            option_gating=_smuggle_option_gating,
        ),
        "salvage": ObjectiveHandler(
            "salvage",
            on_trigger=_salvage_trigger,
            on_complete=_salvage_wreck_cleanup,
            secures_quest_loot=True,
            ensure_spawns=_ensure_salvage_spawns,
        ),
        "visit": ObjectiveHandler("visit", on_trigger=_visit_trigger),
        "bump": ObjectiveHandler("bump", on_trigger=_bump_trigger),
        "delve": ObjectiveHandler(
            "delve",
            secures_quest_loot=True,
        ),
        "bounty": ObjectiveHandler(
            "bounty",
            ensure_spawns=_ensure_bounty_spawns,
        ),
        "prison": ObjectiveHandler("prison"),
    }


def _registry() -> dict[str, ObjectiveHandler]:
    global _HANDLERS
    if _HANDLERS is None:
        _HANDLERS = _build_handlers()
    return _HANDLERS


def handler_for(objective_type: str) -> ObjectiveHandler | None:
    """Return the handler for ``objective_type`` (``None`` if unknown)."""
    return _registry().get(objective_type)


def registered_objective_types() -> tuple[str, ...]:
    """Every objective type with a registered handler, in table order."""
    return tuple(_registry())


__all__ = [
    "ObjectiveHandler",
    "handler_for",
    "registered_objective_types",
]
