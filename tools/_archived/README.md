# Archived tooling

One-shot AST migration scripts from earlier refactor epochs
(P3.6.x context-bundle migration, N1 modal extraction).

Kept for historical reference only. Superseded by the actual
commits that applied them; do not run.

Active tooling lives at `tools/` root. Currently:

- `smoke.py` -- pre-commit gate that imports all major modules
  and validates key entry points survived signature changes.