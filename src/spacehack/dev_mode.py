"""Dev-mode overrides for playtesting.

When the ``SPACEHACK_DEV`` environment variable is set, the player
starts with a super-powered frigate, maxed modules, 999,999 credits,
two kinetic rifles, and the best available armor in every slot. Call
:func:`apply_dev_overrides` and :func:`apply_dev_ground_loadout` during
new-game setup so the overrides are in place before the game loop starts.

Extracted from ``__main__.py`` to keep the entry point clean and
make dev-mode easy to extend (debug overlay, god-mode toggle, etc.)
"""

from __future__ import annotations

from typing import Any

from . import ship as ship_module
from . import ui
from .input_helpers import Outcome, _run_pick
from .data.ground_armor import list_ground_armor


_DEV_FACTION_OPTIONS = (
    ("militia", "Militia", "Order, procedure, and a sanctioned breach."),
    ("merchants", "Merchants", "Routes, leverage, and a quiet way through."),
    ("bar", "Free Captains", "Rumors, favors, and the outlaw route."),
    ("lab", "Research Lab", "Evidence, analysis, and dangerous questions."),
)
_DEV_FACTION_LABELS = {option[0]: option[1] for option in _DEV_FACTION_OPTIONS}


def main_quest_faction_menu() -> ui.MenuScreen:
    """Return the faction picker used by the Act 0 dev shortcut."""
    return ui.MenuScreen(
        title="Choose Act 0 Faction",
        instruction="ARROW KEYS or J/K navigate - ENTER select - ESC cancel",
        options=tuple(
            (faction_id, label)
            for faction_id, label, _ in _DEV_FACTION_OPTIONS
        ),
        descriptions={
            faction_id: description
            for faction_id, _, description in _DEV_FACTION_OPTIONS
        },
    )


def _dev_faction_label(faction_id: str) -> str:
    """Return the display label for a registered developer faction."""
    return _DEV_FACTION_LABELS[faction_id]


def _pygame_faction_frames(menu: ui.MenuScreen):
    """Build the shared fixed-layout frames for the dev faction picker."""
    from . import pygame_menu

    items = tuple(
        pygame_menu.MenuItem(
            label=label,
            description=menu.descriptions.get(faction_id, ""),
            action=faction_id,
        )
        for faction_id, label in menu.options
    )
    return tuple(
        pygame_menu.MenuFrame(
            title=menu.title.upper(),
            body="Choose the faction whose Act 0 path you want to test.",
            items=items,
            hints=(menu.instruction,),
            selected=selected,
        )
        for selected in range(len(items))
    )


def _run_pygame_faction_pick(
    context, menu: ui.MenuScreen,
) -> tuple[Outcome, str | None] | None:
    """Run the dev faction picker in Pygame, or return None for fallback."""
    from . import pygame_menu

    frames = _pygame_faction_frames(menu)
    if not frames:
        return None
    while True:
        outcome, action, _selected = pygame_menu.run_for_context(
            context,
            frames,
            caption="spacehack - choose act 0 faction",
        )
        if outcome == "GUIDE":
            continue
        if outcome == "QUIT":
            return Outcome.QUIT, None
        if outcome == "BACK":
            return Outcome.BACK, None
        if outcome == "SELECT":
            valid_ids = {faction_id for faction_id, _label in menu.options}
            if action in valid_ids:
                return Outcome.CONFIRM, action
        return None


def choose_main_quest_faction(context) -> tuple[Outcome, str | None]:
    """Run the Act 0 faction picker in the shared Pygame window."""
    result = _run_pygame_faction_pick(context, main_quest_faction_menu())
    if result is None:
        raise RuntimeError("Developer faction picker returned no outcome")
    return result


_GROUND_ARMOR_SLOTS = ("head", "body", "hands", "legs", "feet")


