# DESIGN: Tombstones — death review files

**Status: REFINED 2026-09-26 — SETTLED 1 recorded; phase 1 brief
drafted and ADVISE-reviewed (corrections folded); three rulings
REOPENED by the review (see Open questions). Nothing implemented.**

## Overview

On every player death, the game writes a **tombstone** to disk: a
plain-text morgue file carrying the character, the kit, the
circumstances, and the **message log in full** — the roguelike
standard (DCSS morgue files, NetHack tombstones). Deaths are about to
get more informative as balance tightens (the doc-50 era: rifleman
coin-flips, brute one-shots, splash suicides); the tombstone turns
each death into a reviewable autopsy for the player — and a tuning
datum for the designer ("what actually killed people, wearing what").

User framing (2026-09-26): "now that the game is getting difficult as
we balance things, it needs a way to review how you died. usually in a
roguelike it saves a tombstone to disk with your message log in full."

## Contents (v1 — SETTLED 1)

```
================================================
  REST IN PEACE — <species> <class>
  Level <L> — died <YYYY-MM-DD HH:MM> (real time)
  <day/month/year clock> — <system / system+planet>
  Slain by: <killer line — the last hostile damage
            source, e.g. "a Pirate Rifleman's laser
            rifle">
  Damage taken (career): <total_damage_taken>
  Run seed: <INIT_SEED>
  Final state: HP <n>/<max>  AP <n>     (ground)
               hull <n>  shields <n>    (space)
================================================

  THE SHEET: level + XP, pilot skills, ground stats,
             traits
  THE KIT: both weapon sets (id + quality + loaded
           ammo), armor slots, bandolier state,
           expedition pack,
           SHIP: installed weapons (id + quality +
                 loaded ammo) + modules

  --- MESSAGE LOG (full, oldest first) ---
  ... every entry, colours stripped ...
```

## SETTLED 1 (2026-09-26, user — the v1 rulings: all three open questions + the draft decisions)

> Death screen: "Yes — full filename." v1 sections: "Damage tally,
> Run seed, Final HP/AP state" + "Traits, stats, and equipped
> gear/modules dump."

- **All seven draft decisions confirmed**: location beside the
  autosave, timestamped filename, plain UTF-8 with the log
  colours-stripped, killer line from the death path, write at the
  shared finish before autosave deletion, best-effort failure, no v1
  in-game browser.
- **Location resolved to the real autosave dir (code check)**: the
  autosave lives at `~/.spacehack/saves/` (`saveload._saves_dir()`),
  NOT the repo-root `saves/` (that is the debug-drop location).
  Tombstones: `~/.spacehack/saves/tombstones/` — per-install, never
  the repo.
- **Decision "200-entry ring" CORRECTED (code check)**: MessageLog
  retains EVERY entry of the run — `history()` is unbounded,
  capacity=6 is the HUD slice only, and saves serialize the full
  history untrimmed (`saveload.py:188`). The tombstone ships the
  COMPLETE log at any run length; open question 1 (capacity bump) is
  dissolved — no change to MessageLog.
- **No `<name>` slot in the header (code check)**: no player-name
  field exists; the character is `<species_name> <class_name>`
  (`CharacterInfo`). Level is real (`ctx.player_level`).
- **Open question 2 RULED — yes, full filename**: the death screen
  adds one line naming the exact artifact,
  `Tombstone saved: <full path including filename>`. The screen
  already takes `lines` (`pygame_combat.present_death`); both theater
  call sites append it. UI state copy, not prose.
- **Markdown sibling RULED OUT for v1 (raised in review, same day)**:
  one classic plain-text morgue per death — grep-friendly, no doubled
  format pins, no renderer-pair drift. The pure section builders keep
  the door open: a ~30-line `.md` sibling renderer later IF a real
  share-rendered-autopsies workflow emerges in the tuning loop.
- **Open question 3 RULED — all three extras land in v1**, plus the
  write-in extending the dump:
  - **Damage tally** — `ctx.player_counters.total_damage_taken`
    (as tracked today: SPACE damage only — `_ai.py:497` is the sole
    increment site, ADVISE correction; nothing reads the counter for
    progression) — one header line; extend-vs-relabel REOPENED as
    question 2 below.
  - **Run seed** — `engine.INIT_SEED` (persisted in saves) — one
    header line; enables re-simming the run in the doc-50 balance
    harness.
  - **Final HP/AP state** — last ground HP/AP or space hull/shields
    at death.
  - **"Traits, stats, and equipped gear/modules dump"** (user
    write-in) — the SHEET already carried stats + traits and the KIT
    the ground side; the write-in extends the KIT to the SHIP:
    installed weapons (id + quality + loaded ammo) and modules join
    the dump (`ctx.player_owned_ship`).

## Phases

- [ ] 1. **The tombstone writer** — the module (format + sections +
  log export), the death-path hook (both theaters), file placement,
  tests (format pins, both death paths write, log stripping, killer
  line, failure-is-nonfatal). Brief at refine time.

