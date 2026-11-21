# Agent Instructions for coinlet

This file provides instructions for AI coding agents working on this repository.

## Available Skills

### Matt Pocock Skills (in `~/.cursor/skills-mattpocock/skills/`)

These skills are automatically available in your environment. Use them for disciplined engineering:

- **`/grill-with-docs`** - Before starting work, get grilled on requirements to ensure alignment
- **`/tdd`** - Test-driven development with red-green-refactor loop
- **`/diagnosing-bugs`** - Disciplined debugging: reproduce → minimize → hypothesize → fix
- **`/code-review`** - Two-axis review: Standards + Spec compliance
- **`/retro`** - After completing work, suggest improvements to the codebase/environment
- **`/improve-codebase-architecture`** - Scan for architectural improvements

To use a skill, read it from `~/.cursor/skills-mattpocock/skills/engineering/<skill-name>/SKILL.md`.

### Chrome DevTools MCP

Browser automation and debugging is available via chrome-devtools-mcp. Use it for:
- Performance profiling of web interfaces
- Screenshot capture for documentation
- Browser-based testing and debugging

## Required Workflow

**BEFORE committing any code, you MUST run:**

```bash
bash .cursor/pre-commit-checks.sh
```

This runs:
1. **Linting** - `ruff check` for code quality
2. **Format check** - `ruff format --check` for consistent style
3. **Tests** - `pytest` to ensure nothing is broken
4. **Security audit** - `pip-audit` to check for vulnerable dependencies
5. **Secrets check** - Scan for accidentally committed credentials

Only commit if all checks pass. Fix any issues before committing.

## After Completing Work

After finishing a task, consider running `/retro` from Matt Pocock's skills to:
- Identify improvements to the development environment
- Suggest additions to coding standards
- Recommend tooling or automation improvements

## Project Structure

```
coinlet/
├── src/coinlet/     # Main package source
├── tests/           # Test files
├── notebooks/       # Marimo notebooks for exploration
├── scripts/         # Utility scripts
├── docs/            # Documentation
└── .cursor/         # Cloud Agent environment config
```

## Development Commands

```bash
# Install dependencies
uv sync --group dev

# Run tests
uv run pytest

# Run specific test
uv run pytest tests/test_something.py -v

# Lint
uv run ruff check src/ tests/

# Format
uv run ruff format src/ tests/

# Security audit
pip-audit -r <(uv pip compile pyproject.toml)
```

## Code Style

- Follow existing patterns in the codebase
- Use type hints for all function signatures
- Write docstrings for public functions
- Keep functions focused and testable
- Prefer composition over inheritance
