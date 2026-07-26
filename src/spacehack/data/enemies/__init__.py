"""Enemy ship templates — static specs for hostile NPC ships.

Each enemy references existing Ship, WeaponSpec, and ModuleSpec ids.
The AIProfile drives behaviour generically via numeric fields.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..pilot_skills import PilotSkills


@dataclass(frozen=True)
class AIProfile:
    """Numeric AI personality that drives per-turn decisions.

    Attributes:
        aggressiveness: 0-100. Chance to attack vs reposition each turn.
        preferred_range: AI tries to maintain this distance from target.
        flee_threshold: Hull % (0.0-1.0) below which AI tries to flee.
        accuracy_bonus: Per-difficulty modifier to hit chance.
        dodge_bonus: Per-difficulty modifier to dodge chance.
    """
    aggressiveness: int = 50
    preferred_range: int = 3
    flee_threshold: float = 0.15
    accuracy_bonus: int = 0
    dodge_bonus: int = 0


@dataclass(frozen=True)
class EnemySpec:
    """Static template for an enemy ship.

    Attributes:
        id: registry key, e.g. "pirate_scout".
        name: display name shown in combat HUD.
        char: glyph on the solar system map.
        fg: foreground colour.
        ship_id: hull reference (scout/hauler/cruiser).
        weapons: weapon ids fitted at spawn.
        modules: module ids fitted at spawn.
        ai: AIProfile driving behaviour.
        detect_radius: cells before combat triggers.
        min_power_gen: base power generated per turn.
        pilot_skills: per-skill bonuses (gunner/piloting/engineering).
    """
    id: str
    name: str
    char: str
    fg: tuple[int, int, int]
    ship_id: str
    weapons: tuple[str, ...] = ()
    modules: tuple[str, ...] = ()
    ai: AIProfile = AIProfile()
    detect_radius: int = 8
    min_power_gen: int = 3
    pilot_skills: PilotSkills = PilotSkills(gunnery=20, piloting=20, engineering=10)


_BY_ID: dict[str, EnemySpec] | None = None


def _build_registry() -> dict[str, EnemySpec]:
    from . import pirates as pirates_module
    combined: dict[str, EnemySpec] = {}
    for e in pirates_module.ENEMIES:
        combined[e.id] = e
    return combined


def _registry() -> dict[str, EnemySpec]:
    global _BY_ID
    if _BY_ID is None:
        _BY_ID = _build_registry()
    return _BY_ID


def find_enemy(enemy_id: str) -> EnemySpec:
    """Look up an EnemySpec by id; raises KeyError on miss."""
    try:
        return _registry()[enemy_id]
    except KeyError:
        raise KeyError(f"unknown enemy id: {enemy_id!r}") from None
