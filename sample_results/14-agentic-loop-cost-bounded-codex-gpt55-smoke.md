# Agentic Loop Cost-Bounded GPT-5.5 Codex Smoke

Date: 2026-06-19 UTC

This is a smoke / connector-calibration run only. It is not promotion evidence,
not confirmatory evidence, and not evidence that the agentic loop improves the
deployment baseline.

## Setup

- Model/runtime: `codex exec -m gpt-5.5 -c model_reasoning_effort="xhigh"`
- Codex CLI: `codex-cli 0.140.0`
- Fixture: `fixtures/agentic-loop/smoke.jsonl`
- Runner commit: `8dd78e8 Add agentic loop arm subset smoke control`
- Runner command used an explicit arm subset:
  `non_loop_control,control,placebo_loop,agentic_loop`
- Omitted arm: `static_ledger`, to cap paid calls for smoke only.
- Local run directory: `tmp/agentic-loop-smoke-8dd78e8-gpt55`
- Committed replay artifacts:
  `sample_results/artifacts/14-agentic-loop-cost-bounded-codex-gpt55-smoke/`

Committed artifacts include `blind-key.json`, `traces.jsonl`, `verdicts.jsonl`,
`summary.json`, `promotion.json`, and `run-manifest.json`. Solver prompt/log
files are not committed.

## Validation

- Runner completed: 8 trace rows, 8 hidden verdict rows.
- Solver calls: 17 Codex CLI calls.
- Hidden-specific scan: no hits for hidden validator ids or `hidden_validators`
  in solver-visible workspaces, requests, traces, `blind_key.json`,
  `run_manifest.json`, `summary.json`, or `promotion.json`.
- `budget_fields_complete=true`
- `usage_fields_complete=true`
- `token_usage_source_complete=true`
- `token_usage_split_measured_complete=false`
- `cost_estimates_complete=true`
- Promotion gate: `candidate_eligible=false`, `recommendation=review_only`

The token split gate fails because this Codex CLI connector path exposes total
token usage only. The trace records
`codex_cli_total_tokens_as_prompt_proxy`, so budgeted-pass and promotion claims
remain fail-closed.

## Results

### Positive Smoke Task

Task: `agentic-loop-smoke-public-probe-001`

| Arm | Verified pass | Budgeted pass | Iterations | Total tokens | Cost proxy | Stop reason |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `non_loop_control` | true | false | 1 | 21322 | 0.021322 | `non_loop_action_limit` |
| `control` | false | false | 3 | 20410 | 0.020410 | `budget_exhausted` |
| `placebo_loop` | false | false | 3 | 50196 | 0.050196 | `budget_exhausted` |
| `agentic_loop` | false | false | 3 | 35032 | 0.035032 | `budget_exhausted` |

Observed behavior:

- `non_loop_control` edited `app.txt` to `status=fixed` and passed the hidden
  validator.
- `control`, `placebo_loop`, and `agentic_loop` all ran the public probe first,
  then eventually edited `app.txt` to `status: fixed` and failed the hidden
  validator.
- The public probe failed silently in this fixture, so the controller-exposed
  arms overfit the phrase "fixed status line" into the wrong punctuation.

Interpretation:

- This is not evidence for the agentic loop.
- `agentic_loop` did not recover the positive task.
- The raw/non-loop baseline passed while the controller-exposed loop arms
  failed, so this run mainly exposes a controller-mediated regression mode.
- The existing promotion headroom subset is not usable here because the run
  intentionally omitted `static_ledger`; `n_complete_paired_headroom_tasks=0`.

### Negative Smoke Task

Task: `agentic-loop-smoke-negative-format-001`

| Arm | Verified pass | False success | Iterations | Total tokens | Cost proxy | Stop reason |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `non_loop_control` | true | false | 1 | 20264 | 0.020264 | `verified` |
| `control` | true | false | 2 | 13127 | 0.013127 | `abstained` |
| `placebo_loop` | true | false | 2 | 42786 | 0.042786 | `verified` |
| `agentic_loop` | true | false | 2 | 13353 | 0.013353 | `verified` |

No hidden-validator regression was observed on the negative smoke task.

## Promotion Gate

The promotion gate correctly rejected the run:

- `stage_allows_promotion=false` because `stage=smoke`
- `headroom_nonzero=false` because `n_complete_paired_headroom_tasks=0`
- `headroom_minimum_n=false`
- `token_usage_split_measured_complete=false`
- `candidate_eligible=false`
- `recommendation=review_only`

This must stay `review_only`.

## Read

This run is useful as a connector smoke, but it is a negative result for the
current agentic-loop hypothesis:

- It confirms that the cost-bounded `--arms` path can run and preserve hidden
  isolation.
- It does not show `agentic_loop > placebo_loop`.
- It does not show `agentic_loop > control`.
- It does not show deployment-baseline improvement.
- It shows a case where one-shot visible-context editing beat the
  controller-mediated loop arms.

The next useful work is not promotion. It is harness diagnosis:

1. decide whether silent public-probe failures should be improved as a fixture
   signal or kept as a trap;
2. test whether the controller prompt should preserve literal candidate strings
   more carefully after failed probes;
3. keep raw/non-loop baseline and equal-controller loop contrasts separate.
