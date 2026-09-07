# Design doc workflow — reference

Design docs live in `docs/design/` and are the contract between the user and
the agent for building complex features. This README holds the **reference**
material that changes rarely: the directory layout, creating a new doc, and
lifecycle moves.

The **mandatory process rules** — pre-implementation audit, iterating,
and the self-audit pass — live in `knowledge.md`
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

## Implementation briefs and `/implement-phase`

A phase is **buildable only when its section carries an
Implementation brief**: scope (exact files/hook points), build order,
binding rulings, required tests, the stop point (what NOT to start),
and the playtest checkpoint. Write the brief during review/ruling —
before the build session — so the build session's prompt is just the
command:

    /implement-phase 40.3      # named doc + phase
    /implement-phase 40        # that doc's first unchecked phase

`.zcode/commands/implement-phase.md` primes a fresh session: read
`knowledge.md` + this reference + the target doc in full, pick the
phase from the doc's Phases list (the list IS the build queue,
unchecked in order), and run the standard loop — pre-implementation
audit → implement → `make check` → reviewer (REVIEW, via
`make review-pack`) → atomic commits → tick checkboxes → numbered
playtest checklist at the brief's checkpoint → stop at the brief's
stop point. A phase with no brief is never coded: the command
proposes a brief to the user instead.

## The session lifecycle (riff → refine → implement → close)

One feature moves through five session types. Only two are commands —
commands earn their keep for *loops with mandatory discipline*; the
one-shot stages are ordinary sessions whose rules live in this
reference and `knowledge.md`.

1. **Riff + dump** (conversational): ideas with the user; when they
   say dump, write one or more docs per "Creating a design doc" above
   — full structure, PLAYTEST per phase, open questions, nothing
   implemented, presented for review before anything is ruled.
2. **`/refine-design <n>`** — the ruling loop: open questions become
   dated SETTLED sections (user wording verbatim; the doc never left
   contradicting itself), and each settled phase gets an approved
   Implementation brief. A phase is buildable only after this step.
3. **`/implement-phase <n>[.<p>]`** — the build loop; refuses
   unbriefed phases; ends at the brief's playtest checkpoint.
4. **Playtest notice** (conversational): the user reports pass/fail;
   update the phase bullet (LANDED + PLAYTEST PASSED, or what failed
   and the follow-up), record mid-playtest rulings, commit
   (`docs: ...`), then prompt for the next phase or the close.
5. **Close** (conversational): every checkbox checked, playtests
   recorded, no open questions — on the user's confirmation, move the
   doc to `complete/`, fix cross-references, and add/amend the
   phase's entries in `docs/design/SYSTEMS.md` (the inventory) in the
   same commit.

`/design-brief <n>` is report-only and usable at any point in the
loop; it edits nothing.
