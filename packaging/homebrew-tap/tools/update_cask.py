#!/usr/bin/env python3
"""Update Casks/spacehack.rb with the sha256 of a released macOS zip.

Stdlib only (no brew, no requests) so it runs anywhere Python does.

Usage:
  python3 tools/update_cask.py                     # refresh sha256 for the version already in the cask
  python3 tools/update_cask.py --version 0.3.4     # bump version + sha256 for a new release tag v0.3.4
  python3 tools/update_cask.py --zip path.zip      # compute sha256 of a local zip (no network)
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
DEFAULT_CASK = Path(__file__).resolve().parent.parent / "Casks" / "spacehack.rb"


def _get(url: str, timeout: int):
    request = urllib.request.Request(url, headers={"User-Agent": "spacehack-cask-updater"})
    return urllib.request.urlopen(request, timeout=timeout)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_stanza(cask: Path, name: str) -> str | None:
    match = re.search(rf'^\s*{name} "([^"]+)"', cask.read_text(), re.MULTILINE)
    return match.group(1) if match else None


def patch_stanza(cask: Path, name: str, value: str) -> bool:
    """Rewrite one ``name "value"`` stanza in place. Returns True if changed."""
    text = cask.read_text()
    pattern = re.compile(rf'^(\s*){name} "[^"]+"', re.MULTILINE)
    match = pattern.search(text)
    if match is None:
        sys.exit(f"error: no '{name}' stanza found in {cask}")
    if match.group(0).rsplit('"', 2)[-2] == value:
        return False
    cask.write_text(
        pattern.sub(lambda m: f'{m.group(1)}{name} "{value}"', text, count=1)
    )
    return True


def release_asset_url(version: str) -> str:
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


def download_sha(url: str) -> str:
    print(f"downloading {url}")
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", help="release tag version to bump to (e.g. 0.3.4); defaults to the cask's current version")
    parser.add_argument("--zip", help="path to a local spacehack-macos.zip (skips the network)")
    parser.add_argument("--cask", default=str(DEFAULT_CASK), help="path to the cask file")
    args = parser.parse_args()

    cask = Path(args.cask)
    current_version = read_stanza(cask, "version")
    if current_version is None:
        sys.exit(f"error: no 'version' stanza found in {cask}")
    version = args.version or current_version
    print(f"updating {cask} for v{version}")

    new_sha = sha256_of(Path(args.zip)) if args.zip else download_sha(release_asset_url(version))

    changed = patch_stanza(cask, "version", version)
    changed = patch_stanza(cask, "sha256", new_sha) or changed
    if changed:
        print(f"cask updated: version={version} sha256={new_sha}")
    else:
        print("cask already up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
