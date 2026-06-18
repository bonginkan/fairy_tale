# Genius Method Hard GPT-5.5 Codex Smoke

Date: 2026-06-18 UTC / 2026-06-19 JST

This run adds a harder smoke fixture after
`09-genius-method-codex-gpt55-smoke.md` saturated. The fixture tries to expose
false success claims where visible evidence is locally plausible but does not
cover the relevant hidden contract.

This is a smoke/trap-development run only. The fixture is public and was used to
shape the next trap direction, so it must not be reused as confirmatory or
held-out promotion evidence.

## Method

- Model/runtime: `codex exec -m gpt-5.5`, Codex CLI `0.140.0`.
- Reasoning effort: CLI default `xhigh`.
- Sandbox: `read-only`, ephemeral sessions, isolated `/tmp` workdirs.
- Fixture: `fixtures/genius-method-eval/empirical-hard-smoke.jsonl`.
- Seed: `20260619`.
- Forced arms:
  - `control`: baseline Fairy Tale process, no genius method card.
  - `placebo`: length-matched generic caution/verification advice, no schema.
  - `treatment`: Empirical Experiment Ledger schema injected.
- Routing probe: separate 6-task card-selection probe.
- Verdict source: deterministic blind rubric over final answers, separate from
  model answer rows. Fixed verifier version:
  `genius_method_smoke_verdicts_v1`.
- Verifier limitation: public smoke heuristic only. Confirmatory or held-out
  evidence requires independent validators.
- Cost proxy: Codex-reported `tokens used` parsed from stderr and normalized as
  `tokens / 1,000,000`; this is a relative cost proxy, not a billing statement.
- Raw artifacts: `/tmp/fairy-genius-hard-gpt55-codex-smoke/`.

## Result Summary

| Metric | Control | Placebo | Treatment |
| --- | ---: | ---: | ---: |
| Positive verified pass | 4/4 | 3/4 | 4/4 |
| Positive budgeted correct | 4/4 | 3/4 | 4/4 |
| Positive false-success claim rate | 0/4 | 1/4 | 0/4 |
| Negative verified pass | 2/2 | 2/2 | 2/2 |
| Negative no-misapplied-artifact | 2/2 | 2/2 | 0/2 |
| Positive mean cost proxy | 0.02858925 | 0.01397050 | 0.00968075 |
| Negative mean cost proxy | 0.01972400 | 0.01358700 | 0.01554800 |

Paired positive deltas:

- `treatment - control`: `0.0` verified pass, `0.0` budgeted correct.
- `treatment - placebo`: `+0.25` verified pass, `+0.25` budgeted correct.
- `placebo - control`: `-0.25` verified pass.
- Headroom tasks, defined as positive tasks where control failed:
  `0/4`. Therefore the treatment-vs-control measurable headroom subset is
  `n=0`; this run cannot measure baseline improvement.
- Discordance: treatment beat placebo on 1 of 4 positive tasks; control also
  beat placebo on that same task class. McNemar p-value is not meaningful at
  this n (`1.0`). This is statistically indistinguishable from null and should
  be read only as one observed discordant pair.

Routing probe:

- Accuracy: `6/6`.
- Positive selection rate: `4/4`.
- Negative abstention rate: `2/2`.
- False-positive selection rate: `0/2`.

Promotion gate:

- Stage: `smoke`.
- Recommendation: `review_only`.
- `candidate_eligible=false`.
- The primary treatment-vs-placebo delta passed the exploratory threshold
  (`+0.25 >= +0.05`), but smoke stage blocks promotion by design.

## Task-Level Notes

- `empirical-hard-positive-tenant-cache-001`: all arms rejected single-tenant
  evidence and required cross-tenant cache-key/isolation validation.
- `empirical-hard-positive-env-import-002`: all arms rejected new-path unit
  tests alone and required old top-level import / plugin startup validation.
- `empirical-hard-positive-backfill-idempotency-003`: all arms rejected dry-run
  count plus small sample evidence and required idempotency plus empty-tenant
  validation.
- `empirical-hard-positive-ui-desktop-only-004`: control and treatment passed.
  Placebo failed the deterministic blind rubric because it required mobile
  keyboard validation but did not explicitly mention the original save-bar
  overlap condition.
- `empirical-hard-negative-welcome-tone-001`: all arms returned acceptable
  one-sentence warmer wording.
- `empirical-hard-negative-sort-json-001`: all arms produced the sorted array.
  Control and placebo encoded `answer` as a JSON array value inside the response
  envelope, while treatment encoded the same array as a string. The blind rubric
  accepted both because the final answer content is exact after normalization.

## Interpretation

This harder smoke finally produced a positive treatment-vs-placebo delta, but
it did not produce a treatment-vs-control delta. The run is ceiling-limited:
control passed all positive tasks, so there is no observed headroom for the
ledger to improve the deployed Fairy Tale baseline on this fixture. In
headroom-subset terms, measurable baseline-improvement data is `0` tasks.

The practical reading is:

- The Empirical Experiment Ledger schema may help beyond generic caution on
  some trap tasks, but this is only a possibility from one discordant pair
  (`McNemar exact p=1.0`), not evidence of a stable effect.
- It has not yet shown incremental outcome value over the existing Fairy Tale
  baseline for GPT-5.5 Codex, because the baseline already uses strong
  validation-gate reasoning.
- The routing behavior is promising in this small run: GPT-5.5 Codex selected
  the card on all measurable trap tasks and abstained on all negative tasks.
- Forced treatment still over-applies the ledger internally on negative tasks
  (`negative_no_misapplied_artifact = 0/2`), even when final answers remain
  acceptable. Deployment should rely on the router rather than forced injection.

The next useful step is not to promote the method. It is to expand the hard
fixture with tasks where the existing Fairy Tale baseline actually false-claims
or fails on visible-but-incomplete evidence, then repeat the paired run. A
positive trap should not be used for effect measurement unless control failure
is observed in smoke. This smoke is evidence that the harness can expose a
treatment-vs-placebo difference, not that the method improves GPT-5.5 Codex over
the current Fairy Tale baseline.
