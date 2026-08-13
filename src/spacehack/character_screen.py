"""Character screen — level, XP, skills, traits, and ground equipment.

Opened via the C hotkey from city or space mode. TAB cycles between
the Stats tab and the Equipment tab.

The Stats tab shows all 6 skill rows: Gunnery, Piloting, Engineering
(ship skills) and Reflexes, Strength, Stamina (ground stats).
"""

from __future__ import annotations

from .game_context import GameContext

_SKILLS: tuple[str, ...] = (
    "gunnery", "piloting", "engineering",
    "reflexes", "strength", "stamina",
)
# One-line general description per skill, shown at the bottom of the
# Stats tab. Kept in sync with the guide's Character & Skills section.
_SKILL_DESCRIPTIONS: dict[str, str] = {
    "gunnery": "+0.5% hit chance per point in space combat",
    "piloting": "AP per turn (3 + Piloting//20) and dodge (cap 60%)",
    "engineering": "shield regen costs -1 power per 20 pts; +1 max power per 5",
    "reflexes": "ranged accuracy and dodge bonus on foot",
    "strength": "melee damage and two-handed weapon efficiency",
    "stamina": "HP pool (20 + Stamina//3) and damage resistance",
}
_ARMOR_SLOTS: tuple[str, ...] = ("head", "body", "hands", "legs", "feet")
_ARMOR_SLOT_LABELS: dict[str, str] = {
    "head": "Head", "body": "Body", "hands": "Hands",
    "legs": "Legs", "feet": "Feet",
}

def _character_frame(
    ctx: GameContext,
    tab: int,
    selected: int,
    *,
    equipment_management: bool = False,
    swap_allowed: bool = True,
):
    """Build a Pygame snapshot for one Character tab."""
    from .xp import xp_for_level, _xp_to_next

    level = ctx.player_level
    current_xp = max(0, ctx.player_xp - xp_for_level(level))
    needed = _xp_to_next(level)
    title = f"CHARACTER - Level {level} {ctx.character_info.get('class_name', '').title()}"
    if tab == 0:
        return _stats_frame(ctx, title, current_xp, needed, selected)
    return _equipment_frame(
        ctx, title, selected,
        equipment_management=equipment_management,
        swap_allowed=swap_allowed,
    )


def _stats_frame(ctx: GameContext, title: str, current_xp: int, needed: int, selected: int):
    """Build the Stats-tab frame (skills, XP, traits)."""
    from . import pygame_screen, pygame_ui

    rows = tuple(
        pygame_screen.ScreenRow(
            text=f"{skill.title():<12} {getattr(ctx.stats if index < 3 else ctx.ground_stats, skill, 10):>3}  "
            f"{'[+]' if ctx.player_skill_points > 0 and getattr(ctx.stats if index < 3 else ctx.ground_stats, skill, 10) < 100 else 'MAX' if getattr(ctx.stats if index < 3 else ctx.ground_stats, skill, 10) >= 100 else ''}",
            detail=_SKILL_DESCRIPTIONS[skill],
            action=f"SPEND:{skill}",
        )
        for index, skill in enumerate(_SKILLS)
    )
    body = (
        f"XP: {current_xp} / {needed}    Skill points available: {ctx.player_skill_points}",
        f"Traits: {', '.join(ctx.player_traits) if ctx.player_traits else 'None'}",
    )
    footer = (pygame_ui.modal_hint(
        pygame_ui.NAV_HINT, "ENTER spend", "TAB equipment",
        "ESC close", pygame_ui.GUIDE_HINT,
    ),)
    return pygame_screen.ScreenFrame(
        title, body, rows, footer, selected,
        tabs=("STATS", "EQUIPMENT"), active_tab=0,
    )


def _equipment_frame(
    ctx: GameContext,
    title: str,
    selected: int,
    *,
    equipment_management: bool,
    swap_allowed: bool,
):
    """Build the Equipment-tab frame (loadout + backpack)."""
    from . import pygame_screen, pygame_ui

    rows = _equipment_rows(
        ctx,
        equipment_management=equipment_management,
        swap_allowed=swap_allowed,
    )
    capacity = _expedition_capacity(ctx)
    body = (
        f"Equipped ground gear    Expedition Pack: "
        f"{len(ctx.ground_expedition_inventory)}/{capacity}",
        "Select a slot and press ENTER to swap from your backpack."
        if equipment_management
        else "Equipment is read-only outside management mode.",
    )
    footer = (pygame_ui.modal_hint(
        pygame_ui.NAV_HINT,
        "ENTER swap" if equipment_management else "TAB stats",
        "TAB stats", "ESC close", pygame_ui.GUIDE_HINT,
    ),)
    return pygame_screen.ScreenFrame(
        title, body, rows, footer, selected,
        tabs=("STATS", "EQUIPMENT"), active_tab=1,
    )

