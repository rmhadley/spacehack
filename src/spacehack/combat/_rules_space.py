"""Space combat rules — flavor module for the unified combat loop.

All state and behavior that differs between space and ground combat
lives here. The unified loop in :mod:`._loop` calls these functions
by name — same call shape whether the rules module is
``_rules_space`` or ``_rules_ground``.

**Combat session state** is encapsulated in :class:`SpaceCombatState`,
a single module-level dataclass replacing the old scattered globals.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .. import world
from .. import hud_combat as _hud
from .. import message_log as _ml
from ..engine import SCREEN_WIDTH, SCREEN_HEIGHT
from ..data.weapons import find_weapon as _find_weapon
from ..pygame_target_card import quick_row

if TYPE_CHECKING:
    from ..pygame_overlay import ShieldBubble
from ..game_context import GameContext

from ._space_init import (
    build_initial_enemies as _build_initial_enemies,
    dedupe_enemy_positions as _dedupe_enemy_positions,
    find_player_entity as _find_player_entity,
    flown_weapons as _flown_weapons,
    match_enemy_entities as _match_enemy_entities,
)
from ._types import EnemyInstance, CombatResult, SpaceCombatState
from ._space_kills import on_kill as _kill_chain
from ._stats import (
    calc_hit_chance as _space_hit_chance,
    _calc_dodge_bonus,
    _distance,
)
from ._actions import (
    start_player_turn,
    move_entity,
    resolve_damage,
    can_afford_action as _space_can_afford,
    _sync_back_hull,
    _sync_back_ammo,
    set_combat_locks,
)
from ._animations import (
    _has_los,
    _paint_target_highlight,
    _paint_range_line,
    DamagePopup,
)
from ._shot_animations import _animate_weapon_shot
from ._space_presentation import build_target_card as _build_target_card
from . import _space_focus
from ..xp import (
    sharpshooter_hit_bonus as _sharpshooter_bonus,
    ace_pilot_ap_bonus as _ace_pilot_bonus,
    laser_specialist_hit_bonus as _laser_specialist_bonus,
    missileer_hit_bonus as _missileer_bonus,
    momentum_hit_bonus as _momentum_hit_bonus,
    pirate_opener_damage_pct as _opener_damage_pct,
    pirate_opener_hit_bonus as _opener_hit_bonus,
    plasma_savant_ap_discount as _plasma_ap_discount,
    systems_expert_power_bonus as _systems_expert_bonus,
)

# ---------------------------------------------------------------------------
# SpaceCombatState — all session state in one place (class lives in
# _types; the module-level global lives here, per the state contract)
# ---------------------------------------------------------------------------

_state: SpaceCombatState | None = None

def _set_combat_locks(locked: bool, entities=None) -> None:
    """Freeze/release combat entities from the ``move_npcs`` patrol pass.

    See :func:`combat._actions.set_combat_locks` for the flag contract.
    """
    _ents = entities if entities is not None else _state.enemy_ents
    if isinstance(_ents, dict):
        _ents = _ents.values()
    set_combat_locks(locked, _ents)

# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


def _sync_enemy_entity_positions(enemy_ents: dict[int, Any], enemy_insts: list[EnemyInstance]) -> None:
    """Copy deduped instance positions back onto their map entities."""
    for _i, _ent in enemy_ents.items():
        if _i < len(enemy_insts):
            _ent.pos = enemy_insts[_i].pos

def _activate_combat_state(
    ctx, console, game_map, log,
    player_state, enemy_insts, enemy_specs, enemy_ents, player_ent,
    weapons_list, active_weapons, weapon_qualities=(),
) -> None:
    """Commit the assembled state and freeze the engaged set."""
    global _state
    _cr = CombatResult()
    start_player_turn(player_state)
    # Clear locks from an abnormally-ended previous fight.
    if _state is not None:
        _set_combat_locks(False)
    _state = SpaceCombatState(
        ctx=ctx, console=console, game_map=game_map, log=log,
        player_state=player_state,
        enemy_insts=enemy_insts, enemy_specs=enemy_specs,
        enemy_ents=enemy_ents, player_ent=player_ent,
        weapons_list=weapons_list, active_weapons=active_weapons,
        weapon_qualities=list(weapon_qualities),
        cr=_cr,
    )
    # Freeze the engaged set immediately.
    _set_combat_locks(True, enemy_ents)

def init(
    ctx,
    console,
    player_ship_catalog,
    player_owned_ship,
    player_pos: world.Position,
    player_pilot_skills,
    enemy_specs: list,
    enemy_positions: list[world.Position],
    game_map: world.GameMap,
    log,
) -> None:
    """Set up combat session state for a space combat encounter."""
    global _state
    if not enemy_specs or not enemy_positions:
        return
    _player_state, _enemy_insts = _build_initial_enemies(
        ctx, player_ship_catalog, player_owned_ship,
        player_pos, player_pilot_skills, enemy_specs, enemy_positions,
        ap_bonus=_ace_pilot_bonus(ctx),
        plasma_ap_discount=_plasma_ap_discount(ctx),
        max_power_bonus=_systems_expert_bonus(ctx),
    )
    _weapons_list, _weapon_qualities = _flown_weapons(player_owned_ship)
    _active_weapons = [True] * max(1, len(_weapons_list))
    _player_ent = _find_player_entity(game_map)
    _enemy_ents = _match_enemy_entities(game_map, _player_ent, _enemy_insts)
    _dedupe_enemy_positions(game_map, _enemy_insts)
    _sync_enemy_entity_positions(_enemy_ents, _enemy_insts)
    _activate_combat_state(
        ctx, console, game_map, log,
        _player_state, _enemy_insts, list(enemy_specs),
        _enemy_ents, _player_ent, _weapons_list, _active_weapons,
        weapon_qualities=_weapon_qualities,
    )

# ---------------------------------------------------------------------------
# State accessors
# ---------------------------------------------------------------------------

def player_weapon_quality(ctx, slot: int) -> int:
    """The flown weapon's rolled tier (doc 48.7 player side) by slot.

    The unified loop's volley seam: quality multiplies each shot's
    damage exactly as it multiplies enemy weapon damage. Bounds-guarded
    so a mid-combat loadout change cannot raise IndexError.
    """
    _quals = _state.weapon_qualities if _state is not None else []
    if 0 <= slot < len(_quals):
        return int(_quals[slot])
    return 0


def player_hp(ctx) -> int:
    return _state.player_state.get("hull", 100)

def player_max_hp(ctx) -> int:
    return _state.player_state.get("max_hull", 100)

def player_shields(ctx) -> int:
    return _state.player_state.get("shields", 0)

def last_attacker(ctx) -> str | None:
    """The tracked killer label for the tombstone (doc 53); None until
    hostile damage lands — the header renders the fallback line."""
    return _state.last_attacker

def player_ap(ctx) -> int:
    return _state.player_state.get("ap_remaining", 0)

def player_ap_total(ctx) -> int:
    return _state.player_state.get("ap_total", 3)

def player_weapons(ctx) -> list[str]:
    return list(_state.weapons_list)

def active_weapons(ctx) -> list[bool]:
    return list(_state.active_weapons)

def set_active_weapons(ctx, active: list[bool]) -> None:
    _state.active_weapons = list(active)

# ---------------------------------------------------------------------------
# Enemy accessors
# ---------------------------------------------------------------------------

def set_target_idx(ctx, idx: int) -> None:
    _state.target_idx = idx

def _active_weapon_ids() -> list[str]:
    """Ids of the enabled weapon slots — the volley about to fire."""
    return [
        _state.weapons_list[i] for i in range(len(_state.weapons_list))
        if i < len(_state.active_weapons) and _state.active_weapons[i]
    ]

def _alive_target():
    _alive = [e for e in _state.enemy_insts if e.alive]
    if 0 <= _state.target_idx < len(_alive):
        return _alive[_state.target_idx]
    return None

def get_enemies(ctx) -> list[EnemyInstance]:
    return [e for e in _state.enemy_insts if e.alive]

def combat_should_end(ctx, game_map: world.GameMap, enemies: list) -> bool:
    """Space keeps the classic end: VICTORY when no enemies remain."""
    return not enemies

def refresh_engaged(ctx, game_map: world.GameMap) -> None:
    """Space has no mid-fight joins — the enemy set is fixed at init."""
    pass

def enemy_pos(enemy: EnemyInstance) -> world.Position:
    return enemy.pos

def enemy_name(enemy: EnemyInstance) -> str:
    return enemy.name

def enemy_hp(enemy: EnemyInstance) -> int:
    return enemy.hull

def enemy_max_hp(enemy: EnemyInstance) -> int:
    return enemy.max_hull

def enemy_alive(enemy: EnemyInstance) -> bool:
    return enemy.alive

# ---------------------------------------------------------------------------
# Combat math
# ---------------------------------------------------------------------------

def _opener_flags() -> tuple[bool, bool]:
    """``(enemy_fired, opener_spent)`` on the installed session; both
    False when no session is live, so formula-only callers read the
    flags of whatever fight is (or was last) installed — None reads
    as a fresh fight."""
    if _state is None:
        return False, False
    return _state.enemy_fired, _state.opener_spent


def _player_hit_bonus(ctx, weapon_id: str) -> int:
    """The player's per-weapon permanent hit bonus: Sharpshooter plus
    weapon specialists plus Momentum's always-on +5 (doc 49) plus the
    Pirate opener while the window is open (doc 49 phase 2) — the ONE
    assembly both hit-chance sites read."""
    _ef, _os = _opener_flags()
    _hit_bonus = (
        _sharpshooter_bonus(ctx) + _momentum_hit_bonus(ctx)
        + _opener_hit_bonus(ctx, enemy_fired=_ef, opener_spent=_os)
    )
    try:
        _slot_type = _find_weapon(weapon_id).slot_type
    except KeyError:
        _slot_type = ""
    if _slot_type == "energy":
        _hit_bonus += _laser_specialist_bonus(ctx)
    elif _slot_type == "missile":
        _hit_bonus += _missileer_bonus(ctx)
    return _hit_bonus


def hit_chance(weapon_id: str, enemy: EnemyInstance, ctx, quality: int = 0) -> int:
    # ``quality`` is the rolled instance tier seam the unified loop
    # threads; quality scales accuracy (doc 47 SETTLED 2, space side
    # landed 2026-09-28) and damage — the gunnery/dodge terms stay
    # pilot-side (same as the enemy shot path).
    _dist = _distance(_state.player_state["pos"], enemy.pos)
    _dodge = _calc_dodge_bonus(
        enemy.cells_moved_this_turn,
        int(enemy.pilot_piloting * 0.5),
    )
    return _space_hit_chance(
        weapon_id, _state.player_state["gunnery"], _dist, _dodge,
        hit_bonus=_player_hit_bonus(ctx, weapon_id),
        max_range=_space_focus.max_range(weapon_id, ctx),
        min_range=_space_focus.min_range(weapon_id, ctx),
        weapon_quality=quality,
    )

def _player_damage_mult(weapon_id: str, ctx, dist) -> float:
    """The player's damage multiplier for one volley: the Focus trait's
    range scaling times the Pirate opener while its window is open
    (doc 49 phase 2) — the ONE read both the damage site and tests
    share."""
    _ef, _os = _opener_flags()
    return _space_focus.damage_mult(weapon_id, ctx, dist) * (
        _opener_damage_pct(ctx, enemy_fired=_ef, opener_spent=_os) / 100
    )


def damage(
    weapon_id: str, enemy: EnemyInstance, ctx, quality: int = 0,
) -> tuple[int, bool]:
    """Apply weapon damage to an enemy. Returns ``(hull_dmg, is_glancing)``.

    The glance flag rides the return so the caller can label the
    floating damage number (``GLANCE -X``) the same way the log line
    does. Hull damage is the number the popup reports. A focused shot
    doubles damage beyond half its (doubled) range via the Focus trait.
    ``quality`` is the flown instance's tier (doc 48.7) — it multiplies
    damage inside resolve_damage, mirroring the enemy shot path.
    """
    _dist = _distance(_state.player_state["pos"], enemy.pos)
    _dmg, _sdmg, _fh, _is_glancing = resolve_damage(
        weapon_id, enemy.hull, enemy.shields,
        target_pilot_piloting=enemy.pilot_piloting,
        damage_taken_mult=_player_damage_mult(weapon_id, ctx, _dist),
        weapon_quality=quality,
    )
    enemy.shields = max(0, enemy.shields - _sdmg)
    _prev_hull = enemy.hull
    enemy.hull = _fh
    if _fh <= 0:
        enemy.alive = False
    return _prev_hull - enemy.hull, _is_glancing

# ---------------------------------------------------------------------------
# Weapon actions
# ---------------------------------------------------------------------------

def can_fire(slot_idx: int, ctx) -> tuple[bool, str]:
    _mult = 2 if _space_focus.is_focus_active(ctx) else 1
    _ok, _reason = _space_can_afford(
        _state.player_state, slot_idx, ap_mult=_mult, power_mult=_mult,
    )
    if not _ok:
        return _ok, _reason
    _target = _alive_target()
    if _target is not None:
        if not _has_los(
            _state.game_map,
            _state.player_state["pos"].x, _state.player_state["pos"].y,
            _target.pos.x, _target.pos.y,
        ):
            return False, "Blocked by obstacle"
    return True, ""

def weapon_ap_cost(weapon_id: str, ctx) -> int:
    """AP cost to fire ``weapon_id``: doubled for the focused weapon."""
    return _space_focus.ap_cost(weapon_id, ctx)


def mark_opener_spent() -> None:
    """Spend the Pirate opener (doc 49 SETTLED 5): the shared fire
    loop calls this once the player's first attack action resolved,
    hit or miss — the bonus never returns this fight."""
    _state.opener_spent = True

def weapon_name(weapon_id: str, ctx, quality: int = 0) -> str:
    # ``quality``: the ground-instance tier seam (ignored in space).
    from ..data.weapons import find_weapon as _fw
    return _fw(weapon_id).name

def consume_shot(slot_idx: int, ctx) -> None:
    from ..data.weapons import find_weapon as _fw
    _weapons = _state.player_state.get("weapons", ())
    if not (0 <= slot_idx < len(_weapons)):
        return
    _ws = _fw(_weapons[slot_idx])
    if hasattr(ctx, "player_counters"):
        if _ws.slot_type == "energy":
            ctx.player_counters.laser_shots += 1
        elif _ws.slot_type == "missile":
            ctx.player_counters.missile_shots += 1
        elif _ws.slot_type == "plasma":
            ctx.player_counters.plasma_shots += 1
        if _space_focus.is_focus_active(ctx):
            ctx.player_counters.focused_shots += 1
    if _ws.slot_type in ("energy", "plasma"):
        _state.player_state["power_pool"] -= _space_focus.power_cost(
            _weapons[slot_idx], ctx,
        )
    elif _ws.slot_type == "missile":
        old = _state.player_state["weapon_ammo"].get(slot_idx, 0)
        _state.player_state["weapon_ammo"][slot_idx] = max(0, old - _ws.ammo_per_shot)

# ---------------------------------------------------------------------------
# Player movement
# ---------------------------------------------------------------------------

def try_move(ctx, game_map: world.GameMap, dx: int, dy: int) -> bool:
    new_pos, ok = move_entity(
        _state.player_state["pos"], dx, dy, game_map,
        exclude=_state.player_ent,
    )
    if ok:
        _state.player_state["pos"] = new_pos
        _state.player_state["ap_remaining"] -= 1
        _state.player_state["cells_moved_this_turn"] += 1
        if _state.player_ent is not None:
            _state.player_ent.pos = new_pos
    return ok

# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _build_hit_chances(target) -> dict[str, int]:
    """Return {weapon_id: hit_chance_pct} for all weapons against target."""
    _result: dict[str, int] = {}
    if not _state.weapons_list or target is None:
        return _result
    _dist = _distance(_state.player_state["pos"], target.pos)
    _target_dodge = _calc_dodge_bonus(
        target.cells_moved_this_turn,
        int(target.pilot_piloting * 0.5),
    )
    for _index, _wid in enumerate(_state.weapons_list):
        try:
            _result[_wid] = _space_hit_chance(
                _wid, _state.player_state["gunnery"], _dist, _target_dodge,
                hit_bonus=_player_hit_bonus(_state.ctx, _wid),
                max_range=_space_focus.max_range(_wid, _state.ctx),
                min_range=_space_focus.min_range(_wid, _state.ctx),
                weapon_quality=player_weapon_quality(_state.ctx, _index),
            )
        except KeyError:
            pass
    return _result

def _calc_camera():
    _cw = max(0, _state.game_map.width - _state.view_w)
    _ch = max(0, _state.game_map.height - _state.view_h)
    _cx = max(0, min(_state.player_state["pos"].x - _state.view_w // 2, _cw))
    _cy = max(0, min(_state.player_state["pos"].y - _state.view_h // 2, _ch))
    return _cx, _cy

def _player_shield_bubble(camera_x: int, camera_y: int) -> ShieldBubble | None:
    """Return the player's shield bubble, or None when unshielded/off-view."""
    from ..pygame_overlay import _bubble_intersects_region, _shield_bubble

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

