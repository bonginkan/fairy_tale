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