### Phase 1 Implementation brief (proposed 2026-09-26 — awaiting approval)

**Scope — exact files and hook points**

- NEW `src/spacehack/tombstone.py` — the writer, split so the text is
  pure and the I/O is a thin shell:
  - `TombstoneFacts` dataclass — the combat-side inputs the finish
    builds: `killer: str | None`, `final_state: str` (the one-line
    ground HP/AP or space hull/shields readout).
  - Pure section builders (`_header_lines(ctx, facts)`,
    `_sheet_lines(ctx)`, `_kit_lines(ctx)`, `_log_lines(log)`) —
    no I/O, no mutation; `build_tombstone_text(ctx, facts) -> str`
    composes them in the settled order.
  - `write_tombstone(ctx, facts) -> str | None` — resolves
    `saveload._saves_dir() / "tombstones"` (mkdir parents), writes
    UTF-8, returns the full path string; any `OSError` → print to the
    real console and return `None` (never blocks the death path).
  - Filename `tombstone-<YYYYMMDD>-<HHMMSS>.txt`; if the target
    exists (two deaths within one second), suffix `-2`, `-3`, …
  - Contents per SETTLED 1's mock. Data sources, all read-only:
    header from `ctx.character_info`, `ctx.player_level`,
    `datetime.now()`, `ctx.time_day/month/year`, current
    system/planet identity (ADVISE resolution — NOT the HUD line,
    which lives on game-loop state unavailable here with a wrong
    'Derelict Ship' default: use `solar_system_module.current_system().name`
    + `game_map.location_name` when present (dungeon maps carry it)
    + a city-name fallback via the city catalog),
    `ctx.player_counters.total_damage_taken` (space-only today —
    reopened Q2), `engine.INIT_SEED`, `facts`; sheet from pilot
    skills + ground
    stats + traits (same accessors the character screen uses);
    kit from `ground_weapon_sets.partition_weapon_sets` (id +
    quality + loaded ammo via the ground-ammo store), the five
    equipped-armor slots, `ctx.bandolier`,
    `ctx.ground_expedition_items`, and
    `ctx.player_owned_ship` weapons + modules (id + quality + ammo),
    guarded for `None` (`OwnedShip | None` — omit the ship block,
    never crash the write) (ADVISE);
    log from `ctx.log.history()` — text only, `runs`/`fg` dropped,
    oldest first.
- `combat/_types.py` — `CombatResult` gains
  `tombstone_path: str | None = None` (session-scoped, never
  serialized → no save/load impact).
- Killer tracking at the TWO theater death sites (ADVISE correction:
  `_apply_enemy_hit` is SPACE-only — it logs "Your ship has been
  destroyed!"; ground fire is APPLIED by the caller):
  - space: `combat/_ai.py::_apply_enemy_hit` sets
    `state.last_attacker` from `_ei.name` + `_e_ws.name`.
  - ground: `combat/_rules_ground.py::_spend_one_enemy_turn` — the
    site that applies the damage `_ai_ground` returns and detects
    death (`:859-863`) — sets it from the enemy instance + weapon
    (weapon label the way `_ai_ground._present_enemy_shot` builds
    it, incl. quality).
  - Each state dataclass gains `last_attacker: str | None = None`
    DECLARED IN ITS OWNING MODULE (`SpaceCombatState` →
    `combat/_types.py`; `GroundCombatState` →
    `combat/_rules_ground.py`), exposed via a per-rules accessor
    (mirroring `player_hp(ctx)`) so `_finish_combat` reads it
    through `rules`. Both states are per-fight, never serialized —
    save-neutral.
- `combat/_loop.py::_finish_combat` — on DEFEAT, BEFORE
  `_delete_save()`: build `TombstoneFacts` (killer from
  `rules`-state `last_attacker` — fallback line `Slain by: unknown
  causes`; final state read from the combat state post-`sync_state`),
  call `write_tombstone`, stash the returned path on the
  `CombatResult`. Sequencing inside `_finish_combat` (ADVISE): the
  write goes before the `_delete_save()` call; the path stashes
  where `_cr` is built just after — no reorder of `sync_state`.
- Death-screen line, both sites append when
  `result.tombstone_path` is set:
  `f"Tombstone saved: {result.tombstone_path}"`:
  - space: `combat/_encounter.py` DEFEAT branch (`_cr` in scope,
    passes `lines` to `_render_death_screen`).
  - ground: `game_flow.py::_show_ground_defeat` (`ground_result`
    in scope; extend the existing `lines` tuple).
  - city (pending reopened Q3): city hostile-bump fights route
    through `_finish_combat` (the tombstone WRITES) but their DEFEAT
    `raise SystemExit()` with no screen at all (`city_npcs.py`) —
    pre-existing UX gap; ruling pending.
  - Long-path note (ADVISE): a HOME-heavy full path can exceed the
    100-col grid — clip or wrap at the screen seam (build-session
    call).

**Build order**

1. `tombstone.py` pure builders + `build_tombstone_text` + format
   pin tests (no combat needed).
2. Log export test (runs-bearing entry → text-only in output).
3. `last_attacker` tracking + `CombatResult.tombstone_path`.
4. `_finish_combat` hook + `write_tombstone` I/O + filename
   collision suffix test.
5. Death-screen lines at both sites.
6. Both-theater integration tests.

**Binding rulings (SETTLED 1)** — location
`~/.spacehack/saves/tombstones/` (NEVER the repo-root `saves/`);
timestamped filename with collision suffix; plain UTF-8; complete
log, colours stripped, oldest first; write before autosave deletion,
failure non-fatal; killer from tracked state, not log parsing; no
`<name>` slot; death screen names the FULL filename; v1 section set
is settled (sheet incl. traits/stats, kit incl. SHIP weapons +
modules, career damage tally, run seed, final HP/AP, full log); no
in-game browser; ONE `.txt` artifact per death — no sibling
markdown format (SETTLED 1; the pure section builders keep a
`.md` renderer a cheap later add, not built now).

**Required tests** (`tests/test_tombstone.py` + additions under
`tests/combat/`)

- Format pins: header carries species/class/level/clock/location/
  killer/tally/seed/final-state; sections present in settled order;
  log verbatim oldest-first.
- Log stripping: a `runs`-bearing entry appears as text only.
- Writer: file created in the sandboxed saves dir with the name
  pattern; same-second second write gets the `-2` suffix;
  monkeypatched write failure → `None`, no exception.
- Both death paths (pattern: existing `tests/combat/` +
  `tests/balance/` real-combat harness; its contracts apply —
  `pygame.init()`, absorbing console, RNG snapshot/restore, HOME
  sandbox since DEFEAT deletes the real autosave): space DEFEAT and
  ground DEFEAT each write a tombstone, `tombstone_path` set, killer
  line names the attacking enemy + weapon.
- Non-DEFEAT outcomes (VICTORY both theaters, ground DISENGAGED)
  write NO file — the `result == "DEFEAT"` gate pinned in tests, not
  just playtested (ADVISE).
- Killer-`None` fallback pin: header reads `Slain by: unknown
  causes` (exact string per the sign-off list below).
- Self-splash death killer per reopened Q1's ruling (pin whatever
  line it settles on).
