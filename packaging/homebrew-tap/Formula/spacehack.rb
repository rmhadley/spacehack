class Spacehack < Formula
  include Language::Python::Virtualenv

  desc "ASCII-art sci-fi roguelike"
  homepage "https://github.com/rmhadley/spacehack"
  # Literal tag URL on purpose: formula stanzas evaluate top-to-bottom and
  # #{version} interpolation in `url` is eager, so an explicit `version`
  # stanza would have to precede `url` to work. The conventional pattern is
  # a literal URL - brew derives the version (0.3.3) from the tag itself.
  # tools/update_cask.py rewrites this line (and sha256) on each release.
  url "https://github.com/rmhadley/spacehack/archive/refs/tags/v0.3.3.tar.gz"
  sha256 "392bc0204270d95a6c84cd4f37e5ecc65643eee4ba34fa0e0fcb6c6a667d4f31"
  license "MIT"
  head "https://github.com/rmhadley/spacehack.git", branch: "main"

  depends_on "python@3.12"

  def install
    # Creates a venv in the Cellar and pip-installs the project plus its
    # dependencies (tcod, pygame, numpy) from PyPI wheels. The game runs
    # as a Python script launched from the terminal, so there is no .app
    # bundle for Gatekeeper/LaunchServices to assess - no quarantine, no
    # signature requirement, works on macOS 15+ with no bypass.
    virtualenv_install_with_resources
  end

  test do
    assert_predicate bin/"spacehack", :exist?
    system Formula["python@3.12"].opt_bin/"python3.12", "-c", "import spacehack"
  end
end
