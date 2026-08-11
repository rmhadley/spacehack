#!/bin/bash
# Open Spacehack.command — double-clickable macOS launcher.
#
# macOS stamps com.apple.quarantine (and, on macOS 13+, com.apple.provenance)
# on anything that arrives from the internet, which makes Gatekeeper reject
# the ad-hoc-signed app as "damaged" / "unidentified developer".  Clearing the
# attributes (xattr -cr) lets it run without a paid Developer ID certificate.
# The .command itself may prompt once in Terminal — click Open.
#
# Keep this file in the same folder as spacehack.app.
set -e
cd "$(dirname "$0")"

APP="$(pwd)/spacehack.app"
if [ ! -d "$APP" ]; then
    echo "spacehack.app not found next to this launcher."
    echo "Keep 'Open Spacehack.command' in the same folder as spacehack.app."
    read -r -p "Press Enter to close… " _
    exit 1
fi

xattr -cr "$APP" 2>/dev/null || true
open "$APP"
