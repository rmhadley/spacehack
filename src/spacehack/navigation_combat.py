"""Combat encounter detection + NPC auto-comms warning.

Extracted from ``navigation.py`` to keep that module under the 1,000-line
architecture limit. Every function here stays under 40 lines.
"""

from __future__ import annotations

import math

from . import main_quest as main_quest_module
from . import ship as ship_module
from . import solar_system as solar_system_module
from . import world
from .data.npc_ships import find_npc_ship
from .faction import get_attitude as _get_attitude


# ---------------------------------------------------------------------------
# Encounter detection
# ---------------------------------------------------------------------------


def _charged_cell_aggro(ctx, system_id: str, faction: str) -> bool:
    """True when the charged-cell heat makes ``faction`` aggro from afar."""
    return (
        main_quest_module.charged_cell_in_sol(ctx, system_id)
        and faction == "militia"
    )


def _alive_entity_at(ctx, pos) -> bool:
    """True when a non-owned entity currently occupies ``pos``."""
    return any(
        _e for _e in ctx.game_map.entities
        if not getattr(_e, "owned", False)
        and _e.pos.x == pos.x and _e.pos.y == pos.y
    )


def _trigger_static_spawns(ctx, player_pos, system, alive_spawns):
    """Pass 1a: mark static system spawns within detect radius."""
    _triggered_squad_ids: set = set()
    _triggered_solo_positions: set = set()
    _system_id = getattr(system, "id", "")
    for _spawn in getattr(system, "enemies", ()) or ():
        try:
            _espec = find_npc_ship(_spawn.enemy_id)
        except KeyError:
            continue
        if not _alive_entity_at(ctx, _spawn.pos):
            continue
        alive_spawns.append((_spawn, _espec))
        _dist = math.hypot(
            player_pos.x - _spawn.pos.x, player_pos.y - _spawn.pos.y,
        )
        _radius = _espec.detect_radius
        if _charged_cell_aggro(ctx, _system_id, getattr(_espec, "faction", "")):
            _radius = max(_radius, 30)
        if _dist > 0 and _dist <= _radius:
            # Static system enemies always engage (territorial).
            if _spawn.squad_id is not None:
                _triggered_squad_ids.add(_spawn.squad_id)
            else:
                _triggered_solo_positions.add((_spawn.pos.x, _spawn.pos.y))
    return _triggered_squad_ids, _triggered_solo_positions


def _trigger_bounty_spawns(ctx, player_pos, system_id, alive_spawns):
    """Pass 1b: mark dynamic bounty spawns within detect radius."""
    _triggered_solo_positions: set = set()
    _bounty_spawns = ctx.bounty_spawns.get(system_id, [])
    for _bs in _bounty_spawns:
        try:
            _espec = find_npc_ship(_bs.enemy_id)
        except KeyError:
            continue
        if not _alive_entity_at(ctx, _bs.pos):
            continue
        alive_spawns.append((_bs, _espec))
        _dist = math.hypot(player_pos.x - _bs.pos.x, player_pos.y - _bs.pos.y)
        _radius = _espec.detect_radius
        _aggro = _charged_cell_aggro(ctx, system_id, getattr(_espec, "faction", ""))
        if _aggro:
            _radius = max(_radius, 30)
        if _dist > 0 and _dist <= _radius:
            # Reputation gate: only hostile factions trigger combat
            # (militia aggro bypasses rep — they attack on sight).
            if not _aggro and _get_attitude(
                ctx.faction_reputation.get(_espec.faction, 0),
            ) not in ("enemy", "disliked"):
                continue
            _triggered_solo_positions.add((_bs.pos.x, _bs.pos.y))
            # Squad grouping: if ANY squad member triggers, add ALL
            # squad members so the entire squad joins combat together.
            _squad_ref = _bs.spawn_id if _bs.squad_group_id is None else _bs.squad_group_id
            if _bs.squad_size > 1 or _bs.squad_group_id is not None:
                for _other in _bounty_spawns:
                    if _other.spawn_id == _squad_ref or _other.squad_group_id == _squad_ref:
                        _triggered_solo_positions.add((_other.pos.x, _other.pos.y))
    return _triggered_solo_positions


