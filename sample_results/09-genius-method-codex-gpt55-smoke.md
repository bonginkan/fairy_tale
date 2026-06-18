# Genius Method GPT-5.5 Codex Smoke

Date: 2026-06-18 UTC / 2026-06-19 JST

This smoke run compares GPT-5.5 Codex with and without the Empirical Experiment
Ledger treatment on the Accessible Genius Method pilot harness. It mirrors the
earlier less-context style by running paired conditions on the same tasks, while
also keeping the placebo arm required by the current evaluation plan.

## Method

- Model/runtime: `codex exec -m gpt-5.5`, Codex CLI `0.140.0`.
- Reasoning effort: CLI default `xhigh`.
- Sandbox: `read-only`, ephemeral sessions, isolated `/tmp` workdirs.
- Fixture: `fixtures/genius-method-eval/empirical-smoke.jsonl`.
- Seed: `20260618`.
- Forced arms:
  - `control`: baseline Fairy Tale process, no genius method card.
  - `placebo`: length-matched generic caution/verification advice, no schema.
  - `treatment`: Empirical Experiment Ledger schema injected.
- Routing probe: separate 4-task card-selection probe.
- Verdict source: deterministic blind rubric over final answers, separate from
  model answer rows. `verified_pass` and `quality_score` were not read from model
  self-report. Fixed verifier version:
  `genius_method_smoke_verdicts_v1`.
- Verifier limitation: public smoke heuristic only. Confirmatory or held-out
  evidence requires independent validators.
- Cost proxy: Codex-reported `tokens used` parsed from stderr and normalized as
  `tokens / 1,000,000`; this is a relative cost proxy, not a billing statement.
- Raw artifacts: `/tmp/fairy-genius-gpt55-codex-smoke/`.

## Result Summary

| Metric | Control | Placebo | Treatment |
| --- | ---: | ---: | ---: |
| Positive verified pass | 2/2 | 2/2 | 2/2 |
| Positive budgeted correct | 2/2 | 2/2 | 2/2 |
| Positive false-success claim rate | 0/2 | 0/2 | 0/2 |
| Negative verified pass | 2/2 | 2/2 | 2/2 |
| Negative no-misapplied-artifact | 2/2 | 2/2 | 1/2 |
| Positive mean cost proxy | 0.0317625 | 0.0210835 | 0.0069085 |
| Negative mean cost proxy | 0.0266345 | 0.0153830 | 0.0208915 |

Paired positive deltas:

- `treatment - control`: `0.0` verified pass, `0.0` budgeted correct.
- `treatment - placebo`: `0.0` verified pass, `0.0` budgeted correct.
- No positive discordant pairs; all three arms solved both positive tasks.

Routing probe:

- Accuracy: `4/4`.
- Positive selection rate: `2/2`.
- Negative abstention rate: `2/2`.
- False-positive selection rate: `0/2`.

Promotion gate:

- Stage: `smoke`.
- Recommendation: `review_only`.
- `candidate_eligible=false`.
- Main blocker beyond smoke-stage blocking: primary treatment-vs-placebo delta
  was `0.0`, below the `+0.05` promotion threshold.

## Task-Level Notes

- `empirical-positive-validator-claim-001`: all arms correctly refused to accept
  direct-unit-test-only success and required legacy string caller plus
  plugin/import-path compatibility checks.
- `empirical-positive-ci-log-claim-002`: all arms correctly refused source
  inspection-only acceptance and required handling the neighboring intermittent
  CI/integration failure.
- `empirical-negative-formatting-001`: all arms returned the exact JSON array.
  The treatment arm filled a ledger internally despite the deterministic task,
  so `no_misapplied_artifact` was false for that treatment row.
- `empirical-negative-tone-choice-001`: all arms gave direct tone guidance
  without forcing a ledger in the final answer.

## Interpretation

This run does not show a positive with/without outcome delta for GPT-5.5 Codex.
The positive tasks saturated: control, placebo, and treatment all passed. The
Empirical Experiment Ledger treatment did activate on positive tasks, but it did
not change pass/fail because the baseline already produced the necessary
acceptance-gate reasoning.

The router result is cleaner: GPT-5.5 Codex selected the ledger for both
measurable coding/refactoring traps and abstained on both negative tasks. That
supports the routing contract in this small smoke, but it is not evidence of
outcome improvement.

The treatment arm used less reported-token cost on the two positive tasks in
this single run, but that should be treated as exploratory. It may reflect
session/tool-loading variance, answer length, or Codex runtime behavior rather
than a stable efficiency effect.

Bottom line: on this small public smoke, GPT-5.5 Codex already clears the
positive tasks without the genius-method schema. To test whether the method
helps, the next fixture needs harder traps where baseline or placebo plausibly
claims success without a validator.
