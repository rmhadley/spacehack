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
re-exports its data module's symbols and defines its own runtime
functions identically.
"""
from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

from . import main_quest as main_quest_module
from .data.npcs import NPC, find_npc, list_npcs
from .game_context import GameContext

if TYPE_CHECKING:
    from .mission import Mission

class TalkOutcome(Enum):
    """What happened during a single NPC-talk dialog iteration.

    ESC walks away (BACK); Enter opens the NPC's mission offerings
    (WORK); when the player has an active delivery mission that
    this NPC can fulfil (:data:`Mission.required_cargo_size` > 0
    and giver matches), Enter drives :attr:`DELIVER` instead and
    the dialog paints an extra ``> Deliver <title> <`` row. Quit
    closes the window; anything else is IGNORE. Mirrors
    :class:`spacehack.__main__.ShipBuyOutcome` so a future
    iteration can grow the dialog with more branches (e.g.
    ``WORK`` -> goods for sale, ``REST``) without churning the
    call site.
    """
    IGNORE = auto()
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

def _npc_pygame_items(npc, missions, quest_options=()):
    """Build opaque Pygame actions for every NPC-talk option."""
    from . import pygame_menu

    items = [
        pygame_menu.MenuItem(label, "Continue the main-quest conversation.", f"QUEST:{step_id}")
        for label, step_id in quest_options
    ]
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

def _map_pygame_npc_result(outcome, action, missions):
    """Map a worker result to the existing NPC talk contract."""
    if outcome == "QUIT":
        return (TalkOutcome.QUIT, None)
    if outcome != "SELECT":
        return (TalkOutcome.BACK, None)
    if action == "WORK":
        return (TalkOutcome.WORK, None)
    if action.startswith("QUEST:"):
        return (TalkOutcome.QUEST, action.split(":", 1)[1])
    if action.startswith("DELIVER:"):
        try:
            index = int(action.split(":", 1)[1])
            return (TalkOutcome.DELIVER, missions[index])
        except (ValueError, IndexError):
            return None
    return None

def _run_pygame_npc_talk(ctx, npc, quest_body, missions, quest_options=()):
    """Run NPC talk through the shared selectable Pygame screen."""
    from . import pygame_menu

    items = _npc_pygame_items(npc, missions, quest_options)
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
) -> tuple[TalkOutcome, Mission | None]:
    """Show the talk modal for ``npc`` and return the chosen outcome.

    Resolves main-quest dialogue for this NPC: the body text
    overrides ``flavor_text`` when a live quest dialogue exists, and
    a ``quest_options`` row appears when the entry has an
    ``option_label`` + ``trigger_on_talk``. Picking the quest row
    calls :func:`main_quest.trigger_dialogue` (plants the faction
    claim + unlocks the tool) and returns :attr:`TalkOutcome.QUEST`.

    Menu has one "Deliver: <title>" row per deliverable mission
    (highlighted gold), then "View available work" at the bottom.
    ENTER on a deliver row returns DELIVER with that mission;
    ENTER on the work row returns WORK.

    Returns ``(outcome, deliver_mission)``: the specific mission
    when DELIVER, ``None`` otherwise.
    """
    ctx.log.add(f"You chat briefly with {npc.name}.")
    # Resolve quest dialogue for the talk modal body: when the NPC has
    # live quest dialogue, the body text shows the appropriate variant
    # (intro / active / complete). The quest option row (below) is the
    # only way to trigger the full-screen overlay — no auto-trigger.
    _quest_body, _ = main_quest_module.resolve_npc_dialogue(ctx, npc.id)

    _missions = deliver_missions or []
    n_deliver = len(_missions)

    # Main-quest dialogue resolution (read-only lookups).
    _quest_options: list[tuple[str, str]] = []
    _opt = main_quest_module.quest_option_for(ctx, npc.id)
    if _opt is not None:
        _quest_options.append(_opt)
    n_quest = len(_quest_options)
    n_work = 1 if npc.guild else 0
    n_options = n_quest + n_deliver + n_work  # quest rows + deliver rows + work
    if n_options == 0:
        # No menu items — but if there's quest dialogue text that
        # differs from the NPC's standard flavor, show it as a
        # read-only overlay so the player can read it.
        if _quest_body != npc.flavor_text:
            main_quest_module.show_quest_readout(ctx, npc, _quest_body)
        else:
            ctx.log.add(f'{npc.name} has nothing more to say right now.')
        return (TalkOutcome.BACK, None)

    # Quest-option rows still use the domain modal because selecting one
    # immediately mutates main-quest state; ordinary talk uses shared Pygame.
    result = _run_pygame_npc_talk(
        ctx,
        npc,
        _quest_body,
        _missions,
        _quest_options,
    )
    if result is None:
        raise RuntimeError("NPC talk returned no outcome")
    outcome, payload = result
    if outcome is TalkOutcome.QUEST and isinstance(payload, str):
        _offer = main_quest_module.show_help_offer(ctx, npc.id, payload)
        if _offer is main_quest_module.OfferOutcome.QUIT:
            return (TalkOutcome.QUIT, None)
        if _offer is main_quest_module.OfferOutcome.ACCEPT:
            main_quest_module.trigger_dialogue(ctx, npc.id, payload)
            main_quest_module.maybe_continue_chain(ctx, npc.id, payload)
        return (outcome, None)
    return result

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
