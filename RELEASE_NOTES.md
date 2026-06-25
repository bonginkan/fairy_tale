# Release Notes

## 0.2.2

- Added closure/frame-completeness checks before negative-space discovery so
  agents do not treat a visible or stated item count as exhaustive without
  evidence.
- Added negative-space discovery, recall/noise guards, Tier A/B/C handling,
  precision/taste learning signals, and problem-finding cards to the Fairy Tale
  process templates.
- Updated skill and plugin discovery descriptions so closure and latent-need
  review tasks can trigger the Fairy Tale skill.

## Public Release Preparation

This release prepares Fairy Tale for public distribution as an Apache-2.0
workflow-augmentation package.

Highlights:

- Added root Apache-2.0 licensing and NOTICE terms.
- Clarified that Fairy Tale studies public reports and reproducible workflow
  patterns, not restricted model weights or bypass techniques.
- Packaged Fairy Tale skills for generic agents, Codex, and Claude Code.
- Added Codex and Claude Code plugin manifests.
- Included defensive security constraints, best-practice gates, benchmark
  validation notes, OSS watch notes, adapters, runners, and sample comparison
  outputs.
- Added a wide Fairy Tale logo asset for repository branding.

Known boundaries:

- Benchmark rows are reproducible local measurements, not final leaderboard
  claims.
- Third-party repositories, datasets, benchmark materials, reports, and assets
  remain under their own licenses and terms.
- Security workflows are defensive-only.
