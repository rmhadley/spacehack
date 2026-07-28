# Design: Game Time System

## Overview

Add a day/month/year clock to the game that advances as the player flies
through space. Every 10 space moves (manual + auto-nav) = 1 day. The clock
lives on `GameContext` so every subsystem can read it, and a single
`advance_time()` helper centralizes the tick + future hook points.

## Philosophy alignment

| Principle | How this design follows it |
|-----------|---------------------------|
| ctx-first | Time fields live on `GameContext`; `advance_time(ctx, days)` mutates them |
| Data-first | Time is pure data (three ints); no new data catalog needed |
| Domain ownership | A new `src/spacehack/time.py` module owns the clock logic |
| Atomic commits | Each phase is one commit |
| Extensible | `advance_time()` is the single choke-point; future systems subscribe by reading `ctx.time_*` or by having their tick called inside `advance_time()` |

## Data model

```python
# On GameContext (four new fields):
time_day: int = 1       # 1–30
time_month: int = 1     # 1–12
time_year: int = 2200   # starting year
move_counter: int = 0   # increments per space move; ticks a day at ship.speed
```

- 30 days per month, 12 months per year. Simple, predictable, no leap-year edge cases.
- Start date: Day 1, Month 1, Year 2200. Sci-fi future, clean start.
- Time advances based on ship speed: fast ships (scout=14) need more moves per day;
  slow ships (freighter=6) need fewer. Distance = time, modified by ship choice.
- All fields are plain `int`.

## Domain: `src/spacehack/time.py`

```
advance_time(ctx, days: int) -> None
    Advance the clock by `days`. Wraps months at 30, years at 12.
    Detects month/year rollover and fires subscriber hooks.
    Also calls existing tick_economy(ctx) on every advance.
    This is THE single function that mutates time — all paths go through it.
    (Now only called internally by tick_move; no external callers remain.)

tick_move(ctx) -> None
    Count a space movement. Checks the player ship's ``speed`` stat
    (moves per day); advances time when counter >= speed.
    Counter persists across jumps and landings (does NOT reset).
    Called from manual space movement (__main__.py) and auto-nav (navigation.py).

format_date(ctx) -> str
    Return "Date: YYYYMMDD" for HUD rendering (e.g. "Date: 22000115").
    Sci-fi compact format, fits within HUD_WIDTH (20 chars).
```

## Tick events (where time advances)

Time advances through **movement**: every 10 space moves = 1 day. A "move"
is one cell of travel in space mode — both manual (h/j/k/l/y/u/b/n) and
auto-nav (G key) steps count. The counter persists across all actions
(jumps/lands do NOT reset it).

| Event | Days advanced | Rationale |
|-------|--------------|-----------|
| 10 space moves (manual) | 1 day | Flying across a solar system takes time |
| 10 auto-nav steps | 1 day | Same rate as manual — distance = time |
| Jump gate travel | 0 days | Jump is instantaneous FTL |
| Planet landing | 0 days | Docking is quick |
| Launch to space | 0 days | Taking off is quick |
| Wait (`.` in space) | 0 days | Waiting is minutes/hours, not days |
| Walk (city mode) | 0 days | Walking around a city is minutes |
| Combat moves | 0 days | Combat has its own movement system |

This makes distance meaningful: Earth → Mars (~80 cells) = ~8 days,
Earth → Alpha Centauri Gate (~55 cells) = ~5.5 days. The player feels
the scale of the solar system through the clock ticking as they fly.

## Ship speed reference

Each ship has a `speed` stat (moves per day). Faster ships cover more
cells per day — travel time varies significantly by hull choice.

| Ship | Speed | Earth→Mars (80 cells) |
|------|-------|----------------------|
| Scout | 14 | ~5.7 days |
| Starter | 10 | ~8.0 days |
| Cruiser | 9 | ~8.9 days |
| Frigate | 8 | ~10.0 days |
| Hauler | 7 | ~11.4 days |
| Freighter | 6 | ~13.3 days |

Future: engine/thruster modules could add a `speed_bonus` to
increase moves-per-day beyond the hull base speed.

## HUD display

### City mode HUD
```
Location: Earth
Day 15, Month 3, Year 2200    ← new line, silver/dim color, below location
---
HP: 10/10
$: 100
```

### Space mode HUD
```
SCOUT
SOL
Day 15, Month 3, Year 2200    ← same format, below system name
---
Fuel: 90/100
Hull: 95%
...
```

Both modes show time in `COLOR_VALUE_DIM` (silver), on its own line between
the location and the first divider. Unobtrusive but always visible.

## Phased implementation plan

### Phase 1: Core time module + GameContext fields

