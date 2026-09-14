#!/usr/bin/env python3
"""Serve ``build/web`` with the headers the pygbag loader needs.

``make serve-web`` — a static server that adds the cross-origin
isolation headers (COOP ``same-origin`` + COEP ``credentialless``)
the wasm loader requires; a plain header-less server stalls it
(doc 46, phase-0 defect 1). Serves until interrupted; the port is
argv[1] (default 8460). Re-run ``make web`` for a new bundle.
"""
from __future__ import annotations

import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "build" / "web"
DEFAULT_PORT = 8460


class WebHandler(SimpleHTTPRequestHandler):
    """Static files + the cross-origin isolation the loader requires."""

    def end_headers(self) -> None:
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "credentialless")
        super().end_headers()


def make_server(directory: Path, port: int) -> ThreadingHTTPServer:
    """Bound server over ``directory`` (port 0 = ephemeral, for tests)."""
    return ThreadingHTTPServer(
        ("0.0.0.0", port), partial(WebHandler, directory=str(directory))
    )


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    if not WEB.is_dir():
        sys.exit("build/web is missing — run make web first")
    srv = make_server(WEB, port)
    print(f"serving {WEB}")
    print(f"open http://localhost:{srv.server_address[1]}/ — Ctrl-C to stop")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
