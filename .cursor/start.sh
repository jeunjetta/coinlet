#!/usr/bin/env bash
set -euo pipefail

echo "=== Cloud Agent environment starting ==="

# Set Chrome executable path for headless browser tools
export CHROME_PATH="${CHROME_PATH:-/usr/bin/chromium-browser}"
export PUPPETEER_EXECUTABLE_PATH="$CHROME_PATH"

echo "Chrome path: $CHROME_PATH"
echo "Matt Pocock skills: $HOME/.cursor/skills-mattpocock"
echo "=== Ready ==="
