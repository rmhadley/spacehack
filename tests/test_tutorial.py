"""Tutorial-mode tests: board forcing, setup, loadout predicate, step state.

The tutorial module's popup firing itself needs a live tcod context, so
the tests here cover the deterministic parts: the mission-board filter,
the credit/board setup, the pure loadout predicate, and step-state
idempotence + the tick's early returns (which must never fire a modal).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from types import SimpleNamespace
from unittest.mock import patch

from src.spacehack import mission
from src.spacehack import tutorial
from src.spacehack.ship import OwnedShip


class _StubLog:
    """Minimal message-log stand-in (setup_tutorial writes to it)."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def add(self, line: str) -> None:
        self.lines.append(str(line))

    def add_colored(self, line: str, color=None) -> None:
        self.lines.append(str(line))


class _StubStats:
    """Minimal HudStats stand-in (setup_tutorial credits)."""

    def __init__(self, credits: int = 75) -> None:
        self.credits = credits


class _StubCtx:
    """Minimal GameContext-like stub for tutorial logic tests."""

    def __init__(self) -> None:
        self.tutorial_mode = False
        self.tutorial_complete = False
        self.tutorial_steps: set[str] = set()
        self.stats = _StubStats()
        self.log = _StubLog()
        self.time_month = 1
        self.mission_boards: dict = {}
        self.player_active_missions: list = []
        self.player_owned_ship = None
        self.equipped_ground_weapons: list[str] = []
        self.current_city_id = "earth"
        self.main_quest_progress: dict = {}
        self.faction_reputation: dict = {}
        self.game_map = None


class TestSetupTutorial:
    def test_grants_credit_bonus_and_seeds_bounty_board(self):
        ctx = _StubCtx()
        tutorial.setup_tutorial(ctx)

        assert ctx.tutorial_mode is True
        assert ctx.stats.credits == 75 + tutorial.TUTORIAL_CREDIT_BONUS
        board = ctx.mission_boards[mission.board_key("bounty_master", "earth")]
        assert board.slots == ["bhguild_sol_scout", None, None, None, None]
        # Refill is suppressed this month so the first talk keeps the seed.
        assert board.last_refresh_month == ctx.time_month


class TestBoardForcing:
    def test_fill_empty_slots_tutorial_only_crimson_no_procedural(self):
        """Tutorial boards show only Crimson Jack; no procedural fill."""
        ctx = _StubCtx()
        ctx.tutorial_mode = True
        board = mission.ensure_board(ctx, "bounty_master", max_slots=5, planet_id="earth")
        generated: dict = {}

        mission.fill_empty_slots(
            board,
            planet_tier=1,
            completed_ids=frozenset(),
            active_ids=frozenset(),
            planet_id="earth",
            generated=generated,
            ctx=ctx,
        )

        filled = [s for s in board.slots if s is not None]
        assert filled == ["bhguild_sol_scout"]
        assert generated == {}

    def test_fill_empty_slots_non_tutorial_still_procedural(self):
        """Normal games keep procedural bounty generation (regression guard)."""
        ctx = _StubCtx()  # tutorial_mode stays False
        board = mission.ensure_board(ctx, "bounty_master", max_slots=5, planet_id="earth")
        generated: dict = {}

        mission.fill_empty_slots(
            board,
            planet_tier=1,
            completed_ids=frozenset(),
            active_ids=frozenset(),
            planet_id="earth",
            generated=generated,
            ctx=ctx,
        )

        # Remaining slots fill with generated procedural bounties.
        assert any(s is not None for s in board.slots[1:])
        assert generated


class TestLoadoutPredicate:
    def test_requires_two_energy_weapons_and_a_shield(self):
        assert tutorial._has_loadout(None) is False

        one_laser = OwnedShip(ship_id="starter", weapons=("light_laser",), modules=())
        assert tutorial._has_loadout(one_laser) is False

        two_lasers = OwnedShip(
            ship_id="starter",
            weapons=("light_laser", "light_laser"),
            modules=(),
        )
        assert tutorial._has_loadout(two_lasers) is False

        with_shield = OwnedShip(
            ship_id="starter",
            weapons=("light_laser", "light_laser"),
            modules=("shield_mk1",),
        )
        assert tutorial._has_loadout(with_shield) is True


