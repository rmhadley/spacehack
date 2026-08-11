#!/usr/bin/env python3
"""Reject new tcod references while the project migrates away from tcod.

The repository still contains a checked-in inventory of existing tcod usage.
The normal command compares the current protected-file inventory against that
baseline and fails only when references are added. Use ``--write-baseline``
only when an approved migration intentionally changes the inventory.

Run from the project root:

    python3 tools/tcod_freeze.py
    python3 tools/tcod_freeze.py --write-baseline
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys


_ROOT = Path(__file__).resolve().parent.parent
_BASELINE = Path("tools/tcod_freeze_baseline.json")

# These are the production, test, dependency, packaging, and CI surfaces
# whose tcod inventory must not grow. Design/history docs and explicitly
# historical visual/codemod tools are intentionally outside this gate.
_SCAN_PATHS = (
    Path("src"),
    Path("tests"),
    Path("tools"),
    Path("README.md"),
    Path("knowledge.md"),
    Path("run.py"),
    Path("run_spacehack"),
    Path("run_spacehack.bat"),
    Path("requirements.txt"),
    Path("pyproject.toml"),
    Path("Makefile"),
    Path("spacehack.spec"),
    Path(".github"),
    Path("packaging"),
)
_EXCLUDED_PATHS = {
    Path("tools/tcod_freeze.py"),
    Path("tools/tcod_freeze_baseline.json"),
    Path("tools/text_render_spike.py"),
}
_EXCLUDED_PREFIXES = (
    Path("tools/_archived"),
    Path("packaging/homebrew-tap/.git"),
)
# Capture the most specific tcod API expression available. Keeping the full
# dotted expression prevents a new `tcod.event` use from hiding behind an old
# `tcod.console` count in the same file. Standalone `tcod` references remain
# inventory items for prose, dependency names, and generic imports.
_TCOD_TOKEN = re.compile(
    r"(?<![A-Za-z0-9_])tcod(?:\.[A-Za-z_][A-Za-z0-9_]*)+|"
    r"(?<![A-Za-z0-9_])tcod(?![A-Za-z0-9_])",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Reference:
    """One tcod token occurrence in a protected file."""

    path: str
    token: str
    line: int
    source: str = ""

    @property
    def key(self) -> tuple[str, str, str]:
        """Return a stable identity including the source-line context."""
        return self.path, self.token.lower(), self.source.strip()


def _is_excluded(path: Path) -> bool:
    """Return whether a repository-relative path is outside the freeze."""
    if path in _EXCLUDED_PATHS:
        return True
    return any(path == prefix or prefix in path.parents for prefix in _EXCLUDED_PREFIXES)


def _iter_files(root: Path) -> tuple[Path, ...]:
    """Return readable files under the protected scan paths."""
    files: list[Path] = []
    for relative in _SCAN_PATHS:
        candidate = root / relative
        if candidate.is_file():
            if not _is_excluded(relative):
                files.append(relative)
            continue
        if not candidate.is_dir():
            continue
        files.extend(
            path.relative_to(root)
            for path in candidate.rglob("*")
            if path.is_file()
            and not _is_excluded(path.relative_to(root))
        )
    return tuple(sorted(set(files)))


def find_references(root: Path = _ROOT) -> tuple[Reference, ...]:
    """Find all tcod token occurrences in protected repository files."""
    references: list[Reference] = []
    for relative in _iter_files(root):
        try:
            lines = (root / relative).read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        path = relative.as_posix()
        for line_number, line in enumerate(lines, start=1):
            references.extend(
                Reference(
                    path=path,
                    token=match.group(0).lower(),
                    line=line_number,
                    source=line,
                )
                for match in _TCOD_TOKEN.finditer(line)
            )
        if relative.suffix == ".py":
            try:
                tree = ast.parse("\n".join(lines), filename=path)
            except SyntaxError:
                tree = None
            if tree is not None:
                references.extend(
                    Reference(
                        path=path,
                        token=f"{node.module}.{alias.name}",
                        line=int(node.lineno),
                        source=lines[node.lineno - 1],
                    )
                    for node in ast.walk(tree)
                    if isinstance(node, ast.ImportFrom)
                    and node.module is not None
                    and (
                        node.module == "tcod"
                        or node.module.startswith("tcod.")
                    )
                    for alias in node.names
                    if alias.name != "*"
                )
    return tuple(references)


def _counts(references: tuple[Reference, ...] | list[Reference]) -> Counter[tuple[str, str, str]]:
    """Count exact references by file and expression for stable diffs."""
    return Counter(reference.key for reference in references)


def _read_baseline(path: Path) -> tuple[Reference, ...]:
    """Read the checked-in baseline reference inventory."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw_references = payload["references"]
        if not isinstance(raw_references, list):
            raise TypeError("references must be a list")
        parsed: list[Reference] = []
        for item in raw_references:
            if not isinstance(item, dict):
                raise TypeError("reference entries must be objects")
            path_name = item["path"]
            token = item["token"]
            source = item.get("source", "")
            if (
                not isinstance(path_name, str)
                or not isinstance(token, str)
                or not isinstance(source, str)
            ):
                raise TypeError("reference path, token, and source must be strings")
            parsed.append(
                Reference(path=path_name, token=token.lower(), line=0, source=source)
            )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid tcod freeze baseline: {path}") from exc
    return tuple(parsed)


def _write_baseline(path: Path, references: tuple[Reference, ...]) -> None:
    """Write a stable baseline containing source-aware identities."""
    counts = _counts(references)
    payload = {
        "version": 1,
        "description": "Approved tcod reference inventory; new occurrences fail the freeze audit.",
        "references": [
            {"path": path_name, "token": token, "source": source}
            for path_name, token, source in sorted(counts)
            for _ in range(counts[(path_name, token, source)])
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _format_changes(
    current: tuple[Reference, ...],
    baseline: tuple[Reference, ...],
) -> tuple[list[str], list[str]]:
    """Return added and removed reference descriptions."""
    current_counts = _counts(current)
    baseline_counts = _counts(baseline)
    added: list[str] = []
    removed: list[str] = []
    for key, count in sorted((current_counts - baseline_counts).items()):
        path, token, _source = key
        lines = [str(reference.line) for reference in current if reference.key == key]
        added.append(f"{path}:{','.join(lines)} added {token} x{count}")
    for key, count in sorted((baseline_counts - current_counts).items()):
        path, token, _source = key
        removed.append(f"{path} removed {token} x{count}")
    return added, removed


def audit(root: Path = _ROOT, baseline_path: Path = _BASELINE) -> int:
    """Compare the current protected inventory against the baseline."""
    try:
        baseline = _read_baseline(root / baseline_path)
    except ValueError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    current = find_references(root)
    added, removed = _format_changes(current, baseline)
    if added:
        print("FAIL: tcod freeze detected new protected-file references:", file=sys.stderr)
        for change in added:
            print(f"  - {change}", file=sys.stderr)
        if removed:
            print("Approved references also removed; update the baseline after review.", file=sys.stderr)
        return 1
    print(
        f"PASS: tcod freeze OK ({len(current)} protected references; "
        f"{len(removed)} approved references removed)."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the tcod freeze CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="write the current approved inventory instead of auditing it",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=_BASELINE,
        help="repository-relative baseline path",
    )
    args = parser.parse_args(argv)
    references = find_references(_ROOT)
    if args.write_baseline:
        _write_baseline(_ROOT / args.baseline, references)
        print(f"Wrote tcod freeze baseline: {args.baseline} ({len(references)} references).")
        return 0
    return audit(_ROOT, args.baseline)


if __name__ == "__main__":
    raise SystemExit(main())
