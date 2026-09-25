"""Character screen — stats, equipment, and ship cargo.

Opened via the C hotkey from city or space mode. TAB cycles between
the Stats, Equipment, and Cargo tabs.

The Stats tab shows all 6 skill rows: Gunnery, Piloting, Engineering
(ship skills) and Reflexes, Strength, Stamina (ground stats).
"""

from __future__ import annotations

from .game_context import GameContext

from .ground_equipment import (  # noqa: F401 — re-exported slot tables
    ARMOR_SLOTS as _ARMOR_SLOTS,
    ARMOR_SLOT_LABELS as _ARMOR_SLOT_LABELS,
)

def _character_frame(
    ctx: GameContext,
    tab: int,
    selected: int,
    *,
    equipment_management: bool = False,
    swap_allowed: bool = True,
    in_ground_combat: bool = False,
    floor_available: bool = True,
):
    """Build a Pygame snapshot for one Character tab."""
    from .xp import xp_for_level, _xp_to_next

    level = ctx.player_level
    current_xp = max(0, ctx.player_xp - xp_for_level(level))
    needed = _xp_to_next(level)
    title = f"CHARACTER - Level {level} {ctx.character_info.get('class_name', '').title()}"
    if tab == 0:
        return _stats_frame(ctx, title, current_xp, needed, selected)
    if tab == 1:
        return _equipment_frame(
            ctx, title, selected,
            equipment_management=equipment_management,
            swap_allowed=swap_allowed,
        )
    return _cargo_character_frame(ctx, title, selected)


def _equipment_frame(
    ctx: GameContext,
    title: str,
    selected: int,
    *,
    equipment_management: bool,
    swap_allowed: bool,
):
    """Build the Equipment-tab split frame (doc 52.3 amendment): equipment
    management on the left, the read-only bandolier on the right."""
    from . import pygame_split, pygame_ui

    rows = _equipment_rows(
        ctx,
        equipment_management=equipment_management,
        swap_allowed=swap_allowed,
    )
    capacity = _expedition_capacity(ctx)
    hint_parts = (
        (pygame_ui.NAV_HINT, "ENTER swap", "TAB stats", "ESC close", pygame_ui.GUIDE_HINT)
        if equipment_management else
        (pygame_ui.NAV_HINT, "TAB stats", "ESC close", pygame_ui.GUIDE_HINT)
    )
    return pygame_split.SplitFrame(
        title, "Equipment", "Bandolier",
        _split_equipment_rows(rows), _bandolier_rows(ctx),
        f"Expedition Pack: {_expedition_used_slots(ctx)}/{capacity}",
        "Ammo is read-only",
        pygame_ui.modal_hint(*hint_parts),
        selected=selected,
        screen_tabs=("STATS", "EQUIPMENT", "CARGO"), active_screen_tab=1,
    )


def _split_equipment_rows(rows) -> tuple:
    """Convert the Equipment tab's screen rows to split rows (doc 52.3):
    section headers become dividers; the row builders stay single-sourced."""
    from . import pygame_split

    return tuple(
        pygame_split.SplitRow(
            row.text, "", row.detail, row.action,
            divider=row.header, selectable=row.selectable, runs=row.runs,
        )
        for row in rows
    )


def _bandolier_rows(ctx: GameContext) -> tuple:
    """The read-only bandolier panel: every caliber's current/max in an
    aligned readout (doc 52.3 — the inventory view the HUD's
    carried-caliber lines deliberately omit). Feeder names removed and
    the counts column-aligned by the 52.3 playtest ruling (the
    "(Rocket Launcher)" style suffixes read as noise and broke the
    count column)."""
    from . import bandolier as _bandolier, pygame_split
    from .data.ground_items import list_ground_ammo

    pool = getattr(ctx, "bandolier", None) or {}
    entries = [
        (
            spec.name,
            pool.get(spec.ammo_type, 0),
            _bandolier.effective_cap(spec.ammo_type),
        )
        for spec in list_ground_ammo()
    ]
    name_w = max(len(name) for name, _cur, _cap in entries) + 2
    num_w = max(len(str(cap)) for _name, _cur, cap in entries)
    return tuple(
        pygame_split.SplitRow(
            f"{name:<{name_w}}{cur:>{num_w}}/{cap:>{num_w}}",
            "", "", "", selectable=False,
        )
        for name, cur, cap in entries
    )

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
    """Return the token-prefixed display name for one pack entry."""
    from . import ground_equipment

    return ground_equipment.display_name(
        entry.item_type, entry.item_id, entry.quality,
    )


