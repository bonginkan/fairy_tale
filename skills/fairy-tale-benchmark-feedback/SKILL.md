---
name: fairy-tale-benchmark-feedback
description: Apply evaluated feedback from SWE-Bench Pro, HLE-style closed-ended tasks, and defensive ExploitBench sandbox runs by classifying measured misses and observed success practices, adding narrow reusable rules, pruning contradictions, and retrying held-out samples without benchmark-specific hardcoding.
---

# Fairy Tale Benchmark Feedback

Use this skill after a measured benchmark miss, work-product failure, or
successful benchmark slice whose practice should be made reproducible in
agentic coding, HLE-style closed-ended reasoning, or defensive ExploitBench
sandbox runs.

Do not inspect gold patches, hidden answers, private rubrics, scorer internals,
or restricted data. Use only task instructions, public/visible tests, official
harness artifacts, logs, and local work product.

## Feedback Loop

1. Preserve the run conditions: model, effort, prompt, tools, scorer, sample
   IDs, budget, concurrency, and artifacts.
2. Convert misses and observed success practices into a feedback ledger:
   - SWE-Bench Pro: `scripts/benchmark_feedback_ledger.py swe-bench-pro`
   - HLE-style tasks: `scripts/benchmark_feedback_ledger.py hle`
   - ExploitBench: `scripts/benchmark_feedback_ledger.py exploitbench`
3. Run pruning before promotion:
   `scripts/feedback_pruner.py --ledger <ledger.json> --output <prune.json>`.
4. Keep only narrow candidate or observed-success rules with evidence. Do not
   promote a rule because it sounds plausible.
5. If the same failure signature repeats, a run produces no meaningful artifact,
   or the validation ledger is missing, run bounded Fairy Fusion before retry:
   isolated reviewers, one synthesis pass, append-only review artifacts, and
   only a compact closure hint returned to the main agent.
6. Retry a held-out or failed slice under the same scorer. Record before/after
   pass rate, confidence interval when applicable, cost, and regressions.
7. Promote only rules that improve the retry without task-ID hardcoding or
   cross-domain regression.

## SWE-Bench Pro Miss Classes

- `existing_behavior_regression`: the patch satisfied a new requirement by
  breaking visible existing behavior. Preserve old invariants unless the task
  explicitly deprecates them; implement new priority rules narrowly.
- `missing_public_interface`: the task named a function, type, method, helper,
  or path, but the symbol was not importable/exported exactly as specified.
- `self_selected_validation_gap`: self-chosen focused checks passed, but
  scorer-selected adjacent tests failed. Add compatibility checks for touched
  helper/API surfaces.
- `scorer_failure_general`: the failure needs a concrete behavior/interface
  hypothesis before retry; avoid broad prompt growth.

Before finalizing a SWE patch:

1. List every named new interface and verify exact export/import/callability.
2. Run or inspect adjacent existing tests that encode prior behavior for every
   touched helper/API.
3. If new and old behavior appear to conflict, preserve old behavior by adding
   a narrower condition, not by replacing the old invariant.
4. If progress stalls, use Fairy Fusion SWE reviewers: interface, regression,
   validation, and minimality. Treat their synthesis as a checklist to verify,
   not as a replacement for repository evidence.
5. Use benchmark tools and container checks, but do not inspect hidden answers
   or gold patches.

## SWE-Bench Pro Success Practices

- `local_invariant_mapping`: map existing helpers, types, call sites, and
  adjacent tests before editing; reuse local abstractions.
- `targeted_container_validation`: validate inside the benchmark container with
  focused tests for the touched surface and record exact commands.
- `named_interface_completion`: implement the exact requested symbol at the
  requested path while preserving backward-compatible wrappers when existing
  callers rely on them.

## HLE-Style Miss Classes

- `output_exhaustion_no_final_answer`
- `missing_final_answer`
- `multiple_choice_label_drift`
- `overconfident_wrong_answer`
- `objective_without_feasibility_check`: the answer optimizes a scalar objective
  but fails to prove physical, geometric, placement, domain, or constraint
  feasibility.
- `wrong_answer_general`

Before finalizing HLE-style answers, write the exact final answer field first,
then compactly verify assumptions, answer format, and independent terms.
For optimization, packing, scheduling, routing, geometry, or resource allocation
items, verify both objective optimality and feasibility; do not assume additive
benefit, non-overlap, independence, or realizability merely because the
objective value is larger.

Successful HLE-style runs should preserve:

- exact answer field, confidence, model, judge model, dataset, seed, and
  item-level judged artifact,
- parseable final answer before optional explanation,
- compact derivation that verifies only the independent terms needed for the
  answer.

## ExploitBench Miss Classes

- `coverage_only_plateau`: basic code reachability exists, but the run did not
  progress to the next official sandbox signal.
- `no_signal_timeout`: the run spent too long exploring without harness-visible
  signal.

ExploitBench feedback is defensive-only. Use official sandbox artifacts and
upstream-compatible `stuck,wrapup` nudges. Do not convert transcripts into
real-target exploit instructions.

Successful ExploitBench practice includes:

- official sandbox IDs, seed, model, turn budget, cost cap, manifest, score
  artifact, and aggregate artifact,
- tying actions to official harness-visible capability signals rather than
  speculative exploit narratives,
- preserving defensive-only boundaries even when score improves.

## Promotion Rules

Keep candidate feedback out of default behavior until it has:

- measured evidence,
- a held-out retry result,
- no task-ID or sample-specific wording,
- no contradiction with existing kept rules,
- no material regression in another task family.
