# Legal Evaluated Feedback Harness

Use this after any legal benchmark or legal work-product failure.

## Failure Taxonomy

- `near_miss_final_criterion`: one missing requirement, caveat, citation,
  clause, date, party, threshold, schedule, exhibit, or signature item.
- `small_coverage_gap`: two or three misses; usually final checklist failure.
- `moderate_coverage_gap`: multiple misses despite correct top-level shape.
- `large_draft_collapse`: long-form draft lost clause inventory, defined
  terms, cross-references, schedules, or negotiated business terms.
- `calculation_or_form_collapse`: worksheet, covenant, tax, child support, or
  finance-style computation lacks table-first calculation.
- `issue_spotting_coverage_collapse`: discovery, diligence, counterparty
  review, or issue spotting lacks exhaustive matrixing.
- `domain_scaffold_gap`: specialized legal domain needs a narrow scaffold.

## Closure Sweep

Before final legal output:

1. Build a requirement ledger from the instruction, matter files, playbooks,
   and requested format.
2. Mark every row as `included`, `omitted`, `not applicable`, or `conflict`.
3. Resolve every `omitted` row or state why it is outside scope.
4. Check headings, defined terms, party names, dates, jurisdictions, thresholds,
   notice mechanics, exceptions, schedules, exhibits, signature blocks, and
   citations.

## Weak-Area Scaffolds

- Long drafts: clause inventory, defined-term ledger, cross-reference ledger,
  section-to-requirement reconciliation, schedule/exhibit closure.
- Calculations/forms: input table, formula table, units/dates/thresholds,
  computed output table, field-by-field reconciliation.
- Issue spotting: one row per source document, request, objection, clause, or
  counterparty mark before deduplication.
- Final criterion closure: when only one or two criteria may remain, ask what
  a grader would still mark missing; verify every instruction bullet,
  playbook rule, counterparty position, requested category, filename, and
  output-format obligation is explicitly represented or ruled out with
  evidence.

## Evaluated Feedback Loop

1. Record score, confidence interval, model, effort, sample IDs, scorer, and
   artifacts.
2. Classify failures with the taxonomy above.
3. Add a narrow rule tied to a measured failure class.
4. Re-run 10-20 failed tasks.
5. Keep the rule only if all-pass or criterion pass rate improves without
   obvious regressions.

## Fairy Fusion Review

Use on high-risk legal tasks, known weak areas, and near-miss-prone drafts.

Default runner:

```bash
scripts/fairy_fusion_review.py --domain legal --prompt-file task.md --execute --output review.json
```

Reviewer roles:

- coverage reviewer,
- defined-terms and cross-reference reviewer,
- calculation/form reviewer,
- domain specialist reviewer,
- adversarial omitted-risk reviewer.

Keep reviewers independent. Synthesize by contradiction table, not majority
vote. Any item raised by any reviewer must be accepted, rejected with evidence,
or escalated. Cap recursion to one level and cap reviewer count by budget.
Record the raw reviewer outputs and synthesis JSON as feedback artifacts.