def presentation_shield_bubbles(
    *,
    ctx: GameContext | None = None,
    camera_x: int | None = None,
    camera_y: int | None = None,
) -> tuple:
    """Return live shield bubbles in the current space-combat viewport."""
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

def toggle_target_card(ctx) -> None:
    """Show/hide the floating target card (``v`` key)."""
    _state.show_target_card = not _state.show_target_card

def _quick_resource_row(ctx):
    """The compact resource strip above the target card (the ground
    module's twin): labeled stats in PLAYER-block order, the armed
    volley's costs as a FIRE verb phrase."""
    _active_ids = _active_weapon_ids()
    _ap_needed = max(
        (_space_focus.ap_cost(weapon_id, ctx) for weapon_id in _active_ids),
        default=0,
    )
    _power_available = _state.player_state.get("power_pool", 0)
    _power_cost = sum(
        _space_focus.power_cost(weapon_id, ctx) for weapon_id in _active_ids
    )
    return quick_row(
        f"HP {player_hp(ctx)}/{player_max_hp(ctx)}   "
        f"AP {player_ap(ctx)}/{player_ap_total(ctx)}   "
        f"POW {_power_available}/{_state.player_state.get('max_power', 10)}   "
        f"FIRE {_ap_needed} AP {_power_cost} POW"
    )


