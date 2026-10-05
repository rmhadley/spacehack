"""The carried-loot doctrine (doc 48 phase 12, SETTLED 55-58).

The census over every row's drop channels, keyed on
:func:`loot_class` — the classifier the tinker gate, the authoring
laws, and the expectations table all read. Pins grow with the
builds: this file lands with the classifier (build 1) and carries
the retirement, fiction-cleanup, trophy, and volume pins as the
phase's builds land.
"""

from src.spacehack.data.npc_chars import list_npc_chars, loot_class

CLASS_PINS = {
    "ancient": {"watcher", "shredder", "warden"},
    "apex": {
        "dune_behemoth", "glacier_wyrm", "caldera_tyrant",
        "canopy_maw", "scrap_colossus", "mesa_mauler",
    },
    "machine": {"sentry_drone", "assault_drone"},
    "humanoid": {
        "pirate_raider", "pirate_rifleman", "pirate_brute",
        "militia_trooper", "militia_marine", "militia_sniper",
        "merchant", "consortium_gunner", "consortium_enforcer",
        "consortium_executor",
    },
    # fauna: everything else — the bystander is the one faction-carrying
    # row outside the four (civilian, retired axis, never a loot class).
    "fauna": {
        "rock_scavenger", "ice_worm", "dust_prowler", "frost_spitter",
        "hull_parasite", "vine_hound", "spore_spitter", "ember_crawler",
        "magma_spitter", "scrap_hound", "rust_wasp", "crag_lurker",
        "canyon_viper",
    },
}


def test_loot_class_census_is_pinned():
    classified = {}
    for spec in list_npc_chars():
        if spec.id == "civilian_bystander":
            continue  # ambient dressing, never a loot source
        classified.setdefault(loot_class(spec), set()).add(spec.id)
    assert classified == CLASS_PINS, (
        f"loot_class census drift: {classified}"
    )


def test_scrap_colossus_is_apex_not_machine():
    """The ADVISE-folded precedence call: the colossus is scrap-THEMED
    fauna, not a machine — trophy-only, no energy cells."""
    from src.spacehack.data.npc_chars import find_npc_char

    assert loot_class(find_npc_char("scrap_colossus")) == "apex"


def test_the_warden_is_ancient_however_elite():
    """Precedence headpin: mechanics beats elite — the bold-W ancient
    never classifies apex."""
    from src.spacehack.data.npc_chars import find_npc_char

    assert loot_class(find_npc_char("warden")) == "ancient"


# --- the worn-armor resolver (SETTLED 55) ------------------------------------

from src.spacehack import ground_scale  # noqa: E402
from src.spacehack.data.ground_armor import find_ground_armor, slot_tiers  # noqa: E402


def _cyber_ids() -> set[str]:
    return {
        spec.id for spec in (
            find_ground_armor(pid) for pid in (
                "cybernetic_eyes", "cybernetic_torso",
                "cybernetic_arms", "cybernetic_legs",
            )
        )
    }


def test_slot_ladders_exclude_cyber_and_cover_five_slots():
    ladders = slot_tiers()
    assert sorted(ladders) == ["body", "feet", "hands", "head", "legs"]
    _cyber = _cyber_ids()
    for slot, tiers in ladders.items():
        for ids in tiers.values():
            assert not (_cyber & set(ids)), slot
    # The live gap: hands has NO t4 — the snap-toward-top case.
    assert sorted(ladders["hands"]) == [1, 2, 3]
    assert sorted(ladders["head"]) == [1, 2, 3, 4]


