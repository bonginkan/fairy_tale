# Fairy Tale Residency Harness

Fairy Tale must stay resident for long context, benchmark, and multi-agent
runs. If the active agent silently loses the core skill or feedback skill, the
run is not comparable to a Fairy Tale run.

## What It Checks

`scripts/fairy_tale_residency_check.py` fails closed when any required
repository integration is missing or stale:

- canonical skills under `skills/`,
- distributable plugin skills under `plugins/fairy-tale/skills/`,
- repo-local Codex/AGENTS skills under `.agents/skills/`,
- repo-local Claude Code skills under `.claude/skills/`,
- Codex and Claude Code plugin manifests pointing at `./skills/`,
- repo marketplace entries pointing at `./plugins/fairy-tale`,
- AGENTS/CLAUDE guard files mentioning the residency check,
- benchmark runners mentioning Fairy Tale and the benchmark feedback skill.

The check compares repo-local and plugin skill copies against the canonical
`skills/` source. Drift is a failure, not a warning.

## Commands

Repository preflight:

```bash
python3 scripts/fairy_tale_residency_check.py
```

Include user-level installs without failing on absent installs:

```bash
python3 scripts/fairy_tale_residency_check.py --check-installed
```

Strict local-machine preflight before a long run:

```bash
python3 scripts/fairy_tale_residency_check.py --check-installed --strict-installed
```

JSON output for CI or a wrapper harness:

```bash
python3 scripts/fairy_tale_residency_check.py --json
```

## Repair Policy

When the check fails:

1. Stop the benchmark or long agent run.
2. Sync the stale copy from `skills/` or reinstall the plugin/skill package.
3. Rerun the residency check.
4. Resume only after the check passes.

For skill-only installs, refresh from a checkout:

```bash
./install.sh --agent codex --source . --force
./install.sh --agent claude --source . --force
./install.sh --agent agents --source . --force
```

Use `--create` only when the target skills directory is intentionally new.
