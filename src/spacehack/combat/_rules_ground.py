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
from .. import ui
from .. import message_log as _ml
from ..engine import RNG, SCREEN_WIDTH, SCREEN_HEIGHT, HUD_WIDTH
from ..game_context import GameContext
from ..data.ground_weapons import find_ground_weapon as _find_gw
from ..data.npc_chars import find_npc_char as _find_nc
from ..data.ground_armor import find_ground_armor as _find_ga
from ..ground_equipment import (
    sum_armor_bonus as _sum_armor_bonus,
    tier_filtered_equipment as _tier_loot,
)
from ..hud import _bar_str
from ..xp import (
    sharpshooter_hit_bonus as _sharpshooter_bonus,
    ace_pilot_ap_bonus as _ace_pilot_bonus,
)

from ._types import CombatResult
from ._stats import _distance
from ._actions import (
    move_entity,
    _spawn_loot_at_position as _shared_loot,
    _spawn_equipment_loot_at_position as _shared_equipment_loot,
    set_combat_locks,
)
from ._animations import (
    _has_los,
    _paint_target_highlight,
    _draw_range_colored_line,
    DamagePopup,
)
from ._shot_animations import _animate_ground_shot


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
    # Presentation-only: while True, ``render_frame`` skips the player's
    # range/accuracy line. Set during shot animations and the whole enemy
    # turn so the line never clutters frames the player isn't acting on.
    range_line_hidden: bool = False


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
    max_hp = 20 + ctx.ground_stats.stamina // 3 + _sum_armor_bonus(armor_ids, "hp_bonus")
    delta = max_hp - ctx.ground_max_hp
    if delta > 0:
        ctx.ground_hp += delta
    return min(ctx.ground_hp, max_hp), max_hp


def _armor_defense_total(ctx) -> int:
    """Sum flat defense across equipped armor pieces."""
    total = 0
    for armor_id in ctx.equipped_ground_armor.values():
        if armor_id:
            try:
                total += _find_ga(armor_id).defense
            except KeyError:
                pass
    return total


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
    _w = list(ctx.equipped_ground_weapons)
    return _w if _w else ["fists"]


def active_weapons(ctx) -> list[bool]:
    return list(_state.active_weapon_list)


def set_active_weapons(ctx, active: list[bool]) -> None:
    _state.active_weapon_list = list(active)


def refresh_equipment_state(ctx) -> None:
    """Refresh cached ground-combat equipment after a character-screen swap."""
    _weapons = list(ctx.equipped_ground_weapons) or ["fists"]
    _state.active_weapon_list = [
        _state.active_weapon_list[index]
        if index < len(_state.active_weapon_list) else True
        for index in range(len(_weapons))
    ]
    _armor_defense = 0
    for armor_id in ctx.equipped_ground_armor.values():
        if not armor_id:
            continue
        try:
            _armor_defense += _find_ga(armor_id).defense
        except KeyError:
            continue
    _state.armor_defense = _armor_defense


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


def _ground_damage_raw(
    weapon_id: str, strength: int, armor_defense: int, melee_bonus: int = 0,
) -> int:
    """Raw hit damage: base + melee bonuses - armor, minimum 1.

    ``armor_bypass`` weapons ignore armor entirely; plasma halves
    ``armor_defense``; ``melee_bonus`` (cybernetic arms) applies only
    to melee weapons.
    """
    _ws = _find_gw(weapon_id)
    _str_bonus = strength // 10 if _ws.damage_type == 'melee' else 0
    _melee = melee_bonus if _ws.damage_type == 'melee' else 0
    if _ws.armor_bypass:
        armor_defense = 0
    elif _ws.damage_type == 'plasma':
        armor_defense = armor_defense // 2
    return max(1, _ws.damage + _str_bonus + _melee - armor_defense)


def _ground_point_blank_penalty(weapon_id: str, distance: int) -> int:
    """Return the emergency accuracy penalty for firing inside minimum range.

    Minimum range remains meaningful during normal play, but a pinned player
    must retain an actionable response. Each cell inside the minimum range
    costs 35 accuracy points; ordinary in-range and melee shots have no
    penalty.
    """
    _ws = _find_gw(weapon_id)
    return max(0, _ws.min_range - distance) * 35


