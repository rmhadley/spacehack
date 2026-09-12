"""Shared landing-path scaffolding for city-landing tests.

The dev-teleport test (test_dev_mode) and the dark-dock-gate tests
(test_identity) both drive ``land_at_city`` through a minimal
GameLoopState; one factory keeps the two in sync.
"""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack import game_interactions


def landing_state(**ctx_extra) -> game_interactions.GameLoopState:
    """A minimal space-mode state (no ship) shaped for land_at_city.

    Extra kwargs land on the ctx (e.g. ``broadcast_dark=True``).
    """
    ctx = SimpleNamespace(
        current_city_id="earth", game_map=None, player=object(),
        militia_scanned=[], ground_hp=23, ground_max_hp=23,
        # Doc 42 phase 3: landing at a dark port fires the discovery
        # trigger through this path — pre-heard so the idempotent
        # no-op keeps these tests off the presentation modal.
        known_rumors=["dark_berth_1"],
        **ctx_extra,
    )
    return game_interactions.GameLoopState(
        ctx=ctx, console=object(), map_w=40, map_h=24,
        log=SimpleNamespace(add=lambda _msg: None), stats=object(),
        game_map=object(), player=object(), current_mode="space",
        current_city_id="earth", player_owned_ship=None,
        player_active_missions=[],
    )
