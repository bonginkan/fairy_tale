# Excess Dogfood Iteration 2

Status: self-review artifact for the Fairy Tale loop pilot.

Scope: apply the Excess / Redundancy / Legacy-Surface Discovery harness to
`fairy_tale` itself after the 0.2.5 runtime promotion.

Guardrail: this pass does not delete files. Mistaken removal is the worst
failure mode, so findings stop at issues, migration questions, or intentional
keep records unless zero-use and compatibility are independently proven.

## Inputs

```text
repo: bonginkan/fairy_tale
base: c5d0088d8016fa962fbcd28d33a2f5aa37858995
trigger: dogfood the new subtractive review harness against its own repo
review card: skills/fairy-tale/references/process.md
implementer: Codex MISA
reviewers: MISA 3, CC MISA
```

Existing open issues were checked before creating new work. Issue #7 covers CI
checks, issue #8 covers a future CLI entrypoint, and issue #3 covers the
distribution umbrella. None directly covers the residency marker metadata
source-of-truth gap below.

## Finding 1: Residency Marker Metadata Is Manually Duplicated

```text
candidate surface: scripts/fairy_tale_residency_check.py artifact marker tables
surface type: duplicate
classification: consolidate-later
surface form: issue
issue: https://github.com/bonginkan/fairy_tale/issues/22
```

Evidence:

- `LATENT_STRUCTURE_FILES` contains 7 path entries, including 4
  `plugins/fairy-tale/...` mirror entries.
- `AGENTIC_LOOP_FILES` contains 9 path entries, including 4 plugin mirror
  entries.
- `LOOP_ENGINEERING_FILES` and `INSTALL_SMOKE_FILES` each duplicate one
  root/plugin artifact pair.
- `scripts/fairy_tale_residency_check.py` and
  `plugins/fairy-tale/scripts/fairy_tale_residency_check.py` are byte-identical
  mirrors, so every metadata change also needs copy parity.
- PR #21 showed the failure mode: adding a harness required marker edits, and a
  marker split across lines initially caused residency to fail until the marker
  was made stable.

Why not remove now:

- The mirrored artifacts are intentional distribution surfaces, not dead code.
- The plugin package must validate both root and plugin-shipped artifacts.
- Removing plugin-specific checks would weaken residency coverage.

Required companion work:

- Keep root and plugin artifact validation fail-closed.
- Derive mechanical plugin mirror paths from canonical root paths where
  possible, or introduce a small helper that defines marker sets once and emits
  both root and plugin checks.
- Preserve readable failure labels for PR review.
- Validate with residency, inject, install smoke, and root/plugin script parity.

## Finding 2: Mirrored Skill And Plugin Trees Are Intentional

```text
candidate surface: skills, .agents/skills, .claude/skills, plugins/fairy-tale/skills
surface type: duplicate
classification: keep-intentionally
surface form: PR finding
```

Evidence:

- `skills/fairy-tale/SKILL.md`, `.agents/skills/fairy-tale/SKILL.md`,
  `.claude/skills/fairy-tale/SKILL.md`, and
  `plugins/fairy-tale/skills/fairy-tale/SKILL.md` currently have matching
  content hashes.
- The same is true for `fairy-tale/references/process.md` and
  `fairy-tale/references/loop-engineering-automation.md` across the four skill
  roots.
- `docs/fairy-tale-residency-harness.md` documents these copies as checked
  residency surfaces, and `docs/best-practices.md` says plugin copies mirror
  the canonical skill and references before publishing.

Why it stays:

- These copies serve different agent/plugin runtimes.
- Residency checks compare them against canonical `skills/` and fail on drift.
- Deleting them would break repo-local Codex/AGENTS, Claude Code, and plugin
  distribution paths.

Learning signal: `accepted_keep`.

## Finding 3: Ignored Python Cache Files Are Not Repo Findings

```text
candidate surface: scripts/__pycache__ and plugins/fairy-tale/scripts/__pycache__
surface type: generated cache
classification: rejected_false_positive
surface form: no issue
```

Evidence:

- Local temp clones can contain `*.pyc` after validation commands run.
- `git ls-files` shows no tracked `__pycache__` / `*.pyc` entries.
- `.gitignore` ignores `__pycache__/`, and `git check-ignore -v` confirms the
  generated cache paths are ignored.

Why no action:

- The files are local validation byproducts, not tracked repo surfaces.
- Removing ignored temp files from a local clone would not improve the repo.
- If a `*.pyc` file ever becomes tracked, it should become a normal
  `remove-now` candidate with a focused validator.

Learning signal: `rejected_false_positive`.

## Summary

No direct deletion is justified from this pass. The only actionable repo change
is issue #22, which asks for consolidation of residency marker metadata while
preserving the intentional mirrored distribution surfaces.