def _expedition_capacity(ctx: GameContext) -> int:
    """Return the current Expedition Pack capacity."""
    from . import ground_equipment

    strength = int(getattr(getattr(ctx, "ground_stats", None), "strength", 10))
    return ground_equipment.expedition_capacity(strength)


def _armor_effects(spec) -> str:
    """Format one armor piece's cybernetic bonuses, or an empty string."""
    bonuses = []
    if spec.ap_bonus:
        bonuses.append(f"+{spec.ap_bonus} AP")
    if spec.hit_bonus:
        bonuses.append(f"+{spec.hit_bonus}% Hit")
    if spec.melee_bonus:
        bonuses.append(f"+{spec.melee_bonus} Melee")
    if spec.hp_bonus:
        bonuses.append(f"+{spec.hp_bonus} HP")
    return f"   {' '.join(bonuses)}" if bonuses else ""


def _pack_entry_name(entry) -> str:
    """Return the display name for one Expedition Pack entry."""
    from .data.ground_armor import find_ground_armor
    from .data.ground_weapons import find_ground_weapon

    if entry.item_type == "weapon":
        return find_ground_weapon(entry.item_id).name
    return find_ground_armor(entry.item_id).name


def _pack_entry_detail(entry) -> str:
    """Return the useful detail text for one Expedition Pack entry."""
    from .data.ground_armor import find_ground_armor
    from .data.ground_weapons import find_ground_weapon

    if entry.item_type == "weapon":
        spec = find_ground_weapon(entry.item_id)
        hands = "2H" if spec.hands == 2 else "1H"
        return (
            f"{hands}  {spec.damage_type.title()}  Damage {spec.damage}  "
            f"Accuracy {spec.accuracy}%  Range {spec.min_range}-{spec.max_range}"
        )
    spec = find_ground_armor(entry.item_id)
    return f"{spec.slot.title()}  Defense {spec.defense}{_armor_effects(spec)}  {spec.description}"


def _swap_options(ctx: GameContext, item_type: str, slot: str) -> tuple[tuple[int, str, str], ...]:
    """Return compatible Expedition Pack entries for one active slot."""
    from . import ground_equipment
    from .data.ground_armor import find_ground_armor

    options = []
    for index, entry in enumerate(ctx.ground_expedition_inventory):
        if entry.item_type != item_type:
            continue
        try:
            if item_type == "armor":
                if find_ground_armor(entry.item_id).slot != slot:
                    continue
            elif slot == "1" and ctx.equipped_ground_weapons:
                if ground_equipment.weapon_hands(ctx.equipped_ground_weapons[0]) == 2:
                    continue
                if ground_equipment.weapon_hands(entry.item_id) == 2:
                    continue
            elif ground_equipment.weapon_hands(entry.item_id) == 2 and slot != "0":
                continue
            name = _pack_entry_name(entry)
            options.append((index, name, _pack_entry_detail(entry)))
        except KeyError:
            continue
    return tuple(options)


def _secondary_weapon_slot_enabled(
    ctx: GameContext,
    options: tuple[tuple[int, str, str], ...],
    *,
    swap_allowed: bool,
) -> bool:
    """Return whether Weapon 2 can offer a valid managed swap."""
    if not swap_allowed or options:
        return bool(swap_allowed)
    if not ctx.ground_expedition_inventory:
        return True
    from . import ground_equipment

    return any(
        entry.item_type == "weapon"
        and _weapon_is_one_handed(ground_equipment, entry.item_id)
        for entry in ctx.ground_expedition_inventory
    )


def _weapon_is_one_handed(ground_equipment, item_id: str) -> bool:
    """Return whether a catalog weapon can occupy the secondary slot."""
    try:
        return ground_equipment.weapon_hands(item_id) != 2
    except KeyError:
        return False