def _pack_entry_runs(entry) -> tuple:
    """``(label, runs)`` for one backpack row — the tier name coloured."""
    from . import message_log
    from .data.quality import quality_mark

    return message_log.with_runs(
        quality_mark(_pack_entry_name(entry), entry.quality),
    )


def _pack_entry_detail(entry) -> str:
    """Return the useful (tier-scaled) detail text for one pack entry."""
    from .data.quality import effective_armor_spec, effective_weapon_spec

    if entry.item_type == "weapon":
        spec = effective_weapon_spec(entry.item_id, entry.quality)
        hands = "2H" if spec.hands == 2 else "1H"
        from .ground_equipment import stored_mag_suffix

        bypass = "  Armor bypass" if spec.armor_bypass else ""
        return (
            f"{hands}  {spec.damage_type.title()}  Damage {spec.damage}  "
            f"Accuracy {spec.accuracy}%  Range {spec.min_range}-{spec.max_range}"
            f"{stored_mag_suffix(entry)}{bypass}"
        )
    spec = effective_armor_spec(entry.item_id, entry.quality)
    return f"{spec.slot.title()}  Defense {spec.defense}{_armor_effects(spec)}  {spec.description}"


def _swap_options(ctx: GameContext, slot: str) -> tuple[tuple[int, str, str], ...]:
    """Return compatible Expedition Pack armor entries for one slot."""
    from .data.ground_armor import find_ground_armor

    options = []
    for index, entry in enumerate(ctx.ground_expedition_inventory):
        if entry.item_type != "armor":
            continue
        try:
            if find_ground_armor(entry.item_id).slot != slot:
                continue
            name = _pack_entry_name(entry)
            options.append((index, name, _pack_entry_detail(entry)))
        except KeyError:
            continue
    return tuple(options)


def _equipment_row(
    text: str,
    detail: str = "",
    *,
    action: str = "",
    selectable: bool = False,
    header: bool = False,
    runs=None,
):
    """Build one consistently spaced Equipment-tab row.

    ``header`` marks the ``--- SECTION ---`` rows; the split converter
    renders them as dividers (doc 52.3).
    """
    from . import pygame_screen

    return pygame_screen.ScreenRow(
        text, detail, action, selectable=selectable, header=header, runs=runs,
    )


def _weapon_rows(ctx: GameContext, equipment_management: bool, swap_allowed: bool) -> list:
    from .character_screen_weapons import _weapon_rows as _rows
    return _rows(ctx, equipment_management, swap_allowed)


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
    rows.append(_equipment_row("--- ARMOR ---", header=True))
    rows += _armor_rows(ctx, equipment_management, swap_allowed)
    if equipment_management:
        rows += _backpack_rows(ctx)
    return tuple(rows)


def _armor_rows(
    ctx: GameContext, equipment_management: bool, swap_allowed: bool,
) -> list:
    """Build the five armor-slot rows for the active ground loadout."""

    rows: list = []
    for slot in _ARMOR_SLOTS:
        entry = ctx.equipped_ground_armor.get(slot)
        label = f"{_ARMOR_SLOT_LABELS[slot]} armor"
        _managed = _armor_managed(ctx, slot, equipment_management, swap_allowed)
        _filled = (
            _filled_armor_row(entry, label, ctx, slot, equipment_management, _managed)
            if entry is not None else None
        )
        rows.append(_filled if _filled is not None else _equipment_row(
            f"{label}: None", "",
            action=f"SWAP:armor:{slot}" if _managed else "",
            selectable=False if not equipment_management else _managed,
        ))
    return rows


def _filled_armor_row(entry, label: str, ctx, slot, equipment_management, managed):
    """One filled armor-slot row with the tier name coloured, or None
    when the entry no longer resolves."""
    from . import ground_equipment, message_log
    from .data.quality import effective_armor_spec, quality_mark

    try:
        spec = effective_armor_spec(entry.item_id, entry.quality)
    except KeyError:
        return None
    _text, _runs = message_log.with_runs(
        f"{label}: ",
        quality_mark(
            ground_equipment.display_name("armor", entry.item_id, entry.quality),
            entry.quality,
        ),
    )
    return _equipment_row(
        _text,
        f"Defense {spec.defense}{_armor_effects(spec)}   {spec.description}",
        action=f"SWAP:armor:{slot}" if managed else "",
        selectable=True if not equipment_management else managed,
        runs=_runs,
    )


