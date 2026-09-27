"""Character helpers: formulas that combine the player-picked species
and class into runtime values for the HUD, combat init, and ground combat.

The data catalogs (species + class tuples, gameplay numbers) live in
:mod:`spacehack.data.species` and :mod:`spacehack.data.classes`. This
module is a thin layer above those catalogs that performs the
SPECIES + CLASS math (skill bonuses, HP, credits, ground stats) and
exposes ``starting_pilot_skills`` / ``starting_ground_stats`` /
``starting_stats`` / ``format_combo``.

New species or classes only need edits in their data modules — the
formulas below read straight off the resolved spec dataclasses.
"""
from __future__ import annotations

from dataclasses import dataclass

from .data.species import find_species, list_species
from .data.classes import find_class, list_classes
from .data.pilot_skills import GroundStats as _GroundStats


# Base pilot-skill rating before species or class bonuses are added.
# Kept at module level (not on a dataclass field) so changing it
# retroactively re-tunes every existing pilot without touching data
# files. Mirrors the convention elsewhere in the project where
# tunable defaults live close to the formula.
#
# A fresh character starts as a "nobody" on the 0-100 scale: the
# level cap (60) x 5 skill points per level = 295 points, which lets
# a dedicated L60 specialist max out 3 of the 6 stats. Starting at
# base 10 keeps the growth arc long and makes species/class bonuses
# (flagship +12) land as 2.5-3x the base.
PILOT_SKILL_BASE = 10

# Base ground-stat rating before species or class bonuses are added.
# All six skills (ship + ground) share the same 0-100 scale so the
# Character screen, skill points, and combat formulas stay symmetric.
GROUND_STAT_BASE = 10


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


@dataclass
class GroundStats:
    """Per-character ground combat stats (0-100).

    ``reflexes`` affects ranged accuracy and dodge bonus.
    ``strength`` affects melee damage and heavy-weapon efficiency.
    ``stamina`` affects HP pool and damage resistance.
    """
    reflexes: int = GROUND_STAT_BASE
    strength: int = GROUND_STAT_BASE
    stamina: int = GROUND_STAT_BASE


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


def starting_ground_stats(species_id: str, class_id: str) -> GroundStats:
    """Starting :class:`GroundStats` for a (species, class) combo.

    Reads stat bonuses straight off the resolved spec dataclasses
    (see :attr:`spacehack.data.species.Species.ground_bonus` and
    :attr:`spacehack.data.classes.GameClass.ground_bonus`). Unknown
    ids fall through to the base stat only.
    """
    sp = _safe_lookup_species(species_id)
    cl = _safe_lookup_class(class_id)
    sp_bonus = sp.ground_bonus if sp is not None else _GroundStats()
    cl_bonus = cl.ground_bonus if cl is not None else _GroundStats()
    return GroundStats(
        reflexes=GROUND_STAT_BASE + sp_bonus.reflexes + cl_bonus.reflexes,
        strength=GROUND_STAT_BASE + sp_bonus.strength + cl_bonus.strength,
        stamina=GROUND_STAT_BASE + sp_bonus.stamina + cl_bonus.stamina,
    )


def species_hp_bonus(species_id: str) -> int:
    """The species layer's ground-HP bonus (doc 49 SETTLED 3-A).

    Folds into the ground max-HP formula (see
    :func:`spacehack.xp.ground_max_hp_total`); hull HP is class-only.
    Unknown ids (stale saves) read as 0.
    """
    sp = _safe_lookup_species(species_id)
    return sp.hp_bonus if sp is not None else 0


def species_appearance(species_id: str) -> tuple[str, tuple[int, int, int]]:
    """The species' on-map ``(glyph, color)`` (doc 49).

    ``@``/white for unknown ids (stale saves) — every transient
    player-entity construction site reads this ONE helper, so the
    exotic glyphs (``&``, ``♦``, ``Q``) stay consistent across modes.
    The color feeds only the HEALTHY state of the on-map tint;
    wounded amber / critical red stay universal.
    """
    sp = _safe_lookup_species(species_id)
    if sp is None:
        return "@", (255, 255, 255)
    return sp.glyph, sp.color


def species_appearance_for(ctx) -> tuple[str, tuple[int, int, int]]:
    """:func:`species_appearance` read off the live ctx's species id."""
    return species_appearance(
        getattr(ctx, "character_info", {}).get("species_id", ""),
    )


def starting_stats(species_id: str, class_id: str):
    """Starting :class:`spacehack.hud.HudStats` for a (species, class).

    HP = ``class.hp_base`` — the ship-layer readout is class-only
    (doc 49 SETTLED 3-A: the species hp_bonus is ground HP, folded
    into the ground max-HP formula instead). Credits come straight
    off the class spec. Pilot skills (gunnery, piloting, engineering)
    are computed from species + class bonuses applied on top of
    :data:`PILOT_SKILL_BASE`. Unknown ids fall through to safe
    defaults so a future save/load path that emits an unrecognised
    species or class id can't crash the HUD init.
    """
    # Local import avoids any chance of a module-load circular dep if
    # hud.py ever starts importing back from character.
    from .hud import HudStats
    cl = _safe_lookup_class(class_id)
    hp_base = cl.hp_base if cl is not None else 10
    credits = cl.credits if cl is not None else 50

    # Compute pilot skills — reuse starting_pilot_skills internally
    # so the three skill values stay in sync with the combat init.
    skills = starting_pilot_skills(species_id, class_id)
    return HudStats(
        hp=hp_base,
        max_hp=hp_base,
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
    "GROUND_STAT_BASE",
    "PilotSkills",
    "GroundStats",
    "list_species",
    "list_classes",
    "species_hp_bonus",
    "species_appearance",
    "species_appearance_for",
    "starting_pilot_skills",
    "starting_ground_stats",
    "starting_stats",
    "format_combo",
]