def _calc_ground_move_dodge(cells_moved: int) -> int:
    """Movement evade: +5% per cell moved, capped at 30.

    Reflexes are already handled by the ``target_reflexes // 2`` term
    in :func:`_ground_hit_chance_raw` — this helper is movement-only."""
    return min(cells_moved * 5, 30)


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
    _dmg = _ground_damage_raw(
        weapon_id, ctx.ground_stats.strength, _armor, _melee_bonus,
    )
    enemy.hp -= _dmg
    # Wound persistence: sync to the map entity so a fight that ends
    # with survivors (LOS aggro) keeps their wounds on re-engagement.
    if enemy.entity is not None:
        enemy.entity.hp = max(0, enemy.hp)
    return _dmg, False


# ---------------------------------------------------------------------------
# Weapon actions
# ---------------------------------------------------------------------------

def can_fire(slot_idx: int, ctx) -> tuple[bool, str]:
    _weapons = player_weapons(ctx)
    if not (0 <= slot_idx < len(_weapons)):
        return False, "Unknown weapon"
    _ws = _find_gw(_weapons[slot_idx])
    _alive = get_enemies(ctx)
    if _state.target_idx >= len(_alive):
        return False, "No valid target"
    _target = _alive[_state.target_idx]
    _dist = int(_distance(ctx.player.pos, _target.pos))
    if _dist > _ws.max_range:
        return False, f"Out of range ({_dist}u, need {_ws.min_range}-{_ws.max_range})"
    _reason = ""
    if _dist < _ws.min_range:
        _penalty = _ground_point_blank_penalty(_weapons[slot_idx], _dist)
        _reason = f"Emergency point-blank shot: {_penalty}% accuracy penalty."
    if _state.player_ap < _ws.ap_cost:
        return False, f"Need {_ws.ap_cost} AP (have {_state.player_ap})"
    if not _has_los(
        _state.game_map,
        ctx.player.pos.x, ctx.player.pos.y,
        _target.pos.x, _target.pos.y,
    ):
        return False, "Blocked by wall"
    return True, _reason


def weapon_ap_cost(weapon_id: str, ctx) -> int:
    return _find_gw(weapon_id).ap_cost


def weapon_name(weapon_id: str, ctx) -> str:
    return _find_gw(weapon_id).name


def consume_shot(slot_idx: int, ctx) -> None:
    pass


# ---------------------------------------------------------------------------
# Player movement
# ---------------------------------------------------------------------------

def try_move(ctx, game_map: world.GameMap, dx: int, dy: int) -> bool:
    # Solid collision via the shared primitive: enemies and furniture
    # block, while loot is a walkable floor object.
    # combatant (melee attacks fire at range 1, there is no bump-attack).
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
# Rendering
# ---------------------------------------------------------------------------

_COLOR_GROUND_TITLE: tuple[int, int, int] = (255, 200, 100)
_COLOR_GROUND_PLAYER: tuple[int, int, int] = (100, 220, 255)
_COLOR_GROUND_ENEMY: tuple[int, int, int] = (255, 100, 100)
_COLOR_GROUND_ENEMY_TARGET: tuple[int, int, int] = (255, 220, 100)
_COLOR_GROUND_WEAPON: tuple[int, int, int] = (255, 200, 100)
_COLOR_GROUND_WEAPON_DIM: tuple[int, int, int] = (120, 100, 60)
_COLOR_GROUND_ACTION: tuple[int, int, int] = (180, 220, 255)
# Distance-readout threat colors, mirroring the space HUD's range tints.
_COLOR_DIST_SAFE: tuple[int, int, int] = (100, 235, 115)     # out of enemy range
_COLOR_DIST_DANGER: tuple[int, int, int] = (255, 80, 80)      # enemy can fire now
_COLOR_DIST_TOO_CLOSE: tuple[int, int, int] = (255, 160, 60)  # inside min range


def _ground_range_line(console, player_pos, target_pos, weapon_id, cam_x, cam_y, region_x, region_y, game_map, *, color_override=None):
    try:
        _ws = _find_gw(weapon_id)
    except KeyError:
        return
    _draw_range_colored_line(
        console, player_pos, target_pos,
        _ws.max_range, _ws.min_range,
        cam_x, cam_y, _RENDER_WIDTH, _RENDER_HEIGHT,
        region_x=region_x, region_y=region_y,
        color_override=color_override,
        game_map=game_map,
    )