def presentation_target_card(*, ctx: GameContext | None = None):
    """Return the native info card for the currently targeted enemy ship, or None."""
    if _state is None or not _state.active or (ctx is not None and _state.ctx is not ctx):
        return None
    if not _state.show_target_card:
        return None
    _target = _alive_target()
    if _target is None:
        return None
    _active_ids = _active_weapon_ids()
    _active_wid = _active_ids[0] if _active_ids else None
    _hit = hit_chance(_active_wid, _target, ctx) if _active_wid else None
    _hit_range = (
        (
            _space_focus.min_range(_active_wid, ctx),
            _space_focus.max_range(_active_wid, ctx),
        ) if _active_wid else None
    )
    _quick = _quick_resource_row(ctx)
    _avoid = [_state.player_state["pos"]]
    _avoid.extend(_e.pos for _e in get_enemies(ctx))
    return _build_target_card(
        _target,
        game_map=_state.game_map,
        player_pos=_state.player_state["pos"],
        region_w=_state.view_w,
        region_h=_state.view_h,
        hit_chance=_hit,
        hit_weapon_id=_active_wid,
        hit_weapon_range=_hit_range,
        avoid_positions=_avoid,
        quick_rows=(_quick,),
    )

def _render_combat_range_line(
    console, game_map: world.GameMap, cam_x: int, cam_y: int,
) -> str | None:
    """Paint the active weapon's range line; return the weapon id drawn."""
    _range_wid = None
    if _state.weapons_list and any(_state.active_weapons):
        from ..data.weapons import find_weapon as _fw
        _active_ids = _active_weapon_ids()
        if _active_ids:
            _range_wid = min(_active_ids, key=lambda wid: _fw(wid).max_range)
    if _range_wid is None:
        return None
    _tgt = _alive_target()
    if _tgt is None:
        return _range_wid
    _los_ok = _has_los(
        _state.game_map,
        _state.player_state["pos"].x, _state.player_state["pos"].y,
        _tgt.pos.x, _tgt.pos.y,
    )
    _paint_range_line(
        console,
        _state.player_state["pos"], _tgt.pos,
        _range_wid,
        cam_x, cam_y, _state.view_w, _state.view_h, 0, 0,
        color_override=None if _los_ok else (255, 60, 60),
        game_map=game_map,
        max_range=_space_focus.max_range(_range_wid, _state.ctx),
        min_range=_space_focus.min_range(_range_wid, _state.ctx),
    )
    return _range_wid

