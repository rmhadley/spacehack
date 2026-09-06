---
description: Interactive ruling/refinement loop over a design doc — record rulings as SETTLED sections, draft each settled phase's implementation brief; never writes code
argument-hint: [doc-number] — e.g. `41`; bare lists open docs with open questions and unbriefed phases
---
You are the design-refinement session for a design doc — the converse of /implement-phase: this session produces the briefs that command requires. Work in this order:

1. Read `/workspace/knowledge.md` (repo playbook and contracts) and `/workspace/docs/design/knowledge.md` (doc workflow reference). They govern everything below; this command only aims you at the right files.
2. Target selection from the argument `$ARGUMENTS`:
   - `<n>` — the doc in `docs/design/in_progress/` whose filename starts `<n>_`.
   - No argument — list every doc in `in_progress/` with its open questions and which phases lack an Implementation brief, then STOP and ask which to work.
   - Named doc does not exist (a new design): create it per the reference's "Creating a design doc" — full structure, a PLAYTEST section per phase, open questions — present it for review, and rule nothing until the user responds.
3. Read the target doc IN FULL. Open with a three-line status: settled rulings, open questions, phases and their brief state. No more reporting than that — `/design-brief` is the reporting command.
4. Ruling loop (interactive — the heart of the session): present the open questions and unmade decisions for the phase at hand. Specific questions; batch them only when independent; one at a time when the next question depends on the previous answer. Record each settled batch as a dated SETTLED section in the doc (matching the doc's existing ones), use the user's wording verbatim for anything they dictate, and when a ruling invalidates an earlier section, rewrite that section in the same pass — the doc is the contract and must never contradict itself.
5. Briefing: when a phase's questions are settled, draft its Implementation brief in the house shape — scope (exact files/hook points), build order, binding rulings, required tests, stop point (what NOT to start), playtest checkpoint (numbered in-game checklist items) — and propose it for approval. Amending an existing brief (rulings moved, or one drafted at a build checkpoint) is the same act. A phase is done being refined only when its brief is approved; `/implement-phase` refuses to code without one.
6. Commit doc changes at natural stopping points (`docs: doc <n> — ...`). Docs-only commits need no reviewer subagent; for a contested design section, offer an ADVISE-mode reviewer dispatch instead of arguing your own view.
7. Hard stops: never write code, never tick implementation checkboxes, never start another doc unprompted. When the next phase carries an approved brief, end with the handoff: ready for `/implement-phase <n>.<p>`.
