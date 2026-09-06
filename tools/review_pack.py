#!/usr/bin/env python3
"""Assemble a self-contained review pack for the reviewer subagent.

Concatenates the working-tree (or range) diff, git status, recent log,
untracked-file contents, and named doc/question files into one output
file the reviewer reads with a single Read. Never embeds tracked file
bodies — the reviewer reads touched files itself; doubling them here is
pure token waste. Untracked files ARE embedded: their content is the
addition, and `git diff` would otherwise hide it entirely.

Usage:
  python3 tools/review_pack.py                       # working tree
  python3 tools/review_pack.py --range HEAD~2..HEAD  # commit range
  python3 tools/review_pack.py --doc docs/design/in_progress/40_DESIGN_TRANSPONDER_ID.md
  python3 tools/review_pack.py --question "Is the dock gate save-safe?"
"""
import argparse
import subprocess
import sys
from pathlib import Path

READ_TRUNCATES_AT = 2000  # reviewer's Read tool truncates silently here


def _run(args: list[str]) -> str:
    out = subprocess.run(args, capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"review_pack: git failed: {out.stderr.strip()}")
    return out.stdout.strip("\n")


def _untracked_paths(status: str) -> list[str]:
    return [line[3:].strip('"') for line in status.splitlines()
            if line.startswith("?? ")]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--range", dest="range_", default=None,
                    help="commit range to review (default: working tree vs HEAD)")
    ap.add_argument("--doc", action="append", default=[],
                    help="doc/brief file to embed (repeatable)")
    ap.add_argument("--question", action="append", default=[],
                    help="dispatch question (repeatable)")
    ap.add_argument("--out", default="/tmp/review_pack.md")
    args = ap.parse_args()

    for doc in args.doc:
        if not Path(doc).is_file():
            sys.exit(f"review_pack: no such file: {doc}")

    diff_args = ["git", "diff", args.range_] if args.range_ else ["git", "diff", "HEAD"]
    diff = _run(diff_args)
    status = _run(["git", "status", "--short"])
    untracked = _untracked_paths(status)
    if not diff.strip() and not status.strip():
        scope = f"range {args.range_}" if args.range_ else "clean tree"
        sys.exit(f"review_pack: nothing to review ({scope}; no diff, no files)")

    parts = [f"# Review pack — {args.range_ or 'working tree'}\n",
             "## git status\n", status or "(clean)", "",
             "## log\n", _run(["git", "log", "--oneline", "-8"]), "",
             "## diff\n", "```diff", diff or "(empty)", "```", ""]
    if untracked:
        parts.append("## untracked files — absent from the diff above; "
                     "their content IS the addition\n")
        for path in untracked:
            parts += [f"### {path}\n", "```", Path(path).read_text(), "```", ""]
    for doc in args.doc:
        parts += [f"## doc: {doc}\n", Path(doc).read_text(), ""]
    if args.question:
        parts += ["## questions\n"] + [f"- {q}" for q in args.question] + [""]

    text = "\n".join(parts)
    out = Path(args.out)
    out.write_text(text)
    lines = text.count("\n") + 1
    warn = " WARNING: exceeds the reviewer Read tool's silent 2000-line" \
           " truncation — split the dispatch." if lines > READ_TRUNCATES_AT else ""
    print(f"{out} — {lines} lines{warn}")


if __name__ == "__main__":
    main()