def _trigger_procedural_spawns(ctx, player_pos, system_id, alive_spawns):
    """Pass 1c: mark procedural NPC squads within detect radius."""
    _triggered_squad_ids: set = set()
    _procedural_entities = [
        _e for _e in ctx.game_map.entities
        if not getattr(_e, "owned", False)
        and getattr(_e, "procedural_squad_id", "") != ""
    ]
    for _pe in _procedural_entities:
        _pid = getattr(_pe, "npc_ship_id", "") or "pirate_scout"
        try:
            _espec = find_npc_ship(_pid)
        except (KeyError, ImportError):
            continue
        alive_spawns.append((_pe, _espec))
        _dist = math.hypot(player_pos.x - _pe.pos.x, player_pos.y - _pe.pos.y)
        _radius = _espec.detect_radius
        _aggro = _charged_cell_aggro(ctx, system_id, getattr(_espec, "faction", ""))
        if _aggro:
            _radius = max(_radius, 30)
        if _dist > 0 and _dist <= _radius:
            # Reputation gate: only hostile factions trigger combat.
            if not _aggro and _get_attitude(
                ctx.faction_reputation.get(_espec.faction, 0),
            ) not in ("enemy", "disliked"):
                continue
            _triggered_squad_ids.add(_pe.procedural_squad_id)
    return _triggered_squad_ids


def _build_encounter_payload(alive_spawns, triggered_squad_ids, triggered_solo_positions):
    """Pass 2: collect specs/positions for every triggered spawn."""
    _nearby_specs: list = []
    _nearby_positions: list = []
    for _spawn, _espec in alive_spawns:
        _sq = getattr(_spawn, "squad_id", None) or getattr(_spawn, "procedural_squad_id", None)
        if _sq is not None:
            if _sq in triggered_squad_ids:
                _nearby_specs.append(_espec)
                _nearby_positions.append(_spawn.pos)
        elif (_spawn.pos.x, _spawn.pos.y) in triggered_solo_positions:
            _nearby_specs.append(_espec)
            _nearby_positions.append(_spawn.pos)
    if _nearby_specs:
        return (_nearby_specs, _nearby_positions)
    return None


def _detect_combat_encounter(
    ctx, player_pos: world.Position, system: object,
) -> tuple[list, list[world.Position]] | None:
    """Run the squad-aware enemy scan and return combat payload, or ``None``.

    Two-pass design: pass 1 marks alive enemy spawns within
    ``detect_radius`` as triggered (squad or solo), pass 2 builds
    the encounter payload for any spawn whose squad was triggered
    OR whose own position was triggered as a solo. Returns
    ``(specs, positions)`` if any spawn was triggered, else ``None``.
    """
    _system_id = getattr(system, "id", "")
    _alive_spawns: list = []
    _triggered_squad_ids, _triggered_solo = _trigger_static_spawns(
        ctx, player_pos, system, _alive_spawns,
    )
    _triggered_solo.update(_trigger_bounty_spawns(
        ctx, player_pos, _system_id, _alive_spawns,
    ))
    _triggered_squad_ids.update(_trigger_procedural_spawns(
        ctx, player_pos, _system_id, _alive_spawns,
    ))
    return _build_encounter_payload(
        _alive_spawns, _triggered_squad_ids, _triggered_solo,
    )


# ---------------------------------------------------------------------------
# NPC auto-comms warning (before combat triggers)
# ---------------------------------------------------------------------------


def _militia_scan_chance(ctx) -> float:
    """Chance [0.0, 1.0] a militia patrol initiates a cargo scan.

    Allied = wave through, Liked = 20%, Neutral = 40%,
    Disliked/Enemy = 80%. Bar-chain militia heat (Act 0) applies a
    +30% floor (min 60%, capped 80%) while hot quest cargo is held.
    """
    _rep = ctx.faction_reputation.get("militia", 0)
    _att = _get_attitude(_rep)
    _table = {
        "allied": 0.0,
        "liked": 0.20,
        "neutral": 0.40,
        "disliked": 0.80,
        "enemy": 0.80,
    }
    _chance = _table.get(_att, 0.40)
    if main_quest_module.bar_heat_active(ctx):
        _chance = max(0.60, min(0.80, _chance + 0.30))
    return _chance


def _calc_flee_chance(ctx) -> float:
    """Player's chance [0.0, 1.0] to flee a militia scan.

    Scales with ship effective speed (+2% per point above 10) and
    piloting skill (+0.5% per point above 30). Clamped to [0.15, 0.90].
    """
    _chance = 0.40
    if ctx.player_owned_ship is not None:
        _ship_cat = ship_module.find_ship(ctx.player_owned_ship.ship_id)
        _speed = ship_module.effective_speed(_ship_cat, ctx.player_owned_ship)
        _chance += (_speed - 10) * 0.02
    _chance += (ctx.stats.piloting - 30) * 0.005
    return max(0.15, min(0.90, _chance))


def _entity_hail_key(_e) -> str:
    """Return a stable key for per-entity hail tracking.

    Uses ``procedural_squad_id`` when available (moving entities like
    militia patrols and pirates), falling back to a position-based key
    for static entities (blockade, derelicts). The position-based
    fallback is safe because static entities never move.
    """
    _sq = getattr(_e, "procedural_squad_id", "")
    if _sq:
        return _sq
    _pid = getattr(_e, "npc_ship_id", "")
    return f"{_pid}:{_e.pos.x}:{_e.pos.y}"


