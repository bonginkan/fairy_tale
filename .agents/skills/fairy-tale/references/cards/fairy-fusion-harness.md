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
- In plugin-managed harnesses, record a trigger decision when the same
  normalized failure signature repeats at least three times, a required
  validation ledger is missing, an expected artifact is empty or meaningless,
  independent reviews conflict, or a user/operator explicitly requests fusion.
  The generic automatic check is decision-only: it must not launch reviewers,
  call a provider, or retry work. Apply the caller's approval/provider policy
  before any separate reviewer execution.
- For a repeated failure signature, a missing validation ledger, or an empty or
  meaningless artifact, a `trigger` is not a stop. Under that same policy the
  caller runs the bounded review this card already defines — isolated
  reviewers, one synthesis pass, append-only artifacts — returns only the
  compact hint to the main agent, and the main agent keeps control and
  continues under its existing clear and stop conditions. Those are the
  reasons an existing integration already handles this way when its retry and
  execution policy enables it; a caller outside that integration follows the
  same sequence under its own. The automatic check still only decides.
- An explicit request needs no redirection rule: the request is its own
  grounds, and the caller invokes review directly. A conflict between
  independent reviews is the one reason with no established handling to reach,
  so it stays with the caller's own policy instead of being routed by default.
- Record the trigger reasons, reviewer cap, recursion depth and cap, intended
  review artifact path, and input identity. Default automatic recursion to one
  level; a trigger condition at depth 1 or greater is blocked rather than
  recursively reviewed.
- For coding tasks, use SWE specialist roles before retrying: interface
  reviewer, regression reviewer, validation reviewer, and minimality reviewer.
- Keep fan-out capped. A human may launch a separate review under a different
  policy, but must not mutate the automatic decision's one-level recursion
  contract.
