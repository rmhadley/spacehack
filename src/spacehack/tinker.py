"""Tinker kits — raise one owned item's quality one tier (doc 47.5).

A kit is a stackable consumable used from the character screen's pack
manage modal: one CHOOSE TARGET list over EVERY eligible owned entry
(SETTLED 33) — equipped weapons and armor, pack gear, armory-warehouse
gear, ship-storage modules, installed modules. Eligibility is quality
alone (SETTLED 31): tiers 0-2, never a randart seed; prototype is the
ceiling, so t3 rows are filtered. One kit = +1 tier (SETTLED 32).
Quality is identity and stats are always derived, so a bump is a field
replace — nothing cached, nothing to invalidate.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from .data.quality import QUALITY_TOKENS

# SETTLED 31: kits cap at prototype — overclocked (quality 2) is the
# highest raisable tier; a Prototype item (quality 3) never appears.
MAX_RAISED_QUALITY: int = len(QUALITY_TOKENS) - 1

# SETTLED 36: the chooser is the teacher — this line only states the
# empty case, it never enumerates target types.
NO_TARGETS_LINE = "Nothing you own can be modified."


def _eligible(quality: int, randart_seed) -> bool:
    """True for one raisable entry: a non-randart tier below prototype."""
    return 0 <= quality <= MAX_RAISED_QUALITY and randart_seed is None


def _raised(entry):
    """One quality tier up, preserving every other field (pure)."""
    return dataclasses.replace(entry, quality=entry.quality + 1)


def _kit_log_line(label: str, new_quality: int) -> str:
    """The apply log line at its single seam (draft in the brief)."""
    token = QUALITY_TOKENS[new_quality - 1].title()
    return f"Tinker kit: {label} is now {token}."


def _ground_label(entry) -> str:
    from .ground_equipment import display_name

    return display_name(entry.item_type, entry.item_id, entry.quality)


def _weapon_label(instance) -> str:
    from .ground_equipment import display_name

    return display_name("weapon", instance.weapon_id, instance.quality)


def _module_label(entry) -> str:
    from .ship import module_display_name

    return module_display_name(entry.item_id, entry.quality, entry.randart_seed)


@dataclass(frozen=True)
class _Target:
    """One eligible kit target: its chooser row and its apply action."""

    key: str
    row: str
    apply: object


def _target(key: str, entry, label_of, apply) -> _Target:
    """Build one target: the preview row and the deferred bump share
    the same entry, so rows and applies can never drift apart."""
    return _Target(
        key,
        f"{label_of(entry)} -> {label_of(_raised(entry))}",
        apply,
    )


def _indexed_apply(entries: list, index: int, label_of):
    """Zero-arg apply: raise ``entries[index]``, return its log line."""
    def apply() -> str | None:
        entry = entries[index]
        if not _eligible(entry.quality, getattr(entry, "randart_seed", None)):
            return None
        line = _kit_log_line(label_of(entry), entry.quality + 1)
        entries[index] = _raised(entry)
        return line
    return apply


def _slotted_apply(mapping: dict, slot: str, label_of):
    """Zero-arg apply: raise ``mapping[slot]``, return its log line."""
    def apply() -> str | None:
        entry = mapping.get(slot)
        if entry is None or not _eligible(entry.quality, None):
            return None
        line = _kit_log_line(label_of(entry), entry.quality + 1)
        mapping[slot] = _raised(entry)
        return line
    return apply


def _installed_apply(owned, index: int, label_of):
    """Zero-arg apply: raise ``owned.modules[index]`` (a tuple field)."""
    def apply() -> str | None:
        modules = owned.modules
        if not 0 <= index < len(modules):
            return None
        entry = modules[index]
        if not _eligible(entry.quality, entry.randart_seed):
            return None
        line = _kit_log_line(label_of(entry), entry.quality + 1)
        raised = list(modules)
        raised[index] = _raised(entry)
        owned.modules = tuple(raised)
        return line
    return apply


def _weapon_targets(ctx) -> list[_Target]:
    instances = getattr(ctx, "equipped_ground_weapons", ())
    return [
        _target(
            f"KIT:WEAPON:{index}", instance, _weapon_label,
            _indexed_apply(ctx.equipped_ground_weapons, index, _weapon_label),
        )
        for index, instance in enumerate(instances)
        if _eligible(instance.quality, None)
    ]


def _armor_targets(ctx) -> list[_Target]:
    from .ground_equipment import ARMOR_SLOTS

    armor = getattr(ctx, "equipped_ground_armor", {})
    return [
        _target(
            f"KIT:ARMOR:{slot}", entry, _ground_label,
            _slotted_apply(ctx.equipped_ground_armor, slot, _ground_label),
        )
        for slot in ARMOR_SLOTS
        if (entry := armor.get(slot)) is not None
        and _eligible(entry.quality, None)
    ]


def _pack_targets(ctx) -> list[_Target]:
    entries = getattr(ctx, "ground_expedition_inventory", [])
    return [
        _target(
            f"KIT:PACK:{index}", entry, _ground_label,
            _indexed_apply(entries, index, _ground_label),
        )
        for index, entry in enumerate(entries)
        if entry.item_type in ("weapon", "armor")
        and _eligible(entry.quality, None)
    ]


def _armory_targets(ctx) -> list[_Target]:
    """The unlimited armory warehouse (doc 19) — the user's "stored
    items at the mechanic/armory" (SETTLED 33), a sixth container the
    phase-5 audit wrongly folded into the pack."""
    entries = getattr(ctx, "ground_armory_storage", [])
    return [
        _target(
            f"KIT:ARMORY_STORAGE:{index}", entry, _ground_label,
            _indexed_apply(entries, index, _ground_label),
        )
        for index, entry in enumerate(entries)
        if entry.item_type in ("weapon", "armor")
        and _eligible(entry.quality, None)
    ]


def _stored_targets(ctx) -> list[_Target]:
    entries = getattr(ctx, "ship_storage", [])
    return [
        _target(
            f"KIT:STORED:{index}", entry, _module_label,
            _indexed_apply(entries, index, _module_label),
        )
        for index, entry in enumerate(entries)
        if entry.item_type == "module" and _eligible(
            entry.quality, entry.randart_seed,
        )
    ]


def _installed_targets(ctx) -> list[_Target]:
    owned = getattr(ctx, "player_owned_ship", None)
    modules = owned.modules if owned is not None else ()
    return [
        _target(
            f"KIT:INSTALLED:{index}", entry, _module_label,
            _installed_apply(owned, index, _module_label),
        )
        for index, entry in enumerate(modules)
        if _eligible(entry.quality, entry.randart_seed)
    ]


def eligible_targets(ctx) -> tuple[_Target, ...]:
    """Every eligible owned entry across all six containers."""
    return (
        *_weapon_targets(ctx),
        *_armor_targets(ctx),
        *_pack_targets(ctx),
        *_armory_targets(ctx),
        *_stored_targets(ctx),
        *_installed_targets(ctx),
    )


def chooser_rows(targets) -> tuple[tuple[str, str], ...]:
    """The chooser options: one current -> next preview per target."""
    return tuple((target.row, target.key) for target in targets)


def _apply_chosen(ctx, index: int, targets, chosen) -> bool:
    """Apply the chosen target and consume one charge.

    Bump then consume: the six target containers are disjoint from
    the pack stack list, so a completed bump cannot invalidate the
    charge's own resolution — the reverse order would risk charging
    for a bump that failed re-validation.
    """
    from .ground_consumables import consume_kit_charge

    if chosen == "__QUIT__":
        raise SystemExit
    target = next((t for t in targets if t.key == chosen), None)
    if target is None:
        return False
    line = target.apply()
    if line is None or not consume_kit_charge(ctx, index):
        return False
    ctx.log.add(line)
    return True


async def try_manage_kit(ctx, index: int) -> bool | None:
    """The C-screen Use path for a tinker-kit stack (doc 47.5).

    Returns None when the stack isn't a kit (the caller falls through
    to the ordinary consumable use); True when a kit was applied;
    False when the use resolved without applying — nothing eligible,
    or the chooser was backed out. A charge is consumed only on a
    completed bump.
    """
    from . import pygame_story
    from .ground_consumables import is_tinker_kit, resolve_pack_consumable

    spec = resolve_pack_consumable(ctx, index)
    if spec is None or not is_tinker_kit(spec):
        return None
    targets = eligible_targets(ctx)
    if not targets:
        ctx.log.add(NO_TARGETS_LINE)
        return False
    chosen = await pygame_story.choose(
        ctx,
        title="TINKER KIT",
        body=spec.effect_label,
        options=chooser_rows(targets),
        caption="spacehack - tinker kit",
        compact=True,
    )
    return _apply_chosen(ctx, index, targets, chosen)
