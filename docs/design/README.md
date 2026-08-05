# Design doc workflow — reference

Design docs live in `docs/design/` and are the contract between the user and
the agent for building complex features. This README holds the **reference**
material that changes rarely: the directory layout, creating a new doc, and
lifecycle moves.

The **mandatory process rules** — pre-implementation audit, iterating,
self-audit pass, and the code-reviewer checklist — live in `knowledge.md`
(the session knowledge contract) because they fire on almost every session.

## Directory structure

```
docs/design/
  <architectural-reference>.md         ─ reference docs (already implemented)
  complete/                            ─ implemented design docs
    <feature>.md
  in_progress/                          ─ doc currently being worked on
    <feature>.md
```

## Creating a design doc

When the user says "let's design X", the agent MUST first check if a design doc already exists for X (in any of the three directories). If none exists:

1. Create `docs/design/in_progress/<feature>.md`
2. Structure it with: overview, philosophy alignment table, data model, domain changes, phased implementation plan with checkboxes, acceptance criteria, open questions
3. Include a **PLAYTEST** section in each phase with concrete steps the user can follow
4. **Do NOT start implementation yet** — present the doc to the user for feedback first.

## Moving docs through the lifecycle

1. **`in_progress/`** — Doc is being actively worked on. Playtests are happening. Checkboxes are being checked.
2. **`complete/`** — ALL checkboxes checked, final playtest passed, no open questions remain.
3. **`docs/design/` (root, reference)** — Architectural docs that describe already-implemented systems (not feature-iteration docs). These live in the root of `docs/design/` permanently as reference material.

When a phase completes with no next phase to start, ask the user: "Move this to complete?" before committing.
