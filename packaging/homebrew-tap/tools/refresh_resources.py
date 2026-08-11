#!/usr/bin/env python3
"""Regenerate the pip dependency pins in Formula/spacehack.rb.

Homebrew sandboxes formula builds, so pip can never reach PyPI at install
time - every dependency is pinned as a ``resource`` in the formula. This
script resolves the newest compatible wheels from PyPI's JSON API for
CPython 3.12 on macOS (arm64 + x86_64) and rewrites the resource block
between the ``===== resources =====`` markers.

Stdlib only. Usage:
  python3 tools/refresh_resources.py [--formula PATH]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

DEFAULT_FORMULA = Path(__file__).resolve().parent.parent / "Formula" / "spacehack.rb"
PYTHON = "cp312"
PURE_PACKAGES = ("attrs", "pycparser", "typing_extensions")
ARCH_PACKAGES = ("cffi", "numpy", "pygame", "tcod")
START_MARKER = "  # ===== resources: regenerate with tools/refresh_resources.py ====="
END_MARKER = "  # ===== end resources ====="


def _get(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": "spacehack-refresh-resources"})
    return urllib.request.urlopen(request, timeout=60)


BLOCK_NAME = {"arm64": "on_arm", "x86_64": "on_intel"}


def _version_key(version: str) -> tuple:
    return tuple(int(p) for p in version.split("."))


def _platform_score(plat: str) -> tuple:
    """Lower is better: 'any' wheels first, then lowest macOS requirement."""
    if plat == "any":
        return (0, 0, 0)
    match = re.match(r"macosx_(\d+)_(\d+)_(?:arm64|x86_64|universal2)", plat)
    if match:
        return (1, int(match.group(1)), int(match.group(2)))
    return (99, 0, 0)


def _wheel_parts(filename: str) -> tuple | None:
    """Return (py_tag, abi_tag, platform_tag) for a wheel filename, else None."""
    if not filename.endswith(".whl"):
        return None
    parts = filename[:-4].split("-")
    if len(parts) < 5:
        return None
    return parts[-3], parts[-2], parts[-1]


def compatible(filename: str, arch: str) -> bool:
    """True if the wheel installs on CPython 3.12 / macOS <arch>."""
    parsed = _wheel_parts(filename)
    if parsed is None:
        return False
    py, abi, plat = parsed
    if py in ("py3", "py2.py3", PYTHON):
        pass
    elif abi == "abi3" and re.fullmatch(r"cp3(?:10|11|12)", py):
        pass
    else:
        return False
    if abi not in (PYTHON, "abi3", "none"):
        return False
    if plat == "any":
        return True
    if "macosx" not in plat:
        return False
    return ("arm64" in plat or "universal2" in plat) if arch == "arm64" else ("x86_64" in plat or "universal2" in plat)


def resolve(name: str, arch: str) -> dict:
    """Newest compatible wheel for *name* on <arch>. Raises if none found."""
    data = json.load(_get(f"https://pypi.org/pypi/{name}/json"))
    candidates: list[tuple] = []
    seen_versions: set[str] = set()
    releases = {**{data["info"]["version"]: data["urls"]}, **data.get("releases", {})}
    for version, files in releases.items():
        # Skip pre-releases (rc/b/a/dev/post) - only stable versions.
        if version in seen_versions or re.search(r"[^0-9.]", version):
            continue
        seen_versions.add(version)
        for entry in files:
            filename = entry["filename"]
            parsed = _wheel_parts(filename)
            if parsed is None or not compatible(filename, arch):
                continue
            # Highest version wins; within a version prefer exact cp312/none
            # abi over abi3, then the lowest macOS requirement (widest compat).
            abi_preference = 0 if parsed[1] in (PYTHON, "none") else 1
            plat_score = _platform_score(parsed[2])
            candidates.append((
                _version_key(version),
                -abi_preference,
                -plat_score[0], -plat_score[1], -plat_score[2],
                entry,
            ))
    if not candidates:
        raise SystemExit(f"error: no compatible {name} wheel found for macOS {arch}")
    candidates.sort()
    return candidates[-1][5]


def stanza(name: str, entry: dict, indent: str = "  ") -> str:
    return (
        f'{indent}resource "{name}" do\n'
        f'{indent}  url "{entry["url"]}"\n'
        f'{indent}  sha256 "{entry["digests"]["sha256"]}"\n'
        f"{indent}end\n"
    )


def generate() -> str:
    lines = [START_MARKER]
    for name in PURE_PACKAGES:
        lines.append("")
        lines.append(stanza(name, resolve(name, "arm64")).rstrip("\n"))
    for arch in ("arm64", "x86_64"):
        lines.append("")
        lines.append(f"  {BLOCK_NAME[arch]} do")
        for name in ARCH_PACKAGES:
            lines.append("")
            lines.append(stanza(name, resolve(name, arch), indent="    ").rstrip("\n"))
        lines.append("  end")
    lines.append(END_MARKER)
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--formula", default=str(DEFAULT_FORMULA), help="path to the formula file")
    args = parser.parse_args()
    formula = Path(args.formula)
    text = formula.read_text()
    if START_MARKER not in text or END_MARKER not in text:
        sys.exit(f"error: resource markers not found in {formula}")
    new_block = generate()
    updated = re.sub(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
        lambda _m: new_block.rstrip("\n"),
        text,
        count=1,
        flags=re.DOTALL,
    )
    formula.write_text(updated)
    print(f"resources regenerated in {formula}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
