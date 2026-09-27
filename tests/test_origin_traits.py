"""Tests for the doc 49 origin-trait layer — ORIGIN_TRAITS registry and
the character-creation grant.

Origin traits are granted by species at creation, live outside
ALL_TRAITS (milestones can never offer them), and resolve through
``trait_name`` for the C screen and tombstones.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack.data.traits.core import (
    ALL_TRAITS,
    ORIGIN_TRAITS,
    trait_name,
)
from src.spacehack.game_loop import _configure_new_context
from src.spacehack.game_context import GameContext
from src.spacehack.xp import _qualifying_traits


def _fresh_ctx(species_id: str = "human") -> GameContext:
    """A minimal new-game GameContext (no Pygame runtime attached)."""
    from src.spacehack import message_log, world
    from src.spacehack.hud import HudStats
    _tiles = [[world.Tile("floor", ".", True, (200, 200, 200), (0, 0, 0))
               for _ in range(3)] for _ in range(3)]
    return GameContext(
        context=SimpleNamespace(),
        character_info={"species_id": species_id,
                        "species_name": species_id.title(),
                        "class_id": "merchant", "class_name": "Merchant"},
        log=message_log.MessageLog(capacity=4),
        game_map=world.GameMap(
            width=3, height=3, tiles=_tiles, entities=[],
        ),
        player=world.Entity(
            char="@", fg=(255, 255, 255),
            pos=world.Position(1, 1), name="Player",
        ),
        stats=HudStats(hp=10, max_hp=10, credits=50),
    )


def test_every_species_trait_id_resolves_in_origin_registry():
    from src.spacehack.data.species import list_species
    for spec in list_species():
        assert spec.trait_id in ORIGIN_TRAITS, (
            f"{spec.id}'s trait {spec.trait_id!r} is not registered"
        )


def test_origin_traits_never_appear_in_the_milestone_pool():
    assert not (set(ORIGIN_TRAITS) & {t.id for t in ALL_TRAITS})


def test_qualifying_traits_never_offer_origin_traits():
    """A maxed sheet qualifies for every milestone trait — but no origin
    trait may ever be offered, even though the player holds none."""
    ctx = SimpleNamespace(
        player_traits=[],
        faction_reputation={},
        stats=SimpleNamespace(gunnery=100, piloting=100, engineering=100),
        ground_stats=SimpleNamespace(reflexes=100, strength=100, stamina=100),
        player_counters=SimpleNamespace(
            **{field: 10_000 for field in (
                "merchant_missions_completed", "bar_missions_completed",
                "bounty_missions_completed", "total_kills", "melee_kills",
                "railgun_kills", "explosive_hits", "laser_shots",
                "missile_shots", "plasma_shots", "focused_shots",
            )},
        ),
    )
    qualified = [t.id for t in _qualifying_traits(ctx)]
    assert qualified, "sanity: the maxed sheet must qualify for something"
    assert not (set(qualified) & set(ORIGIN_TRAITS))


def test_trait_name_resolves_origin_traits():
    assert trait_name("sturdy") == "Sturdy"
    assert trait_name("fast_learner") == "Fast Learner"
    assert trait_name("momentum") == "Momentum"
    assert trait_name("longshot") == "Longshot"
    assert trait_name("nimble") == "Nimble"


def test_creation_grant_lands_the_species_trait():
    from src.spacehack.data.species import list_species
    for spec in list_species():
        ctx = _fresh_ctx(spec.id)
        _configure_new_context(ctx, spec.id, "merchant", False)
        assert ctx.player_traits == [spec.trait_id], spec.id
        assert ctx.faction_reputation  # sanity: rep seeded in the same pass


# ---------------------------------------------------------------------------
# Ground hooks (doc 49 phase 1, commit 3): Sturdy, Nimble, hp fold
# ---------------------------------------------------------------------------

def _ground_ctx(traits=(), species_id="human", stamina=10):
    return SimpleNamespace(
        player_traits=list(traits),
        equipped_ground_armor={},
        ground_stats=SimpleNamespace(reflexes=10, strength=10, stamina=stamina),
        character_info={"species_id": species_id},
    )


def test_sturdy_counts_two_armor_with_none_worn():
    from src.spacehack.combat._rules_ground import _armor_defense_total
    assert _armor_defense_total(_ground_ctx(["sturdy"])) == 2
    assert _armor_defense_total(_ground_ctx([])) == 0


def test_sturdy_armor_stacks_with_worn_pieces():
    """The user's model verbatim: gloves +1 on a Martian read +3 total."""
    from src.spacehack.ground_equipment import StoredGroundEquipment
    from src.spacehack.combat._rules_ground import _armor_defense_total
    ctx = _ground_ctx(["sturdy"])
    ctx.equipped_ground_armor = {
        "hands": StoredGroundEquipment("armor", "tactical_gloves", 0),
    }
    assert _armor_defense_total(ctx) == 3


