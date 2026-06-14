# fairy_tale

Private research workspace for distilling reported Fable/Mythos-class agent
behavior into reproducible agent skills and plugin packages.

Think of this project as the nightingale's scorebook.

In Andersen's tale, the court becomes enchanted by a jeweled mechanical bird,
only to learn that the living song matters more than the glittering machine.
Fairy Tale does not try to steal the bird, open the cage, or pretend to be the
emperor's locksmith. It listens to public traces of unusually good agent work,
separates melody from myth, and writes down the repeatable patterns as skills,
checks, adapters, and sample results.

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
  - a distributable Claude Code plugin under `plugins/fairy-tale/`
- Track OSS pioneers and reusable ideas without importing unsafe behavior.

## Current status

The first songbook is usable:

- Fairy Tale skills are packaged for generic agents, Codex, and Claude Code.
- The plugin package supports Codex and Claude Code manifests.
- Research notes, defensive security constraints, best-practice gates, OSS watch
  notes, adapter plans, and sample comparison outputs are checked in.
- The project is still private while the melodies are tuned against controlled
  evaluations.

## Important boundaries

- Security workflows are defensive-only.
- No exploit weaponization, persistence, stealth, credential theft, or bypass guidance.
- Use budgets and validation gates before launching parallel agents.
- Treat user reports as anecdotal unless independently reproduced.
- Preserve provenance for all research claims.

## Primary docs

- `docs/research-summary.md`
- `docs/domain-gap-analysis.md`
- `docs/cybersecurity-strengthening.md`
- `docs/arc-agi-3-lab-analysis.md`
- `docs/best-practices.md`
- `docs/openmythos-external-adapter.md`
- `docs/similarity-refactoring-adapter.md`
- `docs/oss-watch.md`
- `skills/fairy-tale/SKILL.md`
- `crates/fairy-adapter-runner/`

## Claude Code plugin

This repo includes a Claude Code marketplace catalog at
`.claude-plugin/marketplace.json`. In Claude Code, add the local marketplace and
install the plugin:

```text
/plugin marketplace add .
/plugin install fairy-tale@fairy-tale-marketplace
```

The same `plugins/fairy-tale/` package also remains a Codex plugin via
`plugins/fairy-tale/.codex-plugin/plugin.json`.

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
- `ossf/scorecard` - future OSS repository security-health reference.
  https://github.com/ossf/scorecard
