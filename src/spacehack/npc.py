"""NPC runtime layer: dialog helpers and data facade.

NPCs live in two layers:

  * :mod:`spacehack.data.npcs` — the static catalog (the :class:`NPC`
    dataclass + per-guild tuples + :func:`find_npc` / :func:`list_npcs`
    lookup helpers). Adding a new NPC is a one-file edit there.
  * Here — the runtime dialog helpers (render/update/run NPC talk)
    that were extracted from :mod:`spacehack.__main__`, plus the
    :class:`TalkOutcome` enum they depend on, plus re-exports of
    the data-layer symbols so consumers (e.g. ``spacehack.__main__``)
    can keep using ``npc_module.NPC`` / ``npc_module.find_npc``
    without a second import line.

Mirrors the pattern established by :mod:`spacehack.mission`, which
re-exports its data module's symbols while keeping runtime functions
in the mission package.
"""
from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

from . import main_quest as main_quest_module
from .data.npcs import NPC, find_npc, list_npcs
from . import message_log as _ml
from .game_context import GameContext

if TYPE_CHECKING:
    from .mission import ActiveMission

class TalkOutcome(Enum):
    """What happened during a single NPC-talk dialog iteration.

    SCRUB: the player selected a scrub-broker's purchase row (doc 40).
    CUTOUT: the player selected a cut-out tech's install row (doc 40
    phase 5).

    ESC walks away (BACK); Enter opens the NPC's mission offerings
    (WORK); when the player has an active delivery mission that
    this NPC can fulfil (:data:`ActiveMission.required_cargo_size` > 0
    and giver matches), Enter drives :attr:`DELIVER` instead and
    the dialog paints an extra ``> Deliver <title> <`` row. Quit
    closes the window; anything else is IGNORE. Mirrors
    :class:`spacehack.__main__.ShipBuyOutcome` so a future
    iteration can grow the dialog with more branches (e.g.
    ``WORK`` -> goods for sale, ``REST``) without churning the
    call site.
    """
    IGNORE = auto()
    SCRUB = auto()
    CUTOUT = auto()
    BACK = auto()
    WORK = auto()
    DELIVER = auto()
    QUIT = auto()
    QUEST = auto()  # player picked the main-quest dialogue option row

def _run_pygame_menu(ctx, frames, *, caption: str):
    """Run the menu in the shared Pygame window."""
    from . import pygame_menu, pygame_runtime

    if not pygame_runtime.is_shared_context(getattr(ctx, "context", ctx)):
        raise pygame_menu.PygameMenuUnavailable("Shared Pygame runtime is not open")
    return pygame_menu.run_shared(ctx.context, frames, caption=caption)

def _npc_pygame_items(npc, missions, quest_options=(), scrub_price=None,
                      cutout_price=None):
    """Build opaque Pygame actions for every NPC-talk option."""
    from . import pygame_menu

    items = [
        pygame_menu.MenuItem(label, "Continue the main-quest conversation.", f"QUEST:{step_id}")
        for label, step_id in quest_options
    ]
    if scrub_price is not None:
        items.append(pygame_menu.MenuItem(
            f"Buy a scrubbed ID ({scrub_price:,}cr)",
            "A hull number with no history, filed to your collection.",
            "SCRUB",
        ))
    if cutout_price is not None:
        items.append(pygame_menu.MenuItem(
            f"Install a transponder cut-out ({cutout_price:,}cr)",
            "A one-time job: the transponder can go dark afterward.",
            "CUTOUT",
        ))
    items.extend(
        pygame_menu.MenuItem(
            "Deliver: " + mission.title,
            "Hand over the mission cargo.",
            f"DELIVER:{index}",
        )
        for index, mission in enumerate(missions)
    )
    if npc.guild:
        items.append(pygame_menu.MenuItem(
            "View available work",
            "Browse this guild's current mission offerings.",
            "WORK",
        ))
    return tuple(items)

def _npc_pygame_frames(npc, quest_body, items):
    """Build selected-state frames for ordinary NPC talk."""
    from . import pygame_menu, pygame_ui

    title = f"{npc.name} ({npc.guild})" if npc.guild else npc.name
    body = f'"{quest_body if quest_body else npc.flavor_text}"'
    return tuple(
        pygame_menu.MenuFrame(
            title=title,
            body=body,
            items=items,
            hints=(pygame_ui.modal_hint(
                pygame_ui.NAV_HINT, "ENTER select", "ESC walk away",
                pygame_ui.GUIDE_HINT,
            ),),
            selected=selected,
        )
        for selected in range(max(1, len(items)))
    )

# Simple action -> result rows; QUEST:/DELIVER: need prefix parsing.
_ACTION_RESULTS = {
    "SCRUB": (TalkOutcome.SCRUB, None),
    "CUTOUT": (TalkOutcome.CUTOUT, None),
    "WORK": (TalkOutcome.WORK, None),
}


def _map_pygame_npc_result(outcome, action, missions):
    """Map a worker result to the existing NPC talk contract."""
    if outcome == "QUIT":
        return (TalkOutcome.QUIT, None)
    if outcome != "SELECT":
        return (TalkOutcome.BACK, None)
    if action in _ACTION_RESULTS:
        return _ACTION_RESULTS[action]
    if action.startswith("QUEST:"):
        return (TalkOutcome.QUEST, action.split(":", 1)[1])
    if action.startswith("DELIVER:"):
        try:
            index = int(action.split(":", 1)[1])
            return (TalkOutcome.DELIVER, missions[index])
        except (ValueError, IndexError):
            return None
    return None

def _cutout_offer(ctx, npc_id: str) -> int | None:
    """The install row's price, or None when installed / wrong NPC."""
    from .identity import cutout_price
    if getattr(ctx, "transponder_cutout", False):
        return None
    return cutout_price(npc_id)


