# Fairy Tale Best-Practice Reference

Use this reference when updating the skill, plugin, adapters, eval harnesses,
or public-release surface.

## Source hierarchy

1. Official product documentation and official upstream repositories.
2. Local reproducible evidence from this repository or adapters.
3. Maintained public OSS examples.
4. Public user reports and demos.

Do not turn a user report into a capability claim unless there is a reproduction
artifact, negative-case record, and boundary note.

## Domain routing

- Fill a domain router card before benchmark-style work.
- Use the Fable Harness for software-shaped work only.
- Use Knowledge Crystallization for closed-ended expert or HLE-style tasks.
- Use Legal Reasoning for legal redlines, legal summaries, and legal
  benchmarks.
- Use Bio/Health Safety for biology, medicine, chemistry-adjacent, and health
  tasks.
- Use Evidence Table for finance, spreadsheets, charts, tables, and documents.
- Require controlled evidence before making capability claims.

## Effort selection

- Do not assume maximum effort wins.
- Sweep `medium`, `high`, and `xhigh` or provider-equivalent settings on the
  same sample before choosing.
- Keep model, API path, prompt, scorer, sample IDs, judge, and output budget
  fixed.
- Keep new items per worker constant when tuning concurrency.
- If higher effort underperforms, diagnose the cause and fix it.
- Use the lowest effort that wins or ties within confidence bounds after cost
  and latency are considered.

## Evaluation

- Every claimed process advantage needs an eval card.
- Record baseline process, candidate process, task family, budget, tools,
  memory, cost, elapsed time, validation artifacts, and negative cases.
- Preserve false positives, false negatives, timeouts, refusals, fallbacks,
  hallucinated validation, answer-format failures, and incomplete responses.
- Treat failures as structured feedback: classify failure modes, add a narrow
  harness rule, and re-run a held-out retry set before promoting the rule.

## Fairy Fusion review

- Use Fairy Fusion review only when the cost of being wrong exceeds the cost of
  extra independent reviewer passes.
- Keep reviewers independent and task-scoped; each reviewer gets all required
  context and a narrow output schema.
- Synthesize by consensus, contradictions, partial coverage, unique insights,
  and blind spots rather than majority vote.
- Cap panel size, tool calls, recursion depth, and budget before launch.
- Do not send confidential matter files to external providers without explicit
  authorization.
- Use `scripts/fairy_fusion_review.py` or the equivalent harness-native
  independent reviewer contract; do not route through OpenRouter unless a
  future adapter explicitly adds that integration and the user authorizes it.
- Label internal runs as Fairy Fusion or fusion-style review, not OpenRouter
  Fusion.

## Tool and adapter contracts

- Each adapter must state source, license, entrypoints, input/output contract,
  evidence artifacts, validation checks, safety boundaries, and forbidden
  claims.
- Prefer Rust orchestration for Fairy Tale-owned validation.
- Keep Python or other external runtimes behind adapter boundaries when
  upstream projects require them.
- Do not vendor speculative reconstructions without an explicit license and
  claim-boundary review.

## Context and memory

- Keep always-loaded skill text short.
- Move long evidence and benchmark logs into topic files.
- Leave recovery handles for long runs: objective, state, touched artifacts,
  validation status, open risks, and next safe action.
- Context compaction is not validation.

## OSS readiness

- Choose a root license before public release.
- Add or finalize `SECURITY.md`, `CONTRIBUTING.md`, release notes, and
  third-party acknowledgements.
- Keep private claims separate from public reproducible workflows.
- Run dependency and repository-health checks before publication.
