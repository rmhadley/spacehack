"""The Terminus Tech kiosk (doc 102 cluster A / Brief 4.2).

The chrome counter: the fourth service terminal on every spaceport
apron. One-step stock + install — the six t1 pieces, always
stocked, prices riding the port's local band (the dead-zone lesson
lands at the machine that sold the first pieces). The SPLIT family
(the armory's shape, revised at playtest 2026-10-16): left pane the
stock, right pane the installed with removal, TAB between panes,
the selected row's ruled detail line pinned under the focused
pane. The three-check instrument blocks; the consent modal carries
the ruled Before/After table; removals teach the ratchet. The ONLY
loose chrome in the game is the kiosk's own swap-backs, delivered
to armory storage.
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


def _stock_rows(ctx: "GameContext") -> tuple:
    """The left pane: every catalog piece, its banded price + bay,
    its ruled detail line."""
    from .. import pygame_split
    from ..data.chrome import list_chrome

    return tuple(
        pygame_split.SplitRow(
            spec.name,
            f"{_kiosk_price(ctx, spec.price)}$ ({spec.bay})",
            spec.detail,
            f"INSTALL:{spec.id}",
        )
        for spec in list_chrome()
    )


def _installed_rows(ctx: "GameContext") -> tuple:
    """The right pane: one removal row per worn piece (the teaching
    surface), the same detail line."""
    from .. import pygame_split
    from ..data.chrome import find_chrome

    rows = []
    for piece_id in ctx.installed_chrome:
        try:
            _spec = find_chrome(piece_id)
        except KeyError:
            continue
        rows.append(pygame_split.SplitRow(
            _spec.name,
            "Remove",
            _spec.detail,
            f"REMOVE:{piece_id}",
        ))
    if not rows:
        rows.append(pygame_split.SplitRow(
            "[empty]", "", "Nothing installed.", "",
            selectable=False,
        ))
    return tuple(rows)


def _kiosk_frame(ctx: "GameContext", focus: int, selected: int):
    """Build one kiosk snapshot (the armory frame's shape)."""
    from .. import pygame_split, pygame_ui
    from ..chrome import band, band_name, ego_load, ego_pool

    _pool = ego_pool(ctx)
    return pygame_split.SplitFrame(
        "TERMINUS TECH", "Available", "Installed",
        _stock_rows(ctx), _installed_rows(ctx),
        f"Ego {_pool - ctx.ego_burn}  Burnt Ego {ctx.ego_burn}"
        f"  Install Room {_pool - ego_load(ctx)}",
        f"State: {band_name(band(ctx.ego_burn))}   "
        + pygame_ui.credits_label(ctx.stats.credits),
        pygame_ui.modal_hint(
            "UP/DOWN navigate", "TAB switch panel", "ENTER select",
            "ESC back", pygame_ui.GUIDE_HINT,
        ),
        focus=focus, selected=selected,
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


def _complete_install(
    ctx: "GameContext", piece_id: str, spec, price: int,
) -> None:
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
    armory's split loop: apply-and-stay-open on SELECT, TAB flips
    panes inside the family)."""
    from .. import pygame_split

    def build_frame():
        return _kiosk_frame(ctx, 0, 0)

    async def apply_action(action, focus, selected):
        if action.startswith("INSTALL:"):
            await _attempt_install(ctx, action.partition(":")[2])
        elif action.startswith("REMOVE:"):
            _remove(ctx, action.partition(":")[2])
        return True

    await pygame_split.run_interactive(
        ctx, build_frame, apply_action, caption="spacehack - terminus tech",
    )
