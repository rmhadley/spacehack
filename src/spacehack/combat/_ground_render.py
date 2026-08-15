"""Ground combat HUD rendering and target-card session wrappers.

The full on-foot HUD — player/weapons/enemies/actions panels, the
range/accuracy line, and the floating target card — lives here, split
out of :mod:`._rules_ground` to keep that flavor module within its
architecture line budget.

Rendering reads the shared combat session state from :mod:`._rules_ground`
through :func:`_rules`, a lazy import that breaks the render→rules cycle
(:mod:`._rules_ground` re-exports :func:`render_frame`,
:func:`toggle_target_card`, and :func:`presentation_target_card` from here).
"""

from __future__ import annotations

from typing import Any

from .. import ui, world
from .. import message_log as _ml
from ..engine import SCREEN_WIDTH, SCREEN_HEIGHT, HUD_WIDTH
from ..game_context import GameContext
from ..data.ground_weapons import find_ground_weapon as _find_gw
from ..hud import (
    _bar_str,
    _render_action_pairs,
    COLOR_HP_GOOD,
    COLOR_HP_LOW,
    HUD_TEXT_MAX,
    volley_costs,
)
from ._animations import (
    _has_los,
    _paint_target_highlight,
    _draw_range_colored_line,
)
from ._stats import _distance
from ._ground_presentation import (
    build_target_card as _build_target_card,
    enemy_detail_lines,
    enemy_threat_color,
)


def _rules() -> Any:
    """Ground rules module (lazy import to break the render→rules cycle)."""
    from . import _rules_ground

    return _rules_ground


# Distance-readout / panel palette (kept local to ground rendering so the
# HUD text and cards can never drift from each other).
_COLOR_GROUND_TITLE: tuple[int, int, int] = (255, 200, 100)
_COLOR_GROUND_PLAYER: tuple[int, int, int] = (100, 220, 255)
_COLOR_GROUND_ENEMY: tuple[int, int, int] = (255, 100, 100)
_COLOR_GROUND_ENEMY_TARGET: tuple[int, int, int] = (255, 220, 100)
_COLOR_GROUND_WEAPON: tuple[int, int, int] = (255, 200, 100)
_COLOR_GROUND_WEAPON_DIM: tuple[int, int, int] = (120, 100, 60)
_COLOR_GROUND_ACTION: tuple[int, int, int] = (180, 220, 255)
_COLOR_GROUND_TEMP_AP: tuple[int, int, int] = (100, 170, 255)


def _ground_range_line(
    console, player_pos, target_pos, weapon_id,
    cam_x, cam_y, region_x, region_y, game_map, *, color_override=None,
) -> None:
    """Draw the player's range line using the weapon's range bands."""
    try:
        _ws = _find_gw(weapon_id)
    except KeyError:
        return
    _rules_mod = _rules()
    _min_range, _max_range = _rules_mod.weapon_range(
        weapon_id, _rules_mod._state.ctx, _rules_mod._state.player_ap,
    )
    _draw_range_colored_line(
        console, player_pos, target_pos,
        _max_range, _min_range,
        cam_x, cam_y, _rules_mod._RENDER_WIDTH, _rules_mod._RENDER_HEIGHT,
        region_x=region_x, region_y=region_y,
        color_override=color_override,
        game_map=game_map,
    )


def render_frame(console, ctx, game_map: world.GameMap) -> None:
    console.clear()
    cam = _render_ground_world(console, ctx, game_map)
    alive = _rules().get_enemies(ctx)
    weapons = _rules().player_weapons(ctx)
    active_w = _active_weapon_ids(ctx, weapons)
    _render_range_line(console, ctx, game_map, active_w, alive, cam)
    y = _render_player_panel(console, ctx)
    y = _render_weapons_panel(console, ctx, weapons, alive, y)
    y = _render_enemies_panel(console, ctx, alive, y)
    _render_actions_panel(console, weapons, y)
    _ml.render_message_log(
        console, ctx.log,
        screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT,
    )


def _render_ground_world(
    console, ctx, game_map: world.GameMap,
) -> tuple[int, int, int, int]:
    """Clear, render the world view, and paint the target highlight."""
    _rules_mod = _rules()
    _state = _rules_mod._state
    _rw = _rules_mod._RENDER_WIDTH
    _rh = _rules_mod._RENDER_HEIGHT
    cam_x, cam_y, rx, ry = world.camera_for_view(
        game_map, ctx.player.pos,
        region_w=_rw, region_h=_rh,
    )
    world.render_world_view(
        console, game_map,
        region_x=rx, region_y=ry,
        region_w=_rw, region_h=_rh,
        camera_x=cam_x, camera_y=cam_y,
    )
    alive = _rules_mod.get_enemies(ctx)
    if _state.target_idx < len(alive):
        _paint_target_highlight(
            console, cam_x, cam_y, _rw, _rh, rx, ry,
            alive[_state.target_idx].entity,
        )
    return cam_x, cam_y, rx, ry