def _priced_rows(ctx, npc_id: str) -> tuple[int | None, int | None]:
    """(scrub, cutout) row prices — None where no row shows."""
    from .identity import scrub_price
    return scrub_price(npc_id), _cutout_offer(ctx, npc_id)

def _run_pygame_npc_talk(
    ctx, npc, quest_body, missions, quest_options=(), scrub_price=None,
    cutout_price=None,
):
    """Run NPC talk through the shared selectable Pygame screen."""

    items = _npc_pygame_items(
        npc, missions, quest_options, scrub_price, cutout_price,
    )
    frames = _npc_pygame_frames(npc, quest_body, items)
    while True:
        outcome, action, _selected = _run_pygame_menu(
            ctx,
            frames,
            caption=f"spacehack - {npc.name}",
        )
        if outcome == "GUIDE":
            from .help import _run_help_guide
            _run_help_guide(ctx)
            continue
        return _map_pygame_npc_result(outcome, action, missions)

def _run_npc_talk(
    ctx: GameContext,
    npc: NPC,
    *,
    deliver_missions: list | None = None,
) -> tuple[TalkOutcome, ActiveMission | None]:
    """Run the talk modal: quest row, deliver rows, work row.

    Returns ``(outcome, mission)`` — the mission when DELIVER, else None.
    """
    ctx.log.add(f"You chat briefly with {npc.name}.")
    _quest_body, _ = main_quest_module.resolve_npc_dialogue(ctx, npc.id)
    _missions = deliver_missions or []
    _quest_options = _quest_rows(ctx, npc)
    _scrub_price, _cutout_price = _priced_rows(ctx, npc.id)
    n_options = (
        len(_quest_options) + len(_missions) + (1 if npc.guild else 0)
        + int(_scrub_price is not None) + int(_cutout_price is not None)
    )
    if n_options == 0:
        return _no_options_reply(ctx, npc, _quest_body)

    # The domain modal: quest rows mutate main-quest state on select.
    result = _run_pygame_npc_talk(
        ctx,
        npc,
        _quest_body,
        _missions,
        _quest_options,
        _scrub_price,
        _cutout_price,
    )
    if result is None:
        raise RuntimeError("NPC talk returned no outcome")
    _purchase = _PURCHASE_HANDLERS.get(result[0])
    if _purchase is not None:
        return _purchase(ctx, npc)
    if result[0] is TalkOutcome.QUEST and isinstance(result[1], str):
        return _finish_quest_row(ctx, npc, result)
    return result


def _finish_quest_row(ctx, npc, result):
    """Resolve a selected quest row (offer -> accept -> trigger)."""
    _quit = _accept_quest_option(ctx, npc, result[1])
    if _quit:
        return (TalkOutcome.QUIT, None)
    return (result[0], None)


def _quest_rows(ctx, npc) -> list[tuple[str, str]]:
    """The live quest option row, if this NPC offers one."""
    _opt = main_quest_module.quest_option_for(ctx, npc.id)
    return [_opt] if _opt is not None else []


def _no_options_reply(ctx, npc, quest_body):
    """No menu rows: read-only flavor overlay, or the nothing-to-say log."""
    if quest_body != npc.flavor_text:
        main_quest_module.show_quest_readout(ctx, npc, quest_body)
    else:
        ctx.log.add(f'{npc.name} has nothing more to say right now.')
    return (TalkOutcome.BACK, None)


def _handle_scrub_purchase(ctx, npc):
    """Resolve a scrub-broker purchase row (doc 40)."""
    from .identity import buy_scrubbed_id as _buy_scrub
    if _buy_scrub(ctx, npc.id):
        ctx.log.add_colored(
            f"Scrubbed ID filed: {ctx.collected_ids[-1]['id']}. "
            "Cycle IDs on the F screen.",
            _ml.COLOR_IMPORTANT_EVENT,
        )
    else:
        ctx.log.add(f"{npc.name} names a price you can't meet.")
    return (TalkOutcome.BACK, None)


def _handle_cutout_purchase(ctx, npc):
    """Resolve a cut-out-tech install row (doc 40 phase 5)."""
    from .identity import buy_transponder_cutout as _buy_cutout
    if _buy_cutout(ctx, npc.id):
        ctx.log.add("Cut-out installed.")
    else:
        ctx.log.add(f"{npc.name} names a price you can't meet.")
    return (TalkOutcome.BACK, None)


# Resolved at call time (both handlers defined above).
_PURCHASE_HANDLERS = {
    TalkOutcome.SCRUB: _handle_scrub_purchase,
    TalkOutcome.CUTOUT: _handle_cutout_purchase,
}


def _accept_quest_option(ctx, npc, payload) -> bool:
    """Offer the quest, and on accept trigger it plus follow-ups.

    Returns True only when the player quit out of the offer modal.
    """
    _offer = main_quest_module.show_help_offer(ctx, npc.id, payload)
    if _offer is main_quest_module.OfferOutcome.QUIT:
        return True
    if _offer is main_quest_module.OfferOutcome.ACCEPT:
        main_quest_module.trigger_dialogue(ctx, npc.id, payload)
        main_quest_module.maybe_continue_chain(ctx, npc.id, payload)
    return False

# IDENTITY GUARANTEE: ``npc_module.NPC is NPC`` (and ditto for
# find_npc / list_npcs). Smoke-verified at the registry build site
# so a future refactor that accidentally drops the re-exports (or
# wraps the symbol in a proxy) breaks the identity check rather
# than silently changing consumer semantics.
__all__ = [
    "NPC",
    "TalkOutcome",
    "find_npc",
    "list_npcs",
    "_run_npc_talk",
]
