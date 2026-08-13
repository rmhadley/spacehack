"""Renderer-neutral enemy info for ground combat.

Formatting and camera math for the enemy info surfaced in the HUD column
and in the native pygame floating target card. Pure helpers only — no
combat session state lives here, so both :mod:`._rules_ground` and
:mod:`..pygame_combat` can call in without an import cycle.
"""

from __future__ import annotations

from typing import Any

from .. import ui, world
from ..data.ground_weapons import find_ground_weapon as _find_gw
from ..pygame_target_card import TargetCard

# Distance-readout threat colors, mirroring the space HUD's range tints.
COLOR_DIST_SAFE: tuple[int, int, int] = (100, 235, 115)     # out of enemy range
COLOR_DIST_DANGER: tuple[int, int, int] = (255, 80, 80)     # enemy can fire now
COLOR_DIST_TOO_CLOSE: tuple[int, int, int] = (255, 160, 60)  # inside min range


def enemy_weapon(enemy: Any):
    """Resolve an enemy's weapon spec, or None when unarmed/unknown."""
    if not enemy.weapon_id:
        return None
    try:
        return _find_gw(enemy.weapon_id)
    except KeyError:
        return None


def _weapon_card_stats(weapon: Any) -> tuple[str, int, int, int]:
    """Return ``(name, damage, min_range, max_range)``; unarmed defaults."""
    if weapon is None:
        return "", 0, 1, 1
    return weapon.name, weapon.damage, weapon.min_range, weapon.max_range


def enemy_detail_lines(enemy: Any) -> tuple[str, str, str]:
    """Return the (armor, weapon, stats) HUD lines for one enemy.

    The armor line reports the enemy's flat DR (``ARM 0`` when
    unarmored) so the player can decide between raw damage and armor
    piercing. The weapon line names the weapon, and the stats line
    shows ``DMG``/``RNG`` so a heavy ranged threat is spotted before
    it fires (and melee is unmistakably ``RNG 1-1``).
    """
    armor = enemy.spec.armor if enemy.spec else 0
    weapon = enemy_weapon(enemy)
    if weapon is None:
        return f"ARM {armor}", "Unarmed", ""
    return (
        f"ARM {armor}",
        weapon.name,
        f"DMG {weapon.damage}  RNG {weapon.min_range}-{weapon.max_range}",
    )


def enemy_threat_color(
    enemy: Any, dist: int,
) -> tuple[int, int, int]:
    """Return the color for the enemy's distance readout.

    Red when the enemy's weapon can fire at this distance, orange when
    the player is inside the enemy's minimum range (too close to fire),
    green when safely out of range.
    """
    weapon = enemy_weapon(enemy)
    if weapon is None:
        return ui.COLOR_VALUE_DIM
    if dist < weapon.min_range:
        return COLOR_DIST_TOO_CLOSE
    if dist <= weapon.max_range:
        return COLOR_DIST_DANGER
    return COLOR_DIST_SAFE


def _viewport_cells(
    positions: tuple[world.Position, ...],
    *,
    cam_x: int,
    cam_y: int,
    rx: int,
    ry: int,
    region_w: int,
    region_h: int,
) -> tuple[tuple[int, int], ...]:
    """Map map positions to viewport cells, dropping any off-screen."""
    cells: list[tuple[int, int]] = []
    for _p in positions:
        _x, _y = rx + _p.x - cam_x, ry + _p.y - cam_y
        if 0 <= _x < region_w and 0 <= _y < region_h:
            cells.append((_x, _y))
    return tuple(cells)


def build_target_card(
    enemy: Any,
    *,
    game_map: world.GameMap,
    player_pos: world.Position,
    region_w: int,
    region_h: int,
    hit_chance: int | None = None,
    avoid_positions: tuple[world.Position, ...] = (),
) -> TargetCard | None:
    """Build the floating info card for ``enemy``, or None when off-view."""
    cam_x, cam_y, rx, ry = world.camera_for_view(
        game_map, player_pos, region_w=region_w, region_h=region_h,
    )
    sx, sy = rx + enemy.pos.x - cam_x, ry + enemy.pos.y - cam_y
    if not (0 <= sx < region_w and 0 <= sy < region_h):
        return None
    # Player is always in view; its cell drives away-from-player placement.
    wname, wdmg, wmin, wmax = _weapon_card_stats(enemy_weapon(enemy))
    return TargetCard(
        name=enemy.name,
        armor=enemy.spec.armor if enemy.spec else 0,
        weapon=wname,
        damage=wdmg,
        min_range=wmin,
        max_range=wmax,
        hp=enemy.hp,
        max_hp=enemy.max_hp,
        max_ap=getattr(enemy, "ap_total", 0),
        hit_chance=hit_chance,
        avoid_cells=_viewport_cells(
            avoid_positions,
            cam_x=cam_x, cam_y=cam_y, rx=rx, ry=ry,
            region_w=region_w, region_h=region_h,
        ),
        player_cell=(rx + player_pos.x - cam_x, ry + player_pos.y - cam_y),
        x=sx,
        y=sy,
    )
