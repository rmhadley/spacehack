cask "spacehack" do
  version "0.3.3"
  sha256 "53c45e0cd79003e2ce78c0184dcfc50c11deff3930d54f00b75430d776fa2976"

  url "https://github.com/rmhadley/spacehack/releases/download/v#{version}/spacehack-macos.zip"
  name "Spacehack"
  desc "ASCII-art sci-fi roguelike"
  homepage "https://github.com/rmhadley/spacehack"

  app "spacehack.app"

  caveats <<~EOS
    Spacehack is ad-hoc signed (no paid Developer ID, no notarization).
    Homebrew does not apply the quarantine attribute to cask installs, so
    the app opens normally without any Gatekeeper bypass.
  EOS
end
