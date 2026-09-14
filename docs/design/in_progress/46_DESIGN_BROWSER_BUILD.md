# DESIGN: Browser Build — pygbag, with Desktop as the Invariant

**Status: DESIGN IN PROGRESS — no implementation until the user
explicitly requests it.** Scope doc from the 2026-09-13 assessment
session; the spike (phase 0) is the go/no-go.

Companions: `DESIGN_PYGAME_RUNTIME_MIGRATION.md` (doc 16 — how the
game got onto pygame-ce in the first place; that migration is why
this doc is small).

## The requirement this doc serves (user, 2026-09-13)

> #1 requirement here is to not degrade the current play
> experience.

The desktop build is the invariant every phase is gated against.
The browser build is a second output of the same game — never a
trade against the first.

## Requirement #1, operationally

1. **Native path unchanged.** Wheel + `run.py` venv launcher +
   PyInstaller spec + homebrew tap stay exactly as they are.
   `make web` is a new sibling target, never a replacement step.
2. **Feel-identical desktop after every phase.** Frame pacing
   (vsync + `clock.tick`), input latency, and animation timing are
   the invariant. Phase 1 is the only phase that touches the
   desktop loop; it lands with a measured before/after AND a full
   desktop playtest pass BEFORE any web-only code exists. If feel
   differs, the phase reverts — no "close enough."
3. **Saves untouched on desktop.** Same `~/.spacehack/saves/`
   location, same JSON format, same `saveload.py` API. The web
   storage backend is an output-target swap behind one choke point,
   not a format change.
4. **pygame-ce never held back for web's sake.** If a desktop-side
   pygame-ce upgrade outpaces pygbag's prebuilt wasm wheels, the
   WEB build waits; desktop ships. Lockstep is desired, desktop
   priority is the rule.
5. **Desktop stays the only dev surface.** Dev mode, seed pinning,
   text overlay, `SPACEHACK_*` flags, `make check`, and all
   playtests live on desktop. Nothing dev-side moves into the
   browser bundle.
6. **Content parity.** The web build ships the same data bundle —
   no web-specific content, balance, fonts, or UI. The guide gets
   no browser entries (the game is the game).

## Measured port surface (2026-09-13)

Why this is a packaging project, not a rewrite:

- ~80k LOC / 294 files of pure Python. **Sole runtime dependency:
  pygame-ce ≥ 2.5.8** — the flavor pygbag's wasm builds support.
  No numpy, no own C extensions, **no audio/mixer at all**, no
  sockets, no threading in shipped code, no asyncio yet.
- **Only four files pump input events:**
  `pygame_runtime.py` (the one central `while True` loop),
  `pygame_engine.py` (per-frame drain),
  `navigation_travel.py` (modal loops + a sleep-poll helper),
  `combat/_animations.py` (sleep-poll helper). 5 timing calls
  total. The async conversion is a sweep of four files.
- **Filesystem surface is tiny:** 9 `open()` sites; saves are JSON
  through the single `_saves_dir()` choke in `saveload.py`.
- **Data is 3.6 MB / 554 files** loaded via `importlib.import_module`
  of bundled Python modules (planet specs, city data, missions) +
  `.layout` files + bundled ttf fonts — all fine under pygbag's
  virtual filesystem.
- Tests (~42k LOC), `tools/`, and `make check` never run in a
  browser and are not ported.

## Rulings

**Ruling 1 (user, 2026-09-13): all `os.environ` reads are 100%
desktop-only. The browser build runs flagless — zero flag
plumbing, no query-param shim.** Every read is an optional gate
whose absent-branch IS the shipped player path: 13× `SPACEHACK_DEV`
gates (game_loop, dev_mode, title_flow, npc_ships), the
`SPACEHACK_SEED` pin (absent = random seed — normal new-game
behavior), `SPACEHACK_TEXT_DIR` (dev overlay override), and one
harmless `SDL_RENDER_SCALE_QUALITY` setdefault. If browser dev
shortcuts are ever wanted, one query param does it — a later want,
not part of this port.

**Ruling 2 (this doc): pygbag over the existing codebase.**
Rejected: a TypeScript/web rewrite (reimplementing 80k lines plus
the data toolchain to preserve a proven engine), and hosted
streaming (server cost + latency for a single-player game). The
result is a static bundle hostable anywhere a header-capable host
will take it (itch direct with its experimental SharedArrayBuffer
toggle, or a `_headers`-capable static host; GitHub Pages ruled out
2026-09-14 — no custom response headers, and the wasm runtime's
SharedArrayBuffer requirement makes COOP/COEP unavoidable) —
user-run ops, outside the container.

