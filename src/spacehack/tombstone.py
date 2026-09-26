"""Tombstones — the death-review morgue file (doc 53).

One plain-text artifact per DEFEAT, written beside the autosave:
character, kit, circumstances, and the complete message log (the
roguelike morgue standard). The section builders are pure — no I/O,
no mutation; :func:`write_tombstone` is the thin filesystem shell
whose failure never blocks the death path (best-effort, SETTLED 1).
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .saveload import _saves_dir

_RULE = "=" * 48
_UNKNOWN_KILLER = "unknown causes"
# The death-screen notice's wrap width: the shared frame centers body
# text on the logical surface, so a HOME-heavy full path wraps rather
# than running off the seam (doc 53 ADVISE long-path note).
_NOTICE_WIDTH = 90


@dataclass(frozen=True)
class TombstoneFacts:
    """Combat-side facts only the shared finish can resolve.

    ``killer`` is the tracked last-attacker label (``None`` renders
    the settled fallback line); ``final_state`` is the one-line ground
    HP/AP or space hull/shields readout at death.
    """

    killer: str | None = None
    final_state: str = ""


def notice_lines(path: str) -> tuple[str, ...]:
    """The death-screen notice naming the FULL filename (SETTLED 1),
    wrapped at the frame seam when the path alone would overflow."""
    notice = f"Tombstone saved: {path}"
    if len(notice) <= _NOTICE_WIDTH:
        return (notice,)
    return ("Tombstone saved:", *textwrap.wrap(path, _NOTICE_WIDTH))


def result_notice_lines(result) -> tuple[str, ...]:
    """The death-screen lines for a finished fight's result: the
    tombstone notice when a file landed, else nothing (the frame's
    default lines stand)."""
    if not result.tombstone_path:
        return ()
    return notice_lines(result.tombstone_path)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------


def _location_name(ctx) -> str:
    """Where the run ended: the map's own name, else the city when the
    map IS a city (``city_transit`` marks city maps and nothing else,
    so a space death can never print a stale city), else nothing."""
    location = getattr(ctx.game_map, "location_name", "")
    if not location and getattr(ctx.game_map, "city_transit", None) is not None:
        return ctx.current_city_id.replace("_", " ").title()
    return location


def _header_lines(ctx, facts: TombstoneFacts, now: datetime) -> list[str]:
    from . import solar_system
    from .engine import INIT_SEED

    system = solar_system.current_system().name
    location = _location_name(ctx)
    where = f"{system} / {location}" if location else system
    counters = ctx.player_counters
    return [
        _RULE,
        f"  {ctx.character_info['species_name']}"
        f" {ctx.character_info['class_name']}",
        f"  Level {ctx.player_level} — died {now:%Y-%m-%d %H:%M}",
        f"  {ctx.time_day}/{ctx.time_month}/{ctx.time_year} — {where}",
        f"  Slain by: {facts.killer or _UNKNOWN_KILLER}",
        f"  Damage taken (career): space {counters.total_damage_taken},"
        f" ground {counters.ground_damage_taken}",
        f"  Run seed: {INIT_SEED}",
        f"  Final state: {facts.final_state}",
        _RULE,
    ]


# ---------------------------------------------------------------------------
# The sheet
# ---------------------------------------------------------------------------


def _lookup(finder, key):
    """One catalog lookup; a stale save key degrades to ``None`` so
    the morgue write never crashes on unknown content ids."""
    try:
        return finder(key)
    except KeyError:
        return None


def _trait_names(ctx) -> str:
    """Trait display names; a stale save id degrades to the raw id."""
    from .data.traits.core import trait_name

    names = []
    for trait_id in ctx.player_traits:
        name = _lookup(trait_name, trait_id)
        names.append(name if name is not None else trait_id)
    return ", ".join(names) or "None"


def _char_lines(ctx) -> list[str]:
    from . import xp

    level = ctx.player_level
    current = max(0, ctx.player_xp - xp.xp_for_level(level))
    return [
        "  CHAR",
        f"  Level {level}   XP {current}/{xp._xp_to_next(level)}",
        f"  Pilot skills: gunnery {ctx.stats.gunnery},"
        f" piloting {ctx.stats.piloting},"
        f" engineering {ctx.stats.engineering}",
        f"  Ground stats: reflexes {ctx.ground_stats.reflexes},"
        f" strength {ctx.ground_stats.strength},"
        f" stamina {ctx.ground_stats.stamina}",
        f"  Traits: {_trait_names(ctx)}",
    ]


# ---------------------------------------------------------------------------
# The kit
# ---------------------------------------------------------------------------


def _catalog_label(item_type: str, item_id: str, quality: int = 0) -> str:
    """Ground item label through the display seam; a stale save id
    degrades to the raw id so the write never crashes."""
    from .ground_equipment import display_name

    try:
        return display_name(item_type, item_id, quality)
    except KeyError:
        return item_id


def _loaded_suffix(capacity: int, loaded: int | None) -> str:
    """``" [n/cap]"`` for a finite magazine (unspecified reads full)."""
    if capacity <= 0:
        return ""
    return f" [{loaded if loaded is not None else capacity}/{capacity}]"


def _ground_weapon_line(instance) -> str:
    from .data.ground_weapons import find_ground_weapon

    label = _catalog_label("weapon", instance.weapon_id, instance.quality)
    spec = _lookup(find_ground_weapon, instance.weapon_id)
    capacity = spec.ammo_capacity if spec is not None else 0
    return label + _loaded_suffix(capacity, instance.loaded_ammo)


def _armor_line(ctx) -> str:
    from .ground_equipment import ARMOR_SLOT_LABELS, ARMOR_SLOTS

    parts = []
    for slot in ARMOR_SLOTS:
        entry = ctx.equipped_ground_armor.get(slot)
        name = (
            _catalog_label("armor", entry.item_id, entry.quality)
            if entry else "none"
        )
        parts.append(f"{ARMOR_SLOT_LABELS[slot]} {name}")
    return "  Armor: " + ", ".join(parts)


def _caliber_name(ammo_type: str) -> str:
    from . import bandolier

    spec = bandolier._spec_by_ammo_type().get(ammo_type)
    return spec.name if spec is not None else ammo_type


def _ammo_line(ctx) -> str:
    carried = getattr(ctx, "bandolier", None) or {}
    rounds = ", ".join(
        f"{_caliber_name(ammo_type)} {count}"
        for ammo_type, count in sorted(carried.items())
        if count > 0
    )
    return f"  Ammo: {rounds or 'empty'}"


def _stack_label(stack) -> str:
    from .data.ground_items import (
        find_ground_ammo,
        find_ground_consumable,
    )

    finder = (
        find_ground_ammo if stack.item_type == "ammo" else find_ground_consumable
    )
    spec = _lookup(finder, stack.item_id)
    return spec.name if spec is not None else stack.item_id


def _pack_line(ctx) -> str:
    equipment = ", ".join(
        _catalog_label(entry.item_type, entry.item_id, entry.quality)
        for entry in getattr(ctx, "ground_expedition_inventory", ())
    )
    stacks = ", ".join(
        f"{_stack_label(stack)} x{stack.quantity}"
        for stack in getattr(ctx, "ground_expedition_items", ())
    )
    carried = ", ".join(part for part in (equipment, stacks) if part)
    return f"  Expedition pack: {carried or 'empty'}"


def _ship_lines(owned) -> list[str]:
    from . import ship as ship_module
    from .data.weapons import find_weapon

    name = owned.display_name or ship_module.find_ship(owned.ship_id).name
    weapons = ", ".join(
        ship_module.weapon_display_name(weapon_id)
        + _loaded_suffix(
            find_weapon(weapon_id).ammo_capacity,
            owned.weapon_ammo.get(index),
        )
        for index, weapon_id in enumerate(owned.weapons)
    ) or "none"
    modules = ", ".join(
        ship_module.module_display_name(
            module.item_id, module.quality, module.randart_seed,
        )
        for module in owned.modules
    ) or "none"
    return [
        f"  SHIP: {name}",
        f"    Weapons: {weapons}",
        f"    Modules: {modules}",
    ]


def _gear_lines(ctx) -> list[str]:
    lines = ["  GEAR"]
    for label, instances in (
        ("ACTIVE SET", getattr(ctx, "equipped_ground_weapons", ()) or ()),
        ("HOLSTERED SET", getattr(ctx, "holstered_ground_weapons", ()) or ()),
    ):
        names = ", ".join(_ground_weapon_line(i) for i in instances) or "none"
        lines.append(f"  {label}: {names}")
    lines.append(_armor_line(ctx))
    lines.append(_ammo_line(ctx))
    lines.append(_pack_line(ctx))
    owned = getattr(ctx, "player_owned_ship", None)
    if owned is not None:
        lines.extend(_ship_lines(owned))
    return lines


# ---------------------------------------------------------------------------
# The log + composition
# ---------------------------------------------------------------------------


def _log_lines(log) -> list[str]:
    """The complete run log, oldest first — plain text only (any
    inline colour runs drop with the entry's text read)."""
    return [
        "  --- MESSAGE LOG (full, oldest first) ---",
        *(f"  {entry.text}" for entry in log.history()),
    ]


def build_tombstone_text(ctx, facts: TombstoneFacts) -> str:
    """Compose the morgue file: header, sheet, kit, full log."""
    sections = (
        _header_lines(ctx, facts, datetime.now()),
        _char_lines(ctx),
        _gear_lines(ctx),
        _log_lines(ctx.log),
    )
    return "\n\n".join("\n".join(lines) for lines in sections) + "\n"


# ---------------------------------------------------------------------------
# The filesystem shell
# ---------------------------------------------------------------------------


def _unique_path(directory: Path, stamp: str) -> Path:
    """First free filename: the plain stamp, then -2, -3, ... — two
    deaths inside one second never overwrite each other."""
    candidate = directory / f"tombstone-{stamp}.txt"
    suffix = 2
    while candidate.exists():
        candidate = directory / f"tombstone-{stamp}-{suffix}.txt"
        suffix += 1
    return candidate


def write_tombstone(ctx, facts: TombstoneFacts) -> str | None:
    """Write the morgue file under the real saves dir's ``tombstones/``.

    Returns the full path on success; any :class:`OSError` prints to
    the real console and returns ``None`` — best-effort by ruling, the
    death path is never blocked.
    """
    try:
        directory = _saves_dir() / "tombstones"
        directory.mkdir(parents=True, exist_ok=True)
        path = _unique_path(directory, datetime.now().strftime("%Y%m%d-%H%M%S"))
        path.write_text(build_tombstone_text(ctx, facts), encoding="utf-8")
        return str(path)
    except OSError as exc:
        print(f"Tombstone write failed: {exc}")
        return None
