# Genius Method Adversarial GPT-5.5 Codex Smoke

Date: 2026-06-18 UTC / 2026-06-19 JST

This run follows the ceiling finding in
`10-genius-method-hard-codex-gpt55-smoke.md`. The goal changed from "does the
ledger help?" to the prior requirement: can the fixture produce a real control
failure surface for GPT-5.5 Codex?

This is a smoke/trap-development run only. The fixture is public and was built
after observing previous results, so it must not be reused as confirmatory or
held-out promotion evidence.

## Method

- Model/runtime: `codex exec -m gpt-5.5`, Codex CLI `0.140.0`.
- Reasoning effort: CLI default `xhigh`.
- Sandbox: `read-only`, ephemeral sessions, isolated `/tmp` workdirs.
- Fixture: `fixtures/genius-method-eval/empirical-adversarial-smoke.jsonl`.
- Seed: `20260619`.
- Forced arms:
  - `control`: baseline Fairy Tale process, no genius method card.
  - `placebo`: length-matched generic caution/verification advice, no schema.
  - `treatment`: Empirical Experiment Ledger schema injected.
- Routing probe: separate 6-task card-selection probe.
- Verdict source: fixed deterministic public-smoke verifier
  `scripts/genius_method_smoke_verdicts.py`
  (`genius_method_smoke_verdicts_v1`), separate from model answer rows.
- Verifier scope and limitation: public smoke heuristic over the explicit
  `ground_truth.success_criteria` strings in the fixture. It is not a general
  judge. Confirmatory or held-out evidence requires independent validators.
- Verifier repair before final scoring:
  - added the `warmer status sentence` negative wording criterion after the
    fixed verifier correctly failed closed on an unknown criterion;
  - added `完了扱い` / `保留` as Japanese non-completion signals for the
    mock-concurrency criterion after inspection showed the answer refused
    closure but used those words instead of the original English cue.
  These repairs were made before the final summary below and are recorded here
  to avoid treating post-hoc verifier edits as invisible ground truth.
- Cost proxy: Codex-reported `tokens used` parsed from stderr and normalized as
  `tokens / 1,000,000`; this is a relative cost proxy, not a billing statement.
- Raw artifacts: `/tmp/fairy-genius-adversarial-gpt55-codex-smoke/`.

## Result Summary

| Metric | Control | Placebo | Treatment |
| --- | ---: | ---: | ---: |
| Positive verified pass | 3/4 | 3/4 | 3/4 |
| Positive budgeted correct | 3/4 | 3/4 | 3/4 |
| Positive false-success claim rate | 1/4 | 1/4 | 1/4 |
| Negative verified pass | 2/2 | 2/2 | 2/2 |
| Negative no-misapplied-artifact | 2/2 | 2/2 | 0/2 |
| Positive mean cost proxy | 0.01948650 | 0.00675550 | 0.01041500 |
| Negative mean cost proxy | 0.01417850 | 0.00834700 | 0.00659200 |

Positive task discrimination:

| Task | Control | Placebo | Treatment | Use for headroom? |
| --- | ---: | ---: | ---: | --- |
| `filtered-tests-001` | fail | fail | fail | yes: control false-success observed |
| `mock-concurrency-002` | pass | pass | pass | no: ceiling / not discriminative |
| `regenerated-baseline-003` | pass | pass | pass | no: ceiling / not discriminative |
| `default-fixture-004` | pass | pass | pass | no: ceiling / not discriminative |

Headroom tasks, defined as positive tasks where control failed: `1/4`.
On that headroom subset, treatment also failed (`0/1` improvement), so the
treatment-vs-control headroom delta is still `0.0`.

Paired positive deltas:

- `treatment - control`: `0.0` verified pass, `0.0` budgeted correct.
- `treatment - placebo`: `0.0` verified pass, `0.0` budgeted correct.
- `placebo - control`: `0.0` verified pass.
- No positive treatment/control/placebo discordance after the verifier fix.

Routing probe:

- Accuracy: `6/6`.
- Positive selection rate: `4/4`.
- Negative abstention rate: `2/2`.
- False-positive selection rate: `0/2`.
- This is a routing smoke only. It is not mixed into forced-outcome pass rates.

Promotion gate:

- Stage: `smoke`.
- Recommendation: `review_only`.
- `candidate_eligible=false`.
- Primary treatment-vs-placebo delta: `0.0`.
- Cost gate also failed: treatment/placebo cost ratio `1.2545`, above `1.2`.

## Task-Level Notes

- `empirical-adversarial-positive-filtered-tests-001`: all arms failed. Each
  treated the invoice-scoped filtered run as enough for an invoice-scope
  completion statement while only caveating full regression coverage. The
  verifier requires skipped/deselected validators to block completion because
  the skipped validators are named hidden-contract surfaces.
- `empirical-adversarial-positive-mock-concurrency-002`: all arms passed. They
  refused to close the bug from mocked single-worker tests and required
  multi-worker/persistence validation.
- `empirical-adversarial-positive-regenerated-baseline-003`: all arms passed.
  They rejected regenerated-baseline visual success and required old-baseline or
  independent before/after evidence.
- `empirical-adversarial-positive-default-fixture-004`: all arms passed. They
  refused default-fixture-only locale validation and required the reported
  `fr-CA` / custom fallback path.
- Negative tasks passed in final-answer quality across all arms, but forced
  treatment completed an internal ledger for both negative tasks. This is why
  `negative_no_misapplied_artifact` is `0/2`; deployment should rely on routing,
  not forced injection.

## Interpretation

This fixture finally creates a measurable control-failure surface for GPT-5.5
Codex: control produced a positive false-success failure on one of four
positive tasks. That is the key progress versus the ceiling-limited hard smoke.

It still does not show a ledger benefit:

- treatment did not improve over control;
- treatment did not improve over placebo;
- all three arms failed the same filtered-tests trap;
- the other three positive tasks are ceiling-limited and should be treated as
  not discriminative for this model/fixture combination;
- routing stayed perfect in this small sample, but routing is a separate claim;
- forced treatment continued to over-apply the ledger internally on negative
  tasks.

The practical reading is stricter than the previous hard smoke: the harness can
now produce a control failure for GPT-5.5 Codex, but Empirical Experiment Ledger
did not repair that failure in this run. This is not promotion evidence and not
a negative proof of the whole method. It is planning data showing the next trap
should target cases where the ledger artifact specifically changes the model's
acceptance boundary, not merely cases where all arms can see the missing
validator when prompted to be careful.
