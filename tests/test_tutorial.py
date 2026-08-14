"""Tutorial-mode tests: board forcing, setup, loadout predicate, step state.

The tutorial module's popup firing itself needs a live graphics context, so
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
from src.spacehack.ground_equipment import GroundWeaponInstance
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
        self.equipped_ground_weapons: list[GroundWeaponInstance] = []
        self.current_city_id = "earth"
        self.main_quest_progress: dict = {}
        self.faction_reputation: dict = {}
        self.game_map = None
        self.player_xp = 0
        self.player_level = 1
        self.player_skill_points = 0


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

    def test_fill_empty_slots_after_tutorial_complete_fills_normally(self):
        """Once the finale fires, boards repopulate (static + procedural).

        Regression: suppression was gated on ``tutorial_mode`` alone,
        which stays True for the whole run, so every non-bounty board
        stayed empty forever after the tutorial ended.
        """
        ctx = _StubCtx()
        ctx.tutorial_mode = True
        ctx.tutorial_complete = True
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

        # The whitelist no longer applies and procedural gen is back on.
        assert generated
        assert sum(1 for s in board.slots if s is not None) > 1

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
    and ordering are testable without a live graphics context.
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


class TestSpaceCombatAndLoot:
    """Phase 3 — combat intro, loot popups, and the signal beat."""

    @staticmethod
    def _tutorial_ctx() -> _StubCtx:
        ctx = _StubCtx()
        ctx.tutorial_mode = True
        # Everything through launch done; the fight is next.
        for _s in ("intro", "first_move", "accepted_crimson",
                   "equipped_loadout", "launched"):
            tutorial.mark_step(ctx, _s)
        return ctx

    @staticmethod
    def _loot_entity():
        return SimpleNamespace(loot_data={"good_id": "scrap_metal", "quantity": 1})

    def _run(self, ctx, mode: str):
        fired: list[str] = []

        def _fake_show(_, step_id):
            fired.append(step_id)
            tutorial.mark_step(ctx, step_id)

        with patch("src.spacehack.tutorial._show_step", side_effect=_fake_show):
            tutorial.tick(ctx, mode=mode)
        return fired

    def test_space_combat_intro_fires_once(self):
        ctx = self._tutorial_ctx()
        fired: list[str] = []

        def _fake_show(_, step_id):
            fired.append(step_id)
            tutorial.mark_step(ctx, step_id)

        with patch("src.spacehack.tutorial._show_step", side_effect=_fake_show):
            tutorial.maybe_space_combat_intro(ctx)
            tutorial.maybe_space_combat_intro(ctx)

        assert fired == ["space_combat_intro"]

    def test_loot_dropped_then_pickup_fallback(self):
        ctx = self._tutorial_ctx()
        tutorial.mark_step(ctx, "space_combat_intro")
        ctx.game_map = SimpleNamespace(entities=[self._loot_entity()])

        assert self._run(ctx, "space") == ["loot_dropped"]
        # Loot cleared (picked up or left the field) → the jump lesson
        # fires as the tick fallback.
        ctx.game_map = SimpleNamespace(entities=[])
        assert self._run(ctx, "space") == ["picked_up_loot"]

    def test_notify_pickup_fires_only_after_loot_cleared(self):
        ctx = self._tutorial_ctx()
        tutorial.mark_step(ctx, "space_combat_intro")
        ctx.game_map = SimpleNamespace(entities=[self._loot_entity()])
        fired: list[str] = []

        def _fake_show(_, step_id):
            fired.append(step_id)
            tutorial.mark_step(ctx, step_id)

        with patch("src.spacehack.tutorial._show_step", side_effect=_fake_show):
            # P pressed but loot remains → the beat waits for actual pickup.
            tutorial.notify_pickup(ctx)
            assert fired == []
            ctx.game_map = SimpleNamespace(entities=[])
            tutorial.notify_pickup(ctx)

        assert fired == ["picked_up_loot"]

    def test_signal_triggered_after_jump(self):
        ctx = self._tutorial_ctx()
        tutorial.mark_step(ctx, "space_combat_intro")
        tutorial.mark_step(ctx, "picked_up_loot")
        ctx.main_quest_progress = {"prologue_signal": "completed"}

        assert self._run(ctx, "space") == ["signal_triggered"]
        assert self._run(ctx, "space") == []

    def test_signal_triggered_gated_on_pickup_lesson(self):
        """The signal popup waits until the jump lesson was delivered."""
        ctx = self._tutorial_ctx()
        ctx.main_quest_progress = {"prologue_signal": "completed"}
        # No loot on the space map and no combat yet → nothing fires.
        assert self._run(ctx, "space") == []
        assert "signal_triggered" not in ctx.tutorial_steps


class TestMarsAndFinale:
    """Phase 4 — armory, Mars, ground-combat intro, and the finale."""

    @staticmethod
    def _tutorial_ctx() -> _StubCtx:
        ctx = _StubCtx()
        ctx.tutorial_mode = True
        # Every beat through the signal already delivered.
        for _s in ("intro", "first_move", "accepted_crimson",
                   "equipped_loadout", "launched", "space_combat_intro",
                   "loot_dropped", "picked_up_loot", "signal_triggered"):
            tutorial.mark_step(ctx, _s)
        ctx.main_quest_progress = {"prologue_signal": "completed"}
        return ctx

    def _run(self, ctx, mode: str):
        fired: list[str] = []

        def _fake_show(_, step_id):
            fired.append(step_id)
            tutorial.mark_step(ctx, step_id)

        with patch("src.spacehack.tutorial._show_step", side_effect=_fake_show):
            tutorial.tick(ctx, mode=mode)
        return fired

    def test_earth_armory_fires_on_earth_after_signal(self):
        ctx = self._tutorial_ctx()
        assert self._run(ctx, "city") == ["earth_armory"]
        # One shot only.
        assert self._run(ctx, "city") == []

    def test_earth_armory_gated_on_signal(self):
        """Early city frames (no signal yet) must not fire the popup."""
        ctx = self._tutorial_ctx()
        # Withdraw the signal beat: mark everything but the signal step.
        ctx.tutorial_steps.discard("signal_triggered")
        ctx.main_quest_progress = {}
        assert self._run(ctx, "city") == []
        assert "earth_armory" not in ctx.tutorial_steps
        # Signal arrives → the signal popup leads, then the armory popup.
        ctx.main_quest_progress = {"prologue_signal": "completed"}
        assert self._run(ctx, "city") == ["signal_triggered"]
        assert self._run(ctx, "city") == ["earth_armory"]

    def test_armed_ground_fires_after_armory_buy(self):
        ctx = self._tutorial_ctx()
        assert self._run(ctx, "city") == ["earth_armory"]
        ctx.equipped_ground_weapons = [GroundWeaponInstance("kinetic_rifle", 20)]
        assert self._run(ctx, "city") == ["armed_ground"]

    def test_armed_ground_gated_on_armory_beat(self):
        ctx = self._tutorial_ctx()
        ctx.equipped_ground_weapons = [GroundWeaponInstance("kinetic_rifle", 20)]  # bought early
        assert self._run(ctx, "city") == ["earth_armory"]  # armory first
        assert self._run(ctx, "city") == ["armed_ground"]

    def test_ground_combat_intro_fires_once(self):
        ctx = self._tutorial_ctx()
        tutorial.mark_step(ctx, "earth_armory")
        tutorial.mark_step(ctx, "armed_ground")
        fired: list[str] = []

        def _fake_show(_, step_id):
            fired.append(step_id)
            tutorial.mark_step(ctx, step_id)

        with patch("src.spacehack.tutorial._show_step", side_effect=_fake_show):
            tutorial.maybe_ground_combat_intro(ctx)
            tutorial.maybe_ground_combat_intro(ctx)

        assert fired == ["mars_ground_combat_intro"]

    def test_ground_combat_end_teaches_level_up_first(self):
        """After ground combat the player is levelled up and taught C."""
        ctx = self._tutorial_ctx()
        tutorial.mark_step(ctx, "earth_armory")
        tutorial.mark_step(ctx, "armed_ground")
        tutorial.mark_step(ctx, "mars_ground_combat_intro")
        fired: list[str] = []

        def _fake_show(_, step_id):
            fired.append(step_id)
            tutorial.mark_step(ctx, step_id)

        with patch("src.spacehack.tutorial._show_step", side_effect=_fake_show):
            tutorial.notify_ground_combat_ended(ctx)

        # The level-up lesson fires (not the finale), and the player is
        # guaranteed at least level 2 with skill points to spend.
        assert fired == ["level_up"]
        assert ctx.player_level >= 2
        assert ctx.player_skill_points > 0
        assert "finale" not in ctx.tutorial_steps
        assert ctx.tutorial_complete is False

    def test_finale_waits_for_skill_points_spent(self):
        """The finale fires only after the player spends their points."""
        ctx = self._tutorial_ctx()
        tutorial.mark_step(ctx, "earth_armory")
        tutorial.mark_step(ctx, "armed_ground")
        tutorial.mark_step(ctx, "mars_ground_combat_intro")
        fired: list[str] = []

        def _fake_show(_, step_id):
            fired.append(step_id)
            tutorial.mark_step(ctx, step_id)

        with patch("src.spacehack.tutorial._show_step", side_effect=_fake_show):
            tutorial.notify_ground_combat_ended(ctx)
            # Points still unspent → tick stays silent.
            tutorial.tick(ctx, mode="dungeon")
            assert fired == ["level_up"]

            # Player spends all points via the C character screen.
            ctx.player_skill_points = 0
            tutorial.tick(ctx, mode="dungeon")
            assert fired == ["level_up", "finale"]
            assert ctx.tutorial_complete is True

            # After completion every hook and tick must be silent.
            tutorial.notify_ground_combat_ended(ctx)
            tutorial.maybe_ground_combat_intro(ctx)
            tutorial.tick(ctx, mode="city")
            assert fired == ["level_up", "finale"]

    def test_finale_unlocks_mission_boards(self):
        """Finishing the tutorial lets boards refresh on their next visit."""
        ctx = self._tutorial_ctx()
        board = mission.ensure_board(ctx, "bar_owner", max_slots=3, planet_id="earth")
        board.last_refresh_month = ctx.time_month  # visited during tutorial
        tutorial.mark_step(ctx, "earth_armory")
        tutorial.mark_step(ctx, "armed_ground")
        tutorial.mark_step(ctx, "mars_ground_combat_intro")
        fired: list[str] = []

        def _fake_show(_, step_id):
            fired.append(step_id)
            tutorial.mark_step(ctx, step_id)

        with patch("src.spacehack.tutorial._show_step", side_effect=_fake_show):
            tutorial.notify_ground_combat_ended(ctx)
            ctx.player_skill_points = 0
            tutorial.tick(ctx, mode="dungeon")

        assert ctx.tutorial_complete is True
        assert fired == ["level_up", "finale"]
        assert board.last_refresh_month == 0

    def test_level_up_gated_on_ground_intro(self):
        """A stray combat resolution before the intro beat cannot level up."""
        ctx = self._tutorial_ctx()
        tutorial.notify_ground_combat_ended(ctx)
        assert "level_up" not in ctx.tutorial_steps
        assert "finale" not in ctx.tutorial_steps
        assert ctx.tutorial_complete is False

    def test_level_up_skips_xp_topup_when_already_leveled(self):
        """Players who levelled earlier keep their XP untouched."""
        ctx = self._tutorial_ctx()
        tutorial.mark_step(ctx, "earth_armory")
        tutorial.mark_step(ctx, "armed_ground")
        tutorial.mark_step(ctx, "mars_ground_combat_intro")
        ctx.player_level = 3
        ctx.player_xp = 500
        ctx.player_skill_points = 12

        fired: list[str] = []

        def _fake_show(_, step_id):
            fired.append(step_id)
            tutorial.mark_step(ctx, step_id)

        with patch("src.spacehack.tutorial._show_step", side_effect=_fake_show):
            tutorial.notify_ground_combat_ended(ctx)

        assert fired == ["level_up"]
        assert ctx.player_level == 3
        assert ctx.player_xp == 500
        assert ctx.player_skill_points == 12


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
        """A finished tutorial never fires popups (no graphics context needed)."""
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
