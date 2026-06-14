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

## Pruning Gate

Run pruning before promoting feedback into the default skill, and periodically
after new benchmark runs:

```bash
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

- `keep`: positive or neutral measured evidence and no conflict,
- `review`: unresolved conflict, weak evidence, stale evidence, or protected
  approved rule with regression,
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