def render_frame(console, ctx, game_map: world.GameMap) -> None:
    console.clear()
    cam = _render_ground_world(console, ctx, game_map)
    alive = get_enemies(ctx)
    weapons = player_weapons(ctx)
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
    cam_x, cam_y, rx, ry = world.camera_for_view(
        game_map, ctx.player.pos,
        region_w=_RENDER_WIDTH, region_h=_RENDER_HEIGHT,
    )
    world.render_world_view(
        console, game_map,
        region_x=rx, region_y=ry,
        region_w=_RENDER_WIDTH, region_h=_RENDER_HEIGHT,
        camera_x=cam_x, camera_y=cam_y,
    )
    alive = get_enemies(ctx)
    if _state.target_idx < len(alive):
        _paint_target_highlight(
            console, cam_x, cam_y, _RENDER_WIDTH, _RENDER_HEIGHT, rx, ry,
            alive[_state.target_idx].entity,
        )
    return cam_x, cam_y, rx, ry


def _active_weapon_ids(ctx, weapons: list[str]) -> list[str]:
    """Return equipped weapons still marked active in the combat state."""
    return [
        weapons[i] for i in range(len(weapons))
        if i < len(_state.active_weapon_list) and _state.active_weapon_list[i]
    ]


def _render_range_line(
    console, ctx, game_map, active_w: list[str], alive, cam,
) -> None:
    """Draw the player's range/accuracy line unless hidden mid-animation."""
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


def _render_player_panel(console, ctx) -> int:
    """Paint the player HP/AP/evasion block; return the next HUD row."""
    hud_x = SCREEN_WIDTH - HUD_WIDTH
    y = 0
    console.print(x=hud_x, y=y, string="> GROUND COMBAT <", fg=_COLOR_GROUND_TITLE)
    y += 2
    console.print(x=hud_x, y=y, string="PLAYER", fg=_COLOR_GROUND_PLAYER)
    y += 1
    hp_bar = _bar_str(_state.player_hp, _state.player_max_hp, width=8)
    hp_pct = _state.player_hp * 100 // max(_state.player_max_hp, 1)
    console.print(x=hud_x, y=y, string=f"HP  {hp_bar} {hp_pct}%", fg=_COLOR_GROUND_PLAYER)
    y += 1
    console.print(x=hud_x, y=y, string=f"AP: {_state.player_ap}/{_state.player_ap_total}", fg=_COLOR_GROUND_ACTION)
    y += 1
    eva = _calc_ground_move_dodge(_state.cells_moved_this_turn)
    console.print(x=hud_x, y=y, string=f"EVA: {eva}%", fg=_COLOR_GROUND_ACTION)
    return y + 2


def _render_weapons_panel(console, ctx, weapons, alive, y: int) -> int:
    """Paint the weapon list with hit/damage/range; return the next row."""
    hud_x = SCREEN_WIDTH - HUD_WIDTH
    console.print(x=hud_x, y=y, string="WEAPONS", fg=_COLOR_GROUND_TITLE)
    y += 1
    for i, wid in enumerate(weapons):
        try:
            ws = _find_gw(wid)
        except KeyError:
            continue
        is_active = _state.active_weapon_list[i] if i < len(_state.active_weapon_list) else True
        sel = "[x]" if is_active else "[ ]"
        name_fg = _COLOR_GROUND_WEAPON if is_active else _COLOR_GROUND_WEAPON_DIM
        console.print(x=hud_x, y=y, string=f"{sel}[{i+1}] {ws.name}"[:24], fg=name_fg)
        y += 1
        hc = hit_chance(wid, alive[_state.target_idx], ctx) if _state.target_idx < len(alive) else 0
        console.print(x=hud_x, y=y, string=f"     DMG {ws.damage} HIT {hc}%", fg=ui.COLOR_VALUE_DIM)
        y += 1
        rng = f"{ws.min_range}-{ws.max_range}" if ws.min_range > 0 else f"0-{ws.max_range}"
        console.print(x=hud_x, y=y, string=f"     RNG {rng} AP {ws.ap_cost}", fg=ui.COLOR_VALUE_DIM)
        y += 1
    return y + 1


