#!/usr/bin/env python3
"""Enforce source-size rules for changed application modules.

Existing oversized modules are reported but grandfathered until touched. A
changed source module with added code must be at most 1000 lines and contain no
function over 40 lines. Deletion-only cleanups do not add architecture debt and
remain grandfathered. This is intentionally a local gate; CI is not required.

The gate is a forcing function, not a hurdle to route around: touching an
oversized module makes its pre-existing debt blocking on purpose, so that
change must include the refactor that brings the module back under the limit
(split the module into cohesive siblings, split oversized functions). It is
never a workaround target — do not keep a module untouched to dodge the gate,
move code somewhere it doesn't belong, or bury oversized logic to hide the
line count.
"""
from __future__ import annotations

import ast
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_ROOT = ROOT / "src" / "spacehack"
MODULE_LIMIT = 1000
FUNCTION_LIMIT = 40


@dataclass(frozen=True)
class Violation:
    path: Path
    kind: str
    actual: int
    limit: int
    name: str = ""

    def describe(self) -> str:
        subject = f"{self.kind} {self.name}".strip()
        return f"{self.path}: {subject} is {self.actual} lines (limit {self.limit})"


def _git_names(args: tuple[str, ...]) -> set[str]:
    try:
        result = subprocess.run(
            ("git", *args), cwd=ROOT, capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"git {' '.join(args)} failed: {exc}") from exc
    return {line for line in result.stdout.splitlines() if line}


def _git_numstat() -> dict[str, int]:
    """Return added-line counts for tracked files changed from HEAD."""
    try:
        result = subprocess.run(
            ("git", "diff", "--numstat", "HEAD", "--"),
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"git diff --numstat HEAD failed: {exc}") from exc
    additions: dict[str, int] = {}
    for line in result.stdout.splitlines():
        fields = line.split("\t", 2)
        if len(fields) != 3 or fields[0] == "-":
            continue
        try:
            additions[fields[2]] = int(fields[0])
        except ValueError:
            continue
    return additions


def _changed_source_paths() -> tuple[Path, ...]:
    changed = _git_names(("diff", "--name-only", "HEAD", "--"))
    untracked = _git_names(("ls-files", "--others", "--exclude-standard"))
    changed.update(untracked)
    additions = _git_numstat()
    paths = {
        ROOT / name
        for name in changed
        if name.startswith("src/spacehack/")
        and name.endswith(".py")
        and (name in untracked or additions.get(name, 0) > 0)
    }
    return tuple(sorted((path for path in paths if path.is_file()), key=str))


def violations_for_text(path: Path, text: str) -> tuple[Violation, ...]:
    tree = ast.parse(text, filename=str(path))
    violations: list[Violation] = []
    line_count = len(text.splitlines())
    if line_count > MODULE_LIMIT:
        violations.append(Violation(path, "module", line_count, MODULE_LIMIT))
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        length = node.end_lineno - node.lineno + 1
        if length > FUNCTION_LIMIT:
            violations.append(Violation(path, "function", length, FUNCTION_LIMIT, node.name))
    return tuple(violations)


def _violations(path: Path) -> tuple[Violation, ...]:
    return violations_for_text(path, path.read_text(encoding="utf-8"))


def _format_backlog(violations: tuple[Violation, ...]) -> list[str]:
    grouped: dict[Path, list[Violation]] = {}
    for violation in violations:
        grouped.setdefault(violation.path, []).append(violation)
    lines = []
    for path, items in sorted(grouped.items(), key=lambda item: str(item[0])):
        modules = [item for item in items if item.kind == "module"]
        functions = [item for item in items if item.kind == "function"]
        detail = []
        if modules:
            detail.append(f"module {modules[0].actual}/{MODULE_LIMIT}")
        if functions:
            detail.append(f"{len(functions)} function(s) > {FUNCTION_LIMIT} lines")
        lines.append(f"  {path.relative_to(ROOT)}: {', '.join(detail)}")
    return lines


def main() -> int:
    try:
        changed = set(_changed_source_paths())
    except RuntimeError as exc:
        print(f"FAIL: architecture check could not inspect Git state: {exc}")
        return 1
    all_violations = tuple(
        violation
        for path in SOURCE_ROOT.rglob("*.py")
        for violation in _violations(path)
    )
    backlog = tuple(item for item in all_violations if item.path not in changed)
    if backlog:
        print("INFO: untouched architecture violations are grandfathered:")
        print("\n".join(_format_backlog(backlog)))
    blocking = tuple(item for item in all_violations if item.path in changed)
    if blocking:
        print("FAIL: changed source modules must be brought within architecture limits:")
        print("\n".join(f"  {item.describe()}" for item in blocking))
        return 1
    changed_label = f"{len(changed)} changed source module(s)" if changed else "no changed source modules"
    print(f"PASS: architecture check ({changed_label}; grandfathered backlog may remain).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
