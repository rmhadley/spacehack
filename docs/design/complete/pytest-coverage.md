# DESIGN: Automated test coverage (pytest)

> **Status: COMPLETE** — all 4 phases implemented (2026-08-07).
> **191 tests across 12 files, all green.** `knowledge.md` contracts
> updated: pre-commit gate requires pytest, pure + mutation-wrapper
> functions must ship with tests.

## Rationale

We have **zero automated tests** today — `tools/smoke.py` only verifies imports
and entry-point signatures. It catches module-level breakage (missing attributes,
bad import chains) but says nothing about the correctness of the code beneath
those entry points.

The game has grown past the point where a single manual playtest can verify
every fork of behavior in a reasonable loop. In particular:

- **Combat math** — hit chance, dodge bonus, damage formulas, flee chance —
  a ±1 error in any of these is invisible to a playtest. The player sees a
  percentage on the HUD, fires, and gets a hit or miss. The number could be
  wrong by 5% and no one notices until many combats in.
- **Price curves** — `trade_price()` can drift by a few credits and the player
  won't spot it for dozens of trades, if ever.
- **XP curves** — `xp_for_level()` produces 30 threshold values. A single
  off-by-one in the loop body shifts every level from 2–30. Completely
  invisible until a player grinds to a specific level and notices it "felt
  slow."