def _managed_swap_enabled(
    ctx: GameContext,
    item_type: str,
    slot: str,
    options: tuple[tuple[int, str, str], ...],
    *,
    swap_allowed: bool,
) -> bool:
    """Return whether a management row should accept Enter."""
    if item_type == "weapon" and slot == "1":
        return _secondary_weapon_slot_enabled(
            ctx, options, swap_allowed=swap_allowed,
        )
    return bool(swap_allowed)


def _equipment_row(
    text: str,
    detail: str = "",
    *,
    action: str = "",
    selectable: bool = False,
):
    """Build one consistently spaced Equipment-tab row."""
    from . import pygame_screen

    return pygame_screen.ScreenRow(
        text, detail, action, selectable=selectable,
    )


def _equipment_rows(
    ctx: GameContext,
    *,
    equipment_management: bool = False,
    swap_allowed: bool = True,
) -> tuple:
    """Build Equipment-tab rows with optional Expedition Pack actions.

    Filled slots and compatible empty slots become selectable only for the
    dungeon/combat management view. All rows use the same presentation shape;
    the screen renderer supplies identical spacing for empty and equipped rows.
    """
    rows = _weapon_rows(ctx, equipment_management, swap_allowed)
    rows += _armor_rows(ctx, equipment_management, swap_allowed)
    if equipment_management:
        rows += _backpack_rows(ctx)
    return tuple(rows)


def _weapon_rows(
    ctx: GameContext, equipment_management: bool, swap_allowed: bool,
) -> list:
    """Build the two weapon-slot rows for the active ground loadout."""
    rows: list = []
    weapons = list(ctx.equipped_ground_weapons)
    while len(weapons) < 2:
        weapons.append("")
    first_weapon_is_two_handed = _first_weapon_is_two_handed(weapons)
    for index, weapon_id in enumerate(weapons[:2], 1):
        rows.append(_weapon_row(
            ctx, index, weapon_id,
            occupied_by_two_handed=(
                index == 2 and first_weapon_is_two_handed
            ),
            equipment_management=equipment_management,
            swap_allowed=swap_allowed,
        ))
    return rows


def _first_weapon_is_two_handed(weapons: list[str]) -> bool:
    """Return whether the first equipped weapon is two-handed."""
    from .data.ground_weapons import find_ground_weapon

    if not weapons[0]:
        return False
    try:
        return find_ground_weapon(weapons[0]).hands == 2
    except KeyError:
        return False


def _weapon_row(
    ctx: GameContext,
    index: int,
    weapon_id: str,
    *,
    occupied_by_two_handed: bool,
    equipment_management: bool,
    swap_allowed: bool,
):
    """Build one weapon-slot row (filled, empty, or occupied-by-2H)."""
    from .data.ground_weapons import find_ground_weapon

    label = f"Weapon slot {index}"
    if occupied_by_two_handed:
        return _equipment_row(f"{label}: --- (occupied by 2H)")
    if weapon_id:
        try:
            spec = find_ground_weapon(weapon_id)
            detail = (
                f"{spec.damage_type.title()}   Damage {spec.damage}   "
                f"Accuracy {spec.accuracy}%   Range {spec.min_range}-"
                f"{spec.max_range}   AP {spec.ap_cost}"
            )
            if spec.ammo_capacity > 0:
                detail += f"   Ammo {spec.ammo_capacity}"
            _managed = _weapon_managed(ctx, index - 1, equipment_management, swap_allowed)
            return _equipment_row(
                f"{label}: {spec.name}", detail,
                action=f"SWAP:weapon:{index - 1}" if _managed else "",
                selectable=True if not equipment_management else _managed,
            )
        except KeyError:
            pass
    _managed = _weapon_managed(ctx, index - 1, equipment_management, swap_allowed)
    return _equipment_row(
        f"{label}: Fists", "",
        action=f"SWAP:weapon:{index - 1}" if _managed else "",
        selectable=False if not equipment_management else _managed,
    )


def _weapon_managed(
    ctx: GameContext, slot_index: int, equipment_management: bool, swap_allowed: bool,
) -> bool:
    """Return whether one weapon slot is actionable in management mode."""
    if not equipment_management:
        return False
    _options = _swap_options(ctx, "weapon", str(slot_index))
    return _managed_swap_enabled(
        ctx, "weapon", str(slot_index), _options,
        swap_allowed=swap_allowed,
    )


