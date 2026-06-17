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
3. Before writing a candidate rule, localize the first actionable fault step
   in the failed trajectory or work product. Link it to an existing Fairy Tale
   rule when that rule misled the run; otherwise mark it as missing coverage.
4. Revise an existing rule when responsibility is clear. Generate a new narrow
   rule only when no existing rule can be safely revised. Make no skill update
   when the trace does not support the attribution.
5. Run pruning before promotion:
   `scripts/feedback_pruner.py --ledger <ledger.json> --output <prune.json>`.
6. Keep only narrow candidate or observed-success rules with evidence. Do not
   promote a rule because it sounds plausible.
7. If the same failure signature repeats, a run produces no meaningful artifact,
   or the validation ledger is missing, run bounded Fairy Fusion before retry:
   isolated reviewers, one synthesis pass, append-only review artifacts, and
   only a compact closure hint returned to the main agent. Continue retrying
   until the local clear condition is met or the user/operator stops the run.
8. Retry a held-out or failed slice under the same scorer. Record before/after
   pass rate, confidence interval when applicable, cost, and regressions.
9. Promote only rules that improve the retry without task-ID hardcoding or
   cross-domain regression.

## SWE-Bench Pro Miss Classes

- `api_compatibility_break`: a patch changes a function, method, constructor,
  return shape, argument list, exported symbol, or file path in a way that
  breaks existing callers or visible tests.
- `missing_adjacent_symbol`: a patch references a helper, type, component,
  module, constant, or path that was not added, exported, generated, or
  imported on the touched surface.
- `test_mock_contract_break`: production code may work, but the patch changes
  construction or dependency-injection shape in a way that breaks existing test
  doubles, mocks, or factories.
- `edge_case_invariant_gap`: the main path compiles, but an existing invariant
  still fails for a migration, mapping, default, empty, boundary, duplicate,
  ordering, or error-path case.
- `weak_test_oracle`: the patch changes or adds tests that can pass without
  proving the requested behavior, such as tautological assertions, testing
  implementation details, mirroring current buggy output, or mocking the unit
  under test into success.
- `architectural_erosion`: the patch may pass current tests while making the
  next change harder through duplicated logic, large special-case chains,
  unrelated surface area, or added complexity in already-large functions.
- `dependency_or_artifact_churn`: the patch changes dependencies, lockfiles,
  generated outputs, vendored code, snapshots, or broad config without clear
  task necessity and validation.
- `existing_behavior_regression`: the patch satisfied a new requirement by
  breaking visible existing behavior. Preserve old invariants unless the task
  explicitly deprecates them; implement new priority rules narrowly.
- `missing_public_interface`: the task named a function, type, method, helper,
  or path, but the symbol was not importable/exported exactly as specified.
- `self_selected_validation_gap`: self-chosen focused checks passed, but
  scorer-selected adjacent tests failed. Add compatibility checks for touched
  helper/API surfaces.
- `implicit_contract_gap`: the prompt did not spell out an invariant, but
  adjacent code, legacy callers, mocks, fixtures, generated files, docs, or
  domain conventions relied on it. Recover tacit intent from artifacts before
  editing and verify the inferred contract with a neighboring check.
- `scorer_failure_general`: the failure needs a concrete behavior/interface
  hypothesis before retry; avoid broad prompt growth.

Before finalizing a SWE patch:

1. List every named new interface and verify exact export/import/callability.
2. Before changing an existing contract, list affected callers and visible
   tests for the touched function/method/type/component/module. Preserve
   backward-compatible wrappers, defaults, overloads, or adapters unless the
   task explicitly removes the old behavior.
3. Recover tacit contracts from artifacts: adjacent files, old tests,
   generated code, mocks/fixtures, docs, issue wording, naming conventions,
   and existing error handling. Mark each inferred contract as confirmed,
   likely, risky, or needs user/input evidence.
4. Verify every referenced helper/type/component/module exists at the final
   path and is exported/imported exactly as the surrounding code expects.
5. Run or inspect adjacent existing tests that encode prior behavior for every
   touched helper/API.
6. If new and old behavior appear to conflict, preserve old behavior by adding
   a narrower condition, not by replacing the old invariant.
7. Design one applicable edge-case check for each changed surface: empty,
   nil/null, default/legacy path, boundary size, duplicate/order,
   mapping/migration, permission/error path, or fixture/mock construction.
8. If validation logs show missing arguments, undefined symbols, missing
   modules, constructor/type errors, or equality invariant failures, classify
   the patch as a contract failure and fix that before adding more feature
   logic.
9. If tests or fixtures are edited, require red-green or external-behavior
   proof. Reject tests that assert `true`, assert only implementation details,
   snapshot accidental output, or mock the unit under test so the test cannot
   fail for the real bug.
10. Review maintainability and change surface: reject duplicated logic, broad
   special-case chains, dependency/lockfile churn, generated/vendor artifacts,
   and large unrelated diffs unless the task explicitly requires them.
11. If progress stalls, use Fairy Fusion SWE reviewers: interface,
   contract-compatibility, regression, edge-case validation, and minimality.
   Treat their synthesis as a checklist to verify, not as a replacement for
   repository evidence.
12. Use benchmark tools and container checks, but do not inspect hidden answers
   or gold patches.

## SWE-Bench Pro Success Practices

- `local_invariant_mapping`: map existing helpers, types, call sites, and
  adjacent tests before editing; reuse local abstractions.
- `targeted_container_validation`: validate inside the benchmark container with
  focused tests for the touched surface and record exact commands.
- `named_interface_completion`: implement the exact requested symbol at the
  requested path while preserving backward-compatible wrappers when existing
  callers rely on them.
- `executable_model_verification`: before spending broad retries, encode the
  current understanding as a small checkable model: expected inputs, state,
  transitions, public contract, old invariants, and success condition; then
  falsify it with adjacent tests or a focused script.

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
- first-actionable-fault attribution and a revise-or-generate decision,
- a held-out retry result,
- no task-ID or sample-specific wording,
- no contradiction with existing kept rules,
- no material regression in another task family.
