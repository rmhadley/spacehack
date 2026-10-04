"""NPC character catalog — ground-combat NPC templates with faction linkage.

Mirrors ``data/npc_ships/`` but for foot soldiers rather than ships.
Each :class:`NpcCharSpec` has a ``faction`` field so hostility is
determined by faction reputation rather than a hardcoded flag —
exactly how :class:`NpcShipSpec` works for space combat.

Ground identity families (doc 48 SETTLED 34, the
:data:`CHAR_CLASS_FAMILIES` table): one LETTER per family, members
are case variants of it (lowercase common / uppercase serious), ONE
consistent color per family — pirate `r`/`R` rust, militia `m` blue,
merchant `h` green, consortium `e`/`E` corporate navy, civilian `c`,
machines `d`/`D` bronze. The ancient family amends the convention
(SETTLED 45): three DISTINCT glyphs — Watcher `O`, Shredder `S`,
Warden bold `W` — in one cold violet. The (glyph, color) PAIR is the
identity — a char may repeat across families when the colors
separate. Fauna are not families: species glyphs in biome palettes,
bold apexes later (phase 10).

Adding a new NPC character is one entry in an ``NPC_CHARS`` tuple
in any submodule — no if/else chains, no registry edits.

Note: ``pirate_raider`` names a ground row HERE and a ship in
``data/npc_ships/`` — one pirate crew, two registries. Bare-id
consumers must know which registry they mean (``find_npc_char`` vs
``find_npc_ship``).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MachineMechanics:
    """Per-machine mechanic dials (doc 48 SETTLED 42) — authored data
    on the ancient rows, ``None`` on every ordinary row. A dial at 0
    means the machine lacks that mechanic entirely.

    Attributes:
        stare_core: the Watcher's pre-soak core damage; the 3x3 ring
            reads half. 0 = no stare.
        shriek_radius: the Watcher's alarm hearing radius (the family
            noise column's loud one, 25-40 dial band).
        mend_rate: the Shredder's in-combat start-of-turn heal; NO
            out-of-combat tick (wounds persist between fights).
        field_tile_hp: the Warden's per-shell-tile HP (radius-2 shell,
            one tile thick, empty interior).
        field_regen: the Warden's start-of-turn tile regen, in combat
            (+10/turn minimum — space-shield symmetry, ground-side).
    """

    stare_core: int = 0
    shriek_radius: int = 0
    mend_rate: int = 0
    field_tile_hp: int = 0
    field_regen: int = 0


@dataclass(frozen=True)
class CharClassFamily:
    """One ground identity family (SETTLED 34).

    ``faction`` families recruit every spec carrying that faction;
    explicit ``members`` list ids for factionless families (the
    contemporary machines — fauna share ``faction=""`` but stay out).

    ``glyphs`` is the SETTLED 45 distinct-letter form (the ancient
    family: three utterly different machines, one color): when set,
    members' chars must be IN it. Empty (every other family) means
    the one-letter case-variant convention.
    """

    letter: str
    color: tuple[int, int, int]
    faction: str = ""
    members: tuple[str, ...] = ()
    glyphs: tuple[str, ...] = ()


CHAR_CLASS_FAMILIES: dict[str, CharClassFamily] = {
    "pirate": CharClassFamily(
        letter="r", color=(220, 120, 80), faction="pirate",
    ),
    "militia": CharClassFamily(
        letter="m", color=(100, 200, 255), faction="militia",
    ),
    "merchant": CharClassFamily(
        letter="h", color=(100, 220, 140), faction="merchant",
    ),
    "consortium": CharClassFamily(
        letter="e", color=(90, 120, 200), faction="consortium",
    ),
    "civilian": CharClassFamily(
        letter="c", color=(235, 215, 175), faction="civilian",
    ),
    "machine": CharClassFamily(
        letter="d", color=(200, 180, 110),
        members=("sentry_drone", "assault_drone"),
    ),
    # The ancient family (SETTLED 45): three DISTINCT letters, ONE cold
    # violet — each machine is its own silhouette; bold stays the
    # Warden's unique callout (emphasis now, not disambiguation).
    "ancient": CharClassFamily(
        letter="", color=(170, 140, 250),
        members=("watcher", "shredder", "warden"),
        glyphs=("O", "S", "W"),
    ),
}


@dataclass(frozen=True)
class NpcCharSpec:
    """One ground-combat NPC character template.

    Fields mirror :class:`NpcShipSpec` where applicable. The ``faction``
    field is the primary hostility driver — callers look up
    ``faction.get_attitude(ctx.faction_reputation[faction])`` to
    decide whether this NPC is hostile, neutral, or allied.

    Attributes:
        id: registry key, e.g. ``pirate_raider``.
        name: display name shown in combat HUD.
        char: glyph on the dungeon map, e.g. ``r`` — a case variant
            of the spec's family letter (SETTLED 34; see
            :data:`CHAR_CLASS_FAMILIES`).
        fg: the family's ONE color (SETTLED 34) — members render in
            the same family color exactly; fauna keep species
            palettes.
        faction: ``"pirate"`` | ``"merchant"`` | ``"militia"`` |
            ``"consortium"`` (hidden axis, doc 48) | ``"civilian"``
            (retired as a rep axis — an ambient-dressing accounting
            tag, SETTLED 8) — links to faction reputation for
            hostility.
        hp: base HP before the derived stamina bonus (total =
            ``hp + stamina // 3`` at the spawn's band, doc 48 SETTLED 35).
        weapons: ground weapon ids the NPC always carries — fixed
            rows (fauna, machines) whose organic parts never ladder.
        weapon_families: catalog family modules the band's tier
            window rolls in (doc 48 SETTLED 35); empty = the row is
            fixed via ``weapons``. Families take precedence when both
            are set — never author both.
        melee_weapons: the MELEE set's fixed weapon ids (doc 48
            SETTLED 43 — the player's two-set model mirrored); empty
            = no fixed melee weapon. The same families-take-precedence
            law holds per set: never author both melee fields.
        melee_families: catalog family modules the band's tier window
            rolls the melee set in (the SAME windows as the ranged
            set); empty = no melee set (fauna, machines with organic
            parts).
        stat_weights: six archetype shares (reflexes, strength,
            stamina + the flat 0.05 space-skill share each, SETTLED
            19/35) splitting the band's stat budget; all-zero = the
            band-exempt bystander. Build via :func:`six_weights`.
        elite: bold-render flag (doc 48 SETTLED 33/34) — the unique
            callout (brute, sniper); theater-uniform with ships.
        pin_window_top: take the tier window's ceiling tier outright
            (the sniper's top-rifle pin, SETTLED 35).
        ap: action points per combat round (doc 48 SETTLED 27) —
            humans default 4; non-humans author the speed axis
            (predators 5-6, armored anchors 3). Also the combat-time
            movement budget for un-engaged entities (SETTLED 17).
        ai_aggressiveness: the fire-vs-reposition dial (10-90, doc 48
            SETTLED 23/43 — one dial, one job, both theaters). RAW on
            the ground (the space shield/hull bend stays space); roll
            below fires, at/above repositions in band, re-rolled every
            decision point. Default 50 for every row until the tuning
            pass authors per-spec values (phase 9 build 1's v1).
        loot_pool: trade good ids the NPC may drop on death.
        equipment_loot_pool: optional ``(item_type, item_id)`` ground gear
            entries dropped on death.
        field_item_loot_pool: optional typed ammo/consumable entries dropped
            on death and packed into the Expedition Pack.
        loot_count: (min, max) number of trade-good loot items per kill.
        xp_reward: XP awarded on kill.
        always_hostile: True = ignore faction reputation entirely;
            combat on sight (used for dungeon monsters — non-sentient
            creatures/drones that never grant or cost faction rep).
        behavior: out-of-combat movement mode — ``"hunter"`` patrols
            the map, ``"ambusher"`` holds still until the player gets
            close, ``"guard"`` holds a position without roaming.
        squad_size: (min, max) squad members when procedurally
            spawned (dungeon population / layout ENEMY scatter).
        pack_pool: the PACK APEX's hunting-pack member ids (doc 48
            SETTLED 48) — one species picked per spawn, the pack
            spawned as ONE squad with its apex under a shared
            squad_id (the existing unit mechanics; zero new AI).
            Empty = solo (every other row unchanged).
        pack_size: (min, max) hunting-pack members rolled at spawn
            when ``pack_pool`` is authored.
        tier: drop tier — equipment drops filter to ``tech_level <= tier``.
        armor: flat damage reduction subtracted from player hits
            (plasma halves it).
        fixed_band: pins the spec's band FLAT (doc 48 SETTLED 42) —
            the site's floor-band stamp never dilutes the row.
            0 (every ordinary row) = the entity's stamped band.
        mechanics: the ancient machines' per-row mechanic dials (doc
            48 SETTLED 42) — stare/shriek/mend/field parameters as
            authored data; ``None`` on every ordinary row.
    """
    id: str
    name: str
    char: str
    fg: tuple[int, int, int]
    faction: str
    hp: int = 20
    weapons: tuple[str, ...] = ()
    weapon_families: tuple[str, ...] = ()
    melee_weapons: tuple[str, ...] = ()
    melee_families: tuple[str, ...] = ()
    stat_weights: tuple[float, ...] = ()
    elite: bool = False
    pin_window_top: bool = False
    ap: int = 4
    ai_aggressiveness: int = 50
    loot_pool: tuple[str, ...] = ()
    equipment_loot_pool: tuple[tuple[str, str], ...] = ()
    field_item_loot_pool: tuple[tuple[str, str], ...] = ()
    field_item_loot_count: tuple[int, int] = (0, 1)
    loot_count: tuple[int, int] = (1, 2)
    xp_reward: int = 20
    always_hostile: bool = False
    behavior: str = "hunter"
    squad_size: tuple[int, int] = (1, 1)
    pack_pool: tuple[str, ...] = ()
    pack_size: tuple[int, int] = (1, 1)
    tier: int = 1
    armor: int = 0
    fixed_band: int = 0
    mechanics: MachineMechanics | None = None


# The flat minor share every archetype gives its space skills
# (SETTLED 19: all six on every NPC; SETTLED 35: the share is flat).
SPACE_SKILL_SHARE: tuple[float, float, float] = (0.05, 0.05, 0.05)


def six_weights(
    reflexes: float, strength: float, stamina: float,
) -> tuple[float, ...]:
    """Close one archetype's three ground shares into a six-tuple.

    The ground shares must sum to 0.85; the lint pins the flat space
    tail. Three zero shares mean the band-exempt bystander — the
    exemption is ALL SIX zero, so no stamp ever moves anything.
    """
    if not (reflexes or strength or stamina):
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    return (reflexes, strength, stamina) + SPACE_SKILL_SHARE


# ---------------------------------------------------------------------------
# Lazy-built registry (auto-discover via package iteration)
# ---------------------------------------------------------------------------

_BY_ID: dict[str, NpcCharSpec] | None = None


def _build_registry() -> dict[str, NpcCharSpec]:
    """Auto-discover all NPC char modules under this package."""
    import importlib, pkgutil
    combined: dict[str, NpcCharSpec] = {}
    for _finder, name, _ispkg in pkgutil.iter_modules(__path__):
        if name.startswith("_"):
            continue
        mod = importlib.import_module(f"{__name__}.{name}")
        if hasattr(mod, "NPC_CHARS"):
            for spec in mod.NPC_CHARS:
                combined[spec.id] = spec
    return combined


def _registry() -> dict[str, NpcCharSpec]:
    global _BY_ID
    if _BY_ID is None:
        _BY_ID = _build_registry()
    return _BY_ID


# Save-compat alias (doc 48 phase 3): pre-rename saves carry the
# misspelled bystander id in ``npc_char_id`` — resolve to the fixed id.
_ID_ALIASES = {"civillian_bystander": "civilian_bystander"}


def find_npc_char(char_id: str) -> NpcCharSpec:
    """Look up an :class:`NpcCharSpec` by id; raises :class:`KeyError` on miss."""
    char_id = _ID_ALIASES.get(char_id, char_id)
    try:
        return _registry()[char_id]
    except KeyError:
        raise KeyError(f"unknown npc char id: {char_id!r}") from None


def list_npc_chars() -> tuple[NpcCharSpec, ...]:
    """All registered specs, in registry order (the test/lint surface
    for catalog-wide assertions — sibling of ``list_npc_ships``)."""
    return tuple(_registry().values())
