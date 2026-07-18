# E3 Minimum-Sufficient Execution Harness

Use E3 for a tool-using execution task when all of these are true:

- success has at least one explicit, executable acceptance check;
- the task has two or more plausible scope levels, such as a named local site,
  direct callers, and dependency or integration surfaces;
- a verified narrow result could complete the task without inspecting the
  broader levels.

Do not route plain Q&A, divergent generation, brainstorming, or an independent
review/sign-off through E3. Those tasks either have no execution trajectory or
require an intentionally broad frame. E3 controls execution scope; it does not
reduce the user's requested deliverable or review frame.

## 1. Estimate

Record the initial operating point
`x0 = (difficulty, scope, risk, confidence)` before broad inspection.

- `difficulty` is the starting level: `1` local site, `2` direct related
  sites, or `3` dependency/integration surface.
- `scope` names the minimum files, symbols, resources, or operations needed at
  that level.
- `risk` is `low`, `medium`, or `high` and determines the verification floor.
- `confidence` is a finite value in `[0, 1]`.
- Use no more than one cheap search or metadata probe. Reuse its hits later.
- If wording, metadata, or the probe conflicts with the initial estimate,
  lower confidence and set the expansion-candidate flag. Do not expand before
  executing and verifying the estimated scope.

The estimate is deliberately cheap and may be optimistic. Expand is the safety
net; the estimator is not an oracle.

## 2. Execute

Execute exactly the estimated scope first.

- Level 1: locate, change or act at the named site, then run a local check.
- Level 2: reuse cached search hits and cover direct related sites.
- Level 3: trace dependencies, imports, integration boundaries, or downstream
  consumers and run full verification.
- Verification must cover every acceptance check and every required safety
  gate exactly once, and bind each non-`not_run` result to a concrete
  namespaced, URL, or digest evidence ref.
- Aggregate `fail` requires at least one actual failed check. `not_run` records
  missing work and cannot by itself unlock expansion.
- Record raw latency, token, tool-call, and inspected-item observations for
  every attempt.
- Verification strength scales with risk: low permits local, medium requires
  focused, and high requires full verification. Level 3 always requires full
  verification.

Verified success is a hard stop. Do not inspect more files, invoke more tools,
or add another attempt after a passing verification.

## 3. Expand

Expand only after failed verification.

- Increase exactly one level, never jump directly to an unbounded full read.
- Keep the prior scope and add a strict superset.
- Reuse the complete ordered evidence cache; do not restart from zero.
- Respect the recorded expansion cap and the absolute level-3 ceiling.
- Verify again at the new level. Stop on pass, block on a blocked check, and
  report exhausted when the bounded levels are consumed.

## Non-Suppressible Safety Floor

E3 optimizes redundant execution effort, not safety or completeness.

- Preserve the planned validation gate.
- Preserve Closure Check and recall-protected Tier A companions.
- Preserve authority, credential, privacy, security, and production gates.
- Preserve repository profile constraints, user scope, and required handoff
  evidence.
- Treat a safety-floor failure as a blocker, never as a reason to claim the
  narrower path succeeded.
- The canonical ledger must retain all four default safety gates; callers may
  add gates but cannot replace or suppress the defaults.
- A terminal pass requires evidence-backed `pass` outcomes for every required
  safety gate, not only the presence of gate names in ledger metadata.

## Machine Contract

Use `fairy e3` to create and advance the canonical JSON ledger:

```bash
./fairy e3 init --help
./fairy e3 record --help
./fairy e3 validate --ledger e3-execution.json
./fairy e3 render --ledger e3-execution.json --output e3-execution.md
```

The JSON ledger is canonical. Markdown is a derived review view. When a command
writes both, failure to stage or replace either output leaves the prior bundle
unchanged. The strict schema is
`schemas/e3-execution-ledger.schema.json`, and the process template is
`../process/e3-execution-record.md`.
The schema enforces the expressible evidence, aggregate-result, and default
safety-gate floor. Exact coverage of task-specific acceptance checks and
custom safety gates depends on values in other arrays, so `fairy e3 validate`
is the authoritative semantic validator for those dynamic constraints and
state transitions. A schema-only pass is not terminal E3 verification.

## ACRR Boundary

Only compute the Agent Cost Reduction Ratio when the run succeeded and an exact
positive minimum-sufficient oracle cost exists:

`ACRR = (actual_cost - minimum_sufficient_cost) / minimum_sufficient_cost`.

Normal tasks do not provide that oracle. `fairy e3` does not emit ACRR. It
records raw latency, token, tool-call, and inspected-item counts instead of
inventing a ratio. Compute ACRR only in a separate controlled evaluation where
successful runs and the exact oracle minimum are independently established.

Source checked 2026-07-18: arXiv:2607.13034, especially Algorithm 1 and
Sections 3.3 and 4.2-4.5. This card is an independent workflow implementation;
no companion repository source code is copied.
