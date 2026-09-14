# web/ — pygbag bundle template (doc 46, phase 3)

Everything `make web` needs that is NOT generated: the async entry,
the persistence shim, the patched loader template, and the two
files the pygbag CDN deleted. Built output (and the ~16 MB mirrored
runtime) lands in `build/web/` — gitignored, never committed.

## Files

| File | Role |
|------|------|
| `main.py` | pygbag entry: awaits `spacehack.__main__._amain()`, marks boot milestones in the URL hash |
| `sh46.js` | `window.sh46` IndexedDB persistence shim (phase-2 spec: db `spacehack`, store `files`, POSIX rel-paths, UTF-8 text) + `window.b46mark` boot-diagnostic helper. Injected BEFORE the loader by `index.tmpl`. |
| `index.tmpl` | pygbag 0.9.3 `default.tmpl` + exactly ONE patch: a `sh46.js` script tag injected before the pythons.js loader (verified: the only line that differs from upstream). The template's service-worker registration is already commented out upstream — no patch needed. |
| `browserfs.min.js` | vendored — removed from the pygbag CDN (404); boot stalls without it (`PyMain: BrowserFS not found`) |
| `empty.html` | vendored — likewise 404 on the CDN; loader iframe fallback |

## Vendored-file provenance

Both from the pygbag source repo, pinned to commit:

- repo: `pygame-web/pygbag` @ `df678453b3c9090f1ba659a0a8f740b4437ad8d3` (main, 2026-09-14)
- `browserfs.min.js` = `static/browserfs.min.js` (251354 bytes — identical
  size to the copy the phase-0 spike measured off the then-live CDN)
- `empty.html` = `static/empty.html` (14 bytes: `<html></html>`)

Foreign JavaScript enters the repo ONLY here, as build tooling the
loader hard-requires — never as a game asset.

## Runtime mirror (downloaded at build, cached in build/, never committed)

`tools/web_build.py` mirrors the pygbag CDN pieces the page fetches
at runtime so the bundle is self-contained (Ruling 5): the loader,
the CPython 3.12 wasm runtime, cpythonrc, the xterm terminal set,
the wheel index, and the pinned pygame-ce 2.5.7 wasm wheel
(`cp312/pygame_ce-2.5.7-cp312-cp312-wasm32_bi_emscripten.whl`).
Wheel pin moves only with an explicit pygbag bump (lockstep tax,
see doc 46 Risks).
