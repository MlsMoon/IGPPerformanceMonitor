# Security Policy

## Supported versions

Security fixes are applied to the latest tagged release on GitHub.

## Reporting a vulnerability

Please **do not** open a public issue for security reports.

Use [GitHub Security Advisories](https://github.com/MlsMoon/IGPPerformanceMonitor/security/advisories/new) or email the maintainer listed on the repository profile.

Include:

- Affected version / commit
- Reproduction steps
- Impact (privilege, data exposure, remote code)

## Secrets

Never commit cloud keys, tokens, or private config.

- CI must use GitHub Actions secrets only when a secret is actually required
- Release publishing uses `GITHUB_TOKEN` (no third-party object-storage keys)
- Local files such as `.claude/settings.local.json` stay untracked
