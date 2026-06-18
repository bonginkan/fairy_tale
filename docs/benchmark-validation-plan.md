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

Benchmark reporting rows must separate:

- known Fable/Mythos data from the benchmark image or primary source,
- known GPT-5.5 data from the benchmark image or primary source,
- measured GPT-5.5 data from local `without_fairy_tale` runs, when needed,
- measured GPT-5.5 + Fairy Tale data from local `fairy_tale` runs.

If the Fairy Tale result is a sample estimate, report the uncertainty next to
the score. Prefer a 95% confidence interval for proportions; when space is
tight, include the half-width as `+/-N pp`. Do not mix official known data and
local measured data in the same score cell.

Methodology alignment notes:

- HLE's official public evaluation is closed-ended: all public questions,
  temperature 0 when configurable, final answer plus confidence, automatic
  extraction/judging, and large enough output budget. Treat any Fairy Tale
  tool/skill-assisted HLE run as a separate local condition, not the official
  no-extra-tool public row.
- ExploitBench compares model agents through the upstream CLI/MCP container
  ladder and caps episodes by turns. Keep the defensive-use boundary intact and
  record AutoNudge/Codex/provider-routing differences as separate conditions.
- SWE-Bench Pro local runs should use an agent harness that can inspect, edit,
  and validate inside the benchmark container. If using Codex CLI, install the
  Fairy Tale plugin and record model, effort, sandbox, container image, and
  generated patch artifacts before official scoring.

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

1. Start with a small SWE-Bench Pro public slice because the dataset and OS
   evaluation harness are public.
2. Keep new tasks per worker constant while tuning concurrency.
3. Record pass/fail plus maintainability rubrics:
   - minimal diff,
   - correct tests,
   - no unrelated churn,
   - reproducible command log,
   - regression safety.
4. Escalate from `medium` only when the same sample proves higher effort helps.
5. Treat FrontierCode as non-runnable unless Cognition releases a public
   preview, API access, or task bundle. Its public examples may inform a
   FrontierCode-style maintainer rubric, but they must not be reported as
   FrontierCode benchmark scores.

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

ExploitBench runner readiness:

- Official repository `exploitbench/exploitbench` is public and MIT-licensed.
  Checked on 2026-06-14 JST at commit
  `11569a070683f4eb304563f919fdaee0cc17e0cf`.
- The public site reports ExploitBench as a V8 capability-ladder benchmark with
  16 mechanically graded capabilities grouped from coverage to full control.
- The upstream CLI supports `doctor`, mock smoke, one-cell benchmark filters,
  aggregation, cost caps, turn budgets, and provider routing through native or
  OpenAI-compatible APIs.
- Fairy Tale wraps the official CLI in `scripts/exploitbench_run.py`, records a
  manifest before each action, and refuses real benchmark runs unless
  `--confirm-real-run` is present.
- `--fairy-feedback` maps evaluated Fairy Tale feedback into upstream-compatible
  `stuck,wrapup` nudges instead of passing free-form instructions to the
  official harness.
- Real V8 runs may pull very large GHCR images. Start with `doctor`, mock
  smoke, and `--dry-run` single-cell commands before any paid run.

ExploitBench wrapper commands:

```text
scripts/exploitbench_run.py ensure-repo
scripts/exploitbench_run.py install
scripts/exploitbench_run.py doctor
scripts/exploitbench_run.py smoke --mock-llm
scripts/exploitbench_run.py sample-envs --sample-size 3 --seed 20260614
scripts/exploitbench_run.py benchmark --models openai/gpt-5.5 --envs v8-cve-2024-1939 --seeds 1 --turn-budget 20 --cost-cap-usd 2 --dry-run
scripts/exploitbench_run.py benchmark --models openai/gpt-5.5 --envs v8-cve-2024-1939 --seeds 1 --turn-budget 20 --cost-cap-usd 2 --docker-platform linux/amd64 --dry-run
scripts/exploitbench_run.py benchmark --models openai/gpt-5.5 --envs v8-cve-2024-1939 --seeds 1 --turn-budget 20 --cost-cap-usd 2 --docker-platform linux/amd64 --fairy-feedback --confirm-real-run
scripts/exploitbench_run.py aggregate --benchmark-id v8
```

