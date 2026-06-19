# Agentic Loop Design Plan

Status: design draft / not promotion evidence.

This document defines the next evaluation and implementation route after the
Genius Method smoke results. The static Empirical Experiment Ledger did not
improve GPT-5.5 Codex over the Fairy Tale baseline in the public smoke runs.
The next hypothesis is narrower:

> For tasks where the baseline makes a false success claim or fails a hidden
> contract, an explicit observe-act-validate loop can recover failures more
> often than static advice or a static ledger, within a pre-registered cost
> budget.

This is not a claim that "agentic loops always help" or that Fairy Tale should
promote a new default behavior. It is a testable design for producing and
measuring recovery on headroom tasks.

## Why The Static Ledger Was Not Enough

The smoke runs showed two separate problems:

- Ceiling-limited tasks: GPT-5.5 Codex already passed the positive task under
  control, leaving no measurable treatment-vs-control headroom.
- Headroom task without recovery: an adversarial task produced a control
  failure surface, but the treatment arm failed the same filtered-test trap.

The likely missing ingredient is not another form to fill. It is a loop that
requires an external observation, changes the next action based on that
observation, and blocks success claims until a verifier has run.

## External Anchors

The design borrows only the transferable mechanisms from prior agent work:

- ReAct interleaves reasoning with actions and uses external observations to
  update plans rather than reasoning in isolation:
  https://arxiv.org/abs/2210.03629
- Reflexion uses feedback signals and a memory of reflected failures to improve
  later attempts without weight updates:
  https://arxiv.org/abs/2303.11366
- SWE-agent emphasizes the agent-computer interface: an agent needs compact,
  reliable ways to inspect files, edit, and run tests:
  https://arxiv.org/abs/2405.15793
- AlphaCodium treats code generation as a multi-stage test-driven flow rather
  than a single prompt:
  https://arxiv.org/abs/2401.08500
- Voyager uses environment feedback, execution errors, and self-verification
  for iterative program improvement, while keeping learned skills auditable:
  https://arxiv.org/abs/2305.16291
- Tree-of-Thought and LATS motivate bounded branching/search, but this design
  uses them only when an observation leaves multiple plausible next actions:
  https://arxiv.org/abs/2305.10601 and https://arxiv.org/abs/2310.04406

The common constraint is that self-reflection is not enough. The loop must be
anchored to environment feedback, tests, logs, screenshots, replay probes, or
other auditable observations.

## Loop Contract

Each task run is a sequence of bounded iterations. Every iteration records:

1. **State**: current objective, visible evidence, unresolved assumptions,
   known failures, and remaining budget.
2. **Hypothesis**: the smallest actionable claim about why the current answer
   might fail or what hidden contract may matter.
3. **Probe plan**: one minimal external action that can change belief. Examples
   include a targeted test, grep/search, runtime command, screenshot check,
   replay, fixture variant, or explicit user/question probe where appropriate.
4. **Action**: the executed command, edit, inspection, or question. Actions are
   restricted by the harness allowlist and sandbox.
5. **Observation**: raw output, failure message, diff, screenshot result, or
   validator verdict. Observations are immutable trace entries.
6. **Attribution**: first actionable fault step or reason the observation does
   not change the plan.
7. **Next decision**: continue with changed strategy, finalize, abstain, or
   stop as blocked.

The loop is fail-closed:

- A success claim without an external verifier is not a verified pass.
- Repeating the same failure class without a changed probe or strategy stops
  the loop.
- A loop cannot promote a reusable rule unless the final validator passes and
  the evidence links to the action that depended on the rule.
- Hidden validators remain outside the solver workspace. The agent may run
  public/local probes; the scorer runs ground-truth validators separately.

## Trace Schema

The harness should write an `agentic_loop_trace.json` artifact per run:

```json
{
  "schema_version": "agentic_loop.v1",
  "task_id": "string",
  "task_family": "agentic_coding|arc|legal|research|ui|security|other",
  "arm": "control|static_ledger|placebo_loop|agentic_loop",
  "model": "string",
  "budgets": {
    "max_iterations": 4,
    "max_prompt_tokens": 0,
    "max_completion_tokens": 0,
    "max_elapsed_seconds": 0,
    "max_cost_estimate": 0.0
  },
  "iterations": [
    {
      "index": 1,
      "state_summary": "string",
      "hypothesis": "string",
      "probe_plan": "string",
      "action": {
        "type": "command|edit|inspect|ask|answer",
        "input": "string",
        "allowed": true
      },
      "observation": {
        "source": "test|log|runtime|screenshot|diff|validator|user|none",
        "summary": "string",
        "artifact_path": "string"
      },
      "failure_class": "missing_validator|wrong_scope|overfit_visible|format|runtime|blocked|none",
      "next_decision": "continue|finalize|abstain|blocked"
    }
  ],
  "scored_observation_effects": [
    {
      "iteration_index": 1,
      "external_observation": true,
      "state_diff_changed_answer_or_action": true,
      "decisive_for_recovery": false
    }
  ],
  "final": {
    "claimed_success": false,
    "solver_answer_path": "string",
    "public_validation_passed": false,
    "ground_truth_verified_pass": null,
    "stop_reason": "verified|budget_exhausted|repeated_failure|blocked|abstained"
  }
}
```