**Ruling 3 (this doc, subordinate to requirement #1): ONE async
path, no dual loops.** The frame pump yields to the event loop each
frame; on desktop `asyncio.run(main())` drives it with
`clock.tick()` still the pacer — pacing identical by construction,
and verified by measurement anyway (phase 1 exit gate). If
verification fails, the phase does not land; there is no
platform-conditional loop fallback.

**Ruling 4 (user, 2026-09-14): phase-3 verification is LOCAL/LAN
only — a header-serving local static server is the exit target.**
Hosting (itch with its experimental SharedArrayBuffer toggle, or a
`_headers`-capable static host) is a later want, user-run per
Ruling 2; the bundle ships host-ready but unshipped. GitHub Pages
is out: it cannot set custom response headers, and the wasm
runtime's SharedArrayBuffer requirement makes the loader's
COOP/COEP need unavoidable (measured, phase-0 defect 1). The
phase-3 exit gate is therefore amended: "plain" (header-less)
static servers stall the loader by construction.

**Ruling 5 (user, 2026-09-14): the shipped bundle is
self-contained — `make web` mirrors the pinned pygame-ce wasm
wheel (1.5 MB) into the bundle.** The player's first load touches
nothing third-party (requirement #1's spirit; mirroring already
proven mechanically in phase 0). pygbag's CDN stays a build-time
concern only.

## Phases

Build queue — unchecked in order; the spike gates everything.
Requirement #1's ordering is structural: phase 1's desktop
verification gate closes before any web-only code is written.

### Phase 0 — spike / go-no-go

Boot the REAL title screen under pygbag — `src/` on main untouched
(this phase cannot degrade anything by construction). Measure and record: (a) payload size + first-load
time (expect ~15–25 MB: wasm CPython runtime + game; cached after),
(b) new-game world-gen freeze under wasm vs native, (c) per-move
lighting-recompute latency under wasm vs native, (d) pygame-ce ↔
pygbag wheel alignment at the current pin (≥ 2.5.8). Exit: the four
numbers in this doc + an explicit go/no-go. Pure-Python under wasm
runs ~3–8× slower; at human input rates that is almost certainly
fine — the spike exists to prove it, not assume it.

**Brief (approved 2026-09-13):**

- *Scope.* Build staging happens OUTSIDE the repo (/tmp: `main.py`
  + a `src/` copy); a `spike/pygbag-46` branch exists only if
  `src/` needs a patch, and it never merges. `pygbag` installed ad
  hoc — no pyproject/requirements change until the go ruling.
  Scratch `main.py` entry (`async def main()`, pygbag convention).
  A minimal yield-per-frame patch to the four event-pumping sites
  is the throwaway phase-1 prototype and is attempted ONLY if an
  unpatched boot hangs — cheapest honest boot wins.
- *Build order:* pin alignment → shim (+ patch if needed) + desktop
  sanity boot → `pygbag build` + serve → browser-automation play
  (title → new game → planet → N moves) → record (a)–(d) → tick.
- *Tests:* no shipped code, no new tests; `make check` green on
  main and on any branch commit.
- *Stop point:* recorded numbers + recommendation handed to the
  user for the go/no-go ruling. Not started: phase 1 landing,
  desktop A/B work, persistence shim, `make web`.
- *Playtest checkpoint:* none — no shipped behavior; the handoff
  IS the numbers. Guide edits: none.

- [x] pygbag installed; pygame-ce ↔ pygbag pin verdict recorded (d)
- [x] entry shim boots the title screen under wasm — boot + run
      proven by beacon trail; visual paint required the async
      pattern (round 4), which is phase 1's prototype
- [x] (a) payload + first-load recorded; (b) world-gen and
      (c) per-move moved to phase 1's desktop verification (the
      sync build cannot present by construction — see round 4)
- [x] numbers + GO recommendation in this doc; ruling requested

**Run log (2026-09-13, container spike — staging in /tmp, `src/`
untouched, zero commits outside docs):**

- Payload (a), measured: game bundle transfers as `sh46.tar.gz`
  = **1.02 MB** (apk 1.28 MB packed — all 524 src/data entries);
  wasm CPython 3.12 runtime `main.wasm` = **13.4 MB**; pygame-ce
  wasm wheel = 1.5 MB; BrowserFS shim = 0.24 MB. First-load total
  ≈ **16.2 MB**, inside the 15–25 MB forecast, dominated by the
  runtime, not the game.
- Pin verdict (d): pygbag 0.9.3 provides pygame-ce **2.5.7**
  wasm32/emscripten on CPython 3.12 — **one patch behind** the
  repo's ≥ 2.5.8. Desktop keeps 2.5.8 regardless; whether 2.5.7
  suffices is decided by the boot proof.
