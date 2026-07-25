"""Hard audit: detect bare loose Name refs in migrated helper bodies.

After the P3.6.2 migration dropped :data:`game_map` / ``log`` / ``stats``
/ ``character_info`` / ``player_owned_ship`` / ``player_active_mission``
from selected helper signatures in :mod:`spacehack.__main__`
(replacing them with ``ctx`` + ``ctx.X`` access), surviving bare
references raise :class:`NameError` at the first runtime call to the
helper. Three such bugs surfaced post-migration
(``game_map.entities``, ``player_owned_ship.ship_id``, the
``log.add('You defeated ...')`` VICTORY line); this audit catches the
next one mechanically.

Strategy: walk the module AST. For each :attr:`SCAN`'d function, find
every :class:`ast.Name` whose ``id`` is in :attr:`LOOSE`. Skip cases
that are NOT runtime reads of a bare Name:

* The Name is the ``value`` of an :class:`ast.Attribute` (i.e. part of
  an Attribute chain like ``ctx.X`` or ``ctx.X.Y.Z``).
* The Name is an :class:`ast.arg` (function parameter).
* The Name is the ``arg`` of an :class:`ast.keyword` (kwarg name --
  e.g., ``stats=ctx.stats``: the first ``stats`` is the kwarg
  identifier, not a runtime reference).
* The Name is an :class:`ast.alias` (import alias).
* The Name is the target of an :class:`ast.Assign` /
  :class:`ast.AugAssign` / :class:`ast.AnnAssign`
  (LHS of an assignment -- a fresh local binding, not a read).

Anything else is reported. Using the AST instead of regex / tokenize
heuristics means: triple-quoted docstrings (correctly contained in
``ast.Expr.value`` if the docstring is a bare string statement, or
just regular string statements), f-string interpolations (handled
natively by ``ast.FormattedValue``), and arbitrarily-deep Attribute
chains are all delegated to Python's own parser.

Runs: ``python3 tools/audit_loose_refs.py`` from project root.
Exit 0 on clean, 1 on bugs (each printed as ``name:L:tok``).
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

# Tokens the migration removed from helper signatures. ``player`` is
# INTENTIONALLY not in this set -- it overlaps with the prefix
# variants ``player_owned_ship`` / ``player_active_mission`` and any
# other ``player_*`` identifiers, and dropping it avoids false
# positives on legitimate aliases like ``player_entity``.
LOOSE = frozenset({
    "game_map",
    "log",
    "stats",
    "character_info",
    "player_owned_ship",
    "player_active_mission",
})

# Audit scope: only helpers that have been FULLY migrated to ctx-based
# field access (P3.6.2.x chain). ``_launch_to_space`` and
# ``_return_to_city`` are pragma-deferred from P3.6.2.2 (deliberately
# still loose -- bodies take ``log``/``stats``/``character_info``/
# ``game_map`` etc. as parameters today). Once their migration lands,
# add them here so partial regression on the new shape gets caught.
SCAN = (
    "_handle_combat_encounter",
    "_jump_to_system",
    "_detect_combat_encounter",
    "_animate_jump",
)
DEFERRED = (
    "_launch_to_space",
    "_return_to_city",
)


def _parent_map(root):
    """Return ``{child: parent}`` for every node reachable from ``root``.

    Built via an explicit stack walk (not :func:`ast.walk`) so parent
    info is preserved. ``ast.iter_child_nodes`` is the only correct
    way to enumerate immediate children for both ``Expr`` and
    arbitrary statement bodies.
    """
    parent = {}
    stack = [root]
    while stack:
        node = stack.pop()
        for child in ast.iter_child_nodes(node):
            parent[child] = node
            stack.append(child)
    return parent


def _flatten_targets(target):
    """Yield every :class:`ast.Name` beneath an assignment target.

    Handles ``name = ...`` (single Name) and ``a, b = ...``
    (Tuple/List of Names) and ``a, *b = ...``
    (Tuple containing :class:`ast.Starred`).
    """
    if isinstance(target, (ast.Tuple, ast.List)):
        for elt in target.elts:
            yield from _flatten_targets(elt)
    elif isinstance(target, ast.Starred):
        yield from _flatten_targets(target.value)
    elif isinstance(target, ast.Name):
        yield target


def _is_skippable_name(name_node, parent_of):
    """True if ``name_node`` is a non-runtime bare ref (binding, alias, etc.)."""
    parent = parent_of.get(name_node)
    # No parent => a Module-level bare ref. That counts as a runtime
    # ref if it's loaded as -- but name only appears at expression
    # level if it's a Statement (Expr) or below. Treat as runtime.
    if parent is None:
        return False
    # Attribute access chain (e.g. ``ctx`` in ``ctx.log``).
    if isinstance(parent, ast.Attribute) and parent.value is name_node:
        return True
    # Function parameter.
    if isinstance(parent, ast.arg):
        return True
    # Import alias (covers both ``import X as Y`` and ``from X import Y``).
    if isinstance(parent, ast.alias):
        return True
    # Keyword arg name (e.g. ``stats`` in ``stats=ctx.stats``).
    if isinstance(parent, ast.keyword) and parent.arg is name_node:
        return True
    # Assignment targets (LHS) -- fresh local rebinding, not a read.
    if isinstance(parent, ast.Assign):
        for t in parent.targets:
            if any(tn is name_node for tn in _flatten_targets(t)):
                return True
    if isinstance(parent, ast.AnnAssign) and parent.target is name_node:
        return True
    if isinstance(parent, ast.AugAssign) and parent.target is name_node:
        return True
    # For ... in ... -- the in-target loop variable.
    if isinstance(parent, ast.For) and parent.target is name_node:
        return True
    return False


def audit(target_path=Path("src/spacehack/__main__.py")) -> int:
    """Run audit on ``target_path``. Returns 0 on clean, 1 on bugs."""
    if not target_path.exists():
        print(f"FAIL: {target_path} does not exist", file=sys.stderr)
        return 2
    try:
        text = target_path.read_text()
        tree = ast.parse(text, filename=str(target_path))
    except (SyntaxError, OSError) as exc:
        print(f"FAIL: cannot parse {target_path}: {exc}", file=sys.stderr)
        return 1
    parent_of = _parent_map(tree)
    bugs = []
    for func in ast.walk(tree):
        if not isinstance(func, ast.FunctionDef) or func.name not in SCAN:
            continue
        for sub in ast.walk(func):
            if isinstance(sub, ast.Name) and sub.id in LOOSE:
                if _is_skippable_name(sub, parent_of):
                    continue
                bugs.append((func.name, sub.lineno, sub.id))
    if bugs:
        print(f"FAIL: {len(bugs)} bare loose ref(s) in {target_path}:")
        for name, lineno, tok in bugs:
            print(f"  {name} L{lineno}: bare `{tok}`")
        return 1
    print(f"OK: zero bare loose refs in {', '.join(SCAN)}")
    return 0


if __name__ == "__main__":
    sys.exit(audit())
