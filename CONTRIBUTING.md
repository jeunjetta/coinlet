# Contributing to coinlet

Thank you for your interest in contributing! This guide covers the development workflow, quality standards, and dependency policy.

## Quick Start

```bash
# Clone and install
git clone https://github.com/jeunjetta/coinlet.git
cd coinlet
uv sync --dev

# Run all checks (do this before every PR)
make check

# Or run individual checks
make lint      # Linting with security rules
make test      # Tests with coverage
make audit     # Dependency vulnerability scan
make secrets   # Secret detection
```

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Write Tests First

Every code change needs tests. Write a failing test before implementing:

```bash
# Run tests in watch mode during development
uv run pytest tests/ -v --tb=short
```

Aim for the coverage threshold (60%). New features should have higher coverage.

### 3. Run All Checks

Before opening a PR, run the full check suite:

```bash
make check
```

This runs:
- **Lint**: ruff with security rules (S/bandit-equivalent)
- **Format**: Code style check
- **Test**: pytest with coverage threshold
- **Audit**: pip-audit for dependency vulnerabilities
- **Secrets**: gitleaks for hardcoded credentials

All checks must pass before the PR can be merged.

### 4. Commit and Push

```bash
git add .
git commit -m "feat: add awesome feature"
git push -u origin feature/your-feature-name
```

### 5. Open a Pull Request

CI will automatically run all checks. Required status checks must pass before merge.

## Code Standards

### Linting

We use [ruff](https://docs.astral.sh/ruff/) with these rule sets:

- **E/W**: pycodestyle errors and warnings
- **F**: pyflakes
- **I**: isort (import sorting)
- **S**: flake8-bandit (security)
- **B**: flake8-bugbear
- **C4**: flake8-comprehensions
- **UP**: pyupgrade
- **RUF**: ruff-specific rules

Fix lint errors with:

```bash
make fix  # Auto-fix what's possible
```

### Security

The S rules catch common security issues:
- Hardcoded passwords/secrets
- Use of `eval()` or `exec()`
- SQL injection risks
- Insecure random number generation
- And more

If you need to suppress a security warning, add an inline comment explaining why:

```python
password = os.environ["DB_PASSWORD"]  # noqa: S105 - loaded from env, not hardcoded
```

## Dependency Policy

### Adding New Dependencies

Before adding a new dependency, consider:

1. **Is it necessary?** Can you achieve the same with stdlib or existing deps?
2. **Is it well-maintained?** Check:
   - Recent commits (active in last 6 months)
   - Responsive to issues/PRs
   - Multiple maintainers (not abandoned if one leaves)
3. **Is it popular?** Higher download counts = more eyes = bugs found faster
4. **Is it from a trusted source?** Beware of:
   - Typosquatting (e.g., `reqeusts` instead of `requests`)
   - Packages with no history that appeared recently
   - Install-time scripts from unknown sources

### Process

1. Add to `pyproject.toml` with a minimum version constraint
2. Run `uv lock` to update the lockfile
3. Commit both `pyproject.toml` and `uv.lock`
4. In your PR, briefly justify the new dependency

### Lockfile

The `uv.lock` file is committed and must stay in sync:
- It contains hashes for reproducible, secure builds
- CI fails if it's out of sync with `pyproject.toml`
- Never edit it manually; always use `uv lock`

## Pre-commit Hooks

Optional but recommended for catching issues early:

```bash
uv run pre-commit install
```

This runs fast checks (ruff, gitleaks, file hygiene) on every commit. Full tests run in CI.

## CI/CD

Every push and PR triggers:

| Check | What it does |
|-------|--------------|
| Lint & Format | ruff with security rules |
| Test & Coverage | pytest with 70% threshold |
| Dependency Audit | pip-audit for vulnerabilities |
| Lockfile Sync | Ensures uv.lock matches pyproject.toml |
| Secret Scan | gitleaks on full history |
| Dependency Review | Blocks moderate+ vulns, GPL/AGPL licenses (PRs only) |
| CodeQL | GitHub's semantic code analysis |

All checks must pass before merge.

## Questions?

Open an issue or check the existing documentation:
- [README.md](README.md) — Project overview and usage
- [SECURITY.md](SECURITY.md) — Security policy and checks explained
- [AGENTS.md](AGENTS.md) — Instructions for AI coding agents

---

*Based on engineering practices from [mattpocock/skills](https://github.com/mattpocock/skills): write tests first, run checks before every PR, and keep dependencies lean and vetted.*
