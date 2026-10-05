"""Ground enemy band resolver (doc 48 phase 4, SETTLED 35).

One vocabulary — a ground site's BAND (1-4) — sizes every
``NpcCharSpec`` spawn along the three axes: stats (band →
effective-level budget split by the spec's archetype weights), gear
(weapon FAMILIES rolled inside the band's tier window), and quality
(equip- and drop-time ladders step with band). Pure functions only:
callers pass ``rng``; nothing here mutates or draws.

Band 0 is "no band": base-10 stats, band-1 quality — exactly today's
numbers. Bystanders author all-zero weights so any stamp leaves them
scale-invariant (the SETTLED 14 exemption, as data); un-stamped
legacy saves derive their band from the site via :func:`entity_band`.
"""

from __future__ import annotations

from dataclasses import dataclass

# The player system the bands mirror (SETTLED 15): base 10, five
# points per level, stats cap at 100.
STAT_BASE: int = 10
STAT_CAP: int = 100

# Band → effective player level (SETTLED 35): budgets read
# +10 / +45 / +85 / +145 points over base 10 across the six stats.
BAND_LEVELS: tuple[int, ...] = (3, 10, 18, 30)

# Top-two tier windows, weighted up (SETTLED 35 verbatim): band 2
# rolls t1 70% / t2 30%; bands 3-4 roll 30% low / 70% high.
BAND_WINDOWS: tuple[tuple[tuple[int, float], ...], ...] = (
    ((1, 1.0),),
    ((1, 0.7), (2, 0.3)),
    ((2, 0.3), (3, 0.7)),
    ((3, 0.3), (4, 0.7)),
)

# Equip-time and drop-time quality ladders by band (SETTLED 35).
# Band 1 equals KILL_QUALITY_RATES — un-stamped spawns roll today's
# odds exactly.
BAND_QUALITY_RATES: tuple[tuple[int, int, int], ...] = (
    (5, 11, 25), (7, 14, 30), (8, 17, 35), (10, 20, 40),
)

# stat_weights positional order — reflexes, strength, stamina, then
# the three space skills (SETTLED 19: every NPC carries all six) —
# IS GroundBandStats's field order.


@dataclass(frozen=True)
class GroundBandStats:
    """One enemy's derived six-block at a band."""

    reflexes: int = STAT_BASE
    strength: int = STAT_BASE
    stamina: int = STAT_BASE
    gunnery: int = STAT_BASE
    piloting: int = STAT_BASE
    engineering: int = STAT_BASE


def clamp_band(band: int) -> int:
    """Clamp into ``[0, 4]`` — 0 stays (no band)."""
    return max(0, min(4, int(band)))


def band_level(band: int) -> int:
    """The band's effective player level (SETTLED 35: 3/10/18/30)."""
    return BAND_LEVELS[max(1, clamp_band(band)) - 1]


def band_budget(band: int) -> int:
    """Total stat points the band's effective level grants: 5×(L−1)."""
    band = clamp_band(band)
    return 0 if band == 0 else 5 * (BAND_LEVELS[band - 1] - 1)


def allocate_budget(budget: int, weights) -> list[int]:
    """Largest-remainder split of ``budget`` over ``weights`` — the
    ONE allocation loop both theaters' resolvers call (ground stats,
    ship skills; doc 48 phases 4+7).

    Fractional ties go to the earlier slot; zero-weight slots never
    receive remainder points; the whole budget lands when weights sum
    to 1.
    """
    raw = [budget * weight for weight in weights]
    floors = [int(value) for value in raw]
    candidates = sorted(
        (i for i, weight in enumerate(weights) if weight > 0),
        key=lambda i: (-(raw[i] - floors[i]), i),
    )
    for i in range(min(budget - sum(floors), len(candidates))):
        floors[candidates[i]] += 1
    return floors


