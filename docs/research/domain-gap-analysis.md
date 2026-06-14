# Domain Strengthening Plan: HLE, Legal, Knowledge, and Effort Inversion

Date: 2026-06-14 JST

## Scope

This note strengthens Fairy Tale for domains that are not adequately covered by
the current coding-heavy harness: HLE-style closed-ended knowledge tasks, legal
reasoning, bio/health, finance/document analysis, and reasoning-effort
selection. It treats benchmark observations as evidence only when run
conditions are controlled and reproduced.

## Diagnosis

The current Fairy Tale skill is strongest on agentic coding, codebase
navigation, 3D/UI construction, workflow self-improvement, and mechanism
discovery. HLE is a broad closed-ended academic benchmark across math, natural
science, humanities, and expert knowledge. Legal, bio/health, finance, and
document workflows likewise require domain-specific contracts that differ from
software engineering.

The likely gaps are:

1. Routing gap: the skill may choose a coding harness for non-coding tasks.
2. Scaffolding gap: coding-agent instructions may add unnecessary process
   overhead and distract from exact-answer extraction.
3. Effort-selection gap: `xhigh` may be assumed better before proving
   it on this task family.
4. Budget gap: xhigh-style reasoning may need a larger output/reasoning buffer
   than quick smoke tests typically use.
5. Scoring-contract gap: closed-ended benchmarks need strict answer
   extraction and item-level error taxonomy, not general "good reasoning"
   prose.

## Effort Inversion Debugger

"xhigh beats medium" is not a rule. If higher effort lowers accuracy, the
correct response is not to label it as a risk and move on. The correct response
is to identify the mechanism and remove the inversion.

Run an effort sweep whenever a task family shows unexpected effort behavior:

1. Use the same model, API family, prompt, sample IDs, scorer, output token
   budget, and judge.
2. Test at least `medium`, `high`, and `xhigh`.
3. Keep the new-item-count per worker constant when tuning concurrency.
4. Record status, incomplete responses, output token usage, reasoning token
   usage where available, latency, cost, and exact-answer extraction failures.
5. Compare item-level deltas, not just aggregate accuracy.
6. Classify each error:
   - insufficient reasoning budget,
   - answer truncated before visible output,
   - answer-format mismatch,
   - over-decomposition,
   - independent options incorrectly coupled,
   - hallucinated evidence,
   - domain knowledge gap,
   - stale or wrong source assumption,
   - grader mismatch,
   - refusal/fallback/safety redirection.
7. Keep the lowest effort that wins or ties within confidence bounds after
   accounting for cost and latency.

For OpenAI `gpt-5.5`, `medium` is the documented default and balanced starting
point; `xhigh` should only be used when an eval shows a clear benefit that
justifies extra latency and cost. For Claude Fable 5, Anthropic recommends
considering all effort levels; higher effort can overplan routine tasks while
also improving verification on hard work.

## Domain Router

Fairy Tale must route by benchmark/task family before choosing a harness.

### Agentic coding and refactoring

Use the existing Fable Harness and Refactoring Similarity Harness. Keep
acceptance gates, repository evidence, tests, and small validated slices.

### Knowledge and HLE-style closed-ended tasks

Use a Knowledge Crystallization Harness:

1. classify subject and answer type,
2. isolate independent terms and answer choices,
3. write only the minimum derivation needed for the final answer,
4. force a strict answer contract,
5. run item-level error analysis across effort settings,
6. avoid broad agentic loops unless tools are part of the benchmark.

Do not use coding-agent migration prompts for HLE-style questions.

### Legal work

Use a Legal Reasoning Harness:

1. identify jurisdiction, authority type, date, procedural posture, and task
   type,
2. separate facts, issue, rule, application, conclusion, and caveats,
3. require citation or source grounding when the task permits external
   authority,
4. preserve privilege/confidentiality and avoid legal-advice overclaiming,
5. score by subtask because LegalBench-style performance can vary dramatically
   by legal task type.

LegalBench and LegalAgentBench should be treated as separate eval families:
LegalBench is broad legal reasoning, while LegalAgentBench measures practical
agent behavior with intermediate-process scoring.

### Biology, medicine, and health

Use a Bio/Health Safety Harness:

1. classify whether the task is benign explanation, clinical/health advice,
   lab protocol, molecular mechanism, dual-use biology, or hazardous content,
2. use conservative safety boundaries for protocols and actionable wet-lab
   steps,
3. separate literature-grounded facts from hypotheses,
4. require uncertainty and escalation language for medical or clinical claims,
5. record fallback/refusal behavior as part of the result.

Anthropic's Fable safeguards explicitly cover biology and life sciences, and
public reports show false positives in benign biology. Fairy Tale should not
treat biological benchmark failure as a pure reasoning failure until fallback,
safety routing, and task class are checked.

### Finance, documents, and enterprise knowledge work

Use an Evidence Table Harness:

1. extract table/chart/document facts first,
2. preserve citations, cell references, and assumptions,
3. compute expected values or reconciliations separately from prose,
4. audit every user-facing progress or result claim against an artifact.

### Spatial, UI, and 3D

Use the existing Spatial Forge Harness. Keep rendered-output validation and
separate visual plausibility from geometric, physical, and mechanical
correctness.

## Strengthening Plan

- Add the Domain Router to the main skill.
- Add Knowledge Crystallization, Legal Reasoning, Bio/Health Safety, and
  Evidence Table harnesses.
- Add the Effort Inversion Debugger to every benchmark-oriented process.
- Add eval cards that require same-sample effort sweeps before claiming
  superiority.
- Use `medium` as the default starting point for OpenAI `gpt-5.5` benchmark
  sweeps, then escalate only when the same eval slice proves benefit.

## Sources checked

- Anthropic Fable/Mythos launch:
  https://www.anthropic.com/news/claude-fable-5-mythos-5
- Anthropic Fable prompting guide:
  https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5
- Anthropic Fable product page:
  https://www.anthropic.com/claude/fable
- OpenAI GPT-5.5 model page:
  https://developers.openai.com/api/docs/models/gpt-5.5
- OpenAI reasoning models guide:
  https://developers.openai.com/api/docs/guides/reasoning
- Artificial Analysis HLE methodology:
  https://artificialanalysis.ai/evaluations/humanitys-last-exam
- Artificial Analysis Fable 5 intelligence-index note:
  https://artificialanalysis.ai/articles/claude-fable-5-mythos-intelligence-index
- Vals AI LegalBench:
  https://www.vals.ai/benchmarks/legal_bench
- HazyResearch LegalBench:
  https://github.com/HazyResearch/legalbench
- LegalAgentBench paper:
  https://aclanthology.org/2025.acl-long.116.pdf
- Endor Labs cautionary coding/security benchmark:
  https://www.endorlabs.com/learn/claude-fable-5-mythos-grade-hype
- OpenAI community lineage-bench effort anomaly report:
  https://community.openai.com/t/low-logical-reasoning-performance-of-gpt-5-2-at-medium-and-high-reasoning-effort-levels/1372853
