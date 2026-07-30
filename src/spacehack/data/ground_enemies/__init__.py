"""Ground combat enemy catalog — hostile NPCs for dungeon boarding.

Each enemy is a frozen :class:`GroundEnemySpec` dataclass, distinct
from space NPC ships (NpcShipSpec). Ground enemies use ground-combat
stats (reflexes/strength/stamina) and carry GroundWeaponSpec weapons.

Adding a new enemy is one entry in a WARES tuple — no if/else chains.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GroundEnemySpec:
    """One ground-combat enemy type.

    Attributes:
        id: registry key, e.g. ``derelict_scavenger``.
        name: display name, e.g. ``Derelict Scavenger``.
        char: glyph on the dungeon map, e.g. ``s``.
        fg: foreground colour tuple.
        hp: base HP (before stamina bonus).
        weapons: tuple of GroundWeaponSpec ids the enemy always carries.
        weapon_pick: tuple of GroundWeaponSpec ids for RNG selection
            (picks one per spawn).
        reflexes: base hit/dodge stat (0-100).
        strength: base melee damage stat (0-100).
        stamina: base HP stat (hp = base_hp + stamina * 2).
        detect_radius: cells — triggers combat when player enters range.
        loot_pool: good_ids the enemy may drop on death.
        loot_count: (min, max) number of loot items per kill.
        xp_reward: XP awarded on kill.
    """
    id: str
    name: str
    char: str
    fg: tuple[int, int, int]
    hp: int = 20
    weapons: tuple[str, ...] = ()
    weapon_pick: tuple[str, ...] = ()
    reflexes: int = 10
    strength: int = 10
    stamina: int = 10
    detect_radius: int = 4
    loot_pool: tuple[str, ...] = ()
    loot_count: tuple[int, int] = (1, 2)
    xp_reward: int = 20


# ---------------------------------------------------------------------------
# Lazy-built registry
# ---------------------------------------------------------------------------

_BY_ID: dict[str, GroundEnemySpec] | None = None


def _build_registry() -> dict[str, GroundEnemySpec]:
    """Auto-discover all ground-enemy modules under this package."""
    import importlib, pkgutil
    combined: dict[str, GroundEnemySpec] = {}
    for _finder, name, _ispkg in pkgutil.iter_modules(__path__):
        if name.startswith("_"):
            continue
        mod = importlib.import_module(f"{__name__}.{name}")
        if hasattr(mod, "WARES"):
            for w in mod.WARES:
                combined[w.id] = w
    return combined


def _registry() -> dict[str, GroundEnemySpec]:
    global _BY_ID
    if _BY_ID is None:
        _BY_ID = _build_registry()
    return _BY_ID


def find_ground_enemy(enemy_id: str) -> GroundEnemySpec:
    """Look up a :class:`GroundEnemySpec` by id; raises :class:`KeyError` on miss."""
    try:
        return _registry()[enemy_id]
    except KeyError:
        raise KeyError(f"unknown ground enemy id: {enemy_id!r}") from None


def list_ground_enemies() -> tuple[GroundEnemySpec, ...]:
    """All registered ground enemies, in undefined order."""
    return tuple(_registry().values())
