"""Loadout split-screen modal for the mechanic terminal (doc 56
phase 3): the left pane keeps the STORE/STORAGE parts lists; the
right pane is the fitting-grid editor — cursor + pick/place
(SETTLED 16), installs hand off into the editor's hand (SETTLED 17),
D stores and X sells the held part, and every exit resolves the hand
(SETTLED 12).

The hand is modal-runner LOCAL session state (never module-level,
never serialized): a picked-up entry stays in the owned tuple at its
origin anchor — the tuple is always the whole truth — while a
handed-over part is not in the tuple until dropped. QUIT paths write
no save, so disk state simply predates the session.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .. import ship as ship_module
from ..menus import _grid_editor


_LOADOUT_MODES: tuple[str, ...] = ("STORE", "STORAGE")
_MODE_LABELS = {
    "STORE": "STORE",
    "STORAGE": "STORAGE",
}


@dataclass
class _Hand:
    """The editor's hand: the rich half beside the pure mirror.

    ``source`` is "installed" (picked up from the grid; the entry
    stays in its tuple at ``index``), "storage" (popped from storage),
    or "buy" (charged, not yet placed). ``part`` is the pure layer's
    mirror (size, upkeep, origin anchor or None).
    """

    entry: ship_module.StoredEquipment
    kind: str
    source: str
    part: _grid_editor.HeldPart
    index: int = -1


@dataclass
class _Session:
    """Modal-runner session state (doc 56 phase 3's hand model)."""

    state: _grid_editor.EditorState
    mode: str = "STORE"
    focus: int = 0
    hand: _Hand | None = None


def open_session(ship_spec) -> _Session:
    """A fresh loadout session over the hull's grid."""
    return _Session(
        state=_grid_editor.initial_state(ship_spec.grid_w, ship_spec.grid_h),
    )


def _storage_list(ctx):
    """Return the player's storage list, creating a legacy default if needed."""
    storage = getattr(ctx, "ship_storage", None)
    if storage is None:
        storage = []
        ctx.ship_storage = storage
    return storage


def _loadout_hint(mode: str, on_grid: bool) -> str:
    """Return the modal's controls; the grid pane carries the editor's
    key surface (SETTLED 16)."""
    from .. import pygame_ui

    if on_grid:
        return pygame_ui.modal_hint(
            "B buy", "S storage", "ENTER pick up/drop", "D store held",
            "X sell held", "TAB parts", "ESC back", pygame_ui.GUIDE_HINT,
        )
    action_hint = {
        "STORE": "ENTER buy",
        "STORAGE": "ENTER choose",
    }[mode]
    return pygame_ui.modal_hint(
        "B buy", "S storage", "UP/DOWN navigate", "TAB switch panel",
        action_hint, "ESC back", pygame_ui.GUIDE_HINT,
    )


def _stored_label(stored) -> str:
    """Display label for one stored part (token seam for modules and
    ship weapons — doc 48.7: flown-and-stored weapons are
    quality-bearing)."""
    if stored.item_type == "module":
        from ..ship import module_display_name
        return module_display_name(
            stored.item_id, stored.quality, stored.randart_seed,
        )
    if stored.item_type == "weapon":
        from ..ship import weapon_display_name
        return weapon_display_name(stored.item_id, stored.quality)
    return stored.item_id.replace('_', ' ').title()


def _stored_row(stored, index: int, ctx=None):
    """Build one stored-equipment row, preserving its actual list index."""
    from .. import pygame_split
    from ..ship import module_display_name, weapon_display_name

    detail = _stored_detail(stored, ctx)
    if stored.item_type == "weapon":
        name = weapon_display_name(stored.item_id, stored.quality)
        runs = _weapon_runs(stored.item_id, stored.quality)
    else:
        name = module_display_name(
            stored.item_id, stored.quality, stored.randart_seed,
        )
        runs = _module_runs(stored.item_id, stored.quality, stored.randart_seed)
    return pygame_split.SplitRow(name, "", detail, f"MANAGE_STORED:{index}", runs=runs)


def _with_footprint(spec, detail: str) -> str:
    """One shopping row's detail: the stat/description line, then the
    part's letter-block footprint (ruling 2026-09-30 — the size
    previews while scrolling, before the part enters the editor's
    hand). The ONE composer; both store and storage rows call it."""
    from ..menus._grid_editor import footprint_lines

    return "\n".join((
        detail, *footprint_lines(spec.id, spec.grid_w, spec.grid_h),
    ))


def _stored_detail(stored, ctx=None) -> str:
    """A stored row's detail: the stat line plus the part's footprint
    (ruling 2026-09-30 — the size previews while scrolling, before the
    part ever enters the editor's hand)."""
    from ..data.weapons import find_weapon
    from ..menus._grid_editor import _weapon_detail
    from ..ship import module_detail

    spec = _stored_spec(stored)
    if stored.item_type == "weapon":
        detail = _weapon_detail(
            find_weapon(stored.item_id), ammo=stored.ammo, ctx=ctx,
            quality=stored.quality,
        )
    else:
        detail = module_detail(
            stored.item_id, stored.quality, stored.randart_seed,
        )
    return _with_footprint(spec, detail)


def _module_runs(module_id: str, quality: int, randart_seed) -> tuple | None:
    """Runs colouring one module row's label at its tier (the randart
    name counts as legendary)."""
    from ..data.quality import LEGENDARY_QUALITY, quality_color
    from ..ship import module_display_name

    _tier = LEGENDARY_QUALITY if randart_seed is not None else quality
    _color = quality_color(_tier)
    if _color is None:
        return None
    return ((module_display_name(module_id, quality, randart_seed), _color),)


def _weapon_runs(weapon_id: str, quality: int) -> tuple | None:
    """Runs colouring one weapon row's label at its tier (the module
    twin — base reads plain, tokens carry their tier colour)."""
    from ..data.quality import quality_color
    from ..ship import weapon_display_name

    _color = quality_color(quality)
    if _color is None:
        return None
    return ((weapon_display_name(weapon_id, quality), _color),)


def _stored_spec(stored):
    """Return the catalog specification for one stored equipment entry."""
    from ..data.modules import find_module
    from ..data.weapons import find_weapon

    if stored.item_type == "weapon":
        return find_weapon(stored.item_id)
    if stored.item_type == "module":
        return find_module(stored.item_id)
    raise ValueError(f"Unknown stored equipment type: {stored.item_type!r}")


def _storage_rows(ctx):
    """Build storage rows for hand-off installation or sale."""
    from .. import pygame_split

    rows = [pygame_split.section_header("OWNED EQUIPMENT")]
    valid_rows = []
    for index, stored in enumerate(_storage_list(ctx)):
        try:
            valid_rows.append(_stored_row(stored, index, ctx))
        except (AttributeError, KeyError, TypeError, ValueError):
            continue
    if valid_rows:
        rows.extend(valid_rows)
    else:
        rows.append(
            pygame_split.SplitRow(
                "[empty]", "", "No equipment is currently held in storage.", "", False,
            )
        )
    return tuple(rows)


def _market_rows(weapon_ids, module_ids):
    """Build catalog rows for the current mechanic's parts inventory."""
    from .. import pygame_split
    from .. import pygame_ui
    from ..data.modules import find_module
    from ..data.weapons import find_weapon
    from ..menus._grid_editor import _weapon_detail

    rows = [pygame_split.section_header("WEAPONS")]
    rows.extend(
        pygame_split.SplitRow(
            spec.name,
            pygame_ui.price_cell(spec.price),
            _with_footprint(spec, _weapon_detail(spec)),
            f"BUY_WEAPON:{spec.id}",
        )
        for spec in sorted((find_weapon(item_id) for item_id in weapon_ids), key=lambda item: item.price)
    )
    rows.append(pygame_split.section_header("MODULES"))
    rows.extend(
        pygame_split.SplitRow(
            spec.name,
            pygame_ui.price_cell(spec.price),
            _with_footprint(spec, spec.description),
            f"BUY_MODULE:{spec.id}",
        )
        for spec in sorted((find_module(item_id) for item_id in module_ids), key=lambda item: item.price)
    )
    return tuple(rows)


def _store_rows_for_mode(weapon_ids, module_ids):
    """Resolve STORE-mode rows, defaulting to the full catalog."""
    if weapon_ids is None or module_ids is None:
        from ..data.modules import list_modules
        from ..data.weapons import list_weapons
        weapon_ids = tuple(item.id for item in list_weapons())
        module_ids = tuple(item.id for item in list_modules())
    return _market_rows(weapon_ids, module_ids)


# ---------------------------------------------------------------------------
# The grid pane + the POWER footer
# ---------------------------------------------------------------------------


def _as_if_bonuses(ctx, session) -> list[int]:
    """The as-if-fitted effective power list: every installed module
    plus the hand's exactly once (picked-up parts are already in the
    tuple; handed-over parts join until dropped or returned)."""
    owned = ctx.player_owned_ship
    bonuses = [
        ship_module.effective_upkeep(entry)
        for entry in (getattr(owned, "modules", ()) or ())
    ]
    hand = session.hand
    if hand is not None and hand.source != "installed":
        bonuses.append(hand.part.upkeep)
    return bonuses


def _power_inputs(ctx, session) -> tuple[int, list[int]]:
    """``(base_gen, as-if bonuses)`` — the footer's and ghost's input."""
    owned = ctx.player_owned_ship
    ship_spec = ship_module.find_ship(owned.ship_id)
    return getattr(ship_spec, "base_power_gen", 3), _as_if_bonuses(ctx, session)


def _installed_key(hand: _Hand | None) -> str | None:
    """The held picked-up entry's tuple key (its cells vacate)."""
    if hand is not None and hand.source == "installed":
        return f"{hand.kind}:{hand.index}"
    return None


def _hover_detail(session, pieces) -> str:
    """The readout on the pane's first row: the held part while
    holding, else whatever sits under the cursor."""
    hand = session.hand
    if hand is not None:
        return _grid_editor._entry_detail(hand.entry)
    hovered = _grid_editor.piece_at(pieces, session.state.cursor)
    return hovered.detail if hovered is not None else ""


def _grid_pane_rows(ctx, session) -> tuple:
    """The right pane: the letter grid with the cursor and held ghost
    painted in (SETTLED 16). The hovered/held part's readout rides the
    FIRST row's detail — the split's pinned-detail zone reads row 0, so
    the tooltip shows at the pane's bottom while the grid is focused
    (playtest 2026-09-30)."""
    from .. import pygame_split

    owned = ctx.player_owned_ship
    ship_spec = ship_module.find_ship(owned.ship_id)
    pieces = _grid_editor.pieces_for(owned, omit_key=_installed_key(session.hand))
    occupied = ship_module.occupied_cells(
        owned, ship_spec.grid_w, ship_spec.grid_h,
    )
    base_gen, bonuses = _power_inputs(ctx, session)
    hand = session.hand
    held_letter = _grid_editor.letter(hand.entry.item_id) if hand else ""
    lines = _grid_editor.pane_rows(
        session.state, pieces, occupied, base_gen, bonuses,
        held_letter=held_letter,
    )
    hover = _hover_detail(session, pieces)
    return tuple(
        pygame_split.SplitRow(
            text, "", hover if index == 0 else "", "",
            selectable=False, runs=runs,
        )
        for index, (text, runs) in enumerate(lines)
    )


def _pygame_loadout_frame(
    ctx,
    session: _Session,
    planet_id: str = "",
    weapon_ids: tuple[str, ...] | None = None,
    module_ids: tuple[str, ...] | None = None,
):
    """Build one presentation-only loadout frame (grid right pane)."""
    from .. import pygame_split
    from .. import pygame_ui

    owned = ctx.player_owned_ship
    if owned is None:
        return pygame_split.SplitFrame(
            pygame_ui.terminal_title("MECHANIC", "SHIP LOADOUT"),
            "Store", "My Ship", (), (), "", "", pygame_split.SPLIT_SHOP_HINT,
        )
    if session.mode not in _LOADOUT_MODES:
        raise ValueError(f"Unknown loadout mode: {session.mode!r}")
    if session.mode == "STORE":
        left = _store_rows_for_mode(weapon_ids, module_ids)
    else:
        left = _storage_rows(ctx)
    base_gen, bonuses = _power_inputs(ctx, session)
    return pygame_split.SplitFrame(
        title=pygame_ui.terminal_title("MECHANIC", "SHIP LOADOUT"),
        left_label=_MODE_LABELS[session.mode].title(),
        right_label="My Ship",
        left_rows=left,
        right_rows=_grid_pane_rows(ctx, session),
        footer_left=pygame_ui.credits_label(ctx.stats.credits),
        footer_right=_grid_editor.power_footer(base_gen, bonuses),
        hint=_loadout_hint(session.mode, session.focus == 1),
        left_tabs=("[B]uy", "[S]torage"),
        active_left_tab=0 if session.mode == "STORE" else 1,
        focus=session.focus,
        grid_pane=True,
        grid_holding=session.hand is not None,
    )


# ---------------------------------------------------------------------------
# Refusals and logs (approved strings, doc 56)
# ---------------------------------------------------------------------------


def _install_refusal_text(reason: str, stored) -> str:
    """One ``install_refusal``/drop reason to its player-facing line
    (doc 56 phase-2 approved strings; the reason->string dispatch is
    the phase-2 REVIEW minor-1 conversion)."""
    label = _stored_label(stored)
    table = {
        ship_module.INSTALL_REFUSAL_ROOM: f"No room on the grid for {label}.",
        ship_module.INSTALL_REFUSAL_POWER: (
            f"{label} needs more power than the ship generates."
        ),
    }
    return table.get(reason, "That stored item is not valid equipment.")


def _installed_item_label(kind: str, item) -> tuple[str, str, int]:
    """Return (chooser body, sell id, quality) for one installed item."""
    if kind == "weapon":
        from ..ship import weapon_display_name
        return (
            weapon_display_name(item.item_id, item.quality),
            item.item_id, item.quality,
        )
    from ..ship import module_display_name
    return (
        module_display_name(
            item.item_id, item.quality, item.randart_seed,
        ),
        item.item_id, item.quality,
    )


def _log_removal_refusal(ctx, owned, kind: str, slot: int) -> None:
    """SETTLED 3: removal through the power gate, refused aloud."""
    entry = (owned.weapons if kind == "weapon" else owned.modules)[slot]
    ctx.log.add(
        f"Removing {_installed_item_label(kind, entry)[0]} would leave "
        "the ship short on power."
    )


def _log_installed(ctx, stored) -> None:
    """``"Installed Overclocked Shield Mk. 2 from storage."`` with the
    tiered name coloured (the armory _log_equipped twin)."""
    from .. import message_log
    from ..data.quality import quality_mark

    _msg, _runs = message_log.with_runs(
        "Installed ", quality_mark(_stored_label(stored), stored.quality),
        " from storage.",
    )
    ctx.log.add(_msg, runs=_runs)


def _log_sold(ctx, stored, price: int) -> None:
    """``"Sold Medium Laser for 60$."`` with the tiered name coloured."""
    from .. import message_log
    from ..data.quality import quality_mark

    _msg, _runs = message_log.with_runs(
        "Sold ", quality_mark(_stored_label(stored), stored.quality),
        f" for {price}$.",
    )
    ctx.log.add(_msg, runs=_runs)


# ---------------------------------------------------------------------------
# The editor's hand — pick/place, D/X, hand-off, and every exit
# ---------------------------------------------------------------------------


def _hand_upkeep(entry, kind: str) -> int:
    """Weapons draw no upkeep (doctrine: guns cost power when fired)."""
    return 0 if kind == "weapon" else ship_module.effective_upkeep(entry)


def _release_hand(session) -> None:
    session.hand = None
    session.state = _grid_editor.release(session.state)


def _take_hand(ctx, session, entry, kind: str, source: str, index: int = -1) -> None:
    """Put a part in the hand (shared by pickup and both hand-offs);
    the editor pane takes focus (SETTLED 17 — the part is placed on
    the grid)."""
    spec = _stored_spec(entry)
    part = _grid_editor.HeldPart(
        w=spec.grid_w, h=spec.grid_h,
        upkeep=_hand_upkeep(entry, kind),
        origin=(entry.grid_x, entry.grid_y) if source == "installed" else None,
    )
    session.hand = _Hand(
        entry=entry, kind=kind, source=source, part=part, index=index,
    )
    session.state = _grid_editor.hold_part(session.state, part)
    session.focus = 1


def _resolve_hand(ctx, session) -> None:
    """SETTLED 12: the hand resolves at every pane switch and exit —
    snap-back for a picked-up part (still installed at its origin:
    nothing to move), storage for a handed-over part (never-fitted
    storage neutrality: storing it cannot trip the gate)."""
    hand = session.hand
    if hand is None:
        return
    if hand.source != "installed":
        _storage_list(ctx).append(hand.entry)
        ctx.log.add("Moved equipment to storage.")
    _release_hand(session)


def _drop_held(ctx, session) -> None:
    """ENTER while holding: place the part at the cursor — the red
    ghost is the refusal (SETTLED 16/17); a refused drop speaks the
    approved refusal string."""
    owned = ctx.player_owned_ship
    ship_spec = ship_module.find_ship(owned.ship_id)
    hand = session.hand
    occupied = ship_module.occupied_cells(
        owned, ship_spec.grid_w, ship_spec.grid_h,
    )
    base_gen, bonuses = _power_inputs(ctx, session)
    reason = _grid_editor.drop_refusal(
        session.state, occupied, base_gen, bonuses,
    )
    if reason is not None:
        ctx.log.add(_install_refusal_text(reason, hand.entry))
        return
    x, y = session.state.cursor
    placed = replace(hand.entry, grid_x=x, grid_y=y)
    if hand.source == "installed":
        _replace_installed(owned, hand, placed)
    else:
        if hand.kind == "weapon":
            ship_module._install_weapon(owned, placed, ctx)
            ship_module.clamp_installed_magazine(owned, hand.entry, ctx)
        else:
            ship_module._install_module(owned, placed)
        if hand.source == "storage":
            _log_installed(ctx, hand.entry)
    _release_hand(session)


def _replace_installed(owned, hand: _Hand, placed) -> None:
    """Rearranging a picked-up part re-anchors it in place — no tuple
    insertion, no re-index (rearrangement never trips the gate)."""
    entries = owned.weapons if hand.kind == "weapon" else owned.modules
    updated = tuple(
        placed if index == hand.index else entry
        for index, entry in enumerate(entries)
    )
    if hand.kind == "weapon":
        owned.weapons = updated
    else:
        owned.modules = updated


def _pick_up(ctx, session) -> None:
    """ENTER empty-handed: take the piece under the cursor; the cursor
    snaps to its anchor so the ghost starts where it was."""
    owned = ctx.player_owned_ship
    piece = _grid_editor.piece_at(
        _grid_editor.pieces_for(owned), session.state.cursor,
    )
    if piece is None:
        return
    kind, index = piece.key.split(":")
    entries = owned.weapons if kind == "weapon" else owned.modules
    _take_hand(
        ctx, session, entries[int(index)], kind, "installed", int(index),
    )


def _store_held(ctx, session) -> None:
    """D while holding: store the part (SETTLED 3 — removing the
    funding generator refuses)."""
    hand = session.hand
    owned = ctx.player_owned_ship
    ship_spec = ship_module.find_ship(owned.ship_id)
    if hand.source == "installed":
        if ship_module.removal_trips_power(
            owned, ship_spec, hand.kind, hand.index, ctx,
        ):
            _log_removal_refusal(ctx, owned, hand.kind, hand.index)
            return
        if hand.kind == "weapon":
            ship_module.store_weapon(owned, _storage_list(ctx), hand.index, ctx)
        else:
            ship_module.store_module(owned, _storage_list(ctx), hand.index)
    else:
        _storage_list(ctx).append(hand.entry)
    ctx.log.add("Moved equipment to storage.")
    _release_hand(session)


async def _sell_held(ctx, session) -> None:
    """X while holding: sell the part through the removal gate, with
    the price confirm (SETTLED 16)."""
    hand = session.hand
    owned = ctx.player_owned_ship
    ship_spec = ship_module.find_ship(owned.ship_id)
    price = ship_module._sell_price(
        hand.kind, hand.entry.item_id, hand.entry.quality,
    )
    if hand.source == "installed" and ship_module.removal_trips_power(
        owned, ship_spec, hand.kind, hand.index, ctx,
    ):
        _log_removal_refusal(ctx, owned, hand.kind, hand.index)
        return
    from .. import pygame_story
    confirmed = await pygame_story.confirm(
        ctx,
        title="SELL EQUIPMENT",
        body=_stored_label(hand.entry),
        accept_label=f"Sell for {price}$",
        cancel_label="Keep",
        caption="spacehack - sell equipment",
    )
    if confirmed == "QUIT":
        raise SystemExit
    if confirmed != "CONFIRM":
        return
    if hand.source == "installed":
        if hand.kind == "weapon":
            ship_module._remove_weapon(owned, hand.index, ctx)
        else:
            ship_module._remove_module(owned, hand.index)
    ctx.stats.credits += price
    _log_sold(ctx, hand.entry, price)
    _release_hand(session)


# ---------------------------------------------------------------------------
# Left-pane actions — buys and stored parts hand off into the editor
# ---------------------------------------------------------------------------


def _purchase_spec(item_type: str, item_id: str):
    """Return the catalog specification for a purchasable ship part."""
    from ..data.modules import find_module
    from ..data.weapons import find_weapon

    if item_type == "WEAPON":
        return find_weapon(item_id)
    if item_type == "MODULE":
        return find_module(item_id)
    raise ValueError(f"Unknown purchase type: {item_type!r}")


def _apply_stored_handoff(ctx, session, storage_index: int) -> None:
    """SETTLED 17: a stored part pops into the editor's hand — no
    room/power pre-check (the red ghost is the refusal)."""
    storage = _storage_list(ctx)
    if not 0 <= storage_index < len(storage):
        ctx.log.add("That storage entry is no longer available.")
        return
    if session.hand is not None:
        ctx.log.add("You are already holding a part.")
        return
    stored = storage[storage_index]
    try:
        _stored_spec(stored)
    except (AttributeError, KeyError, TypeError, ValueError):
        ctx.log.add("That storage entry is no longer available.")
        return
    storage.pop(storage_index)
    _take_hand(ctx, session, stored, stored.item_type, "storage")


async def _choose_stored_action(ctx, session, action: str) -> str:
    """Ask whether a stored part should be installed or sold."""
    storage_index = int(action.split(":", 1)[1])
    storage = _storage_list(ctx)
    if not 0 <= storage_index < len(storage):
        return "__BACK__"
    stored = storage[storage_index]
    try:
        sell_price = ship_module._sell_price(
            stored.item_type, stored.item_id, stored.quality,
        )
    except (AttributeError, KeyError, TypeError, ValueError):
        return "__BACK__"
    from .. import pygame_story
    return await pygame_story.choose(
        ctx,
        title="STORED EQUIPMENT",
        body=_stored_label(stored),
        options=(
            ("Install", f"INSTALL_STORED:{storage_index}"),
            (f"Sell for {sell_price}$", f"SELL_STORED:{storage_index}"),
        ),
        caption="spacehack - stored equipment",
        compact=True,
    )


async def _apply_manage_stored_item(ctx, session, action: str) -> None:
    """Open the Install/Sell chooser and apply its selected action."""
    chosen = await _choose_stored_action(ctx, session, action)
    if chosen in {None, "__BACK__", "__GUIDE__"}:
        return
    if chosen == "__QUIT__":
        raise SystemExit
    if chosen.startswith("INSTALL_STORED:"):
        _apply_stored_handoff(ctx, session, int(chosen.split(":", 1)[1]))
    elif chosen.startswith("SELL_STORED:"):
        _apply_sell_stored(ctx, session, chosen)


def _apply_sell_stored(ctx, _session, action: str) -> None:
    """Sell one stored weapon or module and return its purchase value share."""
    storage_index = int(action.split(":", 1)[1])
    storage = _storage_list(ctx)
    if not 0 <= storage_index < len(storage):
        ctx.log.add("That storage entry is no longer available.")
        return
    stored = storage[storage_index]
    try:
        sell_price = ship_module._sell_price(
            stored.item_type, stored.item_id, stored.quality,
        )
    except (AttributeError, KeyError, TypeError, ValueError):
        ctx.log.add("That storage entry is no longer available.")
        return
    if sell_price <= 0:
        ctx.log.add("That storage entry is no longer available.")
        return
    storage.pop(storage_index)
    ctx.stats.credits += sell_price
    _log_sold(ctx, stored, sell_price)


def _apply_purchase(ctx, session, item_type: str, item_id: str, destination: str) -> None:
    """Complete a purchase after the player chooses its destination.

    Install hands the part into the editor (SETTLED 17): AFFORDABILITY
    ONLY is checked before the charge — no room/power pre-check, the
    red ghost is the placement refusal, and a bought part that cannot
    place auto-returns to storage at session end (never destroyed).
    """
    spec = _purchase_spec(item_type, item_id)
    if ctx.stats.credits < spec.price:
        ctx.log.add(f"You need {spec.price}$ to buy {spec.name}.")
        return
    kind = "weapon" if item_type == "WEAPON" else "module"
    entry = ship_module.StoredEquipment(kind, item_id)
    if destination == "INSTALL":
        if session.hand is not None:
            ctx.log.add("You are already holding a part.")
            return
        ctx.stats.credits -= spec.price
        _take_hand(ctx, session, entry, kind, "buy")
        ctx.log.add(f"Bought {spec.name} for {spec.price}$.")
    else:
        ctx.stats.credits -= spec.price
        _storage_list(ctx).append(entry)
        ctx.log.add(f"Stored {spec.name} for {spec.price}$.")


async def _choose_purchase_action(ctx, item_type: str, item_id: str) -> str:
    """Ask whether a purchased part should be installed or stored."""
    spec = _purchase_spec(item_type, item_id)
    from .. import pygame_story

    return await pygame_story.choose(
        ctx,
        title="BUY EQUIPMENT",
        body=spec.name,
        options=(
            ("Install", f"BUY_INSTALL_{item_type}:{item_id}"),
            ("Store", f"BUY_STORE_{item_type}:{item_id}"),
        ),
        caption="spacehack - buy equipment",
        compact=True,
    )


async def _apply_buy(ctx, session, action: str) -> None:
    """Validate funds, open the destination chooser, and complete a buy."""
    action_type, item_id = action.split(":", 1)
    item_type = action_type.removeprefix("BUY_")
    spec = _purchase_spec(item_type, item_id)
    if ctx.stats.credits < spec.price:
        ctx.log.add(f"You need {spec.price}$ to buy {spec.name}.")
        return
    chosen = await _choose_purchase_action(ctx, item_type, item_id)
    if chosen in {None, "__BACK__", "__GUIDE__"}:
        return
    if chosen == "__QUIT__":
        raise SystemExit
    if chosen.startswith(f"BUY_INSTALL_{item_type}:"):
        _apply_purchase(ctx, session, item_type, item_id, "INSTALL")
    elif chosen.startswith(f"BUY_STORE_{item_type}:"):
        _apply_purchase(ctx, session, item_type, item_id, "STORE")


# ---------------------------------------------------------------------------
# Action routing (the GRID: key surface rides the same keep-open path)
# ---------------------------------------------------------------------------


async def _apply_grid_move(ctx, session, action: str) -> None:
    _dx, _dy = action.rsplit(":", 2)[1:]
    session.state = _grid_editor.move_cursor(
        session.state, int(_dx), int(_dy),
    )


async def _apply_grid_enter(ctx, session, _action: str) -> None:
    if session.hand is not None:
        _drop_held(ctx, session)
    else:
        _pick_up(ctx, session)


async def _apply_grid_store(ctx, session, _action: str) -> None:
    if session.hand is not None:
        _store_held(ctx, session)


async def _apply_grid_sell(ctx, session, _action: str) -> None:
    if session.hand is not None:
        await _sell_held(ctx, session)


async def _apply_grid_esc(ctx, session, _action: str) -> None:
    """Two-stage ESC, first stage: the hand returns to where it was."""
    _resolve_hand(ctx, session)


async def _apply_grid_tab(ctx, session, _action: str) -> None:
    """TAB off the grid pane: resolve the hand, then the pane flips."""
    _resolve_hand(ctx, session)
    session.focus = 0


_GRID_ACTION_HANDLERS = {
    "GRID:MOVE": _apply_grid_move,
    "GRID:ENTER": _apply_grid_enter,
    "GRID:STORE": _apply_grid_store,
    "GRID:SELL": _apply_grid_sell,
    "GRID:ESC": _apply_grid_esc,
    "GRID:TAB": _apply_grid_tab,
}

_LOADOUT_ACTION_HANDLERS = (
    ("BUY_WEAPON:", _apply_buy),
    ("BUY_MODULE:", _apply_buy),
    ("MANAGE_STORED:", _apply_manage_stored_item),
    ("SELL_STORED:", _apply_sell_stored),
)


async def _apply_pygame_loadout_action(
    ctx, session: _Session, action: str, focus: int, selected: int, planet_id: str,
) -> bool:
    """Apply one loadout action using table-driven routing."""
    if not action:
        return True
    if action.startswith("GRID:"):
        verb = ":".join(action.split(":", 2)[:2])
        handler = _GRID_ACTION_HANDLERS.get(verb)
        if handler is None:
            raise ValueError(f"Unknown grid action: {action!r}")
        await handler(ctx, session, action)
        return True
    handler = next(
        (handler for prefix, handler in _LOADOUT_ACTION_HANDLERS if action.startswith(prefix)),
        None,
    )
    if handler is None:
        raise ValueError(f"Unknown loadout action: {action!r}")
    await handler(ctx, session, action)
    return True


def _resolve_loadout_catalog(ctx, planet_id: str):
    """Resolve the sorted weapon/module specs for the loadout modal."""
    from ..data.modules import find_module as _fm, list_modules as _lm
    from ..data.planets import resolve_mech_inventory
    from ..data.weapons import find_weapon as _fw, list_weapons as _lw
    from ..time import month_index

    if planet_id:
        weapon_ids, module_ids = resolve_mech_inventory(planet_id, month_index(ctx))
        weapons = tuple(sorted((_fw(i) for i in weapon_ids), key=lambda item: item.price))
        modules = tuple(sorted((_fm(i) for i in module_ids), key=lambda item: item.price))
    else:
        weapons = tuple(sorted(_lw(), key=lambda item: item.price))
        modules = tuple(sorted(_lm(), key=lambda item: item.price))
    return weapons, modules


async def _run_loadout_menu(ctx, planet_id: str = "") -> None:
    """Show the loadout terminal in the shared Pygame window."""
    owned = ctx.player_owned_ship
    if owned is None:
        ctx.log.add("You need a ship to manage its loadout.")
        return

    weapons, modules = _resolve_loadout_catalog(ctx, planet_id)
    session = open_session(ship_module.find_ship(owned.ship_id))

    def build_frame():
        return _pygame_loadout_frame(
            ctx, session, planet_id,
            tuple(item.id for item in weapons),
            tuple(item.id for item in modules),
        )

    async def apply_action(action, focus, selected):
        session.focus = focus
        if action.startswith("MODE:"):
            requested = action.split(":", 1)[1]
            if requested in _LOADOUT_MODES:
                session.mode = requested
            return True
        return await _apply_pygame_loadout_action(
            ctx, session, action, focus, selected, planet_id,
        )

    from .. import pygame_split
    outcome = await pygame_split.run_interactive(
        ctx,
        build_frame,
        apply_action,
        caption="spacehack - ship loadout",
    )
    if outcome == "BACK":
        # Every exit resolves the hand (SETTLED 12). Two-stage ESC
        # empties it first, so this is the defensive leg; QUIT writes
        # no save — disk state simply predates the session.
        _resolve_hand(ctx, session)
