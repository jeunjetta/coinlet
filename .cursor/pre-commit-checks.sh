#!/usr/bin/env bash
set -euo pipefail

# Pre-commit checks for Cloud Agents
# Run this BEFORE committing code to ensure quality and security

# Add common tool paths
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:/usr/local/bin:$PATH"

# Helper to run Python tools (via uv if available, else direct)
run_py() {
    if command -v uv >/dev/null 2>&1; then
        uv run "$@"
    elif [ -f ".venv/bin/python" ]; then
        .venv/bin/python -m "$@"
    else
        python3 -m "$@"
    fi
}

echo "========================================"
echo "  Running Pre-Commit Checks"
echo "========================================"

FAILED=0

# 1. Linting with ruff
echo ""
echo "--- Linting (ruff) ---"
if run_py ruff check src/ tests/; then
    echo "✓ Linting passed"
else
    echo "✗ Linting failed"
    FAILED=1
fi

# 2. Format check with ruff
echo ""
echo "--- Format check (ruff format) ---"
if run_py ruff format --check src/ tests/; then
    echo "✓ Format check passed"
else
    echo "✗ Format check failed - run 'ruff format src/ tests/' to fix"
    FAILED=1
fi

# 3. Type checking (if mypy is available)
echo ""
echo "--- Type checking ---"
if run_py mypy --version >/dev/null 2>&1; then
    if run_py mypy src/ --ignore-missing-imports 2>/dev/null; then
        echo "✓ Type check passed"
    else
        echo "⚠ Type check had issues (non-blocking)"
    fi
else
    echo "⚠ mypy not installed, skipping type check"
fi

# 4. Run tests
echo ""
echo "--- Running tests ---"
if run_py pytest tests/ -x -q --tb=short; then
    echo "✓ Tests passed"
else
    echo "✗ Tests failed"
    FAILED=1
fi

# 5. Security audit - Python packages
echo ""
echo "--- Security audit (pip-audit) ---"
if command -v pip-audit >/dev/null 2>&1; then
    if pip-audit --progress-spinner off 2>/dev/null; then
        echo "✓ No known vulnerabilities in Python packages"
    else
        echo "⚠ Security vulnerabilities found (review recommended)"
    fi
elif command -v uv >/dev/null 2>&1; then
    echo "Running uv-based audit..."
    if uv pip compile pyproject.toml -o /tmp/requirements-audit.txt 2>/dev/null; then
        pip-audit -r /tmp/requirements-audit.txt --progress-spinner off 2>/dev/null || echo "⚠ Audit incomplete"
    fi
else
    echo "⚠ pip-audit not installed, skipping Python security audit"
    echo "  Install with: pip install pip-audit"
fi

# 6. Security audit - npm packages (for TypeScript projects)
if [ -f "package.json" ]; then
    echo ""
    echo "--- Security audit (npm) ---"
    if npm audit --audit-level=moderate 2>/dev/null; then
        echo "✓ No high/critical vulnerabilities in npm packages"
    else
        echo "⚠ npm vulnerabilities found (review recommended)"
    fi
fi

# 7. Check for secrets/sensitive data
echo ""
echo "--- Checking for secrets ---"
# Check staged files for potential secrets (excluding common false positives)
SECRETS_FOUND=0
while IFS= read -r file; do
    if [ -f "$file" ] && grep -qE "(api_key|secret_key|password|private_key|AWS_SECRET|GITHUB_TOKEN)\s*[:=]" "$file" 2>/dev/null; then
        echo "⚠ Potential secret in: $file"
        SECRETS_FOUND=1
    fi
done < <(git diff --cached --name-only 2>/dev/null || git diff --name-only HEAD~1 2>/dev/null || find . -name "*.py" -o -name "*.ts" -o -name "*.js" -o -name "*.env*" 2>/dev/null | head -50)

if [ $SECRETS_FOUND -eq 0 ]; then
    echo "✓ No obvious secrets detected"
fi

echo ""
echo "========================================"
if [ $FAILED -eq 0 ]; then
    echo "  All checks passed ✓"
    echo "========================================"
    echo ""
    echo "💡 Consider running /retro after completing your task"
    echo "   to identify improvements for the codebase."
    exit 0
else
    echo "  Some checks failed ✗"
    echo "========================================"
    exit 1
fi
