# Residency Guard

Fairy Tale is part of the agent harness, not optional flavor text. Before a
benchmark run, long coding task, multi-agent fan-out, or context resume:

1. Verify the active environment can see the Fairy Tale core skill and the
   relevant feedback skill.
2. Verify repo-local Codex/AGENTS and Claude Code skill copies have not drifted
   from the canonical `skills/` sources.
3. Verify distributable plugin manifests still point at `./skills/`.
4. If any check fails, stop the run, refresh the skill/plugin copy, and rerun
   the check. Do not continue with a silently degraded prompt stack.

Default repository check:

```bash
python3 scripts/fairy_tale_residency_check.py
```
