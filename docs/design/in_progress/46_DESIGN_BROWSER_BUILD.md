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
result is a static bundle hostable anywhere (itch embed, GitHub
Pages — user-run ops, outside the container).

**Ruling 3 (this doc, subordinate to requirement #1): ONE async
path, no dual loops.** The frame pump yields to the event loop each
frame; on desktop `asyncio.run(main())` drives it with
`clock.tick()` still the pacer — pacing identical by construction,
and verified by measurement anyway (phase 1 exit gate). If
verification fails, the phase does not land; there is no
platform-conditional loop fallback.

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
- [ ] entry shim boots the title screen under wasm (patch only if
      the unpatched boot hangs)
- [ ] (a) payload + first-load, (b) world-gen wasm vs native,
      (c) per-move lighting wasm vs native — recorded
- [ ] numbers + go/no-go recommendation in this doc; ruling
      requested

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

### Phase 1 — one async path

Convert the four event-pumping files to yield per frame; desktop
runs the same loop under `asyncio.run` with `clock.tick()` pacing.
Exit gate (requirement #1's): measured frame-pacing and
input-latency A/B vs pre-change (dev-instrumented), plus a FULL
desktop playtest pass. No web-only code in this phase.

- [ ] brief approved (written at the phase-0 handoff)
- [ ] one async path landed; measured pacing/input A/B identical
- [ ] full desktop playtest pass recorded

### Phase 2 — persistence shim

`_saves_dir()` gains a backend target: desktop unchanged (same
path, same JSON), web = IndexedDB-backed directory + sync-on-save.
Exit: the save/load/quicksave/autosave/Shift+S-reroll checklist on
BOTH targets, including quit-mid-save and reload.

- [ ] brief approved (written at the phase-1 checkpoint)
- [ ] desktop save path/format byte-identical; checklist passes on
      both targets

### Phase 3 — `make web` target

pygbag packaging as a sibling of the wheel; fullscreen rides the
Window API and degrades gracefully on a fixed canvas; pygbag's
loading screen is the first-load UX. Exit: the static bundle boots
and plays from a plain static web server; desktop build artifacts
and pipeline unchanged.

- [ ] brief approved (written at the phase-2 checkpoint)
- [ ] bundle boots from a plain static server; desktop artifacts
      unchanged

### Phase 4 — perf + dual playtest

In-browser numbered playtest checklist (browser automation can
drive it) + desktop regression checklist; `make check` green.
World-gen freeze gets a loading beat ONLY if the spike says it
needs one (wordless — motion/light, no prose, per house style).
Exit: both checklists pass; doc close then audits SYSTEMS.md
(the render path and loop entries gain a web-target note).

- [ ] brief approved (written at the phase-3 checkpoint)
- [ ] in-browser + desktop checklists pass; `make check` green

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
