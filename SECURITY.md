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

## API Key Safety

This project uses public exchange APIs (Coinbase, Yahoo Finance) for price data. These APIs do **not** require authentication for the read-only operations this package performs.

**Important for users:**

- **Never commit API keys** to this repository or your forks
- Use **environment variables** for any credentials in your own scripts
- If using exchange APIs for trading (not part of this project), use **read-only API keys** without trading or withdrawal permissions
- Keep secrets in `.env` files (which are git-ignored)

If you accidentally commit a secret, consider it compromised and revoke it immediately.