def _paint_combat_target(console, cam_x: int, cam_y: int) -> None:
    """Highlight the currently-targeted enemy, if any."""
    _tgt = _alive_target()
    if _tgt is not None:
        _paint_target_highlight(
            console, cam_x, cam_y, _state.view_w, _state.view_h, 0, 0, _tgt,
        )

def _paint_status_hud(console, hit_chances, evade, range_weapon_id) -> None:
    """The right-panel combat HUD (the boarding hint rides along)."""
    from ._space_boarding import board_denial, board_target
    _board_enemy, _board_ent = board_target(_state, _state.target_idx)
    _hud.render_combat_hud(
        console,
        screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT,
        player_state=_state.player_state,
        enemies=_state.enemy_insts,
        target_idx=_state.target_idx,
        player_mode="DEFAULT",
        active_weapons=_state.active_weapons,
        weapon_list=tuple(_state.weapons_list),
        hit_chances=hit_chances,
        evade_bonus=evade,
        can_board=_board_enemy is not None
        and board_denial(_state, _board_enemy, _board_ent) is None,
        range_weapon_id=range_weapon_id,
        focus_active=_space_focus.is_focus_active(_state.ctx),
        weapon_qualities=tuple(_state.weapon_qualities),
        ctx=_state.ctx,
    )


