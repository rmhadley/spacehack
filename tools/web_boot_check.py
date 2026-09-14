#!/usr/bin/env python3
"""In-container boot beacon for the web bundle (doc 46, phase 3).

Loads build/web through the SAME header server make serve-web uses,
in chromium under Xvfb, and proves the handover isn't dead on
arrival: loader -> wheel install -> runtime import -> ``main()``
entered (the ``b46:main`` milestone web/main.py prints to the
xterm — python stdout is the boot channel; URL-hash marking was
tried and dropped: the game runs in the sandboxed iframe, whose
history is invisible to the top frame). The milestone text is read
via CDP evaluate, guarded — with the async loop running an
evaluate can fail transiently, so failures just poll again.

Headless is NOT an option here: the runtime's aio loop pumps on
rAF, which headless chromium throttles to ~0 (doc 46, phase-0
round 2/3) — a real compositor, even Xvfb, runs it at rate. The
self-containment gate lives here too: ANY request leaving
127.0.0.1 (page-local blob: excepted), or any 404, fails. No
gameplay is attempted in-container — the user's browser is the
primary instrument.

Requires: playwright + Xvfb (.docker_venv in the container;
pip install -e ".[dev]" elsewhere).

Usage: .docker_venv/bin/python3 tools/web_boot_check.py [timeout_s]
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
import serve_web  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "build" / "web"
DEFAULT_TIMEOUT_S = 480
XVFB_DISPLAY = ":46"


def _start_xvfb() -> subprocess.Popen:
    """A real compositor for the rAF-driven aio loop (main() pre-checks)."""
    proc = subprocess.Popen(
        ["Xvfb", XVFB_DISPLAY, "-screen", "0", "1920x1200x24"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(1)
    os.environ["DISPLAY"] = XVFB_DISPLAY
    return proc


def _run(timeout_s: int) -> int:
    requests: dict[str, str] = {}
    console: list[str] = []
    srv = serve_web.make_server(WEB, 0)
    server_thread = threading.Thread(target=srv.serve_forever, daemon=True)
    server_thread.start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    failures: list[str] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        page = browser.new_page()
        page.on("response", lambda r: requests.__setitem__(r.url, str(r.status)))
        page.on("requestfailed",
                lambda r: requests.__setitem__(r.url, f"FAIL {r.failure}"))
        page.on("console", lambda m: console.append(f"{m.type}: {m.text[:160]}"))
        page.on("pageerror", lambda e: console.append(f"PAGEERROR: {str(e)[:200]}"))
        # The wasm boot (compile + wheel install) can run minutes;
        # commit-level navigation + the hash watch below see it
        # through instead of timing out inside goto.
        page.goto(url, timeout=90000, wait_until="commit")
        print(f"loaded {url} — watching for b46:main (timeout {timeout_s}s)")
        deadline = time.time() + timeout_s
        marker = ""
        while time.time() < deadline:
            try:
                marker = page.evaluate(
                    "() => { const el = document.querySelector('.xterm-rows');"
                    " return el ? el.innerText : '' }"
                ) or ""
            except Exception:
                marker = ""  # evaluate can fail transiently — poll again
            if "b46:main" in marker or "b46:done" in marker:
                print(f"boot milestone: {marker[-120:]!r}")
                break
            time.sleep(2)
        else:
            failures.append(f"no b46:main within {timeout_s}s (last marker {marker[-80:]!r})")
        browser.close()
    srv.shutdown()
    server_thread.join(timeout=5)

    for url_, status in sorted(requests.items()):
        if url_.startswith("blob:"):  # page-generated, not a network fetch
            continue
        if not url_.startswith("http://127.0.0.1"):
            failures.append(f"external request (Ruling 5): {status} {url_}")
        elif status != "200":
            failures.append(f"bad status {status}: {url_}")
    print(f"{len(requests)} requests, all local"
          if not failures else f"{len(requests)} requests")
    for line in console[-12:]:
        print("  ", line)
    for fail in failures:
        print("FAIL:", fail)
    return 1 if failures else 0


def main() -> None:
    if not WEB.is_dir():
        sys.exit("build/web is missing — run make web first")
    if shutil.which("Xvfb") is None:
        sys.exit("Xvfb is required (the aio loop pumps on rAF) — apt install xvfb")
    timeout_s = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TIMEOUT_S
    xvfb = _start_xvfb()
    try:
        sys.exit(_run(timeout_s))
    finally:
        xvfb.terminate()


if __name__ == "__main__":
    main()