def _armor_rows(
    ctx: GameContext, equipment_management: bool, swap_allowed: bool,
) -> list:
    """Build the five armor-slot rows for the active ground loadout."""
    from .data.ground_armor import find_ground_armor

    rows: list = []
    for slot in _ARMOR_SLOTS:
        item_id = ctx.equipped_ground_armor.get(slot)
        label = f"{_ARMOR_SLOT_LABELS[slot]} armor"
        if item_id:
            try:
                spec = find_ground_armor(item_id)
                _managed = _armor_managed(ctx, slot, equipment_management, swap_allowed)
                rows.append(_equipment_row(
                    f"{label}: {spec.name}",
                    f"Defense {spec.defense}{_armor_effects(spec)}   {spec.description}",
                    action=f"SWAP:armor:{slot}" if _managed else "",
                    selectable=True if not equipment_management else _managed,
                ))
                continue
            except KeyError:
                pass
        _managed = _armor_managed(ctx, slot, equipment_management, swap_allowed)
        rows.append(_equipment_row(
            f"{label}: None", "",
            action=f"SWAP:armor:{slot}" if _managed else "",
            selectable=False if not equipment_management else _managed,
        ))
    return rows


def _armor_managed(
    ctx: GameContext, slot: str, equipment_management: bool, swap_allowed: bool,
) -> bool:
    """Return whether one armor slot is actionable in management mode."""
    if not equipment_management:
        return False
    _options = _swap_options(ctx, "armor", slot)
    return _managed_swap_enabled(
        ctx, "armor", slot, _options,
        swap_allowed=swap_allowed,
    )


def _backpack_rows(ctx: GameContext) -> list:
    """Build the backpack header and item rows for the management view."""
    capacity = _expedition_capacity(ctx)
    rows = [_equipment_row(
        f"--- BACKPACK ITEMS ({len(ctx.ground_expedition_inventory)}/{capacity}) ---",
    )]
    if not ctx.ground_expedition_inventory:
        rows.append(_equipment_row("[empty]"))
        return rows
    for index, entry in enumerate(ctx.ground_expedition_inventory):
        try:
            rows.append(_equipment_row(
                _pack_entry_name(entry), _pack_entry_detail(entry),
                action=f"PACK_ITEM:{index}", selectable=True,
            ))
        except (KeyError, TypeError, ValueError):
            continue
    return rows


def _swap_pack_entry(
    ctx: GameContext,
    item_type: str,
    slot: str,
    pack_index: int,
) -> bool:
    """Swap one selected pack entry into an active slot."""
    from . import ground_equipment

    strength = int(getattr(getattr(ctx, "ground_stats", None), "strength", 10))
    try:
        if item_type == "weapon":
            ground_equipment.swap_weapon_from_expedition(
                ctx.equipped_ground_weapons,
                ctx.ground_expedition_inventory,
                pack_index, int(slot), strength=strength,
            )
        else:
            ground_equipment.swap_armor_from_expedition(
                ctx.equipped_ground_armor,
                ctx.ground_expedition_inventory,
                pack_index, slot, strength=strength,
            )
    except (IndexError, KeyError, ValueError) as exc:
        ctx.log.add(str(exc))
        return False
    ctx.log.add("Expedition gear swapped.")
    return True


def _pack_weapon_slots(ctx: GameContext, pack_index: int) -> tuple[str, ...]:
    """Return active weapon slots compatible with one pack entry."""
    ctx.ground_expedition_inventory[pack_index]  # bounds check
    return tuple(
        str(slot)
        for slot in range(2)
        if any(
            option[0] == pack_index
            for option in _swap_options(ctx, "weapon", str(slot))
        )
    )


def _discard_pack_item(ctx: GameContext, pack_index: int) -> bool:
    """Discard one carried pack item."""
    if not 0 <= pack_index < len(ctx.ground_expedition_inventory):
        ctx.log.add("That backpack item is no longer available.")
        return False
    entry = ctx.ground_expedition_inventory.pop(pack_index)
    try:
        name = _pack_entry_name(entry)
    except (KeyError, TypeError, ValueError):
        name = "equipment"
    ctx.log.add(f"Discarded {name}.")
    return True


