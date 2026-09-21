"""Legendary randart generation (doc 47 phase 4).

A randart is the rolled top of the quality ladder (SETTLED 1/19):
modules only, delve-bottom exclusive. Its identity is a seed — the
same seed + module id always recomposes the same name and bonus
spread, so a randart is THE same artifact all run (the dig-site
name-composition lineage). Axes are integer deltas applied on top of
the tier-scaled base; deltas never round (SETTLED 18 governs the
scaled part only).
"""

from __future__ import annotations

from dataclasses import dataclass

# Two-part relic register (SETTLED 21) — drafts carried in the doc-47
# phase-4 brief; prose gate, reviewed verbatim at the playtest
# checkpoint. Any pairing must read clean.
RANDART_PREFIXES: tuple[str, ...] = (
    "Pale", "Silent", "Iron", "Hollow", "Ember", "Quiet",
    "Sundered", "Cold", "Late", "Vagrant", "Ashen", "Patient",
)
RANDART_SUFFIXES: tuple[str, ...] = (
    "Meridian", "Covenant", "Vigil", "Ledger", "Compass",
    "Lantern", "Sentinel", "Requiem", "Furnace", "Harbor",
    "Testament", "Beacon",
)

# One signed range per ModuleSpec bonus field (SETTLED 20): most axes
# lean positive, a few can roll drawbacks — the rarest find is an
# equip decision, not a strict upgrade. Zero never rolls (a zero
# delta would be a nothing-axis). Opening guesses, tuned at playtest
# (engineering raised to the gunnery/piloting band, SETTLED 28).
RANDART_AXES: tuple[tuple[str, int, int], ...] = (
    ("power_gen_bonus", -2, 4),
    ("max_shield_bonus", 5, 25),
    ("shield_recharge_bonus", 1, 3),
    ("cargo_bonus", -10, 30),
    ("gunnery_bonus", 3, 10),
    ("piloting_bonus", 3, 10),
    ("engineering_bonus", 3, 10),
    ("max_hull_bonus", 5, 20),
    ("speed_bonus", -1, 2),
    ("smuggler_cargo", 5, 20),
)

# Long-form axis labels for the pickup modal's spread list — phrased
# to the module detail-row conventions (the delegated wording in the
# brief; reviewed at the playtest checkpoint with the other strings).
AXIS_LABELS: dict[str, str] = {
    "power_gen_bonus": "power generated per turn",
    "max_shield_bonus": "max shields",
    "shield_recharge_bonus": "shield regen per turn",
    "cargo_bonus": "cargo capacity",
    "gunnery_bonus": "gunnery",
    "piloting_bonus": "piloting",
    "engineering_bonus": "engineering",
    "max_hull_bonus": "max hull",
    "speed_bonus": "speed",
    "smuggler_cargo": "smuggler hold",
}


@dataclass(frozen=True)
class RandartManifest:
    """One rolled randart's identity: name plus signed axis deltas."""

    name: str
    axes: tuple[tuple[str, int], ...]


def roll_randart(module_id: str, seed: int) -> RandartManifest:
    """Compose the manifest for one module id at one seed (pure).

    Determinism is the contract: the same ``(module_id, seed)`` pair
    always yields the identical manifest, in any process, because the
    stream derives from :func:`engine.seeded_rng` (md5-keyed, stable
    across runs — Python's ``hash`` is salted and must not be used).
    """
    from .. import engine

    rng = engine.seeded_rng(seed, "randart", module_id)
    name = f"{rng.choice(RANDART_PREFIXES)} {rng.choice(RANDART_SUFFIXES)}"
    picked = rng.sample(RANDART_AXES, rng.randint(2, 4))
    axes = tuple((field, _roll_delta(rng, low, high)) for field, low, high in picked)
    return RandartManifest(name, axes)


def _roll_delta(rng, low: int, high: int) -> int:
    """Roll one axis delta in [low, high], never landing on zero."""
    crosses_zero = low <= 0 <= high
    span = high - low + 1 - (1 if crosses_zero else 0)
    roll = rng.randrange(span)
    if crosses_zero and roll >= -low:
        roll += 1
    return low + roll


def axis_line(field: str, delta: int) -> str:
    """One modal spread line: "+6 max shields" (the detail-row voice)."""
    return f"{delta:+d} {AXIS_LABELS[field]}"


def parse_randart_seed(raw) -> int | None:
    """Parse one persisted randart seed; malformed values migrate to
    "not a randart" (None). Shared by the save/load parse paths and
    the loot-pickup boundary (the ``parse_quality`` twin)."""
    try:
        seed = int(raw)
    except (TypeError, ValueError):
        return None
    return seed if seed > 0 else None
