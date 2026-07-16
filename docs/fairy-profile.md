# Repository Fairy Profiles

A repository may declare local workflow rules in `.fairy/profile.json`. The
profile is optional: repositories without one keep the generic Fairy Tale
behavior. A present profile is fail-closed and must satisfy
`schemas/fairy-profile.schema.json` plus the runtime checks in
`scripts/task_artifacts.py`.

## Discovery And Scope

The first supported location is fixed at `.fairy/profile.json`. Discovery
starts from the Task Card output directory or the directory passed to
`profile-check`, then uses the nearest Git root. It does not read `AGENTS.md`,
`CLAUDE.md`, or arbitrary executable configuration. The file must be regular
UTF-8 JSON; symlinks, malformed JSON, unknown keys, duplicate rule IDs, and
unsafe artifact paths block validation.

`fairy doctor` checks the caller repository profile before residency and
adapter health. No profile is a successful compatibility fallback. A malformed
profile is a reasoned failure.

## Closed Shape

```json
{
  "schema_version": "1.0",
  "profile_id": "example-repository",
  "required_validations": [
    {
      "id": "focused-tests",
      "description": "Run the repository focused test suite.",
      "command": "python3 -m pytest tests/focused"
    }
  ],
  "prohibited_actions": [
    {
      "id": "no-force-push",
      "description": "Do not force-push repository branches."
    }
  ],
  "recommended_steps": [],
  "artifact_paths": [
    {
      "id": "release-notes",
      "description": "Record user-visible changes.",
      "path": "RELEASE_NOTES.md"
    }
  ]
}
```

All four rule lists are required and may be empty, but the profile as a whole
must declare at least one rule. IDs are unique across all lists. Artifact paths
are repository-relative and reject absolute paths, parent traversal, Windows
drive syntax, and backslashes.

Commands in `required_validations` are declarations, not executable hooks.
Fairy Tale records them in the Task Card validation plan but never executes
repository-provided command text automatically.

## Artifact Binding

Task Card creation captures the parsed profile, its fixed source path, and a
SHA-256 digest of canonical JSON. Prohibited actions are projected into
`constraints`; required validations are projected into `validation_plan`.
The full snapshot also keeps recommended steps and artifact paths visible in
JSON and rendered Markdown.

Ledger initialization copies the exact snapshot from the Task Card. Link
validation rejects a Ledger whose snapshot differs from its Task Card, and the
snapshot validator recomputes the digest from the embedded profile. This keeps
the local rules used for a task stable even if the repository profile changes
later.

The schemas are:

- `schemas/fairy-profile.schema.json`
- `schemas/repo-profile-snapshot.schema.json`
- `schemas/task-card.schema.json`
- `schemas/validation-ledger.schema.json`

The Fairy Tale repository includes `.fairy/profile.json` as a working sample.
