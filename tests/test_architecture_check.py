from pathlib import Path

from tools import architecture_check
from tools.architecture_check import violations_for_text


_THIS_FILE = Path(__file__)


def test_module_limit_violation_is_reported():
    text = "\n".join(["value = 1"] * 1001)

    violations = violations_for_text(_THIS_FILE, text)

    assert [(item.kind, item.actual, item.limit) for item in violations] == [
        ("module", 1001, 1000),
    ]


def test_function_limit_violation_is_reported():
    text = "def too_long():\n" + "\n".join("    pass" for _ in range(40))

    violations = violations_for_text(_THIS_FILE, text)

    assert [(item.kind, item.name, item.actual, item.limit) for item in violations] == [
        ("function", "too_long", 41, 40),
    ]


def test_module_and_function_limits_are_inclusive():
    text = "def exactly_forty():\n" + "\n".join("    pass" for _ in range(39))

    violations = violations_for_text(_THIS_FILE, text)

    assert violations == ()


def test_changed_source_paths_include_staged_and_untracked_files(monkeypatch, tmp_path):
    root = tmp_path
    source = root / "src" / "spacehack"
    source.mkdir(parents=True)
    staged = source / "staged.py"
    untracked = source / "untracked.py"
    staged.write_text("value = 1\n")
    untracked.write_text("value = 2\n")

    def fake_git_names(args):
        if args[:2] == ("diff", "--name-only"):
            return {"src/spacehack/staged.py"}
        return {"src/spacehack/untracked.py"}

    monkeypatch.setattr(architecture_check, "ROOT", root)
    monkeypatch.setattr(architecture_check, "_git_names", fake_git_names)

    assert architecture_check._changed_source_paths() == (staged, untracked)


def test_main_grandfathers_untouched_violations(monkeypatch, tmp_path, capsys):
    root = tmp_path
    source = root / "src" / "spacehack"
    source.mkdir(parents=True)
    oversized = source / "old.py"
    oversized.write_text("value = 1\n" * 1001)

    monkeypatch.setattr(architecture_check, "ROOT", root)
    monkeypatch.setattr(architecture_check, "SOURCE_ROOT", source)
    monkeypatch.setattr(architecture_check, "_changed_source_paths", lambda: ())

    assert architecture_check.main() == 0
    output = capsys.readouterr().out
    assert "untouched architecture violations are grandfathered" in output
    assert "old.py" in output


def test_main_reports_git_state_failure(monkeypatch, capsys):
    def fail_git():
        raise RuntimeError("git unavailable")

    monkeypatch.setattr(architecture_check, "_changed_source_paths", fail_git)

    assert architecture_check.main() == 1
    assert "FAIL: architecture check could not inspect Git state" in capsys.readouterr().out


def test_main_blocks_a_changed_oversized_module(monkeypatch, tmp_path, capsys):
    root = tmp_path
    source = root / "src" / "spacehack"
    source.mkdir(parents=True)
    oversized = source / "changed.py"
    oversized.write_text("value = 1\n" * 1001)

    monkeypatch.setattr(architecture_check, "ROOT", root)
    monkeypatch.setattr(architecture_check, "SOURCE_ROOT", source)
    monkeypatch.setattr(architecture_check, "_changed_source_paths", lambda: (oversized,))

    assert architecture_check.main() == 1
    output = capsys.readouterr().out
    assert "changed source modules must be brought within architecture limits" in output
    assert "changed.py" in output