def test_roll_worn_slot_respects_chance_and_windows():
    class _AlwaysMiss:
        def random(self):
            return 0.99  # above every fill chance

        def choice(self, seq):
            return seq[0]

    class _Hit:
        def __init__(self):
            self.draws = 0

        def random(self):
            return 0.0  # every fill hits; the window's FIRST tier wins

        def choice(self, seq):
            return seq[0]

    assert ground_scale.roll_worn_slot("head", 4, _AlwaysMiss()) == ""
    # A low draw fills the slot AND lands the window's FIRST tier —
    # hands at band 4 goes straight to t3 (the window's low entry).
    assert ground_scale.roll_worn_slot(
        "hands", 4, _Hit(),
    ) in slot_tiers()["hands"][3]
    # THE SNAP PIN (the reviewer's probe): a TOP draw on the gap
    # slot rolls t4, and _snap_tier lands the tier below — hands has
    # no t4, so the t4 window roll snaps to powered_gloves (t3).
    assert ground_scale.roll_worn_slot("hands", 4, _TopDraw()) == (
        "powered_gloves"
    )
    # The same top draw on head (a real t4 exists) lands the top.
    assert ground_scale.roll_worn_slot(
        "head", 4, _TopDraw(),
    ) in slot_tiers()["head"][4]


class _TopDraw:
    def random(self):
        return 0.85  # fills (chance .9); window 0.85-0.3=0.55 -> top tier

    def choice(self, seq):
        return seq[0]


def test_roll_worn_slot_fill_mod_shapes_the_row():
    """Merchants author ~0.15 — a scripted .20 draw fills the default
    row but not the merchant-shaped one."""

    class _Draw:
        def __init__(self, value):
            self._value = value

        def random(self):
            return self._value

        def choice(self, seq):
            return seq[0]

    assert ground_scale.roll_worn_slot("body", 1, _Draw(0.20)) != ""
    assert ground_scale.roll_worn_slot(
        "body", 1, _Draw(0.20), fill_mod=0.15,
    ) == ""


def test_roll_worn_slot_skips_an_empty_ladder():
    assert ground_scale.roll_worn_slot("nonexistent", 3, _Hit_()) == ""


class _Hit_:
    def random(self):
        return 0.0

    def choice(self, seq):
        return seq[0]


def test_fixed_worn_sets_bypass_the_resolver():
    """The rungs' cybernetics never roll slots — the fixed set wins
    outright (SETTLED 55)."""
    from types import SimpleNamespace

    from src.spacehack import ground_loadout
    from src.spacehack.data.npc_chars import find_npc_char

    spec = find_npc_char("consortium_executor")
    entity = SimpleNamespace(npc_char_id="consortium_executor")
    stamp = {"ranged": None, "melee": None, "loaded": {}, "pool": []}
    worn = ground_loadout.ensure_worn(stamp, entity, None, spec, 4)
    assert [entry[1] for entry in worn] == list(spec.worn_armor)
    assert all(entry[2] >= spec.quality_floor for entry in worn)


def test_slot_rows_resolve_through_the_composition():
    """A slot-authored row stamps per-slot pieces with inline
    qualities; the RNG order is deterministic under a seed."""
    from types import SimpleNamespace

    from src.spacehack import engine, ground_loadout

    spec = SimpleNamespace(
        id="row", worn_armor=(), worn_armor_slots=("head", "hands"),
        worn_fill_mod=1.0, quality_floor=0,
    )
    entity = SimpleNamespace(npc_char_id="row")
    # The p12 idiom: the draws import engine.RNG at CALL time, so
    # seeding the engine binding reaches them directly.
    engine.RNG.seed(11)
    stamp_a = {}
    worn_a = ground_loadout.ensure_worn(stamp_a, entity, None, spec, 3)
    engine.RNG.seed(11)
    stamp_b = {}
    worn_b = ground_loadout.ensure_worn(stamp_b, entity, None, spec, 3)
    assert worn_a == worn_b  # deterministic draw order
    for entry in worn_a:
        ladders = slot_tiers()
        slot = find_ground_armor(entry[1]).slot
        assert entry[1] in ladders[slot][find_ground_armor(entry[1]).tech_level]
        assert 0 <= entry[2] <= 3
