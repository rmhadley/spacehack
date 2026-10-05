"""Enemy loadout stamps — the two-set weapon model, entity-side.

Doc 48 SETTLED 43 (the player's doc-51 set model mirrored enemy-side):
every humanoid carries a RANGED set and a MELEE set, a per-weapon
magazine, and a pre-rolled carried ammo pool — all in ONE stamp on the
world entity (``rolled_loadout``), serialized and mutated in place so a
mid-fight save captures the exact state. First resolution is idempotent
(what fired at you is what drops, on every later fight); the roll lives
in :func:`ground_scale.roll_loadout` (pure), this module owns the stamp:
ensure/migrate, accessors, and the combat mutations (swap, drain,
reload) the volley loop drives.

Set names are positional vocabulary: the legacy single-roll slot is
"ranged" even when a family row rolls a melee-class weapon into it
(pirate raiders author the melee family on the ranged side) — slot 0
and slot 1, nothing more. ``guard_leash`` keys the RANGED slot's
weapon, always (SETTLED 43's dry-guard corner: a swapped-to-melee
guard keeps its authored kingdom).
"""

from __future__ import annotations

from . import world
from . import ground_scale

SET_RANGED = "ranged"
SET_MELEE = "melee"


def ensure_loadout(
    entity: world.Entity, game_map=None, spec=None,
) -> dict | None:
    """The entity's persisted two-set stamp (idempotent).

    First resolution rolls the full loadout through the band resolver
    and stamps it on the entity. A stamp whose ``melee`` key is absent
    is a migrated pre-43 save: the ENTIRE remainder — melee set, the
    ranged slot's magazine, and any missing pool entries — resolves
    NOW, at first engagement (a migrated gunner must not load
    permanently dry). The spec's WORN cyber pieces resolve through the
    same idempotent law (doc 48 SETTLED 51). The spec is derived from
    ``npc_char_id`` when not passed; a weaponless row (both slots
    ``None``) still stamps — drops read the emptiness.
    """
    _spec = _band = None  # resolved on the fresh path, reused for worn
    _stamp = getattr(entity, "rolled_loadout", None)
    if _stamp is None:
        from .data.npc_chars import find_npc_char

        _spec = spec or find_npc_char(entity.npc_char_id)
        _band = ground_scale.entity_band(entity, game_map, spec=_spec)
        from .engine import RNG  # the LIVE binding (seed_rng rebinds)

        entity.rolled_loadout = ground_scale.roll_loadout(
            _spec, _band, RNG,
        )
        _stamp = entity.rolled_loadout
    if SET_MELEE not in _stamp:
        _complete_migrated_stamp(_stamp, entity, game_map, spec)
    ensure_worn(_stamp, entity, game_map, _spec, _band)
    return _stamp


def ensure_worn(
    stamp: dict, entity, game_map=None, spec=None, band=None,
) -> list:
    """Resolve the spec's worn cyber pieces ONCE into the stamp's
    ``worn`` key (doc 48 SETTLED 51 — the idempotent first-resolution
    law): quality-stamped beside the loadout, so what they wear is
    what they are (every fold reads the stamp) and what drops (the
    kit path, at stamped qualities). Key-absent = unresolved (a
    pre-phase-11 save fills at first engagement, the melee-set
    precedent). ``spec``/``band`` may arrive pre-resolved from the
    caller's own fresh roll — one derivation per resolution."""
    if "worn" in stamp:
        return stamp["worn"]
    from .data.npc_chars import find_npc_char

    _spec = spec or find_npc_char(entity.npc_char_id)
    _band = band if band is not None else ground_scale.entity_band(
        entity, game_map, spec=_spec,
    )
    stamp["worn"] = _roll_worn(_spec, _band)
    return stamp["worn"]


def _roll_worn(spec, band: int) -> list:
    """The worn set's first resolution (doc 48 SETTLED 55): a FIXED
    ``worn_armor`` set wins outright (the rungs' cybernetics); else
    each eligible slot resolves through :func:`ground_scale.
    roll_worn_slot` (fill chance x the row's mod, then the tier
    window on the catalog ladder) with the quality drawn INLINE per
    piece at the band's ladder, clamped to the spec's floor (SETTLED
    51 — worn gear never reads base on a rung). RNG order pinned:
    per slot in authored order, fill-then-tier-then-pick, then that
    piece's quality."""
    from .engine import RNG  # the LIVE binding (seed_rng rebinds)

    _floor = getattr(spec, "quality_floor", 0)
    _fixed = getattr(spec, "worn_armor", ())
    if _fixed:
        return [
            ["armor", pid, ground_scale.rolled_quality(band, RNG, _floor)]
            for pid in _fixed
        ]
    _mod = getattr(spec, "worn_fill_mod", 1.0)
    _worn = []
    for _slot in getattr(spec, "worn_armor_slots", ()):
        _pid = ground_scale.roll_worn_slot(_slot, band, RNG, _mod)
        if not _pid:
            continue
        _worn.append([
            "armor", _pid, ground_scale.rolled_quality(band, RNG, _floor),
        ])
    return _worn