Ground-truth fields such as `ground_truth_verified_pass` are joined only after
the independent scorer runs. They must not come from the model answer.
Mechanism fields such as `state_diff_changed_answer_or_action` and
`decisive_for_recovery` are also scorer-derived. The model may summarize an
observation, but it cannot self-score whether the observation changed its
belief or caused the recovery.

## Evaluation Arms

Use paired tasks and keep model, sandbox, tool budget, iteration budget, and
scorer fixed.

| Arm | Description | Purpose |
| --- | --- | --- |
| `control` | Current Fairy Tale baseline. | Deployment baseline. |
| `static_ledger` | Empirical Ledger schema without controller-enforced probing. | Separates artifact completion from actual agentic recovery. |
| `placebo_loop` | Same loop budget and command affordances, but generic retry/verification advice and no structured loop state. | Separates extra tool time from loop policy. |
| `agentic_loop` | Controller-enforced observe-act-validate loop with trace schema. | Measures the loop increment. |

The primary comparisons are:

- `agentic_loop` versus `control` on headroom tasks;
- `agentic_loop` versus `placebo_loop` to isolate the structured controller
  from extra retries/tools;
- `agentic_loop` versus `static_ledger` to test whether acting on observations
  beats writing a ledger.
- `placebo_loop` versus `control` to report how much recovery comes from extra
  retries and tool exposure alone.

### Current Runner Control Caveat

The Phase 2/3 controlled runner sends every arm through the same
controller-mediated request/action/observation channel. Its `control` arm is
therefore a controller-exposed Fairy Tale baseline, not a raw one-shot or full
deployment Codex baseline. If `control` recovers a task, that task has no
headroom for measuring `agentic_loop` improvement in this runner, even when
`agentic_loop` beats `placebo_loop` or `static_ledger`.

Do not use this runner to claim deployment-baseline improvement until a separate
non-loop baseline path is added or explicitly pre-registered. The current
runner is still useful for comparing structured loop guidance against generic
retry under equal controller exposure.

## Headroom First

Do not average away ceiling tasks. A positive task contributes to recovery
metrics only if control failed or made a false success claim under the same
ground-truth verifier.

Primary metrics:

- `headroom_recovery_rate`: among control-failed positive tasks, proportion
  recovered by the evaluated arm.
- `false_success_claim_rate`: claimed success while the ground-truth verifier
  fails.
- `verified_pass_rate`: ground-truth pass from a separate verdict artifact.
- `budgeted_verified_pass`: verified pass within pre-registered token, time,
  iteration, and cost budgets.

Secondary metrics:

- `iterations_used`;
- `changed_strategy_after_observation_rate`, derived by the scorer from
  answer/action state diffs after an external observation, not from model
  self-report;
- `repeated_failure_stop_rate`;
- `cost_estimate`;
- `quality_per_token` where a quality score exists.

Ceiling tasks remain useful for non-regression and cost checks, but they do not
prove improvement.

Mechanism attribution is limited to recoveries where a decisive observation was
external to the model's prior context: a test failure, grep hit, runtime error,
screenshot fact, replay result, or comparable environment signal. If the agent
only restates a self-generated concern and then improves, score the recovery as
valid outcome evidence but not as observation-driven loop evidence.

## Controller Semantics

The first implementation should be a thin harness, not a new general skill:

1. Build an isolated workspace for each task.
2. Give the agent only visible task files and public probes.
3. Ask the agent for one JSON loop step at a time.
4. Execute only allowlisted actions.
5. Append the observation to the trace.
6. Re-prompt with the trace summary and remaining budget.
7. Stop on verified local pass, abstention, repeated failure, or budget.
8. Run hidden/ground-truth scorer outside the workspace.

Allowed actions for the first coding pilot:

- `inspect_file`;
- `search`;
- `run_public_test`;
- `edit`;
- `write_answer`;
- `abstain`;
- `blocked`.

No direct hidden-test access is allowed. No success claim is accepted unless the
trace includes a matching validator observation.

## Pilot Task Design

Use tasks that are explicitly calibrated to produce control failures for the
selected model population.

For GPT-5.5 Codex:

- keep only tasks where control false-success is observed in smoke;
- raise trap difficulty through filtered tests, stale baselines, mocked
  concurrency, hidden locale paths, generated artifacts, or partial CI surfaces;
