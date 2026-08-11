# Homebrew Tap — spacehack

Homebrew tap for [spacehack](https://github.com/rmhadley/spacehack), an
ASCII-art sci-fi roguelike.

## Install

```bash
brew tap rmhadley/tap
brew install --cask spacehack
```

Installs the macOS `.app` release into `/Applications`. The cask's
`postflight` step runs `xattr -cr` on the installed app, stripping every
extended attribute (including any `com.apple.quarantine` left behind by
browsers/Downloads) so the ad-hoc-signed build opens cleanly on macOS 15+
with no Gatekeeper bypass and no `xattr -cr` needed by hand.

## Updating after a release

Bump the cask to a new GitHub release (tag `v0.3.4`):

```bash
python3 tools/update_cask.py --version 0.3.4
```

This fetches the new `spacehack-macos.zip` sha256 from the GitHub API and
rewrites the cask's `version` and `sha256` stanzas. Or refresh just the
current version's sha with no arguments, and hash a local zip offline with
`--zip`. The script is stdlib-only — no brew or extra dependencies.

Commit and push; users then run `brew upgrade --cask spacehack`.

## Repository layout

This directory is a standalone Homebrew tap. To publish it, push its
contents to a new GitHub repo named `homebrew-tap` (owned by the same
account as the spacehack repo):

```bash
gh repo create rmhadley/homebrew-tap --public --source packaging/homebrew-tap --push
```

Casks live in `Casks/`.

## Notes

- The release `.app` build is arm64-only (CI runs on Apple Silicon
  runners).
- Local sanity check: `brew audit --cask Casks/spacehack.rb`.
