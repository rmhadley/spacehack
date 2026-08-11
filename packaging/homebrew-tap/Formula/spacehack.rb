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

  # Homebrew sandboxes formula builds (no network), so pip cannot resolve
  # dependencies from PyPI at install time - every dependency must be
  # pinned here as a resource. The closure below is COMPLETE (resources
  # install with --no-deps): tcod -> attrs, cffi, numpy, typing_extensions;
  # cffi -> pycparser; pygame/numpy/attrs -> none. The game's own deps
  # (tcod>=16, pygame>=2.5) are satisfied by these pins.
  #
  # Regenerate the pins with: python3 tools/refresh_resources.py
  # ===== resources: regenerate with tools/refresh_resources.py =====

  resource "attrs" do
    url "https://files.pythonhosted.org/packages/64/b4/17d4b0b2a2dc85a6df63d1157e028ed19f90d4cd97c36717afef2bc2f395/attrs-26.1.0-py3-none-any.whl"
    sha256 "c647aa4a12dfbad9333ca4e71fe62ddc36f4e63b2d260a37a8b83d2f043ac309"
  end

  resource "pycparser" do
    url "https://files.pythonhosted.org/packages/0c/c3/44f3fbbfa403ea2a7c779186dc20772604442dde72947e7d01069cbe98e3/pycparser-3.0-py3-none-any.whl"
    sha256 "b727414169a36b7d524c1c3e31839a521725078d7b2ff038656844266160a992"
  end

  resource "typing_extensions" do
    url "https://files.pythonhosted.org/packages/49/d3/b8441a820a491ddfc024b0b0cf0393375b75ea13866d9c66727e54c2fc80/typing_extensions-4.16.0-py3-none-any.whl"
    sha256 "481caa481374e813c1b176ada14e97f1f67a4539ce9cfeb3f350d78d6370c2e8"
  end

  on_arm do

    resource "cffi" do
      url "https://files.pythonhosted.org/packages/54/7d/16e5a096677b5e313ca80cd5e5170efa3ea44624a82bb111925522da64b1/cffi-2.1.1-cp312-cp312-macosx_11_0_arm64.whl"
      sha256 "f81b3b8f3d4e343550fa4baa0e479bba9f2d29ce9c2e9b51d1ce1718d7442fcf"
    end

    resource "numpy" do
      url "https://files.pythonhosted.org/packages/60/2e/b5aee50a1f74ac815cf8331812cb8251e29024025de462e0c047641c614c/numpy-2.5.2-cp312-cp312-macosx_11_0_arm64.whl"
      sha256 "4bbd96c833ecc8cc069ce518078fc8c60cb9cbfb0fea5b7a803ad65035596d03"
    end

    resource "pygame" do
      url "https://files.pythonhosted.org/packages/cd/53/77ccbc384b251c6e34bfd2e734c638233922449a7844e3c7a11ef91cee39/pygame-2.6.1-cp312-cp312-macosx_11_0_arm64.whl"
      sha256 "c8040ea2ab18c6b255af706ec01355c8a6b08dc48d77fd4ee783f8fc46a843bf"
    end

    resource "tcod" do
      url "https://files.pythonhosted.org/packages/65/16/95919304c6552e15803893660e3115e504d01540aa6e12e9f511b12c7d31/tcod-21.2.1-cp310-abi3-macosx_10_13_universal2.whl"
      sha256 "a481b535f93d0befd71721b198163e69217560a559b044dfb85cf50f1feaae02"
    end
  end

  on_intel do

    resource "cffi" do
      url "https://files.pythonhosted.org/packages/10/69/43965eccfdead3b9220015fd1320e117be8c6ed01a62ffab76eeb752f5d5/cffi-2.1.1-cp312-cp312-macosx_10_15_x86_64.whl"
      sha256 "c8c69575568085ba0b1b10c0249d779a214aea6f6522e949a0fc9fb0fcb449d0"
    end

    resource "numpy" do
      url "https://files.pythonhosted.org/packages/69/72/dccb0aaf40972777283303919f613964227266d0c13adebb79ac124f1c3e/numpy-2.5.2-cp312-cp312-macosx_10_13_x86_64.whl"
      sha256 "14e373cfc6387177e8409dac3c7159be8eb05cd77096cd7c950268b86f62831c"
    end

    resource "pygame" do
      url "https://files.pythonhosted.org/packages/92/16/2c602c332f45ff9526d61f6bd764db5096ff9035433e2172e2d2cadae8db/pygame-2.6.1-cp312-cp312-macosx_10_9_x86_64.whl"
      sha256 "4ee7f2771f588c966fa2fa8b829be26698c9b4836f82ede5e4edc1a68594942e"
    end

    resource "tcod" do
      url "https://files.pythonhosted.org/packages/65/16/95919304c6552e15803893660e3115e504d01540aa6e12e9f511b12c7d31/tcod-21.2.1-cp310-abi3-macosx_10_13_universal2.whl"
      sha256 "a481b535f93d0befd71721b198163e69217560a559b044dfb85cf50f1feaae02"
    end
  end
  # ===== end resources =====

  def install
    # Homebrew's virtualenv_install_with_resources only installs a resource
    # as a wheel FILE when its URL matches the pure-wheel pattern
    # (py3-none-any); binary wheels get staged as extracted directories and
    # pip rejects those under --no-binary=:all: ("Neither 'setup.py' nor
    # 'pyproject.toml' found"). So: pure wheels go through brew's normal
    # path, binary wheels are installed from the cached wheel file itself -
    # pip accepts explicit wheel files even with --no-binary=:all:.
    #
    # The game runs as a Python script launched from the terminal, so there
    # is no .app bundle for Gatekeeper or LaunchServices to assess - no
    # quarantine, no signature requirement, works on macOS 15+ with no
    # bypass.
    venv = virtualenv_create(libexec, "python3.12")
    resources.each do |r|
      if r.url&.match?("[.-]py3[^-]*-none-any.whl$")
        venv.pip_install r
      else
        r.stage do
          venv.pip_install r.cached_download
        end
      end
    end
    venv.pip_install_and_link buildpath
  end

  test do
    assert_predicate bin/"spacehack", :exist?
    system Formula["python@3.12"].opt_bin/"python3.12", "-c", "import spacehack.__main__"
  end
end