These are exactly the kinds of regressions that **only automated tests catch**
because manual sniff tests rely on coarse, eyeball-scale signals ("that number
looks about right").

**So the strategy is: test first whatever I can no longer verify by eyeballing
a single playtest.** Start with the formulas whose regressions are invisible
at human scale, then expand outward.

---

## 1. Test infrastructure

### Dependency

Add `pytest` as a dev dependency in `pyproject.toml`:

```toml
[project.optional-dependencies]
dev = ["pytest"]
```

Or document it as a `pip install pytest` prerequisite alongside tcod.
Keeping it optional keeps the production install minimal — only devs
and CI need it.

### Directory layout

```
tests/
    __init__.py                          # empty
    combat/
        __init__.py
        test_stats.py                    # calc_hit_chance, calc_flee_chance, _calc_*, etc.
        test_rules_ground.py             # _ground_hit_chance_raw, _ground_damage_raw
        test_actions.py                  # resolve_damage (with RNG seed)
    test_faction.py                      # get_attitude, starting_reputation, table lookups
    test_trade.py                        # trade_price
    test_ship.py                         # effective_speed, effective_max_cargo, etc.
    test_xp.py                           # xp_for_level
    test_saveload.py                     # round-trip (stretch)
```

Mirrors `src/spacehack/`. Each test file imports from `src.spacehack.<module>`.

### Test runner

Add a `tools/test.py` wrapper that mirrors `tools/smoke.py`'s venv auto-mount
pattern:

```python
#!/usr/bin/env python3
"""Run the pytest suite, auto-mounting .venv/bin/python3 if needed."""
import os
import sys
from pathlib import Path

def _ensure_venv() -> None:
    if sys.prefix != sys.base_prefix:
        return
    venv_py = Path(__file__).resolve().parent.parent / ".venv" / "bin" / "python3"
    if venv_py.exists():
        os.execv(str(venv_py), [str(venv_py), "-m", "pytest", *sys.argv[1:]])
    print("FAIL: .venv/bin/python3 not found.", file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    _ensure_venv()
    sys.exit(os.system("python3 -m pytest tests/"))
```

Alternatively, wire it into `tools/smoke.py` itself — add a `--pytest` flag or
run pytest automatically after the import checks. Keeps the pre-commit gate as
a single `python3 tools/smoke.py` invocation.

**Recommendation:** keep `tools/smoke.py` separate from `tools/test.py`.
They test different things (import chain integrity vs. formula correctness)
and run at different speeds. The pre-commit gate becomes:

```bash
python3 tools/smoke.py && python3 tools/test.py
```

but `tools/smoke.py` remains the canonical gate script.

### RNG in tests

Several combat functions call `RNG.randint()` / `RNG.uniform()` internally
(e.g. `resolve_damage`, `_animate_laser_shot`). The pure-candidate functions
can be tested in two ways:

1. **Seed the RNG** before the test, assert the deterministic output given
   that seed. Works for `resolve_damage` and `_ground_damage_raw` (which
   is pure — no RNG).
2. **Refactor to inject the random value** — `resolve_damage` currently calls
   `RNG.randint(1, 100)` internally for the quality roll. For pure testing,
   extract a `_resolve_damage_with_roll(weapon_id, hull, shields, quality_roll, ...)`
   that takes the roll as a parameter, and keep `resolve_damage` as the thin
   wrapper that draws the roll.

Phase 1 does NOT refactor — it seeds the RNG. Refactoring for injectable
randomness is a Phase 2+ item if the seeded approach proves brittle.

---

## 2. Tighten the pre-commit gate

**Current `knowledge.md` language (Pre-commit gate section):**

> Run the smoke test before each commit: `python3 tools/smoke.py`
> Never commit without a passing smoke test.

**Proposed update** (once the pytest suite exists and is stable):

> Run the smoke test AND the pytest suite before each commit:
>
> ```bash
> python3 tools/smoke.py && python3 tools/test.py
> ```
>
> Never commit without both passing. The smoke test guards import
> integrity; the pytest suite guards formula and state correctness.

This goes into `knowledge.md` as part of Phase 1's implementation —
update the Pre-commit gate section once `tools/test.py` exists and
the first batch of tests passes.

---

## 3. Inventory of pure, already-testable functions

Audit of the codebase per the "Pure functions for computation" guardrail.
Listed with file:line and a note on why it's a testing candidate.

### Tier A — combat formulas (highest priority)

These are invisible-regression candidates: a small error survives playtesting
indefinitely.

| Function | File:line | Why test | RNG? |
|----------|-----------|----------|------|
| `calc_hit_chance(weapon_id, gunnery, distance, target_dodge_bonus, hit_bonus)` | `combat/_stats.py:120` | Core accuracy formula — every shot in every fight depends on this | No |
| `calc_flee_chance(player_piloting, enemy_piloting, hull_pct, distance, attempts)` | `combat/_stats.py:145` | Flee chance — wrong by 5% = player never notices | No |
| `_calc_dodge_bonus(cells_moved, piloting_bonus)` | `combat/_stats.py:88` | Movement dodge cap at 30, soft-cap at 60 | No |
| `_calc_ap(piloting, ap_bonus)` | `combat/_stats.py:79` | AP per turn — wrong by 1 = turns feel off | No |
| `_calc_hull(ship_catalog, owned_ship)` | `combat/_stats.py:24` | Hull HP from damage pct — wrong = ship has wrong health | No |
| `_calc_max_hull(ship_catalog, owned_ship)` | `combat/_stats.py:30` | Max hull with module bonuses | No |
| `_calc_hull_for_enemy(enemy_spec)` | `combat/_stats.py:40` | Enemy hull from spec + modules | No |
| `_calc_power_gen(ship_catalog, owned_ship)` | `combat/_stats.py:54` | Power generation with module bonuses | No |
| `_calc_max_shields(ship_catalog, owned_ship)` | `combat/_stats.py:64` | Max shields with module bonuses | No |
| `_distance(a, b)` | `combat/_stats.py:110` | Euclidean distance — trivial but used everywhere | No |
| `_ground_hit_chance_raw(weapon_id, att_reflexes, tgt_reflexes, dodge_bonus, hit_bonus)` | `combat/_rules_ground.py:251` | Ground combat accuracy — same invisible-regression risk as space | No |
| `_ground_damage_raw(weapon_id, strength, armor_defense)` | `combat/_rules_ground.py:260` | Ground damage — melee str bonus, armor mitigation | No |
| `_calc_ground_move_dodge(cells_moved)` | `combat/_rules_ground.py:266` | Movement evade cap (same shape as space dodge) | No |
| `resolve_damage(weapon_id, hull, shields, piloting, mult)` | `combat/_actions.py:120` | Damage resolution — marginal, but calls RNG internally | Yes |

### Tier B — economy formulas

Wrong by small amounts, accumulate over many trades.

| Function | File:line | Why test |
|----------|-----------|----------|
| `trade_price(base_price, current_stock, target_stock)` | `trade.py:48` | Core pricing curve — wrong by 1 credit = invisible for dozens of trades |
| `xp_for_level(level)` | `xp.py:30` | 30 cumulative thresholds — off-by-one shifts every level |
| `_xp_to_next(level)` | `xp.py:37` | Per-level cost — used for HUD progress bar |

### Tier C — faction attitude + table lookups

These are pure table lookups — trivial but zero test coverage today.

| Function | File:line | Why test |
|----------|-----------|----------|
| `get_attitude(reputation)` | `faction.py:39` | 5-zone mapping — wrong zone = wrong prices, comms, missions |
| `starting_reputation(species_id, class_id)` | `faction.py:126` | Species+class combo → starting rep — must match design doc tables |
| `adjust_reward_pct(attitude)` | `faction.py:235` | Mission pay scaling per zone |
| `decay_rate(attitude)` | `faction.py:249` | Monthly rep drift direction + magnitude |
| `buy_price_modifier(attitude)` | `faction.py:296` | Faction rep buy discount |
| `sell_price_modifier(attitude)` | `faction.py:303` | Faction rep sell bonus |
| `guild_to_faction(guild)` | `faction.py:224` | Guild→faction key mapping |

### Tier D — ship stat helpers

Visible in HUD, so errors are easier to spot, but still formulaic.

| Function | File:line | Why test |
|----------|-----------|----------|
| `total_ammo_cargo(weapons)` | `ship.py:22` | Ammo cargo volume — wrong = cargo HUD off |
| `effective_speed(ship_spec, owned)` | `ship.py:165` | Moves-per-day — wrong = game clock drifts |
| `effective_max_cargo(ship_spec, owned)` | `ship.py:178` | Max cargo with module bonuses |
| `smuggler_hold_capacity(owned)` | `ship.py:188` | Contraband concealment capacity |
| `_sell_price(item_type, item_id)` | `ship.py:239` | 50% sell-back value |
| `ship_display_name(owned)` | `ship.py:148` | Name priority (display_name → catalog name → "Ship") |

---

## 4. Prioritization

Ranked by "can I still catch this by playtesting in a reasonable amount of time?"

### Phase 1 — Must-have (invisible regressions)

**`combat/_stats.py`** — the module docstring literally says "suitable for
testing in isolation." Every function here feeds the HUD hit-chance display
and the actual combat resolution. A 5% error in `calc_hit_chance` is invisible
to a playtester but changes the entire game balance.

**`combat/_rules_ground.py` pure functions** — same risk, ground flavor.

**`xp_for_level` / `_xp_to_next`** — 30 threshold values. A loop off-by-one
shifts every level silently.

### Phase 2 — High-value (accumulates slowly)

**`trade_price`** — the pricing curve. Wrong by a few credits per trade,
invisible until the player runs a multi-system trading route and notices
they're slightly richer/poorer than expected.

**`faction.py` pure functions** — `get_attitude`, `starting_reputation`,
the modifier tables. Wrong zone = wrong prices, wrong comms behavior.
Hard to catch because the player sees "the pirate is hostile" and doesn't
know whether that's correct for their rep score.

### Phase 3 — Medium (visible but formulaic)

**`ship.py` pure functions** — stats show in the HUD, so regressions are easier
to catch, but they're still pure formulas that deserve coverage.

### Phase 4 — Stretch (save/load round-trip)

The save/load contract is explicitly called out in `knowledge.md` as "not
checked by the smoke test." A round-trip test would:

1. Construct a `GameContext` with known state
2. Call `save_game()` to write the autosave JSON
3. Call `load_game()` to rebuild a `GameContext`
4. Assert every field matches

This is NOT pure — it hits the filesystem and constructs tcod contexts.
It needs a different test shape (probably a `tmp_path` fixture + a mock
tcod context). Flag it as a stretch item; it doesn't fit in early phases.

---

## 5. Phased plan

### Phase 1: Infra + combat math (highest risk)

- [x] Add `pytest` as dev dependency (document in pyproject.toml or README)
- [x] Create `tests/` directory layout mirroring `src/spacehack/`
- [x] Create `tools/test.py` with venv auto-mount pattern
- [x] `tests/combat/test_stats.py`: cover `calc_hit_chance`, `calc_flee_chance`,
      `_calc_dodge_bonus`, `_calc_ap`, `_calc_hull`, `_calc_max_hull`,
      `_calc_hull_for_enemy`, `_calc_power_gen`, `_calc_max_shields`, `_distance`
- [x] `tests/combat/test_rules_ground.py`: cover `_ground_hit_chance_raw`,
      `_ground_damage_raw`, `_calc_ground_move_dodge`
- [x] `tests/test_xp.py`: cover `xp_for_level`, `_xp_to_next` (verify all
      30 threshold values against the design doc table)
- [x] Update `knowledge.md` Pre-commit gate section to require pytest
- [x] Add "Pure function test contract" to `knowledge.md` (see section 6)

**PLAYTEST:** Run `tools/test.py` — confirm all tests green. Run
`tools/smoke.py` — confirm no regressions. Then run `python3 tools/smoke.py &&
python3 tools/test.py` to verify the full pre-commit gate works as a single
command chain.

### Phase 2: Economy + faction

- [x] `tests/test_trade.py`: cover `trade_price` (shortage zone, equilibrium,
      surplus zone, edge cases at 0/target stock)
- [x] `tests/test_faction.py`: cover `get_attitude` (boundary values at -76,
      -26, +26, +76), `starting_reputation` (all species×class combos from
      design doc), `adjust_reward_pct`, `decay_rate`, `buy_price_modifier`,
      `sell_price_modifier`, `guild_to_faction`

**PLAYTEST:** `tools/test.py` green, `tools/smoke.py` green.

### Phase 3: Ship stats + resolve_damage

- [x] `tests/test_ship.py`: cover `total_ammo_cargo`, `effective_speed`,
      `effective_max_cargo`, `smuggler_hold_capacity`, `_sell_price`,
      `ship_display_name`
- [x] `tests/combat/test_actions.py`: cover `resolve_damage` (seed RNG,
      verify damage output for known weapon + quality roll values)

**PLAYTEST:** `tools/test.py` green, `tools/smoke.py` green.

### Phase 4: Save/load round-trip (stretch)

- [x] `tests/test_saveload.py`: round-trip test — build GameContext, save,
      load, assert field-level equality for all serialized fields
- [x] Requires: mock tcod context (or a real one from `tcod.context.new()`)

**PLAYTEST:** `tools/test.py` green, `tools/smoke.py` green. Additionally,
run a manual sniff test: start new game → play a few turns → save/quit →
continue → verify exact state match.

---

## 6. Ongoing contract — "Pure functions ship with tests"

Propose a new rule for `knowledge.md`, added alongside the existing
save/load / guide / module-state contracts:

### Pure function test contract

> **Every new pure function added to the codebase must ship with a pytest
> test in the same commit. Any modification to an existing pure function
> that changes its behavior or signature must update its corresponding
> test in the same commit.**
>
> "Pure" follows the existing guardrail: no I/O, no mutation of
> arguments, no side effects, deterministic given its inputs.
>
> A pure function without a test — or a test that hasn't been updated
> to match a changed function — is a regression waiting to happen: its
> correctness is invisible to the smoke test AND to manual playtesting.
>
> This applies to all new and modified code. Existing untested pure
> functions are backfilled on the schedule in the pytest coverage
> design doc.

This is what stops the gap from reopening. Everything else in this doc
only backfills the past — the contract is the ongoing enforcement
mechanism.

**Checklist before shipping any new or modified pure function:**
- [ ] Is there a corresponding test in `tests/`?
- [ ] If the function was modified, was the test updated to match?
- [ ] Does the test cover the function's key edge cases (boundaries, min/max,
      zero/empty inputs)?
- [ ] Does `tools/test.py` pass?

---

## Open questions (resolved)

1. **`resolve_damage` RNG strategy** — Kept seeded RNG in Phase 3.
   No flakiness observed; all seeded values pinned as exact assertions.

2. **`tools/test.py` vs `tools/smoke.py`** — Kept separate. Pre-commit
   gate runs both: `python3 tools/smoke.py && python3 tools/test.py`.

3. **CI integration** — Not yet wired; remains a follow-up ops change.

4. **Property-based testing** — Not pursued. Example-based tests proved
   sufficient for all 191 assertions; no edge-case gaps found.
