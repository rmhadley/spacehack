"""Character data model: species and class catalogs for character creation.

For now all species and classes are **cosmetic** - they affect the menu the
player sees at the start of a new game but carry no stat or ability bonus
yet. The data model below is shaped so that gameplay effects (starting
stats, abilities, equipment) can be added to ``Species`` / ``GameClass``
later without breaking the menus that consume them.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Species:
    """A playable species."""
    id: str
    name: str
    description: str


@dataclass(frozen=True)
class GameClass:
    """A playable class."""
    id: str
    name: str
    description: str


# The two starting species. Frozen tuples so callers can't accidentally
# mutate the catalog at runtime; iteration order is the menu order.
SPECIES: tuple[Species, ...] = (
    Species(
        id="human",
        name="Human",
        description="Native to Earth. Versatile and adaptable.",
    ),
    Species(
        id="martian",
        name="Martian",
        description="Native to Mars. Hardy in extremes, adapted to low-gravity.",
    ),
)


# The three starting classes.
CLASSES: tuple[GameClass, ...] = (
    GameClass(
        id="pirate",
        name="Pirate",
        description="Lives beyond the law. Plunders and pillages.",
    ),
    GameClass(
        id="merchant",
        name="Merchant",
        description="Trades goods across the systems.",
    ),
    GameClass(
        id="bounty_hunter",
        name="Bounty Hunter",
        description="Hunts the wanted. Paid in credits.",
    ),
)


def find_species(species_id: str) -> Species:
    """Look up a ``Species`` by id. Raises :class:`KeyError` if unknown."""
    for sp in SPECIES:
        if sp.id == species_id:
            return sp
    raise KeyError(f"unknown species id: {species_id!r}")


def find_class(class_id: str) -> GameClass:
    """Look up a ``GameClass`` by id. Raises :class:`KeyError` if unknown."""
    for cls in CLASSES:
        if cls.id == class_id:
            return cls
    raise KeyError(f"unknown class id: {class_id!r}")


# ---------------------------------------------------------------------------
# Pilot skills (used in space combat)
# ---------------------------------------------------------------------------


@dataclass
class PilotSkills:
    """Per-pilot combat skill ratings (0-100).

    ``gunnery`` affects weapon accuracy.
    ``piloting`` affects AP per turn and dodge bonus.
    ``engineering`` affects power efficiency and shield recharge.
    """
    gunnery: int = 30
    piloting: int = 30
    engineering: int = 30


SPECIES_SKILL_BONUSES: dict[str, dict[str, int]] = {
    "human":   {"gunnery": 5,  "piloting": 0,  "engineering": 5},
    "martian": {"gunnery": 5,  "piloting": 10, "engineering": 5},
}


CLASS_SKILL_BONUSES: dict[str, dict[str, int]] = {
    "pirate":        {"gunnery": 15, "piloting": 10, "engineering": 0},
    "merchant":      {"gunnery": 0,  "piloting": 5,  "engineering": 15},
    "bounty_hunter": {"gunnery": 10, "piloting": 10, "engineering": 5},
}


def starting_pilot_skills(species_id: str, class_id: str) -> PilotSkills:
    """Compute starting PilotSkills for a (species, class) combo."""
    sp_bonus = SPECIES_SKILL_BONUSES.get(species_id, {})
    cl_bonus = CLASS_SKILL_BONUSES.get(class_id, {})
    return PilotSkills(
        gunnery=30 + sp_bonus.get("gunnery", 0) + cl_bonus.get("gunnery", 0),
        piloting=30 + sp_bonus.get("piloting", 0) + cl_bonus.get("piloting", 0),
        engineering=30 + sp_bonus.get("engineering", 0) + cl_bonus.get("engineering", 0),
    )


def format_combo(species: Species, klass: GameClass) -> str:
    """Render the picked combo as a single human-readable string."""
    return f"{species.name} {klass.name}"


# ---------------------------------------------------------------------------
# Cosmetic starting stats
# ---------------------------------------------------------------------------
#
# These tables tie the species + class the player picked through character
# creation to the numbers the HUD shows on the city screen. They are
# cosmetic only - they don't affect gameplay yet. Martian gets a small
# HP bonus; combat classes (pirate + bounty hunter) start tougher; the
# merchant starts weaker but richer. Unknown ids fall through to safe
# defaults so future save/load code never crashes on a stale id.

_SPECIES_HP_BONUS: dict[str, int] = {
    "human": 0,
    "martian": 1,
}

_CLASS_HP_BASE: dict[str, int] = {
    "pirate": 9,
    "merchant": 7,
    "bounty_hunter": 10,
}

_CLASS_GOLD: dict[str, int] = {
    "pirate": 100,
    "merchant": 180,
    "bounty_hunter": 70,
}


def starting_stats(species_id: str, class_id: str):
    """Compute the starting :class:`spacehack.hud.HudStats` for a
    (species, class) combination.

    Cosmetic differentiation only - nothing on the HUD actually
    affects gameplay yet. The :class:`spacehack.hud.HudStats` returned
    has ``hp == max_hp`` so the bar reads as full health.
    """
    # Local import avoids any chance of a module-load circular dep if
    # hud.py ever starts importing back from character.
    from .hud import HudStats
    hp = (_CLASS_HP_BASE.get(class_id, 10)
          + _SPECIES_HP_BONUS.get(species_id, 0))
    gold = _CLASS_GOLD.get(class_id, 100)
    return HudStats(hp=hp, max_hp=hp, gold=gold)