def _armor_managed(
    ctx: GameContext, slot: str, equipment_management: bool, swap_allowed: bool,
) -> bool:
    """Return whether one armor slot is actionable in management mode."""
    del ctx, slot
    return equipment_management and swap_allowed


def _backpack_rows(ctx: GameContext) -> list:
    """Build the backpack header plus equipment and field-item rows."""
    capacity = _expedition_capacity(ctx)
    used = _expedition_used_slots(ctx)
    rows = [_equipment_row(
        f"--- BACKPACK ITEMS ({used}/{capacity}) ---", header=True,
    )]
    if not used:
        rows.append(_equipment_row("[empty]"))
        return rows
    rows += _backpack_equipment_rows(ctx)
    rows += _backpack_item_rows(ctx)
    return rows


def _backpack_equipment_rows(ctx: GameContext) -> list:
    """Build the selectable equipment rows for the backpack view."""
    rows: list = []
    for index, entry in enumerate(ctx.ground_expedition_inventory):
        try:
            _label, _runs = _pack_entry_runs(entry)
            rows.append(_equipment_row(
                _label, _pack_entry_detail(entry),
                action=f"PACK_ITEM:{index}", selectable=True, runs=_runs,
            ))
        except (KeyError, TypeError, ValueError):
            continue
    return rows


def _backpack_item_rows(ctx: GameContext) -> list:
    """Build the consumable stack rows for the backpack."""
    rows: list = []
    for index, stack in enumerate(getattr(ctx, "ground_expedition_items", [])):
        try:
            rows.append(_equipment_row(
                _item_stack_name(stack), _item_stack_detail(stack),
                action=f"PACK_STACK:{index}",
                selectable=True,
            ))
        except (KeyError, TypeError, ValueError):
            continue
    return rows


def _item_stack_name(stack) -> str:
    """Return the display name and current/max quantity for one stack."""
    from .data.ground_items import find_ground_item
    from .ground_equipment import item_stack_capacity

    name = find_ground_item(stack.item_type, stack.item_id).name
    capacity = item_stack_capacity(stack.item_type, stack.item_id)
    return f"{name} [{stack.quantity}/{capacity}]"


def _item_stack_detail(stack) -> str:
    """Return the useful detail text for one consumable stack."""
    from .data.ground_items import find_ground_item

    spec = find_ground_item(stack.item_type, stack.item_id)
    detail = f"Consumable  {stack.quantity}/{spec.quantity_per_stack}  {spec.effect_label or spec.name}"
    if spec.outside_full_heal:
        detail += f"  combat +{spec.combat_heal_amount} HP/+{spec.combat_regen_amount} HP x{spec.duration_turns}"
    elif spec.combat_ap_bonus:
        detail += f"  +{spec.combat_ap_bonus} AP x{spec.duration_turns}"
    return detail


def _swap_pack_entry(
    ctx: GameContext,
    item_type: str,
    slot: str,
    pack_index: int,
) -> bool:
    """Swap one selected pack armor entry into its slot (doc 51.3:
    weapons install through :func:`_install_pack_weapon`)."""
    from . import ground_equipment

    strength = int(getattr(getattr(ctx, "ground_stats", None), "strength", 10))
    try:
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


def _install_pack_weapon(ctx: GameContext, pack_index: int, displace_index=None) -> bool:
    """Install one pack weapon into its class home (doc 51.3).

    Displaced members route back to the pack, capacity-checked
    atomically; the log names a holstered landing honestly.
    """
    from . import ground_equipment, ground_weapon_sets

    strength = int(getattr(getattr(ctx, "ground_stats", None), "strength", 10))
    try:
        _entry, role = ground_weapon_sets.install_set_weapon(
            ctx.equipped_ground_weapons, ctx.holstered_ground_weapons,
            ctx.ground_expedition_inventory, pack_index,
            displace_index=displace_index,
            displaced_storage=ctx.ground_expedition_inventory,
            displaced_container=ground_equipment.EXPEDITION_INVENTORY,
            strength=strength,
        )
    except (IndexError, KeyError, ValueError) as exc:
        ctx.log.add(str(exc))
        return False
    suffix = " (holstered)" if role == "HOLSTER" else ""
    ctx.log.add(f"Expedition gear swapped{suffix}.")
    return True