def _best_ground_armor() -> dict[str, str]:
    """Return the strongest registered armor id for every armor slot."""
    _by_slot: dict[str, list] = {slot: [] for slot in _GROUND_ARMOR_SLOTS}
    for _armor in list_ground_armor():
        if _armor.slot in _by_slot:
            _by_slot[_armor.slot].append(_armor)
    return {
        _slot: max(
            _items,
            key=lambda _item: (_item.defense, _item.tech_level, _item.price),
        ).id
        for _slot, _items in _by_slot.items()
        if _items
    }


def _dev_ground_loadout() -> tuple[list[str], dict[str, str]]:
    """Return the standard developer starting ground loadout."""
    return ["kinetic_rifle", "kinetic_rifle"], _best_ground_armor()


def apply_dev_ground_loadout(ctx) -> None:
    """Equip developer ground weapons and armor when dev mode is enabled."""
    import os as _os

    if not _os.environ.get("SPACEHACK_DEV"):
        return
    ctx.equipped_ground_weapons, ctx.equipped_ground_armor = _dev_ground_loadout()
    ctx.log.add("[DEV MODE] Two kinetic rifles + best armor equipped.")


def advance_main_quest(ctx, faction_id: str) -> None:
    """Put Act 0 immediately before the Mars door-opening interaction.

    ``faction_id`` mirrors the normal Act 0 lock-in choice, so post-prison
    dialogue and faction-gated objectives behave like a real run. The
    caller must gate this action behind ``SPACEHACK_DEV``.
    """
    if faction_id not in _DEV_FACTION_LABELS:
        raise ValueError(f"Unknown developer faction: {faction_id}")
    if ctx.main_quest_chain and ctx.main_quest_chain != faction_id:
        raise ValueError("Developer faction cannot replace an existing quest chain")
    _progress = ctx.main_quest_progress
    ctx.main_quest_chain = faction_id
    ctx.main_quest_backing.add(faction_id)
    _progress.update({
        "prologue_signal": "completed",
        "prologue_mars_unlocked": "completed",
        "prologue_mars_entrance": "completed",
        "prologue_seek_help": "completed",
    })
    if _progress.get("prologue_open") != "completed":
        _progress["prologue_open"] = "active"
    ctx.log.add(
        f"[DEV MODE] Act 0 skipped as {_dev_faction_label(faction_id)} - "
        "the Mars door can now be opened."
    )


def apply_dev_overrides(
    starter_ship: Any,
    starter_entity: Any,
    player_owned_ship: Any,
    stats: Any,
    log: Any,
) -> tuple[Any, Any, Any]:
    """If ``SPACEHACK_DEV`` is set, grant a super-powered frigate.

    Mutates ``stats`` and ``log`` in-place (they're mutable objects)
    and returns ``(starter_ship, starter_entity, player_owned_ship)``
    with the frigate override applied. If the env var is not set,
    returns the same objects unchanged.

    Call this right before :class:`GameContext` construction so the
    overridden values flow into ctx without the caller needing to
    know whether dev mode is active.
    """
    import os as _os

    if not _os.environ.get("SPACEHACK_DEV"):
        return starter_ship, starter_entity, player_owned_ship

    frigate = ship_module.find_ship("frigate")
    starter_ship = frigate
    starter_entity.char = frigate.char
    starter_entity.fg = frigate.fg
    starter_entity.name = f"Your Ship: {frigate.name}"
    starter_entity.ship_id = frigate.id
    player_owned_ship = ship_module.OwnedShip(
        ship_id="frigate",
        weapons=(
            "plasma_cannon", "plasma_cannon", "plasma_cannon", "plasma_cannon",
            "heavy_missile", "heavy_missile", "heavy_missile", "heavy_missile",
        ),
        modules=(
            "reactor_mk4", "shield_mk4", "shield_recharger",
            "targeting_mk4", "gyro_mk4", "armor_mk4",
        ),
        fuel=999,
    )
    stats.credits = 999999
    log.add("[DEV MODE] Super-powered frigate + 999,999 credits.")
    return starter_ship, starter_entity, player_owned_ship