def worn_entries(stamp: dict | None) -> tuple:
    """The worn pieces as :class:`StoredGroundEquipment` entries — the
    input shape the armor bonus/defense sum helpers read (the player's
    own modifier math, one pass over the stamped pieces)."""
    from .ground_equipment import StoredGroundEquipment

    entries = []
    for _piece in (stamp or {}).get("worn") or ():
        # Armor-tagged triples only — a hand-corrupted tag never
        # type-confuses the kit-drop payload (the shape filter in the
        # loader can't see the tag).
        if not isinstance(_piece, (list, tuple)) or len(_piece) < 3:
            continue
        if str(_piece[0]) != "armor":
            continue
        try:
            entries.append(
                StoredGroundEquipment("armor", str(_piece[1]), int(_piece[2])),
            )
        except (TypeError, ValueError):
            continue
    return tuple(entries)


def worn_bonuses(stamp: dict | None) -> tuple:
    """The worn pieces' ``(hit_bonus, melee_bonus)`` (SETTLED 27/41 —
    the eyes' +8 hit moves volley pick AND shot resolution
    identically; the arms' melee bonus rides the same damage math)."""
    from .ground_equipment import sum_armor_bonus

    _entries = worn_entries(stamp)
    return (
        sum_armor_bonus(_entries, "hit_bonus"),
        sum_armor_bonus(_entries, "melee_bonus"),
    )


def _complete_migrated_stamp(stamp: dict, entity, game_map, spec) -> None:
    """Finish a migrated pre-43 stamp at first engagement: resolve the
    melee set, then backfill the ranged slot's magazine and any pool
    entries the migration left empty (the review catch: a legacy pair
    loaded with ``loaded: {}`` / ``pool: []`` must reach the volley
    economy armed, not knife-locked)."""
    from .data.npc_chars import find_npc_char

    _spec = spec or find_npc_char(entity.npc_char_id)
    _band = ground_scale.entity_band(entity, game_map, spec=_spec)
    from .engine import RNG  # the LIVE binding (seed_rng rebinds)

    stamp[SET_MELEE] = ground_scale.roll_slot(
        getattr(_spec, "melee_families", ()),
        getattr(_spec, "melee_weapons", ()), _band, RNG,
        quality_floor=getattr(_spec, "quality_floor", 0),
    )
    for _pair in (pair_for(stamp, SET_RANGED), pair_for(stamp, SET_MELEE)):
        _arm_migrated_pair(stamp, _pair)


def _arm_migrated_pair(stamp: dict, pair) -> None:
    """Give one migrated pair its magazine (full) and pool entry when
    the stamp lacks them — never touches live mid-fight counts."""
    from .engine import RNG  # the LIVE binding (seed_rng rebinds)
    from .data.ground_weapons import find_ground_weapon

    if pair is None:
        return
    try:
        _ws = find_ground_weapon(pair[0])
    except KeyError:
        return
    if not ground_scale.ammo_fed(_ws):
        return
    if stamp.get("loaded", {}).get(pair[0]) is None:
        stamp.setdefault("loaded", {})[pair[0]] = _ws.ammo_capacity
    if pool_entry_index(stamp, _ws.ammo_type) is None:
        _entry = ground_scale.roll_pool_entry(_ws.ammo_type, RNG)
        if _entry is not None:
            stamp.setdefault("pool", []).append(_entry)


def pair_for(stamp: dict, set_name: str):
    """One set's ``(weapon_id, quality)`` pair, or ``None``."""
    _pair = stamp.get(set_name)
    return None if not _pair else (_pair[0], _pair[1])


def other_set(set_name: str) -> str:
    """The opposite set's name."""
    return SET_MELEE if set_name == SET_RANGED else SET_RANGED


def active_set(stamp: dict) -> str:
    """The active set's name (defaults to ranged on stale stamps)."""
    return stamp.get("active") or SET_RANGED


def active_pair(stamp: dict):
    """The active set's ``(weapon_id, quality)`` pair, or ``None``."""
    return pair_for(stamp, active_set(stamp))


def swap_active(stamp: dict) -> None:
    """Flip the active-set flag — the 1-AP set switch (silent by
    design; the scorer drives it, never a log line)."""
    stamp["active"] = other_set(active_set(stamp))


def has_any_weapon(stamp: dict | None) -> bool:
    """Whether the loadout carries at least one weapon."""
    if not stamp:
        return False
    return stamp.get(SET_RANGED) is not None or stamp.get(SET_MELEE) is not None


def pool_entry_index(stamp: dict, ammo_type: str) -> int | None:
    """The pool list index feeding ``ammo_type``, or ``None``."""
    from .data.ground_items import list_ground_ammo

    _ids = {_a.id for _a in list_ground_ammo() if _a.ammo_type == ammo_type}
    for _i, _entry in enumerate(stamp.get("pool", [])):
        if _entry[0] == "ammo" and _entry[1] in _ids:
            return _i
    return None