class TestTickOrder:
    """Phase 2 — the mission → loadout → launch script sequence.

    ``_show_step`` is monkeypatched to a recorder that marks steps done
    (mimicking the real dismiss-then-mark flow) so the tick's gating
    and ordering are testable without a tcod context.
    """

    @staticmethod
    def _tutorial_ctx() -> _StubCtx:
        ctx = _StubCtx()
        ctx.tutorial_mode = True
        # Phase 1 popups already shown — skip to the mission flow.
        tutorial.mark_step(ctx, "intro")
        tutorial.mark_step(ctx, "first_move")
        return ctx

    def _run(self, ctx, mode: str):
        fired: list[str] = []

        def _fake_show(_, step_id):
            fired.append(step_id)
            tutorial.mark_step(ctx, step_id)

        with patch("src.spacehack.tutorial._show_step", side_effect=_fake_show):
            tutorial.tick(ctx, mode=mode)
        return fired

    def test_accept_then_loadout_then_launch(self):
        ctx = self._tutorial_ctx()
        ctx.player_active_missions = [
            SimpleNamespace(mission_id="bhguild_sol_scout"),
        ]
        ctx.player_owned_ship = OwnedShip(
            ship_id="starter",
            weapons=("light_laser", "light_laser"),
            modules=("shield_mk1",),
        )

        assert self._run(ctx, "city") == ["accepted_crimson"]
        assert self._run(ctx, "city") == ["equipped_loadout"]
        assert self._run(ctx, "space") == ["launched"]
        # All three consumed; nothing left to fire in city/space.
        assert self._run(ctx, "space") == []

    def test_equipped_loadout_gated_on_accepted_contract(self):
        """Buying the loadout early must not skip the contract popup."""
        ctx = self._tutorial_ctx()
        ctx.player_owned_ship = OwnedShip(
            ship_id="starter",
            weapons=("light_laser", "light_laser"),
            modules=("shield_mk1",),
        )

        assert self._run(ctx, "city") == []  # no contract yet — nothing fires
        ctx.player_active_missions = [
            SimpleNamespace(mission_id="bhguild_sol_scout"),
        ]
        assert self._run(ctx, "city") == ["accepted_crimson"]
        assert self._run(ctx, "city") == ["equipped_loadout"]

    def test_launched_gated_on_equipped_loadout(self):
        """Launching without the suggested loadout skips the launch popup
        (the script self-heals from the combat beat onward)."""
        ctx = self._tutorial_ctx()
        ctx.player_active_missions = [
            SimpleNamespace(mission_id="bhguild_sol_scout"),
        ]

        assert self._run(ctx, "city") == ["accepted_crimson"]
        assert self._run(ctx, "space") == []  # not equipped — no launch popup

    def test_accept_only_fires_once(self):
        ctx = self._tutorial_ctx()
        ctx.player_active_missions = [
            SimpleNamespace(mission_id="bhguild_sol_scout"),
        ]
        assert self._run(ctx, "city") == ["accepted_crimson"]
        assert self._run(ctx, "city") == []


class TestStepState:
    def test_mark_step_idempotent(self):
        ctx = _StubCtx()
        ctx.tutorial_mode = True
        tutorial.mark_step(ctx, "intro")
        tutorial.mark_step(ctx, "intro")
        assert ctx.tutorial_steps == {"intro"}
        # Unknown step ids are ignored.
        tutorial.mark_step(ctx, "nope")
        assert ctx.tutorial_steps == {"intro"}

    def test_tick_returns_when_tutorial_complete(self):
        """A finished tutorial never fires popups (no tcod context needed)."""
        ctx = _StubCtx()
        ctx.tutorial_mode = True
        ctx.tutorial_complete = True
        tutorial.tick(ctx, mode="city")
        assert ctx.tutorial_steps == set()

    def test_tick_ignores_non_tutorial_runs(self):
        ctx = _StubCtx()  # tutorial_mode False
        tutorial.tick(ctx, mode="city")
        assert ctx.tutorial_steps == set()

    def test_hooks_noop_outside_tutorial(self):
        """Combat/pickup/move hooks must not fire outside tutorial runs."""
        ctx = _StubCtx()  # tutorial_mode False
        tutorial.notify_move(ctx)
        tutorial.notify_pickup(ctx)
        tutorial.maybe_space_combat_intro(ctx)
        tutorial.maybe_ground_combat_intro(ctx)
        tutorial.notify_ground_combat_ended(ctx)
        assert ctx.tutorial_steps == set()
        assert ctx.tutorial_complete is False
