"""Character helpers: formulas that combine the player-picked species
and class into runtime values for the HUD and combat init.

The data catalogs (species + class tuples, gameplay numbers) live in
:mod:`spacehack.data.species` and :mod:`spacehack.data.classes`. This
module is a thin layer above those catalogs that performs the
SPECIES + CLASS math (skill bonuses, HP, gold) and exposes
``starting_pilot_skills`` / ``starting_stats`` / ``format_combo``.

New species or classes only need edits in their data modules — the
formulas below read straight off the resolved spec dataclasses, so
the five scattered lookup dicts (``SPECIES_SKILL_BONUSES``,
``CLASS_SKILL_BONUSES``, ``_SPECIES_HP_BONUS``, ``_CLASS_HP_BASE``,
``_CLASS_GOLD``) are gone.
"""
from __future__ import annotations

from dataclasses import dataclass

from .data.species import find_species, list_species
from .data.classes import find_class, list_classes


# Base pilot-skill rating before species or class bonuses are added.
# Kept at module level (not on a dataclass field) so changing it
# retroactively re-tunes every existing pilot without touching data
# files. Mirrors the convention elsewhere in the project where
# tunable defaults live close to the formula.
PILOT_SKILL_BASE = 30


@dataclass
class PilotSkills:
    """Per-pilot combat skill ratings (0-100).

    ``gunnery`` affects weapon accuracy.
    ``piloting`` affects AP per turn and dodge bonus.
    ``engineering`` affects power efficiency and shield recharge.
    """
    gunnery: int = PILOT_SKILL_BASE
    piloting: int = PILOT_SKILL_BASE
    engineering: int = PILOT_SKILL_BASE


def starting_pilot_skills(species_id: str, class_id: str) -> PilotSkills:
    """Starting :class:`PilotSkills` for a (species, class) combo.

    Reads skill bonuses straight off the resolved spec dataclasses
    (see :attr:`spacehack.data.species.Species.skill_bonus` and
    :attr:`spacehack.data.classes.GameClass.skill_bonus`). Unknown
    ids fall through to the base pilot only — future iterations
    that hit an unrecognised species/class id (e.g. a stale save
    file) won't crash the formula.
    """
    # Resolved specs, with safe-empty fallbacks for stale ids.
    sp = _safe_lookup_species(species_id)
    cl = _safe_lookup_class(class_id)
    sp_skills = sp.skill_bonus if sp is not None else PilotSkills()
    cl_skills = cl.skill_bonus if cl is not None else PilotSkills()
    return PilotSkills(
        gunnery=PILOT_SKILL_BASE + sp_skills.gunnery + cl_skills.gunnery,
        piloting=PILOT_SKILL_BASE + sp_skills.piloting + cl_skills.piloting,
        engineering=PILOT_SKILL_BASE + sp_skills.engineering + cl_skills.engineering,
    )


def starting_stats(species_id: str, class_id: str):
    """Starting :class:`spacehack.hud.HudStats` for a (species, class).

    HP = ``class.hp_base + species.hp_bonus`` (cosmetic — read by
    HUD only, doesn't gate gameplay yet). Gold comes straight off
    the class spec. Pilot skills (gunnery, piloting, engineering)
    are computed from species + class bonuses applied on top of
    :data:`PILOT_SKILL_BASE`. Unknown ids fall through to safe
    defaults so a future save/load path that emits an unrecognised
    species or class id can't crash the HUD init.
    """
    # Local import avoids any chance of a module-load circular dep if
    # hud.py ever starts importing back from character.
    from .hud import HudStats
    sp = _safe_lookup_species(species_id)
    cl = _safe_lookup_class(class_id)
    hp_base = cl.hp_base if cl is not None else 10
    credits = cl.credits if cl is not None else 1000
    hp_bonus = sp.hp_bonus if sp is not None else 0
    
    # Compute pilot skills — reuse starting_pilot_skills internally
    # so the three skill values stay in sync with the combat init.
    skills = starting_pilot_skills(species_id, class_id)
    return HudStats(
        hp=hp_base + hp_bonus,
        max_hp=hp_base + hp_bonus,
        credits=credits,
        gunnery=skills.gunnery,
        piloting=skills.piloting,
        engineering=skills.engineering,
    )


def format_combo(species, klass) -> str:
    """Render the picked combo as a single human-readable string."""
    return f"{species.name} {klass.name}"


def _safe_lookup_species(species_id: str):
    """Resolve a species id without raising. Returns ``None`` on miss.

    The character's HUD / combat-init formulas are best-effort —
    a stale save file from a removed species shouldn't crash the
    game. Production callers (the picker UI) only emit ids that
    resolve successfully, so ``None`` is a defensive fallback for
    save-load / future-content paths.
    """
    try:
        return find_species(species_id)
    except KeyError:
        return None


def _safe_lookup_class(class_id: str):
    """Resolve a class id without raising. Returns ``None`` on miss.

    See :func:`_safe_lookup_species` for the rationale.
    """
    try:
        return find_class(class_id)
    except KeyError:
        return None


__all__ = [
    "PILOT_SKILL_BASE",
    "PilotSkills",
    "list_species",
    "list_classes",
    "starting_pilot_skills",
    "starting_stats",
    "format_combo",
]