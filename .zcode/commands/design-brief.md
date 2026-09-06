---
description: Report a design doc's phase checklist, per-phase summaries, and open questions
argument-hint: <doc-number> — e.g. `40`; bare lists available docs
---
Report-only task: never edit any file.

1. Locate the doc from the argument `$ARGUMENTS`: `<n>` matches the file starting `<n>_` in `docs/design/in_progress/`; if not there, search the rest of `docs/design/` (root reference docs and `complete/`). No argument: list every doc across `docs/design/` (all three locations) by number and title, then stop.
2. Read the doc IN FULL.
3. Output, in this shape and nothing more:
   - **Doc** — number, title, location, and the status line from its header if present.
   - **Phases** — one entry per phase in the doc's Phases list: the literal checkbox state (`[x]` done / `[ ]` open), the phase name, and a 1–3 sentence summary of what it does, strictly from the doc's own text — never invent scope.
   - **Open questions** — every question the doc marks open, parked, or unruled, each with the section it lives in; if none, say "No open questions."
   - **Next actionable phase** — the first unchecked phase and whether it carries an Implementation brief (i.e. whether `/implement-phase <n>.<p>` can run it now).
Keep the whole report under one screen; do not restate doc sections beyond the summaries.
