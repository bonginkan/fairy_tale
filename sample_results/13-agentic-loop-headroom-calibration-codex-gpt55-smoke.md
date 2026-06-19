# Agentic Loop Headroom Calibration GPT-5.5 Codex Smoke

Date: 2026-06-19 UTC

This is a smoke / fixture-calibration run only. It is not promotion evidence and
does not show deployment-baseline improvement.

## Setup

- Model/runtime: `codex exec -m gpt-5.5 -c model_reasoning_effort="xhigh"`
- Codex CLI: `codex-cli 0.140.0`
- Fixture: `fixtures/agentic-loop/headroom-calibration.jsonl`
- Runner: `scripts/agentic_loop_runner.py`
- Connector: `scripts/agentic_loop_codex_solver.py`
- Raw local artifacts:
  `tmp/agentic-loop-headroom-calibration-gpt55-codex-20260619T015011Z/run`

The positive task was designed as a two-stage public-probe fixture: the first
probe exposes `status=fixed`, the second exposes `seal=probe-confirmed`. The
goal was to test whether structured observe-act-validate guidance recovers a
task that generic retry does not.

## Validation

- Runner completed: 8 trace rows, 8 hidden verdict rows.
- Hidden-specific scan: no hits for hidden validator ids or `hidden_validators`
  in solver-visible workspaces, requests, traces, `blind_key.json`, or
  `run_manifest.json`.
- `budget_fields_complete=true`
- `usage_fields_complete=true`
- `token_usage_source_complete=true`
- `token_usage_split_measured_complete=false`
- `cost_estimates_complete=true`
- `budget_parity.passed=true`
- Promotion gate: `candidate_eligible=false`, `recommendation=review_only`

The token split gate fails because Codex CLI exposes total token usage only in
this connector path. The trace marks that as
`codex_cli_total_tokens_as_prompt_proxy`; this is correct fail-closed behavior
for promotion and budgeted-pass claims.

## Results

### Positive Calibration Task

Task: `agentic-loop-headroom-two-stage-probe-001`

| Arm | Verified pass | Budgeted pass | Iterations | Total tokens | Cost proxy | Stop reason |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `control` | true | false | 5 | 66106 | 0.066106 | `budget_exhausted` |
| `static_ledger` | false | false | 5 | 66146 | 0.066146 | `budget_exhausted` |
| `placebo_loop` | false | false | 5 | 50891 | 0.050891 | `budget_exhausted` |
| `agentic_loop` | true | false | 5 | 51153 | 0.051153 | `budget_exhausted` |

Observed deltas:

- `agentic_loop` beat `placebo_loop` on this positive task.
- `agentic_loop` beat `static_ledger` on this positive task.
- `control` also passed, so `n_headroom_tasks=0`.
- Therefore this task is not evidence of improvement over the runner's
  `control` arm.

Interpretation: the fixture can separate structured agentic guidance from the
placebo retry prompt in this single run, but it does not create headroom against
the current runner control. The current `control` arm is still
controller-mediated and can use repeated observations, so it is stronger than a
raw one-shot baseline.

### Negative Task

Task: `agentic-loop-headroom-negative-no-edit-001`

| Arm | Verified pass | False success | Iterations | Total tokens | Cost proxy | Stop reason |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `control` | true | false | 2 | 27932 | 0.027932 | `budget_exhausted` |
| `static_ledger` | true | false | 2 | 13325 | 0.013325 | `abstained` |
| `placebo_loop` | true | false | 2 | 28085 | 0.028085 | `abstained` |
| `agentic_loop` | true | false | 2 | 13358 | 0.013358 | `abstained` |

No negative regression or false-success increase was observed in this one
negative smoke task.

## Promotion Gate

The promotion gate correctly rejected the run:

- `stage_allows_promotion=false` because `stage=smoke`
- `headroom_nonzero=false`, observed `0`
- `headroom_minimum_n=false`, observed `0`, threshold `>=8`
- `token_usage_split_measured_complete=false`, observed `8` proxy rows
- `candidate_eligible=false`

This must stay `review_only`.

## Read

This smoke is useful, but not in the way originally hoped:

- It shows one positive task where `agentic_loop` passed and `placebo_loop`
  failed.
- It also shows that the current `control` arm passed the same task, so the
  primary headroom subset is empty.
- The current controlled runner gives all arms the same request/action/
  observation channel; this makes `control` a controller-exposed baseline, not
  a raw deployment baseline.

Next fixture work should either:

1. create tasks where even the controller-exposed `control` arm fails while
   `agentic_loop` passes; or
2. add a separate non-loop baseline path and pre-register that comparison
   separately from the equal-controller comparison.