def render_frame(console, ctx, game_map: world.GameMap) -> None:
    console.clear()
    _cam_x, _cam_y = _calc_camera()
    world.render_world_view(
        console, game_map,
        region_x=0, region_y=0,
        region_w=_state.view_w, region_h=_state.view_h,
        camera_x=_cam_x, camera_y=_cam_y,
    )

    # Native Pygame gets live shields via the overlay; cells stay neutral.
    _range_wid = _render_combat_range_line(console, game_map, _cam_x, _cam_y)
    _paint_combat_target(console, _cam_x, _cam_y)

    _hit_chances = _build_hit_chances(_alive_target())
    _evade = _calc_dodge_bonus(
        _state.player_state.get("cells_moved_this_turn", 0),
        int(_state.player_state.get("piloting", 0) * 0.5),
    )
    _paint_status_hud(console, _hit_chances, _evade, _range_wid)
    # The message band is painted natively by pygame_combat.present from
    # ctx.log via the shared log_band_rows builder — no cell capture.

async def animate_fire(
    console, ctx, game_map: world.GameMap,
    from_pos: world.Position, to_pos: world.Position, is_hit: bool,
    damage: DamagePopup = None,
    *, weapon_id: str = "",
) -> None:
    """Animate one ship-combat shot with a weapon-appropriate effect."""
    _cam_x, _cam_y = _calc_camera()

    _hit_chances = _build_hit_chances(_alive_target())

    _evade = _calc_dodge_bonus(
        _state.player_state.get("cells_moved_this_turn", 0),
        int(_state.player_state.get("piloting", 0) * 0.5),
    )

    _wid = weapon_id or (_state.weapons_list[0] if _state.weapons_list else "light_laser")
    await _animate_weapon_shot(
        console, ctx, game_map,
        from_pos, to_pos,
        _wid, is_hit=is_hit,
        damage=damage,
        cam_x=_cam_x, cam_y=_cam_y,
        view_w=_state.view_w, view_h=_state.view_h,
        player_state=_state.player_state,
        enemies=_state.enemy_insts,
        target_idx=_state.target_idx,
        log=_state.log,
        weapon_list=tuple(_state.weapons_list),
        active_weapons=_state.active_weapons,
        evade_bonus=_evade,
        hit_chances=_hit_chances,
    )

# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

async def on_kill(game_map: world.GameMap, enemy: EnemyInstance, ctx) -> None:
    """Rules interface — the kill chain lives in ``_space_kills``."""
    await _kill_chain(_state, game_map, enemy, ctx)


def on_player_death(ctx) -> None:
    """Mark the player dead; the encounter wrapper owns presentation."""
    ctx.player_dead = True

# ---------------------------------------------------------------------------
# Defense toggle
# ---------------------------------------------------------------------------

def handle_defense(ctx) -> None:
    max_sh = _state.player_state.get("max_shields", 0)
    if max_sh > 0:
        cur = _state.player_state.get("shield_regen_rate", 0)
        next_rate = (cur + 1) % 11
        _state.player_state["shield_regen_rate"] = next_rate
        if next_rate == 0:
            _state.log.add_colored("Shield regen: OFF", _ml.COLOR_PLAYER_ACTION)
        else:
            _state.log.add_colored(
                f"Shield regen rate: {next_rate}/10", _ml.COLOR_PLAYER_ACTION,
            )
    else:
        _state.log.add_colored("No shields installed.", _ml.COLOR_PLAYER_ACTION)

# ---------------------------------------------------------------------------
# Enemy turns
# ---------------------------------------------------------------------------

async def run_enemy_turns(ctx, game_map: world.GameMap) -> int:
    from ._ai import _run_enemy_turn as _enemy_ai

    _hit_chances = _build_hit_chances(_alive_target())

    _evade = _calc_dodge_bonus(
        _state.player_state.get("cells_moved_this_turn", 0),
        int(_state.player_state.get("piloting", 0) * 0.5),
    )

    _result = await _enemy_ai(
        _state,
        hit_chances=_hit_chances,
        evade_bonus=_evade,
        calc_cam=_calc_camera,
        ctx=ctx,
    )

    if _result == "DEFEAT":
        return 999
    return 0

