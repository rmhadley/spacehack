# DESIGN: Headless Combat Balance Simulator

**Status: FUTURE — seed doc captured 2026-09-22. Not started. Blocked on
combat/gear/enemy content reaching a purposefully-designed state ready for
playtesting — see the open questions below before fleshing this out.**

## The problem

Combat is mid-polish/refactor right now, with enemies, NPCs, gear, and ships
being purposefully (re)designed. Once that settles, tuning numbers by feel
and manual playtest alone won't scale — a bad matchup (an enemy type
unwinnable at a given level, a weapon that trivializes everything) is easy
to ship without noticing until a playtester hits it.

## The idea

A headless tool that runs the game's real combat resolution
(`combat/_rules_space.py`, `combat/_rules_ground.py`, `combat/_stats.py`)
against synthetic matchups in bulk — N encounters per matchup, no
rendering, no UI — and reports outcomes: win rate, average rounds to
resolve, damage taken, ammo/resource consumption. The goal isn't just to
*measure* the current feel, it's to *enforce* a target feel the user has
already decided on (e.g. "a fresh pilot vs. a Pirate Scout should win
~70% of the time in 3-5 rounds") — a regression check for balance, not
just a balance report.

Likely builds on pieces that already exist: `tests/support/fake_pygame.py`
and combat's existing test fixtures show the resolution logic is already
exercised headlessly in the test suite; `tools/save_debug.py` shows the
project's pattern for a CLI tool that drives real game logic outside the
UI (though it explicitly stops at the combat boundary today).

## Open questions (settle before expanding this into a full design)

1. What are the target feel benchmarks, per matchup class? (win rate,
   round count, resource cost — needs the user's numbers, not guesses)
2. Which axis is being tuned first — ship combat, ground combat, or both
   in parallel?
3. Does this run as a one-off CLI (`tools/balance_sim.py`) or become part
   of `make check` as a regression gate once benchmarks exist?
4. How is enemy/gear variation parameterized — sweep every stat block in
   `data/`, or a curated matchup list the user maintains by hand?
5. AI behavior: use the real combat AI (`combat/_ai.py`,
   `combat/_ai_ground.py`) as-is, or does simulation need simplified/seeded
   AI to get statistically clean, reproducible results across N runs?
