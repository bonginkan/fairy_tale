# Benchmark Validation Plan

Date: 2026-06-14 JST

## Goal

Measure whether Fairy Tale improves practical benchmark performance when used as
a workflow-augmentation layer on top of the same base model.

Do not publish result claims until they are stable, reproducible, and positive.
Failed or mixed pilot runs are debugging evidence, not project results.

## Priority order

The current priority is:

1. cybersecurity,
2. agentic coding,
3. legal,
4. bio/health,
5. HLE and broad knowledge work later.

This order reflects immediate product needs. It also avoids treating HLE as the
default proxy for all Fairy Tale value.

Published baseline shortcut:

- Omit local `without_fairy_tale` reruns only when the benchmark image or a
  primary source already has a comparable GPT-5.5 baseline for that benchmark.
- Run `without_fairy_tale` locally when GPT-5.5 is absent, the benchmark version
  changed, the scorer must be calibrated, or the published GPT-5.5 number is not
  comparable to the local run setup.

## Comparison contract

Every direct comparison must use:

- same model,
- same API path,
- same reasoning effort,
- same sample IDs,
- same max output budget,
- same wall-clock and tool budget,
- same scorer,
- same retry policy,
- same safety policy.

Conditions:

- `baseline`: base model without Fairy Tale process guidance.
- `fairy_tale`: same model plus Fairy Tale domain router, harness, and
  validation gates.

When a comparable GPT-5.5 published baseline exists, the local run only needs
the `fairy_tale` condition. Record the public source and exact GPT-5.5 score
used as the baseline.

Minimum recorded fields:

- domain,
- benchmark/source,
- sample IDs,
- prompt template version,
- model and effort,
- cost and latency,
- pass/fail or rubric score,
- item-level deltas,
- truncation/refusal/fallback events,
- scorer version,
- artifact paths.

## Domain cards

### Cybersecurity

Primary official benchmark candidate:

- ExploitBench / v8-bench.

Reason to handle carefully:

- ExploitBench measures an exploitation ladder, from reaching vulnerable code to
  exploit primitives and code execution.
- Fairy Tale's security workflow is defensive-only, so optimizing directly for
  offensive capability is not the same as improving security utility.

Plan:

1. Start with a defensive cyber triage pilot:
   - OWASP Web / OWASP LLM vulnerability review,
   - safe evidence,
   - patch-first remediation,
   - regression tests,
   - detection coverage,
   - root-cause deduplication.
2. Score with rubric criteria, not exploit payload success.
3. Treat official ExploitBench as a separate sandboxed safety review. Run it
   only if the objective is explicitly to measure exploit-ladder capability in
   its own isolated benchmark environment.

Success metric:

- Increased defensive finding quality, lower false positives, better patch/test
  coverage, and no unsafe exploit detail.

### Agentic coding

Primary candidates:

- SWE-Bench Pro public set,
- Terminal-Bench,
- FrontierCode as a reference benchmark if runnable access is unavailable.

Plan:

1. Start with a small Terminal-Bench or SWE-Bench Pro slice.
2. Keep new tasks per worker constant while tuning concurrency.
3. Record pass/fail plus maintainability rubrics:
   - minimal diff,
   - correct tests,
   - no unrelated churn,
   - reproducible command log,
   - regression safety.
4. Escalate from `medium` only when the same sample proves higher effort helps.

Success metric:

- Higher task pass rate or equal pass rate with lower cost/latency, while
  preserving maintainability and test evidence.

### Legal

Primary candidates:

- Harvey Legal Agent Benchmark (LAB),
- LegalAgentBench,
- LegalBench for smaller exact-answer legal subtasks.

Plan:

1. Use Harvey LAB-style long-horizon legal tasks when accessible because the
   structure mirrors real legal work product: matter files, instructions, and
   expert rubric criteria.
2. Use LegalAgentBench where Chinese legal-agent tool use is acceptable for the
   experiment.
3. Use LegalBench for low-cost pilot subsets and scorer calibration.

Success metric:

- Higher rubric completion, better citation/evidence grounding, fewer missed
  hard stops, and lower hallucinated authority.

### Bio/Health

Primary candidates:

