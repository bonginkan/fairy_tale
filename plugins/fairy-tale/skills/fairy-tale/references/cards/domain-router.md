# Domain Router

- Do not apply the coding harness to every benchmark. Route first by task
  family: agentic coding/refactoring, HLE-style closed-ended knowledge, legal,
  biology/medicine/health, finance/document analysis, spatial/UI/3D, narrative,
  mechanism discovery, or defensive security.
- If the task is closed-ended, prefer a strict answer contract and item-level
  error taxonomy over broad autonomous exploration.
- If the task is legal, identify jurisdiction, authority, task type, facts,
  issue, rule, application, conclusion, and citation needs before answering.
- If the task is bio/health, classify safety category before reasoning and
  separate literature-grounded facts from hypotheses or clinical advice.
- If the task is finance/document work, extract evidence tables before making
  judgments.
- Treat domain-specific benchmark failures as routing/debugging evidence, not
  as proof that all Fairy Tale workflows fail.

