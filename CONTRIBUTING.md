# Contributing

Thank you for improving Fairy Tale.

## Contribution Principles

- Preserve provenance for claims, benchmark rows, and source-derived workflow
  rules.
- Treat public reports as anecdotal until independently reproduced.
- Keep security work defensive-only and authorized.
- Do not add restricted-model bypass, export-control bypass, exploit
  weaponization, persistence, stealth, credential theft, or unsafe operational
  guidance.
- Keep changes small, reviewable, and validated.

## Development

- Use the repository skill at `.agents/skills/fairy-tale/SKILL.md` or the
  canonical skill at `skills/fairy-tale/SKILL.md` when changing Fairy Tale
  workflows.
- Validate Rust changes with `cargo metadata --no-deps --format-version 1` and
  relevant targeted checks.
- Validate plugin manifest changes with the Codex plugin validator when
  available.
- Keep generated benchmark downloads, virtualenvs, and scratch data under
  ignored `tmp/` paths unless an artifact is intentionally curated for release.

## Licensing

Contributions to repository code, skills, adapters, schemas, scripts, and
documentation are accepted under Apache-2.0 unless explicitly stated otherwise.
The Fairy Tale name, logo, and other brand assets are not licensed under
Apache-2.0; see `NOTICE`.