- HealthBench,
- BioMysteryBench preview and full set if access is granted.

Plan:

1. Use HealthBench for realistic health conversations and physician-written
   rubric scoring.
2. Use BioMysteryBench preview for bioinformatics workflow pilots.
3. Separate safety routing from capability:
   - clinical advice boundaries,
   - wet-lab or dual-use boundaries,
   - uncertainty handling,
   - evidence-grounded answer quality.

Success metric:

- Higher rubric score with conservative safety behavior preserved. For
  BioMysteryBench, score against the answer rubric and record whether required
  data files and allowed domains were used correctly.

## Pilot ladder

### Stage 0: readiness

- Generate harness plan.
- Fix local hygiene gates.
- Confirm benchmark dataset access.
- Confirm API key availability without printing secrets.
- Record source licenses and terms.

Current readiness notes:

- Hugging Face CLI is available and authenticated.
- BioMysteryBench preview is accessible. Dry-run shows `problems.csv`,
  `problems.parquet`, and `data.zip` (~11.4 MB).
- BioMysteryBench rubrics contain expected answers, so runners must keep rubrics
  out of model prompts and use them only for scoring.
- GitHub access is available for Harvey LAB, SWE-Bench Pro OS, ExploitBench,
  Terminal-Bench, and OpenAI simple-evals.
- Docker is available for containerized coding or security benchmarks.
- Harness Designer baseline cycle passes repository profile, hygiene,
  maintainability, Rust, and AI I/O checks; only production-readiness remains
  red because this research/plugin repo has no CI workflow yet.

BioMysteryBench preview runner:

```text
scripts/biomystery_runner.py prepare
scripts/biomystery_runner.py list
scripts/biomystery_runner.py run --ids all --condition baseline --dry-run --output tmp/biomystery-runs/dry-run-baseline.jsonl
scripts/biomystery_runner.py run --ids hb053 --condition fairy_tale --model gpt-5.5 --preview-bytes 70000 --output tmp/biomystery-runs/smoke-fairy-tale-hb053.jsonl
scripts/biomystery_runner.py score --predictions tmp/biomystery-runs/smoke-fairy-tale-hb053.jsonl
```

The runner is dependency-light and uses only Python standard library modules.
It calls the OpenAI Responses API directly when `OPENAI_API_KEY` is set.

### Stage 1: smoke

- 3 to 5 samples per urgent domain.
- `baseline` vs `fairy_tale`.
- One worker first; then tune concurrency with constant new items per worker.
- Use `medium` effort first unless benchmark official methodology requires
  otherwise.

### Stage 2: pilot

- 20 to 40 samples per domain.
- Run effort sweep only if smoke indicates meaningful variance.
- Track item-level deltas.
- Do not write public Results yet.

### Stage 3: confirmation

- Larger slice or official benchmark subset.
- Freeze prompt/template/scorer versions.
- Re-run baseline and Fairy Tale under identical conditions.
- Publish result only if the improvement is stable and explainable.

## Sources

- OpenAI evaluation best practices:
  https://developers.openai.com/api/docs/guides/evaluation-best-practices
- SWE-Bench Pro public dataset:
  https://labs.scale.com/leaderboard/swe_bench_pro_public
- SWE-Bench Pro OS repo:
  https://github.com/scaleapi/SWE-bench_Pro-os
- Terminal-Bench:
  https://github.com/harbor-framework/terminal-bench
- FrontierCode:
  https://cognition.ai/blog/frontier-code
- ExploitBench:
  https://exploitbench.ai/
- ExploitBench repo:
  https://github.com/exploitbench/exploitbench
- Harvey Legal Agent Benchmark:
  https://www.harvey.ai/blog/introducing-harveys-legal-agent-benchmark
- Harvey LAB repo:
  https://github.com/harveyai/harvey-labs
- LegalAgentBench:
  https://github.com/CSHaitao/LegalAgentBench
- HealthBench:
  https://openai.com/index/healthbench/
- OpenAI simple-evals HealthBench implementation:
  https://github.com/openai/simple-evals
- BioMysteryBench preview:
  https://huggingface.co/datasets/Anthropic/BioMysteryBench-preview
