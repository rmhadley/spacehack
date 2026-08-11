# Homebrew Tap — spacehack

Homebrew tap for [spacehack](https://github.com/rmhadley/spacehack), an
ASCII-art sci-fi roguelike.

## Install

Two ways to install:

```bash
brew tap rmhadley/tap
brew install --cask spacehack        # macOS .app in /Applications
# or
brew install spacehack               # `spacehack` command from a Cellar venv
```

**Cask** — downloads the macOS `.app` release. Homebrew does not apply the
`com.apple.quarantine` attribute to cask installs, so the app opens without
a Gatekeeper bypass.

**Formula** — builds the game into a Python venv inside the Cellar and
installs a `spacehack` command. Because the game runs as a Python script
launched from the terminal, there is **no `.app` bundle for Gatekeeper or
LaunchServices to assess at all** — no quarantine, no signature
requirement, nothing to bypass, on any macOS. This is the most
gatekeeper-proof path. First install pulls the tcod/pygame/numpy wheels
from PyPI (~100 MB); later installs are cached by Homebrew.

## Updating after a release

Bump the tap to a new GitHub release (tag `v0.3.4`):

```bash
python3 tools/update_cask.py --version 0.3.4
```

This updates **both** the cask (macOS zip sha256) and the formula (source
tarball sha256) from the GitHub API. Or refresh just the current version's
hashes with no arguments, and hash local files offline with `--zip` /
`--tarball`. The script is stdlib-only — no brew or extra dependencies.

Commit and push; users then run `brew upgrade` / `brew upgrade --cask spacehack`.

## Repository layout

This directory is a standalone Homebrew tap. To publish it, push its
contents to a new GitHub repo named `homebrew-tap` (owned by the same
account as the spacehack repo):

```bash
gh repo create rmhadley/homebrew-tap --public --source packaging/homebrew-tap --push
```

Casks live in `Casks/`, formulae in `Formula/`.

## Notes

- The release build is arm64-only (CI runs on Apple Silicon runners).
- Local sanity checks: `brew audit --cask Casks/spacehack.rb` and
  `brew audit --formula Formula/spacehack.rb`.
