"""Class catalog: playable classes for character creation.

Each class is a frozen :class:`GameClass` dataclass. Adding a new
class is one entry in the :data:`_CLASS_TUPLES` list (or a new file
under this package) - no if/else chains, no dispatcher rewrites.
The lookup helpers below read all gameplay numbers straight off the
spec.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..pilot_skills import PilotSkills, GroundStats


@dataclass(frozen=True)
class GameClass:
    """A playable class.

    Attributes:
        id: registry key, e.g. ``\"pirate\"``.
        name: display name shown in the class-pick menu.
        description: one-line flavour line under the name.
        hp_base: starting HP that this class sets before the picked
            species adds its :attr:`spacehack.data.species.Species.hp_bonus`.
        credits: starting credits this class grants on a new game.
        skill_bonus: per-skill additive bonuses added at character
            creation (see :func:`spacehack.character.starting_pilot_skills`).
        ground_bonus: per-stat additive bonuses for ground combat
            (see :func:`spacehack.character.starting_ground_stats`).
    """
    id: str
    name: str
    description: str
    hp_base: int = 10
    credits: int = 1000
    skill_bonus: PilotSkills = PilotSkills()
    ground_bonus: GroundStats = GroundStats()


# Per-file class tuples — append an import + line in
# ``_build_registry`` when adding a new file (mirrors how
# ``data/weapons/__init__.py`` picks up new weapon modules).
# Order is preserved as menu order (see ``list_classes``).


def _build_registry() -> dict[str, "GameClass"]:
    from . import core as core_module
    combined: dict[str, GameClass] = {}
    for cls in core_module.CLASSES:
        combined[cls.id] = cls
    return combined


_BY_ID: dict[str, GameClass] | None = None


def _registry() -> dict[str, GameClass]:
    global _BY_ID
    if _BY_ID is None:
        _BY_ID = _build_registry()
    return _BY_ID


def find_class(class_id: str) -> GameClass:
    """Look up a :class:`GameClass` by id; raises :class:`KeyError` on miss."""
    try:
        return _registry()[class_id]
    except KeyError:
        raise KeyError(f"unknown class id: {class_id!r}") from None


def list_classes() -> tuple[GameClass, ...]:
    """All registered classes, in registration (menu) order."""
    return tuple(_registry().values())


__all__ = ["GameClass", "find_class", "list_classes"]
