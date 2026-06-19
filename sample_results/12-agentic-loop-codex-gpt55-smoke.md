# Agentic Loop GPT-5.5 Codex Smoke

Date: 2026-06-19 UTC

This is a smoke / connector run only. It is not promotion evidence, not a
confirmatory result, and not evidence that the agentic loop improves over the
current Fairy Tale baseline.

## Setup

- Model/runtime: `codex exec -m gpt-5.5 -c model_reasoning_effort="xhigh"`
- Codex CLI: `codex-cli 0.140.0`
- Connector: `scripts/agentic_loop_codex_solver.py`
- Runner: `scripts/agentic_loop_runner.py`
- Fixture: `fixtures/agentic-loop/smoke.jsonl`
- Arms: `control`, `static_ledger`, `placebo_loop`, `agentic_loop`
- Raw local artifacts:
  `tmp/agentic-loop-gpt55-codex-smoke-20260619T011404Z/run`

The connector uses controller-mediated actions. The Codex-facing prompt does not
receive `workspace_path`, hidden validators, ground truth, verdicts, or
scorer-only fields. Solver telemetry is a proxy parsed from Codex CLI stderr:
`tokens used / 1,000,000`, not an actual billing charge.

## Validation

- Runner completed: 8 trace rows, 8 hidden verdict rows.
- Hidden validator scan: no hits in solver-visible workspaces, requests,
  `traces.jsonl`, `blind_key.json`, or `run_manifest.json`.
- Hidden validator specs remain in `judge_manifest.jsonl` only.
- `budget_fields_complete=true`
- `usage_fields_complete=true`
- `cost_estimates_complete=true`
- `budget_parity.passed=true`
- Promotion gate: `candidate_eligible=false`, `recommendation=review_only`

## Results

### Positive Headroom Task

Task: `agentic-loop-smoke-public-probe-001`

| Arm | Verified pass | Budgeted pass | Iterations | Total tokens | Cost proxy | Stop reason |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `control` | false | false | 3 | 35172 | 0.035172 | `budget_exhausted` |
| `static_ledger` | false | false | 3 | 34910 | 0.034910 | `budget_exhausted` |
| `placebo_loop` | true | false | 3 | 35231 | 0.035231 | `budget_exhausted` |
| `agentic_loop` | false | false | 3 | 20190 | 0.020190 | `budget_exhausted` |

Headroom subset:

- `n_headroom_tasks=1`
- `placebo_loop_vs_control`: `+1.0` on the single headroom task
- `agentic_loop_vs_control`: `0.0`
- `agentic_loop_vs_placebo_loop`: `-1.0`
- `agentic_loop` decisive external recovery count: `0`

Interpretation: this smoke created one measurable control-failure surface, but
the agentic loop did not recover it. The only recovery came from `placebo_loop`.
With `n=1`, the result is anecdotal planning data, not stable evidence.

### Negative Task

Task: `agentic-loop-smoke-negative-format-001`

| Arm | Verified pass | False success | Iterations | Total tokens | Cost proxy | Stop reason |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `control` | true | false | 2 | 13327 | 0.013327 | `verified` |
| `static_ledger` | true | false | 2 | 28136 | 0.028136 | `verified` |
| `placebo_loop` | true | false | 2 | 28176 | 0.028176 | `verified` |
| `agentic_loop` | true | false | 2 | 27904 | 0.027904 | `abstained` |

No negative regression was observed in this one smoke task.

## Promotion Gate

The promotion gate correctly rejected the run:

- `stage_allows_promotion=false` because `stage=smoke`
- `headroom_minimum_n=false` because observed headroom is `1`, threshold is `>=8`
- `agentic_beats_placebo_loop=false`, observed `-1.0`, threshold `>=0.05`
- `agentic_beats_control=false`, observed `0.0`, threshold `>=0.05`
- `external_observation_recovery_present=false`, observed `0`

This should stay `review_only`.

## Read

This run validates that the controlled runner and Codex connector can execute a
real GPT-5.5 Codex smoke while preserving hidden-validator isolation and
fail-closed promotion gates.

It does not show an agentic-loop improvement. The useful signal is narrower:
the fixture can produce at least one headroom task, but the current agentic loop
did not recover that task and did not beat the placebo retry loop. The next
fixture should target cases where generic retry is insufficient and the
structured observe-act-validate policy has a plausible unique advantage.
