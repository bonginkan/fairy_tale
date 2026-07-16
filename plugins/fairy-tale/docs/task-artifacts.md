# Task Cards and Validation Ledgers

Use a Task Card before long or tightly scoped work, then record validation in
the linked ledger. JSON is canonical. Markdown is a rendered view for reviews,
handoffs, and completion reports.

`scripts/task_artifacts.py` owns the artifact contract. A unified `fairy` CLI
may delegate to it later; wrappers must not reimplement the schemas or closure
rules.

## Create a Task Card

The generator supports `coding`, `research`, `security`, and `benchmark` modes.
Budgets are explicit inputs rather than universal defaults.

```powershell
python3 scripts/task_artifacts.py task-card `
  --task-id demo-coding `
  --mode coding `
  --objective "Add a bounded behavior without unrelated changes." `
  --success "Focused behavior passes." `
  --success "Adjacent behavior remains compatible." `
  --target "src/" `
  --target "tests/" `
  --constraint "Preserve public contracts." `
  --max-elapsed-minutes 60 `
  --max-tool-calls 40 `
  --max-subagents 1 `
  --max-searches 8 `
  --token-or-cost-limit "one bounded agent run" `
  --stop "Stop on an authority or safety boundary." `
  --validation "focused test" `
  --validation "adjacent compatibility test" `
  --ledger-path validation-ledger.json `
  --output task-card.json `
  --markdown-output task-card.md;
```

The canonical output includes the required frame and the ledger link:

```json
{
  "artifact_type": "task_card",
  "budget": {
    "max_elapsed_minutes": 60,
    "max_searches": 8,
    "max_subagents": 1,
    "max_tool_calls": 40,
    "token_or_cost_limit": "one bounded agent run"
  },
  "ledger_path": "validation-ledger.json",
  "mode": "coding",
  "objective": "Add a bounded behavior without unrelated changes.",
  "schema_version": "1.0",
  "task_id": "demo-coding"
}
```

The excerpt omits the required list fields for brevity. Validate the complete
file against `schemas/task-card.schema.json` or the built-in validator.

## Record Validation

Initialize the ledger from the card. The command derives `task_id` and creates
a two-way path link; an explicit `--output` must match the card's `ledger_path`.
Stored links are portable filenames and reject absolute, nested, or parent
(`..`) traversal references. Keep the canonical pair in one artifact directory;
that directory itself may be anywhere the surrounding workflow allows.
The stored filenames must exactly match regular directory entries; case aliases
and file-level symlinks cannot stand in for either canonical artifact.
Canonical JSON, its derived Markdown view, and the linked counterpart must use
distinct paths; commands reject collisions before writing either artifact.

```powershell
python3 scripts/task_artifacts.py ledger-init --task-card task-card.json;
python3 scripts/task_artifacts.py ledger-add --ledger validation-ledger.json --check-id focused-test --plan-item "focused test" --command "python3 -m pytest tests/test-focus.py" --result pass --artifact artifacts/focused.txt;
python3 scripts/task_artifacts.py ledger-add --ledger validation-ledger.json --check-id adjacent-test --plan-item "adjacent compatibility test" --command "python3 -m pytest tests/test-adjacent.py" --result pass --artifact artifacts/adjacent.txt;
python3 scripts/task_artifacts.py ledger-finalize --ledger validation-ledger.json --status complete --summary "Focused and adjacent checks passed." --remaining-risk "No visual surface changed.";
python3 scripts/task_artifacts.py render --artifact validation-ledger.json --verify-link --output validation-ledger.md;
```

Each check records a plan item, command or manual check, result, artifact paths,
and notes. Results are exactly `pass`, `fail`, `blocked`, or `not_run`.
Every `pass` must carry evidence: a non-empty command, at least one artifact
path, or a concrete manual observation in notes. An all-empty pass is invalid.
`ledger-add --replace` updates an existing check explicitly.

A ledger cannot finalize as `complete` while any check is not `pass`, a blocker
is open, a planned validation item is unrecorded, or the Task Card link is
invalid. Finalizing as `blocked` requires a concrete blocker and summary.
Remaining non-blocking risk stays explicit in either final state.

## Validate and Exercise

```powershell
python3 scripts/task_artifacts.py validate --artifact task-card.json;
python3 scripts/task_artifacts.py validate --artifact validation-ledger.json;
python3 scripts/task_artifacts.py selftest;
python3 scripts/task_artifacts.py cases --cases fixtures/task-artifacts/cases.jsonl;
```

The JSON schemas are `schemas/task-card.schema.json` and
`schemas/validation-ledger.schema.json`. Keep canonical JSON and rendered
Markdown together only when the surrounding repository wants durable task
artifacts; otherwise place them in an ignored or external run directory.
Schemas enforce each document's closed shape and final-state floor. Use the
built-in validator for cross-file task-ID, back-reference, exact-name, and
validation-plan coverage checks that JSON Schema cannot resolve by itself.
Ledger validation performs those link checks by default; `--verify-link` remains
accepted for explicit invocations and scripts.