Agentic coding readiness notes:

- SWE-Bench Pro public set is the primary runnable target for the next coding
  evaluation.
- Hugging Face dataset `ScaleAI/SWE-bench_Pro` is public and ungated; metadata
  check on 2026-06-14 JST showed revision
  `7ab5114912baf22bb098818e604c02fe7ad2c11f` with one parquet data file.
- The official OS repo is available under ignored path `tmp/swe-bench-pro-os`;
  shallow clone checked at `ca10a60a5fcae51e6948ffe1485d4153d421e6c5`.
  Official evaluation entrypoints are `swe_bench_pro_eval.py` and
  `helper_code/gather_patches.py`.
- A local ignored virtual environment exists at `tmp/swe-bench-pro-venv` with
  the official requirements installed. `swe_bench_pro_eval.py --help` and
  `helper_code/gather_patches.py --help` both run.
- HF streaming access can read at least one instance:
  `instance_NodeBB__NodeBB-04998908ba6721d64eba79ae3b65a351dcfbc5b5-vnan`,
  repo `NodeBB/NodeBB`, language `js`, docker tag
  `nodebb.nodebb-NodeBB__NodeBB-04998908ba6721d64eba79ae3b65a351dcfbc5b5`.
- `scripts/swebench_pro_prepare.py` prepares two artifacts: `raw-eval.jsonl`
  and `raw-eval.csv` for the evaluator, and `agent-tasks.jsonl` for the coding
  agent. The agent task artifact excludes gold patches, test patches,
  fail/pass scorer fields, selected test files, setup commands, and dockerfile
  fields.
- `scripts/swebench_pro_run.py` records SWE-agent instance/config generation,
  Codex CLI patch generation, compatibility patches, plan, patch-gather, and
  official-eval manifests. Use either SWE-agent or Codex CLI as the coding
  agent, then gather/evaluate after predictions are written.
- SWE-Bench Pro public Docker images are amd64. Apple Silicon can run them only
  through emulation, which is materially slower; use an x86_64 Linux machine or
  a temporary cloud VM for practical runs.
- FrontierCode has no public task bundle or preview runner as of 2026-06-14
  JST; Cognition states that tasks are not currently planned for public release
  to reduce contamination. Use the public blog examples only for qualitative
  rubric design.
- The SWE-Bench Pro adapter is tracked in `adapters/swe-bench-pro.adapter.json`.

SWE-Bench Pro wrapper commands:

```text
scripts/swebench_pro_prepare.py --sample-size 1 --seed 20260614 --output-dir tmp/swe-bench-pro-runs/prepared-smoke
scripts/swebench_pro_run.py sweagent-instances --prepared-manifest tmp/swe-bench-pro-runs/prepared-smoke/manifest.json --output tmp/swe-bench-pro-os/SWE-agent/data/fairy-smoke.yaml
scripts/swebench_pro_run.py sweagent-config --instances-path data/fairy-smoke.yaml --instances-slice :1 --output tmp/swe-bench-pro-os/SWE-agent/config/fairy_tale_swebench_pro.yaml
scripts/swebench_pro_run.py --python tmp/swe-agent-venv/bin/python sweagent-compat
scripts/swebench_pro_run.py plan --prepared-manifest tmp/swe-bench-pro-runs/prepared-smoke/manifest.json
scripts/swebench_pro_run.py codex-patches --prepared-manifest tmp/swe-bench-pro-runs/prepared-smoke/manifest.json --dry-run
scripts/swebench_pro_run.py gather --pred-dir tmp/swe-bench-pro-runs/predictions --prefix gpt-5.5-fairy-tale-codex --dry-run
scripts/swebench_pro_run.py eval --prepared-manifest tmp/swe-bench-pro-runs/prepared-smoke/manifest.json --patch-path tmp/swe-bench-pro-runs/current/patches.json --use-local-docker --dry-run
```

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