def _pack_weapon_options(ctx: GameContext, set_class: str) -> tuple:
    """Pack weapon entries of one class, for a group's equip options."""
    from .ground_weapon_sets import weapon_set

    options = []
    for index, entry in enumerate(ctx.ground_expedition_inventory):
        if entry.item_type != "weapon":
            continue
        try:
            if weapon_set(entry.item_id) != set_class:
                continue
            options.append((index, _pack_entry_name(entry), _pack_entry_detail(entry)))
        except KeyError:
            continue
    return tuple(options)


async def _choose_displaced_member(ctx, home: list, entry) -> int | None:
    """The member chooser (SETTLED 3): who leaves when a set is full."""
    from . import pygame_story
    from .character_screen_weapons import _member_label

    choices = []
    for index, instance in enumerate(home):
        label, runs = _member_label(instance)
        choices.append((label, f"SET_MEMBER:{index}", runs))
    chosen = await pygame_story.choose(
        ctx, title="WEAPON SET IS FULL", body=_pack_entry_name(entry),
        options=tuple(choices), caption="spacehack - weapon set", compact=True,
    )
    if chosen in {None, "__BACK__", "__DISMISS__", "__GUIDE__"}:
        return None
    if chosen == "__QUIT__":
        raise SystemExit
    try:
        return int(chosen.rsplit(":", 1)[1])
    except (IndexError, ValueError):
        return None


def _discard_pack_item(ctx: GameContext, pack_index: int) -> bool:
    """Drop one carried pack item to the floor at the player's feet
    (doc 47.1: Discard puts it down, never destroys)."""
    from .loot import _drop_expedition_entry_at

    if not 0 <= pack_index < len(ctx.ground_expedition_inventory):
        ctx.log.add("That backpack item is no longer available.")
        return False
    try:
        _entry = ctx.ground_expedition_inventory[pack_index]
        name, quality = _pack_entry_name(_entry), _entry.quality
    except (KeyError, TypeError, ValueError):
        name, quality = "equipment", 0
    _drop_expedition_entry_at(ctx, ctx.player.pos, pack_index)
    from . import message_log
    from .data.quality import quality_mark

    _msg, _runs = message_log.with_runs(
        "Dropped ", quality_mark(name, quality), ".",
    )
    ctx.log.add(_msg, runs=_runs)
    return True