def _fire_warning(ctx, _sys_id: str, _e) -> tuple[bool, object] | None:
    """Mark entity scanned and open comms with the entity."""
    ctx.militia_scanned.add(_entity_hail_key(_e))
    from .comms import open_comms_direct as _ocd
    _attack_data = _ocd(ctx, _e)
    return (True, _attack_data)


def _check_spec_distance(e, player_pos, max_dist) -> bool:
    """Pure: True when player is within ``max_dist`` of entity ``e``."""
    _dist = math.hypot(player_pos.x - e.pos.x, player_pos.y - e.pos.y)
    return 0 < _dist <= max_dist


def _check_viewport_visible(e, player_pos, system) -> bool:
    """Pure: True when entity ``e`` is within the player's viewport."""
    _view_w = solar_system_module.SOL_VIEW_W
    _view_h = solar_system_module.SOL_VIEW_H
    _cam_x = max(0, min(player_pos.x - _view_w // 2, system.width - _view_w))
    _cam_y = max(0, min(player_pos.y - _view_h // 2, system.height - _view_h))
    return (_cam_x <= e.pos.x < _cam_x + _view_w
            and _cam_y <= e.pos.y < _cam_y + _view_h)


def _spec_distance_hail(ctx, sys_id: str, e, spec, player_pos):
    """Spec-distance auto-hail branch (blockade + militia patrols + others)."""
    _pid = getattr(e, "npc_ship_id", "")
    _faction = getattr(spec, "faction", "")
    if _pid == "militia_blockade":
        if _entity_hail_key(e) in ctx.militia_scanned:
            return None
        return _fire_warning(ctx, sys_id, e)
    if _faction == "militia":
        _key = _entity_hail_key(e)
        if _key in ctx.militia_scanned:
            return None  # already checked this patrol
        ctx.militia_scanned.add(_key)
        from . import engine as _engine
        _chance = _militia_scan_chance(ctx)
        if _chance <= 0.0 or _engine.RNG.random() >= _chance:
            return None  # no scan — wave through
        return _fire_warning(ctx, sys_id, e)
    if _entity_hail_key(e) in ctx.militia_scanned:
        return None
    return _fire_warning(ctx, sys_id, e)


def _auto_hail_entity(ctx, sys_id: str, e, player_pos, system):
    """Check one entity's auto-hail triggers; return ``(True, data)`` or ``None``."""
    _pid = getattr(e, "npc_ship_id", "")
    if not _pid:
        return None
    try:
        _spec = find_npc_ship(_pid)
    except (KeyError, ImportError):
        return None
    _spec_distance = _spec.comms_warning_range
    _spec_viewport = getattr(_spec, "comms_trigger_viewport", False)
    _entity_bounty_range = getattr(e, "bounty_comms_range", 0)
    if _spec_distance <= 0 and not _spec_viewport and _entity_bounty_range <= 0:
        return None
    if _spec_distance > 0 and _check_spec_distance(e, player_pos, _spec_distance):
        return _spec_distance_hail(ctx, sys_id, e, _spec, player_pos)
    if _entity_bounty_range > 0 and _check_spec_distance(e, player_pos, _entity_bounty_range):
        if _entity_hail_key(e) in ctx.militia_scanned:
            return None
        return _fire_warning(ctx, sys_id, e)
    if _spec_viewport and _check_viewport_visible(e, player_pos, system):
        if _entity_hail_key(e) in ctx.militia_scanned:
            return None
        return _fire_warning(ctx, sys_id, e)
    return None


def _check_auto_comms_warning(
    ctx, player_pos, system,
) -> tuple[bool, object] | None:
    """Check if any entity with auto-hail behaviour is within range.

    Three independent trigger sources, checked per entity:
      1. **Spec distance** — ``comms_warning_range > 0`` (blockade).
      2. **Bounty entity distance** — ``bounty_comms_range`` set at
         spawn time from ``BountySpawn.comms_warning_range``.
      3. **Spec viewport** — ``comms_trigger_viewport`` (derelicts).

    Returns ``(True, attack_data_or_None)`` when a warning was issued,
    else ``None`` (no qualifying entity, or already warned).
    """
    _sys_id = getattr(system, "id", "")
    if not _sys_id:
        return None
    for _e in ctx.game_map.entities:
        if getattr(_e, "owned", False):
            continue
        _result = _auto_hail_entity(ctx, _sys_id, _e, player_pos, system)
        if _result is not None:
            return _result
    return None