# ---------------------------------------------------------------------------
# Reinforcements
# ---------------------------------------------------------------------------

def _find_reinforcement_entity(game_map: world.GameMap, pos: world.Position) -> Any:
    """Return the unowned, non-loot entity at ``pos``, or None."""
    for _ge in game_map.entities:
        if getattr(_ge, 'owned', False):
            continue
        if getattr(_ge, 'loot_data', None) is not None:
            continue
        if _ge.pos.x == pos.x and _ge.pos.y == pos.y:
            return _ge
    return None

def _build_reinforcement_enemy(spec, pos: world.Position) -> EnemyInstance:
    """Build one joiner from the JOINER's own spec — the one enemy
    construction path (doc 48 SETTLED 21: joiner stats must match
    their spec). The old player-hull reads fed a discarded player
    state and a spurious None dropped legitimate joiners whenever the
    PLAYER's catalog lookup failed."""
    from ._stats import _build_enemy
    return _build_enemy(spec, pos)

def _join_reinforcements(
    ctx,
    game_map: world.GameMap,
    new_specs: list,
    new_positions: list[world.Position],
    existing_entity_ids: set[int],
) -> None:
    """Build and attach newly-detected reinforcement enemy instances."""
    for _ns, _np in zip(new_specs, new_positions):
        _found_entity = _find_reinforcement_entity(game_map, _np)
        if _found_entity is not None and id(_found_entity) in existing_entity_ids:
            continue
        if any(
            _ei.pos.x == _np.x and _ei.pos.y == _np.y
            for _ei in _state.enemy_insts
        ):
            continue
        _new_ei = _build_reinforcement_enemy(_ns, _np)
        _state.enemy_insts.append(_new_ei)
        _state.enemy_specs.append(_ns)
        if _found_entity is not None:
            _state.enemy_ents[len(_state.enemy_insts) - 1] = _found_entity
            if getattr(_found_entity, 'name', ''):
                _new_ei.name = _found_entity.name
        _state.log.add_colored(
            f"{getattr(_found_entity, 'name', '') or _ns.name} joins the fight!",
            _ml.COLOR_COMBAT_EVENT,
        )

def check_reinforcements(ctx, game_map: world.GameMap) -> None:
    from ..npc_ships import move_npcs as _tick_npcs
    from ..navigation import _detect_combat_encounter as _re_detect
    from .. import solar_system as _ss_module

    # Freeze combatants before the patrol tick so they can't drift/despawn.
    _set_combat_locks(True)

    _tick_npcs(ctx, game_map)

    for _i, _ent in _state.enemy_ents.items():
        if _i < len(_state.enemy_insts) and _state.enemy_insts[_i].alive:
            _state.enemy_insts[_i].pos = _ent.pos

    _new_encounter = _re_detect(ctx, _state.player_state["pos"], _ss_module.current_system())
    if _new_encounter is None:
        return

    _new_specs, _new_positions = _new_encounter
    _existing_entity_ids = {id(_e) for _e in _state.enemy_ents.values()}
    _join_reinforcements(ctx, game_map, _new_specs, _new_positions, _existing_entity_ids)