def _active_weapon_ids(ctx, weapons: list[str]) -> list[str]:
    """Return equipped weapons still marked active in the combat state."""
    _state = _rules()._state
    return [
        weapons[i] for i in range(len(weapons))
        if i < len(_state.active_weapon_list) and _state.active_weapon_list[i]
    ]


def _render_range_line(
    console, ctx, game_map, active_w: list[str], alive, cam,
) -> None:
    """Draw the player's range/accuracy line unless hidden mid-animation."""
    _state = _rules()._state
    if not active_w or _state.target_idx >= len(alive) or _state.range_line_hidden:
        return
    cam_x, cam_y, rx, ry = cam
    target = alive[_state.target_idx]
    los_blocked = not _has_los(
        game_map,
        ctx.player.pos.x, ctx.player.pos.y,
        target.pos.x, target.pos.y,
    )
    _ground_range_line(
        console, ctx.player.pos, target.pos,
        active_w[0], cam_x, cam_y, rx, ry, game_map,
        color_override=(255, 60, 60) if los_blocked else None,
    )


def _active_regen_amount() -> int:
    """Return the total HP regenerated at the next turn boundary."""
    return sum(
        effect.regen_amount
        for effect in _rules()._state.active_consumable_effects.values()
    )


def _active_ap_bonus() -> int:
    """Return the temporary AP added on the next turn boundary."""
    return sum(
        effect.ap_bonus
        for effect in _rules()._state.active_consumable_effects.values()
    )


def _render_player_panel(console, ctx) -> int:
    """Paint the player HP/AP/evasion block; return the next HUD row."""
    _state = _rules()._state
    hud_x = SCREEN_WIDTH - HUD_WIDTH
    y = 0
    console.print(x=hud_x, y=y, string="> GROUND COMBAT <", fg=_COLOR_GROUND_TITLE)
    y += 2
    console.print(x=hud_x, y=y, string="PLAYER", fg=_COLOR_GROUND_PLAYER)
    y += 1
    _regen = _active_regen_amount()
    _regen_suffix = f" +{_regen}" if _regen > 0 else ""
    _bar_width = 7 if _regen > 0 else 8
    hp_bar = _bar_str(_state.player_hp, _state.player_max_hp, width=_bar_width)
    console.print(
        x=hud_x, y=y,
        string=f"HP  {hp_bar} {_state.player_hp}/{_state.player_max_hp}{_regen_suffix}",
        fg=_COLOR_GROUND_PLAYER,
    )
    y += 1
    console.print(
        x=hud_x, y=y,
        string=f"ARM: {_state.armor_defense}",
        fg=_COLOR_GROUND_ACTION,
    )
    y += 1
    _ap_text = f"AP: {_state.player_ap}/{_state.player_ap_total}"
    console.print(x=hud_x, y=y, string=_ap_text, fg=_COLOR_GROUND_ACTION)
    _ap_bonus = _active_ap_bonus()
    if _ap_bonus > 0:
        console.print(
            x=hud_x + len(_ap_text) + 1, y=y,
            string=f"+{_ap_bonus}", fg=_COLOR_GROUND_TEMP_AP,
        )
    y += 1
    eva = _rules()._calc_ground_move_dodge(_state.cells_moved_this_turn)
    console.print(x=hud_x, y=y, string=f"EVA: {eva}%", fg=_COLOR_GROUND_ACTION)
    return y + 2


def _reserve_count(ctx, ammo_type: str) -> int:
    """Total reserve rounds carried for a weapon's ammo type."""
    from ..ground_equipment import reserve_ammo_count

    return reserve_ammo_count(getattr(ctx, "ground_expedition_items", []), ammo_type)


def _render_weapons_panel(console, ctx, weapons, alive, y: int) -> int:
    """Paint the weapon list + armed-volley AP cost; return the next row."""
    _state = _rules()._state
    hud_x = SCREEN_WIDTH - HUD_WIDTH
    # Ground has no power economy: the burst AP (max-once) is the whole cost.
    _count, _max_ap = volley_costs(weapons, _state.active_weapon_list, _find_gw)[:2]
    console.print(x=hud_x, y=y, string="WEAPONS", fg=_COLOR_GROUND_TITLE)
    if _count:
        console.print(x=hud_x + 8, y=y, string=f"[{_count}]", fg=ui.COLOR_VALUE_DIM)
        _ap_fg = COLOR_HP_GOOD if _max_ap <= _state.player_ap else COLOR_HP_LOW
        console.print(x=hud_x + 12, y=y, string=f"{_max_ap}AP", fg=_ap_fg)
    y += 1
    for i, wid in enumerate(weapons):
        try:
            ws = _find_gw(wid)
        except KeyError:
            continue
        is_active = _state.active_weapon_list[i] if i < len(_state.active_weapon_list) else True
        sel = "[x]" if is_active else "[ ]"
        name_fg = _COLOR_GROUND_WEAPON if is_active else _COLOR_GROUND_WEAPON_DIM
        console.print(x=hud_x, y=y, string=f"{sel}[{i+1}] {ws.name}"[:HUD_TEXT_MAX], fg=name_fg)
        y += 1
        hc = _rules().hit_chance(wid, alive[_state.target_idx], ctx) if _state.target_idx < len(alive) else 0
        console.print(x=hud_x, y=y, string=f"     DMG {ws.damage} HIT {hc}%", fg=ui.COLOR_VALUE_DIM)
        y += 1
        _min_range, _max_range = _rules().weapon_range(wid, ctx, _state.player_ap)
        console.print(x=hud_x, y=y, string=f"     RNG {_min_range}-{_max_range} AP {ws.ap_cost}", fg=ui.COLOR_VALUE_DIM)
        y += 1
        _inst = (
            ctx.equipped_ground_weapons[i]
            if i < len(ctx.equipped_ground_weapons) else None
        )
        if _inst is not None and _inst.loaded_ammo is not None:
            console.print(
                x=hud_x, y=y,
                string=f"     AMMO {_inst.loaded_ammo}/{ws.ammo_capacity} RES {_reserve_count(ctx, ws.ammo_type)}",
                fg=ui.COLOR_VALUE_DIM,
            )
            y += 1
    return y + 1


