# Cyber Frontier Defense Harness

- Use only for authorized defensive work.
- Start with scope, asset map, trust boundaries, entry points, privileged
  actions, tenant/data boundaries, secrets, queues, external APIs, and model/tool
  authority.
- Classify findings by OWASP Web, OWASP LLM, cloud/IAM, supply chain, tenant
  isolation, data privacy, secrets handling, business logic, and agent/tool
  risks.
- For LLM apps, explicitly check prompt injection, sensitive information
  disclosure, insecure output handling, excessive agency, system prompt leakage,
  vector/embedding weakness, data/model poisoning, and unbounded consumption.
- Require non-weaponized evidence before severity: affected component,
  preconditions, trust boundary crossed, impacted data/action, and why existing
  controls fail.
- Prefer patch-first output: minimal change, tests, detection coverage, rollout,
  and owner notes.
- Deduplicate by root cause and separate confirmed, likely, speculative, and
  informational findings.

