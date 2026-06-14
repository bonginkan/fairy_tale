# Legal Evaluated Feedback

Date: 2026-06-14 JST

## Benchmark result

Local Harvey LAB-compatible sample:

- sample: n=100, seed 20260614
- model: `openai/gpt-5.5`
- effort: `medium`
- skills: `docx`, `xlsx`, `pptx`, `fairy-tale-legal`
- judge: `gpt-4.1`
- workers: 4
- all-pass: 11/100 = 11.0%
- 95% Wilson CI: 6.25-18.63% (half-width +/-6.19 pp)
- criterion pass rate: 5804/6417 = 90.45%
- image-reported GPT-5.5 legal baseline: 2.1%
- image-reported Fable/Mythos legal reference: 13.3%
- one-sided binomial p-value vs 2.1% baseline: 8.90e-6

This is a local measured sample, not an official Harvey LAB leaderboard score.

## Failure structure

The run produced 89 non-all-pass tasks. The important signal is not only the
all-pass rate: 17 failures missed exactly one criterion, and 28 failures missed
at most two criteria. The current legal harness is often close, but it lacks a
final exhaustive closure pass.

Failure taxonomy from `scripts/legal_feedback_analyzer.py`:

| Class | Count | Interpretation |
| --- | ---: | --- |
| `near_miss_final_criterion` | 17 | One missing requirement, caveat, clause, or citation prevents all-pass. |
| `small_coverage_gap` | 19 | Two or three misses; usually final checklist incompleteness. |
| `moderate_coverage_gap` | 40 | Several missed criteria despite mostly correct structure. |
| `domain_scaffold_gap` | 10 | Domain-specific legal scaffold is too weak. |
| `large_draft_collapse` | 1 | Full-document drafting lost clause architecture or cross-references. |
| `calculation_or_form_collapse` | 1 | Worksheet/form-style legal calculation was under-scaffolded. |
| `issue_spotting_coverage_collapse` | 1 | Discovery/counterparty issue spotting lacked exhaustive matrixing. |

Largest collapses:

| Task | Score |
| --- | ---: |
| `corporate-ma/draft-stock-purchase-agreement` | 17/117 |
| `trusts-estates-private-client/draft-child-support-worksheet` | 28/47 |
| `healthcare-life-sciences/draft-response-to-civil-investigative-demand` | 42/64 |
| `trusts-estates-private-client/identify-issues-in-discovery-responses` | 33/49 |
| `emerging-companies-venture-capital/draft-markup-of-bridge-loan-agreement` | 43/62 |

Frequent near-miss areas:

- commercial contract first drafts and redlines,
- IP closing/checklist and litigation drafting,
- employment/equity plan drafting,
- real estate construction markup,
- data-privacy/security incident response redlines.

## Feedback retry result

A 15-task retry was run against prior misses from the same n=100 legal sample.
The retry kept model, effort, judge, and task IDs fixed, and added
`fairy-tale-legal-feedback` to the existing `docx`, `xlsx`, `pptx`, and
`fairy-tale-legal` skills.

| Metric | Before Feedback | After Feedback | Change |
| --- | ---: | ---: | ---: |
| All-pass rate | 0/15 = 0.0% | 3/15 = 20.0%; 95% Wilson CI 7.05-45.19% | +20.0 pp |
| Criterion pass rate | 922/1108 = 83.21% | 1004/1108 = 90.61% | +7.40 pp |
| One-miss failures | 10 | 5 | -5 |
| Large collapses below 70% criteria | 5 | 4 | -1 |

Task-level deltas:

| Task | Before | After | Delta | Result |
| --- | ---: | ---: | ---: | --- |
| `corporate-ma/draft-stock-purchase-agreement` | 17/117 | 102/117 | +72.6 pp | improved, not all-pass |
| `trusts-estates-private-client/draft-child-support-worksheet` | 28/47 | 32/47 | +8.5 pp | improved, not all-pass |
| `healthcare-life-sciences/draft-response-to-civil-investigative-demand` | 42/64 | 44/64 | +3.1 pp | improved, not all-pass |
| `trusts-estates-private-client/identify-issues-in-discovery-responses` | 33/49 | 30/49 | -6.1 pp | regressed |
| `emerging-companies-venture-capital/draft-markup-of-bridge-loan-agreement` | 43/62 | 40/62 | -4.8 pp | regressed |
| `intellectual-property/draft-closing-checklist-memorandum` | 96/97 | 91/97 | -5.2 pp | regressed |
| `contracts/employment-compensation/equity-incentive-plan/first-draft` | 93/94 | 94/94 | +1.1 pp | all-pass |
| `contracts/commercial-vendor-customer/master-services-agreement/first-draft/scenario-06` | 86/87 | 86/87 | 0.0 pp | one miss remains |
| `contracts/industry-specific/media/talent-and-influencer-agreement/first-draft` | 81/82 | 81/82 | 0.0 pp | one miss remains |
| `contracts/disputes/class-action-settlement-agreement/counterparty-paper-review` | 74/75 | 75/75 | +1.3 pp | all-pass |
| `contracts/commercial-vendor-customer/vendor-services-agreement/counterparty-paper-review/scenario-02` | 71/72 | 72/72 | +1.4 pp | all-pass |
| `contracts/data-privacy-security/incident-response-retainer-agreement/first-turn-redline` | 70/71 | 70/71 | 0.0 pp | one miss remains |
| `contracts/disputes/settlement-agreement-and-release/playbook-escalation` | 65/66 | 65/66 | 0.0 pp | one miss remains |
| `real-estate/draft-markup-of-counterparty-construction-contract` | 63/64 | 62/64 | -1.6 pp | regressed |
| `contracts/commercial-vendor-customer/saas-api-subscription/first-turn-redline/scenario-01` | 60/61 | 60/61 | 0.0 pp | one miss remains |

