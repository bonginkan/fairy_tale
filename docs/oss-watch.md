# OSS Watch

This file tracks public projects and ecosystems relevant to reproducible
Fable/Mythos-class workflows.

## Agent skill ecosystems

- OpenAI Codex Agent Skills:
  - https://developers.openai.com/codex/skills
  - https://github.com/openai/skills
- Claude Agent Skills:
  - https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
  - https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- Awesome Claude Skills:
  - https://github.com/ComposioHQ/awesome-claude-skills
- Awesome Codex Skills:
  - https://github.com/composiohq/awesome-codex-skills
- Awesome Agent Skills:
  - https://github.com/VoltAgent/awesome-agent-skills

## Claude Code workflow components

- Claude Code subagents:
  - https://code.claude.com/docs/en/sub-agents
  - https://github.com/VoltAgent/awesome-claude-code-subagents
- Claude Code hooks:
  - https://code.claude.com/docs/en/hooks
  - https://github.com/disler/claude-code-hooks-mastery
- Claude Code skills and command compatibility:
  - https://code.claude.com/docs/en/slash-commands

## Relevant open-source workflow themes

Useful ideas to borrow:

- Progressive disclosure: load only the skill and references needed for the task.
- Subagent role separation: scouts gather and summarize; the main agent decides.
- Hooks for safety: enforce validation, budget checks, and write guards.
- Skill bundles: package repeatable workflows as portable `SKILL.md` directories.
- MCP integration: connect tools and data sources through explicit contracts.
- Evaluation harnesses: preserve prompts, artifacts, cost, elapsed time, and
  failure modes for benchmark-like comparison.
- Defensive security triage: convert model-discovered issues into authorized
  scope, safe evidence, patch plans, regression tests, detection coverage, and
  responsible disclosure artifacts.
- Domain routers: choose a task-family harness before prompting, especially for
  legal, bio/health, finance/document, and HLE-style closed-ended work.
- Effort sweeps: treat medium/high/xhigh or provider-equivalent effort levels
  as eval variables; diagnose inversions item by item instead of assuming max
  effort wins.
- 3D/game stacks: prefer established engines and renderers such as Three.js,
  native GPU frameworks, or CAD APIs; validate rendered frames instead of
  trusting generated code.
- External reconstruction adapters: keep speculative architecture projects
  outside the core repo and connect them through manifests, pinned commits, and
  evidence records.

## External reconstruction projects

- OpenMythos:
  - upstream: https://github.com/kyegomez/OpenMythos
  - fork: https://github.com/bonginkan/OpenMythos
  - role: public theoretical RDT/looped-transformer substrate for controlled
    probes, not proof of Anthropic internals.

## Refactoring and similarity tools

- kongyo2/similarity:
  - https://github.com/kongyo2/similarity
  - package: `@kongyo2/similarity-ts`
  - role: TypeScript structural-similarity detector for generating grounded
    refactoring candidates before an AI coding assistant rewrites code.
  - caveat: reports are candidates, not proof of semantic equivalence.

## Cross-vendor agent loops

- DanMcInerney/architect-loop:
  - https://github.com/DanMcInerney/architect-loop
  - role: separates Claude Fable-style architect/reviewer behavior from
    GPT-5.5 Codex builder/researcher behavior, with specs and gates written
    before builder execution.
  - useful idea: freeze acceptance gates before fan-out and keep builder edits
    away from the gate definitions.
  - caveat: do not copy worktree-discard assumptions into environments where
    the operator forbids worktrees.

## Legal and knowledge benchmarks

- HazyResearch LegalBench:
  - https://github.com/HazyResearch/legalbench
  - role: broad legal-reasoning benchmark with many legal task families.
- LegalAgentBench:
  - https://aclanthology.org/2025.acl-long.116.pdf
  - role: practical legal-agent benchmark with intermediate process signals.
- Center for AI Safety HLE:
  - dataset: https://huggingface.co/datasets/cais/hle
  - repo: https://github.com/centerforaisafety/hle
  - role: broad closed-ended academic benchmark across math, science,
    humanities, and other expert domains.

## Defensive security references

- OWASP Top 10 for LLM Applications:
  - https://owasp.org/www-project-top-10-for-large-language-model-applications/
  - role: LLM app security taxonomy for prompt injection, output handling,
    sensitive disclosure, excessive agency, and related risks.
- OWASP GenAI Security Project:
  - https://genai.owasp.org/llm-top-10/
  - role: updated GenAI security risk references.
- Project Glasswing:
  - https://www.anthropic.com/glasswing
  - role: official frontier defensive cyber collaboration reference.
- Cloudflare Project Glasswing report:
  - https://blog.cloudflare.com/cyber-frontier-models/
  - role: field report on using frontier security models against owned
    infrastructure.
- Rapid7 Project Glasswing note:
  - https://www.rapid7.com/blog/post/ai-rapid7-accesses-anthropics-project-glasswing-exploring-frontier-artificial-cybersecurity-intelligence/
  - role: operational reminder that vulnerability finding must be followed by
    context, remediation, validation, and detection coverage.

## Fable-specific public curation

- Awesome Claude Fable 5:
  - https://github.com/Anil-matcha/awesome-claude-fable-5
  - Useful as a source index for demos, benchmark evidence, limits, and 3D
    reports.
  - Treat as a curated secondary source; follow links to original demos before
    using any claim as evidence.

Avoid importing:

- Unbounded autonomous fan-out.
- Untrusted skills that execute network or filesystem operations without review.
- Offensive security procedures.
- Skills that hide side effects behind vague instructions.
