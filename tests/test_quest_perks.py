"""Quest perks: free trait grants from the Act 0 epilogue (doc 38).

The perks ride the existing trait system — persisted in
``player_traits``, checked by ``has_trait`` everywhere — but are
granted by step completion and never appear as milestone picks.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support.quest_ctx import quest_ctx


def test_perk_grants_on_completion_and_is_free():
    """complete_step appends the perk and logs it; no skill point is
    spent (the milestone screen never offers these)."""
    from src.spacehack.data.traits.core import ALL_TRAITS, QUEST_PERKS
    from src.spacehack.main_quest._core import complete_step

    ctx = quest_ctx(chain="militia", progress={"epilogue_reward_militia": "available"})
    _points_before = ctx.player_skill_points

    assert complete_step(ctx, "epilogue_reward_militia")

    assert "warrant_license" in ctx.player_traits
    # Free: level-ups may AWARD points, but none are consumed.
    assert ctx.player_skill_points >= _points_before
    assert any("Warrant License" in e.text for e in ctx.log.recent(6))
    # Never selectable at milestones.
    assert not (set(QUEST_PERKS) & {t.id for t in ALL_TRAITS})


def test_smugglers_instinct_conceals_a_cut_of_every_hull():
    """10% of natural cargo, minimum 1, stacking with modules."""
    from src.spacehack.data.modules.smuggler import MODULES
    from src.spacehack.ship import smuggler_hold_capacity

    ctx = quest_ctx()
    cruiser = type("O", (), {"ship_id": "cruiser", "modules": ()})()
    starter = type("O", (), {"ship_id": "starter", "modules": ()})()

    assert smuggler_hold_capacity(cruiser) == 0  # no perk, no modules
    ctx.player_traits.append("smugglers_instinct")
    assert smuggler_hold_capacity(cruiser, ctx) == 20  # 200 cargo // 10
    assert smuggler_hold_capacity(starter, ctx) == 5  # 50 cargo // 10
    _mk2 = next(m for m in MODULES if m.smuggler_cargo == 25)
    loaded = type("O", (), {"ship_id": "cruiser", "modules": (_mk2.id,)})()
    assert smuggler_hold_capacity(loaded, ctx) == 45  # perk stacks


def test_perked_hold_protects_a_hot_crate_from_scans():
    """The scan-exposure path honors the perk: a crate that fits the
    perked hold is not confiscated (the bar player's whole career)."""
    from src.spacehack.navigation_scan import _compute_scan_exposure

    crate = type(
        "M", (), {
            "is_smuggle": True, "required_cargo_size": 8,
            "title": "hot run", "mission_id": "mq:test",
            "is_procedural": True, "main_quest_step_id": "",
        }
    )()
    owned = type("O", (), {
        "ship_id": "starter", "modules": (), "inventory": {},
        "mission_reserved": 8, "cargo_ammo": 0,
    })()

    failed, _confiscated = _compute_scan_exposure(owned, [crate])
    assert failed == [crate]  # no perk: the crate overflows the 0 hold

    ctx = quest_ctx()
    ctx.player_traits.append("smugglers_instinct")
    # Starter perk hold is 5 — an 8-unit crate still overflows.
    failed, _confiscated = _compute_scan_exposure(owned, [crate], ctx=ctx)
    assert failed == [crate]
    # A cruiser's 20-unit perk hold covers it.
    owned_cruiser = type("O", (), {
        "ship_id": "cruiser", "modules": (), "inventory": {},
        "mission_reserved": 8, "cargo_ammo": 0,
    })()
    failed, _confiscated = _compute_scan_exposure(owned_cruiser, [crate], ctx=ctx)
    assert failed == []


def test_trait_display_names_cover_quest_perks():
    """Character screen resolves friendly names for BOTH registries —
    quest perks never render as raw ids (playtest catch)."""
    from src.spacehack.character_screen import _trait_names
    from src.spacehack.data.traits.core import trait_name

    assert trait_name("warrant_license") == "Warrant License"
    assert trait_name("smugglers_instinct") == "Smuggler's Instinct"
    assert trait_name("lab_credentials") == "Lab Credentials"
    assert "warrant_license" not in _trait_names(["warrant_license", "sharpshooter"])
    assert "Sharpshooter" in _trait_names(["warrant_license", "sharpshooter"])


def test_board_perk_posts_work_immediately_mid_month():
    """The awkward case (playtest): the board was already viewed this
    month (marked refreshed, empty, perk-gated) — the perk grant
    force-fills it now, not next month."""
    from src.spacehack.mission import ensure_board, fill_empty_slots
    from src.spacehack.main_quest import _core

    ctx = quest_ctx(chain="militia", progress={"epilogue_reward_militia": "available"})
    ctx.mission_boards = {}
    ctx.generated_missions = {}
    # The player checked the captain's board earlier this month: created,
    # filled (gated: nothing posted), marked refreshed.
    board = ensure_board(ctx, "militia_captain", max_slots=5, planet_id="earth")
    fill_empty_slots(
        board, planet_tier=1, completed_ids=frozenset(), active_ids=frozenset(),
        planet_id="earth", generated=ctx.generated_missions, ctx=ctx,
    )
    board.last_refresh_month = ctx.time_month
    assert all(slot is None for slot in board.slots)

    assert _core.complete_step(ctx, "epilogue_reward_militia")

    filled = [slot for slot in board.slots if slot is not None]
    assert filled, "warrants post the moment the perk lands"
    assert all(
        ctx.generated_missions[s].tier >= 3 for s in filled
    )
