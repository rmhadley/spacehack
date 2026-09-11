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
from . import rumor as rumor_module
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
    RIG = auto()
    SELL = auto()
    BACK = auto()
    WORK = auto()
    DELIVER = auto()
    QUIT = auto()
    QUEST = auto()  # player picked the main-quest dialogue option row
    ASKAROUND = auto()  # player opened the Ask Around sub-menu (doc 42)

def _run_pygame_menu(ctx, frames, *, caption: str):
    """Run the menu in the shared Pygame window."""
    from . import pygame_menu, pygame_runtime

    if not pygame_runtime.is_shared_context(getattr(ctx, "context", ctx)):
        raise pygame_menu.PygameMenuUnavailable("Shared Pygame runtime is not open")
    return pygame_menu.run_shared(ctx.context, frames, caption=caption)

def _append_priced_items(items, scrub_price, cutout_price, rig_price):
    """The identity storefront rows (doc 40): each offered only while
    it applies — unowned, at the right NPC."""
    from . import pygame_menu

    _rows = (
        (scrub_price, "Buy a scrubbed ID ({:,}cr)",
         "A hull number with no history, filed to your collection.", "SCRUB"),
        (cutout_price, "Install a transponder cut-out ({:,}cr)",
         "A one-time job: the transponder can go dark afterward.", "CUTOUT"),
        (rig_price, "Buy a clone rig ({:,}cr)",
         "A reusable rig that allows cloning transponder IDs from a "
         "ship's console.", "RIG"),
    )
    for _price, _label, _body, _action in _rows:
        if _price is not None:
            items.append(pygame_menu.MenuItem(
                _label.format(_price), _body, _action,
            ))


def _append_rumor_items(items, ask_around):
    """The doc-42 row: one Ask around entry opening the sub-menu."""
    from . import pygame_menu

    if ask_around:
        items.append(pygame_menu.MenuItem(
            "Ask around", "Ask what they know.", "ASKAROUND",
        ))


def _npc_pygame_items(npc, missions, quest_options=(), scrub_price=None,
                      cutout_price=None, rig_price=None, sell_ids=False,
                      ask_around=False):
    """Build opaque Pygame actions for every NPC-talk option."""
    from . import pygame_menu

    items = [
        pygame_menu.MenuItem(label, "Continue the main-quest conversation.", f"QUEST:{step_id}")
        for label, step_id in quest_options
    ]
    _append_priced_items(items, scrub_price, cutout_price, rig_price)
    _append_rumor_items(items, ask_around)
    items.extend(
        pygame_menu.MenuItem(
            "Deliver: " + mission.title,
            "Hand over the mission cargo.",
            f"DELIVER:{index}",
        )
        for index, mission in enumerate(missions)
    )
    if sell_ids:
        items.append(pygame_menu.MenuItem(
            "Sell a transponder ID",
            "The dealer pays by the sheet.",
            "SELLIDS",
        ))
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

