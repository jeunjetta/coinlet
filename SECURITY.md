# Security Policy

## Supported Versions

Only the latest commit on the `main` branch is supported. There are no versioned releases with backported security fixes.

## Reporting a Vulnerability

**Do not report security vulnerabilities through public GitHub issues.**

Please report vulnerabilities privately using GitHub's **"Report a vulnerability"** feature:

1. Go to the **Security** tab of this repository
2. Click **"Report a vulnerability"**
3. Fill out the advisory form with details about the issue

This creates a private draft advisory visible only to you and the maintainers.

### What to Expect

- **Response time**: Best-effort; this is a small personal project with no SLA
- **No bug bounty**: This project does not offer monetary rewards for vulnerability reports
- **Acknowledgment**: Valid reports will be credited in the fix commit (if you wish)

## Scope

This policy covers:

- The `coinlet` Python package (`src/coinlet/`)
- Example notebooks (`notebooks/`)
- CI/CD workflows (`.github/workflows/`)

---

## Security Checks Explained

This project uses multiple layers of automated security checks. Here's what each one does and why it matters.

### Ruff Security Rules (S/Bandit)

**What**: Static analysis that catches common security mistakes in Python code.

**Why**: Finds issues like hardcoded passwords, use of dangerous functions (`eval`, `exec`), SQL injection patterns, weak cryptography, and more — before the code ever runs.

**Examples it catches**:
- `password = "secret123"` — hardcoded credential
- `eval(user_input)` — arbitrary code execution
- `cursor.execute(f"SELECT * FROM users WHERE id={id}")` — SQL injection

### pip-audit

**What**: Scans all dependencies against the Python Advisory Database for known vulnerabilities.

**Why**: Even if your code is secure, a vulnerable dependency can compromise everything. pip-audit checks every package in `uv.lock` against CVE databases.

**What happens**: CI fails if any dependency has a known vulnerability. Update the affected package or find an alternative.

### Gitleaks

**What**: Scans the entire git history for accidentally committed secrets (API keys, tokens, passwords, private keys).

**Why**: Secrets committed even once are compromised — they exist in git history forever unless you rewrite it. Gitleaks catches them before push.

**What it finds**: AWS keys, GitHub tokens, private keys, generic API keys, passwords in URLs, and 100+ other secret patterns.

### Dependency Review (PRs only)

**What**: GitHub's supply-chain security check that analyzes dependency changes in pull requests.

**Why**: Catches risky dependency additions before they're merged:
- Vulnerabilities (fails on moderate severity or higher)
- License issues (blocks GPL-3.0, AGPL-3.0 — copyleft licenses incompatible with MIT)
- Malicious packages (checks against GitHub's advisory database)

### CodeQL

**What**: GitHub's semantic code analysis that understands data flow through your program.

**Why**: Finds vulnerabilities that simple pattern matching misses — like a user input that flows through several functions before reaching a dangerous sink. Catches injection flaws, authentication issues, and more.

### Lockfile Sync Check

**What**: Verifies that `uv.lock` is in sync with `pyproject.toml`.

**Why**: The lockfile contains exact versions and hashes for reproducible, secure builds. If it's out of sync, you might install different (potentially vulnerable) versions than intended.

---

## API Key Safety

This project uses public exchange APIs (Coinbase, Yahoo Finance) for price data. These APIs do **not** require authentication for the read-only operations this package performs.

**Important for users**:

- **Never commit API keys** to this repository or your forks
- Use **environment variables** for any credentials in your own scripts
- If using exchange APIs for trading (not part of this project), use **read-only API keys** without trading or withdrawal permissions
- Keep secrets in `.env` files (which are git-ignored)

If you accidentally commit a secret, consider it compromised and revoke it immediately.

---

## Recommended GitHub Settings

After making this repository public, enable these security features in **Settings**:

### Branch Protection / Rulesets (Settings → Rules → Rulesets)

Create a ruleset for `main` with:

| Setting | Recommendation |
|---------|----------------|
| **Require pull request** | ✅ Enabled — no direct pushes to main |
| **Required status checks** | ✅ Require these to pass before merge (see list below) |
| **Require branches up to date** | ✅ PR must be rebased on latest main |
| **Block force pushes** | ✅ Enabled — protects history |
| **Block deletions** | ✅ Enabled — prevents accidental deletion |
| **Require linear history** | ✅ Recommended — cleaner git history |
| **Require approvals** | Optional: 1 approval for extra review |

**Required status checks** (exact names from CI):

```
Lint & Format
Test & Coverage
Dependency Audit
Lockfile Sync
Secret Scan
Dependency Review
CodeQL
```

> **Note**: GitHub can't block opening a PR — enforcement happens at merge via required checks.

### Code Security (Settings → Code security)

| Setting | Recommendation |
|---------|----------------|
| **Dependabot alerts** | ✅ Enabled — notifies of vulnerable dependencies |
| **Dependabot security updates** | ✅ Enabled — auto-creates PRs for security fixes |
| **Secret scanning** | ✅ Enabled — detects secrets pushed to repo |
| **Push protection** | ✅ Enabled — blocks pushes containing secrets |
| **Private vulnerability reporting** | ✅ Enabled — allows private security reports |
| **CodeQL default setup** | ✅ Enabled for Python |

### Actions Security (Settings → Actions → General)

| Setting | Recommendation |
|---------|----------------|
| **Fork PR workflows** | Require approval for first-time contributors |
| **Workflow permissions** | Read repository contents (least privilege) |
| **Allow GitHub Actions** | Allow actions from GitHub, verified creators, and specified actions only |

### Repository Settings

| Setting | Location | Recommendation |
|---------|----------|----------------|
| **Auto-delete head branches** | Settings → General | ✅ Enabled — cleans up after merge |
| **2FA on account** | Account settings | ✅ Required — protects against account compromise |

---

## For Maintainers

### Responding to Dependabot Alerts

1. Review the alert severity and affected package
2. Check if the vulnerability affects our usage
3. If yes: merge the Dependabot PR or manually update
4. If no (we don't use the vulnerable feature): dismiss with reason

### Responding to Secret Leaks

If a secret is detected:

1. **Immediately revoke** the compromised credential
2. Generate a new credential
3. Update any services using the old credential
4. If the leak was in a PR, do NOT merge — ask contributor to remove from history
5. If already in main, consider whether history rewrite is necessary

### Keeping Actions Pinned

When updating GitHub Actions:

1. Find the new version's full commit SHA
2. Update the SHA in workflow files
3. Keep the version comment (e.g., `# v4`) for readability
