# Homebrew Tap — spacehack

Homebrew tap for [spacehack](https://github.com/rmhadley/spacehack), an
ASCII-art sci-fi roguelike.

## Install

```bash
brew tap rmhadley/tap
brew install --cask spacehack
```

This downloads the macOS `.app` release (ad-hoc signed, no Developer ID).
Homebrew does **not** apply the `com.apple.quarantine` attribute to cask
installs, so the app opens normally on macOS 15+ with no Gatekeeper
bypass and no `xattr -cr`.

## Updating after a release

Bump the cask to a new GitHub release (tag `v0.3.4`):

```bash
python3 tools/update_cask.py --version 0.3.4
```

Or just refresh the sha256 of the cask's current version:

```bash
python3 tools/update_cask.py
```

The script downloads the release zip from GitHub, computes its sha256,
and rewrites the `version` / `sha256` stanzas in `Casks/spacehack.rb`.
It is stdlib-only — no brew or extra dependencies. For offline testing,
`--zip path/to/spacehack-macos.zip` computes the hash of a local file.

Commit and push; users then run `brew upgrade --cask spacehack`.

## Repository layout

This directory is a standalone Homebrew tap. To publish it, push its
contents to a new GitHub repo named `homebrew-tap` (owned by the same
account as the spacehack repo):

```bash
gh repo create rmhadley/homebrew-tap --public --source packaging/homebrew-tap --push
```

Casks live in `Casks/` (formulae would go in `Formula/`).

## Notes

- The release build is arm64-only (CI runs on Apple Silicon runners).
- Local sanity check: `brew audit --cask Casks/spacehack.rb`