def derive_stats(spec, band: int) -> GroundBandStats:
    """Base-10 six-block plus the band budget split by the spec's
    ``stat_weights``.

    An all-zero row (the band-exempt bystander) reads flat base at
    every band. Each stat caps at 100.
    """
    if not any(spec.stat_weights):
        return GroundBandStats()
    floors = allocate_budget(band_budget(band), spec.stat_weights)
    return GroundBandStats(*(
        min(STAT_CAP, STAT_BASE + floors[i]) for i in range(len(floors))
    ))


def planet_band(mission_tier: int) -> int:
    """A planet's mission tier as a band, clamped into [1, 4]."""
    return max(1, min(4, int(mission_tier)))


def quality_rates(band: int) -> tuple[int, int, int]:
    """The band's equip/drop quality ladder (band 0 reads band 1)."""
    return BAND_QUALITY_RATES[max(1, clamp_band(band)) - 1]


def _window_tier(window, rng) -> int:
    """Roll one tier from a weighted window; the tail catches drift."""
    roll = rng.random()
    for tier, weight in window:
        roll -= weight
        if roll < 0:
            return tier
    return window[-1][0]


def _snap_tier(tiers, tier: int) -> int:
    """Nearest populated family tier, preferring at-or-above (toward
    the window's top) — explosives ladder t3-t4, so a band-3 t2 roll
    lands the grenade launcher, never an empty tier."""
    populated = set(tiers)
    for candidate in (*range(tier, 5), *range(tier - 1, 0, -1)):
        if candidate in populated:
            return candidate
    return tier


def roll_weapon(spec, band: int, rng) -> str:
    """One weapon id from the spec's families at the band's window.

    Family first (uniform over ``weapon_families``), then the tier
    window. ``pin_window_top`` (the sniper) takes the window's ceiling
    tier outright — the railgun at band 4 is the precision payoff.
    Rows without families keep their fixed ``weapons`` and never call
    this; an unpopulated family is a data error and raises. The
    spec-shaped SETTLED-35 surface (test-pinned; the loadout roll
    composes the family-generic primitive beneath it).
    """
    if not spec.weapon_families:
        return ""
    return roll_family_weapon(
        spec.weapon_families, band, rng, pin_window_top=spec.pin_window_top,
    )


def roll_family_weapon(
    families, band: int, rng, *, pin_window_top: bool = False,
) -> str:
    """One weapon id from ``families`` at the band's tier window —
    the family-ladder roll both loadout sets share (doc 48 SETTLED
    43: the melee set rolls through the SAME windows as the ranged
    set)."""
    from .data.ground_weapons import family_tiers

    family = rng.choice(families)
    window = BAND_WINDOWS[max(1, clamp_band(band)) - 1]
    if pin_window_top:
        tier = window[-1][0]
    else:
        tier = _window_tier(window, rng)
    tiers = family_tiers(family)
    return rng.choice(tiers[_snap_tier(tiers, tier)])


def rolled_quality(band: int, rng, quality_floor: int = 0) -> int:
    """One ladder draw at the band's rates, CLAMPED to the floor (doc
    48 SETTLED 51 — the one clamp idiom every ground quality roll
    reads: ``max(floor, rolled)``, the below-floor mass lumping onto
    the floor rung, the top tier's odds never moving)."""
    from .data.quality import roll_quality

    return max(quality_floor, roll_quality(quality_rates(band), rng))


# Per-band per-slot worn-armor fill chance (doc 48 SETTLED 55): each
# eligible slot rolls independently; the row's ``worn_fill_mod``
# shapes it (merchants ~0.15, soldiers 1.0). Tunable — the
# expectations table pins band 1 often-zero and band 4 usually-armored.
WORN_FILL_CHANCE: tuple[float, ...] = (0.25, 0.50, 0.70, 0.90)


def worn_fill_chance(band: int) -> float:
    """The band's per-slot fill probability (band 0 reads band 1)."""
    return WORN_FILL_CHANCE[max(1, clamp_band(band)) - 1]


