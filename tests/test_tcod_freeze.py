"""Tests for the temporary tcod reference freeze audit."""

from pathlib import Path

from tools import tcod_freeze


def test_format_changes_reports_only_new_reference_counts() -> None:
    """New occurrences fail independently of their source line numbers."""
    baseline = (tcod_freeze.Reference("src/example.py", "tcod", 1),)
    current = (
        tcod_freeze.Reference("src/example.py", "tcod", 8),
        tcod_freeze.Reference("src/example.py", "tcod", 12),
    )

    added, removed = tcod_freeze._format_changes(current, baseline)

    assert added == ["src/example.py:8,12 added tcod x1"]
    assert removed == []


def test_format_changes_detects_api_replacement_with_same_count() -> None:
    """Changing tcod APIs cannot hide behind an unchanged occurrence count."""
    baseline = (tcod_freeze.Reference("src/example.py", "tcod.console", 1),)
    current = (tcod_freeze.Reference("src/example.py", "tcod.event", 8),)

    added, removed = tcod_freeze._format_changes(current, baseline)

    assert added == ["src/example.py:8 added tcod.event x1"]
    assert removed == ["src/example.py removed tcod.console x1"]


def test_find_references_tracks_from_tcod_import_names(tmp_path: Path) -> None:
    """Changing imported tcod modules changes the protected inventory."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "live.py").write_text(
        "from tcod import console, event\n", encoding="utf-8",
    )

    references = tcod_freeze.find_references(tmp_path)

    assert {
        (reference.path, reference.token) for reference in references
    } == {
        ("src/live.py", "tcod"),
        ("src/live.py", "tcod.console"),
        ("src/live.py", "tcod.event"),
    }


def test_find_references_tracks_multiline_tcod_imports(tmp_path: Path) -> None:
    """Parenthesized imports remain visible to the AST-backed inventory."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "live.py").write_text(
        "from tcod import (\n    console,\n    event,\n)\n", encoding="utf-8",
    )

    references = tcod_freeze.find_references(tmp_path)

    assert ("src/live.py", "tcod.console") in {
        (reference.path, reference.token) for reference in references
    }
    assert ("src/live.py", "tcod.event") in {
        (reference.path, reference.token) for reference in references
    }


def test_find_references_tracks_nested_tcod_imports(tmp_path: Path) -> None:
    """Nested module imports include the imported symbol in the inventory."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "live.py").write_text(
        "from tcod.console import Console\n", encoding="utf-8",
    )

    references = tcod_freeze.find_references(tmp_path)

    assert ("src/live.py", "tcod.console.Console") in {
        (reference.path, reference.token) for reference in references
    }


def test_find_references_includes_knowledge_policy(tmp_path: Path) -> None:
    """The policy file itself remains inside the protected inventory."""
    (tmp_path / "knowledge.md").write_text(
        "The tcod.console policy is frozen.\n", encoding="utf-8",
    )

    references = tcod_freeze.find_references(tmp_path)

    assert [
        (reference.path, reference.token) for reference in references
    ] == [
        ("knowledge.md", "tcod.console"),
    ]


def test_find_references_excludes_historical_tooling(tmp_path: Path) -> None:
    """Archived codemods and the visual spike do not expand the freeze."""
    (tmp_path / "src").mkdir()
    (tmp_path / "tools" / "_archived").mkdir(parents=True)
    (tmp_path / "tools").mkdir(exist_ok=True)
    (tmp_path / "src" / "live.py").write_text("import tcod\n", encoding="utf-8")
    (tmp_path / "tools" / "_archived" / "old.py").write_text(
        "import tcod\n", encoding="utf-8",
    )
    (tmp_path / "tools" / "text_render_spike.py").write_text(
        "import tcod\n", encoding="utf-8",
    )

    references = tcod_freeze.find_references(tmp_path)

    assert {(reference.path, reference.token) for reference in references} == {
        ("src/live.py", "tcod"),
    }


def test_audit_rejects_malformed_baseline(tmp_path: Path) -> None:
    """Malformed baseline data fails cleanly instead of raising."""
    (tmp_path / "baseline.json").write_text(
        '{"references": [{"path": "src/live.py"}]}', encoding="utf-8",
    )

    assert tcod_freeze.audit(tmp_path, Path("baseline.json")) == 1


def test_audit_passes_when_only_approved_references_remain(tmp_path: Path) -> None:
    """The audit accepts an unchanged inventory and reports success."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "live.py").write_text(
        "# existing tcod reference\n", encoding="utf-8",
    )
    baseline_path = Path("baseline.json")
    references = tcod_freeze.find_references(tmp_path)
    tcod_freeze._write_baseline(tmp_path / baseline_path, references)

    assert tcod_freeze.audit(tmp_path, baseline_path) == 0