# ---------------------------------------------------------------------------
# State sync
# ---------------------------------------------------------------------------

def set_player_ap(ctx, ap: int) -> None:
    _state.player_state["ap_remaining"] = ap

def refund_volley_ap(ctx, amount: int) -> None:
    """Momentum origin trait (doc 49): a space kill refunds the killing
    volley's AP cost. Called by the shared fire loop's post-volley hook
    (ground rules implement no such hook)."""
    from ._space_kills import refund_volley_ap as _refund
    _refund(_state, ctx, amount)

def reset_turn(ctx) -> None:
    start_player_turn(_state.player_state)

def sync_state(ctx) -> None:
    # Release the combatants: with the fight over they resume normal
    # patrol movement on the next space tick.
    _set_combat_locks(False)
    _sync_back_hull(_state.player_state, ctx.player_owned_ship)
    _sync_back_ammo(_state.player_state, ctx.player_owned_ship)
    _state.active = False

def get_combat_result() -> CombatResult:
    return _state.cr


def try_board(ctx, game_map: world.GameMap, target_idx: int) -> bool:
    """BOARD: end the fight into the target's crewed interior (6a).

    Ground rules have no hook — the loop probes with getattr."""
    from ._space_boarding import attempt_board
    return attempt_board(_state, target_idx)


# ---------------------------------------------------------------------------
# Flee (doc 54 phase 1)
# ---------------------------------------------------------------------------

async def reaction_volley(ctx, game_map: world.GameMap) -> bool:
    """The flee reaction volley (doc 54): every live hostile that can
    hit the player RIGHT NOW — LOS plus a weapon in range — fires one
    shot from where it stands; no movement, no repositioning. Shots
    pay their real costs and can kill. Returns True when the player
    was destroyed (death wins: the transition never runs)."""
    from ._ai import _enemy_attack, _reaction_pick

    _p_pos = _state.player_state["pos"]
    _hit_chances = _build_hit_chances(_alive_target())
    _evade = _calc_dodge_bonus(
        _state.player_state.get("cells_moved_this_turn", 0),
        int(_state.player_state.get("piloting", 0) * 0.5),
    )
    for _ei in get_enemies(ctx):
        if not _has_los(game_map, _ei.pos.x, _ei.pos.y, _p_pos.x, _p_pos.y):
            continue
        _pick = _reaction_pick(_ei, _distance(_p_pos, _ei.pos), _state.player_state)
        if _pick is None:
            continue
        if await _enemy_attack(
            _state, _ei, _pick[0],
            hit_chances=_hit_chances, evade_bonus=_evade,
            calc_cam=_calc_camera, ctx=ctx,
        ) == "DEFEAT":
            return True
    return False


async def attempt_flee(ctx, game_map: world.GameMap, action: str) -> str | None:
    """The in-combat exit attempt (doc 54 phase 1), space's hook.

    A move whose target is a world exit (planet / station / jump
    gate) runs the SAME exit prompt the main loop runs — cancels and
    refusals fire nothing (SETTLED 1/3); a committing choice eats the
    reaction volley, then the fight ends WITHOUT running the
    transition (the caller executes it from ``cr.flee_exit``, the
    BOARD seam). Returns ``None`` when the target is no exit (the
    move dispatches normally, blocked bumps logging "Blocked."),
    ``"HELD"`` for a canceled or refused exit (full no-op, same
    turn), ``"FLED"`` when the volley was survived, ``"DEFEAT"``
    when it killed the player."""
    if player_ap(ctx) <= 0:
        return None
    _dx, _dy = world.MOVE_KEYS.get(action.partition(":")[2], (0, 0))
    if (_dx, _dy) == (0, 0):
        return None
    from ..game_interactions import (
        _ctx_state_shim, _space_exit_commit, _space_exit_target,
    )
    _shim = _ctx_state_shim(_state.ctx, _state.console)
    _target = _space_exit_target(_shim, _dx, _dy)
    if _target is None:
        return None
    _commit, _refused = await _space_exit_commit(_shim, _target)
    if _commit is None:
        return "HELD"
    if await reaction_volley(ctx, game_map):
        return "DEFEAT"
    _state.cr.flee_exit = _commit
    return "FLED"
