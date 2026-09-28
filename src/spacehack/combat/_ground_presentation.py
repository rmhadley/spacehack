"""Renderer-neutral enemy info for ground combat.

Formatting for the ground enemy info surfaced in the HUD column and in
the native pygame floating target card. Pure helpers only — no combat
session state lives here, so both :mod:`._rules_ground` and
:mod:`..pygame_combat` can call in without an import cycle. Shared card
geometry lives in :mod:`._card_presentation`.
"""

from __future__ import annotations

from typing import Any

from .. import ui, world
from ..data.ground_weapons import find_ground_weapon as _find_gw
from ..ground_scale import band_level
from ..hud import COLOR_RANGE_GREEN, COLOR_RANGE_ORANGE, COLOR_RANGE_RED
from ..pygame_target_card import (
    TARGET_CARD_DIM,
    TARGET_CARD_TEXT,
    TargetCard,
    dim_row,
    hint_row,
    text_row,
    title_row,
)
from ._card_presentation import build_card as _build_card
from ._card_presentation import hit_color_for_weapon

# Distance-readout threat colors — aliases of the shared combat range
# palette (hud.py) so the enemy-threat readout can never drift from the
# targeting line / target cards.
COLOR_DIST_SAFE = COLOR_RANGE_GREEN       # out of enemy range
COLOR_DIST_DANGER = COLOR_RANGE_RED       # enemy can fire now
COLOR_DIST_TOO_CLOSE = COLOR_RANGE_ORANGE  # inside min range


def enemy_weapon(enemy: Any):
    """Resolve an enemy's weapon spec, or None when unarmed/unknown."""
    if not enemy.weapon_id:
        return None
    try:
        return _find_gw(enemy.weapon_id)
    except KeyError:
        return None


def enemy_effective_weapon(enemy: Any, weapon: Any = None):
    """The enemy's weapon at its rolled tier — card/detail stats must
    read what the enemy actually fires (ground quality scales damage
    AND accuracy, doc 47.2 / SETTLED 13). ``weapon`` accepts an
    already-resolved BASE catalog spec (an effective spec would
    double-scale); None resolves via ``enemy_weapon``."""
    spec = weapon if weapon is not None else enemy_weapon(enemy)
    if spec is None:
        return None
    from ..data.quality import effective_weapon_spec
    return effective_weapon_spec(
        spec.id, getattr(enemy, "weapon_quality", 0),
    )


def _ground_card_rows(
    enemy: Any, weapon: Any, hit_chance: int | None,
    hit_color: tuple[int, int, int] | None = None,
) -> tuple[tuple[tuple[str, tuple[int, int, int]], ...], ...]:
    """Format the ground card body: name, HP+hit, armor+AP, weapon."""
    hit_text = f"HIT {hit_chance}%" if hit_chance is not None else "HIT --"
    _hit_fg = hit_color if (hit_chance is not None and hit_color is not None) else TARGET_CARD_TEXT
    hp_row = (
        (f"HP {enemy.hp}/{enemy.max_hp}", TARGET_CARD_TEXT),
        (f"  {hit_text}", _hit_fg),
    )
    _armor = enemy.spec.armor if enemy.spec else 0
    rows = [
        title_row(
            f"LVL {band_level(getattr(enemy, 'band', 0))} {enemy.name}",
        ),
        hp_row,
        text_row(f"Armor {_armor}  AP {getattr(enemy, 'ap', getattr(enemy, 'ap_total', 0))}"),
    ]
    if weapon:
        rows.append(_weapon_name_row(enemy, weapon))
        _eff = enemy_effective_weapon(enemy, weapon)
        rows.append(text_row(
            f"DMG {_eff.damage}  RNG {weapon.min_range}-{weapon.max_range}"
        ))
    else:
        rows.append(dim_row("Unarmed"))
    rows.append(hint_row())
    return tuple(rows)


def _weapon_name_row(enemy: Any, weapon: Any):
    """The wielded variant's BASE name — no tier token, the card stays
    terse — painted in its tier colour so the palette teaches itself
    (user ruling 2026-09-23: colour, not prefix)."""
    from ..data.quality import quality_color

    color = quality_color(getattr(enemy, "weapon_quality", 0))
    return ((weapon.name, color or TARGET_CARD_DIM),)


def enemy_weapon_fg(
    enemy: Any, default: tuple[int, int, int],
) -> tuple[int, int, int]:
    """The HUD weapon-name line's fg — tier colour when the enemy
    wields a variant (base name, no token), else the caller's default."""
    from ..data.quality import quality_color

    return quality_color(getattr(enemy, "weapon_quality", 0)) or default


def enemy_detail_lines(enemy: Any) -> tuple[str, str, str]:
    """Return the (armor, weapon, stats) HUD lines for one enemy.

    The armor line reports the enemy's flat DR (``Armor 0`` when
    unarmored) so the player can decide between raw damage and armor
    piercing. The weapon line names the weapon, and the stats line
    shows ``DMG``/``RNG`` so a heavy ranged threat is spotted before
    it fires (and melee is unmistakably ``RNG 1-1``).
    """
    armor = enemy.spec.armor if enemy.spec else 0
    weapon = enemy_weapon(enemy)
    if weapon is None:
        return f"Armor {armor}", "Unarmed", ""
    _eff = enemy_effective_weapon(enemy, weapon)
    return (
        f"Armor {armor}",
        weapon.name,
        f"DMG {_eff.damage}  RNG {weapon.min_range}-{weapon.max_range}",
    )


def enemy_threat_color(
    enemy: Any, dist: float,
) -> tuple[int, int, int]:
    """Return the color for the enemy's distance readout.

    Red when the enemy's weapon can fire at this distance, orange when
    the player is inside the enemy's minimum range (too close to fire),
    green when safely out of range. ``dist`` is the raw Euclidean
    distance — the enemy fire gate (``_ai_ground``) compares raw
    floats, so the readout must not pre-truncate.
    """
    weapon = enemy_weapon(enemy)
    if weapon is None:
        return ui.COLOR_VALUE_DIM
    if dist < weapon.min_range:
        return COLOR_DIST_TOO_CLOSE
    if dist <= weapon.max_range:
        return COLOR_DIST_DANGER
    return COLOR_DIST_SAFE


def build_target_card(
    enemy: Any,
    *,
    game_map: world.GameMap,
    player_pos: world.Position,
    region_w: int,
    region_h: int,
    hit_chance: int | None = None,
    hit_weapon_id: str | None = None,
    hit_weapon_range: tuple[int, int] | None = None,
    avoid_positions: tuple[world.Position, ...] = (),
    quick_rows=(),
) -> TargetCard | None:
    """Build the floating info card for ``enemy``, or None when off-view.

    ``hit_weapon_range`` is the wielder's effective ``(min, max)`` from
    ``weapon_range`` so the HIT % color matches the fire gate (trait
    riders included); ``None`` falls back to the catalog profile.
    """
    rows = _ground_card_rows(
        enemy, enemy_weapon(enemy), hit_chance,
        hit_color_for_weapon(
            hit_weapon_id, enemy.pos, player_pos, _find_gw,
            distance_round=int, weapon_range=hit_weapon_range,
        ),
    )
    return _build_card(
        enemy.pos,
        rows,
        game_map=game_map,
        player_pos=player_pos,
        region_w=region_w,
        region_h=region_h,
        avoid_positions=avoid_positions,
        quick_rows=quick_rows,
    )
