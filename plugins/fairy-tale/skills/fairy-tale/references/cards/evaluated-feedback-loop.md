# Evaluated Feedback Loop

- Treat failed benchmark criteria as reusable feedback, not just result data.
- For SWE-Bench Pro, HLE-style closed-ended tasks, and ExploitBench sandbox
  misses, apply `fairy-tale-benchmark-feedback`: classify measured failures,
  add only narrow candidate rules, prune contradictions, then retry a held-out
  slice before promotion.
- Create a narrow rule for each measured failure class and re-run a held-out
  retry slice before promoting the rule to the default skill.
- When benchmark artifacts are available, first convert failures into a scoped
  ledger with `scripts/benchmark_feedback_ledger.py`; do not hand-promote
  plausible rules without the ledger and held-out retry evidence.
- Before retaining or promoting accumulated feedback, run a pruning pass:
  detect contradictions, duplicates, superseded rules, stale evidence, and
  measured regressions. Prefer a small scoped rule over broad prompt growth.
- Treat unproven candidate rules as `review`, not `keep`, until a retry sample
  shows measured improvement.
- When a task is high-risk or repeatedly near-misses, run bounded Fairy Fusion
  review with `scripts/fairy_fusion_review.py` or a harness-native equivalent:
  independent specialist reviewers, contradiction table, blind-spot closure,
  artifact logging, and one-level recursion cap.
- When a miss looks like poor generalization rather than missing effort, run a
  generalization audit before adding task-specific rules: identify the latent
  invariant, the evidence that should have revealed it, the false analogy or
  over-compression that displaced it, and the smallest verifier that would
  have caught the miss on a neighboring task.

