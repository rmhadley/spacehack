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
never a workaround target.

The generic ratchet spirit is: **code that belongs in module X goes in module
X** — even when X is oversized and touching it forces a refactor. The
mechanical incarnation we enforce here is *dataclass-field cohesion*: new
state on a type must be declared as a field in that type's own module, never
attached at runtime (``setattr`` / ``obj.attr = ...``) from a different file
while the owning module is left "untouched" to dodge the gate. Pre-existing
runtime-attached attributes are grandfathered (mirroring the size ratchet):
only a *new* undeclared attribute added by a changed file is blocking, and it
must be hoisted into the dataclass in the owning module in the same commit.
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


@dataclass(frozen=True)
class CohesionViolation:
    path: Path
    lineno: int
    attr: str
    owning_module: str

    def describe(self) -> str:
        return (
            f"{self.path}:{self.lineno} attaches undeclared runtime attribute "
            f"'{self.attr}' on a dataclass that lives in "
            f"{self.owning_module}"
        )


def _git(args: tuple[str, ...]) -> str:
    try:
        result = subprocess.run(
            ("git", *args), cwd=ROOT, capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"git {' '.join(args)} failed: {exc}") from exc
    return result.stdout


def _git_names(args: tuple[str, ...]) -> set[str]:
    return {line for line in _git(args).splitlines() if line}


def _git_numstat() -> dict[str, int]:
    """Return added-line counts for tracked files changed from HEAD."""
    additions: dict[str, int] = {}
    for line in _git(("diff", "--numstat", "HEAD", "--")).splitlines():
        fields = line.split("\t", 2)
        if len(fields) != 3 or fields[0] == "-":
            continue
        try:
            additions[fields[2]] = int(fields[0])
        except ValueError:
            continue
    return additions


def _restore_file(path: Path) -> str:
    """Return the committed (HEAD) content of a tracked source file."""
    rel = path.relative_to(ROOT).as_posix()
    return _git(("show", f"HEAD:{rel}"))


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


# ---------------------------------------------------------------------------
# Dataclass-field cohesion ("belongs in its own module") ratchet
# ---------------------------------------------------------------------------


def _is_dataclass(node: ast.ClassDef) -> bool:
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name) and dec.id == "dataclass":
            return True
        if isinstance(dec, ast.Attribute) and dec.attr == "dataclass":
            return True
    return False


def _dataclass_tables() -> tuple[dict[str, set[str]], dict[str, str]]:
    """Map dataclass class name -> declared fields AND -> owning module file.

    ``owning`` uses the source module path (without the ``.py`` suffix and
    without the ``spacehack.`` package prefix) so the challenge message can
    name the exact file the field must live in.
    """
    fields: dict[str, set[str]] = {}
    owning: dict[str, str] = {}
    for path in SOURCE_ROOT.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.ClassDef) and _is_dataclass(node)):
                continue
            fields[node.name] = {
                target.id
                for stmt in node.body
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
                for target in (stmt.target,)
            }
            owning[node.name] = (
                path.relative_to(SOURCE_ROOT).as_posix().replace(".py", "")
            )
    return fields, owning


def _annotation_class(node: ast.AST | None) -> str | None:
    """Resolve a type annotation's simple class name (unwrap Optionals)."""
    if node is None:
        return None
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        return _annotation_class(node.value)
    if isinstance(node, ast.BinOp):  # X | None
        return _annotation_class(node.left)
    return None


def _call_class(node: ast.AST | None) -> str | None:
    """Resolve a constructor call node's simple class name."""
    if node is None or not isinstance(node, ast.Call):
        return None
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _local_dataclass_types(tree, fields_by_class: dict[str, set[str]]) -> dict[str, str]:
    """Map local variable name -> dataclass class name within one file."""
    types: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            cls = _call_class(node.value)
            if cls and cls in fields_by_class:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        types[target.id] = cls
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            cls = _annotation_class(node.annotation)
            if cls and cls in fields_by_class:
                types[node.target.id] = cls
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for arg in node.args.args:
                cls = _annotation_class(arg.annotation)
                if cls and cls in fields_by_class:
                    types[arg.arg] = cls
    return types


def _undeclared_writes(
    tree,
    fields_by_class: dict[str, set[str]],
    types: dict[str, str],
    grandfathered: set[str],
) -> list[tuple[int, str, str]]:
    """Find undeclared runtime attribute writes on resolved dataclasses.

    Grandfathered attribute names (already attached at HEAD) are skipped.
    Returns ``(lineno, class_name, attr)`` triples.
    """
    found: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        # setattr(obj, "field", ...)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "setattr"
            and len(node.args) >= 2
            and isinstance(node.args[0], ast.Name)
            and isinstance(node.args[1], ast.Constant)
            and isinstance(node.args[1].value, str)
        ):
            obj = node.args[0].id
            attr = node.args[1].value
            cls = types.get(obj)
            if cls and attr not in fields_by_class[cls] and attr not in grandfathered:
                found.append((node.lineno, cls, attr))
        # obj.attr = ...
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                    obj = target.value.id
                    attr = target.attr
                    cls = types.get(obj)
                    if cls and attr not in fields_by_class[cls] and attr not in grandfathered:
                        found.append((target.lineno, cls, attr))
    return found


def _grandfathered_runtime_attrs(fields_by_class: dict[str, set[str]]) -> set[str]:
    """Collect runtime-attached dataclass attributes that already exist at HEAD."""
    grandfathered: set[str] = set()
    for path in SOURCE_ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT)
        try:
            tree = ast.parse(_restore_file(path), filename=str(path))
        except (OSError, SyntaxError, RuntimeError):
            continue
        types = _local_dataclass_types(tree, fields_by_class)
        for _lineno, _cls, attr in _undeclared_writes(
            tree, fields_by_class, types, set()
        ):
            grandfathered.add(attr)
    return grandfathered


def cohesion_violations_for_text(
    path: Path,
    text: str,
    fields_by_class: dict[str, set[str]],
    owning: dict[str, str],
    grandfathered: set[str],
) -> tuple[CohesionViolation, ...]:
    """Return undeclared runtime attribute writes a changed file adds."""
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        return ()
    types = _local_dataclass_types(tree, fields_by_class)
    violations = [
        CohesionViolation(path, lineno, attr, owning.get(cls, "?"))
        for lineno, cls, attr in _undeclared_writes(
            tree, fields_by_class, types, grandfathered
        )
    ]
    return tuple(violations)


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

    fields_by_class, owning = _dataclass_tables()
    grandfathered = _grandfathered_runtime_attrs(fields_by_class)
    cohesion = tuple(
        violation
        for path in sorted(changed, key=str)
        for violation in cohesion_violations_for_text(
            path, path.read_text(encoding="utf-8"),
            fields_by_class, owning, grandfathered,
        )
    )
    if cohesion:
        print("FAIL: new state on a type must be declared in that type's own module:")
        print(
            "\n".join(
                f"  {item.describe()}"
                + "\n    This attribute belongs in that dataclass. Declare it as a field"
                " in its owning module and do any refactor that module's size requires"
                " — in this same commit. Do not tack it on at runtime to keep the"
                " owning module 'untouched'."
                for item in cohesion
            )
        )
        return 1

    changed_label = f"{len(changed)} changed source module(s)" if changed else "no changed source modules"
    print(f"PASS: architecture check ({changed_label}; grandfathered backlog may remain).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
