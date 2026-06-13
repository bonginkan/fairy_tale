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
- `docs/oss-watch.md`
- `skills/fairy-tale/SKILL.md`

