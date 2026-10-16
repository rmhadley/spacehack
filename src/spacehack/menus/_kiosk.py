"""The Terminus Tech kiosk (doc 102 cluster A / Brief 4.2).

The chrome counter: the fourth service terminal on every spaceport
apron. One-step stock + install — the six t1 pieces, always
stocked, prices riding the port's local band (the dead-zone lesson
lands at the machine that sold the first pieces). The three-check
instrument blocks; the consent modal carries the ruled Before/After
table; removals teach the ratchet. The ONLY loose chrome in the
game is the kiosk's own swap-backs, delivered to armory storage.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..game_context import GameContext


def _kiosk_price(ctx: "GameContext", price: int) -> int:
    """The kiosk's charge: catalog price x the local band (ruled —
    the kiosk itself rides the service multiplier)."""
    from ..chrome import banded_price
    return banded_price(ctx, price)


def _install_rows(ctx: "GameContext"):
    """The stock rows: every t1 piece, its banded price, its bay."""
    from .. import pygame_screen
    from ..data.chrome import list_chrome

    rows = [pygame_screen.ScreenRow("AVAILABLE", selectable=False, header=True)]
    for spec in list_chrome():
        rows.append(pygame_screen.ScreenRow(
            spec.name,
            f"{_kiosk_price(ctx, spec.price)}$ ({spec.bay})",
            f"INSTALL:{spec.id}",
        ))
    return tuple(rows)


def _installed_rows(ctx: "GameContext"):
    """The removal rows: one per worn piece (the teaching surface)."""
    from .. import pygame_screen
    from ..data.chrome import find_chrome

    rows = [pygame_screen.ScreenRow("INSTALLED", selectable=False, header=True)]
    for piece_id in ctx.installed_chrome:
        try:
            rows.append(pygame_screen.ScreenRow(
                find_chrome(piece_id).name,
                "Remove (Burnt Ego stays)",
                f"REMOVE:{piece_id}",
            ))
        except KeyError:
            continue
    return tuple(rows)


def _kiosk_frame(ctx: "GameContext", selected: int):
    """Build one kiosk snapshot (rows + the ego readout body)."""
    from .. import pygame_screen, pygame_ui
    from ..chrome import band, band_name, ego_load, ego_pool

    rows = _install_rows(ctx) + _installed_rows(ctx)
    _pool = ego_pool(ctx)
    body = (
        f"Ego {_pool - ctx.ego_burn}   Burnt Ego {ctx.ego_burn}"
        f"   Install Room {_pool - ego_load(ctx)}",
        f"State: {band_name(band(ctx.ego_burn))}",
        pygame_ui.credits_label(ctx.stats.credits),
    )
    footer = (pygame_ui.modal_hint(
        pygame_ui.NAV_HINT, "ENTER select", "ESC back", pygame_ui.GUIDE_HINT,
    ),)
    return pygame_screen.ScreenFrame(
        title="TERMINUS TECH", body=body, rows=rows, footer=footer,
        selected=selected,
    )


def _deliver_swap_back(ctx: "GameContext", piece_id: str) -> None:
    """The replaced piece lands in armory storage (the only loose
    chrome in the game; sellable at the armory)."""
    from .. import ground_equipment
    from ._armory import _armory_storage

    ground_equipment.add_stored(
        _armory_storage(ctx),
        ground_equipment.StoredGroundEquipment("chrome", piece_id, 0),
        container=ground_equipment.ARMORY_STORAGE,
    )


async def _attempt_install(ctx: "GameContext", piece_id: str) -> None:
    """Checks -> charge gate -> consent -> ratchet install +
    swap-back + the ruled log line (one-step transaction)."""
    from .. import message_log as _ml
    from ..chrome import consent_body, install_check
    from ..data.chrome import find_chrome

    _block = install_check(ctx, piece_id)
    if _block is not None:
        ctx.log.add_colored(_block, _ml.COLOR_PLAYER_ACTION)
        return
    _spec = find_chrome(piece_id)
    _price = _kiosk_price(ctx, _spec.price)
    if ctx.stats.credits < _price:
        ctx.log.add_colored(
            f"You need {_price}$ to install {_spec.name}.",
            _ml.COLOR_PLAYER_ACTION,
        )
        return
    _body, _swap = consent_body(ctx, piece_id)
    if _swap is not None:
        _body = f"{_body}\n{_swap}"
    from ..game_flow import _run_pygame_dungeon_confirm
    _answer = await _run_pygame_dungeon_confirm(
        ctx,
        title=f"Install {_spec.name}?",
        body=_body,
        accept_label="Install",
        cancel_label="Leave",
        caption="spacehack - terminus tech",
    )
    if _answer != "CONFIRM":
        return
    _complete_install(ctx, piece_id, _spec, _price)


def _complete_install(ctx: "GameContext", piece_id: str, spec, price: int) -> None:
    """The post-consent tail: ratchet install, swap-back delivery,
    charge, the ruled log line, and the gate's one-time intro."""
    from .. import message_log as _ml
    from ..chrome import maybe_fire_consortium_intro, ratchet_install

    _replaced = ratchet_install(ctx, piece_id)
    if _replaced:
        _deliver_swap_back(ctx, _replaced)
    ctx.stats.credits -= price
    ctx.log.add_colored(f"{spec.name} installed.", _ml.COLOR_PLAYER_ACTION)
    maybe_fire_consortium_intro(ctx)


def _remove(ctx: "GameContext", piece_id: str) -> None:
    """One removal: the ruled table teaches the ratchet."""
    from .. import message_log as _ml
    from ..chrome import removal_table_lines, uninstall_chrome

    _lines = removal_table_lines(ctx, piece_id)  # BEFORE: the load
    uninstall_chrome(ctx, piece_id)               # still includes it
    for _line in _lines:
        ctx.log.add_colored(_line, _ml.COLOR_PLAYER_ACTION)


async def _run_kiosk_menu(ctx: "GameContext", planet_id: str = "") -> None:
    """Run the kiosk terminal in the shared Pygame window (the
    mechanic loop's shape: apply-and-stay-open on SELECT)."""
    from .. import pygame_screen

    selected = 0
    while True:
        _frame = _kiosk_frame(ctx, selected)
        outcome, action, selected = await pygame_screen.run_for_context(
            ctx.context, _frame, caption="spacehack - terminus tech",
        )
        if outcome == "GUIDE":
            from ..help import _run_help_guide
            await _run_help_guide(ctx)
            continue
        if outcome == "QUIT":
            raise SystemExit
        if outcome == "SELECT" and action:
            if action.startswith("INSTALL:"):
                await _attempt_install(ctx, action.partition(":")[2])
            elif action.startswith("REMOVE:"):
                _remove(ctx, action.partition(":")[2])
            continue
        return  # BACK and everything else
