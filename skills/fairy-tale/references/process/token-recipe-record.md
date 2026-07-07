# Token recipe record

Use this at consolidation after a validated success that is likely to recur.
Capture the process precisely enough that the next run can replay it without
re-discovery; never include secret values (names only).

```text
recipe id / name:
goal (one line):
trigger (when to replay this):
preconditions (paths / versions / gates that must still hold):
steps (exact commands, tools, files, in order):
verification (how success is checked; run in full on every replay):
gotchas (what went wrong first time -> fix):
baseline cost (first run: tool calls / time / tokens if visible):
last replay cost:
last verified (date + what was re-checked):
supersedes / superseded by:
```
