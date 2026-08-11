#!/usr/bin/env python3
"""Update the spacehack tap for a release.

Patches the sha256 (and optionally the version) of:
  Casks/spacehack.rb      - the macOS .app release zip
  Formula/spacehack.rb    - the source tarball

Stdlib only (no brew, no requests) so it runs anywhere Python does.

Usage:
  python3 tools/update_cask.py                      # refresh both for the version already in the tap
  python3 tools/update_cask.py --version 0.3.4      # bump version + sha256 for a new release tag v0.3.4
  python3 tools/update_cask.py --zip path.zip       # cask sha256 from a local zip (no network)
  python3 tools/update_cask.py --tarball path.tgz   # formula sha256 from a local tarball (no network)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

REPO = "rmhadley/spacehack"
ASSET = "spacehack-macos.zip"
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CASK = ROOT / "Casks" / "spacehack.rb"
DEFAULT_FORMULA = ROOT / "Formula" / "spacehack.rb"


def _get(url: str, timeout: int):
    request = urllib.request.Request(url, headers={"User-Agent": "spacehack-tap-updater"})
    return urllib.request.urlopen(request, timeout=timeout)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_stanza(file: Path, name: str) -> str | None:
    match = re.search(rf'^\s*{name} "([^"]+)"', file.read_text(), re.MULTILINE)
    return match.group(1) if match else None


def patch_stanza(file: Path, name: str, value: str) -> bool:
    """Rewrite one ``name "value"`` stanza in place. Returns True if changed."""
    text = file.read_text()
    pattern = re.compile(rf'^(\s*){name} "[^"]+"', re.MULTILINE)
    match = pattern.search(text)
    if match is None:
        sys.exit(f"error: no '{name}' stanza found in {file}")
    if match.group(0).rsplit('"', 2)[-2] == value:
        return False
    file.write_text(pattern.sub(lambda m: f'{m.group(1)}{name} "{value}"', text, count=1))
    return True


def release_asset_url(version: str) -> str:
    """URL of the macOS .app zip attached to the v<version> release."""
    api = f"https://api.github.com/repos/{REPO}/releases/tags/v{version}"
    try:
        with _get(api, timeout=30) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            sys.exit(f"error: no release tagged v{version} on {REPO}")
        raise
    for asset in data.get("assets", []):
        if asset.get("name") == ASSET:
            return asset["browser_download_url"]
    sys.exit(f"error: release v{version} has no {ASSET} asset")


def source_tarball_url(version: str) -> str:
    """URL of the source tarball for the v<version> tag."""
    return f"https://github.com/{REPO}/archive/refs/tags/v{version}.tar.gz"


def download_sha(url: str) -> str:
    print(f"downloading {url}")
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        with _get(url, timeout=600) as response, open(tmp_path, "wb") as out:
            while True:
                chunk = response.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
        return sha256_of(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", help="release tag version to bump to (e.g. 0.3.4); defaults to the tap's current version")
    parser.add_argument("--zip", help="path to a local spacehack-macos.zip (cask only, no network)")
    parser.add_argument("--tarball", help="path to a local source tarball (formula only, no network)")
    parser.add_argument("--cask", default=str(DEFAULT_CASK), help="path to the cask file")
    parser.add_argument("--formula", default=str(DEFAULT_FORMULA), help="path to the formula file")
    args = parser.parse_args()

    cask = Path(args.cask)
    formula = Path(args.formula)
    version = args.version or read_stanza(cask, "version") or read_stanza(formula, "version")
    if version is None:
        sys.exit(f"error: could not read the version from {cask} or {formula}")
    print(f"updating tap for v{version}")

    do_cask = do_formula = True
    if args.zip or args.tarball:
        do_cask = args.zip is not None
        do_formula = args.tarball is not None

    changed = False
    if do_cask:
        new_sha = sha256_of(Path(args.zip)) if args.zip else download_sha(release_asset_url(version))
        changed = patch_stanza(cask, "version", version) | patch_stanza(cask, "sha256", new_sha)
        print(f"cask:    version={version} sha256={new_sha} {'(changed)' if changed else '(up to date)'}")
    if do_formula:
        new_sha = sha256_of(Path(args.tarball)) if args.tarball else download_sha(source_tarball_url(version))
        changed = patch_stanza(formula, "version", version) | patch_stanza(formula, "sha256", new_sha)
        print(f"formula: version={version} sha256={new_sha} {'(changed)' if changed else '(up to date)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
