# Agent Instructions

Standing brief for AI coding agents working on coinlet. Keep this short and declarative.

## Commands

```bash
make check      # Run ALL checks before any PR (lint, format, test, audit, secrets)
make test       # Run tests with coverage
make lint       # Lint only
uv sync --dev   # Install dependencies
```

Cloud Agent environments may also run `bash .cursor/pre-commit-checks.sh` (same intent). Prefer `make check` — it is the canonical gate before any PR.

## Hard Constraints

- **Never commit secrets.** No API keys, tokens, passwords, or private keys in code or config. Use environment variables. If you accidentally add one, stop and tell the user immediately.
- **Every code change needs tests.** Write a failing test first, then implement. This is non-negotiable for new features and bug fixes.
- **Run `make check` before opening any PR.** All checks must pass locally before pushing.
- **Keep `uv.lock` committed.** The lockfile ensures reproducible builds with hashes. Run `uv lock` after changing dependencies.

## Available Skills

### Matt Pocock Skills (in `~/.cursor/skills-mattpocock/skills/`)

When available in the Cloud Agent environment:

- **`/grill-with-docs`** — Align on requirements before starting
- **`/tdd`** — Red-green-refactor loop
- **`/diagnosing-bugs`** — Reproduce → minimize → hypothesize → fix
- **`/code-review`** — Standards + Spec compliance
- **`/retro`** — After work, suggest environment/codebase improvements
- **`/improve-codebase-architecture`** — Scan for architectural improvements

Read skills from `~/.cursor/skills-mattpocock/skills/engineering/<skill-name>/SKILL.md`.

### Chrome DevTools MCP

When configured: performance profiling, screenshots, browser-based debugging.

## Code Review Checklist

Before marking work complete, verify:

1. All tests pass with `make test`
2. No lint errors with `make lint`
3. No new security warnings from ruff's S rules
4. No hardcoded secrets or credentials
5. New dependencies justified and vetted (see CONTRIBUTING.md)

## Security Awareness

Flag and report immediately if you see:

- Hardcoded credentials or API keys
- Use of `eval()`, `exec()`, or `pickle` with untrusted data
- SQL queries built with string concatenation
- Shell commands with unsanitized user input
- Disabled SSL verification or weak crypto
- Dependencies from unknown sources or with suspicious names

## Architecture Notes

- `src/coinlet/` — Main package (transform, plot, data sources)
- `tests/` — Pytest tests (mirror src structure)
- `notebooks/` — Marimo interactive notebooks
- `data/` — Sample data files (Parquet, CSV)
- `.cursor/` — Cloud Agent environment config

The package uses public exchange APIs (Coinbase, Yahoo Finance) for price data. These do NOT require API keys for the read-only operations we perform.

---

*Design note: This file follows the pattern from [mattpocock/skills](https://github.com/mattpocock/skills) — keep it short, declarative, and focused on what the agent can't derive from code. Style guides and detailed docs belong elsewhere.*