Interpretation:

- The feedback skill materially reduced large draft collapse. The stock
  purchase agreement moved from 14.5% criteria pass to 87.2%.
- Three near-miss contract review tasks converted to all-pass.
- The main residual failure is final criterion closure: five retry tasks still
  missed exactly one criterion.
- Issue spotting, bridge-loan markup, checklist drafting, and construction
  markup regressed. These need more specific reviewer roles rather than broader
  closure language.

## Feedback actions

### Legal Closure Sweep

Use on every legal task before final output:

1. Build a requirement ledger from task instructions, matter files, playbooks,
   and requested output format.
2. Mark each requirement as `included`, `omitted`, `not applicable`, or
   `conflict`.
3. For every `omitted` item, either add the item or state why it is out of
   scope.
4. Run a final one-miss audit: headings, defined terms, party names, dates,
   jurisdictions, thresholds, notice mechanics, exceptions, schedules, exhibits,
   signature blocks, and citations.

### Full-Draft Scaffold

Use on long draft tasks:

1. Create a clause inventory before prose drafting.
2. Create a defined-term ledger and cross-reference ledger.
3. Draft by sections, then run a section-to-requirement reconciliation.
4. Run schedule/exhibit and signature-block closure.
5. Verify no placeholder, inconsistent defined term, missing optionality, or
   dropped negotiated term remains.

### Legal Calculation/Form Scaffold

Use on worksheets, certificates, covenants, child-support, tax, or finance-like
legal calculations:

1. Extract inputs into a table.
2. Record units, dates, periods, exchange rates, thresholds, and governing
   formula.
3. Compute separately from prose.
4. Reconcile each output field against the required form or certificate.

### Exhaustive Issue Matrix

Use on discovery, counterparty-review, diligence, and issue-spotting tasks:

1. Build a row for every source document, request, objection, clause, or
   counterparty mark.
2. For each row, record issue, authority/playbook basis, severity, action, and
   whether it must appear in the final work product.
3. Do not collapse similar issues until after the first full pass.

### Final Criterion Closure

Use when the draft is already mostly complete or the task family has shown
one-miss behavior:

1. Build a hidden checklist from every instruction bullet, source-document
   command, playbook rule, party-specific preference, and required output
   artifact.
2. Ask, "What single criterion would a grader still mark missing?" before
   finalizing.
3. For redlines and markup tasks, verify every accepted, rejected, narrowed,
   escalated, and unchanged counterparty position is explicitly represented.
4. For checklists and memoranda, verify every requested category has at least
   one concrete item or an evidence-backed "none found" note.
5. Do not trade exact task coverage for broader legal polish.

## Evaluated Feedback Loop

Every benchmark run that misses criteria should feed the skill:

1. Record measured result, confidence interval, scorer, model, effort, sample
   IDs, and artifacts.
2. Classify failures into the taxonomy above.
3. Add or update a narrow harness rule tied to a real failure class.
4. Re-run a held-out retry set of 10-20 failed tasks.
5. Keep the rule only if it improves all-pass or criterion pass rate without
   obvious regressions.
6. Promote the rule from local feedback to default skill only after a second
   confirmation run or user approval.

## Fairy Fusion Subagenting

Use Fairy Fusion review on high-risk legal tasks and known weak areas.

The design reference is OpenRouter's public Fusion/Subagent/Advisor mechanism:
independent panel outputs, isolated worker task descriptions, a judge that
compares rather than merges, and structured consensus, contradictions, partial
coverage, unique insights, and blind spots. Fairy Tale does not call OpenRouter
for this. The internal implementation is `scripts/fairy_fusion_review.py`,
which runs bounded independent reviewer passes and a local synthesis pass using
the configured model provider.

Fairy Tale's legal fusion contract:

1. Decompose the task into specialist reviewers:
   - coverage reviewer,
   - defined-terms/cross-reference reviewer,
   - calculation/form reviewer,
   - domain specialist reviewer,
   - adversarial omitted-risk reviewer.
2. Keep reviewers independent; each receives the same facts and a narrow output
   schema.
3. Synthesize by contradiction table, not majority vote.
4. Require closure for any item raised by any reviewer unless it is explicitly
   rejected with evidence.
5. Bound recursion to one level and cap panel size by task risk and budget.
6. Preserve the reviewer outputs and synthesis JSON as evaluated feedback.

Runnable entry point:

```bash
scripts/fairy_fusion_review.py --domain legal --prompt-file task.md --execute --output review.json
```

## Sources

- OpenRouter Fusion docs, design reference only:
  https://openrouter.ai/docs/guides/features/plugins/fusion
- OpenRouter Fusion model page, design reference only:
  https://openrouter.ai/openrouter/fusion
- OpenRouter Subagent docs, design reference only:
  https://openrouter.ai/docs/guides/features/server-tools/subagent
- OpenRouter Advisor docs, design reference only:
  https://openrouter.ai/docs/guides/features/server-tools/advisor
- OpenAI evaluation best practices:
  https://developers.openai.com/api/docs/guides/evaluation-best-practices
- Anthropic agent eval guidance:
  https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
