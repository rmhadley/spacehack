"""Species catalog: playable species for character creation.

Each species is a frozen :class:`Species` dataclass. Adding a new
species is one entry in the :data:`_SPECIES_TUPLES` list (or a new
file under this package) - no if/else chains, no dispatcher
rewrites. The lookup helpers below read all gameplay numbers
straight off the spec.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Species:
    """A playable species.

    Attributes:
        id: registry key, e.g. ``\"human\"``.
        name: display name shown in the species-pick menu.
        description: one-line flavour line under the name.
        hp_bonus: additive HP bonus granted by this species on top
            of the class's :attr:`spacehack.data.classes.GameClass.hp_base`.
        skill_bonus: ``{gunnery, piloting, engineering}`` additive
            bonuses added at character creation (see
            :func:`spacehack.character.starting_pilot_skills`).
    """
    id: str
    name: str
    description: str
    hp_bonus: int = 0
    skill_bonus: dict[str, int] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.skill_bonus is None:
            object.__setattr__(self, "skill_bonus", {})


# Per-file species tuples — append an import + line in
# ``_build_registry`` when adding a new file (mirrors how
# ``data/weapons/__init__.py`` picks up new weapon modules).
# Order is preserved as menu order (see ``list_species``).


def _build_registry() -> dict[str, "Species"]:
    from . import core as core_module
    combined: dict[str, Species] = {}
    for sp in core_module.SPECIES:
        combined[sp.id] = sp
    return combined


_BY_ID: dict[str, Species] | None = None


def _registry() -> dict[str, Species]:
    global _BY_ID
    if _BY_ID is None:
        _BY_ID = _build_registry()
    return _BY_ID


def find_species(species_id: str) -> Species:
    """Look up a :class:`Species` by id; raises :class:`KeyError` on miss."""
    try:
        return _registry()[species_id]
    except KeyError:
        raise KeyError(f"unknown species id: {species_id!r}") from None


def list_species() -> tuple[Species, ...]:
    """All registered species, in registration (menu) order."""
    return tuple(_registry().values())


__all__ = ["Species", "find_species", "list_species"]
