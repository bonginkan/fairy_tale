---
name: fairy-tale-legal-feedback
description: Apply evaluated legal benchmark feedback, closure sweeps, and Fairy Fusion review to reduce one-miss and large-collapse failures in legal drafting, review, issue spotting, and form/calculation tasks.
---

# Fairy Tale Legal Feedback

Use this skill after a legal benchmark miss, on high-risk legal work product,
or when a legal task resembles known weak areas from the 2026-06-14 LAB-style
sample.

Do not read grading rubrics or hidden expected answers. Use only task
instructions, provided matter documents, authorized tools, and the visible work
product.

## Failure Classes

- `near_miss_final_criterion`: one missing requirement, caveat, citation,
  clause, date, party, threshold, schedule, exhibit, or signature item.
- `small_coverage_gap`: two or three missed requirements.
- `moderate_coverage_gap`: several missed requirements despite a plausible
  top-level structure.
- `domain_scaffold_gap`: a practice area needs a domain-specific checklist.
- `large_draft_collapse`: a long draft lost clause architecture, defined terms,
  cross-references, schedules, or negotiated business terms.
- `calculation_or_form_collapse`: a worksheet, covenant, tax, support, or
  finance-like form was not handled table-first.
- `issue_spotting_coverage_collapse`: discovery, diligence, counterparty
  review, or issue spotting lacked an exhaustive row-by-row matrix.

## Required Closure Sweep

Before final output:

1. Build a requirement ledger from the instructions, matter documents,
   playbooks, requested filenames, and requested output format.
2. Mark each requirement as `included`, `omitted`, `not applicable`, or
   `conflict`.
3. Resolve every `omitted` or `conflict` row before finalizing.
4. Run a one-miss audit for headings, defined terms, party names, dates,
   jurisdictions, thresholds, notice mechanics, exceptions, schedules,
   exhibits, signature blocks, citations, and caveats.

## Weak-Area Scaffolds

- Long drafts: create clause inventory, defined-term ledger,
  cross-reference ledger, section-to-requirement reconciliation, and
  schedule/exhibit/signature closure before prose polish.
- Calculations/forms: extract inputs into a table, record governing formula,
  units, dates, periods, thresholds, and reconcile every output field.
- Issue spotting: create one row per source document, request, objection,
  clause, counterparty mark, or issue before deduplication.
- Final criterion closure: when the work product is close, ask what single
  criterion a grader would still mark missing; verify every instruction bullet,
  playbook rule, counterparty position, requested category, filename, and
  output-format obligation is explicitly represented or ruled out with
  evidence.

## Fairy Fusion Review

Use bounded independent reviewers when the task is high-risk, known weak-area,
or near-miss-prone.

Reviewer roles:

- coverage reviewer,
- draft architecture / defined-term reviewer,
- calculation or form reviewer,
- domain specialist reviewer,
- adversarial omitted-risk reviewer.

Keep reviewers independent. Synthesize by contradiction table, not majority
vote. Any item raised by any reviewer must be accepted, rejected with evidence,
or escalated. Cap recursion at one level and cap reviewer count by budget.

If `scripts/fairy_fusion_review.py` is available, it is the default local
runner. Otherwise, apply the same reviewer contract manually inside the harness.

## Evaluated Feedback Loop

After any scored run:

1. Record score, confidence interval, model, effort, scorer, sample IDs, and
   artifacts.
2. Classify failures using the taxonomy above.
3. Add one narrow rule tied to a measured failure class.
4. Re-run 10-20 failed tasks or a held-out slice.
5. Keep the rule only if all-pass or criterion pass rate improves without
   obvious regressions.
6. Before promoting or retaining accumulated rules, run feedback pruning:
   detect contradictions, duplicates, superseded rules, stale evidence, and
   measured regressions. Prefer scoped corrections over broad prompt growth.

Default pruning command:

```bash
scripts/feedback_pruner.py --ledger feedback-ledger.json --output feedback-prune-report.json
```
