# fairy_tale

Private research workspace for distilling reported Fable/Mythos-class agent
behavior into reproducible agent skills and plugin packages.

This repository does not attempt to bypass access controls, export controls, or
model safeguards. It studies public official information and public user reports
to extract reusable workflows that can be run with Codex, Claude Code, or other
agent-skill-compatible coding assistants.

## Goals

- Describe the strongest reported Fable 5 / Mythos 5 capabilities in operational terms.
- Convert those capabilities into repeatable agent workflows.
- Package the workflow as:
  - a generic Agent Skill under `skills/fairy-tale/`
  - a Codex repo skill under `.agents/skills/fairy-tale/`
  - a Claude Code project skill under `.claude/skills/fairy-tale/`
  - a distributable Codex plugin under `plugins/fairy-tale/`
- Track OSS pioneers and reusable ideas without importing unsafe behavior.

## Current status

Initial scaffold and research synthesis.

## Important boundaries

- Security workflows are defensive-only.
- No exploit weaponization, persistence, stealth, credential theft, or bypass guidance.
- Use budgets and validation gates before launching parallel agents.
- Treat user reports as anecdotal unless independently reproduced.
- Preserve provenance for all research claims.

## Primary docs

- `docs/research-summary.md`
- `docs/arc-agi-3-lab-analysis.md`
- `docs/openmythos-external-adapter.md`
- `docs/similarity-refactoring-adapter.md`
- `docs/oss-watch.md`
- `skills/fairy-tale/SKILL.md`
- `crates/fairy-adapter-runner/`

## Referenced GitHub repositories

These repositories informed the current skill, adapter, and plugin architecture.
They remain external sources unless explicitly vendored or forked. Licenses and
ownership remain with each upstream project.

- `openai/skills` - reference point for portable agent skill structure.
  https://github.com/openai/skills
- `ComposioHQ/awesome-claude-skills` - Claude skill ecosystem examples.
  https://github.com/ComposioHQ/awesome-claude-skills
- `composiohq/awesome-codex-skills` - Codex skill ecosystem examples.
  https://github.com/composiohq/awesome-codex-skills
- `VoltAgent/awesome-agent-skills` - broader agent-skill curation.
  https://github.com/VoltAgent/awesome-agent-skills
- `VoltAgent/awesome-claude-code-subagents` - subagent workflow references.
  https://github.com/VoltAgent/awesome-claude-code-subagents
- `disler/claude-code-hooks-mastery` - Claude Code hooks workflow references.
  https://github.com/disler/claude-code-hooks-mastery
- `Anil-matcha/awesome-claude-fable-5` - curated public Fable 5 reports and demos.
  https://github.com/Anil-matcha/awesome-claude-fable-5
- `kyegomez/OpenMythos` - external theoretical reconstruction substrate.
  https://github.com/kyegomez/OpenMythos
- `bonginkan/OpenMythos` - pinned fork for future external-adapter experiments.
  https://github.com/bonginkan/OpenMythos
- `kongyo2/similarity` - TypeScript structural similarity/refactoring scout.
  https://github.com/kongyo2/similarity
