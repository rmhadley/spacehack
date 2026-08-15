"""Ground combat rules — flavor module for the unified combat loop.

All state and behavior specific to on-foot ground combat lives here.
The unified loop in :mod:`._loop` calls these functions by name —
same call shape as :mod:`._rules_space`.

**Combat session state** is encapsulated in :class:`GroundCombatState`,
a single module-level dataclass replacing the old scattered globals.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from .. import world
from .. import message_log as _ml
from ..engine import RNG, SCREEN_WIDTH, SCREEN_HEIGHT, HUD_WIDTH
from ..game_context import GameContext
from ..data.ground_weapons import find_ground_weapon as _find_gw
from ..data.npc_chars import find_npc_char as _find_nc
from ..data.ground_items import list_ground_consumables as _list_gc
from ..ground_equipment import (
    sum_armor_bonus as _sum_armor_bonus,
    sum_armor_defense as _sum_armor_defense,
    tier_filtered_equipment as _tier_loot,
)
from ..ground_consumables import ActiveConsumableEffect, effect_from_spec
from ..xp import (
    sharpshooter_hit_bonus as _sharpshooter_bonus,
    ace_pilot_ap_bonus as _ace_pilot_bonus,
    apply_ground_damage_reduction as ground_damage_taken,
    ground_evade_bonus as _ground_evade_bonus,
    ground_max_hp_bonus as _ground_max_hp_bonus,
    demolitionist_splash_bonus as _demolitionist_splash_bonus,
    plasma_savant_ap_discount as _plasma_ap_discount,
)

from ._types import CombatResult
from ._stats import _distance
from ._ground_math import (
    calc_ground_move_dodge as _calc_ground_move_dodge,
    ground_point_blank_penalty as _ground_point_blank_penalty,
)
from ._ground_charger import (
    attack_ap_cost as _charge_attack_ap_cost,
    charge_bonuses as _charge_bonuses,
    charge_path as _charge_path,
    charge_tiles as _charge_tiles,
    is_charger_melee as _is_charger_melee,
    weapon_range,
)
from ._actions import (
    move_entity,
    _spawn_loot_at_position as _shared_loot,
    _spawn_equipment_loot_at_position as _shared_equipment_loot,
    _spawn_field_item_loot_at_position as _shared_field_item_loot,
    set_combat_locks,
)
from ._animations import (
    _has_los,
    DamagePopup,
)
from ._shot_animations import _animate_ground_shot
from ._ground_render import render_frame
from ._ground_render import (
    presentation_target_card as presentation_target_card,
    toggle_target_card as toggle_target_card,
)

# ---------------------------------------------------------------------------
# GroundEnemyInstance — per-enemy state during combat
# ---------------------------------------------------------------------------

@dataclass
class GroundEnemyInstance:
    """Per-enemy combat state."""

    entity: world.Entity
    spec: Any
    weapon_id: str = ""
    hp: int = 30
    max_hp: int = 30
    ap: int = 4
    ap_total: int = 4
    cells_moved_this_turn: int = 0

    @property
    def alive(self) -> bool:
        return self.hp > 0

    @property
    def pos(self) -> world.Position:
        return self.entity.pos

    @pos.setter
    def pos(self, value: world.Position) -> None:
        self.entity.pos = value

    @property
    def name(self) -> str:
        return self.spec.name if self.spec else "Unknown"

# ---------------------------------------------------------------------------
# GroundCombatState — all session state in one place
# ---------------------------------------------------------------------------

@dataclass
class GroundCombatState:
    """Encapsulates all mutable state for one ground combat encounter."""

    ctx: GameContext
    game_map: world.GameMap
    enemies: list[GroundEnemyInstance] = field(default_factory=list)
    player_hp: int = 30
    player_max_hp: int = 30
    player_ap: int = 4
    player_ap_total: int = 4
    armor_defense: int = 0
    cells_moved_this_turn: int = 0
    active_weapon_list: list[bool] = field(default_factory=list)
    target_idx: int = 0
    console: Any = None
    # Presentation-only: the floating target card shows by default and
    # can be toggled off with ``v``.
    show_target_card: bool = True
    # Session-liveness flag, mirroring SpaceCombatState: cleared by
    # ``sync_state`` so presentation functions stop returning stale cards.
    active: bool = True
    # Presentation-only: while True, ``render_frame`` skips the player's
    # range/accuracy line. Set during shot animations and the whole enemy
    # turn so the line never clutters frames the player isn't acting on.
    range_line_hidden: bool = False
    active_consumable_effects: dict[str, ActiveConsumableEffect] = field(
        default_factory=dict,
    )

_state: GroundCombatState | None = None

# Rendering constants
_RENDER_WIDTH: int = SCREEN_WIDTH - HUD_WIDTH
_RENDER_HEIGHT: int = SCREEN_HEIGHT - 6

# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

def _build_enemy_instance(_ent: world.Entity) -> GroundEnemyInstance | None:
    """Build one enemy instance from a map entity (init + mid-fight joins).

    Reads/stamps ``entity.hp`` so wounds persist across combat sessions:
    LOS aggro ends fights with survivors, and re-engaging must continue
    at the same HP — never a heal-on-retrigger. Guards also get their
    ``guard_post`` stamped here (the leash anchor).
    """
    try:
        _spec = _find_nc(_ent.npc_char_id)
    except KeyError:
        return None
    _wid = ""
    if _spec.weapons:
        _wid = _spec.weapons[0]
    elif _spec.weapon_pick:
        _wid = RNG.choice(_spec.weapon_pick)
    _max_hp = _spec.hp + _spec.stamina // 3
    # Guard leash anchor: stamp once at first engagement and never
    # move it. LOS aggro can end fights with a guard mid-chase; re-
    # stamping on every re-engagement would drag the post to wherever
    # the guard last stood, letting peek-a-boo slowly relocate a
    # drone's defense area across the map. Save/load also preserves it.
    if _spec.behavior == "guard" and getattr(_ent, "guard_post", None) is None:
        _ent.guard_post = world.Position(_ent.pos.x, _ent.pos.y)
    _cur_hp = getattr(_ent, "hp", 0) or _max_hp
    _ent.hp = _cur_hp
    return GroundEnemyInstance(
        entity=_ent, spec=_spec, weapon_id=_wid,
        hp=_cur_hp, max_hp=_max_hp, ap=4, ap_total=4,
    )

def _build_enemies(
    enemy_entities: list[world.Entity],
) -> list[GroundEnemyInstance]:
    """Build combat instances for every valid enemy entity."""
    enemies: list[GroundEnemyInstance] = []
    for entity in enemy_entities:
        instance = _build_enemy_instance(entity)
        if instance is not None:
            enemies.append(instance)
    return enemies

def _player_hp_state(ctx) -> tuple[int, int]:
    """Return ``(current_hp, max_hp)``, growing ground HP to a new max."""
    armor_ids = ctx.equipped_ground_armor.values()
    max_hp = (
        20 + ctx.ground_stats.stamina // 3
        + _sum_armor_bonus(armor_ids, "hp_bonus")
        + _ground_max_hp_bonus(ctx)
    )
    delta = max_hp - ctx.ground_max_hp
    if delta > 0:
        ctx.ground_hp += delta
    return min(ctx.ground_hp, max_hp), max_hp

def _armor_defense_total(ctx) -> int:
    """Sum flat defense across equipped armor pieces."""
    return _sum_armor_defense(ctx.equipped_ground_armor.values())

def _starting_ap_total(ctx) -> int:
    """Per-turn AP pool: 4 + Ace Pilot trait + cybernetic legs."""
    return 4 + _ace_pilot_bonus(ctx) + _sum_armor_bonus(
        ctx.equipped_ground_armor.values(), "ap_bonus",
    )

def init(ctx, enemy_entities: list[world.Entity], game_map: world.GameMap, *, console=None) -> None:
    """Set up combat session state for a ground combat encounter."""
    global _state

    _enemies = _build_enemies(enemy_entities)
    _player_hp, _player_max_hp = _player_hp_state(ctx)
    _armor_defense = _armor_defense_total(ctx)
    _weapons = player_weapons(ctx)
    _player_ap_total = _starting_ap_total(ctx)

    # Clear combat locks from an abnormally-ended previous fight (e.g.
    # an exception that skipped sync_state) so those NPCs patrol again.
    if _state is not None:
        _set_combat_locks(False)

    _state = GroundCombatState(
        ctx=ctx, game_map=game_map,
        enemies=_enemies,
        player_hp=_player_hp, player_max_hp=_player_max_hp,
        player_ap=_player_ap_total, player_ap_total=_player_ap_total,
        armor_defense=_armor_defense,
        active_weapon_list=[True] * len(_weapons),
        console=console,
    )
    # Freeze the engaged set: the ambient patrol pass (move_ground_npcs
    # via check_reinforcements) must never move combat participants —
    # the combat AI is their only mover.
    _set_combat_locks(True, _enemies)

    ctx.log.add_colored(
        f"Combat starts! {', '.join(_e.name for _e in _enemies)} engage!",
        _ml.COLOR_COMBAT_EVENT,
    )
    _log_ambush_reveals(ctx, _enemies)

def _log_ambush_reveals(
    ctx,
    enemy_instances: list[GroundEnemyInstance],
) -> None:
    """Log a burst-out-of-hiding line for every ambusher in the fight.

    Ambushers (ice worms, hull parasites) hold still out of combat;
    the moment combat starts they "burst out" — one colored log line
    per ambusher makes the ambush read clearly in the feed. Reuses the
    already-resolved spec on each :class:`GroundEnemyInstance` (no
    second lookup pass).
    """
    for _inst in enemy_instances:
        if _inst.spec.behavior == "ambusher":
            ctx.log.add_colored(
                f"{_inst.spec.name} bursts out of hiding!",
                _ml.COLOR_IMPORTANT_EVENT,
            )

def _announce_joins(ctx, joined: list[GroundEnemyInstance]) -> None:
    """Log newly joined mobs — ambushers burst out, others join in."""
    for _inst in joined:
        if _inst.spec.behavior != "ambusher":
            ctx.log.add(f"{_inst.spec.name} joins the fight!")
    _log_ambush_reveals(ctx, joined)

# ---------------------------------------------------------------------------
# State accessors
# ---------------------------------------------------------------------------

def player_hp(ctx) -> int:
    return _state.player_hp

def player_max_hp(ctx) -> int:
    return _state.player_max_hp

def player_ap(ctx) -> int:
    return _state.player_ap

def player_ap_total(ctx) -> int:
    return _state.player_ap_total

def player_weapons(ctx) -> list[str]:
    _w = [instance.weapon_id for instance in ctx.equipped_ground_weapons]
    return _w if _w else ["fists"]

def active_weapons(ctx) -> list[bool]:
    return list(_state.active_weapon_list)

def set_active_weapons(ctx, active: list[bool]) -> None:
    _state.active_weapon_list = list(active)

def refresh_equipment_state(ctx) -> None:
    """Refresh cached ground-combat equipment after a character-screen swap."""
    _weapons = [instance.weapon_id for instance in ctx.equipped_ground_weapons] or ["fists"]
    _state.active_weapon_list = [
        _state.active_weapon_list[index]
        if index < len(_state.active_weapon_list) else True
        for index in range(len(_weapons))
    ]
    _state.armor_defense = _sum_armor_defense(ctx.equipped_ground_armor.values())

# ---------------------------------------------------------------------------
# Enemy accessors
# ---------------------------------------------------------------------------

def set_target_idx(ctx, idx: int) -> None:
    _state.target_idx = idx

def get_enemies(ctx) -> list[GroundEnemyInstance]:
    return [e for e in _state.enemies if e.alive]

def enemy_pos(enemy: GroundEnemyInstance) -> world.Position:
    return enemy.pos

def enemy_name(enemy: GroundEnemyInstance) -> str:
    return enemy.name

def enemy_hp(enemy: GroundEnemyInstance) -> int:
    return enemy.hp

def enemy_max_hp(enemy: GroundEnemyInstance) -> int:
    return enemy.max_hp

def enemy_alive(enemy: GroundEnemyInstance) -> bool:
    return enemy.alive

# ---------------------------------------------------------------------------
# Combat math
# ---------------------------------------------------------------------------

def _ground_hit_chance_raw(
    weapon_id: str,
    attacker_reflexes: int,
    target_reflexes: int,
    target_dodge_bonus: int = 0,
    hit_bonus: int = 0,
    range_penalty: int = 0,
) -> int:
    """Base hit chance before movement dodge.

    Half-rate convention shared with ship combat (Gunnery * 0.5):
    each point of attacker Reflexes adds +0.5% accuracy and each
    point of target Reflexes subtracts 0.5% (dodge). All six stats
    live on the same 0-100 scale. ``hit_bonus`` carries permanent
    bonuses (e.g. the Sharpshooter trait's +10%)."""
    _ws = _find_gw(weapon_id)
    return max(5, min(95,
        _ws.accuracy + attacker_reflexes // 2 - target_reflexes // 2
        - target_dodge_bonus + hit_bonus - range_penalty,
    ))

# Player stat progression steps every 5 points: every 5 Strength adds
# +1 melee damage. Monsters keep the legacy 10-point divisor so their
# tuned damage values are unchanged.
_PLAYER_STRENGTH_STEP: int = 5


def _ground_damage_raw(
    weapon_id: str, strength: int, armor_defense: int,
    melee_bonus: int = 0, strength_step: int = 10,
) -> int:
    """Raw hit damage: base + melee bonuses - armor, minimum 1.

    ``armor_bypass`` weapons ignore armor entirely; plasma halves
    ``armor_defense``; ``melee_bonus`` (cybernetic arms) applies only
    to melee weapons. ``strength_step`` is the divisor for the melee
    strength bonus — the player passes ``_PLAYER_STRENGTH_STEP`` (5)
    so every 5 points of Strength adds +1 melee damage.
    """
    _ws = _find_gw(weapon_id)
    _str_bonus = (strength // strength_step) if _ws.damage_type == 'melee' else 0
    _melee = melee_bonus if _ws.damage_type == 'melee' else 0
    if _ws.armor_bypass:
        armor_defense = 0
    elif _ws.damage_type == 'plasma':
        armor_defense = armor_defense // 2
    return max(1, _ws.damage + _str_bonus + _melee - armor_defense)

def hit_chance(weapon_id: str, enemy: GroundEnemyInstance, ctx) -> int:
    _er = enemy.spec.reflexes if enemy.spec else 10
    _move_dodge = _calc_ground_move_dodge(enemy.cells_moved_this_turn)
    _distance_cells = int(_distance(ctx.player.pos, enemy.pos))
    _range_penalty = _ground_point_blank_penalty(
        weapon_id, _distance_cells,
    )
    # Sharpshooter trait: +10% hit chance; cybernetic eyes add more.
    _hit_bonus = _sharpshooter_bonus(ctx) + _sum_armor_bonus(
        ctx.equipped_ground_armor.values(), "hit_bonus",
    )
    if _is_charger_melee(ctx, weapon_id):
        _hit_bonus += _charge_bonuses(_charge_tiles(ctx))[0]
    return _ground_hit_chance_raw(
        weapon_id, ctx.ground_stats.reflexes, _er,
        target_dodge_bonus=_move_dodge, hit_bonus=_hit_bonus,
        range_penalty=_range_penalty,
    )

def damage(weapon_id: str, enemy: GroundEnemyInstance, ctx) -> tuple[int, bool]:
    """Apply weapon damage to a ground enemy. Returns ``(dmg, False)``.

    Enemy armor (``enemy.spec.armor``) is subtracted here, with plasma
    halving it via :func:`_ground_damage_raw`; cybernetic arms add a melee
    bonus. Ground combat has no glancing mechanic, but the unified loop
    unpacks ``(dmg, is_glancing)`` for both rule sets — ground always
    reports ``False``.
    """
    _armor = enemy.spec.armor if enemy.spec else 0
    _melee_bonus = _sum_armor_bonus(ctx.equipped_ground_armor.values(), "melee_bonus")
    if _is_charger_melee(ctx, weapon_id):
        _melee_bonus += _charge_bonuses(_charge_tiles(ctx))[1]
    _dmg = _ground_damage_raw(
        weapon_id, ctx.ground_stats.strength, _armor, _melee_bonus,
        strength_step=_PLAYER_STRENGTH_STEP,
    )
    enemy.hp -= _dmg
    enemy.ap = max(0, enemy.ap - int(weapon_id == "stun_baton"))
    # Wound persistence: sync to the map entity so a fight that ends
    # with survivors (LOS aggro) keeps their wounds on re-engagement.
    if enemy.entity is not None:
        enemy.entity.hp = max(0, enemy.hp)
    return _dmg, False

def is_explosive(weapon_id: str) -> bool:
    """Whether a ground weapon resolves as an area blast."""
    return _find_gw(weapon_id).damage_type == "explosive"

def _apply_explosive_enemy_hit(
    weapon_id: str,
    enemy: GroundEnemyInstance,
    primary: GroundEnemyInstance,
    ctx,
    *,
    primary_hit: bool = True,
) -> tuple[GroundEnemyInstance, int, bool] | None:
    """Apply one enemy's primary-or-splash share of an explosion."""
    if not enemy.alive:
        return None
    _dx = abs(enemy.pos.x - primary.pos.x)
    _dy = abs(enemy.pos.y - primary.pos.y)
    if _dx > 1 or _dy > 1:
        return None
    _armor = enemy.spec.armor if enemy.spec else 0
    _full_damage = _ground_damage_raw(
        weapon_id, ctx.ground_stats.strength, _armor,
        strength_step=_PLAYER_STRENGTH_STEP,
    )
    _is_primary = enemy is primary and primary_hit
    if _is_primary:
        _damage = _full_damage
    else:
        _splash_pct = 50 + _demolitionist_splash_bonus(ctx)
        _damage = max(1, _full_damage * _splash_pct // 100)
    enemy.hp -= _damage
    if enemy.entity is not None:
        enemy.entity.hp = max(0, enemy.hp)
    return enemy, _damage, _is_primary

def explosive_blast(
    weapon_id: str,
    primary: GroundEnemyInstance,
    ctx,
    *,
    primary_hit: bool = True,
) -> tuple[tuple[tuple[GroundEnemyInstance, int, bool], ...], int]:
    """Resolve an explosive impact around ``primary`` with friendly fire.

    A direct hit damages primary fully; a miss catches it for half damage
    alongside neighboring cells. The player also takes half damage nearby.
    """
    _enemy_hits = tuple(
        _hit for _enemy in _state.enemies
        if (_hit := _apply_explosive_enemy_hit(
            weapon_id, _enemy, primary, ctx, primary_hit=primary_hit,
        )) is not None
    )
    _player_dx = abs(ctx.player.pos.x - primary.pos.x)
    _player_dy = abs(ctx.player.pos.y - primary.pos.y)
    if _player_dx <= 1 and _player_dy <= 1:
        _full_damage = _ground_damage_raw(
            weapon_id, 0, _state.armor_defense,
        )
        _splash_pct = 50 + _demolitionist_splash_bonus(ctx)
        _splash_damage = max(1, _full_damage * _splash_pct // 100)
        _player_damage = ground_damage_taken(ctx, _splash_damage)
        _state.player_hp -= _player_damage
    else:
        _player_damage = 0
    return _enemy_hits, _player_damage

# ---------------------------------------------------------------------------
# Weapon actions
# ---------------------------------------------------------------------------

def can_fire(slot_idx: int, ctx) -> tuple[bool, str]:
    _weapons = player_weapons(ctx)
    if not (0 <= slot_idx < len(_weapons)):
        return False, "Unknown weapon"
    _wid = _weapons[slot_idx]
    _ws = _find_gw(_wid)
    _alive = get_enemies(ctx)
    if _state.target_idx >= len(_alive):
        return False, "No valid target"
    _target = _alive[_state.target_idx]
    _dist = int(_distance(ctx.player.pos, _target.pos))
    _min_range, _max_range = weapon_range(_wid, ctx, _state.player_ap)
    _is_charge = _is_charger_melee(ctx, _wid) and _dist > _ws.max_range
    if _dist > _max_range:
        return False, f"Out of range ({_dist}u, need {_min_range}-{_max_range})"
    _reason = ""
    if _is_charge and _charge_path(ctx, _target, _state.game_map, _state.player_ap) is None:
        return False, "No clear path to charge"
    if _is_charge: _reason = f"Charge {_dist}u into melee."
    elif _dist < _ws.min_range:
        _penalty = _ground_point_blank_penalty(_wid, _dist)
        _reason = f"Emergency point-blank shot: {_penalty}% accuracy penalty."
    _ap_cost = (
        _charge_attack_ap_cost(ctx, _wid, _state.player_ap)
        if _is_charge else weapon_ap_cost(_wid, ctx)
    )
    if _state.player_ap < _ap_cost:
        return False, "Need AP to charge" if _is_charge else f"Need {_ap_cost} AP (have {_state.player_ap})"
    if not _is_charge and not _has_los(
        _state.game_map,
        ctx.player.pos.x, ctx.player.pos.y,
        _target.pos.x, _target.pos.y,
    ):
        return False, "Blocked by wall"
    _ammo_reason = _ground_ammo_reason(ctx, slot_idx, _ws)
    if _ammo_reason:
        return False, _ammo_reason
    return True, _reason

def _ground_ammo_reason(ctx, slot_idx: int, spec) -> str:
    """Return the firing failure reason for a reloadable weapon."""
    _instance = (
        ctx.equipped_ground_weapons[slot_idx]
        if slot_idx < len(ctx.equipped_ground_weapons) else None
    )
    if _instance is None or _instance.loaded_ammo is None:
        return ""
    if _instance.loaded_ammo <= 0:
        return "Empty magazine - reload (R)."
    if _instance.loaded_ammo < spec.ammo_per_shot:
        return "Not enough rounds loaded."
    return ""


def weapon_ap_cost(weapon_id: str, ctx) -> int:
    _spec = _find_gw(weapon_id)
    _discount = (
        _plasma_ap_discount(ctx)
        if getattr(_spec, "damage_type", "") == "plasma" else 0
    )
    return max(1, _charge_attack_ap_cost(ctx, weapon_id, _state.player_ap) - _discount)

def weapon_name(weapon_id: str, ctx) -> str:
    return _find_gw(weapon_id).name

def consume_shot(slot_idx: int, ctx) -> None:
    """Decrement one weapon instance's loaded ammo after an accepted shot."""
    if slot_idx >= len(ctx.equipped_ground_weapons):
        return  # implicit fists: infinite
    from ..ground_equipment import consume_weapon_round

    ctx.equipped_ground_weapons[slot_idx] = consume_weapon_round(
        ctx.equipped_ground_weapons[slot_idx],
    )

def _reloadable_slots(ctx) -> tuple[tuple[int, object, object, int], ...]:
    """Return active weapons with a matching reserve and room to reload."""
    from ..ground_equipment import reserve_ammo_count

    candidates = []
    for _slot, _instance in enumerate(ctx.equipped_ground_weapons):
        if _slot >= len(_state.active_weapon_list) or not _state.active_weapon_list[_slot]:
            continue
        _spec = _find_gw(_instance.weapon_id)
        if _instance.loaded_ammo is None or _instance.loaded_ammo >= _spec.ammo_capacity:
            continue
        _reserve = reserve_ammo_count(ctx.ground_expedition_items, _spec.ammo_type)
        if _reserve > 0:
            candidates.append((_slot, _instance, _spec, _reserve))
    return tuple(candidates)

def _reload_slot(ctx, slot: int) -> bool:
    """Reload one validated slot transactionally and charge its AP cost."""
    from ..ground_equipment import apply_reload

    _instance = ctx.equipped_ground_weapons[slot]
    _spec = _find_gw(_instance.weapon_id)
    _wname = _spec.name
    if _state.player_ap < _spec.reload_ap_cost:
        ctx.log.add(
            f"Need {_spec.reload_ap_cost} AP to reload "
            f"(have {_state.player_ap}).",
        )
        return False
    try:
        _new = apply_reload(
            ctx.equipped_ground_weapons, slot, ctx.ground_expedition_items,
        )
    except (IndexError, KeyError, ValueError) as exc:
        ctx.log.add(f"{_wname}: {exc}")
        return False
    _state.player_ap -= _spec.reload_ap_cost
    ctx.log.add(f"Reloaded {_wname} ({_new.loaded_ammo}/{_spec.ammo_capacity}).")
    return True

def _choose_reload_slot(ctx, candidates) -> int | None:
    """Show the compact weapon chooser and return the selected slot."""
    from .. import pygame_story

    options = tuple(
        (
            f"{_spec.name} {_instance.loaded_ammo}/{_spec.ammo_capacity} "
            f"RES {_reserve}",
            f"RELOAD_SLOT:{_slot}",
        )
        for _slot, _instance, _spec, _reserve in candidates
    )
    chosen = pygame_story.choose(
        ctx,
        title="RELOAD WEAPON",
        body="Choose a weapon to reload.",
        options=options,
        caption="spacehack - reload",
        compact=True,
    )
    if chosen in {None, "__BACK__", "__DISMISS__", "__GUIDE__"}:
        return None
    if chosen == "__QUIT__":
        raise SystemExit
    try:
        _slot = int(chosen.split(":", 1)[1])
    except (IndexError, ValueError):
        ctx.log.add("That reload choice is invalid.")
        return None
    return _slot if _slot in {_candidate[0] for _candidate in candidates} else None

def reload_weapon(ctx) -> bool:
    """Reload one active weapon, choosing when multiple can reload."""
    _candidates = _reloadable_slots(ctx)
    if not _candidates:
        ctx.log.add("No active weapon can be reloaded.")
        return False
    if len(_candidates) == 1:
        return _reload_slot(ctx, _candidates[0][0])
    _slot = _choose_reload_slot(ctx, _candidates)
    return _slot is not None and _reload_slot(ctx, _slot)

# ---------------------------------------------------------------------------
# Player movement
# ---------------------------------------------------------------------------

def try_move(ctx, game_map: world.GameMap, dx: int, dy: int) -> bool:
    # Enemies and furniture block; loot is a walkable floor object.
    _new_pos, ok = move_entity(
        ctx.player.pos, dx, dy, game_map, exclude=ctx.player,
    )
    if not ok:
        return False
    ctx.player.pos = _new_pos
    _state.player_ap -= 1
    _state.cells_moved_this_turn += 1
    from ..dungeon import reveal_around as _reveal_around
    _reveal_around(game_map, ctx.player.pos, radius=game_map.sight_radius)
    return True

# ---------------------------------------------------------------------------
# Animation
# ---------------------------------------------------------------------------

@contextmanager
def _range_line_hidden() -> Iterator[None]:
    """Context manager: suppress the player's range/accuracy line.

    The line is a player-turn aiming affordance only. Shot animations
    and the whole enemy turn wrap their frames in this so the beam /
    tracer / enemy movement reads cleanly instead of sitting under a
    line the player isn't aiming with. Restores the previous state on
    exit (a shot fired mid-enemy-turn keeps it hidden, for example).
    """
    _was_hidden = _state.range_line_hidden
    _state.range_line_hidden = True
    try:
        yield
    finally:
        _state.range_line_hidden = _was_hidden

def animate_fire(
    console, ctx, game_map: world.GameMap,
    from_pos: world.Position, to_pos: world.Position, is_hit: bool,
    damage: DamagePopup = None,
    *, weapon_id: str = "",
) -> None:
    """Animate one ground-combat shot with a weapon-appropriate effect.

    Hides the range/accuracy line for the duration of the animation so
    the beam/tracer reads cleanly instead of being buried under the
    player's own targeting aid.
    """
    _wid = weapon_id or ((player_weapons(ctx) or ["fists"])[0])
    with _range_line_hidden():
        _animate_ground_shot(
            console, ctx, game_map,
            from_pos, to_pos,
            _wid, is_hit=is_hit,
            damage=damage,
            render_callback=render_frame,
        )

# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def on_kill(game_map: world.GameMap, enemy: GroundEnemyInstance, ctx) -> None:
    _ent = enemy.entity
    if _ent is not None and _ent in game_map.entities:
        game_map.entities.remove(_ent)

    if _ent is not None and enemy.spec and enemy.spec.loot_pool:
        _min, _max = enemy.spec.loot_count
        _shared_loot(
            game_map, _ent.pos, enemy.spec.loot_pool,
            count_range=(_min, _max), qty_range=(1, 2),
        )
    if _ent is not None and enemy.spec and enemy.spec.equipment_loot_pool:
        _pool = _tier_loot(enemy.spec.equipment_loot_pool, enemy.spec.tier)
        _shared_equipment_loot(game_map, _ent.pos, _pool)
    if _ent is not None and enemy.spec and enemy.spec.field_item_loot_pool:
        _shared_field_item_loot(
            game_map, _ent.pos, enemy.spec.field_item_loot_pool,
            count_range=enemy.spec.field_item_loot_count,
        )

    if enemy.spec:
        from ..xp import add_xp as _add_xp
        _add_xp(ctx, enemy.spec.xp_reward)
        if hasattr(ctx, 'player_counters'):
            ctx.player_counters.total_kills += 1

    enemy.hp = 0

def on_player_death(ctx) -> None:
    ctx.player_dead = True
    ctx.log.add_colored("You collapse from your wounds...", _ml.COLOR_COMBAT_EVENT)

def handle_defense(ctx) -> None:
    pass

def apply_consumable_effect(ctx, spec) -> bool:
    """Apply a validated consumable effect to the active combat state."""
    if spec.effect_id == "restore_hp":
        _before = _state.player_hp
        _state.player_hp = min(
            _state.player_max_hp,
            _state.player_hp + spec.combat_heal_amount,
        )
        _healed = _state.player_hp - _before
        if _healed > 0:
            ctx.log.add_colored(
                f"{spec.name}: +{_healed} HP.",
                _ml.COLOR_PLAYER_ACTION,
            )
    _effect = effect_from_spec(spec)
    if _effect is not None:
        _state.active_consumable_effects[spec.effect_id] = _effect
    return spec.effect_id in {"restore_hp", "stim"}

def _consumable_name_for_effect(effect_id: str) -> str:
    """Resolve a friendly catalog name for a temporary effect."""
    for _spec in _list_gc():
        if _spec.effect_id == effect_id:
            return _spec.name
    return "Regeneration"

def _advance_consumable_effects() -> int:
    """Apply regeneration and return the current temporary AP bonus."""
    _ap_bonus = 0
    _remaining: dict[str, ActiveConsumableEffect] = {}
    for _effect_id, _effect in _state.active_consumable_effects.items():
        if _effect.regen_amount:
            _before = _state.player_hp
            _state.player_hp = min(
                _state.player_max_hp,
                _state.player_hp + _effect.regen_amount,
            )
            _healed = _state.player_hp - _before
            if _healed > 0:
                _effect_name = _consumable_name_for_effect(_effect_id)
                _state.ctx.log.add_colored(
                    f"{_effect_name} regeneration: +{_healed} HP.",
                    _ml.COLOR_PLAYER_ACTION,
                )
        if _effect.ap_bonus:
            _ap_bonus += _effect.ap_bonus
        _next = _effect.remaining_turns - 1
        if _next > 0:
            _remaining[_effect_id] = ActiveConsumableEffect(
                _effect.effect_id, _next,
                _effect.regen_amount, _effect.ap_bonus,
            )
    _state.active_consumable_effects = _remaining
    return _ap_bonus

# ---------------------------------------------------------------------------
# Enemy turns
# ---------------------------------------------------------------------------

def run_enemy_turns(ctx, game_map: world.GameMap) -> int:
    from ._ai_ground import run_ground_enemy_turn as _enemy_ai

    # The enemy turn is not the player's aiming phase: hide the range
    # line for every movement step and attack animation in it, then
    # restore it for the player's next interactive frame.
    with _range_line_hidden():
        return _run_enemy_turns_impl(ctx, game_map, _enemy_ai)

def _player_ground_dodge(ctx) -> int:
    """Return current ground dodge including the Evasive trait."""
    return _calc_ground_move_dodge(_state.cells_moved_this_turn) + _ground_evade_bonus(ctx)


def _run_enemy_turns_impl(ctx, game_map: world.GameMap, _enemy_ai) -> int:
    _player_dodge = _player_ground_dodge(ctx)
    _total_dmg = 0
    for _gei in _state.enemies:
        if not _gei.alive or _gei.ap <= 0 or not _gei.weapon_id:
            continue

        _ap_before = _gei.ap
        _new_ap, _dmg, _fired = _enemy_ai(
            ctx,
            enemy_weapon_id=_gei.weapon_id,
            enemy_spec=_gei.spec,
            enemy_ap=_gei.ap,
            player_pos=ctx.player.pos,
            enemy_entity=_gei.entity,
            game_map=game_map,
            armor_defense=_state.armor_defense,
            console=_state.console,
            render_callback=render_frame,
            player_dodge=_player_dodge,
        )
        _ap_spent = _ap_before - _new_ap
        if _fired:
            try:
                _weapon_ap = _find_gw(_gei.weapon_id).ap_cost
            except KeyError:
                _weapon_ap = 1
            _gei.cells_moved_this_turn += max(0, _ap_spent - _weapon_ap)
        else:
            _gei.cells_moved_this_turn += _ap_spent
        _gei.ap = _new_ap

        if _dmg > 0:
            _dmg = ground_damage_taken(ctx, _dmg)
            _state.player_hp -= _dmg
            _total_dmg += _dmg
            if _state.player_hp <= 0:
                return 999

    return _total_dmg

def refresh_engaged(ctx, game_map: world.GameMap) -> None:
    """Join scan: any hostile now visible to the player joins immediately.

    Runs at the top of every combat round (design doc 12) so a mob
    that walks into view — or was on screen when the last engaged
    enemy died — is part of the fight right away: targetable and
    acting this round. Joined mobs keep their wounds (``entity.hp``).
    """
    from ._encounter import visible_hostiles as _vh
    _radius = getattr(game_map, "sight_radius", 8)
    _visible = _vh(ctx, game_map, ctx.player.pos, _radius)
    _engaged = {id(_e.entity) for _e in _state.enemies}
    _joined: list[GroundEnemyInstance] = []
    for _ent in _visible:
        if id(_ent) in _engaged:
            continue
        _inst = _build_enemy_instance(_ent)
        if _inst is not None:
            _joined.append(_inst)
    if _joined:
        _state.enemies.extend(_joined)
        _announce_joins(ctx, _joined)

def _set_combat_locks(locked: bool, instances=None) -> None:
    """Freeze/release engaged enemies from the ``move_ground_npcs`` pass.

    See :func:`combat._actions.set_combat_locks` for the flag contract.
    """
    _insts = instances if instances is not None else _state.enemies
    set_combat_locks(locked, (_gei.entity for _gei in _insts))

def check_reinforcements(ctx, game_map: world.GameMap) -> None:
    """Move non-combat ground NPCs during combat (matches space behaviour).

    Combat joins no longer live here — :func:`refresh_engaged` handles
    them at loop top so new mobs are engaged immediately. Idle mobs
    keep wandering so the dungeon stays alive around the fight; the
    engaged enemies are frozen (``combat_locked``) so the patrol pass
    leaves them to the combat AI.
    """
    from ..ground_npcs import move_ground_npcs as _move_ground_npcs

    # Freeze the engaged set (initial enemies + mid-fight joins) before
    # the patrol tick.
    _set_combat_locks(True)
    _move_ground_npcs(ctx, game_map)

def on_disengage(ctx, game_map: world.GameMap) -> None:
    """Give surviving hunters a short memory of where LOS broke."""
    from ..ground_npcs import remember_last_seen as _remember_last_seen

    _survivors = [
        _enemy.entity for _enemy in _state.enemies
        if _enemy.alive and _enemy.entity in game_map.entities
    ]
    _remember_last_seen(_survivors, ctx.player.pos)

def combat_should_end(ctx, game_map: world.GameMap, enemies: list) -> bool:
    """True when the player sees no hostile — LOS aggro end condition.

    The fight ends when nothing hostile is in view: all engaged dead
    (VICTORY) or survivors out of sight (DISENGAGED — they revert to
    map behavior and re-trigger if spotted again). ``enemies`` is kept
    for the rules-module contract (space uses it); ground derives the
    end purely from the map, so a freshly visible-but-unjoined mob
    keeps the fight going instead of declaring victory over it.
    """
    from ._encounter import visible_hostiles as _vh
    _radius = getattr(game_map, "sight_radius", 8)
    return not _vh(ctx, game_map, ctx.player.pos, _radius)

# ---------------------------------------------------------------------------
# State sync
# ---------------------------------------------------------------------------

def set_player_ap(ctx, ap: int) -> None:
    _state.player_ap = ap

def reset_turn(ctx) -> None:
    _state.player_ap = _state.player_ap_total + _advance_consumable_effects()
    _state.cells_moved_this_turn = 0
    for _gei in _state.enemies:
        _gei.ap = _gei.ap_total
        _gei.cells_moved_this_turn = 0

def sync_state(ctx) -> None:
    # Release the engaged enemies: with the fight over they resume
    # patrol/wander behaviour on the next dungeon tick.
    _set_combat_locks(False)
    _state.active = False
    ctx.ground_hp = max(0, _state.player_hp)
    ctx.ground_max_hp = _state.player_max_hp

def get_combat_result() -> CombatResult:
    _cr = CombatResult()
    for _gei in _state.enemies:
        if not _gei.alive and _gei.spec:
            _cr.defeated_names.append(_gei.spec.name)
            _cr.defeated_spec_ids.append(_gei.spec.id)
    return _cr
