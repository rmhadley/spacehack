"""Ground enemy-instance construction (doc 48 SETTLED 35/36/37/51).

The init-support seam split out of :mod:`_rules_ground` (the doc 103
Build A ratchet split, the ``navigation_render``/``_space_kills``
pattern): building one :class:`GroundEnemyInstance` from a map entity
— spec resolution, band stats, loadout stamping, the worn fold — is
one cohesive responsibility with one caller shape (init's full build
and ``refresh_engaged``'s mid-fight joins). ``_rules_ground``
re-exports both public names; tests and the join scan import them
there.
"""

from __future__ import annotations

from .. import world
from .. import ground_loadout
from .. import ground_scale
from ..data.npc_chars import find_npc_char as _find_nc
from ..ground_equipment import (
    sum_armor_defense as _sum_armor_defense,
)
from ._ground_types import GroundEnemyInstance


def _stamp_enemy_loadout(_ent: world.Entity, _spec, _worn=()) -> int:
    """First-resolution stamps at combat entry (doc 48 SETTLED 36/37):
    the pre-rolled carried consumables land once (what they drop is
    what they carry); returns the spec-derived AP total (the worn
    bonus fold retired with the placeholder fields, doc 102.4.2 —
    the enemy chrome seam returns with the container)."""
    from ._actions import roll_carried_consumables
    from ._ground_effects import enemy_ap_total

    if getattr(_ent, "carried_items", None) is None:
        _ent.carried_items = roll_carried_consumables(_spec)
    return enemy_ap_total(_spec, armor_entries=_worn)


def _worn_fold(spec, stats, worn) -> tuple[int, int]:
    """The worn pieces' instance-build fold (doc 48 SETTLED 51/27):
    each piece's defense into the armor read — one pass over the
    stamped pieces. What they wear is what they are, on the card and
    in every soak. (The hp_bonus term retired with the placeholder
    fields, doc 102.4.2.)"""
    return (
        spec.hp + stats.stamina // 3,
        spec.armor + _sum_armor_defense(worn),
    )


def _build_enemy_instance(
    _ent: world.Entity, game_map=None,
) -> GroundEnemyInstance | None:
    """Build one enemy instance from a map entity (init + mid-fight joins).

    Reads/stamps ``entity.hp`` so wounds persist across combat sessions
    (LOS-aggro survivors keep wounds; never a heal-on-retrigger); guards
    get their ``guard_post`` stamped here (SETTLED 37). Stats resolve
    through the band resolver (SETTLED 35); the weapon resolves ONCE and
    persists on the entity (SETTLED 37). The WORN cyber pieces fold
    here (doc 48 SETTLED 51/27) through the player's own modifier math.
    """
    try:
        _spec = _find_nc(_ent.npc_char_id)
    except KeyError:
        return None
    _band = ground_scale.entity_band(_ent, game_map, spec=_spec)
    _stats = ground_scale.derive_stats(_spec, _band)
    _stamp = ground_loadout.ensure_loadout(_ent, game_map, _spec)
    _pair = ground_loadout.active_pair(_stamp) if _stamp else None
    _worn = ground_loadout.worn_entries(_stamp)
    _ap_total = _stamp_enemy_loadout(_ent, _spec, _worn)
    from . import _ancients

    _ancients.stamp_entry_field(_ent, game_map, _spec)
    _max_hp, _armor = _worn_fold(_spec, _stats, _worn)
    if _spec.behavior == "guard" and getattr(_ent, "guard_post", None) is None:
        _ent.guard_post = world.Position(_ent.pos.x, _ent.pos.y)
    _cur_hp = min(getattr(_ent, "hp", 0) or _max_hp, _max_hp)
    _ent.hp = _cur_hp
    return GroundEnemyInstance(
        entity=_ent, spec=_spec,
        weapon_id=_pair[0] if _pair else "",
        weapon_quality=_pair[1] if _pair else 0,
        band=_band, stats=_stats,
        hp=_cur_hp, max_hp=_max_hp, ap=_ap_total, ap_total=_ap_total,
        armor=_armor,
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
