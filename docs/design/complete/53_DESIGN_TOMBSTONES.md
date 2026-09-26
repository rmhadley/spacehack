# DESIGN: Tombstones — death review files

**Status: CLOSED 2026-09-26 — both phases landed and playtest-passed;
moved to complete/; SYSTEMS.md inventory amended in the same commit
(Death & share artifacts, theater-split damage tallies, ESC pause
menu action-surface row).**

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

## Contents (v1 — SETTLED 1, wording pass 2026-09-26)

*Wording pass (user, post-phase-1 playtest, verbatim): drop the
"REST IN PEACE —" header prefix and " (real time)"; section labels
"THE SHEET" → "CHAR", "THE KIT" → "GEAR"; "Bandolier" line → "Ammo".*

```
================================================
  <species> <class>
  Level <L> — died <YYYY-MM-DD HH:MM>
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

  CHAR: level + XP, pilot skills, ground stats,
        traits
  GEAR: both weapon sets (id + quality + loaded
        ammo), armor slots, ammo reserves,
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

## Pre-implementation audit (2026-09-26, before phase 1 code)

**1. Existing classes / modules to extend or reuse** (all verified in
code this session):

- `saveload._saves_dir()` (`saveload.py:26`) — resolves
  `~/.spacehack/saves/`; tombstones are its `tombstones/` subdir.
  `delete_save()` is already sequenced by the shared finish.
- `combat/_loop.py::_finish_combat` (`:625`) — the ONE finish for both
  theaters; already does sync_state → DEFEAT-gated `_delete_save()` →
  `CombatResult` build. The write inserts before `_delete_save()`,
  path stashes on the result — exactly the brief's sequencing.
- `CombatResult` (`combat/_types.py:82`) gains `tombstone_path`;
  `SpaceCombatState` (`_types.py:104`) and `GroundCombatState`
  (`_rules_ground.py:124`) each gain `last_attacker` in their owning
  module (dataclass-field cohesion rule).
- Killer sites (ADVISE-corrected): space `_ai.py::_apply_enemy_hit`
  (`:487` — `_ei.name` + `_e_ws.name` in scope, counters site `:497`);
  ground `_rules_ground.py::_spend_one_enemy_turn` (`:832`, damage +
  death-detect at `:859-863`); self-splash `explosive_blast`
  (`:502-511`).
- Death screens: `_encounter.py::_handle_combat_encounter` DEFEAT
  (`:233-235`; `_render_death_screen(ctx, *, lines)` already takes
  lines); `game_flow.py::_show_ground_defeat` (`:224-238`, lines
  tuple in scope); `city_npcs.py::run_city_fight` (`:389-390` —
  confirmed: `raise SystemExit()` with NO screen today; SETTLED 2's
  gap is real).
- Label seams to reuse verbatim (no new formatter):
  `ground_equipment.display_name("weapon", id, quality)` (the exact
  call `_ai_ground._present_enemy_shot` uses — killer-line parity),
  `ship.weapon_display_name`, `ship.module_display_name`
  (randart-aware). Magazine readout from
  `GroundWeaponInstance.loaded_ammo` + `find_ground_weapon().ammo_capacity`;
  ship slot ammo from `OwnedShip.weapon_ammo` (slot-keyed).
- Sheet accessors: pilot skills `ctx.stats.{gunnery,piloting,engineering}`,
  ground stats `ctx.ground_stats.{reflexes,strength,stamina}`,
  traits via `data.traits.core.trait_name` (resolves both registries —
  the `character_screen_stats._trait_names` pattern); XP curve
  `xp.xp_for_level`.
- Location: `game_loop._present_frame:127-132` is the HUD ladder —
  deliberately NOT reused (wrong 'Derelict Ship' default per ADVISE).
  Tombstone precedence: `getattr(game_map, "location_name", "")` →
  city fallback gated on `game_map.city_transit is not None` (the
  city-only field, `world.py:408` — a space map never carries it, so
  a space death can never print a stale city) → system-only.
- `MessageLog.history()` (`message_log.py:175`) — complete log,
  oldest-first; `entry.text` drops `runs`/`fg` for free.
- `engine.INIT_SEED` (`engine.py:42`) — save-persisted run seed.
- Test harness: `tests/balance/harness.py` — `begin_run` +
  `_mirror_loop` (calls the real `_finish_combat`) +
  `_inert_presentation` + `_sandboxed_home`; reuse for both-theater
  integration tests, reading the tombstone back out of the sandboxed
  HOME.

**2. Three potential duplication hotspots:**

1. Weapon labels — three label seams already exist (ground display
   name, ship weapon name, ship module name); tombstone must not grow
   a fourth bespoke `name + quality` formatter.
2. Location line — the HUD ladder in `game_loop` looks copy-pasteable
   but carries the wrong default; blind reuse imports the bug.
3. Final-state readout — space state lives in a dict
   (`_state.player_state["shields"]`); reaching into it from the
   finish would fork the accessor convention (`player_hp(ctx)` etc.).

**3. DRY strategy per hotspot:**

1. Reuse the seams verbatim; the ground killer line repeats the
   `display_name("weapon", id, quality)` call shape (a one-liner, not
   a wrapped helper).
2. Tombstone resolves location through its own precedence chain,
   documented with the ADVISE citation; shares nothing with the HUD
   ladder by design.
3. Extend the accessor family: `player_shields(ctx)` beside
   `player_hp` in `_rules_space`; `last_attacker(ctx)` on BOTH rules
   modules (mirroring `player_hp(ctx)`) so `_finish_combat` stays
   rules-agnostic. Counters increments stay one-liners at each site —
   the `_ai.py:497` `total_damage_taken` shape (a helper for `+=`
   would be ceremony).

**Audit surprises (recorded, not silently fixed):**

- `saveload._parse_counters` (`:627`) did not rebuild `railgun_kills`
  or `focused_shots` — pre-existing silent reset on load, OUT of this
  phase's scope (`total_damage_taken` stays untouched by ruling);
  flagged to the user at the checkpoint as a found bug. [RESOLVED as
  its own commit 82eda76f the same session — both counters now
  rebuild, pinned in the old-save-default test.]
- `game_map.location_name` is a runtime-attached attribute
  (grandfathered pattern; `saveload_maps` serializes it) — read via
  `getattr`, never assumed.
- The kit's "both weapon sets" need NO `partition_weapon_sets` call —
  doc 51 made the partition REAL state
  (`ctx.equipped_ground_weapons` / `ctx.holstered_ground_weapons`);
  the builders read the two fields directly and label them with
  `ground_weapon_sets.SET_CLASSES`/role vocabulary.
- IN-COMMIT RATCHET PAYMENT (implementation surprise): the phase's
  ground additions pushed `_rules_ground` from 979 to 1010 lines —
  the blast cluster (`is_explosive` + per-enemy shares + the
  friendly-fire self splash) extracted to `combat/_ground_blast.py`
  with the combat state passed explicitly and the rules module's
  public signatures kept as thin wrappers (e89aa124, behavior-
  preserving per the reviewer's verification). `_ai._apply_enemy_hit`
  (41 lines) split its destruction-presentation tail; the space
  death-line append lives in `_encounter._space_death_lines` so
  `_handle_combat_encounter` stays within the function limit.
- REVIEWER (5.3, REVIEW) verdict on the working tree:
  REQUEST_CHANGES, one blocking — the space DEFEAT call passed the
  notice ALONE as `lines`, so a successful write dropped the classic
  destruction lines and rendered the path at title size (the ground
  sibling appended correctly). Fixed to `_DEATH_LINES + notice`
  (both theaters append, notice is body text); the test pin now
  asserts the full four-line tuple. Minors: doc-header staleness
  (this update), a five-site KeyError-degrade folded to a `_lookup`
  seam + one `.get` (4 of 5), record correction on the module size
  (979 pre-phase, not "over 1000").

## Phases

- [x] 1. **The tombstone writer** — the module (format + sections +
  log export), the death-path hook (both theaters), file placement,
  tests (format pins, both death paths write, log stripping, killer
  line, failure-is-nonfatal). Brief at refine time. PLAYTEST PASSED
  2026-09-26 (checklist walked during the session; the user's wording
  pass landed 35607bcb + 25d2089a: no "REST IN PEACE —", no
  " (real time)", CHAR, GEAR, Ammo).

- [x] 2. **Char dump — the living sibling** (PROPOSED 2026-09-26 from
  the phase-1 playtest: "would be nice if there were a char dump
  option. Maybe in the esc menu? esc -> save/exit, dump char log? So
  that a player could share their current game state with a friend
  for advice"). Brief APPROVED same day — rulings below. LANDED
  8d4cee75 + PLAYTEST PASSED 2026-09-26 ("playtest good" — the
  pending-strings list 1-8 approved as built in the same play).

### Phase 2 Implementation brief (APPROVED 2026-09-26, user)

**Rulings (user, same day): contents = full state minus death facts;
acknowledgment = small modal naming the full path; rows "Save & Exit
/ Dump Char / Keep Playing"; file
`~/.spacehack/saves/chardumps/chardump-<stamp>.txt`. Strings approved
verbatim (preview sign-off): header identity line `<species>
<class>`; `Level <L> — dumped <YYYY-MM-DD HH:MM>`; clock+location,
career tally, and seed lines as in the tombstone; modal title
`CHAR DUMP`, body `Char dump saved: <full path>`, item `Continue`.**

**Scope**

- `tombstone.py` gains the dump twins beside the death path:
  `build_char_dump_text(ctx)` (dump header + the SAME
  `_char_lines`/`_gear_lines`/`_log_lines` — no new section builders)
  and `write_char_dump(ctx) -> str | None` (same best-effort I/O,
  same collision-suffix pattern; the two writers share one artifact
  shell). The dump header is the tombstone header minus the death
  facts: no killer line, no final state.
- ESC menu: `_run_pygame_exit_confirm`'s two-row confirm becomes a
  three-row pause menu (the shared `pygame_menu.MenuFrame`):
  Save & Exit / Dump Char / Keep Playing. ENTER on the dump row
  writes the file, shows the CHAR DUMP modal, and returns to the
  game (never exits, never saves). Wiring in `game_flow` +
  `game_loop`'s ESC handler.
- Guide: the ESC row is a controls-adjacent change — review the
  guide's ESC/menu section and edit if it names the old two-row
  confirm; the diff rides the checkpoint handout.

**Build order**: dump writers + content pins → menu + wiring +
tests → gate → reviewer → checkpoint handout.

**Stop point**: no in-game dump VIEWER (files are the surface, same
as v1); no auto-dump on events; no share-button integration.

**Playtest checkpoint (phase 2 — build done, gate green, reviewer
verdict resolved except the prose-gate hold below)**

PENDING STRING SIGN-OFF (reviewer blocking: the complete
unapproved-strings list — the commit waits on the user's word):

1. Pause-menu title `PAUSE`
2. Pause-menu body `Save and return to the main menu, or dump your
   current state?`
3. Dump Char row description `Write your current state to disk to
   share.`
4. CHAR DUMP hint `ENTER continue`
5. Write-failure modal body `Char dump failed to write.`
6. Guide city row: `- ESC: save and exit to the main menu (asks
   first)` → `- ESC: pause menu (save & exit, dump char)`
7. Guide space row (stale BEFORE this phase — ESC opens the pause
   menu in space too; the ship menu is bumping the parked ship):
   `- ESC: ship menu` → `- ESC: pause menu`
8. Guide Start Here alignment: `Save often. ESC asks before saving
   and returning to the main menu.` → `Save often. ESC opens the
   pause menu (save & exit, dump char).`

In-game checklist (numbered):

1. ESC in a city: EXPECT the pause menu (Save & Exit / Dump Char /
   Keep Playing); Keep Playing and ESC-dismiss both return to the
   game with nothing saved.
2. Dump Char: EXPECT the CHAR DUMP modal naming the full path under
   `~/.spacehack/saves/chardumps/chardump-<timestamp>.txt`; the file
   exists; header has NO Slain-by/Final-state lines; CHAR + GEAR +
   full log as in a tombstone; the run continues untouched.
3. Dump twice within a second: EXPECT the `-2` suffix on the second
   file.
4. Save & Exit via the menu: EXPECT the pre-existing save/exit flow.
5. Window-close (not ESC): EXPECT the unchanged immediate save+exit.
6. Space mode ESC: EXPECT the same pause menu (the stale guide's
   "ship menu" line is fixed by edit 7 above).
7. Guide: read the three edited lines (6/7/8) — diffs above.

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
