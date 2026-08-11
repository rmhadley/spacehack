cask "spacehack" do
  version "0.3.3"
  sha256 "53c45e0cd79003e2ce78c0184dcfc50c11deff3930d54f00b75430d776fa2976"

  url "https://github.com/rmhadley/spacehack/releases/download/v#{version}/spacehack-macos.zip"
  name "Spacehack"
  desc "ASCII-art sci-fi roguelike"
  homepage "https://github.com/rmhadley/spacehack"

  app "spacehack.app"

  # The release .app is ad-hoc signed (no Developer ID, no notarization).
  # Homebrew doesn't apply com.apple.quarantine to cask installs, but
  # browsers/Downloads can still leave extended attributes on the files,
  # which Gatekeeper flags on first launch. Strip every xattr after the
  # app lands in /Applications so it opens cleanly on macOS 15+.
  postflight do
    system_command "/usr/bin/xattr",
                   args: ["-cr", "#{appdir}/spacehack.app"]
  end

  caveats <<~EOS
    Spacehack is ad-hoc signed (no paid Developer ID, no notarization).
    The cask strips extended attributes from the installed app (postflight
    xattr -cr), so it opens without any Gatekeeper bypass.
  EOS
end
