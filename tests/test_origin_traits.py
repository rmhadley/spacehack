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


def _fresh_ctx() -> GameContext:
    """A minimal new-game GameContext (no Pygame runtime attached)."""
    from src.spacehack import message_log, world
    from src.spacehack.hud import HudStats
    _tiles = [[world.Tile("floor", ".", True, (200, 200, 200), (0, 0, 0))
               for _ in range(3)] for _ in range(3)]
    return GameContext(
        context=SimpleNamespace(),
        character_info={"species_id": "human", "species_name": "Human",
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
        ctx = _fresh_ctx()
        _configure_new_context(ctx, spec.id, "merchant", False)
        assert ctx.player_traits == [spec.trait_id], spec.id
        assert ctx.faction_reputation  # sanity: rep seeded in the same pass