def pool_rounds(stamp: dict, ammo_type: str) -> int:
    """Carried reserve rounds for ``ammo_type``."""
    _i = pool_entry_index(stamp, ammo_type)
    return 0 if _i is None else stamp["pool"][_i][2]


def _set_pool_rounds(stamp: dict, ammo_type: str, rounds: int) -> None:
    _i = pool_entry_index(stamp, ammo_type)
    if _i is not None:
        stamp["pool"][_i][2] = max(0, rounds)


def loaded_rounds(stamp: dict, weapon_id: str) -> int | None:
    """Rounds in ``weapon_id``'s magazine; ``None`` = not ammo-fed."""
    _loaded = stamp.get("loaded", {})
    return None if weapon_id not in _loaded else _loaded[weapon_id]


def _set_loaded(stamp: dict, weapon_id: str, rounds: int) -> None:
    stamp.setdefault("loaded", {})[weapon_id] = max(0, rounds)


def magazine_pays_shot(stamp: dict, ws) -> bool:
    """Whether the MAGAZINE alone pays one shot. The flee volley's
    fire gate and the burst's mid-action dry break (a pool round
    cannot be chambered mid-burst); the volley pick reads the
    pool-aware :func:`can_feed_shot` since the reload build)."""
    if not ground_scale.ammo_fed(ws):
        return True
    return (loaded_rounds(stamp, ws.id) or 0) >= ws.ammo_per_shot


def can_feed_shot(stamp: dict, ws) -> bool:
    """Whether one FIRE action's first shot is payable in ammo:
    magazine carries a shot, or the pool can refill it (the reload
    era's affordability — the pick flips to this gate when reload
    lands)."""
    if magazine_pays_shot(stamp, ws):
        return True
    return pool_rounds(stamp, ws.ammo_type) > 0


def is_dry(stamp: dict, ws) -> bool:
    """Whether an ammo-fed weapon has NO ammo anywhere — the dry-switch
    trigger (SETTLED 43: dry means the 1-AP swap to the melee set).
    The exact complement of :func:`can_feed_shot` on ammo-fed weapons,
    expressed through it so the two can never drift."""
    if not ground_scale.ammo_fed(ws):
        return False
    return not can_feed_shot(stamp, ws)


def drain_action(stamp: dict, ws, shots_fired: int) -> None:
    """Consume ``ammo_per_shot`` per shot fired from the magazine
    (the player's ``consume_weapon_round`` mirror, per burst shot)."""
    if not ground_scale.ammo_fed(ws):
        return
    _set_loaded(
        stamp, ws.id,
        (loaded_rounds(stamp, ws.id) or 0) - ws.ammo_per_shot * shots_fired,
    )


def needs_reload(stamp: dict, ws) -> bool:
    """Ammo-fed and the magazine cannot pay one shot."""
    if not ground_scale.ammo_fed(ws):
        return False
    return (loaded_rounds(stamp, ws.id) or 0) < ws.ammo_per_shot


def reload_from_pool(stamp: dict, ws) -> int:
    """Move reserve rounds into the magazine; returns rounds moved.
    The amount is the PLAYER's reload law (``reload_amount`` — fill
    toward capacity, bounded by the store): one law, both sides.
    Imported off ground_equipment's stable re-export surface (the
    ground_weapon_ammo cycle resolves through it)."""
    from .ground_equipment import reload_amount

    if not needs_reload(stamp, ws):
        return 0
    _loaded = loaded_rounds(stamp, ws.id) or 0
    _amount = reload_amount(
        _loaded, ws.ammo_capacity, pool_rounds(stamp, ws.ammo_type),
    )
    if _amount <= 0:
        return 0
    _set_loaded(stamp, ws.id, _loaded + _amount)
    _set_pool_rounds(stamp, ws.ammo_type, pool_rounds(stamp, ws.ammo_type) - _amount)
    return _amount


def magazine_ammo_types(stamp: dict | None) -> set:
    """The ammo types of the stamp's own magazine-fed weapons (SETTLED
    43's retirement key: the death-time roll retires for ammo the
    enemy carried a magazine weapon for — organic weapons and machine
    parts author their pool ammo as ordinary loot, untouched). NOT the
    player-side twin ``bandolier.carried_ammo_types`` (that one sweeps
    every typed weapon; this one excludes typed-but-infinite, which
    would over-retire)."""
    from .data.ground_weapons import find_ground_weapon

    _types: set = set()
    for _set_name in (SET_RANGED, SET_MELEE):
        _pair = pair_for(stamp or {}, _set_name)
        if _pair is None:
            continue
        try:
            _ws = find_ground_weapon(_pair[0])
        except KeyError:
            continue
        if ground_scale.ammo_fed(_ws):
            _types.add(_ws.ammo_type)
    return _types


def pool_entries(stamp: dict | None) -> list[list]:
    """The carried pool's remainder entries (drop shape)."""
    if not stamp:
        return []
    return [list(_e) for _e in stamp.get("pool", []) if _e[2] > 0]