def roll_worn_slot(slot: str, band: int, rng, fill_mod: float = 1.0) -> str:
    """One eligible slot's armor id at the band (doc 48 SETTLED 55):
    the fill roll (the band's chance x the row's ``fill_mod``), then
    the tier through the weapon-style window on the slot's catalog
    ladder (derived at call time — new armor joins the bands),
    snapped toward the top on gaps (hands has no t4). ``""`` when
    the fill misses or the slot carries no ladder — a future
    cyber-only slot skips, never raises."""
    from .data.ground_armor import slot_tiers

    if rng.random() >= worn_fill_chance(band) * fill_mod:
        return ""
    tiers = slot_tiers().get(slot)
    if not tiers:
        return ""
    window = BAND_WINDOWS[max(1, clamp_band(band)) - 1]
    tier = _snap_tier(tiers, _window_tier(window, rng))
    return rng.choice(tiers[tier])


def rolled_weapon_quality(weapon_id: str, band: int, rng,
                          quality_floor: int = 0) -> int:
    """Equip-time quality roll (SETTLED 13/35): the ladder rides the
    spawn band, clamped up to the spec's ``quality_floor`` (doc 48
    SETTLED 51 — consortium rungs never roll base). Real gear only —
    organic parts never variant, never consume roll RNG. (Moved from
    ``noise`` when the loadout roll joined its family, doc 48
    SETTLED 43.)"""
    if not weapon_id:
        return 0
    from .data.ground_weapons import find_ground_weapon

    try:
        if not find_ground_weapon(weapon_id).loot_droppable:
            return 0
    except KeyError:
        return 0
    return rolled_quality(band, rng, quality_floor)