- Boot-chain findings — three defects in the DEFAULT 0.9.3
  template, each verified in-browser via console capture, each
  with a bounded workaround: (1) the loader requires
  crossOriginIsolated (COOP/COEP headers) — a plain static server
  stalls it; (2) the template references `browserfs.min.js` on the
  CDN although the CDN removed it ("removed, must be fully
  provided from template") — the app bundle must ship it;
  (3) the wheel URL resolves against the page origin
  (`<origin>/cdn/cp312/…`) — the pygame-ce wheel is mirrored
  locally. Progress proved stepwise: "BrowserFS not found" →
  found → apk mounted → wheel fetched → install began.
- BLOCKER at handoff: once the wheel install starts, the page's
  main thread pins for 4+ minutes with no further output
  (headless Chromium, container). A crash would free the thread;
  a finished import would boot — the desktop test discriminates
  slow-import vs hang. (b) world-gen and (c) per-move latency are
  queued behind the boot proof.
- Packaging-fragility read: the three template defects carry real
  phase-3 scope (`make web` must own headers + browserfs + wheel
  mirroring), but all are bounded; none flip feasibility by
  itself.
- **Round 2 (instrumented, container): the game RUNS under wasm.**
  Beacon trail proves the full chain: wheel install → all 133
  spacehack modules import (~instant) → `main()` → splash
  animation loop alive at rAF rate under a real compositor (xvfb),
  draw + present + poll every iteration; SDL queue receives
  browser mouse events. Earlier "4-min pin" reports were
  `pygame.event.wait()` never returning, not slowness.
- **THE PATHOLOGY (spike's key finding, A/B-proven):** under this
  pygame-ce wasm build, blocking waits are each fatal in their own
  way: `pygame.event.wait()` NEVER returns (hard pin, zero
  output); `pygame.time.wait(16)` returns instantly WITHOUT
  yielding (busy spin at ~1700 iter/s: browser starved — no paint,
  no input = the desktop "gray page"); `time.sleep(0.016)` unwinds
  via emscripten_sleep and hands the browser a real frame
  (rAF-rate ticks; queued input delivered). Headless chromium
  additionally throttles rAF to ~0 without a visible surface —
  container-only artifact; xvfb headed runs real-rate.
- **Phase-1 consequence (binding): the async/yield conversion is
  REQUIRED for playability, not an optimization.** Conversion
  surface = the blocking-wait inventory of the four event-pumping
  files (`pygame.event.wait()` + `clock.tick` + animation sleeps),
  matching Ruling 3's one-async-path. The spike's staging patch
  (splash loop: get + time.sleep) is the prototype pattern.
- Still pending: desktop confirmation that paint + keyboard reach
  the SDL layer through a real browser (mouse proven in-container);
  then (b) world-gen and (c) per-move latency.
- **Round 3: SDL video fully works under wasm.** With vsync
  bypassed under emscripten, beacons prove
  `driver:emscripten surf:(1600, 960)` — set_mode + the Window API
  complete on the emscripten backend. Container ceiling reached:
  under xvfb, CDP can neither dispatch keyboard nor evaluate once
  the asyncify loop runs (only real window-pipeline input gets
  through), and screenshots never composite — so paint and
  keyboard-on-desktop are decidable only by the user's browser.
  Desktop round 3 tested the vsync-off bundle: still gray, as the
  next round explains.
- **Round 4 — presentation PROVEN, verdict reached.** Desktop
  round 3 confirmed gray with vsync off, as staged. A minimal
  async proof app (staging main.py only: set_mode 800×600, fill,
  flip, `await asyncio.sleep(0)` per frame) through the SAME
  bundle pipeline: all frames present — the browser screenshot
  shows the app's exact fill color, and screenshots that never
  composited under the sync loop now land instantly (the
  compositor is alive when the JS stack fully returns each frame).
  Root cause chain closed: sync loop = partial asyncify unwind =
  no frame commit = gray page, regardless of vsync. **Phase-0
  verdict: GO** — phase 1 (the Ruling-3 async conversion) is both
  the fix and the only remaining mechanism risk, and its pattern
  is now proven end-to-end in-container. (b) world-gen and
  (c) per-move latency move into phase 1's desktop verification:
  by construction the sync build can never present, so the
  measurements belong to the converted build.

### Phase 1 — one async path

Convert the four event-pumping files to yield per frame; desktop
runs the same loop under `asyncio.run` with `clock.tick()` pacing.
Exit gate (requirement #1's): measured frame-pacing and
input-latency A/B vs pre-change (dev-instrumented), plus a FULL
desktop playtest pass. No web-only code in this phase.

**Brief (approved 2026-09-13):**

- *Principle:* convert only what parks — a function becomes a
  coroutine iff it can block waiting for input or time; algorithm
  `while True` loops (npc, autoexplore, loot, lighting…) stay sync.
- *Canonical pattern:* `event.wait()` → `event.get()` poll +
  `await context.pump()`; frame-path `time.sleep(x)` →
  `await asyncio.sleep(x)`; `pump()` = one new primitive on
  `PygameContext` (`await asyncio.sleep(seconds)`) — web: full
  JS-stack return → rAF → present commit + input; desktop: one
  event-loop yield, semantics unchanged (the desktop loop is
  event-driven; there is NO clock.tick anywhere).
- *Build order:* baseline capture (dev-instrumented loop timings,
  pre-change) → `pump()` + tests → leaf runners one commit each
  (faction, quantity, quest_log, screen, menu, navigation, split)
  → title/title_flow → navigation_travel + combat/_animations →
  runtime poll + game_loop + `__main__` entry → test updates ride
  → desktop A/B gate → full desktop playtest.
- *Tests:* updated runner tests ride each commit; new `pump()`
  tests (desktop yields without timer, deterministic fake);
  `debug_session` stays untouched (audit-verified: no UI calls).
- *Stop point:* desktop A/B measured + full desktop playtest
  passed. NOT in this phase: persistence shim, `make web`, any
  web integration, `sys.platform` branches.
- *Playtest checkpoint:* numbered desktop checklist with expected
  results + the A/B numbers table. **Guide edits: none.**

**Pre-implementation audit (2026-09-13, before code):**

1. **Extend/reuse:** `PygameContext` (pygame_runtime) gains
   `pump()`; the existing timeout poll path
   (pygame_runtime.py:254–262, poll + 16 ms sleep) is the
   canonical shape every runner replicates via ONE shared async
   helper — `poll_events` itself becomes async rather than each
   runner re-rolling the pattern; `animation_timing._SPEED_SCALE`
   continues to scale animation delays (now asyncio.sleep);
   `tests/support/fake_pygame.py` fakes gain async-capable
   pump/poll doubles.
2. **Duplication hotspots:** (a) poll+pump re-rolled per runner —
   prevented by the shared async `poll_events`; (b) platform
   branches — forbidden by Ruling 3, `pump()` is the single seam;
   (c) per-test `asyncio.run(...)` wrappers — extract a
   tests/support helper if ≥3 sites repeat.
3. **Cascade map (await transitive closure):** 15 runner defs in
   8 modules (split, quantity, title+splash, navigation, menu,
   faction, screen, quest_log) + `pygame_runtime.poll_events` +
   `title_flow` + `game_loop` central loop + `__main__` entry;
   direct runner call sites ~25 in 17 modules (help,
   trait_screen, menus/_ship_menu|_missions|_quest_log|_planet|
   _mechanic|_ship_buy, dev_mode, pygame_story, navigation_travel,
   city_transit, character_screen, trade, console_log, comms ×3,
   npc, input_helpers ×2) + the game_loop dispatch tables (their
   handlers go async; dispatch awaits). Menu-retry `while True`
   loops (input_helpers, menus/*) cascade by containing a runner
   call. Algorithm loops (npc, autoexplore, loot, lighting,
   dungeon_activation, main_quest, rumor, trade internals) stay
   sync. `debug_session.py`: verified zero UI calls — untouched.
   *(Annotation, 2026-09-13: the conversion became necessary anyway —
   debug_session transitively calls `tutorial.notify_move` and
   `dungeon_extensions.tick_activation`, which went async; leaving it
   sync would silently drop those coroutines. Reviewer-verified.)*

- [x] brief approved (this section)
- [x] one async path landed; measured pacing/input A/B identical
      (idle 200ms cadence 0.2162s sync → 0.2117s async, deadline-paced;
      event throughput 0.003 → 0.005 ms/event — +2µs, ~0.01% of a
      16.7ms frame; `tools/async_baseline.py --async`, 2026-09-13)
- [x] full desktop playtest pass recorded (user, 2026-09-13: "desktop
      playtest is good")

**Phase-1 run log (2026-09-13):**

- Landed in commit `c83d84d` after recovering a runaway session (no
  commits, game would not boot, 51 red tests). Closure method: two
  AST sweeps (async-called-bare; await-on-sync) + a handler-table
  sweep, all `iscoroutine` hedges replaced with uniform `Awaitable`
  contracts, over-converted pure lookups reverted. Reviewer APPROVE.
- **Input-loss bug found by the A/B harness itself:** `event.get()`
  drains the whole SDL queue, so the converted `wait_events` returned
  the first relevant event and silently dropped the rest of the batch
  (a fast two-key burst lost the second keystroke). Fixed with a
  retained `_event_backlog` on the runtime (one event per call, the
  old `event.wait()` contract); regression test pins a two-key burst.
- The harness's own async path had a nested-`asyncio.run` bug (never
  exercised pre-conversion) — repaired to await directly.
- **Addendum (2026-09-13, found in the phase-2-era desktop playtest):
  held-key momentum.** The backlog served one event per call from a
  branch that returned WITHOUT re-polling SDL, so repeat keydowns
  queued while a key was held sat ahead of its keyup in the backlog
  and drained one slow async move each after release ("letting go of
  a movement key should make the movement stop"). Fix: wait_events now
  polls SDL BEFORE serving the backlog each call, and a keyup drops
  that key's queued repeat keydowns from the backlog
  (`_drain_sdl_queue`/`_drop_backlog_repeats`; commit `7f7e765`).
  Fast taps keep their single press-step (presses are never purged);
  other keys' repeats survive a release. Renderer-neutral tests in
  `test_pygame_runtime.py` + the shared `FakeSdlEventQueue` double.

### Phase 2 — persistence shim

`_saves_dir()` gains a backend target: desktop unchanged (same
path, same JSON), web = IndexedDB-backed directory + sync-on-save.
Exit: the save/load/quicksave/autosave/Shift+S-reroll checklist on
BOTH targets, including quit-mid-save and reload.

**Audited surface (2026-09-13):** every save byte flows through
`Path` stdlib — `saveload._saves_dir()` (the one choke: mkdir +
`~/.spacehack/saves/`), `save_game` → `write_text(json.dumps)`
(saveload.py:389), `_load_json` → `read_text` (:400),
`save_exists` → `.is_file`, `delete_save` → `.unlink`. TWO twins:
`dev_mode._quicksave_path()` hardcodes the same saves root instead
of routing through the choke (dev-only, folds in here), and
`display_config.default_config_path()` hardcodes
`~/.spacehack/config.toml` — the TITLE OPTIONS menu's "Apply and
save" writes it (`pygame_title` → `context.save_display_config()`;
window mode + animation speed, re-read at every runtime open).
On web without persistence that silently forgets the player's
options on every reload — a play-experience degradation, so
config rides the SAME backend: the persisted thing is the
`~/.spacehack/` user-data root, not just saves.

**Brief (proposed 2026-09-13, pending approval):**

- *Principle:* the path-based stdlib surface is the contract — if
  the FS at the user-data root is durable on web, every existing
  call (mkdir/write/read/is_file/unlink) works unchanged; the only
  new machinery is (a) choosing the root and (b) flushing after
  writes. Desktop stays byte-identical: same directories, same
  JSON/TOML bytes, same write calls; the flush hook is a no-op
  there.
- *Probe first (binding, before any src change):* stage the spike
  bundle (phase-0 pattern, /tmp, repo untouched), boot the
  converted async build, write a probe file under the candidate
  root, reload the page, read it back. Outcome decides the mount
  story: (i) pygbag's runtime already persists the home dir → the
  root is unchanged `Path.home()/.spacehack` and the shim is
  flush-only; (ii) a persisted mount exists elsewhere → root maps
  there; (iii) nothing persists → explicit IDBFS/BrowserFS mount
  added to the staging entry, surfaced as a phase-3 `make web`
  requirement. Record the verdict + mechanism in this doc.
- *Scope:* new `user_data.py` — `spacehack_root()` (environmental
  selection; the codebase's ONLY platform branch, per Ruling 1 the
  browser runs flagless so detection is by platform, never by env
  var) + `sync_persistence()` flush hook (no-op on desktop;
  FS.syncfs-style flush on emscripten). Callers rerouted:
  `saveload._saves_dir()` and `display_config.default_config_path()`
  through the root; `dev_mode._quicksave_path()` through the saves
  choke (twin fold). Flush sites: after `save_game`'s write, after
  `delete_save`'s unlink, after `save_display_config`'s write.
  Nothing else.
- *Build order:* probe → verdict recorded → `user_data.py` + reroutes
  + flush no-ops + tests (one commit) → emscripten flush body per
  verdict (one commit) → staging bundle re-verified in-container
  (build + boot + write) → checklists.
- *Tests:* `spacehack_root()` returns the desktop path
  (monkeypatched platform matrix: linux/darwin/emscripten);
  quicksave + config paths ride the choke; `sync_persistence()`
  desktop no-op at all three flush sites; existing save/load
  round-trip + display-config suites stay green untouched.
- *Stop point:* no `make web` (phase 3), no new options-menu
  entries, no save export/import, no multi-slot saves, no loading
  beats.
- *Playtest checkpoint:* numbered checklist on BOTH targets —
  desktop: new game → ESC save+quit → autosave byte-identical
  shape; Continue exact-state; dev F6/F9 quicksave pair; Shift+S
  reroll sweep; save-then-immediate-quit reloads uncorrupted;
  options Apply → relaunch game → preferences hold (regression:
  config reroute must not disturb the desktop path).
  web (user's browser — container ceiling stands, phase 0 round
  3): save+quit → close TAB → reopen → Continue restores; options
  Apply → close TAB → reopen → preferences hold; quit-mid-save
  never yields corrupt JSON; Continue deletes the save (second run
  shows fresh title). **Guide edits: none** — no player-facing
  change.

- [x] brief approved (user, 2026-09-13 — including the config.toml
      user-data-root amendment)
- [x] desktop save path/format byte-identical; checklist passes on
      both targets (user, 2026-09-14: "passed, both targets" —
      desktop exact-state Continue / quicksave pair / Shift+S reroll /
      options hold; web tab-close Continue restore, options hold,
      no corrupt JSON)

**Run log (2026-09-13, in-container probe → implementation):**

- **Verdict (iii): nothing persists by default.** The 0.9.3 runtime
  is ALL-MEMFS: markers written at `/`, `/data`, `/home/web_user`,
  `/tmp` all died on reload; `FS.filesystems.IDBFS` is undefined (the
  build was not linked with `-lidbfs.js`), so the mount route is dead.
  cpythonrc sets `HOME=/home/web_user` (MEMFS) and contains no
  persistence wiring. Probe facts for posterity: `window.FS` IS the
  emscripten FS (exposed on the window global — `MM.FS` is not);
  `aio.fetch.FS` is a manifest-preloader function, not the FS.
- **Two interpreter constraints (both probe-verified, hard aborts —
  not catchable exceptions):** awaiting a JS promise from python
  aborts the interpreter; a JS→python callback firing while python is
  suspended outside the main await chain (an `ensure_future` task)
  aborts it. The callback bridge is safe ONLY in the main coroutine.
  Consequence: `restore()` (boot, main coroutine) uses the callback
  bridge; `sync_persistence` is a SYNCHRONOUS callback-less
  fire-and-forget — the IndexedDB transaction commits in JS with no
  python re-entry at all.
- **Mechanism (landed):** new `user_data.py` — `spacehack_root()`
  (same logical path on every target; no platform branch on the path,
  only the sync layer branches on `sys.platform == "emscripten"`,
  honoring Ruling 1's flagless browser); `restore()` awaited as the
  first statement of `_amain` (before tileset/config/title —
  reviewer-verified downstream ordering); `sync_persistence(path)`
  after `save_game`'s write, `delete_save`'s unlink (both branches),
  and `save_display_config`'s write. Reroutes: `_saves_dir`,
  `default_config_path`, `dev_mode._quicksave_path` (twin folded).
  `save_game` split into `_save_payload` + write (ratchet; pure
  extraction, reviewer-verified).
- **The sh46 shim API (spec for phase 3's web template — the template
  MUST inject this before the loader):**
  `window.sh46.put(name, text[, cb])`, `.remove(name[, cb])` with
  OPTIONAL callbacks (python fires them with none);
  `.get(name, cb)`, `.keys(cb)` with MANDATORY callbacks; string
  name = root-relative POSIX path; values are UTF-8 text; backed by
  IndexedDB db "spacehack", store "files".
- **In-container e2e (staging bundle, real module chain):** fresh
  page wrote autosave through `saveload._saves_dir()` +
  `sync_persistence` (callback-less, no abort); FULL page reload ran
  `restore()` and materialized the exact bytes
  (`prev={"probe": "e2e"}` — RED verdict). Durability proven through
  the real production path.
- **Rulings recorded:** shim timeout is GRACEFUL (a hung/broken shim
  never blocks play — `restore()` catches `TimeoutError` and the
  session continues without cross-reload persistence); fire-and-forget
  loss window (tab closed before IndexedDB commit = lost, never
  corrupt, save) is accepted and is exactly the quit-mid-save
  checklist case. Test divergence from the brief: no platform matrix
  on `spacehack_root()` — verdict (iii) removed the path branch, so
  the landed test pins the same path everywhere.
- Probe-infrastructure notes for phase 3: serve with
  `Cross-Origin-Embedder-Policy: credentialless` (`require-corp`
  blocks the CDN's scripts); `browserfs.min.js` and `empty.html` must
  ship locally (CDN 404s); the pygame-ce wheel fetches fine from the
  CDN (the phase-0 origin-relative defect no longer applies); python
  stdout routes to the page's xterm, NOT the browser console —
  `location.hash` is the reliable exfiltration channel; headless rAF
  throttling delays composite but never the logic.

### Phase 3 — `make web` target

pygbag packaging as a sibling of the wheel; fullscreen rides the
Window API and degrades gracefully on a fixed canvas; pygbag's
loading screen is the first-load UX. Exit: the self-contained
bundle boots and plays from the local header-serving server
(`make serve-web`, Ruling 4); desktop build artifacts and pipeline
unchanged.

**Brief (proposed 2026-09-14, pending approval):**

- *Principle:* everything the spike learned in-container becomes
  OWNED machinery — the three template defects (COI headers, local
  browserfs, wheel URL) and the sh46 shim stop being staging hacks
  and become a committed template + two Makefile targets. Desktop
  untouched by construction: no `src/` changes; the only
  existing-file edits are `Makefile` and the pyproject dev extras.
  **The loop's deliverable is a USER-TESTABLE local deploy (user,
  2026-09-14): the user's real browser is the primary verification
  instrument — they report results/errors faster and more
  faithfully than the agent's limited docker shell and its
  inability to read non-text inputs. In-container checks exist
  ONLY to prove the handover isn't dead on arrival; no gameplay
  is attempted in-container.**
- *Scope:* new `web/` (top level): `main.py` (pygbag-convention
  async entry: `await spacehack.__main__._amain()`); `sh46.js`
  (the phase-2 shim spec verbatim: `put`/`remove` optional
  callbacks, `get`/`keys` mandatory, root-relative POSIX names,
  UTF-8 text, IndexedDB db "spacehack" store "files", injected
  BEFORE the loader); vendored `browserfs.min.js` + `empty.html`
  with a provenance README (source + version; references-corpus
  convention) — foreign JS as build tooling, never game assets;
  the template-override mechanism pygbag 0.9.3 supports for the
  injection + local refs. `Makefile`: `web` (stage app dir →
  pygbag build → post-process: mirror the pinned pygame-ce 2.5.7
  wasm wheel into the bundle, rewrite its URL local, self-
  containment gate) and `serve-web` (stdlib http server setting
  `Cross-Origin-Opener-Policy: same-origin` +
  `Cross-Origin-Embedder-Policy: credentialless` on every
  response, serving `build/web/`). `pyproject.toml`: pygbag
  ==0.9.3 in dev extras (the phase-0 no-pyproject freeze is lifted
  by the GO ruling). Output to `build/web/` (already gitignored);
  the mirrored wheel is cached under build/, never committed. **No
  `src/` changes expected — any that surface are flagged, not
  smuggled.**
- *Build order:* pyproject + web/ skeleton + provenance README →
  sh46.js + vendored files + template overrides + `main.py` →
  `make web` + self-containment gate (grep the built bundle for
  runtime `https://` fetches — must find none) → `make serve-web`
  (prints the URL; serves until interrupted; rebuild reuses the
  cached wheel mirror) + header test → in-container BOOT beacon
  only (loader → wheel install → runtime import → `main()`
  entered, via the proven `location.hash` channel — proof the
  handover isn't dead on arrival) → `make check` → HAND OVER.
  Fix loop on user reports: fix → `make web` → re-serve.
- *Binding rulings:* R1 (the bundle adds zero flag/query-param
  plumbing); R3 (one async path — the web entry just awaits
  `_amain`); R4 (local/LAN verification; hosting later; GitHub
  Pages out); R5 (wheel mirrored); requirement #1 items 1/4/6
  (native path unchanged; 2.5.7-wasm vs 2.5.8-desktop lockstep
  tax accepted — web waits, desktop ships; same data bundle, no
  web-specific content); phase-2's shim rulings carry over
  (graceful timeout; fire-and-forget sync).
- *Tests:* serve-web handler test (both headers present on every
  response — stdlib, renderer-neutral); `make check` green
  throughout; the in-container beacon trail is the phase's real
  gate, not pytest. `web/` JS sits outside Ruff scope by
  construction.
- *Stop point:* bundle verified in-container + user's browser
  checkpoint passed. NOT started: phase 4 (perf numbers, dual
  playtest, world-gen loading beat), any hosting/deploy work,
  itch upload, touch input, PWA, save export/import.
- *Playtest checkpoint (user's browser — the PRIMARY instrument,
  per the principle):*
  1. `make web` on a clean tree: succeeds; `build/web/` holds the
     bundle incl. mirrored wheel + browserfs.min.js + sh46.js;
     self-containment grep clean.
  2. `make serve-web` → browser → pygbag loading screen → TITLE
     PAINTS (the gray-page pathology absent; first load ≈16 MB,
     cached after).
  3. Keyboard reaches the game: menu navigation → new game →
     ≥10 moves + one planet landing on the surface.
  4. Persistence through the real bundle: save+quit → close tab →
     reopen → Continue restores; options Apply survives a tab
     close/reopen.
  5. Fullscreen via the Window API path: enters/exits cleanly or
     degrades gracefully on the fixed canvas — never locks up.
  6. Desktop regression (cheap — no src/ changed): `run.py` boots
     to title; one save/quit → Continue cycle; `make check`
     green.
  7. Guide diff: NONE (the game is the game — requirement #1
     item 6).
  8. On any failure: paste the page's xterm/console output
     verbatim back to the agent; the fix loop is fix →
     `make web` → `make serve-web` → retest.

**Pre-implementation audit (2026-09-14, before code):**

1. **Extend/reuse:** `spacehack.__main__._amain` (`__main__.py:356`)
   is the self-contained async entry — `web/main.py` awaits it, zero
   src/ changes. `user_data.py` fixes the shim contract exactly
   (`platform.window.sh46`; `put`/`remove` fired with NO callback,
   `get`/`keys` with one; missing key ⇒ callback with null) —
   `web/sh46.js` implements nothing more. pygbag 0.9.3 CLI surface
   (verified in-container): `--build`, `--template` accepts a LOCAL
   file, `--cdn` is baked into index.html and every runtime URL
   derives from it, `--width/--height` set the canvas framebuffer,
   `--ume_block 0` drops the user-gesture gate (safe: no audio).
   Output = `<appdir>/build/web`. `tools/`-behind-make precedent
   (`save-debug`) → `tools/web_build.py` + `tools/serve_web.py`
   behind thin Makefile wrappers. Browser automation =
   `.docker_venv` playwright 1.62 (spike-proven; headless shell +
   `PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS` + apt libs, all
   re-provisioned this session).
2. **Duplication hotspots:** (a) TWO servers drifting — the boot
   check must IMPORT `serve_web`'s handler, never re-roll a server;
   (b) staging copy logic vs `packaging/` — one `_stage()` inside
   `web_build.py` only, packaging/ untouched; (c) the CDN mirror
   list duplicated between builder and checker — it lives ONCE as
   a table in `web_build.py`; the boot check asserts network
   silence (no non-local requests), not the list itself.
3. **DRY strategy:** the mirror set is a table-driven list of
   (remote path → local path) pairs; vendored-vs-downloaded is a
   column in that table; the template patch (sh46 injection — the
   ONLY diff from upstream default.tmpl; the service-worker block
   is already commented out upstream) is documented in
   web/README.md.
4. **Empirical facts this audit is built on (measured
   2026-09-14):** full runtime fetch set enumerated by booting the
   real bundle against the default CDN — versioned dir
   `cdn/0.9.3/`: pythons.js, cpython312/{main.js, main.data,
   main.wasm}, cpythonrc.py; root `cdn/`: index-0.9.3-cp312.json,
   vtx.js, vt/{xterm.js, xterm.css, xterm-addon-image.js},
   cp312/pygame_ce-2.5.7-cp312-cp312-wasm32_bi_emscripten.whl;
   `browserfs.min.js` + `empty.html` are GONE from the CDN
   (vendored from the pygbag repo, 251354 B — matches phase-0's
   measurement); the missing BrowserFS stalls boot before python
   starts ("PyMain: BrowserFS not found"), which is why the
   wheel request only appears with BrowserFS present. The
   template's service-worker registration is cross-origin on the
   default CDN = silently never worked — and is already commented
   out upstream, so nothing to patch or mirror there.

- [x] brief approved (user, 2026-09-14 — including the
      user-testable-deploy amendment: the user's browser is the
      primary instrument, in-container checks are boot-beacon
      only)
- [x] bundle boots from the local header-serving server; desktop
      artifacts unchanged (boot beacon 2026-09-14: `b46:main`
      reached, game window opens 1600×960, 18 requests ALL local,
      zero 404; `git diff --stat -- src/` empty across the phase)

**Phase-3 run log (2026-09-14):**

- Landed: `web/` (main.py entry, sh46.js shim, index.tmpl,
  vendored browserfs/empty.html + provenance README),
  `tools/web_build.py` (stage → pygbag → mirror → gate) and
  `tools/serve_web.py` behind `make web` / `make serve-web`,
  `tools/web_boot_check.py` (xvfb beacon + Ruling-5 network
  silence gate), header test, pygbag==0.9.3 dev extra. Commits
  d40d590 + 0a610c5 (plus 712f9af/bbde00e scaffolding).
- **Four load-bearing boot facts, each found by a failed boot:**
  (1) `--cdn` must be ROOT-relative (`/cdn/0.9.3/`) — vtx.js
  derives an ES-module import specifier from it, and a bare
  relative specifier fails to resolve; (2) the PEP 723 header in
  web/main.py is how the runtime resolves packages — no header ⇒
  no wheel ⇒ the module-level import dies SILENTLY and the
  wrapper prints done + drops to a REPL; (3) the trailing
  `asyncio.run(main())` is what starts the coroutine — pygbag's
  aio layer intercepts it; a bare `async def main` is imported
  and never run; (4) the runtime's packed aio module HARDCODES
  the pygbag CDN as its wheel-repo base (not patchable as a
  file) — sh46.js rewrites `window.fetch`'s host so those
  fetches land on the local mirror: Ruling 5 enforced at one
  seam, proven by the request log (index + wheel both 200 local).
- **Beacon mechanics (supersedes the brief's "location.hash
  channel"):** headless chromium is NOT viable — the runtime's
  aio loop pumps on rAF, throttled to ~0 headless (the phase-0
  round-2/3 ceiling); the beacon runs HEADED under Xvfb.
  Milestones print to the xterm (python stdout) and are read via
  a guarded CDP evaluate. URL-hash marking was tried and dropped:
  the game runs inside the template's sandboxed iframe, whose
  history is invisible to the top-frame URL. The xterm is also
  the user's error-report channel (checkpoint item 8).
- Boot beacon GREEN, twice: loader → wheel install (local,
  redirected) → runtime import → `b46:main` → window
  `(1600, 960)` open; 18 requests, all local, zero 404s; bundle
  25.6 MB (first-load in-browser ≈ 21 MB: runtime 20 MB
  dominates). favicon isn't emitted by pygbag under a local cdn —
  mirrored + copied to the bundle root. `--ume_block 0` (no
  audio ⇒ no gesture gate), `--width/--height 1600/960`.
- **Reviewer loop (2 dispatches):** round 1 REQUEST_CHANGES with
  7 findings — the two blockers were real contract breaks:
  sh46's shared write() helper passed `(value, name)` to IDB
  delete (DataError swallowed ⇒ **remove() never deleted —
  deleted saves would resurrect**, undetected because the
  phase-2 e2e never exercised delete), and `_stage_app` wiped
  all of `build/` (mirror cache + last-good bundle) every
  rebuild. Both fixed (split put/remove; stage-only wipe +
  mirror-before-replace), plus minors: one PYGBAG_VERSION
  constant, atomic `.part` downloads, broadened index gate +
  a build-time index↔wheel consistency check (fail-closed —
  a pygbag index bump now fails the BUILD with an update-the-pin
  message instead of 404ing at runtime), boot-check docstring
  drift, traceback routed to stdout. Round 2 APPROVE; its three
  minors (wipe ordering, fail-open gate, dead guard) fixed
  mechanically.
- Rebuild reuses the mirror cache (verified: second `make web`
  does zero downloads); desktop untouched by construction —
  zero `src/` changes all phase.

### Phase 4 — perf + dual playtest

In-browser numbered playtest checklist (browser automation can
drive it) + desktop regression checklist; `make check` green.
World-gen freeze gets a loading beat ONLY if the spike says it
needs one (wordless — motion/light, no prose, per house style).
Exit: both checklists pass; doc close then audits SYSTEMS.md
(the render path and loop entries gain a web-target note).

- [ ] brief approved (proposed 2026-09-14 at the phase-3
      checkpoint — to be finalized against the user's phase-3
      playtest report)
- [ ] in-browser + desktop checklists pass; `make check` green

**Brief (proposed 2026-09-14, pending the phase-3 playtest report
— perf observations from the user's browser shape the final
scope):**

- *Principle:* the user's browser measures (the
  user-testable-deploy ruling extends to perf — container
  numbers are advisory only). No new machinery is expected; the
  phase's default shape is two checklists and a decision.
- *Scope:* (a) the in-browser numbered checklist below, run by
  the user against `make serve-web`; (b) the desktop regression
  checklist (unchanged game — cheap pass); (c) ONE possible
  addition, only if the user's world-gen observation demands it:
  a wordless loading beat (motion/light, descent_animation-style
  — never prose), web-visible only if trivially uniform, else
  web-side; (d) doc close: move to complete/ + the full
  SYSTEMS.md audit (the render-path and loop entries gain
  web-target notes; the persistence entry gains the IndexedDB
  mirror + sh46 fetch seam; a web-build entry for
  make-web/serve-web/boot-beacon).
- *Build order:* user's phase-3 checklist results → loading-beat
  ruling (yes/no) → if yes: the beat lands with its own tests →
  dual checklists → close + SYSTEMS.md audit.
- *Binding rulings:* R1 (flagless — no perf flags in the
  bundle), R5 (self-contained — any beat ships in the bundle),
  requirement #1 items 2/6 (feel-identical desktop; content
  parity — a loading beat is presentation of EXISTING work, not
  content).
- *Tests:* `make check` green; if the beat lands, its timing
  tests ride the commit (pygame-input-triggered animation
  contract).
- *Stop point:* no hosting/deploy/itch, no touch input, no PWA,
  no save export/import, no balance or content changes.
- *Playtest checkpoint (in-browser, user):*
  1. New game → world-gen: observe the freeze — seconds,
     painful or fine? (the loading-beat ruling hangs on this)
  2. Planet landing → ≥20 moves + one transit: per-move feel.
  3. Save/quit → close tab → reopen → Continue restores (the
     phase-2 core through the phase-3 bundle).
  4. Options Apply → tab close/reopen → preferences hold.
  5. Fullscreen enter/exit (Window API path) — clean or graceful.
  6. Long-ish session (10+ min): steady or degrading?
  7. Desktop regression: run.py boot → save/quit → Continue;
     `make check` green.
  8. Guide diff: NONE (requirement #1 item 6).

## Risks

- **pygame-ce ↔ pygbag lockstep** — the main ongoing tax. Ruling 1
  ordering: desktop never waits on web wheels.
- **wasm performance** on world-gen and the NPC day-tick kernel —
  spike-measured before anything lands; mitigations (loading beat)
  are web-side only.
- **IndexedDB eviction** — browsers may evict stored saves under
  pressure (rare); autosave already bounds the loss. Save
  export/import is a possible later want, out of scope here.
- **First-load weight** — a few seconds on a decent connection,
  cached thereafter; no action unless the spike's numbers disagree.

## Non-goals

Mobile/touch input; any in-browser dev tooling; feature or content
divergence between targets; PWA/offline packaging (nearly free
later if wanted); guide changes.