def toggle_target_card(ctx) -> None:
    """Show/hide the floating target card (``v`` key)."""
    _rules()._state.show_target_card = not _rules()._state.show_target_card


def presentation_target_card(*, ctx: GameContext | None = None):
    """Return the native info card for the currently targeted enemy.

    Thin session wrapper around :func:`._ground_presentation.build_target_card`
    — resolves the targeted enemy from combat state, computes the player's
    hit chance and the visible cells to avoid, then delegates the camera /
    card math. Returns ``None`` when the card is toggled off, there is no
    valid in-view target, or the target scrolled off-screen.
    """
    _rules_mod = _rules()
    _state = _rules_mod._state
    if _state is None or not _state.active or (ctx is not None and _state.ctx is not ctx):
        return None
    if not _state.show_target_card:
        return None
    alive = _rules_mod.get_enemies(ctx)
    if _state.target_idx >= len(alive):
        return None
    _target = alive[_state.target_idx]
    _active = _active_weapon_ids(ctx, _rules_mod.player_weapons(ctx))
    _active_wid = _active[0] if _active else None
    _hit = _rules_mod.hit_chance(_active_wid, _target, ctx) if _active_wid else None
    _avoid = [ctx.player.pos]
    _avoid.extend(_e.pos for _e in alive)
    return _build_target_card(
        _target,
        game_map=_state.game_map,
        player_pos=_state.ctx.player.pos,
        region_w=_rules_mod._RENDER_WIDTH,
        region_h=_rules_mod._RENDER_HEIGHT,
        hit_chance=_hit,
        hit_weapon_id=_active_wid,
        avoid_positions=_avoid,
    )


def _render_enemies_panel(console, ctx, alive, y: int) -> int:
    """Paint the alive-enemy list with HP bars; return the next row."""
    _state = _rules()._state
    hud_x = SCREEN_WIDTH - HUD_WIDTH
    if alive:
        console.print(x=hud_x, y=y, string="ENEMIES", fg=_COLOR_GROUND_TITLE)
        y += 1
        for i, gei in enumerate(alive):
            is_target = i == _state.target_idx
            name_fg = _COLOR_GROUND_ENEMY_TARGET if is_target else _COLOR_GROUND_ENEMY
            marker = ">" if is_target else " "
            console.print(x=hud_x, y=y, string=f"{marker}{gei.name}"[:HUD_TEXT_MAX], fg=name_fg)
            y += 1
            e_bar = _bar_str(gei.hp, gei.max_hp, width=8)
            e_pct = gei.hp * 100 // max(gei.max_hp, 1)
            dist = int(_distance(ctx.player.pos, gei.pos))
            _hp_prefix = f"  HP {e_bar} {e_pct}%  "
            console.print(x=hud_x, y=y, string=_hp_prefix, fg=name_fg)
            console.print(
                x=hud_x + len(_hp_prefix), y=y, string=f"{dist}u",
                fg=enemy_threat_color(gei, dist),
            )
            y += 1
            if is_target:
                for _line in enemy_detail_lines(gei):
                    if not _line:
                        continue
                    console.print(
                        x=hud_x, y=y, string=f"  {_line}"[:HUD_TEXT_MAX],
                        fg=ui.COLOR_VALUE_DIM,
                    )
                    y += 1
    return y + 1


def _render_actions_panel(console, weapons: list[str], y: int) -> None:
    """Paint the action-key legend at the given HUD row."""
    hud_x = SCREEN_WIDTH - HUD_WIDTH
    console.print(x=hud_x, y=y, string="ACTIONS", fg=_COLOR_GROUND_TITLE)
    y += 1
    actions = [
        ("[Tab]", "Target"), ("[m]", "Move"), ("[f]", "Fire"), ("[r]", "Reload"),
        ("[w]", "Wait"), ("[v]", "Info"),
    ]
    if len(weapons) > 1:
        actions.insert(4, (f"[1-{len(weapons)}]", "Toggle Wpn"))
    _render_action_pairs(console, hud_x, y, actions, _COLOR_GROUND_ACTION)
