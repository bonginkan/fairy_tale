# Cybersecurity Strengthening Plan

Date: 2026-06-14 JST

## Scope

This note strengthens Fairy Tale's defensive cybersecurity workflow. It is a
defense-only translation of public Mythos/Fable/Project Glasswing reports and
security best practices. It does not attempt to reproduce offensive capability,
weaponization, stealth, persistence, credential theft, or bypass guidance.

## Source synthesis

Official Anthropic Project Glasswing materials describe frontier models that can
read large codebases, find vulnerabilities, and reason about exploitability.
Anthropic's initial update emphasizes that the software industry must prepare
for a larger volume of AI-generated findings. Cloudflare's field report frames
frontier security models as tools for finding vulnerabilities in one's own
systems and for understanding what future attackers may be able to do. Rapid7
emphasizes that model capability is not enough: reducing real risk requires
business context, remediation, fix validation, and detection coverage.

The practical Fairy Tale translation is:

1. Operate only on authorized systems.
2. Prioritize defensive triage and patching over exploit detail.
3. Convert model findings into reproducible but non-weaponized evidence.
4. Validate fixes and detection coverage before closing.
5. Manage volume, duplicates, false positives, and business impact.

## Cyber Frontier Defense Harness

Use this harness for authorized code audit, vulnerability triage, secure
refactoring, incident-readiness review, dependency risk review, and defensive
validation.

1. **Authorize and scope**
   - Identify owner, repo/system, allowed targets, forbidden targets, and data
     sensitivity.
   - Define whether the task is static review, dynamic validation, threat
     modeling, patch planning, or detection engineering.

2. **Build an asset and trust-boundary map**
   - Entry points, authn/authz, tenant boundaries, data stores, external APIs,
     background jobs, queues, secrets, and privileged actions.
   - Mark untrusted data paths separately from trusted policy/config sources.

3. **Classify risk**
   - Use a vulnerability taxonomy appropriate to the system: OWASP Web,
     OWASP LLM, cloud/IAM, supply chain, tenant isolation, data privacy,
     secrets handling, business logic, and AI agent/tool risk.
   - For LLM applications, explicitly check prompt injection, sensitive
     information disclosure, supply-chain/model dependency risk, data/model
     poisoning, insecure output handling, excessive agency, system prompt
     leakage, vector/embedding weakness, misinformation, and unbounded
     consumption.

4. **Evidence before severity**
   - Record file/path/component, preconditions, affected data/action, trust
     boundary crossed, likely impact, and why existing controls fail.
   - Keep reproduction safe: no public exploit steps, no credential extraction,
     no real target abuse, no persistence, no stealth.

5. **Patch-first planning**
   - Provide minimal code/config changes, tests, migration notes, and rollback.
   - Prefer removing entire vulnerability classes over local string filters.
   - For agentic systems, separate model suggestion from server-side authority.

6. **Validation and detection coverage**
   - Add unit/integration/regression tests.
   - Add audit logs, alerts, dashboards, and incident-response hooks where
     relevant.
   - Confirm that the fix blocks the class of issue, not only the example.

7. **Triage load management**
   - Deduplicate findings by root cause.
   - Separate confirmed, likely, speculative, and informational findings.
   - Sort by reachable impact and remediation leverage, not only model
     confidence.
   - Keep false-positive and non-exploitable notes for later benchmark tuning.

## ExploitBench Evaluation Boundary

ExploitBench is useful as a controlled measurement of exploit-ladder capability,
but it is not the default output style for Fairy Tale cybersecurity work. The
default cybersecurity workflow remains defensive triage, patching, validation,
and detection coverage.

Use `scripts/exploitbench_run.py` only when the objective is benchmark
measurement inside the official ExploitBench sandbox:

1. Confirm the target is the official upstream checkout and official V8
   container environment.
2. Run `doctor` and `smoke --mock-llm` before any paid or long-running run.
3. Start with one `(model, env, seed)` cell and a short turn budget.
4. Keep `cost_cap_usd`, `turn_budget`, `max_parallel`, model id, seed, and nudge
   policy in the manifest.
5. Aggregate results through the official CLI before reporting any score.

Do not convert ExploitBench transcripts into real-target exploit instructions.
Treat capability data as defensive preparedness evidence: which capability tier
was reached, where the model stalled, and which secure-development or
monitoring controls should be prioritized.

## Output contract

For defensive work, output should include:

- scope and assumptions,
- asset/trust-boundary map,
- finding matrix,
- evidence and confidence,
- patch recommendation,
- validation tests,
- detection/monitoring follow-up,
- owner and rollout notes.

Avoid:

- exploit weaponization,
- step-by-step compromise instructions,
- persistence or stealth,
- credential theft,
- live-target instructions outside authorization,
- bypassing safeguards or access controls.

## Sources checked

- Anthropic Project Glasswing:
  https://www.anthropic.com/glasswing
- Anthropic Project Glasswing initial update:
  https://www.anthropic.com/research/glasswing-initial-update
- Anthropic expanding Project Glasswing:
  https://www.anthropic.com/news/expanding-project-glasswing
- Anthropic Fable/Mythos system card:
  https://www-cdn.anthropic.com/d00db56fa754a1b115b6dd7cb2e3c342ee809620.pdf
- Cloudflare Project Glasswing field report:
  https://blog.cloudflare.com/cyber-frontier-models/
- Rapid7 Project Glasswing note:
  https://www.rapid7.com/blog/post/ai-rapid7-accesses-anthropics-project-glasswing-exploring-frontier-artificial-cybersecurity-intelligence/
- OWASP Top 10 for LLM Applications:
  https://owasp.org/www-project-top-10-for-large-language-model-applications/
- OWASP GenAI Security Project:
  https://genai.owasp.org/llm-top-10/
- SEC cybersecurity incident disclosure guide:
  https://www.sec.gov/resources-small-businesses/small-business-compliance-guides/cybersecurity-risk-management-strategy-governance-incident-disclosure
- ExploitBench site:
  https://exploitbench.ai/
- ExploitBench repository:
  https://github.com/exploitbench/exploitbench
