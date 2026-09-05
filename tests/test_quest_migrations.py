"""The declared save-migration table (doc 33 Phase 1).

Renames and retirements are data in ``data/main_quest/migrations.py``
applied by :func:`main_quest.apply_step_migrations` — replacing the
bespoke per-campaign repair functions. Quest catalogs keep their
current ids; the table is purely the save/load contract.
"""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack import main_quest
from src.spacehack.data.main_quest.migrations import RENAMES, RETIRED
from src.spacehack.message_log import MessageLog


def _ctx(progress, *, chain="merchants"):
    return SimpleNamespace(
        main_quest_chain=chain,
        main_quest_progress=dict(progress),
        main_quest_gate={},
        player_active_missions=[],
        log=MessageLog(capacity=6),
    )


def test_every_migration_target_exists_in_the_catalog():
    """The table must never point at an id the catalog dropped."""
    from src.spacehack.data.main_quest import find_main_quest_step

    for targets in RENAMES.values():
        for target in ((targets,) if isinstance(targets, str) else targets):
            find_main_quest_step(target)  # raises KeyError if gone
    for implies in RETIRED.values():
        for template in implies:
            if "{chain}" not in template:
                find_main_quest_step(template)


def test_rename_moves_status_and_gate():
    ctx = _ctx({"mer_q4_calibrate": "completed", "mer_q5_cutter": "available"})
    ctx.main_quest_gate["mer_q5_cutter"] = (9, 9, 9999)

    main_quest.apply_step_migrations(ctx)

    assert ctx.main_quest_progress["mer_q6_survey"] == "completed"
    assert ctx.main_quest_progress["mer_q7_cutter"] == "available"
    assert ctx.main_quest_gate == {"mer_q7_cutter": (9, 9, 9999)}
    assert "mer_q4_calibrate" not in ctx.main_quest_progress


def test_combined_step_completion_completes_every_target():
    """mer_q5_calibration covered alloy + survey: a completed save has
    both done (the 6->7 split's chain-never-strands reconciliation)."""
    ctx = _ctx({"mer_q5_calibration": "completed"})

    main_quest.apply_step_migrations(ctx)

    assert ctx.main_quest_progress["mer_q5_alloy"] == "completed"
    assert ctx.main_quest_progress["mer_q6_survey"] == "completed"


def test_combined_step_in_progress_maps_onto_the_first_target_only():
    ctx = _ctx({"mer_q5_calibration": "active"})

    main_quest.apply_step_migrations(ctx)

    assert ctx.main_quest_progress["mer_q5_alloy"] == "active"
    assert "mer_q6_survey" not in ctx.main_quest_progress


def test_retired_research_steps_drop_with_their_implication():
    """A pre-epilogue save that reached the first translation counts as
    a completed delivery; anything short keeps the reward live."""
    ctx = _ctx(
        {"research_alpha": "completed", "research_alpha_report": "completed"},
        chain="militia",
    )

    main_quest.apply_step_migrations(ctx)

    assert "research_alpha" not in ctx.main_quest_progress
    assert ctx.main_quest_progress["epilogue_reward_militia"] == "completed"

    partial = _ctx({"research_alpha": "available"}, chain="bar")
    main_quest.apply_step_migrations(partial)
    assert "research_alpha" not in partial.main_quest_progress
    assert "epilogue_reward_bar" not in partial.main_quest_progress


def test_migrations_are_idempotent():
    ctx = _ctx({"mer_q5_calibration": "completed", "research_alpha_report": "completed"},
               chain="lab")
    main_quest.apply_step_migrations(ctx)
    snapshot = dict(ctx.main_quest_progress)
    main_quest.apply_step_migrations(ctx)
    assert ctx.main_quest_progress == snapshot


def test_quest_lint_catches_injected_faults(tmp_path, monkeypatch):
    """The linter must actually catch things: corrupt a copy of the
    catalog's overlay with an orphaned key and a market-good crate, and
    expect both flags (the city-audit lesson: a trusted diagnostic
    proves itself on faults, not just on a clean repo)."""
    import tools.quest_lint as lint

    clean = dict(lint.overlay())
    clean["step.not_a_real_step.title"] = "orphan"
    monkeypatch.setattr(lint, "overlay", lambda: clean)

    errors: list[str] = []
    lint._check_orphaned_text(errors)
    assert any("not_a_real_step" in e for e in errors), errors

    # market good in a quest crate (fuel cells are trade goods)
    from src.spacehack.data.main_quest import find_main_quest_step
    smuggle = find_main_quest_step("bar_q5_charged")
    monkeypatch.setattr(
        lint, "list_main_quest_steps",
        lambda: [
            s if s.id != "bar_q5_charged"
            else type(s)(**{**vars(s), "smuggle_good_id": "fuel_cells"})
            for s in lint.__dict__.get("_STEPS_CACHE", []) or [smuggle]
        ],
    )
    errors.clear()
    lint._check_quest_cargo(errors)
    assert any("fuel_cells" in e for e in errors), errors
