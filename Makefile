# coinlet development commands
# Run `make check` before every PR to catch problems early.

.PHONY: help install check lint format test audit secrets clean

PYTHON := uv run python
PYTEST := uv run pytest
RUFF := uv run ruff
PIP_AUDIT := uv run pip-audit

help:
	@echo "coinlet development commands"
	@echo ""
	@echo "  make install   - Install dependencies"
	@echo "  make check     - Run ALL checks (lint, format, test, audit, secrets)"
	@echo "  make lint      - Run ruff linter with security rules"
	@echo "  make format    - Check code formatting"
	@echo "  make test      - Run tests with coverage"
	@echo "  make audit     - Scan dependencies for vulnerabilities"
	@echo "  make secrets   - Scan for hardcoded secrets"
	@echo "  make clean     - Remove build artifacts"
	@echo ""
	@echo "Run 'make check' before opening a PR."

install:
	uv sync --dev

# Main check target - runs everything
check: lint format test audit secrets
	@echo ""
	@echo "✅ All checks passed!"

lint:
	@echo "🔍 Running ruff linter (includes security rules)..."
	$(RUFF) check src/ tests/

format:
	@echo "🎨 Checking code formatting..."
	$(RUFF) format --check src/ tests/

test:
	@echo "🧪 Running tests with coverage..."
	$(PYTEST) tests/ -v --tb=short --cov=src/coinlet --cov-report=term-missing --cov-fail-under=60

audit:
	@echo "🔒 Auditing dependencies for vulnerabilities..."
	$(PIP_AUDIT) --progress-spinner=off

secrets:
	@echo "🔑 Scanning for hardcoded secrets..."
	@if command -v gitleaks >/dev/null 2>&1; then \
		gitleaks detect --source . --verbose --no-git; \
	else \
		echo "⚠️  gitleaks not installed. Install with: brew install gitleaks (macOS) or see https://github.com/gitleaks/gitleaks#installing"; \
		echo "   Skipping secret scan locally. CI will catch any issues."; \
	fi

# Format code (fix, not just check)
fix:
	@echo "🔧 Auto-formatting code..."
	$(RUFF) format src/ tests/
	$(RUFF) check --fix src/ tests/

# Verify lockfile is in sync
lock-check:
	@echo "🔐 Verifying lockfile is in sync..."
	uv lock --check

clean:
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov dist build *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
