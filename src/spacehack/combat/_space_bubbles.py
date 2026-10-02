"""Space-combat shield bubbles (the overlay's live shield read).

Extracted from ``_rules_space`` (the doc-57.3-era ratchet split; the
functions read the module-global combat state lazily — the sibling
import idiom — so the hub keeps no bubble code).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..game_context import GameContext
    from ..pygame_overlay import ShieldBubble


def presentation_shield_bubbles(
    *,
    ctx: GameContext | None = None,
    camera_x: int | None = None,
    camera_y: int | None = None,
) -> tuple:
    """Return live shield bubbles in the current space-combat viewport."""
    from ._rules_space import _calc_camera, _state

    if _state is None or not _state.active or (ctx is not None and _state.ctx is not ctx):
        return ()
    if camera_x is None or camera_y is None:
        camera_x, camera_y = _calc_camera()
    bubbles: list[ShieldBubble] = []
    _pb = _player_shield_bubble(camera_x, camera_y)
    if _pb is not None:
        bubbles.append(_pb)
    bubbles.extend(_enemy_shield_bubbles(camera_x, camera_y))
    return tuple(bubbles)


def _player_shield_bubble(camera_x: int, camera_y: int) -> ShieldBubble | None:
    """Return the player's shield bubble, or None when unshielded/off-view."""
    from ..pygame_overlay import _bubble_intersects_region, _shield_bubble
    from ._rules_space import _state

    player_shields = max(0, int(_state.player_state.get("shields", 0)))
    if player_shields <= 0 or _state.player_ent is None:
        return None
    entity = _state.player_ent
    bubble = _shield_bubble(
        entity.pos.x,
        entity.pos.y,
        camera_x=camera_x,
        camera_y=camera_y,
        width=getattr(entity, "width", 1),
        height=getattr(entity, "height", 1),
        strength=player_shields / max(
            1, _state.player_state.get("max_shields", player_shields),
        ),
    )
    if _bubble_intersects_region(
        bubble, region_x=0, region_y=0,
        region_w=_state.view_w, region_h=_state.view_h,
    ):
        return bubble
    return None

def _enemy_shield_bubbles(camera_x: int, camera_y: int) -> list[ShieldBubble]:
    """Return shield bubbles for every shielded enemy in the viewport."""
    from ..pygame_overlay import _bubble_intersects_region, _shield_bubble
    from ._rules_space import _state

    bubbles: list[ShieldBubble] = []
    for index, enemy in enumerate(_state.enemy_insts):
        if not enemy.alive or enemy.shields <= 0:
            continue
        entity = _state.enemy_ents.get(index)
        x, y = enemy.pos.x, enemy.pos.y
        width = height = 1
        if entity is not None:
            x, y = entity.pos.x, entity.pos.y
            width = max(1, getattr(entity, "width", 1))
            height = max(1, getattr(entity, "height", 1))
        bubble = _shield_bubble(
            x,
            y,
            camera_x=camera_x,
            camera_y=camera_y,
            width=width,
            height=height,
            strength=enemy.shields / max(1, enemy.max_shields),
        )
        if _bubble_intersects_region(
            bubble, region_x=0, region_y=0,
            region_w=_state.view_w, region_h=_state.view_h,
        ):
            bubbles.append(bubble)
    return bubbles
