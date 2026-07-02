# Benchmark Delta Harness

- Identify which benchmark capability is being targeted: agentic coding,
  legal, knowledge work, vision, long-memory, scientific reasoning, defensive
  cyber, health, biology, finance/document analysis, or multimodal UI/3D.
- Recreate the enabling conditions, not the headline score: task budget,
  effort level, context strategy, tools, fallback behavior, memory, validation,
  and elapsed-time allowance.
- Use a baseline model/process on the same task when possible.
- Measure deltas with artifacts: pass/fail tests, rendered screenshots,
  benchmark rubrics, human review notes, cost, and elapsed time.
- Use controlled eval artifacts before claiming Fable/Mythos-informed workflow
  uplift.
- Report benchmark rows with separate cells for known Fable/Mythos data, known
  or measured GPT-5.5 data, and measured GPT-5.5 + Fairy Tale data.
- If the Fairy Tale result is a sample estimate, include the confidence
  interval or a `+/-N pp` half-width next to the score.
- Never present a FrontierCode-style maintainer rubric as a FrontierCode score.
- For SWE-Bench Pro work, use `scripts/swebench_pro_prepare.py` to create
  prompt-safe agent tasks and `scripts/swebench_pro_run.py` to gather patches
  and invoke the official scorer with provenance manifests.
- For ExploitBench work, use `scripts/exploitbench_run.py` against the official
  upstream sandbox only. Run `doctor`, mock smoke, and dry-run single-cell
  commands before any confirmed real benchmark run. Use `--fairy-feedback` to
  map Fairy Tale feedback into upstream-compatible `stuck,wrapup` nudges.