- record non-discriminative tasks as ceiling, not as evidence.

For smaller models:

- run a separate pilot population;
- do not mix small-model effects with GPT-5.5 effects;
- use the same paired arms and verifier contract.

Confirmatory and held-out fixtures must be authored or selected before the
final run. Public smoke fixtures adjusted after observing results are not
promotion evidence.

## Promotion Rules

Smoke results can only support planning. A candidate result requires:

- headroom subset size reported and non-zero;
- headroom subset size meets the pre-registered minimum n from the power
  plan;
- `agentic_loop` improves the pre-registered primary metric over both
  `control` and `placebo_loop` on paired headroom tasks;
- `agentic_loop` does not regress ceiling/negative tasks beyond the margin;
- non-headroom positive tasks and negative tasks are both present so regression
  can be checked fail-closed;
- cost and iteration budgets have 100% coverage and pass the gate;
- trace review shows that at least some recoveries followed from external
  observations, not from format compliance alone;
- held-out reproduction before any `keep` decision.

Default promotion to the core skill is out of scope. If a later confirmed
result justifies adoption, the skill body may receive only a one-line pointer
to a reference document.

## Implementation Phases

Phase 0: design and review.

- Keep this document as the design source.
- Get CC/MISA 3 review before code changes.
- Do not alter `SKILL.md`.

Phase 1: trace-only prototype.

- Add a script that accepts prepared answer/trace artifacts and scores
  headroom recovery, false success, cost coverage, and repeated failures.
- Reuse the existing coverage-aware promotion style from
  `scripts/genius_method_eval.py`.

Implemented entry point:

```bash
python3 scripts/agentic_loop_eval.py score \
  --key tmp/agentic-loop/blind-key.json \
  --traces tmp/agentic-loop/traces.jsonl \
  --verdicts tmp/agentic-loop/verdicts.jsonl \
  --output tmp/agentic-loop/summary.json
```

The scorer derives `scored_observation_effects` itself. Trace rows containing
model-authored `changed_belief`, `state_diff_changed_answer_or_action`,
`decisive_for_recovery`, `verified_pass`, or similar GT/mechanism fields are
rejected.

Phase 2: controlled loop runner.

- Add a local coding-task runner that executes one JSON action per iteration.
- Keep hidden validators outside the workspace.
- Save raw command outputs and trace summaries.

Implemented entry points:

```bash
python3 scripts/agentic_loop_runner.py run \
  --tasks fixtures/agentic-loop/tasks.jsonl \
  --output tmp/agentic-loop-run \
  --solver-command python3 my_solver.py

python3 scripts/agentic_loop_runner.py run-hidden-validators \
  --run-dir tmp/agentic-loop-run \
  --judge-manifest tmp/agentic-loop-run/judge_manifest.jsonl \
  --output tmp/agentic-loop-run/verdicts.jsonl
```

The runner writes hidden validators only to `judge_manifest.jsonl`. They are
not copied into solver workspaces and are not included in solver requests.
Solver requests are logged under `requests/` for audit. Allowed actions are
executed by the controller, not by free-form solver shell commands.

Phase 3: smoke.

- Run small paired smoke on calibrated headroom tasks.
- Report headroom size, recovery count, cost, failure classes, and
  `review_only`.

Implemented smoke connector:

```bash
python3 scripts/agentic_loop_runner.py run \
  --tasks fixtures/agentic-loop/smoke.jsonl \
  --output tmp/agentic-loop-smoke \
  --solver-command python3 /absolute/path/to/scripts/agentic_loop_codex_solver.py \
    --model gpt-5.5 --reasoning-effort xhigh
```

`agentic_loop_codex_solver.py` is action-only: it strips the task
`workspace_path` before prompting Codex, runs Codex in a separate scratch
directory, and returns only one JSON action for the controller. It rejects
hidden-validator or scorer-only fields if they appear in the request or model
output. The public `fixtures/agentic-loop/smoke.jsonl` file is a smoke and
connection fixture only; it is not confirmatory or held-out promotion evidence.

Phase 4: confirmation.

- Use fresh held-out tasks and fixed validators.
- Apply paired statistics only after smoke estimates headroom and discordance.
- Power the confirmation run on the headroom subset, not on total task count.
  Reuse the existing paired/bootstrap planning style from the Genius Method
  eval: estimate control-failure prevalence and discordance in smoke, then
  choose the confirmatory n needed for the pre-registered headroom threshold.

## Non-Goals

- This design does not prove that agentic loops improve Fairy Tale.
- It does not replace official SWE-Bench Pro or ARC-AGI evaluation.
- It does not turn every task into a long loop; routing and budgets remain
  separate claims.
- It does not rely on self-reported pass/fail fields from the model.