def _fists_enemy():
    from src.spacehack import world
    from src.spacehack.combat._rules_ground import GroundEnemyInstance
    return GroundEnemyInstance(
        entity=world.Entity(
            char="r", fg=(200, 60, 60), pos=world.Position(1, 1), name="rat",
        ),
        spec=SimpleNamespace(armor=0),
    )


def test_sturdy_melee_damage_plus_two_fists_included():
    from src.spacehack.combat import _rules_ground
    base = _rules_ground.damage("fists", _fists_enemy(), _ground_ctx([]))[0]
    sturdy = _rules_ground.damage("fists", _fists_enemy(), _ground_ctx(["sturdy"]))[0]
    assert sturdy - base == 2


def test_sturdy_leaves_ranged_damage_untouched():
    from src.spacehack.combat import _rules_ground
    base = _rules_ground.damage("kinetic_pistol", _fists_enemy(), _ground_ctx([]))[0]
    sturdy = _rules_ground.damage(
        "kinetic_pistol", _fists_enemy(), _ground_ctx(["sturdy"]),
    )[0]
    assert sturdy == base


def test_nimble_ap_gain_100_vs_80_twentieths():
    from src.spacehack.combat._rules_ground import _starting_ap_gain_twentieths
    assert _starting_ap_gain_twentieths(_ground_ctx([])) == 80
    assert _starting_ap_gain_twentieths(_ground_ctx(["nimble"])) == 100
    assert _starting_ap_gain_twentieths(
        _ground_ctx(["nimble", "ace_pilot"]),
    ) == 120


def test_ground_max_hp_total_folds_species_hp_bonus():
    """SETTLED 3-A: the species hp_bonus lands in the GROUND formula —
    species-only numbers match the card (Martian 29, Lalandan 22,
    Human 25)."""
    from src.spacehack.xp import ground_max_hp_total
    assert ground_max_hp_total(_ground_ctx([], "martian", stamina=14)) == 29
    assert ground_max_hp_total(_ground_ctx([], "lalandan", stamina=5)) == 22
    assert ground_max_hp_total(_ground_ctx([], "human", stamina=11)) == 25


def test_new_game_ground_max_hp_uses_the_shared_fold():
    ctx = _fresh_ctx("martian")
    _configure_new_context(ctx, "martian", "merchant", False)
    # species 14 + merchant 12 stamina = 26 -> 20 + 13 + 2 = 35
    assert (ctx.ground_max_hp, ctx.ground_hp) == (35, 35)


# ---------------------------------------------------------------------------
# Fast Learner — level-up grant (doc 49 phase 1, commit 5)
# ---------------------------------------------------------------------------

def test_fast_learner_grants_six_skill_points_per_level():
    """6-vs-5 through the real add_xp level-up: a level-1 character
    reaching level 2 (90 XP) earns 6 with the trait, 5 without."""
    from tests.support.asyncutil import run
    from src.spacehack.xp import add_xp

    def _level_ctx(traits):
        return SimpleNamespace(
            player_traits=list(traits),
            player_xp=0, player_level=1, player_skill_points=0,
            log=SimpleNamespace(
                add_colored=lambda *_args, **_kwargs: None,
            ),
        )

    fast = _level_ctx(["fast_learner"])
    run(add_xp(fast, 90))
    assert (fast.player_level, fast.player_skill_points) == (2, 6)

    plain = _level_ctx([])
    run(add_xp(plain, 90))
    assert (plain.player_level, plain.player_skill_points) == (2, 5)
