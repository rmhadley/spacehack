---
description: Prime a fresh session to implement the next planned phase of a design doc by following its implementation brief
argument-hint: [doc-number[.phase]] — e.g. `40` or `40.3`; bare lists open docs
---
You are the implementation session for a design-doc phase. Work in this order:

1. Read `/workspace/knowledge.md` (repo playbook and contracts) and `/workspace/docs/design/knowledge.md` (doc workflow reference). They govern everything below; this command only aims you at the right files.
2. Target selection from the argument `$ARGUMENTS`:
   - `<n>.<p>` (e.g. `40.3`) — the doc in `docs/design/in_progress/` whose filename starts `<n>_`, phase `<p>` from its Phases list.
   - `<n>` — that doc, the FIRST unchecked `[ ]` phase in its Phases list (the list is the build queue, top to bottom).
   - No argument — list every doc in `in_progress/` with its next unchecked phase and whether that phase has a brief, then STOP and ask which to run.
3. Read the target doc IN FULL. If the target phase has no Implementation brief, STOP: propose the brief (scope, build order, binding rulings, tests, stop point, playtest checkpoint) to the user — never code an unbriefed phase.
4. Execute per knowledge.md's mandatory workflow: pre-implementation audit section in the doc BEFORE any code → implement → `make check` before every commit → reviewer subagent (REVIEW mode, dispatch via `make review-pack`) before each code commit → atomic commits with prefixed messages → tick the doc's checkboxes as steps land.
5. At the brief's playtest checkpoint, hand the user a numbered in-game checklist (dev-shortcut setup, expected result per item) and STOP. Do not start the next phase; if the brief says the next phase's brief is written at this checkpoint, draft it as part of the checkpoint handoff.
