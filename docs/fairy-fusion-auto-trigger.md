# Fairy Fusion automatic trigger decisions

Fairy Fusion automatic checks are bounded, deterministic decisions. They do
not launch reviewers, call a model provider, retry work, or change an artifact.
The caller remains responsible for applying its approval and provider policy
before separately invoking reviewer execution.

Create a state file that conforms to
`schemas/fairy-fusion-auto-check-input.schema.json`:

```json
{
  "schema_version": "1.0",
  "failure_signatures": [
    "validation failed at row 41",
    "validation failed at row 42",
    "validation failed at row 43"
  ],
  "validation_ledger_status": "present",
  "artifact_status": "meaningful",
  "review_conflict": false,
  "explicit_request": false,
  "reviewer_cap": 3,
  "recursion_depth": 0,
  "artifact_path": "artifacts/fairy-fusion/review.json"
}
```

Then evaluate it from a source checkout:

```bash
./fairy fusion --auto-check --state-json state.json
./fairy fusion --auto-check --state-json state.json --output decision.json
```

When `--output` is used, its portable path identity must differ from
`--state-json`; the command rejects a collision before writing either artifact.

The result conforms to
`schemas/fairy-fusion-trigger-decision.schema.json` and records the decision,
trigger reasons, reviewer cap, observed recursion depth, recursion cap, intended
review artifact path, input SHA-256, and `automatic_execution: false`.

## Trigger contract

A depth-zero check returns `trigger` when at least one of these conditions is
present:

- the same normalized failure signature appears at least three times;
- a required Validation Ledger is missing;
- an expected artifact is empty or meaningless;
- independent reviews conflict; or
- a user/operator explicitly requests Fairy Fusion.

No condition returns `skip`. A condition at recursion depth 1 or greater
returns `blocked` with `recursion_cap_reached`; automatic fusion never recurses
beyond the default one-level cap. `reviewer_cap` must be between 1 and 5 and is
recorded rather than inferred. `artifact_path` must be a non-empty,
repository-relative path without empty, dot, parent, backslash, or drive-style
segments.

Malformed JSON, unknown or missing fields, invalid enums, unsafe paths, and
out-of-range limits fail closed with exit code 2. Valid `skip`, `trigger`, and
`blocked` decisions return exit code 0 because they are decision artifacts, not
review execution results.

The direct `scripts/fairy_fusion_review.py` interface remains available for
existing integrations. `--auto-check` cannot be combined with task, role,
review execution, or dry-run arguments.

## After a trigger decision

A `trigger` decision carries its reasons, and this section applies to three of
them: `repeated_failure_signature`, `validation_ledger_missing`, and an empty
or meaningless artifact. For those, a `trigger` is a decision to review, not a
decision to stop. Under its own approval and provider policy the caller then
runs the bounded review the harness already defines — isolated reviewers, one
synthesis pass, append-only review artifacts — reads back only the compact
hint, and continues the work it was doing under its existing clear and stop
conditions.

`explicit_request` needs no redirection rule — the request is its own grounds,
and the caller invokes `scripts/fairy_fusion_review.py` directly.
`review_conflict` is the one reason this section does not carry: there is no
established handling for it to point at, so it stays with the caller's own
policy rather than being routed by default.

Nothing in the sequence is new. `scripts/swebench_pro_run.py` implements this
control flow for the benchmark path **when its existing flags enable it**: the
retry loop is entered only under `--fusion-auto` with `--fusion-retry-on-stuck`,
and the review it runs executes reviewers only under `--fusion-execute` —
without it the review runs `--dry-run`. Read it as an existing integration
applying its own retry and execution policy, not as an unconditional
precedent. A caller outside that path follows the same sequence under its own
policy. The automatic check is unchanged and still only decides —
`automatic_execution` stays `false` and the recursion cap stays 1 — so
reaching the review is always the caller's step, never the check's.
