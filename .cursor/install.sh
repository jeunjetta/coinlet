#!/usr/bin/env bash
set -euo pipefail

echo "=== Installing project dependencies ==="
uv sync --frozen 2>/dev/null || uv sync

echo "=== Installing dev dependencies ==="
uv sync --group dev --frozen 2>/dev/null || uv sync --group dev

echo "=== Setting up Matt Pocock skills ==="
SKILLS_DIR="$HOME/.cursor/skills-mattpocock"
if [ -d "$SKILLS_DIR" ]; then
    echo "Updating Matt Pocock skills..."
    cd "$SKILLS_DIR" && git pull --ff-only || true
    cd -
else
    echo "Cloning Matt Pocock skills..."
    git clone --depth 1 https://github.com/mattpocock/skills.git "$SKILLS_DIR"
fi

echo "=== Installing security scanning tools ==="
# Ensure pip-audit is available (may already be in image)
command -v pip-audit >/dev/null || pip3 install --user pip-audit safety

# Install npm audit-related tools for TypeScript projects
npm install -g npm-audit-resolver snyk 2>/dev/null || true

echo "=== Setting up chrome-devtools-mcp ==="
# Pre-cache the MCP server
npx -y chrome-devtools-mcp@latest --version 2>/dev/null || true

echo "=== Environment setup complete ==="
