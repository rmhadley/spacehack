# DESIGN: Tombstones — death review files

**Status: REFINED 2026-09-26 — SETTLED 1 + SETTLED 2 recorded, no
open questions; phase 1 Implementation brief APPROVED (below).
Ready for `/implement-phase 53.1`. Nothing implemented.**

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
  Damage taken (career): space <total_damage_taken>,
                        ground <ground_damage_taken>
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
  - **Damage tally** — reads BOTH counters, one line: space
    `ctx.player_counters.total_damage_taken` (as tracked today:
    SPACE damage only — `_ai.py:497` is the sole increment site,
    ADVISE correction) + the NEW ground metric settled in SETTLED 2.
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

## SETTLED 2 (2026-09-26, user — the ADVISE-review rulings: splash killer, tally metric, city screen)

> Splash: "Self-inflicted line". Tally: "that damage tally counter
> is for another feature in the game. I'm ok with tallying ground
> damage too, for a different trait it could even be useful, but
> it'd have to be a new separate metric." City: "Shared screen".

- **Splash killer RULED — self-inflicted line**: the self-splash
  site (`combat/_rules_ground.py:510-511`) sets the tracked attacker
  to a self-inflicted line; approved wording
  `Slain by: your own explosives` (seen and chosen in the ruling
  option). Pinned by test; a splash suicide never names a stale
  enemy nor "unknown causes".
- **Damage tally RULED — a NEW, SEPARATE ground metric**:
  `total_damage_taken` belongs to the doc-2 XP/trait feature and
  stays SPACE-only — never piggyback it. (Correction of the
  session's earlier "nothing reads it, extend is neutral" claim:
  trait requirements read counters BY FIELD NAME from data —
  invisible to an identifier grep — and the user knows the
  feature's intent.) The tombstone's ground tally comes from a NEW
  `PlayerCounters.ground_damage_taken: int = 0`, incremented at the
  two ground damage sites (`_rules_ground.py:511` splash, `:861`
  enemy fire) — a first-class counter a future trait can require.
  Header reads both: `Damage taken (career): space <n>, ground <m>`.
- **City deaths RULED — shared death screen**: city hostile-bump
  DEFEAT routes through the same full-screen death frame as both
  other theaters (the full-filename line holds everywhere), then
  exits — closing the pre-existing gap where city deaths showed no
  death screen at all.
- **Strings approved this session** (prose gate satisfied):
  `Slain by: unknown causes` (no-attacker fallback),
  `Slain by: your own explosives` (self-splash), section labels per
  the SETTLED 1 mock.

## Phases

- [ ] 1. **The tombstone writer** — the module (format + sections +
  log export), the death-path hook (both theaters), file placement,
  tests (format pins, both death paths write, log stripping, killer
  line, failure-is-nonfatal). Brief at refine time.

### Phase 1 Implementation brief (APPROVED 2026-09-26, user)

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
    `ctx.player_counters.total_damage_taken` +
    `ctx.player_counters.ground_damage_taken` (SETTLED 2's new
    metric; the header line shows both), `engine.INIT_SEED`,
    `facts`; sheet from pilot skills + ground stats + traits (same
    accessors the character screen uses);
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
- NEW ground tally metric (SETTLED 2): `game_context.py`
  `PlayerCounters` gains `ground_damage_taken: int = 0`, declared
  in the owning module; incremented at the two ground player-damage
  sites (`_rules_ground.py:511` self-splash, `:861` enemy fire —
  after the `ground_damage_taken(ctx, …)` DR call, on the applied
  amount). SAVE/LOAD CONTRACT: the write side serializes the
  dataclass wholesale, but `saveload.load_game`'s rebuild names
  counter fields EXPLICITLY — add
  `ground_damage_taken=pc.get("ground_damage_taken", 0)` there
  (old saves default 0). `total_damage_taken` is NOT touched
  (doc-2 trait feature, space-only by ruling).
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
  - city (SETTLED 2): `city_npcs.py`'s DEFEAT branch awaits the
    shared death screen (`_show_ground_defeat`) BEFORE its exit —
    the full-filename line holds in all three theaters, and the
    pre-existing no-screen gap closes.
  - Long-path note (ADVISE): a HOME-heavy full path can exceed the
    100-col grid — clip or wrap at the screen seam (build-session
    call).

**Build order**

1. `tombstone.py` pure builders + `build_tombstone_text` + format
   pin tests (no combat needed).
2. Log export test (runs-bearing entry → text-only in output).
3. `last_attacker` tracking (both sites) + `CombatResult.tombstone_path`
   + the `ground_damage_taken` counter (owning-module field, both
   increments, load-side rebuild) + its round-trip test.
4. `_finish_combat` hook + `write_tombstone` I/O + filename
   collision suffix test.
5. Death-screen lines at all three sites (incl. city routing).
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
`.md` renderer a cheap later add, not built now). SETTLED 2 adds:
self-splash killer line `Slain by: your own explosives` (tracked
at the splash site, never a stale enemy); the ground tally is a
NEW `ground_damage_taken` counter — `total_damage_taken` stays
space-only (doc-2 trait feature, untouched); city DEFEAT joins the
shared death screen before exit.

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
- Self-splash death killer: header reads `Slain by: your own
  explosives` (SETTLED 2 wording; pin it).
- Ground counter: increments at both ground damage sites (enemy
  fire, self-splash); save/load round-trip carries
  `ground_damage_taken` (old save without the key → 0).
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
   Slain-by with enemy + weapon, damage tally (space + ground
   lines), run seed, ground final state; kit lists both weapon
   sets + armor + bandolier + pack + SHIP weapons/modules; full
   log, oldest first.
2. Die in space combat. Same expectations, space final state
   (hull/shields).
3. Win a fight. EXPECT: no tombstone written (DEFEAT only).
4. Save → quit → continue around a won fight. EXPECT: autosave
   intact, no tombstone side effects.
5. Die to a city hostile-bump fight (pick a fight with an armed
   city NPC). EXPECT: the SAME full death screen + tombstone line
   as the other theaters (SETTLED 2's closed gap), then exit.
6. Guide diff: NONE proposed — the death-screen line is the teacher
   (guide = controls/core mechanics; the existing destruction
   mention is untouched). Ruling recorded here for review.

## Open questions

None open — all four reopened by the ADVISE review and ruled in
SETTLED 2. v2 candidates parked in the stop point (in-game browser,
per-source damage breakdown, sibling `.md` renderer).
