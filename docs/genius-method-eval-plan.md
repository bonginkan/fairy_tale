# Genius Method Evaluation Plan

This plan pre-registers the first evaluation route for Accessible Genius Method
cards. The goal is not to prove that "genius methods" are generally effective.
The first measurable claim is narrower:

> For agentic-coding and refactoring trap tasks where a plausible fix can look
> successful without measurement, the Empirical Experiment Ledger schema
> reduces false success claims and improves verified pass rate beyond
> length-matched generic advice.

## Status

- Stage: pre-registered pilot design.
- Active card: Empirical Experiment Ledger.
- Optional later card: Dialectic Refutation Gate, only after trap tasks with
  objective correctness labels are available.
- Promotion status: no default promotion from smoke results. Positive pilot
  results can only create `candidate` or `review` evidence for the measured
  task family.

## Arms

Run the same task under three paired arms. Keep model, effort, tool budget,
output budget, wall-clock budget, retry policy, scorer, and safety policy fixed.

| Arm | Prompt condition | Purpose |
| --- | --- | --- |
| `control` | Fairy Tale baseline without genius method cards. | Baseline behavior. |
| `placebo` | Length-matched generic caution and verification advice, with no artifact schema. | Separates generic extra advice from structured method value. |
| `treatment` | Empirical Experiment Ledger artifact schema plus instruction to fill it before claiming success. | Measures the schema/artifact increment. |

The primary comparison is `treatment` versus `placebo`. `placebo` versus
`control` only measures generic advice or extra-thinking effects.

## Task Criteria

### Positive Tasks

Use agentic-coding or refactoring tasks with ground-truth validation where:

- a plausible naive answer can claim success while hidden or ground-truth tests
  still fail;
- the fix or conclusion depends on observing a test, log, screenshot, runtime
  behavior, or baseline;
- the scorer can independently mark verified pass or failure;
- the prompt does not reveal which arm is running.

Preferred sources are held-out SWE-Bench Pro style tasks, local refactoring
fixtures, UI/log/CI trap fixtures, or less-context style coding seeds with
ground-truth validators.

### Negative Tasks

Use tasks where Empirical Experiment Ledger should not be helpful:

- narrative preference or tone choice,
- low-risk chat,
- purely normative judgment,
- simple deterministic formatting with explicit rules.

Negative-family success is non-inferiority, not improvement. Treatment should
not underperform control beyond the pre-registered margin, and the router probe
should learn to avoid applying the card when it is not useful. When a negative
task has no binary ground-truth pass signal, use a blind quality verdict,
quality-per-token, latency/cost, and misapplied-artifact rate for
non-inferiority.

## Metrics

Primary outcomes:

- `false_success_claim_rate`: proportion of responses that claim the task is
  fixed, passed, or complete while the ground-truth validator fails.
- `verified_pass_rate`: proportion of responses whose artifact passes the
  ground-truth validator. This value must come from a separate blind verdict
  artifact, not from the model answer.

Secondary outcomes:

- `quality_per_token`: verified or rubric score divided by total prompt and
  completion tokens when available.
- `elapsed_seconds`.
- `budgeted_correct`: verified pass within the pre-registered token/time budget.

Mechanism trace, not a primary outcome:

- whether the ledger artifact was produced;
- whether hypothesis, observable, instrument, baseline, procedure, result,
  confounders, and next experiment were filled;
- whether the ledger changed the final answer, stopped a false claim, or
  triggered a validator.

Do not use ledger completion rate as a primary score. Treatment receives the
schema, so rewarding filled fields would be circular.

## Statistics

The design is paired: every task appears in all three arms.

- Smoke: n=8-10 positive tasks is go/no-go and variance estimation only. It
  cannot promote the method.
- Confirmation: choose n after smoke using observed discordance and cost.
- Main paired tests: McNemar exact for binary discordant pairs and paired
  bootstrap over per-task deltas.
- Do not require a fixed `+5 pp` effect with CI95 lower bound above zero at
  small n. That would be underpowered by construction.
- Record confidence intervals and all negative results.

## Routing Probe

Forced-injection evaluation does not measure routing. Add a separate small
routing-accuracy probe:

- Input: task prompt plus all relevant Accessible Genius Method card summaries.
- Positive criterion: select Empirical Experiment Ledger for positive tasks.
- Negative criterion: do not select it for negative tasks.
- Metrics: selection precision/recall, false-positive selection rate, and
  negative-family abstention rate.

Routing probe thresholds apply only to router promotion, not to the forced
schema effect-size test.

## Success Thresholds

Smoke can proceed to confirmation only if:

- treatment improves false success claims or verified pass rate versus placebo
  in the expected direction;
- treatment does not obviously harm negative-family tasks;
- trace review shows the ledger changed at least some decisions rather than
  being ignored;
- cost or latency does not dominate the outcome.

Confirmation can create a `candidate` result only if:

- treatment beats placebo on the pre-registered primary outcome under paired
  analysis;
- negative-family non-inferiority holds within the chosen margin;
- the routing probe is separately acceptable for deployment scenarios where the
  card is not forced;
- quality-per-token and elapsed time are reported.

`keep` requires held-out reproduction. `default` promotion is not allowed from
this pilot; if later justified, the core skill may only receive a one-line
pointer to a reference, not the full card logic.

## Harness Contract

Use `scripts/genius_method_eval.py` to:

1. validate task JSONL fixtures,
2. build arm-specific prompt bundles,
3. write a blind key for grading,
4. summarize answer JSONL joined to separate ground-truth verdict JSONL with
   paired deltas and exact discordance counts.
5. estimate the confirmation-run paired n from the smoke summary with the
   `power` command.

The harness does not call model APIs. Model execution and ground-truth scoring
must be recorded as separate artifacts so the eval remains auditable. Answer
rows may contain `claimed_success`, token usage, elapsed time, and method trace;
verdict rows contain `verified_pass`, `quality_score`, and validator metadata.
