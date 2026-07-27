"""NPC ship templates — unified catalog for all non-player ships.

Replaces ``data/enemies/``. Pirates, merchants, civilians, and future
militia all share a single :class:`NpcShipSpec` dataclass. Faction
field drives default attitude (pirate = hostile, merchant = neutral)
and supports future reputation-based flipping.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NpcShipSpec:
    """Static template for an NPC ship.

    Flat fields (no nested AIProfile/PilotSkills objects) so
    consumers in combat.py read them without import chains.

    Attributes:
        id: registry key, e.g. "pirate_scout".
        name: display name shown in combat HUD / comms.
        char / fg: glyph + colour on the solar system map.
        ship_id: hull reference (scout/hauler/cruiser).
        faction: "pirate" | "merchant" | "civilian" | "militia".
        weapons / modules: equipment fitted at spawn.
        cargo_goods: which trade goods this ship can carry
            (dropped on destruction for pirates, traded for merchants).
        cargo_count: how many unique goods to stock on spawn (0 = none).
        ai_aggressiveness: 0-100 chance to attack vs reposition.
        ai_preferred_range: AI tries to maintain this distance.
        ai_flee_threshold: hull % (0.0-1.0) below which AI flees.
        ai_accuracy_bonus / ai_dodge_bonus: per-difficulty modifiers.
        pilot_gunnery / pilot_piloting / pilot_engineering: skills.
        min_power_gen: base power per turn.
        detect_radius: cells before auto-engaging combat (0 = never).
        comms_range: cells within which player can hail via comms.
        comms_lines: flavour text for comms hail.
        base_speed: cells per movement tick.
    """
    id: str
    name: str
    char: str
    fg: tuple[int, int, int]
    ship_id: str
    faction: str

    # Equipment
    weapons: tuple[str, ...] = ()
    modules: tuple[str, ...] = ()

    # Cargo
    cargo_goods: tuple[str, ...] = ()
    cargo_count: int = 0

    # Combat
    ai_aggressiveness: int = 50
    ai_preferred_range: int = 3
    ai_flee_threshold: float = 0.15
    ai_accuracy_bonus: int = 0
    ai_dodge_bonus: int = 0
    pilot_gunnery: int = 20
    pilot_piloting: int = 20
    pilot_engineering: int = 10
    min_power_gen: int = 3
    detect_radius: int = 0

    # Comms / interaction
    # comms_range: cells within which the player can hail. The
    # viewport is ~80x54 cells, so 60 covers nearly everything visible
    # on screen. If it's on screen, it should be reachable.
    comms_range: int = 60
    comms_lines: tuple[str, ...] = ("Greetings, pilot.",)
    base_speed: int = 1


_BY_ID: dict[str, NpcShipSpec] | None = None


def _build_registry() -> dict[str, NpcShipSpec]:
    from . import core
    combined: dict[str, NpcShipSpec] = {}
    for spec in core.NPC_SHIPS:
        combined[spec.id] = spec
    return combined


def _registry() -> dict[str, NpcShipSpec]:
    global _BY_ID
    if _BY_ID is None:
        _BY_ID = _build_registry()
    return _BY_ID


def find_npc_ship(spec_id: str) -> NpcShipSpec:
    """Look up an NpcShipSpec by id; raises KeyError on miss."""
    try:
        return _registry()[spec_id]
    except KeyError:
        raise KeyError(f"unknown npc ship id: {spec_id!r}") from None
