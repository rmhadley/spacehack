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
from .. import noise
from ..engine import SCREEN_WIDTH, SCREEN_HEIGHT, HUD_WIDTH
from ..game_context import GameContext
from ..data.ground_weapons import find_ground_weapon as _find_gw
from .. import ground_scale
from ..data.npc_chars import find_npc_char as _find_nc
from ..ground_equipment import (
    sum_armor_bonus as _sum_armor_bonus,
    sum_armor_defense as _sum_armor_defense,
)
from ..ground_consumables import ActiveConsumableEffect
from ..ground_weapon_sets import swap_sets_logged
from ..xp import (
    sharpshooter_hit_bonus as _sharpshooter_bonus,
    ace_pilot_ap_bonus as _ace_pilot_bonus,
    apply_ground_damage_reduction as ground_damage_taken,
    ground_evade_bonus as _ground_evade_bonus,
    ground_max_hp_total as _ground_max_hp_total,
    nimble_ap_bonus as _nimble_ap_bonus,
    plasma_savant_ap_discount as _plasma_ap_discount,
    sturdy_armor_bonus as _sturdy_armor_bonus,
    sturdy_melee_bonus as _sturdy_melee_bonus,
)

from ._types import CombatResult, FleeExit
from ._stats import _distance, _roll_ap
from . import _ground_blast
from ._ground_math import (
    calc_ground_move_dodge as _calc_ground_move_dodge,
    ground_damage_raw as _ground_damage_raw,
    ground_hit_chance_raw as _ground_hit_chance_raw,
    ground_point_blank_penalty as _ground_point_blank_penalty,
)
from ._ground_math import _PLAYER_STRENGTH_STEP
from ._ground_charger import (
    attack_ap_cost as _charge_attack_ap_cost,
    charge_bonuses as _charge_bonuses,
    charge_path as _charge_path,
    charge_tiles as _charge_tiles,
    is_charger_melee as _is_charger_melee,
    weapon_range,
)
from . import _ground_deadshot
from ._actions import (
    move_entity,
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
    weapon_quality: int = 0
    # The band this enemy spawned at (doc 48 SETTLED 35) and its
    # derived six-block — combat math reads these, never spec fields.
    band: int = 0
    stats: Any = None
    hp: int = 30
    max_hp: int = 30
    ap: int = 4
    ap_total: int = 4
    # Enemy-side consumable effect state (doc 48 SETTLED 36) —
    # fight-scoped, never serialized: a new fight re-derives from the
    # entity's pre-rolled carried stamp.
    stim_turns: int = 0
    stim_ap_bonus: int = 0
    regen_turns: int = 0
    regen_amount: int = 0
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
    # Fractional AP (TE4-style): per-round gain in twentieths and the
    # banked fraction that rolls into the next round's pool. Ground
    # gains are integer today (4 + trait/armor bonuses), so the carry
    # stays 0 — the mechanism is uniform with ship combat for future
    # fractional bonuses.
    player_ap_gain_twentieths: int = 80
    player_ap_carry_twentieths: int = 0
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
    # Doc 53 killer tracking: the last hostile damage source's label
    # (enemy + wielded variant), or the settled self-splash line.
    # Per-fight session state, never serialized.
    last_attacker: str | None = None
    # Doc 54 phase 2: the committed stair-dance exit (verb = the
    # transition tile kind) — set when the fight ends DISENGAGED at a
    # world exit; get_combat_result copies it onto the CombatResult.
    # Session-scoped, never serialized.
    flee_exit: "FleeExit | None" = None

_state: GroundCombatState | None = None

# Rendering constants
_RENDER_WIDTH: int = SCREEN_WIDTH - HUD_WIDTH
_RENDER_HEIGHT: int = SCREEN_HEIGHT - 6

# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

def _stamp_enemy_loadout(_ent: world.Entity, _spec) -> int:
    """First-resolution stamps at combat entry (doc 48 SETTLED 36/37):
    the pre-rolled carried consumables land once (what they drop is
    what they carry); returns the spec-derived AP total."""
    from ._actions import roll_carried_consumables
    from ._ground_effects import enemy_ap_total

    if getattr(_ent, "carried_items", None) is None:
        _ent.carried_items = roll_carried_consumables(_spec)
    return enemy_ap_total(_spec)


def _build_enemy_instance(
    _ent: world.Entity, game_map=None,
) -> GroundEnemyInstance | None:
    """Build one enemy instance from a map entity (init + mid-fight joins).

    Reads/stamps ``entity.hp`` so wounds persist across combat sessions:
    LOS aggro ends fights with survivors, and re-engaging must continue
    at the same HP — never a heal-on-retrigger. Guards also get their
    ``guard_post`` stamped here (the leash anchor — once, never dragged
    by peek-a-boo re-engagement; SETTLED 37's investigation perch is the
    only re-stamp). Stats resolve through the band resolver (SETTLED 35);
    the weapon resolves ONCE and persists on the entity (SETTLED 37).
    """
    try:
        _spec = _find_nc(_ent.npc_char_id)
    except KeyError:
        return None
    _band = ground_scale.entity_band(_ent, game_map)
    _stats = ground_scale.derive_stats(_spec, _band)
    _wid = noise.ensure_rolled_weapon(_ent, game_map, _spec)
    _quality = _ent.rolled_weapon[1] if _ent.rolled_weapon else 0
    _ap_total = _stamp_enemy_loadout(_ent, _spec)
    _max_hp = _spec.hp + _stats.stamina // 3
    if _spec.behavior == "guard" and getattr(_ent, "guard_post", None) is None:
        _ent.guard_post = world.Position(_ent.pos.x, _ent.pos.y)
    _cur_hp = min(getattr(_ent, "hp", 0) or _max_hp, _max_hp)
    _ent.hp = _cur_hp
    return GroundEnemyInstance(
        entity=_ent, spec=_spec, weapon_id=_wid,
        weapon_quality=_quality,
        band=_band, stats=_stats,
        hp=_cur_hp, max_hp=_max_hp, ap=_ap_total, ap_total=_ap_total,
    )


def _build_enemies(
    enemy_entities: list[world.Entity], game_map=None,
) -> list[GroundEnemyInstance]:
    """Build combat instances for every valid enemy entity."""
    enemies: list[GroundEnemyInstance] = []
    for entity in enemy_entities:
        instance = _build_enemy_instance(entity, game_map)
        if instance is not None:
            enemies.append(instance)
    return enemies

def _player_hp_state(ctx) -> tuple[int, int]:
    """Return ``(current_hp, max_hp)``, growing ground HP to a new max."""
    max_hp = _ground_max_hp_total(ctx)
    delta = max_hp - ctx.ground_max_hp
    if delta > 0:
        ctx.ground_hp += delta
    return min(ctx.ground_hp, max_hp), max_hp

def _armor_defense_total(ctx) -> int:
    """Worn-armor defense plus Sturdy's always-on +2 (doc 49: a
    Martian counts 2 armor with none worn; worn pieces stack on top)."""
    return _sum_armor_defense(ctx.equipped_ground_armor.values()) \
        + _sturdy_armor_bonus(ctx)

def _starting_ap_gain_twentieths(ctx) -> int:
    """Per-round AP gain in twentieths: 4 + Ace Pilot + Nimble + legs."""
    return 80 + 20 * (
        _ace_pilot_bonus(ctx) + _nimble_ap_bonus(ctx)
        + _sum_armor_bonus(ctx.equipped_ground_armor.values(), "ap_bonus")
    )

def init(ctx, enemy_entities: list[world.Entity], game_map: world.GameMap, *, console=None) -> None:
    """Set up combat session state for a ground combat encounter."""
    global _state

    _enemies = _build_enemies(enemy_entities, game_map)
    _player_hp, _player_max_hp = _player_hp_state(ctx)
    _armor_defense = _armor_defense_total(ctx)
    _weapons = player_weapons(ctx)
    _player_ap_gain = _starting_ap_gain_twentieths(ctx)
    _player_ap_total = _player_ap_gain // 20

    # Clear combat locks from an abnormally-ended previous fight (e.g.
    # an exception that skipped sync_state) so those NPCs patrol again;
    # the same recovery retires the stale session's movement mode.
    if _state is not None:
        _set_combat_locks(False)
        _state.active = False

    _state = GroundCombatState(
        ctx=ctx, game_map=game_map,
        enemies=_enemies,
        player_hp=_player_hp, player_max_hp=_player_max_hp,
        player_ap=_player_ap_total, player_ap_total=_player_ap_total,
        player_ap_gain_twentieths=_player_ap_gain, player_ap_carry_twentieths=0,
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


def last_attacker(ctx) -> str | None:
    """The tracked killer label for the tombstone (doc 53); None until
    hostile damage lands — the header renders the fallback line."""
    return _state.last_attacker


def combat_active(ctx) -> bool:
    """Whether a ground fight is live — the combat-time movement mode
    key (doc 48 SETTLED 17/25): un-engaged entities move their AP in
    tiles while True, everyone folds back to the 1-tick stroll after."""
    return _state is not None and _state.active

def player_max_hp(ctx) -> int:
    return _state.player_max_hp

def player_ap(ctx) -> int:
    return _state.player_ap

def player_ap_total(ctx) -> int:
    return _state.player_ap_total

def player_weapons(ctx) -> list[str]:
    _w = [instance.weapon_id for instance in ctx.equipped_ground_weapons]
    return _w if _w else ["fists"]


def player_weapon_quality(ctx, slot: int) -> int:
    """The equipped weapon instance's rolled quality for one slot."""
    _weapons = ctx.equipped_ground_weapons
    return _weapons[slot].quality if 0 <= slot < len(_weapons) else 0

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
    _state.armor_defense = _armor_defense_total(ctx)

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

def hit_chance(
    weapon_id: str, enemy: GroundEnemyInstance, ctx, quality: int = 0,
) -> int:
    _er = enemy.stats.reflexes if enemy.stats else 10
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
    if _ground_deadshot.is_deadshot(ctx, weapon_id):
        _hit_bonus += _ground_deadshot.ap_power_hit_bonus(ctx, weapon_id)
    return _ground_hit_chance_raw(
        weapon_id, ctx.ground_stats.reflexes, _er,
        target_dodge_bonus=_move_dodge, hit_bonus=_hit_bonus,
        range_penalty=_range_penalty, quality=quality,
    )

def damage(
    weapon_id: str, enemy: GroundEnemyInstance, ctx, quality: int = 0,
) -> tuple[int, bool]:
    """Apply weapon damage to a ground enemy. Returns ``(dmg, False)``.

    Enemy armor (``enemy.spec.armor``) is subtracted here, with plasma
    halving it via :func:`_ground_damage_raw`; cybernetic arms add a melee
    bonus. Ground combat has no glancing mechanic, but the unified loop
    unpacks ``(dmg, is_glancing)`` for both rule sets — ground always
    reports ``False``.
    """
    _armor = enemy.spec.armor if enemy.spec else 0
    _melee_bonus = _sum_armor_bonus(ctx.equipped_ground_armor.values(), "melee_bonus")
    # Sturdy's +2 melee damage is melee-only, fists included (doc 49).
    if _find_gw(weapon_id).damage_type == "melee":
        _melee_bonus += _sturdy_melee_bonus(ctx)
    if _is_charger_melee(ctx, weapon_id):
        _melee_bonus += _charge_bonuses(_charge_tiles(ctx))[1]
    _dmg = _ground_damage_raw(
        weapon_id, ctx.ground_stats.strength, _armor, _melee_bonus,
        strength_step=_PLAYER_STRENGTH_STEP, quality=quality,
    )
    if _ground_deadshot.is_deadshot(ctx, weapon_id):
        _dmg += _ground_deadshot.ap_power_damage_bonus(ctx, weapon_id)
    enemy.hp -= _dmg
    enemy.ap = max(0, enemy.ap - int(weapon_id == "stun_baton"))
    # Wound persistence: sync to the map entity so a fight that ends
    # with survivors (LOS aggro) keeps their wounds on re-engagement.
    if enemy.entity is not None:
        enemy.entity.hp = max(0, enemy.hp)
    return _dmg, False

def is_explosive(weapon_id: str) -> bool:
    """Whether a ground weapon resolves as an area blast."""
    return _ground_blast.is_explosive(weapon_id)


def explosive_blast(
    weapon_id: str,
    primary: GroundEnemyInstance,
    ctx,
    *,
    primary_hit: bool = True,
    quality: int = 0,
) -> tuple[tuple[tuple[GroundEnemyInstance, int, bool], ...], int]:
    """Resolve an explosive impact around ``primary`` with friendly
    fire — the blast math + doc 53 tally/killer tracking live in
    :mod:`._ground_blast` (the architecture-ratchet split)."""
    return _ground_blast.explosive_blast(
        _state, weapon_id, primary, ctx, primary_hit=primary_hit,
        quality=quality,
    )

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

def weapon_name(weapon_id: str, ctx, quality: int = 0) -> str:
    from ..ground_equipment import display_name

    return display_name("weapon", weapon_id, quality)

def consume_shot(slot_idx: int, ctx) -> None:
    """Decrement one weapon instance's loaded ammo after an accepted
    shot and emit the firing report (doc 48 SETTLED 17/22) — every
    accepted shot is heard at the shooter's cell per the weapon's
    noise column, both sides symmetric."""
    _wid = "fists"  # implicit fists: infinite ammo, near-silent
    if slot_idx < len(ctx.equipped_ground_weapons):
        from ..ground_equipment import consume_weapon_round

        _wid = ctx.equipped_ground_weapons[slot_idx].weapon_id
        ctx.equipped_ground_weapons[slot_idx] = consume_weapon_round(
            ctx.equipped_ground_weapons[slot_idx],
        )
    if _state is not None:  # no live session = no map to hear the shot
        noise.emit(ctx, _state.game_map, ctx.player.pos, _wid, by_player=True)

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
        _reserve = reserve_ammo_count(ctx.bandolier, _spec.ammo_type)
        if _reserve > 0:
            candidates.append((_slot, _instance, _spec, _reserve))
    return tuple(candidates)

def _reload_slot(ctx, slot: int) -> bool:
    """Reload one validated slot transactionally and charge its AP cost."""
    from ..ground_equipment import apply_reload

    from ..ground_equipment import display_name
    from ..ground_reload_ui import _log_name_line

    _instance = ctx.equipped_ground_weapons[slot]
    _spec = _find_gw(_instance.weapon_id)
    _wname = display_name("weapon", _instance.weapon_id, _instance.quality)
    if _state.player_ap < _spec.reload_ap_cost:
        ctx.log.add(
            f"Need {_spec.reload_ap_cost} AP to reload "
            f"(have {_state.player_ap}).",
        )
        return False
    try:
        _new = apply_reload(
            ctx.equipped_ground_weapons, slot, ctx.bandolier,
        )
    except (IndexError, KeyError, ValueError) as exc:
        _log_name_line(ctx, "", _wname, _instance.quality, f": {exc}")
        return False
    _state.player_ap -= _spec.reload_ap_cost
    _log_name_line(
        ctx, "Reloaded ", _wname, _instance.quality,
        f" ({_new.loaded_ammo}/{_spec.ammo_capacity}).",
    )
    return True

async def reload_weapon(ctx) -> bool:
    """Reload the first dry active slot with reserve (doc 50 SETTLED 5).

    Deterministic — no chooser: the multi-slot chooser shipped dead (the
    dispatch called this coroutine without await, so the live R key
    never ran), and a tutorial-honest reload is one keypress anyway.
    """
    _candidates = _reloadable_slots(ctx)
    if not _candidates:
        ctx.log.add("No active weapon can be reloaded.")
        return False
    return _reload_slot(ctx, _candidates[0][0])


async def swap_weapon_sets(ctx) -> bool:
    """Swap the whole active set for the holstered set (doc 51 phase 2).

    One mid-turn action: 1 AP, never turn-ending. Magazines and quality
    ride the instances; the fresh set arrives all-armed (combat-start
    flags over the fists-fallback weapon list — an empty active set
    swaps to fists, the SETTLED 1 floor). Out of 1 AP: refuse, no
    mutation.
    """
    if _state.player_ap < 1:
        ctx.log.add("Not enough AP to swap weapon sets.")
        return False
    swap_sets_logged(
        ctx.equipped_ground_weapons, ctx.holstered_ground_weapons, ctx.log,
    )
    _state.active_weapon_list = [True] * len(player_weapons(ctx))
    _state.player_ap -= 1
    return True

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

async def animate_fire(
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
        await _animate_ground_shot(
            console, ctx, game_map,
            from_pos, to_pos,
            _wid, is_hit=is_hit,
            damage=damage,
            render_callback=render_frame,
        )

# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

async def on_kill(game_map: world.GameMap, enemy: GroundEnemyInstance, ctx) -> None:
    _ent = enemy.entity
    if _ent is not None and _ent in game_map.entities:
        game_map.entities.remove(_ent)

    if _ent is not None and enemy.spec:
        from ._actions import spawn_kill_drops
        spawn_kill_drops(
            game_map, _ent.pos, enemy.spec, ctx, enemy.weapon_id,
            enemy.weapon_quality, band=enemy.band,
            carried=getattr(_ent, "carried_items", None),
        )

    if enemy.spec:
        from ..xp import add_xp as _add_xp
        await _add_xp(ctx, enemy.spec.xp_reward)
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
    from ._ground_effects import apply_player_effect

    return apply_player_effect(_state, ctx, spec)

# ---------------------------------------------------------------------------
# Enemy turns
# ---------------------------------------------------------------------------

async def run_enemy_turns(ctx, game_map: world.GameMap) -> int:
    from ._ai_ground import run_ground_enemy_turn as _enemy_ai

    # The enemy turn is not the player's aiming phase: hide the range
    # line for every movement step and attack animation in it, then
    # restore it for the player's next interactive frame.
    with _range_line_hidden():
        return await _run_enemy_turns_impl(ctx, game_map, _enemy_ai)

def _player_ground_dodge(ctx) -> int:
    """Return current ground dodge including the Evasive trait."""
    return _calc_ground_move_dodge(_state.cells_moved_this_turn) + _ground_evade_bonus(ctx)


async def _run_enemy_turns_impl(ctx, game_map: world.GameMap, _enemy_ai) -> int:
    _player_dodge = _player_ground_dodge(ctx)
    _total_dmg = 0
    for _gei in _state.enemies:
        if not _gei.alive or _gei.ap <= 0 or not _gei.weapon_id:
            continue
        _dmg = await _spend_one_enemy_turn(
            ctx, game_map, _enemy_ai, _gei, _player_dodge,
        )
        if _dmg >= 999:
            return 999
        _total_dmg += _dmg
    return _total_dmg


def _spent_as_movement(_gei, _fired: bool, _ap_spent: int) -> int:
    """AP spent this turn that reads as movement (the dodge ledger):
    everything except the fired shot's weapon cost (1 on a miss)."""
    if not _fired:
        return _ap_spent
    try:
        _weapon_ap = _find_gw(_gei.weapon_id).ap_cost
    except KeyError:
        _weapon_ap = 1
    return max(0, _ap_spent - _weapon_ap)


def _killer_label(_gei: GroundEnemyInstance) -> str:
    """The tombstone's attacker label: enemy + wielded variant, built
    the same way the enemy-shot log line builds it (quality included)."""
    from ..ground_equipment import display_name

    return (
        f"{_gei.name}'s "
        f"{display_name('weapon', _gei.weapon_id, _gei.weapon_quality)}"
    )


def _apply_enemy_hit(ctx, _gei: GroundEnemyInstance, _dmg: int) -> int:
    """The enemy-damage tail every attack path shares (doc 54 phase 2
    extraction): trait reduction, the doc-53 damage counter, HP, the
    killer label. Returns the reduced damage."""
    _dmg = ground_damage_taken(ctx, _dmg)
    if hasattr(ctx, "player_counters"):
        ctx.player_counters.ground_damage_taken += _dmg
    _state.player_hp -= _dmg
    _state.last_attacker = _killer_label(_gei)
    return _dmg


async def _spend_one_enemy_turn(
    ctx, game_map: world.GameMap, _enemy_ai, _gei, _player_dodge: int,
) -> int:
    """Run one enemy's turn; returns player damage taken (999 = player down).

    Fights at the equip-time rolled quality (doc 47.2 SETTLED 13); may
    first spend AP on a carried consumable (doc 48 SETTLED 36) — booked
    apart so a use never inflates the movement-dodge ledger.
    """
    from ._ground_effects import use_carried_consumable

    _gei.ap -= use_carried_consumable(ctx, _gei, game_map, ctx.player.pos)
    _ap_before = _gei.ap
    _new_ap, _dmg, _fired = await _enemy_ai(
        ctx,
        enemy_weapon_id=_gei.weapon_id,
        enemy_weapon_quality=_gei.weapon_quality,
        enemy_spec=_gei.spec, enemy_stats=_gei.stats, enemy_ap=_gei.ap,
        player_pos=ctx.player.pos, enemy_entity=_gei.entity,
        game_map=game_map, armor_defense=_state.armor_defense,
        console=_state.console, render_callback=render_frame,
        player_dodge=_player_dodge,
    )
    _gei.cells_moved_this_turn += _spent_as_movement(_gei, _fired,
                                                     _ap_before - _new_ap)
    _gei.ap = _new_ap

    if _dmg > 0:
        _dmg = _apply_enemy_hit(ctx, _gei, _dmg)
        if _state.player_hp <= 0:
            return 999
    return _dmg

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
        _inst = _build_enemy_instance(_ent, game_map)
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
    _remember_last_seen(
        _survivors, ctx.player.pos, include_stationary=True,
    )

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
    # Consumable AP bonuses (stim effects) add to this round's gain
    # before the fractional roll, so a temporary +1 is a full extra AP;
    # enemy instances tick their own effects (regen heals, stim APs).
    from ._ground_effects import advance_enemy_effects, advance_player_effects

    _gain = (
        _state.player_ap_gain_twentieths
        + 20 * advance_player_effects(_state)
    )
    _avail, _carry = _roll_ap(_state.player_ap_carry_twentieths, _gain)
    _state.player_ap_carry_twentieths = _carry
    _state.player_ap_total = _avail
    _state.player_ap = _avail
    _state.cells_moved_this_turn = 0
    for _gei in _state.enemies:
        _gei.ap = _gei.ap_total + advance_enemy_effects(_gei)
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
    _cr.flee_exit = _state.flee_exit
    return _cr


# ---------------------------------------------------------------------------
# Flee (doc 54 phase 2) — one-line hooks over the _ground_flee sibling
# ---------------------------------------------------------------------------

async def reaction_volley(ctx, game_map: world.GameMap) -> bool:
    """The flee reaction volley (doc 54) — every enemy in band + LOS
    attacks once. The implementation lives in :mod:`._ground_flee`
    (the size-ratchet sibling; the space hook's mirror, same name)."""
    from . import _ground_flee
    return await _ground_flee.reaction_volley(_state, ctx, game_map)


async def attempt_exit(ctx, game_map: world.GameMap, dx: int, dy: int) -> str | None:
    """The in-combat stair-step exit (doc 54 phase 2), ground's hook —
    called by the loop right after a successful MOVE. The
    implementation lives in :mod:`._ground_flee`. (Named apart from
    space's ``attempt_flee`` deliberately: that hook takes the action
    string at the meta seam; this one takes the step delta it may
    have to refund.)"""
    from . import _ground_flee
    return await _ground_flee.attempt_exit(_state, ctx, game_map, dx, dy)