def _equip_pack_item(
    ctx: GameContext,
    pack_index: int,
    *,
    swap_allowed: bool = True,
) -> bool:
    """Equip one selected pack item, choosing a weapon slot when needed."""
    if not swap_allowed:
        ctx.log.add("You need 1 AP to equip backpack gear.")
        return False
    if not 0 <= pack_index < len(ctx.ground_expedition_inventory):
        ctx.log.add("That backpack item is no longer available.")
        return False
    entry = ctx.ground_expedition_inventory[pack_index]
    if entry.item_type == "armor":
        return _equip_armor_pack_item(ctx, entry, pack_index)
    return _equip_weapon_pack_item(ctx, entry, pack_index)


def _equip_armor_pack_item(ctx: GameContext, entry, pack_index: int) -> bool:
    """Equip one pack armor item into its matching slot."""
    from .data.ground_armor import find_ground_armor

    try:
        slot = find_ground_armor(entry.item_id).slot
    except KeyError:
        ctx.log.add("That backpack item is invalid.")
        return False
    return _swap_pack_entry(ctx, "armor", slot, pack_index)


def _equip_weapon_pack_item(ctx: GameContext, entry, pack_index: int) -> bool:
    """Equip one pack weapon, prompting for a slot when two fit."""
    from . import pygame_story

    slots = _pack_weapon_slots(ctx, pack_index)
    if not slots:
        ctx.log.add("That weapon cannot fit your active loadout.")
        return False
    if len(slots) == 1:
        return _swap_pack_entry(ctx, "weapon", slots[0], pack_index)
    choices = tuple(
        (f"Weapon {int(slot) + 1}", f"PACK_EQUIP_SLOT:{pack_index}:{slot}")
        for slot in slots
    )
    chosen = pygame_story.choose(
        ctx, title="EQUIP BACKPACK ITEM", body=_pack_entry_name(entry),
        options=choices, caption="spacehack - equipment slot", compact=True,
    )
    if chosen in {None, "__BACK__", "__DISMISS__", "__GUIDE__"}:
        return False
    if chosen == "__QUIT__":
        raise SystemExit
    _parts = chosen.split(":")
    return _swap_pack_entry(ctx, "weapon", _parts[-1], pack_index)


def _manage_pack_item(
    ctx: GameContext,
    action: str,
    *,
    swap_allowed: bool = True,
) -> str | None:
    """Offer Equip or Discard for one selectable backpack row."""
    from . import pygame_story

    pack_index = int(action.split(":", 1)[1])
    if not 0 <= pack_index < len(ctx.ground_expedition_inventory):
        ctx.log.add("That backpack item is no longer available.")
        return None
    entry = ctx.ground_expedition_inventory[pack_index]
    try:
        name = _pack_entry_name(entry)
    except (KeyError, TypeError, ValueError):
        ctx.log.add("That backpack item is invalid.")
        return None
    equip_label = "Equip" if swap_allowed else "Equip (requires 1 AP)"
    chosen = pygame_story.choose(
        ctx, title="BACKPACK ITEM", body=name,
        options=(
            (equip_label, f"PACK_EQUIP:{pack_index}"),
            ("Discard", f"PACK_DISCARD:{pack_index}"),
        ),
        caption="spacehack - backpack", compact=True,
    )
    if chosen in {None, "__BACK__", "__DISMISS__", "__GUIDE__"}:
        return None
    if chosen == "__QUIT__":
        raise SystemExit
    if chosen.startswith("PACK_DISCARD:"):
        return "DISCARD" if _discard_pack_item(ctx, pack_index) else None
    if chosen.startswith("PACK_EQUIP:"):
        return "EQUIP" if _equip_pack_item(
            ctx, pack_index, swap_allowed=swap_allowed,
        ) else None
    return None


