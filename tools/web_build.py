#!/usr/bin/env python3
"""Build the self-contained pygbag browser bundle (``make web``).

Stages the app next to a copy of the package, runs pygbag with the
repo's patched template and a LOCAL ``--cdn``, then mirrors every
runtime file the page would otherwise fetch from the pygbag CDN so
the bundle touches nothing third-party at load time (doc 46,
Ruling 5). Mirrors cache under ``build/web-mirror/`` and are reused
across rebuilds — only ``build/spacehack`` (the staging dir) is
wiped, so a rebuild never needs the network and never destroys the
last-known-good ``build/web``. Nothing mirrored is ever committed.

Output: ``build/web/`` — serve with ``make serve-web``.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
STAGE = BUILD / "spacehack"
OUT = BUILD / "web"
CACHE = BUILD / "web-mirror"

# The single lockstep surface: every versioned path below derives
# from this constant (bump ONLY with an explicit pygbag upgrade —
# desktop never waits on web wheels, doc 46 Ruling 1).
PYGBAG_VERSION = "0.9.3"
CDN = "https://pygame-web.github.io/cdn/"
VDIR = f"cdn/{PYGBAG_VERSION}/"  # baked as --cdn; must stay root-relative
INDEX = f"index-{PYGBAG_VERSION}-cp312.json"
# The pygame-ce wasm wheel pin. The runtime resolves the wheel via
# the mirrored index json; _gate() fails the build if the index's
# pygame version and this file disagree.
WHEEL = "cp312/pygame_ce-2.5.7-cp312-cp312-wasm32_bi_emscripten.whl"

# pygbag bake flags: 1600x960 matches the game's logical grid; the
# user-gesture gate is dropped (the game ships no audio). The cdn
# must be ROOT-relative ("/cdn/0.9.3/", not "cdn/0.9.3/"): vtx.js
# derives an ES-module import specifier from it, and a bare
# relative specifier fails to resolve.
PYGBAG_ARGS = [
    "--build",
    "--cdn", f"/{VDIR}",
    "--ume_block", "0",
    "--width", "1600",
    "--height", "960",
    "--app_name", "spacehack",
]

# (remote path under CDN, local path under OUT). Enumerated by booting
# the real bundle against the default CDN and recording every request
# (doc 46 phase-3 audit, 2026-09-14). Unversioned paths (the index,
# vtx, vt/*) are pin-forever by design once cached.
MIRROR = [
    (f"{PYGBAG_VERSION}/favicon.png", f"{VDIR}favicon.png"),
    (f"{PYGBAG_VERSION}/pythons.js", f"{VDIR}pythons.js"),
    (f"{PYGBAG_VERSION}/cpython312/main.js", f"{VDIR}cpython312/main.js"),
    (f"{PYGBAG_VERSION}/cpython312/main.data", f"{VDIR}cpython312/main.data"),
    (f"{PYGBAG_VERSION}/cpython312/main.wasm", f"{VDIR}cpython312/main.wasm"),
    (f"{PYGBAG_VERSION}/cpythonrc.py", f"{VDIR}cpythonrc.py"),
    (f"{PYGBAG_VERSION}/xtermjsixel/xterm-addon-image-worker.js",
     f"{VDIR}xtermjsixel/xterm-addon-image-worker.js"),
    (INDEX, f"cdn/{INDEX}"),
    ("vtx.js", "cdn/vtx.js"),
    ("vt/xterm.js", "cdn/vt/xterm.js"),
    ("vt/xterm.css", "cdn/vt/xterm.css"),
    ("vt/xterm-addon-image.js", "cdn/vt/xterm-addon-image.js"),
    (WHEEL, f"cdn/{WHEEL}"),
]

# Files the CDN deleted — vendored in web/ (provenance: web/README.md).
VENDORED = [
    ("web/browserfs.min.js", f"{VDIR}browserfs.min.js"),
    ("web/empty.html", f"{VDIR}empty.html"),
]

# Mirrored lazily at most; a 404 here is a warning, not a failure.
OPTIONAL = {f"{PYGBAG_VERSION}/xtermjsixel/xterm-addon-image-worker.js"}


def _stage_app() -> None:
    """Fresh staging dir: web entry + the package, caches pruned.

    Wipes ONLY build/spacehack — the mirror cache and the previous
    bundle must survive every rebuild (the fix loop re-serves them).
    """
    shutil.rmtree(STAGE, ignore_errors=True)
    STAGE.mkdir(parents=True)
    shutil.copy(ROOT / "web" / "main.py", STAGE / "main.py")
    shutil.copytree(ROOT / "src" / "spacehack", STAGE / "spacehack",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def _run_pygbag() -> None:
    """Bake index.html from the repo template with the local cdn."""
    try:
        import pygbag  # noqa: F401 — availability check only
    except ImportError:
        sys.exit("pygbag is missing — pip install -e '.[dev]' first")
    # pygbag's icon fetch joins --cdn + favicon into a ROOT-RELATIVE
    # url its urllib downloader can't follow (no scheme) and raises.
    # pygbag also clears build/web-cache whenever build/version.txt
    # is missing — and staging wipes it every build. Seed BOTH: the
    # version marker (so the cache survives) and the md5-named
    # favicon (so the icon resolves from cache, quietly — pygbag
    # then copies it into the bundle itself).
    favicon = _mirror_one(f"{PYGBAG_VERSION}/favicon.png")
    pycache = STAGE / "build"
    pycache.mkdir(parents=True, exist_ok=True)
    (pycache / "version.txt").write_text(PYGBAG_VERSION)
    # a "valid" cache also skips pygbag's own make_cache_dirs
    (pycache / "web").mkdir(exist_ok=True)
    if favicon.is_file():
        seed_dir = pycache / "web-cache"
        seed_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(favicon, seed_dir / (
            hashlib.md5(f"/{VDIR}favicon.png".encode()).hexdigest() + ".png"))
    template = (ROOT / "web" / "index.tmpl").resolve()
    cmd = [sys.executable, "-m", "pygbag", *PYGBAG_ARGS,
           f"--template={template}", STAGE.name]
    print("::", " ".join(cmd), "(cwd build/)")
    subprocess.run(cmd, cwd=BUILD, check=True)
    if not (STAGE / "build" / "web" / "index.html").is_file():
        sys.exit("pygbag produced no index.html — template or flags wrong")


def _mirror_one(remote: str) -> Path:
    """Download a CDN file into the cache; atomic, reused on rebuilds."""
    cached = CACHE / remote
    if cached.is_file() and cached.stat().st_size:
        return cached
    cached.parent.mkdir(parents=True, exist_ok=True)
    partial = cached.with_name(cached.name + ".part")
    url = CDN + remote
    try:
        # .part + replace so a killed download can never ship as a
        # truncated runtime file on the next build.
        urllib.request.urlretrieve(url, partial)  # noqa: S310 — fixed host
        os.replace(partial, cached)
    except Exception:
        partial.unlink(missing_ok=True)
        if remote in OPTIONAL:
            print(f"   optional mirror skipped (404?): {remote}")
            return cached
        raise
    print(f"   mirrored {remote} ({cached.stat().st_size} B)")
    return cached


def _assemble() -> None:
    """Bundle = pygbag output + sh46 + the full local cdn mirror.

    Mirrors populate BEFORE the old bundle is replaced, so a network
    failure (cold cache + offline) leaves the last-known-good
    build/web intact for the fix loop to keep serving.
    """
    cached: list[tuple[Path, Path]] = []
    for remote, local in MIRROR:
        mirror = _mirror_one(remote)
        if mirror.is_file() and mirror.stat().st_size:
            cached.append((mirror, OUT / local))
    favicon = CACHE / f"{PYGBAG_VERSION}/favicon.png"
    if favicon.is_file():
        cached.append((favicon, OUT / "favicon.png"))

    shutil.rmtree(OUT, ignore_errors=True)
    shutil.copytree(STAGE / "build" / "web", OUT)
    shutil.copy(ROOT / "web" / "sh46.js", OUT / "sh46.js")
    # index.html references the icon at the bundle root; pygbag only
    # emits it there when its own CDN fetch succeeds, so emit it too.
    for source, local in VENDORED:
        target = OUT / local
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / source, target)
    for mirror, local in cached:
        local.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(mirror, local)


def _gate() -> None:
    """Bundle self-checks: no absolute/unbaked resource refs, and the
    runtime-resolved wheel (from the mirrored index) is actually present."""
    failures: list[str] = []
    for line in (OUT / "index.html").read_text().splitlines():
        if re.search(r'(src|href)\s*=\s*["\']?((https?:)?//)', line):
            failures.append(f"absolute resource ref: {line.strip()[:80]}")
        if "{{" in line and re.search(r"(src|href)\s*=", line):
            failures.append(f"unbaked template ref: {line.strip()[:80]}")
    index = json.loads((OUT / "cdn" / INDEX).read_text())
    match = re.match(r"cp312/pygame_ce-([\d.]+)-", index.get("pygame", ""))
    if not match:
        failures.append(
            f"{INDEX} has no parsable pygame wheel entry — pygbag index "
            "format moved, re-derive the mirror set")
    elif not list((OUT / "cdn" / "cp312").glob(
            f"pygame_ce-{match.group(1)}-*.whl")):
        failures.append(
            f"index pins pygame-ce {match.group(1)} but the mirrored "
            f"wheel is {WHEEL} — pygbag lockstep moved, update the pin")
    if failures:
        sys.exit("gate failed:\n  " + "\n  ".join(failures))
    total = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    print(f"bundle: {OUT} ({total / 1e6:.1f} MB, "
          f"{len(list(OUT.rglob('*')))} entries)")


def main() -> None:
    _stage_app()
    _run_pygbag()
    _assemble()
    _gate()
    print("self-contained bundle ready — make serve-web, then open the URL")


if __name__ == "__main__":
    main()
