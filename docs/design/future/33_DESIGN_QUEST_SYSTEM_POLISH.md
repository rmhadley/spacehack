# DESIGN: Quest System Polish (deferred)

> Seeded 2026-09-03 from the Merchants Act 0 build (`32_DESIGN_ACT0_
> MERCHANTS.md`) — a review of the quest system after a full dive-in.
> **Verdict that seeded this: the engine is excellent; the authoring
> and test membrane around it is where the remaining friction lives.**
> Tackle after Merchants (and ideally after one more chain) so the
> findings here are corroborated by two builds, not one.

## What validated under extension (do not touch)

- **Objective handler registry**: adding `payment` was one field + one
  table entry + two hooks; dispatch sites grew zero branches. Smuggle
  gating and payment gating coexist untouched.
- **Hook orthogonality**: on_trigger / on_complete / option_gating /
  ensure_spawns / secures_quest_loot covered every behavior needed.
- **Structure/prose split**: Python steps + JSON overlay + extractor
  merge (scaffold missing, preserve writer edits, prune dead keys)
  behaved exactly as documented through a full chain rewrite.
- **Two-text gates**: flavor + ready_message pairs are the tuned Lab
  pattern; the smoke check enforcing ready_message on gated steps
  caught a real miss immediately.
- **Data-rendered structured text** (settled 2026-09-03): option
  labels format from data ("Settle the bond ({credits}cr)") and Q
  renders `Cost: X$ (have Y$)` for payment steps like Reward/Due —
  numbers live in data, prose stays writer-owned and digit-free.

## Findings (each bit the Merchants build)

### 1. Step renames have no first-class story — HIGHEST VALUE
Inserting `mer_q4_bribe` renumbered two ids; the blast radius was:
three test files, the extractor's section list
(`tools/extract_act0_text.py`), a stale comment in
`tau_ceti_b.py`, and a hand-written save migration
(`_repair_merchants_renumber` in `_gates.py`). Ids encode sequence
(`mer_q4`, `mer_q5`), so insertion forces renaming.

**Fix A (cheap):** a `RENAMES: dict[str, str]` table in the quest
catalog that `find_main_quest_step` AND save-load both consult — one
place per rename, no bespoke repair function.
**Fix B (structural):** ids that don't encode order (titles already
carry the poetry). Only worth it if renames stay common.

### 2. No quest linter — HIGHEST VALUE
Authoring rules were learned by failing gates one at a time:
gated step needs ready_message; trigger_on_talk dialogue needs
option_label; two-phase smuggle needs `active` text; npc_presence
must be declared; heat tags listed; text keys must match step ids.
The smoke test covers a slice.

**Proposal: `tools/quest_lint.py`** — validates every chain in one
run and prints a per-chain report:
- dialogue completeness (intro/option/active/complete per type)
- gated steps carry flavor + ready_message pairs
- orphaned text keys (in JSON, not referenced by any step)
- npc_presence / heat / spawns declared consistently
- cost-bearing prose cross-check (see finding 4)
- wait-cadence summary per chain (steps, waits, total gate-days)
Run in `make check` or as its own target. This is the
city-audit-tool lesson applied to quests: a trusted diagnostic that
catches authoring mistakes at commit time instead of playtest time.

### 3. Test ergonomics fight the completion path
The fake quest-context grew six attributes across five test runs
(`log.add`, `add_colored`, `player_xp`, `player_level`,
`player_skill_points`, time fields) because `complete_step` knows the
whole character sheet.

**Fix A (cheap):** shared `tests/support/quest_ctx.py` factory.
**Fix B (structural):** a reward-apply seam — quest completion hands
off xp/level/credit effects to a single function the tests can stub,
instead of reaching into ctx fields directly.

### 4. Prose-vs-data drift — PARTIALLY SOLVED
The `Cost:` line made the payment number single-sourced (landed
`b9b44ae`). Remaining drift surfaces: quantities in prose ("three
crates" vs `smuggle_cargo_size`), day counts (wait prose is
deliberately vague — keep it that way), reward mentions.

**Ruling (user, 2026-09-03):** vars render into structured UI text
(labels, Q lines); prose is writer-owned and carries no interpolations
— writer edits must stay safe (the extractor's preserve-edits
contract) and hand-tuned voice doesn't survive Mad-Libs. Where prose
does cite a number, lint cross-checks it against data rather than
sourcing it.

## Non-findings (checked, fine as-is)

- Branching: the faction fork + payment gate cover current needs; no
  general branch primitive required yet.
- npc_presence per-planet stamping worked; only a stale *comment*
  referenced old ids (lint can flag comment references cheaply, or
  not at all).
- Dev tooling: Shift+D time-skip + dev credits already cover quest
  playtesting needs.

## Phases (when tackled)

- [ ] Phase 1: `RENAMES` table (finding 1, Fix A) + migration tests
- [ ] Phase 2: `tools/quest_lint.py` (finding 2) + wire into a make
      target; fix everything it flags repo-wide
- [ ] Phase 3: `tests/support/quest_ctx.py` (finding 3, Fix A);
      optionally the reward seam (Fix B)
- [ ] Corpus audit + `make check`; move doc per lifecycle

## Acceptance criteria

- Renaming a step id is a one-table edit; saves migrate through it.
- `quest_lint` runs clean on every chain and catches injected faults
  (test: corrupt a copy, expect the flag).
- New-chain test files build on the shared ctx factory with zero
  attribute whack-a-mole.
