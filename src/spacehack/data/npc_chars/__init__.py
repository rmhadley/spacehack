"""NPC character catalog — ground-combat NPC templates with faction linkage.

Mirrors ``data/npc_ships/`` but for foot soldiers rather than ships.
Each :class:`NpcCharSpec` has a ``faction`` field so hostility is
determined by faction reputation rather than a hardcoded flag —
exactly how :class:`NpcShipSpec` works for space combat.

Adding a new NPC character is one entry in an ``NPC_CHARS`` tuple
in any submodule — no if/else chains, no registry edits.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NpcCharSpec:
    """One ground-combat NPC character template.

    Fields mirror :class:`NpcShipSpec` where applicable. The ``faction``
    field is the primary hostility driver — callers look up
    ``faction.get_attitude(ctx.faction_reputation[faction])`` to
    decide whether this NPC is hostile, neutral, or allied.

    Attributes:
        id: registry key, e.g. ``pirate_raider``.
        name: display name shown in combat HUD.
        char: glyph on the dungeon map, e.g. ``r``.
        fg: foreground colour tuple.
        faction: ``"pirate"`` | ``"merchant"`` | ``"civilian"`` |
            ``"militia"`` — links to faction reputation for hostility.
        hp: base HP before stamina bonus (total = ``hp + stamina // 3``).
        weapons: ground weapon ids the NPC always carries.
        weapon_pick: ground weapon ids for RNG selection at spawn time.
        reflexes: hit/dodge stat (0-100), used in hit-chance formula.
        strength: melee damage bonus stat (0-100).
        stamina: HP bonus stat (0-100).
        detect_radius: Chebyshev distance — triggers combat when player
            enters range AND has line-of-sight.
        loot_pool: trade good ids the NPC may drop on death.
        loot_count: (min, max) number of loot items per kill.
        xp_reward: XP awarded on kill.
        always_hostile: True = ignore faction reputation entirely;
            combat on sight (used for dungeon monsters — non-sentient
            creatures/drones that never grant or cost faction rep).
        behavior: out-of-combat movement mode — ``"hunter"`` patrols
            the map, ``"ambusher"`` holds still until the player gets
            close, ``"guard"`` holds a position without roaming.
        squad_size: (min, max) squad members when procedurally
            spawned (dungeon population / layout ENEMY scatter).
    """
    id: str
    name: str
    char: str
    fg: tuple[int, int, int]
    faction: str
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
    always_hostile: bool = False
    behavior: str = "hunter"
    squad_size: tuple[int, int] = (1, 1)


# ---------------------------------------------------------------------------
# Lazy-built registry (auto-discover via package iteration)
# ---------------------------------------------------------------------------

_BY_ID: dict[str, NpcCharSpec] | None = None


def _build_registry() -> dict[str, NpcCharSpec]:
    """Auto-discover all NPC char modules under this package."""
    import importlib, pkgutil
    combined: dict[str, NpcCharSpec] = {}
    for _finder, name, _ispkg in pkgutil.iter_modules(__path__):
        if name.startswith("_"):
            continue
        mod = importlib.import_module(f"{__name__}.{name}")
        if hasattr(mod, "NPC_CHARS"):
            for spec in mod.NPC_CHARS:
                combined[spec.id] = spec
    return combined


def _registry() -> dict[str, NpcCharSpec]:
    global _BY_ID
    if _BY_ID is None:
        _BY_ID = _build_registry()
    return _BY_ID


def find_npc_char(char_id: str) -> NpcCharSpec:
    """Look up a :class:`NpcCharSpec` by id; raises :class:`KeyError` on miss."""
    try:
        return _registry()[char_id]
    except KeyError:
        raise KeyError(f"unknown npc char id: {char_id!r}") from None
