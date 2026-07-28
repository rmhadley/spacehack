# spacehack — Agent knowledge

A terminal-based sci-fi roguelike built on [python-tcod](https://github.com/HexDecimal/python-tcod).

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m spacehack           # run the game
```

## Git workflow (MANDATORY — aggressive local commits)

**Commit after every logical change.** Do not batch changes. Do not wait until the end of a session. The working tree, not the chat log, is the source of truth.

### Commit discipline
- **One commit = one self-contained change** (one refactor step, one feature, or one bug fix).
- **Descriptive messages.** Start with a prefix tag: `feat:`, `fix:`, `refactor:`, `docs:`, `tools:`, `content:`. Example: `feat: add laser damage falloff at range`.
- **Run the smoke gate before each commit.** Never commit without a passing smoke test (see Pre-commit gate below).
- **NO mega-commits.** Break large work into a sequence of atomic commits.

### Commit triggers (AI agents: follow these rules absolutely)

1. **One phase = one commit.** When a design-doc phase is fully implemented and all its checkboxes are checked, commit before starting the next phase.

2. **Bug fixes commit immediately.** A single fix (even one line) is a commit. Do not bundle it with the next feature.

3. **Refactors commit separately.** If a refactor (e.g. DRY extraction) touches files that were modified by the current phase, commit the refactor as its own commit directly after the phase commit.

4. **User says "great" = commit trigger.** Any time the user says some variant of "looks good", "looks great", "nice", "approved" — stop and commit what you have before continuing.

5. **Every distinct file change is a candidate.** If you edit a file that wasn't part of the current phase's plan, that's probably a separate commit waiting to happen.

6. **Boundary rule for cross-cutting changes.** A cross-cutting change (same edit repeated in many files) still counts as ONE commit, because the individual edits are meaningless without each other. Example: wiring `?` into 16 modal handlers across 6 files = one commit ("feat: wire ? into all modal sub-screens").

7. **Never commit without a passing smoke test.** Run ``python3 tools/smoke.py`` first.

**Violation example from a real session:** After a session with 11 files changed, the agent made 2 commits instead of ~6. The second commit bundled 5+ unrelated changes (a feature, a refactor, a content restructure, a HUD addition, and a one-line fix). Each should have been separate.

### Why
Each new AI session opens from `git status` / `git diff --stat` / `git log`. If changes aren't committed, the agent has no memory of what was done. Commit aggressively so the next turn picks up from a clean diff, not from prose recall.

---

## Key conventions (always follow)

### ctx-first design
All cross-cutting state goes through `GameContext` (`ctx`). **Never** use these as bare names in domain functions:

- `game_map`, `log`, `stats`, `character_info`
- `player_owned_ship`, `player_active_mission`, `context`

Always: `ctx.game_map`, `ctx.log`, etc.

### GameContext fields
| Field | Type | Purpose |
|-------|------|---------|
| `species_name`, `class_name` | `str` | character identity |
| `context` | `tcod.context.Context` | SDL window; pass to `ui.Modal` |
| `character_info`, `player` | dataclasses | character + entity state |
| `log` | `MessageLog` | in-game log + colour helpers |
| `game_map` | `world.GameMap` | world / entity container |
| `stats` | `HudStats` | aggregate HUD-facing values |
| `player_owned_ship` | `` `OwnedShip | None` `` | equipped ship |
| `player_active_mission` | `` `ActiveMission | None` `` | current mission |

### Adding content (data-first)
All content lives in `src/spacehack/data/` as frozen dataclasses:

| Content | Location |
|---------|----------|
| Weapons (lasers) | `data/weapons/lasers.py` |
| Weapons (missiles) | `data/weapons/missiles.py` |
| Ship modules (engines) | `data/modules/engines.py` |
| Ship modules (systems) | `data/modules/systems.py` |
| Enemy ships | `data/enemies/pirates.py` |
| Solar systems | `data/solar_systems/<name>.py` + register in `__init__.py` |
| Planets | `data/planets/` |
| NPCs | `data/npcs/` |
| Species | `data/species/` |
| Missions | `data/missions/<faction>.py` |
| Character classes | `data/classes/core.py` |

Each data file exposes a frozen `@dataclass` + `find_<thing>(id)` that raises `KeyError`.

### Adding a new game domain
1. Create `src/spacehack/<domain>.py` — setup, execution, post-state live together.
2. Entry point takes `ctx` (+ pure positional args). Access all state via `ctx`.
3. From `__main__`, hand off: `<domain>.<entry_point>(ctx, ...)`. No indirection.
4. For modal-driven UI: `ui.Modal(ctx.context, console).run(render_fn, update_fn)`
5. Add new cross-cutting state as a field on `GameContext`.
6. **Monitor file size** — If any existing `src/spacehack/*.py` approaches ~1000 lines during development, pause and evaluate whether the new code should live in its own module rather than inflating an existing file.

### Pre-commit gate
```bash
python3 tools/smoke.py
```

The smoke test auto-mounts `.venv/bin/python3` so tcod is always resolved. It verifies all major modules import correctly and key entry points survived signature changes.

### Refactor philosophy
- **Data-first.** New content is a file in `data/` backed by a frozen dataclass. No content lives in `__main__.py` or runtime modules.
- **Cross-cutting state through `ctx`.** No bare-Name regressions.
- **Domains own their flow.** Dispatcher is domain-unaware, one-call handoff.
- **Atomic commits.** One self-contained change per commit. Descriptive message.
- **Git anchors every step.** Each new session starts from `git status` / `git diff --stat`, not prose recall.
- **Gates beat playtests.** Run the smoke test before each commit to catch import errors and missing entry points.
- **Terse code-shaped docs.** Skim-don't-read mode.

## Screen constants (in `engine.py`)
```python
SCREEN_WIDTH   = 100
SCREEN_HEIGHT  = 50
WINDOW_TITLE   = "spacehack"
TILESHEET_FILENAME = "dejavu16x16_gs_tc.png"
```

## Modal UI pattern
```python
ui.Modal(ctx.context, console).run(render_fn, update_fn)
```

---

## Design doc workflow

Design docs live in `docs/design/` and are the contract between the user and the agent for building complex features.

### Directory structure

```
docs/design/
  <architectural-reference>.md         ─ reference docs (already implemented)
  complete/                            ─ implemented design docs
    <feature>.md
  in_progress/                          ─ doc currently being worked on
    <feature>.md
```

### Creating a design doc

When the user says "let's design X", the agent MUST first check if a design doc already exists for X (in any of the three directories). If none exists:

1. Create `docs/design/in_progress/<feature>.md`
2. Structure it with: overview, philosophy alignment table, data model, domain changes, phased implementation plan with checkboxes, acceptance criteria, open questions
3. Include a **PLAYTEST** section in each phase with concrete steps the user can follow
4. **Do NOT start implementation yet** — present the doc to the user for feedback first

### Iterating — doc stays the contract

During implementation, the design doc is a **living document**:

- **Update checkboxes** as each sub-step lands (mark `[x]` done)
- **Update playtest instructions** when you learn something mid-phase that changes what needs testing
- **After each playtest**, update the doc with: what passed, what failed, any new edge cases discovered
- **After each playtest**, the agent should ask "what's next per the design doc?" to steer conversation
- If the user says to change direction, **update the doc first** to reflect the new plan, then implement

### Self-audit pass (MANDATORY before every code review)

**After implementing changes but before spawning the code reviewer**, you MUST do a self-audit pass over every file you touched. This prevents the codebase from accumulating cruft between reviews.

Checklist:

1. **Repetition (DRY)** — Scan the changed file(s) for duplicated patterns. Are there loops, formulas, imports, or entity-construction blocks that appear more than once? Do NOT accept ``it was already duplicated`` as an excuse — flag it even if it is pre-existing. Extract shared helpers before moving on.

2. **ctx-first** — Is new cross-cutting state going through `GameContext` or being passed around as bare parameters?

3. **Data-first** — Does new content belong in a `data/` catalog + frozen dataclass?

4. **Live-by-side-effect** — Are domain functions mutating state directly or returning values for the caller to apply?

5. **Unused code** — Did this change leave behind dead imports, functions, fields, or constants? Remove them.

6. **File size** — Check if any touched domain module exceeds ~1000 lines. If so, plan an extraction before moving to the code reviewer.

Once the self-audit is done and any issues are fixed, spawn the code reviewer with the full reviewer checklist (next section).

### Code reviewer — what to look for

The ``code-reviewer-deepseek-flash`` agent is spawned after every significant change. **You MUST include the checklist below verbatim in the prompt you send to the reviewer** — the reviewer does not read knowledge.md, so it can only check what you ask it to check.

Reviewer checklist to paste into every reviewer prompt:

1. **DRY violations** — Scan the changed file(s) for duplicated patterns. Are there loops, formulas, or entity-construction blocks that appear more than once? Do NOT accept ``it was already duplicated`` as an excuse — flag it even if it is pre-existing. Examples of recent misses:
   - Three inner functions doing the identical planet/gate/station iteration (``_goal_for``, ``_tick_goal``, ``_body_goal``)
   - ``world.Entity(...)`` with the same field set constructed inline in two spawn paths
   - Path-computation + target-storage block copy-pasted between initial and per-tick spawn

2. **Inner functions that should be module-level** — If an inner function has no meaningful closure over the parent scope, it should be a module-level helper. Inner functions that duplicate another inner function's logic are always wrong.

3. **Dead code** — Did the change leave behind unused imports, functions, or variables? Check for functions that were only called from the now-replaced code.

4. **Signature mismatches** — Verify that all call sites match updated function signatures (new params, removed params, renamed fields).

5. **Edge cases** — What happens when inputs are empty/None? Does a loop that used to have a fallback still have one? (E.g. the old pirate random-scatter was a fallback when body goals were missing — if that path was removed, is the new guard equivalent?)

6. **Behavior preservation** — If a refactor claims to be purely structural (no behavior change), verify that claim. If behavior DID change (e.g. pirate spawn location standardisation), confirm that was intentional.

If any of these are found, the reviewer MUST flag them as blocking before commit, even if the change ``works.``

Document findings in the design doc's current phase section. Resolve before moving to the next phase.

### Moving docs through the lifecycle

1. **`in_progress/`** — Doc is being actively worked on. Playtests are happening. Checkboxes are being checked.
2. **`complete/`** — ALL checkboxes checked, final playtest passed, no open questions remain.
3. **`docs/design/` (root, reference)** — Architectural docs that describe already-implemented systems (not feature-iteration docs). These live in the root of `docs/design/` permanently as reference material.

When a phase completes with no next phase to start, ask the user: "Move this to complete?" before committing.
