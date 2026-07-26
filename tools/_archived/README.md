# Archived tooling

One-shot AST migration scripts from earlier refactor epochs
(P3.6.x context-bundle migration, N1 modal extraction).

Kept for historical reference only. Superseded by the actual
commits that applied them; do not run.

Active tooling lives at `tools/` root. Currently:

- `audit_loose_refs.py` -- pre-commit gate that walks the AST
  of `src/spacehack/__main__.py` and `src/spacehack/combat.py`
  for bare LOOSE-token references in SCAN'd function bodies.