- [x] Create `src/spacehack/time.py` with `advance_time()` and `format_date()`
- [x] Add `time_day`, `time_month`, `time_year` fields to `GameContext` (default: 1, 1, 2200)
- [x] Wire `advance_time()` call into `_jump_to_system` (navigation.py, jump gate travel)
- [x] Wire `advance_time()` call into planet landing path in `__main__.py` (PlanetMenuOutcome.LAND)
- [x] Add `format_date()` to both city and space HUD render paths in `hud.py`
- [x] Run smoke test
- [x] Commit

**PLAYTEST — Phase 1:**

*You'll verify: HUD shows time, jumps/lands tick it, other actions don't.*

1. **Start a new game** — pick any species/class, confirm.
   → In the city HUD (right panel), below "Earth", you should see:
     `Day 1, Month 1, Year 2200`

2. **Launch to space** — walk to your ship at the spaceport (top-left building,
   the `>` character), bump into it, select "Launch".
   → In the space HUD, below "SOL", time should STILL say:
     `Day 1, Month 1, Year 2200`  (launching doesn't cost time)

3. **Jump to another system** — fly to a jump gate (look for a bright glyph
   on the space map, use `h/j/k/l` or press `G` to auto-nav). Bump into the
   gate, press ENTER to jump.
   → After the jump animation, the HUD should show:
     `Day 2, Month 1, Year 2200`  (+1 day for the jump)

4. **Land on a planet** — fly to a planet (any colored glyph — e.g. Mars
   looks like a red circle in Sol). Bump into it, select "Land".
   → After landing, the city HUD should show:
     `Day 3, Month 1, Year 2200`  (+1 day for landing)

5. **Jump back** — launch again, jump back to Sol. You should be at Day 4.
   Land on Earth → Day 5. The clock should climb by 1 for each distinct
   jump or land action.

6. **Wait in space** — in space mode, press `.` (period) to wait one turn.
   → Time should NOT change (should still be the same day).

7. **Walk around city** — on a planet, walk around with `h/j/k/l`.
   → Time should NOT change (moving on foot doesn't tick the clock).

8. **Month rollover** — jump back and forth between two systems repeatedly
   (each round-trip = +2 days: jump out + land). Do this 15 round-trips
   starting from Day 1 and you'll hit Day 31 → should wrap to:
     `Day 1, Month 2, Year 2200`

9. **Year rollover** — continue jumping/landing until you pass 12 months.
   After Month 12 Day 30, the next advance should show:
     `Day 1, Month 1, Year 2201`

### Phase 2: DRY evaluation — time surface area

*After Phase 1, before adding more features — audit the time module for
duplication and single-responsibility violations.*

**Checklist:**
- [x] `format_date()` is called in exactly ONE place per HUD mode — the `render_hud()`
  function. No separate `format_date()` call duplicated in city vs space branches.
  Both modes should call the same `format_date(ctx)` and print it in the same spot.
- [x] `advance_time()` is the ONLY function that mutates `ctx.time_day`,
  `ctx.time_month`, or `ctx.time_year`. No file other than `time.py` does
  `ctx.time_day += 1` or equivalent.
- [x] The two tick call sites (`_jump_to_system` and the landing path) both call
  `advance_time(ctx, 1)` — not `advance_time(ctx, 1)` in one place and manual
  field mutation in the other.
- [x] No dead imports: check that `time.py` imports are used, `__main__.py` and
  `navigation.py` don't have leftover unused imports from the wiring.
- [x] `GameContext` has exactly three new fields (`time_day`, `time_month`,
  `time_year`) — no extra helper fields crept in that belong in `time.py` instead.
- [x] Run smoke test.
- [x] Fix any DRY issues found, then commit (separate commit from Phase 1).

### Phase 3: Month/year rollover log messages

- [x] `advance_time()` logs a colored message when month or year changes
- [x] Smoke test
- [x] Commit

**PLAYTEST — Phase 2:**

*You'll verify: the message log announces month/year changes.*

1. **Month rollover message** — start a new game, jump/land repeatedly until
   you go from Day 30 → Day 1 of the next month (30 advances). When the
   month wraps, the message log should show:
     `A new month begins.`  (in a colored/noticeable shade)

2. **Year rollover message** — keep going until Month 12 Day 30 wraps to
   Month 1 of the next year. The log should show:
     `A new year begins — 2201.`  (also colored)

3. **No false messages** — jump a single time mid-month. No month/year
   message should appear. Only on actual rollover.

### Phase 4: Economy hooks into time

- [x] Move `tick_economy(ctx)` call from `_jump_to_system` into `advance_time()`
- [x] So the economy ticks whenever time advances (not just on jumps)
- [x] Smoke test
- [x] Commit

**PLAYTEST — Phase 3:**

*You'll verify: the economy now ticks on landings too (not just jumps).*

1. **Before this phase** — economy only ticks on jumps (the `tick_economy`
   call is inside `_jump_to_system`). Landing doesn't shift prices.

2. **Land on a planet** — launch from Earth, land on Mars. Before landing,
   note the buy/sell prices of a common good (e.g. Food) at the Earth
   trade terminal. After landing, visit the Mars trade terminal. Previously
   only jumps would shift prices; now landing should also cause a tick.

3. **Jump to a new system** — same as before, jump should still tick the
   economy. Verify no double-tick (shouldn't happen — `advance_time` calls
   `tick_economy` once, and `_jump_to_system` no longer calls it directly).

4. **Chain of actions** — do: land → jump → land → jump. Each action
   should advance time by 1 day AND tick the economy. Prices should
   gradually shift across multiple actions.

### Phase 5: Movement-based time (design pivot)

*Replaced the old jump/land tick model with movement-based time.*

- [x] Add `move_counter: int = 0` to `GameContext`
- [x] Add `tick_move(ctx)` to `time.py` — every 10 calls advances time by 1 day
- [x] Remove `advance_time(ctx, 1)` from `_jump_to_system` (navigation.py)
- [x] Remove `advance_time(ctx, 1)` from landing path (`__main__.py`)
- [x] Wire `tick_move(ctx)` into manual space movement (`__main__.py`)
- [x] Wire `tick_move(ctx)` into auto-nav step loop (`_run_goto` in navigation.py)
- [x] Smoke test + code review
- [x] Commit

**PLAYTEST — Phase 5:**

*You'll verify: time advances through movement, not jump/land.*

1. **Manual movement ticks the clock** — start a new game, launch to
   space. Fly around with h/j/k/l. After exactly 10 moves, the HUD
   date should advance by 1 day (from Day 1 to Day 2, Month 1, 2200).
   After 20 more moves (30 total), you should be at Day 4.

2. **Auto-nav ticks the clock** — press `G`, pick a destination like
   Mercury. Watch the auto-nav animation. The date should advance
   roughly every 10 steps. For a ~30-step auto-nav, you should see
   ~3 days pass.

3. **Jump does NOT tick the clock** — after auto-nav to a jump gate,
   bump into it and jump. The date should NOT change. Jumping is
   instantaneous FTL — no time passes.

4. **Landing does NOT tick the clock** — after jumping to a new system,
   fly to a planet and land. The date should NOT change from the
   landing action itself. Only the flight to reach the planet costs time.

5. **Counter persists across actions** — fly 7 steps in space (7/10
   toward next day), then land on a planet. Launch back to space. Fly
   3 more steps. The date should advance by 1 day (7 + 3 = 10).
   The counter accumulated across the landing.

6. **Combat does NOT tick** — if you encounter pirates mid-flight, the
   combat moves should NOT count toward the 10-move counter. After
   combat, your counter should be where it was before combat started.

### Phase 6: DRY evaluation — economy consolidation

*After Phase 4, verify the economy tick is truly single-sourced.*

**Checklist:**
- [x] `tick_economy(ctx)` is called from exactly ONE place: inside `advance_time()`.
  Search the codebase for `tick_economy` — there should be no stray call in
  `_jump_to_system` or any other navigation function.
- [x] `advance_time()` calls `tick_economy` once per invocation, not per day (if
  `days > 1`, it should still call `tick_economy` once, not in a loop).
- [x] The old `from .trade import tick_economy` import in `navigation.py` is removed
  if `_jump_to_system` no longer calls it directly.
- [x] No other tick-like function (NPC movement, shield regen) was accidentally
  pulled into `advance_time()` — this phase only moves `tick_economy`, nothing else.
- [x] Run smoke test.
- [x] Fix any DRY issues found, then commit.

### Phase 7: Shop refresh on month rollover

- [x] Add `_on_month_change(ctx)` as a module-level function in `time.py`
- [x] Reset `mech_visit_count` dict → next mechanic visit gets fresh RNG inventory
- [x] Log "Shops have restocked for the new month."
- [x] Wire `mech_visit_count` into `_loadout.py` — pass `visit_count` to `resolve_mech_inventory()` and increment each visit
- [x] **RNG fix**: `resolve_mech_inventory` now uses shared `engine.RNG` instead of local `random.Random(hash)`. Removed `visit_count` parameter, `mech_visit_count` field, and hash-based seed — inventory changes naturally with RNG state.
- [x] Run smoke test
- [x] Commit

**PLAYTEST — Phase 4:**

*You'll verify: mechanic shops get fresh RNG inventory each new month.*

1. **Note current inventory** — start a new game. Launch to space, fly to
   a planet with an RNG mechanic (NOT Earth — Earth has a fixed curated
   inventory). Try Mars (it has a curated list too, so pick any other
   landable planet like one in Alpha Centauri). Visit the mechanic
   terminal (`%` glyph), note the weapons/modules on offer.

2. **Roll the month** — jump and land 30 times to advance a full month.
   When the month wraps, the log should show:
     `Shops have restocked for the new month.`

3. **Visit the same mechanic** — go back to the same planet's mechanic
   terminal. The inventory should now be DIFFERENT (new RNG seed since
   `mech_visit_count` was reset).

4. **Curated planets unchanged** — Earth's mechanic still shows the same
   fixed inventory (it uses `mech_weapons` tuple directly, not RNG).
   This is correct — only RNG shops refresh.

### Phase 8: DRY evaluation — month-change hook

*After Phase 7, verify the month-change hook is cleanly structured.*

**Checklist:**
- [x] Month rollover detection happens in ONE place — `advance_time()` checks if
  `time_day` wrapped past 30. No other function re-checks this condition.
- [x] `_on_month_change(ctx)` is a separate module-level function in `time.py`,
  not an inner function in `advance_time()`. Inner functions that don't close over
  the parent scope should be module-level (per reviewer checklist in knowledge.md).
- [x] The log message "Shops have restocked for the new month." is inside
  `_on_month_change`, not duplicated in a caller.
- [x] `mech_visit_count` removed entirely — no other code path clears or replaces that dict.
- [x] `_on_month_change` does exactly one thing: log. It doesn't also tick economy
  (that's `advance_time`'s job) or format dates (that's `format_date`'s job).
- [x] **Bonus: full-project RNG audit.** Found 1 gameplay-affecting issue —
  `trade.py` used bare `random.shuffle`/`randint` for NPC trade loot. Fixed to use
  `engine.RNG`. Remaining bare `random` uses (ui.py splash, world.py grass,
  solar_system.py stars) are decoration-only, left as-is per user request.
- [x] Run smoke test.
- [x] Fix any DRY issues found, then commit.

### Phase 9: Mission deadline support

- [ ] Add `time_deadline: tuple[int, int, int] | None` to `ActiveMission`
- [ ] Mission accept computes deadline = current date + N days from mission spec
- [ ] HUD shows "Due: Day D, Month M" when deadline approaching
- [ ] Quest log shows time remaining
- [ ] This phase is designed but implemented later (when we have timed missions)

## Acceptance criteria

1. Time displays correctly in both city and space HUDs
2. Every 10 manual space moves advances time by 1 day
3. Every 10 auto-nav steps advances time by 1 day
4. Move counter persists across jumps and landings (does NOT reset)
5. Jumps, landings, launch, wait, and city walks do NOT advance time directly
6. Combat moves do NOT count toward the move counter
7. Month and year rollover work correctly (30-day months, 12-month years)
8. Rollover log messages appear
9. Economy ticks are consolidated into `advance_time()`
10. Smoke test passes after every phase

## Planned future subscribers to `advance_time()`

These are NOT implemented in the initial phases — they're documented here so
the hook point design is validated before we commit to it:

| Subscriber | Trigger | What it does |
|-----------|---------|-------------|
| `tick_economy(ctx)` | Every advance | Adjusts planet stock levels (already exists, Phase 3 consolidates it) |
| `_on_month_change(ctx)` | Month rollover | Resets `mech_visit_count` → fresh RNG shop inventory (Phase 4); future: rotate trade good availability, refresh mission board |
| `_on_year_change(ctx)` | Year rollover | Future: annual faction reputation drift, rare event spawns, aging of NPC ships |
| Mission deadline checks | Every advance | Compare `ctx.time_*` against active mission deadline; fail expired missions |

## Open questions

1. **Starting year?** 2200 feels right for a sci-fi roguelike. Alternatives: 2400, 3000. → Going with 2200.
2. **Should launching to space cost time?** The user said "landing on planet, traveling through a jump gate" — launch was not mentioned. Starting with 0. Can revisit.
3. **Should waiting (`.`) cost a fraction of a day?** Could add hours later (0–23 hour field). Out of scope for initial design — `.` costs 0 time.
4. **Month names?** Resolved — using compact YYYYMMDD sci-fi format (e.g. "Date: 22000115"). No month names needed.
5. **Shop refresh granularity?** Per-month works well with the 30-day model — each month is 30 jump/land actions, giving enough time between refreshes to feel meaningful without being frustrating. Per-week (every 7 days) could be added later if monthly feels too slow.
