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
- 3D/game stacks: prefer established engines and renderers such as Three.js,
  native GPU frameworks, or CAD APIs; validate rendered frames instead of
  trusting generated code.

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