- Sabotage-prove the DEFEAT-pin (disable the hook → test fails).

**Stop point — do NOT start**

- No in-game tombstone browser/viewer (v1: files are the surface).
- No sibling markdown format (ruled out, SETTLED 1).
- No per-session damage accounting (career total only).
- No MessageLog capacity change (dissolved — full history already
  retained).
- No non-combat death paths or causes invented.
- No v2 "THE FIGHT" section (per-source damage breakdown).

**Playtest checkpoint (numbered, in-game)**

1. Dev-grant a ground fight you lose (armory + hostile delve pack).
   EXPECT: death screen shows the tombstone line with the FULL
   filename; the file exists under `~/.spacehack/saves/tombstones/`;
   header = species/class, level, real time, game clock, location,
   Slain-by with enemy + weapon, damage tally, run seed, ground
   final state; kit lists both weapon sets + armor + bandolier +
   pack + SHIP weapons/modules; full log, oldest first.
2. Die in space combat. Same expectations, space final state
   (hull/shields).
3. Win a fight. EXPECT: no tombstone written (DEFEAT only).
4. Save → quit → continue around a won fight. EXPECT: autosave
   intact, no tombstone side effects.
5. Guide diff: NONE proposed — the death-screen line is the teacher
   (guide = controls/core mechanics; the existing destruction
   mention is untouched). Ruling recorded here for review.

## Open questions (reopened 2026-09-26 by the ADVISE review — brief
on hold until ruled)

1. **Self-splash killer line** — `explosive_blast` player damage
   (`combat/_rules_ground.py:510-511`) sets no attacker, so a splash
   suicide names a STALE enemy (if one hit you earlier in the fight)
   or reads "unknown causes". Splash suicide is a first-class doc-50
   death class (the overview cites it). Options: track a
   self-inflicted line at the splash site vs clear-to-fallback on
   self-damage.
2. **Damage-tally honesty** — `total_damage_taken` increments only
   on space hull damage (`combat/_ai.py:497`, sole site; no
   progression reader exists, so extending is gameplay-neutral).
   Extend to the two ground sites (`_rules_ground.py:511` splash,
   `:861` enemy fire) for a true career total, or relabel the header
   line "Hull damage taken (career)".
3. **City death screen** — city hostile-bump fights write the
   tombstone (they route through `_finish_combat`) but on DEFEAT
   `raise SystemExit()` with NO death screen (`city_npcs.py`) — a
   pre-existing UX gap the "full filename on the death screen"
   ruling silently fails into. Route city defeat through the shared
   death screen, or record the exception as a ruling.
4. **Exact new strings for sign-off** (prose gate): fallback
   `Slain by: unknown causes`; the self-splash line per Q1
   (proposed `Slain by: your own explosives`); section labels per
   the SETTLED 1 mock (THE SHEET / THE KIT / MESSAGE LOG).