async def _equip_pack_item(
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
    return await _equip_weapon_pack_item(ctx, entry, pack_index)


def _equip_armor_pack_item(ctx: GameContext, entry, pack_index: int) -> bool:
    """Equip one pack armor item into its matching slot."""
    from .data.ground_armor import find_ground_armor

    try:
        slot = find_ground_armor(entry.item_id).slot
    except KeyError:
        ctx.log.add("That backpack item is invalid.")
        return False
    return _swap_pack_entry(ctx, "armor", slot, pack_index)


async def _equip_weapon_pack_item(ctx: GameContext, entry, pack_index: int) -> bool:
    """Equip one pack weapon into its class home; a full set opens the
    member chooser for 1H picks (a 2H displaces the whole set)."""
    from . import ground_weapon_sets
    from .ground_equipment import weapon_hands

    resolved = ground_weapon_sets.resolve_weapon_home(
        ctx.equipped_ground_weapons, ctx.holstered_ground_weapons, entry.item_id,
    )
    if resolved is None:
        ctx.log.add(ground_weapon_sets.NO_WEAPON_HOME_LINE)
        return False
    home, _role = resolved
    displace_index = None
    if (
        not ground_weapon_sets.can_fit_weapon_set(home, entry.item_id)
        and weapon_hands(entry.item_id) == 1
    ):
        displace_index = await _choose_displaced_member(ctx, home, entry)
        if displace_index is None:
            return False
    return _install_pack_weapon(ctx, pack_index, displace_index)


def _store_set_member(ctx: GameContext, set_class: str, member_index: int) -> bool:
    """Store one set member into the pack, capacity-checked (doc 51.3)."""
    from . import ground_equipment
    from .character_screen_weapons import _class_home

    strength = int(getattr(getattr(ctx, "ground_stats", None), "strength", 10))
    try:
        ground_equipment.store_weapon(
            _class_home(ctx, set_class), ctx.ground_expedition_inventory,
            member_index,
            container=ground_equipment.EXPEDITION_INVENTORY, strength=strength,
        )
    except (IndexError, KeyError, ValueError) as exc:
        ctx.log.add(str(exc))
        return False
    return True


async def _manage_weapon_set_member(
    ctx: GameContext, set_class: str, member_index: int | None,
) -> bool:
    """Chooser for one weapon group: store a member / equip pack
    entries of the class (both count as equipment changes)."""
    from . import pygame_story

    options = ()
    if member_index is not None:
        options += (("Store in Pack", f"SET_STORE:{set_class}:{member_index}"),)
    options += tuple(
        (name, f"PACK_EQUIP:{index}", _pack_option_runs(ctx, index))
        for index, name, _detail in _pack_weapon_options(ctx, set_class)
    )
    if not options:
        ctx.log.add("No compatible items are in your Expedition Pack.")
        return False
    chosen = await pygame_story.choose(
        ctx, title="WEAPON SET", body=f"Manage the {set_class.title()} set.",
        options=options, caption="spacehack - weapon set", compact=True,
    )
    if chosen in {None, "__BACK__", "__DISMISS__", "__GUIDE__"}:
        return False
    if chosen == "__QUIT__":
        raise SystemExit
    if chosen.startswith("SET_STORE:"):
        _set_class, _member = chosen.split(":", 2)[1:]
        return _store_set_member(ctx, _set_class, int(_member))
    if chosen.startswith("PACK_EQUIP:"):
        return await _equip_pack_item(
            ctx, int(chosen.split(":", 1)[1]), swap_allowed=True,
        )
    return False


def _pack_item_options(equip_label: str, pack_index: int, floor_available: bool):
    """Equip always; Discard only where there is a floor to drop on."""
    options = [(equip_label, f"PACK_EQUIP:{pack_index}")]
    if floor_available:
        options.append(("Discard", f"PACK_DISCARD:{pack_index}"))
    return tuple(options)


def _stack_options(use_label: str, index: int, floor_available: bool):
    """Use/Reload always; Discard only where there is a floor."""
    options = [(use_label, f"STACK_USE:{index}")]
    if floor_available:
        options.append(("Discard", f"STACK_DISCARD:{index}"))
    return tuple(options)


async def _manage_pack_item(
    ctx: GameContext,
    action: str,
    *,
    swap_allowed: bool = True,
    floor_available: bool = True,
) -> str | None:
    """Offer Equip (and Discard, with a floor) for one backpack row."""
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
    chosen = await pygame_story.choose(
        ctx, title="BACKPACK ITEM", body=name,
        options=_pack_item_options(equip_label, pack_index, floor_available),
        caption="spacehack - backpack", compact=True,
    )
    if chosen in {None, "__BACK__", "__DISMISS__", "__GUIDE__"}:
        return None
    if chosen == "__QUIT__":
        raise SystemExit
    if chosen.startswith("PACK_DISCARD:"):
        return "DISCARD" if _discard_pack_item(ctx, pack_index) else None
    if chosen.startswith("PACK_EQUIP:"):
        return "EQUIP" if await _equip_pack_item(
            ctx, pack_index, swap_allowed=swap_allowed,
        ) else None
    return None


async def _manage_consumable_stack(
    ctx: GameContext, index: int, *, in_ground_combat: bool,
    floor_available: bool = True,
) -> str | None:
    """Offer Use (and Discard, with a floor) for one consumable stack."""
    from . import pygame_story

    stack = ctx.ground_expedition_items[index]
    chosen = await pygame_story.choose(
        ctx,
        title="CONSUMABLE",
        body=_item_stack_name(stack),
        options=_stack_options("Use", index, floor_available),
        caption="spacehack - consumable", compact=True,
    )
    if chosen in {None, "__BACK__", "__DISMISS__", "__GUIDE__"}:
        return None
    if chosen == "__QUIT__":
        raise SystemExit
    if chosen.startswith("STACK_USE:"):
        from . import tinker
        from .ground_consumables import use_consumable
        _kit = await tinker.try_manage_kit(ctx, index)
        if _kit is not None:
            return "USE" if _kit else None
        return "USE" if use_consumable(
            ctx, index, in_combat=in_ground_combat,
        ) else None
    if chosen.startswith("STACK_DISCARD:"):
        return "DISCARD" if _discard_pack_stack(ctx, index) else None
    return None


async def _manage_pack_stack(
    ctx: GameContext, action: str, *, in_ground_combat: bool,
    floor_available: bool = True,
) -> str | None:
    """Offer Use (and Discard, with a floor) for one consumable stack."""
    index = int(action.split(":", 1)[1])
    items = getattr(ctx, "ground_expedition_items", [])
    if not 0 <= index < len(items):
        ctx.log.add("That pack item is no longer available.")
        return None
    try:
        return await _manage_consumable_stack(
            ctx, index, in_ground_combat=in_ground_combat,
            floor_available=floor_available,
        )
    except (KeyError, TypeError, ValueError):
        ctx.log.add("That item is invalid.")
        return None


def _discard_pack_stack(ctx: GameContext, index: int) -> bool:
    """Drop one carried field-item stack to the floor at the player's
    feet (doc 47.1: Discard puts it down, never destroys)."""
    from .loot import _drop_expedition_stack_at

    items = getattr(ctx, "ground_expedition_items", [])
    if not 0 <= index < len(items):
        ctx.log.add("That item is no longer available.")
        return False
    try:
        name = _item_stack_name(items[index])
    except (KeyError, TypeError, ValueError):
        name = "item"
    _drop_expedition_stack_at(ctx, ctx.player.pos, index)
    ctx.log.add(f"Dropped {name}.")
    return True


def _pack_manage_choices(ctx, slot: str, options):
    """Build the armor-slot pack choices (tiered names coloured)."""
    return tuple(
        (
            name, f"PACK_SWAP:armor:{slot}:{index}",
            _pack_option_runs(ctx, index),
        )
        for index, name, _detail in options
    )


def _pack_option_runs(ctx, pack_index: int):
    """Runs colouring one swap option's tiered name, if the entry still
    resolves."""
    try:
        return _pack_entry_runs(ctx.ground_expedition_inventory[pack_index])[1]
    except (IndexError, KeyError, TypeError, ValueError):
        return None


async def _swap_from_pack(ctx: GameContext, action: str) -> bool:
    """Route one equipment-row action: weapon groups or armor slots."""
    from . import pygame_story

    _prefix, item_type, rest = action.split(":", 2)
    if item_type == "weapon":
        parts = rest.split(":")
        member_index = int(parts[1]) if len(parts) > 1 else None
        return await _manage_weapon_set_member(ctx, parts[0], member_index)
    options = _swap_options(ctx, rest)
    if not options:
        ctx.log.add("No compatible items are in your Expedition Pack.")
        return False
    chosen = await pygame_story.choose(
        ctx,
        title="EXPEDITION PACK",
        body=f"Manage {rest.title()} armor.",
        options=_pack_manage_choices(ctx, rest, options),
        caption="spacehack - expedition equipment",
        compact=True,
    )
    if chosen in {None, "__BACK__", "__DISMISS__", "__GUIDE__"}:
        return False
    if chosen == "__QUIT__":
        raise SystemExit
    pack_index = int(chosen.rsplit(":", 1)[1])
    return _swap_pack_entry(ctx, "armor", rest, pack_index)


async def _run_pygame_character_screen(
    ctx: GameContext,
    *,
    equipment_management: bool = False,
    in_ground_combat: bool = False,
    floor_available: bool = True,
) -> int | None:
    """Run Character through the shared Pygame screen."""
    from . import pygame_screen, pygame_split

    tab = 0
    selected = 0
    swap_count = 0
    while True:
        frame = _character_frame(
            ctx, tab, selected,
            equipment_management=equipment_management,
            in_ground_combat=in_ground_combat,
            floor_available=floor_available,
            swap_allowed=(
                not in_ground_combat
                or _combat_ap_available(ctx, reserved=swap_count)
            ),
        )
        runner = (
            pygame_split.run_for_screen
            if isinstance(frame, pygame_split.SplitFrame)
            else pygame_screen.run_for_context
        )
        outcome, action, selected = await runner(
            ctx.context, frame, caption="spacehack - character",
        )
        tab, selected, swap_count, done = await _advance_character_screen(
            ctx, outcome, action, tab, selected, swap_count,
            equipment_management=equipment_management,
            in_ground_combat=in_ground_combat,
            floor_available=floor_available,
        )
        if done:
            return swap_count


async def _advance_character_screen(
    ctx: GameContext,
    outcome: str,
    action: str,
    tab: int,
    selected: int,
    swap_count: int,
    *,
    equipment_management: bool,
    in_ground_combat: bool,
    floor_available: bool = True,
) -> tuple[int, int, int, bool]:
    """Advance one loop iteration; return ``(tab, selected, swap_count, done)``."""
    if outcome == "GUIDE":
        from .help import _open_context_guide
        await _open_context_guide(ctx, "Character & Skills")
        return tab, selected, swap_count, False
    if outcome == "TAB":
        return (tab + 1) % 3, 0, swap_count, False
    if outcome == "SHIFT_TAB":
        return (tab - 1) % 3, 0, swap_count, False
    if outcome == "SELECT":
        if tab == 2:
            from .trade import _apply_jettison
            if await _apply_jettison(ctx, ctx.player_owned_ship, action):
                return tab, selected, swap_count, False
            return tab, selected, swap_count, True
        swap_count, should_return = await _apply_character_select(
            ctx, action, tab, swap_count,
            equipment_management=equipment_management,
            in_ground_combat=in_ground_combat,
            floor_available=floor_available,
        )
        return tab, selected, swap_count, should_return
    if outcome in {"PAGE_UP", "PAGE_DOWN"}:
        return tab, selected, swap_count, False
    if outcome == "QUIT":
        raise SystemExit
    return tab, selected, swap_count, True


async def _apply_equipment_select(
    ctx: GameContext,
    action: str,
    swap_count: int,
    *,
    in_ground_combat: bool,
    floor_available: bool = True,
) -> tuple[int, bool]:
    """Apply one Equipment-tab selection; every equipment change
    through C costs 1 AP mid-combat (SETTLED 3, uniform)."""
    if action.startswith("SWAP:") and await _swap_from_pack(ctx, action):
        return swap_count + 1, in_ground_combat
    if action.startswith("PACK_ITEM:"):
        _pack_result = await _manage_pack_item(
            ctx,
            action,
            swap_allowed=(
                not in_ground_combat
                or _combat_ap_available(ctx, reserved=swap_count)
            ),
            floor_available=floor_available,
        )
        if _pack_result == "EQUIP" and in_ground_combat:
            return swap_count + 1, True
    if action.startswith("PACK_STACK:"):
        _pack_result = await _manage_pack_stack(
            ctx, action, in_ground_combat=in_ground_combat,
            floor_available=floor_available,
        )
        if _pack_result == "USE" and in_ground_combat:
            return swap_count, True
    return swap_count, False


async def _apply_character_select(
    ctx: GameContext,
    action: str,
    tab: int,
    swap_count: int,
    *,
    equipment_management: bool,
    in_ground_combat: bool,
    floor_available: bool = True,
) -> tuple[int, bool]:
    from .xp import _apply_skill_point

    if tab == 0 and action.startswith("SPEND:"):
        skill = action.split(":", 1)[1]
        if skill in _SKILLS:
            _apply_skill_point(ctx, skill)
        return swap_count, False
    if tab == 1 and equipment_management:
        return await _apply_equipment_select(
            ctx, action, swap_count,
            in_ground_combat=in_ground_combat,
            floor_available=floor_available,
        )
    return swap_count, False

def _combat_ap_available(ctx: GameContext, *, reserved: int = 0) -> bool:
    """Return whether an active ground combat session has AP to spend."""
    from .combat import _rules_ground

    return _rules_ground.player_ap(ctx) > reserved


async def open_character_screen(
    ctx: GameContext,
    *,
    equipment_management: bool = False,
    in_ground_combat: bool = False,
    floor_available: bool = True,
) -> int:
    """Open the Character screen and return successful swap count."""
    result = await _run_pygame_character_screen(
        ctx,
        equipment_management=equipment_management,
        in_ground_combat=in_ground_combat,
        floor_available=floor_available,
    )
    if result is None:
        raise RuntimeError("Character screen returned no outcome")
    return result


# Stats/cargo builders and skill tables live in the sibling module
# (ratchet split); re-exported so every caller keeps
# character_screen.* import paths.
from .character_screen_stats import (  # noqa: F401 — re-export surface
    _cargo_character_frame,
    _expedition_capacity,
    _expedition_used_slots,
    _SKILLS,
    _skill_base,
    _skill_spend_marker,
    _skill_value_display,
    _SKILL_DESCRIPTIONS,
    _stats_frame,
    _trait_names,
)
