# Fairy CLI

`fairy` is the repository-level entrypoint for common Fairy Tale workflow
operations. It is a thin dispatcher: validation logic remains in the existing
scripts and Rust adapter runner, which stay directly executable.

```bash
./fairy --help
./fairy doctor
./fairy validate
```

`doctor` validates the caller repository's optional `.fairy/profile.json`,
then runs the residency check and adapter manifest validator. It continues
through all three so one failure does not hide the others. A missing profile is
a successful compatibility fallback; a malformed profile fails closed.
`validate` runs the
deterministic repository suite used by CI. Use `validate --list`, `--dry-run`,
or repeated `--only STEP` options to inspect or select registered checks.
The command exits non-zero when any selected check fails or cannot execute.
GitHub credential variables are stripped from ordinary validation subprocesses;
only the two live provenance verification steps receive them when supplied.

Task Card and Validation Ledger commands delegate to the canonical artifact
engine without copying its schemas or lifecycle rules:

```bash
./fairy task-card --help
./fairy ledger --help
./fairy ledger init --help
./fairy ledger validate --artifact validation-ledger.json
```

Fairy Fusion review and deterministic automatic-trigger decisions delegate to
the existing fusion runner:

```bash
./fairy fusion --help
./fairy fusion --auto-check --state-json state.json --output decision.json
```

The automatic check records a bounded decision and never launches reviewers or
calls a provider. See
[Fairy Fusion automatic trigger decisions](fairy-fusion-auto-trigger.md).

Workflow impact scoreboard operations also delegate to their canonical
validator. JSON remains the source of truth; Markdown is a derived view:

```bash
./fairy scoreboard validate --scoreboard examples/workflow-scoreboard.json
./fairy scoreboard summarize --scoreboard examples/workflow-scoreboard.json
```

See [Workflow Impact Scoreboard](workflow-impact-scoreboard.md).

Complexity-aware minimum-sufficient execution delegates to the E3 state
machine. It records a cheap estimate, executes the initial scope, stops on
verified success, and permits only bounded one-level expansion after failure:

```bash
./fairy e3 --help
./fairy e3 init --help
./fairy e3 validate --ledger e3-execution.json
./fairy e3 render --ledger e3-execution.json --output e3-execution.md
```

See [E3 Minimum-Sufficient Execution](e3-execution.md).

The CLI resolves repository tooling relative to its own executable, so
`validate` does not depend on the caller's current directory. `doctor` preserves
the caller directory only as the starting point for repository profile
discovery, while still resolving its validators from the Fairy Tale checkout.
Task artifact paths remain relative to the caller, matching direct
`scripts/task_artifacts.py` use. See
[Repository Fairy Profiles](fairy-profile.md).

The existing `install.sh` remains intentionally skill-only: it installs no host
executable and does not mutate `PATH`. Use `fairy` from a source checkout. This
keeps skill installation portable across Codex, Claude Code, and generic agent
homes while leaving host-level command installation explicit.