# Simple action -> result rows; QUEST:/DELIVER:/RUMOR: need prefix parsing.
_ACTION_RESULTS = {
    "SCRUB": (TalkOutcome.SCRUB, None),
    "CUTOUT": (TalkOutcome.CUTOUT, None),
    "RIG": (TalkOutcome.RIG, None),
    "SELLIDS": (TalkOutcome.SELL, None),
    "WORK": (TalkOutcome.WORK, None),
    "ASKAROUND": (TalkOutcome.ASKAROUND, None),
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

def _talk_refusal(ctx, npc) -> str | None:
    """The NPC's refusal line while the talk gate holds, else None.

    The gate reads the RESOLVED sheet (a pirate-liked clone passes) —
    the same read every reader in the game makes (doc 40 6a)."""
    _gate = getattr(npc, "talk_gate", None)
    if _gate is None:
        return None
    from . import identity
    _faction, _min_standing, _line = _gate
    _standing = identity.effective_reputation(ctx).get(_faction, 0)
    if _standing >= _min_standing:
        return None
    return _line


def _cutout_offer(ctx, npc_id: str) -> int | None:
    """The install row's price, or None when installed / wrong NPC."""
    from .identity import cutout_price
    if getattr(ctx, "transponder_cutout", False):
        return None
    return cutout_price(npc_id)


def _rig_offer(ctx, npc_id: str) -> int | None:
    """The rig row's price, or None when owned / wrong NPC."""
    from .identity import rig_price
    if getattr(ctx, "transponder_rig", False):
        return None
    return rig_price(npc_id)


def _priced_rows(ctx, npc_id: str) -> tuple[int | None, int | None, int | None]:
    """(scrub, cutout, rig) row prices — None where no row shows.

    A knowledge-gated NPC's rows exist only once the gate rumor is
    heard (doc 42 phase 2: the knowledge is the only key)."""
    from . import identity
    _gate = identity.KNOWLEDGE_GATES.get(npc_id)
    if _gate is not None and _gate not in ctx.known_rumors:
        return (None, None, None)
    return (
        identity.scrub_price(npc_id),
        _cutout_offer(ctx, npc_id),
        _rig_offer(ctx, npc_id),
    )

def _run_pygame_npc_talk(
    ctx, npc, quest_body, missions, quest_options=(), scrub_price=None,
    cutout_price=None, rig_price=None, sell_ids=False, items=None,
):
    """Run NPC talk through the shared selectable Pygame screen."""

    if items is None:
        items = _npc_pygame_items(
            npc, missions, quest_options, scrub_price, cutout_price,
            rig_price, sell_ids,
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

def _is_id_buyer(ctx, npc) -> bool:
    """Whether this NPC buys IDs AND the player holds any (the row
    exists only when there is something to sell)."""
    from . import identity
    if npc.id not in identity.ID_BUYERS:
        return False
    return bool(list(getattr(ctx, "collected_ids", ()) or []))


def _sell_ids_items(ctx) -> list:
    """One menu row per held ID, priced by its sheet."""
    from . import pygame_menu
    from .identity import sell_value
    return [
        pygame_menu.MenuItem(
            f"{entry.get('label', 'ID')} {entry['id']} ({sell_value(entry):,}cr)",
            "Sell this ID to the dealer.",
            f"SELLID:{entry['id']}",
        )
        for entry in list(getattr(ctx, "collected_ids", ()) or [])
    ]


def _run_choice_submenu(ctx, *, title, body, items, caption):
    """Run one sub-menu pass until ESC (None), QUIT ("QUIT"), or a
    pick (its action string). The shared loop behind the sell and
    Ask Around sub-menus."""
    from . import pygame_menu, pygame_ui
    from .help import _run_help_guide

    _frames = tuple(
        pygame_menu.MenuFrame(
            title=title,
            body=body,
            items=items,
            hints=(pygame_ui.modal_hint(
                pygame_ui.NAV_HINT, "ENTER select", "ESC done",
                pygame_ui.GUIDE_HINT,
            ),),
            selected=_selected,
        )
        for _selected in range(max(1, len(items)))
    )
    while True:
        _outcome, _action, _selected = _run_pygame_menu(ctx, _frames, caption=caption)
        if _outcome == "GUIDE":
            _run_help_guide(ctx)
            continue
        if _outcome == "SELECT":
            return _action
        if _outcome == "QUIT":
            return "QUIT"
        return None


def _run_sell_menu(ctx):
    """Run the buy sub-menu until ESC (returns None) or a pick
    (returns the ``SELLID:<id>`` action)."""
    while True:
        _items = _sell_ids_items(ctx)
        if not _items:
            ctx.log.add("You have nothing left to sell.")
            return None
        return _run_choice_submenu(
            ctx,
            title="The dealer buys",
            body='"Let me see what you have."',
            items=_items,
            caption="spacehack - sell IDs",
        )


def _handle_sell_ids(ctx):
    """The dealer's buy sub-menu (doc 40 6b): pick an ID, sell it.

    Stays open until ESC — multiple sales per sitting."""
    from .identity import remove_id, sell_value

    while True:
        _action = _run_sell_menu(ctx)
        if _action == "QUIT":
            return (TalkOutcome.QUIT, None)
        if _action is None:
            return (TalkOutcome.BACK, None)
        _entry_id = _action.partition(":")[2]
        _entry = next(
            (_e for _e in ctx.collected_ids if _e.get("id") == _entry_id),
            None,
        )
        if _entry is None:
            continue
        _price = sell_value(_entry)
        remove_id(ctx, _entry_id)
        ctx.stats.credits += _price
        ctx.log.add(
            f"Sold {_entry.get('label', 'ID')} {_entry_id} "
            f"for {_price:,}cr."
        )


def _show_rumor_readout(ctx, npc, text: str) -> None:
    """The heard-text readout — the quest-readout idiom: a modal, not
    a log line; the guide re-presents it, QUIT exits the game."""
    from .pygame_story import dismiss

    while True:
        _outcome = dismiss(
            ctx.context,
            title=npc.name.upper(),
            body=text,
            caption=f"spacehack - {npc.name}",
        )
        if _outcome == "__GUIDE__":
            continue
        if _outcome == "QUIT":
            raise SystemExit
        return


def _labeled(topic: str) -> str:
    """A topic as a row label — the subject, capitalized."""
    return topic[:1].upper() + topic[1:]


def _ask_submenu_items(topics, offers, buys) -> list:
    """Sub-menu rows: hear rows, then Sell offers, then priced buys."""
    from . import pygame_menu

    items = [
        pygame_menu.MenuItem(
            _labeled(topic), "Hear the next piece.", f"ASKTOPIC:{next_id}",
        )
        for topic, next_id in topics
    ]
    items += [
        pygame_menu.MenuItem(
            f"Sell: {_labeled(rumor_module.topic_label(rumor_id))}",
            f"Earn {value} favor.",
            f"OFFER:{rumor_id}",
        )
        for rumor_id, value in offers
    ]
    items += [
        pygame_menu.MenuItem(
            _labeled(rumor_module.topic_label(rumor_id)),
            f"Costs {price} favor.",
            f"BUY:{rumor_id}:{price}",
        )
        for rumor_id, price in buys
    ]
    return items


def _ask_rows(ctx, npc):
    """(topics, offers, buys) for one sub-menu pass — offers and buys
    exist only at a dealer (ruling 10)."""
    from . import identity

    topics = rumor_module.askable_topics(
        ctx.known_rumors, identity.effective_reputation(ctx),
        ctx.player_traits, npc.id,
    )
    if not rumor_module.is_dealer(npc.id):
        return topics, [], []
    offers = rumor_module.offerable_rumors(
        ctx.known_rumors, ctx.rumor_favor, npc.id,
    )
    buys = rumor_module.exclusive_offers(
        ctx.known_rumors, ctx.rumor_favor, npc.id,
        rumor_module.find_dealer(npc.id).exclusives,
    )
    return topics, offers, buys


def _ask_body(ctx, npc) -> str:
    """The body line: the dealer's live balance, else the ask prompt."""
    if rumor_module.is_dealer(npc.id):
        return f"Favor: {rumor_module.favor_for(ctx.rumor_favor, npc.id)}"
    return '"What do you want to know?"'


def _ask_hear(ctx, npc, rumor_id: str) -> None:
    rumor_module.hear(ctx, rumor_id)
    _show_rumor_readout(ctx, npc, rumor_module.witness_text(rumor_id, npc.id))


def _ask_offer(ctx, npc, rumor_id: str) -> None:
    _earned = rumor_module.offer_rumor(ctx, npc.id, rumor_id)
    if _earned:
        ctx.log.add(
            f"Sold {_labeled(rumor_module.topic_label(rumor_id))} "
            f"for {_earned} favor."
        )


def _ask_buy(ctx, npc, payload: str) -> None:
    """A priced pick: the row's holding rides in the action string, so
    the buy spends exactly what the row offered."""
    rumor_id, _, price = payload.partition(":")
    if not rumor_module.buy_exclusive(ctx, npc.id, rumor_id, int(price)):
        ctx.log.add("You don't have the favor for that yet.")
        return
    _show_rumor_readout(ctx, npc, rumor_module.entry_text(rumor_id))


_ASK_PICK_HANDLERS = {
    "ASKTOPIC": _ask_hear,
    "OFFER": _ask_offer,
    "BUY": _ask_buy,
}


def _apply_ask_pick(ctx, npc, action: str) -> None:
    """One sub-menu pick: hear it, sell it, or buy it."""
    _prefix, _, _payload = action.partition(":")
    _handler = _ASK_PICK_HANDLERS.get(_prefix)
    if _handler is not None:
        _handler(ctx, npc, _payload)


def _handle_ask_around(ctx, npc) -> tuple[TalkOutcome, None]:
    """The Ask Around sub-menu (doc 42): askable topics plus — at a
    dealer — Sell offers and priced exclusives over a live Favor line
    (sell-menu idiom: rows rebuild every pass, no per-pick modal).
    Stays open until ESC."""
    while True:
        _topics, _offers, _buys = _ask_rows(ctx, npc)
        if not (_topics or _offers or _buys) and not rumor_module.is_dealer(npc.id):
            return (TalkOutcome.BACK, None)
        _action = _run_choice_submenu(
            ctx,
            title="Ask around",
            body=_ask_body(ctx, npc),
            items=_ask_submenu_items(_topics, _offers, _buys),
            caption=f"spacehack - {npc.name}",
        )
        if _action == "QUIT":
            return (TalkOutcome.QUIT, None)
        if _action is None:
            return (TalkOutcome.BACK, None)
        _apply_ask_pick(ctx, npc, _action)


def _refusal_reply(ctx, npc):
    """The gated NPC's refusal: logged once, no modal (doc 40 6a)."""
    _refusal = _talk_refusal(ctx, npc)
    if _refusal is not None:
        ctx.log.add(_refusal)
        return (TalkOutcome.BACK, None)
    return None


def _offers_rumors(ctx, npc) -> bool:
    """Whether the Ask around row shows: always at a dealer (ruling
    10 — their trade lives in the sub-menu), else when the NPC holds
    an unheard opener they can deliver or a heard chain they can
    extend, read off the RESOLVED sheet (dark reads neutral)."""
    if rumor_module.is_dealer(npc.id):
        return True
    from . import identity

    return bool(rumor_module.askable_topics(
        ctx.known_rumors, identity.effective_reputation(ctx),
        ctx.player_traits, npc.id,
    ))


def _run_npc_talk(
    ctx: GameContext,
    npc: NPC,
    *,
    deliver_missions: list | None = None,
) -> tuple[TalkOutcome, ActiveMission | None]:
    """Run the talk modal: quest row, deliver rows, work row.

    Returns ``(outcome, mission)`` — the mission when DELIVER, else None.
    """
    _refused = _refusal_reply(ctx, npc)
    if _refused is not None:
        return _refused
    ctx.log.add(f"You chat briefly with {npc.name}.")
    _quest_body, _ = main_quest_module.resolve_npc_dialogue(ctx, npc.id)
    _missions = deliver_missions or []
    _quest_options = _quest_rows(ctx, npc)
    _ask_around = _offers_rumors(ctx, npc)
    _scrub_price, _cutout_price, _rig_price = _priced_rows(ctx, npc.id)
    # The builder is the single source of truth for what rows exist: the
    # no-options decision derives from its output, never a parallel count.
    items = _npc_pygame_items(
        npc, _missions, _quest_options, _scrub_price, _cutout_price,
        _rig_price, _is_id_buyer(ctx, npc), _ask_around,
    )
    if not items:
        return _no_options_reply(ctx, npc, _quest_body)

    # The domain modal: quest rows mutate main-quest state on select.
    result = _run_pygame_npc_talk(
        ctx, npc, _quest_body, _missions, _quest_options,
        _scrub_price, _cutout_price, _rig_price, _is_id_buyer(ctx, npc),
        items=items,
    )
    return _resolve_talk_result(ctx, npc, result)


def _resolve_talk_result(ctx, npc, result):
    """Post-modal dispatch: purchases, the ID market, rumors, quest rows."""
    if result is None:
        raise RuntimeError("NPC talk returned no outcome")
    _purchase = _PURCHASE_HANDLERS.get(result[0])
    if _purchase is not None:
        return _purchase(ctx, npc)
    if result[0] is TalkOutcome.SELL:
        return _handle_sell_ids(ctx)
    if result[0] is TalkOutcome.ASKAROUND:
        return _handle_ask_around(ctx, npc)
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


def _purchase_lines(outcome, ctx):
    """(colored, line) for a successful identity purchase (doc 40).

    The scrub's line names the new hull number; the rest are fixed."""
    if outcome is TalkOutcome.SCRUB:
        return True, (
            f"Scrubbed ID filed: {ctx.collected_ids[-1]['id']}. "
            "Cycle IDs on the F screen."
        )
    _plain = {
        TalkOutcome.CUTOUT: "Cut-out installed.",
        TalkOutcome.RIG: "Clone rig acquired.",
    }
    return False, _plain[outcome]


def _handle_purchase(ctx, npc, outcome):
    """Resolve any identity purchase row (doc 40): buy, log, done."""
    from . import identity as _identity

    if outcome is TalkOutcome.SCRUB and _identity.library_full(ctx):
        ctx.log.add("Your ID book is full.")
        return (TalkOutcome.BACK, None)

    _buy = {
        TalkOutcome.SCRUB: _identity.buy_scrubbed_id,
        TalkOutcome.CUTOUT: _identity.buy_transponder_cutout,
        TalkOutcome.RIG: _identity.buy_clone_rig,
    }[outcome]
    if _buy(ctx, npc.id):
        _colored, _line = _purchase_lines(outcome, ctx)
        if _colored:
            ctx.log.add_colored(_line, _ml.COLOR_IMPORTANT_EVENT)
        else:
            ctx.log.add(_line)
    else:
        ctx.log.add(f"{npc.name} names a price you can't meet.")
    return (TalkOutcome.BACK, None)


# Resolved at call time.
_PURCHASE_HANDLERS = {
    outcome: (lambda ctx, npc, _o=outcome: _handle_purchase(ctx, npc, _o))
    for outcome in (TalkOutcome.SCRUB, TalkOutcome.CUTOUT, TalkOutcome.RIG)
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
