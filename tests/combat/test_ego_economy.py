"""The ego economy (doc 102 SETTLED 2/3/5): derived pool and load,
the stored high-water burn ratchet, and the ruled Before/After
vocabulary (Ego / Burnt Ego / Install Room).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.spacehack.chrome import (
    ego_load,
    ego_pool,
    install_room,
    predicted_burn_after,
    ratchet_install,
    uninstall_chrome,
)
from src.spacehack.game_context import GameContext
from src.spacehack.data.chrome import list_chrome


def _ctx(level: int = 1, pieces=(), burn: int = 0):
    ctx = GameContext(
        context=None, character_info={"species_id": "human"},
        log=None, game_map=None, player=None, stats=None,
    )
    ctx.player_level = level
    ctx.installed_chrome = list(pieces)
    ctx.ego_burn = burn
    return ctx


_IDS = [spec.id for spec in list_chrome()]


class TestPool:
    def test_pool_formula_at_birth_zero(self):
        assert ego_pool(_ctx(level=1)) == 6
        assert ego_pool(_ctx(level=10)) == 9    # 6 + 9//3
        assert ego_pool(_ctx(level=30)) == 15
        assert ego_pool(_ctx(level=60)) == 25   # last increment L58

    def test_unknown_species_reads_birth_zero(self):
        ctx = _ctx()
        ctx.character_info = {"species_id": "no_such_species"}
        assert ego_pool(ctx) == 6
        ctx.character_info = {}
        assert ego_pool(ctx) == 6


class TestPredictedBurnOnSwaps:
    """The consent table's after-number must net out the replaced
    piece's claim (reviewer catch: swaps double-counted)."""

    def test_same_anatomy_swap_nets_the_replaced_burn(self):
        ctx = _ctx(pieces=("terminus_optics",), burn=1)
        # Re-wearing the same piece: load unchanged, prediction 1.
        assert predicted_burn_after(ctx, "terminus_optics") == 1

    def test_prediction_matches_the_ratchet_landing(self):
        ctx = _ctx(pieces=("terminus_optics", "terminus_neural_stim"), burn=2)
        _predicted = predicted_burn_after(ctx, "terminus_optics")
        ratchet_install(ctx, "terminus_optics")  # self-swap
        assert ctx.ego_burn == _predicted == 2


class TestLoadAndRoom:
    def test_load_sums_installed_burn(self):
        assert ego_load(_ctx(pieces=_IDS[:3])) == 3  # t1 pieces burn 1
        assert install_room(_ctx(pieces=_IDS[:3], level=1)) == 3

    def test_unknown_ids_contribute_nothing(self):
        assert ego_load(_ctx(pieces=["retired_piece"])) == 0


class TestRatchet:
    def test_install_advances_burn_to_load(self):
        ctx = _ctx()
        ratchet_install(ctx, "terminus_optics")
        assert ctx.ego_burn == 1
        ratchet_install(ctx, "terminus_neural_stim")
        assert ctx.ego_burn == 2

    def test_uninstall_frees_room_never_burn(self):
        ctx = _ctx(pieces=("terminus_optics",), burn=1)
        assert uninstall_chrome(ctx, "terminus_optics") is True
        assert ctx.ego_burn == 1          # the ratchet holds
        assert ego_load(ctx) == 0         # the claim recycles
        assert install_room(ctx) == 6     # room is back

    def test_swap_within_peak_costs_nothing_new(self):
        # SETTLED 2's worked example: within the historical peak the
        # ratchet never moves.
        ctx = _ctx(pieces=("terminus_optics",), burn=1)
        ratchet_install(ctx, "terminus_neural_stim")  # different anatomy
        assert ctx.installed_chrome == [
            "terminus_optics", "terminus_neural_stim",
        ]
        uninstall_chrome(ctx, "terminus_optics")
        uninstall_chrome(ctx, "terminus_neural_stim")
        assert ctx.ego_burn == 2          # peak holds after full strip
        assert predicted_burn_after(ctx, "terminus_optics") == 2  # free

    def test_exceeding_peak_pays_the_difference(self):
        ctx = _ctx(level=10)  # pool 9
        for piece_id in _IDS[:3]:
            ratchet_install(ctx, piece_id)
        assert ctx.ego_burn == 3
        uninstall_chrome(ctx, "terminus_optics")
        uninstall_chrome(ctx, "terminus_neural_stim")
        assert ctx.ego_burn == 3  # the peak holds stripped
        # Re-climb within the historical peak: every install free.
        assert predicted_burn_after(ctx, "terminus_neural_stim") == 3
        ratchet_install(ctx, "terminus_neural_stim")
        ratchet_install(ctx, "terminus_optics")
        assert ctx.ego_burn == 3
        # The fourth simultaneous piece exceeds the peak: pays 1.
        ratchet_install(ctx, "terminus_nano_mesh")
        assert ctx.ego_burn == 4

    def test_capacity_reads_the_pool_not_the_burn(self):
        # Rule C: the CLAIM reads the pool — a stripped character at
        # burn 6 still has full Install Room.
        ctx = _ctx(pieces=(), burn=6)
        assert install_room(ctx) == 6
