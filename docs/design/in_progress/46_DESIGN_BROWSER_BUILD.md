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

Boot the REAL title screen under pygbag from a scratch branch —
`src/` untouched (this phase cannot degrade anything by
construction). Measure and record: (a) payload size + first-load
time (expect ~15–25 MB: wasm CPython runtime + game; cached after),
(b) new-game world-gen freeze under wasm vs native, (c) per-move
lighting-recompute latency under wasm vs native, (d) pygame-ce ↔
pygbag wheel alignment at the current pin (≥ 2.5.8). Exit: the four
numbers in this doc + an explicit go/no-go. Pure-Python under wasm
runs ~3–8× slower; at human input rates that is almost certainly
fine — the spike exists to prove it, not assume it.

### Phase 1 — one async path

Convert the four event-pumping files to yield per frame; desktop
runs the same loop under `asyncio.run` with `clock.tick()` pacing.
Exit gate (requirement #1's): measured frame-pacing and
input-latency A/B vs pre-change (dev-instrumented), plus a FULL
desktop playtest pass. No web-only code in this phase.

### Phase 2 — persistence shim

`_saves_dir()` gains a backend target: desktop unchanged (same
path, same JSON), web = IndexedDB-backed directory + sync-on-save.
Exit: the save/load/quicksave/autosave/Shift+S-reroll checklist on
BOTH targets, including quit-mid-save and reload.

### Phase 3 — `make web` target

pygbag packaging as a sibling of the wheel; fullscreen rides the
Window API and degrades gracefully on a fixed canvas; pygbag's
loading screen is the first-load UX. Exit: the static bundle boots
and plays from a plain static web server; desktop build artifacts
and pipeline unchanged.

### Phase 4 — perf + dual playtest

In-browser numbered playtest checklist (browser automation can
drive it) + desktop regression checklist; `make check` green.
World-gen freeze gets a loading beat ONLY if the spike says it
needs one (wordless — motion/light, no prose, per house style).
Exit: both checklists pass; doc close then audits SYSTEMS.md
(the render path and loop entries gain a web-target note).

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
