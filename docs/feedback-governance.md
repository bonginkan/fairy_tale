# Feedback Governance

Fairy Tale feedback is useful only while it stays measured, scoped, and
non-contradictory. Unbounded feedback accretion turns into prompt mud: old
rules compete with new rules, broad rules hide domain-specific exceptions, and
near-miss fixes can regress other task families.

## Feedback Ledger

Store evaluated feedback as rules with explicit metadata:

```json
{
  "id": "legal-final-criterion-closure-v1",
  "scope": "legal",
  "failure_class": "near_miss_final_criterion",
  "rule": "Before final output, ask what single criterion remains missing.",
  "status": "candidate",
  "evidence": ["fairy-legal-retry-feedback-15-gpt-5-5-medium"],
  "sample_size": 15,
  "metrics": {
    "before_all_pass_rate": 0.0,
    "after_all_pass_rate": 0.2,
    "before_criterion_pass_rate": 0.8321,
    "after_criterion_pass_rate": 0.9061
  },
  "regression_count": 0,
  "created_at": "2026-06-14"
}
```

Minimum fields:

- `id`
- `scope`
- `failure_class`
- `rule`
- `status`
- `evidence`
- `metrics` or a reason why measurement is pending

## Step-Level Skill Adaptation Route

Do not update the default skill from a whole failed trajectory or a vague
session summary. First assign credit to the smallest actionable fault:

1. Preserve the trace, run conditions, active skills, and validation artifact.
2. Extract a short fault chain and select the first step whose correction could
   have changed the outcome.
3. Link that fault to active or candidate skills. If an existing skill misled
   the run, revise that skill. If no skill meaningfully applies, generate a
   narrow new candidate. If the evidence is insufficient, make no skill update.
4. Keep revisions minimal: add preconditions, disambiguation, negative
   examples, and qualification checks only where the trace supports them.
5. Qualify the candidate with a retry and a neighboring or held-out regression
   slice before promotion. Reject broad updates whose benefit is unmeasured or
   whose regression cost is unresolved.

Record this route with the step-level skill adaptation template in
`skills/fairy-tale/references/process.md`. This follows the SkillAdaptor lesson
that stable skill maintenance comes from step-level failure attribution,
responsible-skill linking, targeted modification, and explicit qualification,
not from broad trajectory-level reflection.

## Pruning Gate

Run pruning before promoting feedback into the default skill, and periodically
after new benchmark runs:

```bash
scripts/benchmark_feedback_ledger.py hle \
  --metrics hle-run/metrics.json \
  --judged hle-run/judged.json \
  --output feedback-ledger.json

scripts/feedback_pruner.py \
  --ledger feedback-ledger.json \
  --output feedback-prune-report.json \
  --kept-output feedback-ledger-kept.json
```

The pruner flags:

- exact duplicates under the same scope and failure class,
- explicit `conflicts_with` relationships,
- likely semantic opposition such as `always/include` versus `never/exclude`,
- superseded rules,
- rules with measured regression,
- rules with no evidence or no retry sample,
- stale rules without positive evidence.

The output classifies each rule as:

- `keep`: measured improvement or approved neutral evidence and no conflict,
- `review`: unresolved conflict, unproven candidate, weak evidence, stale
  evidence, or protected approved rule with regression,
- `prune`: superseded, deprecated, rejected, or measured regression with no
  protection.

## Promotion Policy

Do not promote a rule merely because it sounds plausible.

Promote to default skill only when:

1. the rule has a measured source run,
2. it improves all-pass rate or criterion pass rate,
3. it does not create a material regression in another task family,
4. it does not conflict with an existing approved rule,
5. it has survived a pruning gate.

If a rule improves broad coverage but increases one-miss failures, keep it as a
scoped rule and add a narrower closure rule rather than making it global.

## Legal Example

The 2026-06-14 legal retry improved all-pass from 0/15 to 3/15 and criterion
pass rate from 83.21% to 90.61%. That supports keeping the legal feedback
mechanism, but the task-level deltas also show regressions in issue spotting,
bridge-loan markup, checklist drafting, and construction markup. Those
regressions should become scoped review items, not global rules.
