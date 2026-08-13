"""Renderer-neutral enemy info for space combat.

Formats the space target's stats for the native pygame floating info
card. Pure helpers only — no combat session state lives here. Shared
card geometry lives in :mod:`._card_presentation`.
"""

from __future__ import annotations

from typing import Any

from .. import world
from ..data.weapons import find_weapon as _find_w
from ..pygame_target_card import (
    TARGET_CARD_TEXT,
    TargetCard,
    dim_row,
    hint_row,
    text_row,
    title_row,
)
from ._card_presentation import build_card as _build_card


def _space_card_rows(
    enemy: Any, hit_chance: int | None,
) -> tuple[tuple[tuple[str, tuple[int, int, int]], ...], ...]:
    """Format the space card body: name, hull+hit, shield, AP, weapons."""
    hit_text = f"HIT {hit_chance}%" if hit_chance is not None else "HIT --"
    hull_row = (
        (f"HULL {enemy.hull}/{enemy.max_hull}", TARGET_CARD_TEXT),
        (f"  {hit_text}", TARGET_CARD_TEXT),
    )
    rows = [title_row(enemy.name), hull_row]
    if enemy.max_shields > 0:
        rows.append(text_row(f"SHD {enemy.shields}/{enemy.max_shields}"))
    rows.append(text_row(f"AP {enemy.ap_remaining}/{enemy.ap_total}"))
    for _wid in enemy.weapons:
        try:
            _ws = _find_w(_wid)
        except KeyError:
            continue
        rows.append(dim_row(_ws.name))
        rows.append(text_row(f"DMG {_ws.damage}  RNG {_ws.min_range}-{_ws.max_range}"))
    if not enemy.weapons:
        rows.append(dim_row("Unarmed"))
    rows.append(hint_row())
    return tuple(rows)


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
    rows = _space_card_rows(enemy, hit_chance)
    return _build_card(
        enemy.pos,
        rows,
        game_map=game_map,
        player_pos=player_pos,
        region_w=region_w,
        region_h=region_h,
        avoid_positions=avoid_positions,
    )
