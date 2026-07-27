#!/bin/bash
# macOS double-click launcher for spacehack.
# In Terminal.app, make this file executable:
#   chmod +x run_spacehack.command
cd "$(dirname "$0")" || exit 1
python3 run.py
if [ $? -ne 0 ]; then
    echo
    echo "Failed to launch. Make sure Python 3.10+ is installed."
    echo "Press Enter to close..."
    read -r
fi