def _swap_from_pack(ctx: GameContext, action: str) -> bool:
    """Open the backpack submenu and apply one selected equipment swap."""
    from . import pygame_story

    _prefix, item_type, slot = action.split(":", 2)
    options = _swap_options(ctx, item_type, slot)
    if not options:
        ctx.log.add("No compatible items are in your Expedition Pack.")
        return False
    choices = tuple(
        (
            f"{name}",
            f"PACK_SWAP:{item_type}:{slot}:{index}",
        )
        for index, name, _detail in options
    )
    chosen = pygame_story.choose(
        ctx,
        title="EXPEDITION PACK",
        body=f"Swap gear into {('Weapon slot ' + str(int(slot) + 1)) if item_type == 'weapon' else slot.title() + ' armor'}.",
        options=choices,
        caption="spacehack - expedition equipment",
        compact=True,
    )
    if chosen in {None, "__BACK__", "__DISMISS__", "__GUIDE__"}:
        return False
    if chosen == "__QUIT__":
        raise SystemExit
    _parts = chosen.split(":")
    pack_index = int(_parts[-1])
    return _swap_pack_entry(ctx, item_type, slot, pack_index)


def _run_pygame_character_screen(
    ctx: GameContext,
    *,
    equipment_management: bool = False,
    in_ground_combat: bool = False,
) -> int | None:
    """Run Character through the shared Pygame screen."""
    from . import pygame_screen

    tab = 0
    selected = 0
    swap_count = 0
    while True:
        outcome, action, selected = pygame_screen.run_for_context(
            ctx.context,
            _character_frame(
                ctx, tab, selected,
                equipment_management=equipment_management,
                swap_allowed=(
                    not in_ground_combat
                    or _combat_ap_available(ctx, reserved=swap_count)
                ),
            ),
            caption="spacehack - character",
        )
        tab, selected, swap_count, done = _advance_character_screen(
            ctx, outcome, action, tab, selected, swap_count,
            equipment_management=equipment_management,
            in_ground_combat=in_ground_combat,
        )
        if done:
            return swap_count


def _advance_character_screen(
    ctx: GameContext,
    outcome: str,
    action: str,
    tab: int,
    selected: int,
    swap_count: int,
    *,
    equipment_management: bool,
    in_ground_combat: bool,
) -> tuple[int, int, int, bool]:
    """Advance one loop iteration; return ``(tab, selected, swap_count, done)``."""
    if outcome == "GUIDE":
        from .help import _open_context_guide
        _open_context_guide(ctx, "Character & Skills")
        return tab, selected, swap_count, False
    if outcome == "TAB":
        return (tab + 1) % 2, 0, swap_count, False
    if outcome == "SELECT":
        swap_count, should_return = _apply_character_select(
            ctx, action, tab, swap_count,
            equipment_management=equipment_management,
            in_ground_combat=in_ground_combat,
        )
        return tab, selected, swap_count, should_return
    if outcome in {"PAGE_UP", "PAGE_DOWN"}:
        return tab, selected, swap_count, False
    if outcome == "QUIT":
        raise SystemExit
    return tab, selected, swap_count, True


def _apply_character_select(
    ctx: GameContext,
    action: str,
    tab: int,
    swap_count: int,
    *,
    equipment_management: bool,
    in_ground_combat: bool,
) -> tuple[int, bool]:
    """Apply one SELECT action; return ``(swap_count, should_return)``."""
    from .xp import _apply_skill_point

    if tab == 0 and action.startswith("SPEND:"):
        skill = action.split(":", 1)[1]
        if skill in _SKILLS:
            _apply_skill_point(ctx, skill)
        return swap_count, False
    if tab == 1 and equipment_management:
        if action.startswith("SWAP:") and _swap_from_pack(ctx, action):
            swap_count += 1
            return swap_count, in_ground_combat
        if action.startswith("PACK_ITEM:"):
            _pack_result = _manage_pack_item(
                ctx,
                action,
                swap_allowed=(
                    not in_ground_combat
                    or _combat_ap_available(ctx, reserved=swap_count)
                ),
            )
            if _pack_result == "EQUIP" and in_ground_combat:
                return swap_count + 1, True
    return swap_count, False

def _combat_ap_available(ctx: GameContext, *, reserved: int = 0) -> bool:
    """Return whether an active ground combat session has AP to spend."""
    from .combat import _rules_ground

    return _rules_ground.player_ap(ctx) > reserved


def open_character_screen(
    ctx: GameContext,
    *,
    equipment_management: bool = False,
    in_ground_combat: bool = False,
) -> int:
    """Open the Character screen and return successful swap count."""
    result = _run_pygame_character_screen(
        ctx,
        equipment_management=equipment_management,
        in_ground_combat=in_ground_combat,
    )
    if result is None:
        raise RuntimeError("Character screen returned no outcome")
    return result
