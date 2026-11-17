# Security Policy

## Reporting a vulnerability

Please report vulnerabilities privately through GitHub's
[private vulnerability reporting](../../security/advisories/new) rather than opening a public issue.

## Notes

- FDE Coach only calls public, unauthenticated job-board APIs (Greenhouse, Lever, Ashby). It needs no API keys.
- Your data (`data/fde.db`, `reports/`, `config.toml`) stays on your machine and is git-ignored. Don't commit it.