def carried_pool_range(ceiling: int) -> tuple[int, int]:
    """The carried-ammo pool's roll range (doc 48 SETTLED 43 lean):
    half to three-quarters of the old death-roll range — NOT a full
    stack. ``ceiling`` is the drop-quantity law's cap for the ammo."""
    return max(1, ceiling // 2), max(1, -(-ceiling * 3 // 4))


def pool_feed(ammo_type: str) -> tuple[str, int] | None:
    """The ammo stack item feeding ``ammo_type``: ``(item_id, ceiling)``
    or ``None`` when no catalog ammo matches."""
    from .data.ground_items import list_ground_ammo
    from .ground_equipment import drop_quantity_ceiling

    for _a in list_ground_ammo():
        if _a.ammo_type == ammo_type:
            return _a.id, drop_quantity_ceiling(
                "ammo", _a.id, _a.rounds_per_stack,
            )
    return None


def roll_loadout(spec, band: int, rng) -> dict:
    """The full two-set loadout stamp (doc 48 SETTLED 43): both weapon
    pairs (each with its own equip-time quality), per-weapon magazine
    counts (full, the player instance's mirror), and the carried ammo
    pool in the ``carried_items`` shape — one entry per distinct ammo
    type, rolled in the ``carried_pool_range`` window.

    Fixed-weapon rows (fauna, machines) keep their ``weapons``/
    ``melee_weapons`` verbatim; empty slots stamp ``None``. Pure: the
    caller stamps the result on the entity.
    """
    _floor = getattr(spec, "quality_floor", 0)
    _ranged = roll_slot(spec.weapon_families, spec.weapons, band, rng,
                        quality_floor=_floor)
    _melee = roll_slot(getattr(spec, "melee_families", ()),
                       getattr(spec, "melee_weapons", ()), band, rng,
                       quality_floor=_floor)
    _loaded = _full_magazines((_ranged, _melee))
    return {
        "ranged": _ranged, "melee": _melee,
        "loaded": _loaded,
        "pool": _stamp_pool((_ranged, _melee), rng),
        "active": "ranged",
    }


def ammo_fed(ws) -> bool:
    """Whether a ground-weapon spec carries a magazine (doc 48 SETTLED
    43's participation rule: ammo DATA, not faction — melee, plasma,
    and organic parts are infinite and never reload)."""
    return ws.ammo_capacity > 0 and ws.ammo_type is not None


def roll_slot(families, fixed, band: int, rng, quality_floor: int = 0):
    """One set's ``(weapon_id, quality)`` pair, or ``None``: the family
    ladder when families are authored, else the fixed weapon. The
    quality draw clamps to the spec's floor (SETTLED 51)."""
    if families:
        _wid = roll_family_weapon(families, band, rng)
    else:
        _wid = fixed[0] if fixed else ""
    if not _wid:
        return None
    return [_wid, rolled_weapon_quality(_wid, band, rng, quality_floor)]


def _full_magazines(pairs) -> dict:
    """Per-weapon magazine counts for a rolled loadout: every ammo-fed
    weapon stamps FULL capacity (the player instance's mirror)."""
    from .data.ground_weapons import find_ground_weapon

    _loaded: dict[str, int] = {}
    for _pair in pairs:
        if _pair is None:
            continue
        try:
            _ws = find_ground_weapon(_pair[0])
        except KeyError:
            continue
        if _ws.ammo_capacity > 0 and _ws.ammo_type is not None:
            _loaded[_pair[0]] = _ws.ammo_capacity
    return _loaded


def roll_pool_entry(ammo_type: str, rng) -> list | None:
    """One pre-rolled carried-pool entry for ``ammo_type`` (the ONE
    roll both the loadout stamp and the migration fill call, doc 48
    SETTLED 43), or ``None`` when no catalog ammo feeds it."""
    _feed = pool_feed(ammo_type)
    if _feed is None:
        return None
    _lo, _hi = carried_pool_range(_feed[1])
    return ["ammo", _feed[0], rng.randint(_lo, _hi)]


def _stamp_pool(pairs, rng) -> list[list]:
    """The carried-ammo pool for a rolled loadout: one pre-rolled entry
    per DISTINCT ammo type among the pairs' ammo-fed weapons (SETTLED
    43 — what they carry is what they shoot from and drop)."""
    from .data.ground_weapons import find_ground_weapon

    _pool: list[list] = []
    _seen: set[str] = set()
    for _pair in pairs:
        if _pair is None:
            continue
        try:
            _ws = find_ground_weapon(_pair[0])
        except KeyError:
            continue
        if ammo_fed(_ws) and _ws.ammo_type not in _seen:
            _seen.add(_ws.ammo_type)
            _entry = roll_pool_entry(_ws.ammo_type, rng)
            if _entry is not None:
                _pool.append(_entry)
    return _pool


def context_band(game_map) -> int:
    """Derive the site's band from the map (un-stamped legacy saves).

    Dig floors re-derive their climbed band from the cache key through
    the dig module's own formula (single-sourced); every other map
    reads band 1 — today's numbers. New spawns always arrive stamped,
    so this only bridges one save transition.
    """
    key = getattr(game_map, "interior_cache_key", "") or ""
    if not key.startswith("dig:"):
        return 1
    from .digs import _dig_tier, parse_cache_key

    parsed = parse_cache_key(key)
    if parsed is None:
        return 1
    planet_id, _site_id, floor = parsed
    from .data.planets import find_planet_spec

    try:
        return _dig_tier(find_planet_spec(planet_id), floor)
    except KeyError:
        return 1


def entity_band(entity, game_map=None, spec=None) -> int:
    """The entity's band: a spec-authored FIXED band wins outright
    (doc 48 SETTLED 42 — the ancient rows derive at band 4 flat; the
    site's floor stamp never dilutes them); else the stamped band, a
    0 stamp deriving from the site."""
    if spec is not None and getattr(spec, "fixed_band", 0) > 0:
        return clamp_band(spec.fixed_band)
    return clamp_band(getattr(entity, "spawn_band", 0)) or context_band(
        game_map,
    )
