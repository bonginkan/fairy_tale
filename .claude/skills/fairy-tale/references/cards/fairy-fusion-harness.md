# Fairy Fusion Harness

- Choose the fusion mode before running reviewers.
- Use `--blind-panel` when the goal is general answer quality, hidden
  contradiction discovery, or robustness against a single reasoning path. Send
  the same task context to each isolated panelist; do not invent personas or
  specialized lenses.
- Use specialist review when the weakness is already classified, such as legal
  one-miss failures, calculation/form completion, domain-specific omissions, or
  security boundary review.
- Synthesis must preserve consensus, contradictions, partial coverage, unique
  insights, blind spots, rejected items, cost, latency, and closure actions.
- Do not majority-vote away a minority risk. Promote a fused answer only after
  the synthesis has resolved or explicitly carried forward the contradiction.
- Treat fusion reviewers as isolated sidechains: pass only the task context,
  visible artifacts, role contract, and output schema. Keep full reviewer
  outputs as append-only artifacts, then return only a compact synthesis hint to
  the main agent.
- In plugin-managed harnesses, enable automatic fusion when the same failure
  signature repeats at least three times, an implementation attempt produces no
  meaningful diff, or the validation ledger is missing. Continue automatic
  retries until local clear conditions are met or the user/operator stops the
  run; keep every retry auditable with append-only artifacts.
- For coding tasks, use SWE specialist roles before retrying: interface
  reviewer, regression reviewer, validation reviewer, and minimality reviewer.
- Keep fan-out capped and recursion one-level unless a human explicitly
  approves more.

