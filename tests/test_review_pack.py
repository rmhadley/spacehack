"""Tests for tools/review_pack.py — the reviewer dispatch pack assembler."""

import subprocess
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "tools" / "review_pack.py"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *args],
        cwd=repo, check=True, capture_output=True,
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir(exist_ok=True)
    _git(repo, "init")
    (repo / "tracked.txt").write_text("tracked body\n")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-m", "initial")


def _run_pack(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(TOOL), "--out", str(repo / "pack.md"), *args],
        cwd=repo, capture_output=True, text=True,
    )


def test_untracked_files_are_embedded(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "new_module.py").write_text("NEW_FILE_BODY = 1\n")

    result = _run_pack(tmp_path)
    pack = (tmp_path / "pack.md").read_text()

    assert result.returncode == 0
    assert "untracked" in pack
    assert "NEW_FILE_BODY" in pack


def test_clean_tree_reports_nothing_to_review(tmp_path):
    _init_repo(tmp_path)

    result = _run_pack(tmp_path)

    assert result.returncode != 0
    assert "nothing to review" in result.stderr
    assert "clean tree" in result.stderr


def test_empty_range_diff_names_the_range(tmp_path):
    _init_repo(tmp_path)
    _git(tmp_path, "commit", "--allow-empty", "-m", "empty")

    result = _run_pack(tmp_path, "--range", "HEAD~1..HEAD")

    assert result.returncode != 0
    assert "nothing to review" in result.stderr
    assert "HEAD~1..HEAD" in result.stderr
    assert "clean tree" not in result.stderr


def test_missing_doc_path_fails_without_traceback(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "dirty.txt").write_text("dirty\n")

    result = _run_pack(tmp_path, "--doc", "/nonexistent_doc.md")

    assert result.returncode != 0
    assert "/nonexistent_doc.md" in result.stderr
    assert "Traceback" not in result.stderr
