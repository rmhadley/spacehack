"""NPC character catalog — ground-combat NPC templates with faction linkage.

Mirrors ``data/npc_ships/`` but for foot soldiers rather than ships.
Each :class:`NpcCharSpec` has a ``faction`` field so hostility is
determined by faction reputation rather than a hardcoded flag —
exactly how :class:`NpcShipSpec` works for space combat.

Ground identity families (doc 48 SETTLED 34, the
:data:`CHAR_CLASS_FAMILIES` table): one LETTER per family, members
are case variants of it (lowercase common / uppercase serious), ONE
consistent color per family — pirate `r`/`R` rust, militia `m` teal,
consortium `e`/`E` corporate blue, civilian `c`, machines `d`/`D`
bronze. The (glyph, color) PAIR is the identity — a char may repeat
across families when the colors separate. Fauna are not families:
species glyphs in biome palettes, bold apexes later (phase 10).

Adding a new NPC character is one entry in an ``NPC_CHARS`` tuple
in any submodule — no if/else chains, no registry edits.

Note: ``pirate_raider`` names a ground row HERE and a ship in
``data/npc_ships/`` — one pirate crew, two registries. Bare-id
consumers must know which registry they mean (``find_npc_char`` vs
``find_npc_ship``).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CharClassFamily:
    """One ground identity family (SETTLED 34).

    ``faction`` families recruit every spec carrying that faction;
    explicit ``members`` list ids for factionless families (the
    contemporary machines — fauna share ``faction=""`` but stay out).
    """

    letter: str
    color: tuple[int, int, int]
    faction: str = ""
    members: tuple[str, ...] = ()


CHAR_CLASS_FAMILIES: dict[str, CharClassFamily] = {
    "pirate": CharClassFamily(
        letter="r", color=(220, 120, 80), faction="pirate",
    ),
    "militia": CharClassFamily(
        letter="m", color=(130, 230, 220), faction="militia",
    ),
    "consortium": CharClassFamily(
        letter="e", color=(120, 160, 220), faction="consortium",
    ),
    "civilian": CharClassFamily(
        letter="c", color=(235, 215, 175), faction="civilian",
    ),
    "machine": CharClassFamily(
        letter="d", color=(200, 180, 110),
        members=("sentry_drone", "assault_drone"),
    ),
}


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
        char: glyph on the dungeon map, e.g. ``r`` — a case variant
            of the spec's family letter (SETTLED 34; see
            :data:`CHAR_CLASS_FAMILIES`).
        fg: the family's ONE color (SETTLED 34) — members render in
            the same family color exactly; fauna keep species
            palettes.
        faction: ``"pirate"`` | ``"merchant"`` | ``"militia"`` |
            ``"consortium"`` (hidden axis, doc 48) | ``"civilian"``
            (retired as a rep axis — an ambient-dressing accounting
            tag, SETTLED 8) — links to faction reputation for
            hostility.
        hp: base HP before stamina bonus (total = ``hp + stamina // 3``).
        weapons: ground weapon ids the NPC always carries.
        weapon_pick: ground weapon ids for RNG selection at spawn time.
        reflexes: hit/dodge stat (0-100), used in hit-chance formula.
        strength: melee damage bonus stat (0-100).
        stamina: HP bonus stat (0-100).
        detect_radius: Chebyshev distance — triggers combat when player
            enters range AND has line-of-sight.
        loot_pool: trade good ids the NPC may drop on death.
        equipment_loot_pool: optional ``(item_type, item_id)`` ground gear
            entries dropped on death.
        field_item_loot_pool: optional typed ammo/consumable entries dropped
            on death and packed into the Expedition Pack.
        loot_count: (min, max) number of trade-good loot items per kill.
        xp_reward: XP awarded on kill.
        always_hostile: True = ignore faction reputation entirely;
            combat on sight (used for dungeon monsters — non-sentient
            creatures/drones that never grant or cost faction rep).
        behavior: out-of-combat movement mode — ``"hunter"`` patrols
            the map, ``"ambusher"`` holds still until the player gets
            close, ``"guard"`` holds a position without roaming.
        squad_size: (min, max) squad members when procedurally
            spawned (dungeon population / layout ENEMY scatter).
        tier: drop tier — equipment drops filter to ``tech_level <= tier``.
        armor: flat damage reduction subtracted from player hits
            (plasma halves it).
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
    equipment_loot_pool: tuple[tuple[str, str], ...] = ()
    field_item_loot_pool: tuple[tuple[str, str], ...] = ()
    field_item_loot_count: tuple[int, int] = (0, 1)
    loot_count: tuple[int, int] = (1, 2)
    xp_reward: int = 20
    always_hostile: bool = False
    behavior: str = "hunter"
    squad_size: tuple[int, int] = (1, 1)
    tier: int = 1
    armor: int = 0


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


# Save-compat alias (doc 48 phase 3): pre-rename saves carry the
# misspelled bystander id in ``npc_char_id`` — resolve to the fixed id.
_ID_ALIASES = {"civillian_bystander": "civilian_bystander"}


def find_npc_char(char_id: str) -> NpcCharSpec:
    """Look up an :class:`NpcCharSpec` by id; raises :class:`KeyError` on miss."""
    char_id = _ID_ALIASES.get(char_id, char_id)
    try:
        return _registry()[char_id]
    except KeyError:
        raise KeyError(f"unknown npc char id: {char_id!r}") from None


def list_npc_chars() -> tuple[NpcCharSpec, ...]:
    """All registered specs, in registry order (the test/lint surface
    for catalog-wide assertions — sibling of ``list_npc_ships``)."""
    return tuple(_registry().values())
