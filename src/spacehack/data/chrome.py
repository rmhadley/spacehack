"""The chrome catalog (doc 102): cybernetic pieces, tier-1 teach line.

Chrome extends a stat the body already has — every piece does a
THING (a rate, chance, charge, or conditional; flat adds only
garnish, SETTLED 10). Bays are worn alongside armor (SETTLED 1);
one installed piece per anatomy, any brand (SETTLED 14). The t1
line is the invasiveness ladder's bottom rung: grafts, weaves,
and links — enhancement, never replacement.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChromeSpec:
    """One cybernetic piece.

    ``bay`` is the skill-keyed display site; ``skill`` is the stat
    the piece extends; ``anatomy`` is the exclusivity key (one
    installed piece per structure, SETTLED 14 — same-line tiers
    share their key by definition). ``burn`` is the ego cost —
    also the install claim; 4.1 carries the data, 4.2 the economy.
    Effect fields are flat and defaulted: a piece declares only
    what it carries, and the sums live in :mod:`spacehack.chrome`.
    ``detail`` is the ruled kiosk status line (prose ledger 15):
    terse, number-first, what the piece DOES.
    """

    id: str
    name: str
    bay: str
    skill: str
    anatomy: str
    tier: int
    burn: int
    price: int
    crit_chance_space: int = 0
    crit_chance_melee: int = 0
    crit_chance_ranged: int = 0
    crit_damage_points: int = 0
    dodge_tile_bonus: int = 0
    melee_damage_bonus: int = 0
    nano_mesh: bool = False
    core: bool = False
    detail: str = ""


_PIECES: tuple[ChromeSpec, ...] = (
    ChromeSpec(
        id="terminus_optics",
        name="Terminus Optics",
        bay="Ocular",
        skill="gunnery",
        anatomy="ocular",
        tier=1,
        burn=1,
        price=260,
        crit_chance_space=15,
        detail="Space crit chance 15%.",
    ),
    ChromeSpec(
        id="terminus_piloting_jack",
        name="Terminus Piloting Jack",
        bay="Pilot jack",
        skill="piloting",
        anatomy="jack",
        tier=1,
        burn=1,
        price=320,
        dodge_tile_bonus=1,
        detail="+1 dodge per tile moved in space.",
    ),
    ChromeSpec(
        id="terminus_neural_stim",
        name="Terminus Neural Stim",
        bay="Systems spine",
        skill="engineering",
        anatomy="os",
        tier=1,
        burn=1,
        price=300,
        core=True,
        detail="+2 AP this round, -1 next round. Cooldown 3.",
    ),
    ChromeSpec(
        id="terminus_nano_mesh",
        name="Terminus Nano Mesh",
        bay="Vital",
        skill="stamina",
        anatomy="dermal",
        tier=1,
        burn=1,
        price=280,
        nano_mesh=True,
        detail="Armor x1.25 while below half HP.",
    ),
    ChromeSpec(
        id="terminus_muscle_fibers",
        name="Terminus Muscle Fibers",
        bay="Arms",
        skill="strength",
        anatomy="arm_muscle",
        tier=1,
        burn=1,
        price=350,
        crit_chance_melee=15,
        melee_damage_bonus=2,
        detail="Melee crit chance 15%. +2 melee damage.",
    ),
    ChromeSpec(
        id="terminus_smartlink",
        name="Terminus SmartLink",
        bay="Legs",
        skill="reflexes",
        anatomy="hands",
        tier=1,
        burn=1,
        price=330,
        crit_chance_ranged=15,
        detail="Ranged crit chance 15%.",
    ),
)

_BY_ID: dict[str, ChromeSpec] = {spec.id: spec for spec in _PIECES}


def find_chrome(piece_id: str) -> ChromeSpec:
    """Return the chrome spec for ``piece_id`` (KeyError when unknown)."""
    return _BY_ID[piece_id]


def list_chrome() -> tuple[ChromeSpec, ...]:
    """Every chrome piece in catalog order."""
    return _PIECES


# The anatomy glyph table (user ruling 2026-10-17): one char + color
# per ANATOMY — the mark says WHERE in the body is chromed, so
# competitor pieces and future tiers inherit their site's glyph and
# the table stays fixed at the six settled keys. Colors/chars are
# starting values, tuned in playtest.
ANATOMY_GLYPHS: dict[str, tuple[str, tuple[int, int, int]]] = {
    "ocular": ("O", (120, 210, 235)),      # the eyes — cyan
    "jack": ("J", (110, 150, 255)),        # the neck wire — blue
    "os": ("|", (255, 220, 90)),           # the spine — yellow
    "dermal": ("#", (120, 235, 130)),      # the weave — green
    "arm_muscle": ("=", (255, 120, 120)),  # the arm muscle — red
    "hands": (">", (255, 180, 90)),        # the gun link — orange
}
# The fallback for an anatomy without an entry: a future key's pieces
# stay visible on the stat rows (a missing glyph would read as no
# chrome — the silent-miss guard).
_DEFAULT_ANATOMY_GLYPH: tuple[str, tuple[int, int, int]] = (
    "+", (170, 170, 170),
)


def anatomy_glyph(anatomy: str) -> tuple[str, tuple[int, int, int]]:
    """The anatomy's (char, color) mark."""
    return ANATOMY_GLYPHS.get(anatomy, _DEFAULT_ANATOMY_GLYPH)
