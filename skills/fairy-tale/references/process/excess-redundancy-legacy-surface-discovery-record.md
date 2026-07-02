# Excess / redundancy / legacy-surface discovery record

Use this during review, refactoring, deprecation, skill/policy updates, and
cleanup work. It is the subtractive pair to Negative-Space Discovery: the goal
is to find surfaces that may be too much, stale, redundant, or legacy-bound
without turning every smell into an immediate deletion.

```text
task / artifact:
trigger:
source refs:
candidate surface:
surface type: dead-code | duplicate | deprecated | legacy-reader | stale-doc | unused-config | redundant-test | overlapping-skill | other
evidence:
  - static usage:
  - dynamic/runtime usage:
  - data usage / persisted references:
  - public API / compatibility:
  - docs / release notes / migration state:
classification: remove-now | deprecate-with-migration | consolidate-later | keep-intentionally
why this classification:
false-positive deletion risk:
required companion work:
  - migration:
  - compatibility shim / legacy reader:
  - tests:
  - docs:
  - release notes:
  - rollback:
surface form: issue | migration question | PR finding | direct edit
reviewer / owner decision:
later learning signal:
```

Tier policy:

- `remove-now`: only for private/internal surfaces with high-confidence zero
  use, no persisted data dependency, no public API contract, and a focused
  validator proving behavior is preserved. The PR must include tests or a
  narrowly equivalent validation artifact.
- `deprecate-with-migration`: for public, user-visible, cross-agent,
  persisted-data, or compatibility-sensitive surfaces. Mark the new path,
  migration plan, warning/communication surface, and removal condition before
  deleting anything.
- `consolidate-later`: for real duplication where immediate consolidation
  would broaden the current task, require unrelated churn, or need a migration
  window. Create an issue or migration question with evidence instead of
  editing opportunistically.
- `keep-intentionally`: for compatibility shims, forensic/audit traces,
  documented extension points, skill/runtime adapters, and legacy readers that
  still protect users or data. Record why it stays so future reviewers do not
  rediscover the same false positive.

False-positive guard:

- Treat mistaken removal as the worst failure mode. If usage evidence is
  partial, silence is not a valid delete signal.
- Do not remove `@deprecated` or equivalent public surfaces until migration is
  complete and the removal condition is independently checked.
- Do not remove backward-compatibility readers, legacy parsers, or data
  migration paths until data-side references are verified absent or a migration
  has run and been validated.
- Do not perform forensic-clean removal of audit, receipt, provenance, or
  migration traces unless the owner explicitly asks and retention policy allows
  it.
- If any compatibility, migration, data, or ownership fact is missing, stop at
  an issue, migration question, or review finding.

Evidence grounding:

- Local policy has priority for this repo: deprecated surfaces require a
  completed migration before deletion; legacy readers require data-side
  absence or a validated migration; audit/provenance traces are intentionally
  retained unless removal is explicitly approved.
- External sources in `references/sources.md` ground the surrounding practice:
  semantic versioning treats deprecation and incompatible removal differently;
  Java enhanced deprecation separates removal intent and migration
  communication; large-scale changes rely on tooling, migration, and
  coordination; refactoring is behavior-preserving; removing dead code is valid
  only after the code is actually dead.

Learning signals:

```text
accepted_remove_now:
accepted_deprecate:
accepted_consolidate:
accepted_keep:
converted_to_issue:
rejected_false_positive:
rejected_missing_usage_evidence:
rejected_compatibility_risk:
later_confirmed_excess_miss:
later_confirmed_bad_deletion:
```