def _enemy_weapon(enemy: GroundEnemyInstance):
    """Resolve an enemy's weapon spec, or None when unarmed/unknown."""
    if not enemy.weapon_id:
        return None
    try:
        return _find_gw(enemy.weapon_id)
    except KeyError:
        return None


def enemy_detail_lines(enemy: GroundEnemyInstance) -> tuple[str, str, str]:
    """Return the (armor, weapon, stats) HUD lines for one enemy.

    The armor line reports the enemy's flat DR (``ARM 0`` when
    unarmored) so the player can decide between raw damage and armor
    piercing. The weapon line names the weapon, and the stats line
    shows ``DMG``/``RNG`` so a heavy ranged threat is spotted before
    it fires (and melee is unmistakably ``RNG 1-1``).
    """
    armor = enemy.spec.armor if enemy.spec else 0
    weapon = _enemy_weapon(enemy)
    if weapon is None:
        return f"ARM {armor}", "Unarmed", ""
    return (
        f"ARM {armor}",
        weapon.name,
        f"DMG {weapon.damage}  RNG {weapon.min_range}-{weapon.max_range}",
    )


def enemy_threat_color(
    enemy: GroundEnemyInstance, dist: int,
) -> tuple[int, int, int]:
    """Return the color for the enemy's distance readout.

    Red when the enemy's weapon can fire at this distance, orange when
    the player is inside the enemy's minimum range (too close to fire),
    green when safely out of range.
    """
    weapon = _enemy_weapon(enemy)
    if weapon is None:
        return ui.COLOR_VALUE_DIM
    if dist < weapon.min_range:
        return _COLOR_DIST_TOO_CLOSE
    if dist <= weapon.max_range:
        return _COLOR_DIST_DANGER
    return _COLOR_DIST_SAFE


def _render_enemies_panel(console, ctx, alive, y: int) -> int:
    """Paint the alive-enemy list with HP bars; return the next row."""
    hud_x = SCREEN_WIDTH - HUD_WIDTH
    if alive:
        console.print(x=hud_x, y=y, string="ENEMIES", fg=_COLOR_GROUND_TITLE)
        y += 1
        for i, gei in enumerate(alive):
            is_target = i == _state.target_idx
            name_fg = _COLOR_GROUND_ENEMY_TARGET if is_target else _COLOR_GROUND_ENEMY
            marker = ">" if is_target else " "
            console.print(x=hud_x, y=y, string=f"{marker}{gei.name}"[:24], fg=name_fg)
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
                        x=hud_x, y=y, string=f"  {_line}"[:24],
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
        ("[Tab]", "Target"), ("[m]", "Move"), ("[f]", "Fire"), ("[w]", "Wait"),
    ]
    if len(weapons) > 1:
        actions.insert(3, (f"[1-{len(weapons)}]", "Toggle Wpn"))
    for key, desc in actions:
        console.print(x=hud_x, y=y, string=f"{key} {desc}", fg=_COLOR_GROUND_ACTION)
        y += 1


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


def _run_enemy_turns_impl(ctx, game_map: world.GameMap, _enemy_ai) -> int:
    _player_dodge = _calc_ground_move_dodge(_state.cells_moved_this_turn)

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
    _state.player_ap = _state.player_ap_total
    _state.cells_moved_this_turn = 0
    for _gei in _state.enemies:
        _gei.ap = _gei.ap_total
        _gei.cells_moved_this_turn = 0


def sync_state(ctx) -> None:
    # Release the engaged enemies: with the fight over they resume
    # patrol/wander behaviour on the next dungeon tick.
    _set_combat_locks(False)
    ctx.ground_hp = max(0, _state.player_hp)
    ctx.ground_max_hp = _state.player_max_hp


def get_combat_result() -> CombatResult:
    _cr = CombatResult()
    for _gei in _state.enemies:
        if not _gei.alive and _gei.spec:
            _cr.defeated_names.append(_gei.spec.name)
            _cr.defeated_spec_ids.append(_gei.spec.id)
    return _cr
