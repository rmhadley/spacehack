"""serve-web contract: every response carries the isolation headers.

The pygbag wasm loader stalls without COOP/COEP (doc 46, phase-0
defect 1) — a header-less server is a broken server. Renderer-
neutral, stdlib-only: real handler, ephemeral port, no SDL.
"""
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS))

import serve_web  # noqa: E402


def _get(url: str) -> tuple[int, dict[str, str]]:
    try:
        resp = urllib.request.urlopen(url, timeout=5)
    except urllib.error.HTTPError as err:  # 404s still carry the headers
        resp = err
    with resp:
        return resp.status, {k: v for k, v in resp.headers.items()}


def test_every_response_carries_isolation_headers(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<html></html>")
    nested = tmp_path / "cdn"
    nested.mkdir()
    (nested / "x.js").write_text("// x")
    srv = serve_web.make_server(tmp_path, 0)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        port = srv.server_address[1]
        for path in ("/", "/cdn/x.js", "/missing.txt"):
            status, headers = _get(f"http://127.0.0.1:{port}{path}")
            assert headers["Cross-Origin-Opener-Policy"] == "same-origin"
            assert headers["Cross-Origin-Embedder-Policy"] == "credentialless"
            assert status == (404 if path == "/missing.txt" else 200)
    finally:
        srv.shutdown()
        thread.join(timeout=5)
