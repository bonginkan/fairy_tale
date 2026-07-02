# Effort Inversion Debugger

- Do not assume higher effort is better. If `xhigh` or max effort underperforms
  `medium` or `high`, identify and remove the cause before continuing.
- Sweep effort on the same model, API path, sample IDs, prompt, scorer,
  `max_output_tokens`, and judge.
- Keep new items per worker constant when tuning concurrency.
- Record latency, cost, incomplete responses, visible answer extraction,
  reasoning token usage when available, fallback/refusal events, and item-level
  deltas.
- Classify failures as insufficient budget, answer truncation, format mismatch,
  over-decomposition, incorrectly coupled independent terms, hallucinated
  evidence, domain gap, stale source assumption, or grader mismatch.
- Use the lowest effort that wins or ties within confidence bounds after cost
  and latency are considered.

