# Workflow Impact Scoreboard

The workflow impact scoreboard records whether Fairy Tale improved a benchmark
or an ordinary coding, research, review, or documentation task, and what the
improvement cost. Canonical data is JSON under
`schemas/workflow-impact-scoreboard.schema.json`; Markdown is a derived review
view.

## Commands

```bash
./fairy scoreboard validate --scoreboard examples/workflow-scoreboard.json
./fairy scoreboard summarize --scoreboard examples/workflow-scoreboard.json
./fairy scoreboard summarize --scoreboard examples/workflow-scoreboard.json --output scoreboard.md
python3 scripts/workflow_scoreboard.py validate --scoreboard examples/workflow-scoreboard.json
python3 scripts/workflow_scoreboard.py summarize --scoreboard examples/workflow-scoreboard.json
python3 scripts/workflow_scoreboard.py selftest
```

`fairy scoreboard` is the source-checkout convenience entrypoint. The direct
script commands remain portable in the packaged reference bundle.

`summarize` excludes `source_kind=example` by default. Add
`--include-examples` only when reviewing the schema demonstration. The command
rejects an output path that aliases the input scoreboard and writes a requested
Markdown view atomically.

## Committed Sample

`examples/workflow-scoreboard.json` contains three entries:

- an illustrative paired benchmark,
- an illustrative paired normal task, and
- the measured but unpaired 2026-07-02 routing evaluation.

The four small files under `examples/workflow-scoreboard/` are immutable
example run artifacts. Their `example: true` marker, condition, task kind, exact
path, and SHA-256 are checked rather than trusted from the scoreboard label.
The measured routing entry binds to the existing ledger and appears in the
default Markdown view; the two illustrative pairs appear only with
`--include-examples`.

## Comparison Contract

A paired entry records one `baseline` run and one `fairy_tale` run under one
comparison contract. Keep these conditions identical unless the changed field
is the treatment being measured:

- model and effort,
- prompt and scorer versions,
- sample IDs,
- output, wall-clock, and tool budgets,
- retry policy, and
- safety policy.

Use a fresh session for each case. The baseline disables Fairy Tale; the
treated condition enables it. Record pass count, total count, score, elapsed
seconds, cost, and all token components. This follows the official Claude Code
skill evaluation guidance checked on 2026-07-17: run realistic cases in
isolation with and without the skill, then compare pass rate, duration, and
tokens. `paired_external_baseline` is allowed only when the baseline is an
identified official source. An `unpaired` entry is evidence, but cannot claim
uplift or regression against an absent condition.

## Evidence Identity

Every run binds to an artifact path and SHA-256. Repository artifacts must use
an exact, portable repository-relative path and must exist under that name.
Private or local artifacts use a non-sensitive `redacted/...` locator and a
hash; never publish an absolute host path. Missing cost, elapsed, score, budget,
or token data requires a specific unavailability reason.

Artifact provenance is an explicit registry binding, not a run label. Every
artifact names one `source_ref`; the referenced source records an evidence kind
and the same immutable artifact path and SHA-256. `official_external` requires
an `official_run` source with an HTTPS official locator, `measured_local`
requires `measured_run`, and examples require `example_run`. Context citations
cannot be reused as run evidence. Reviewers still assess whether a declared
official locator is authoritative; the machine gate guarantees that the run,
locator, and immutable artifact cannot silently drift apart.

Example runs are also bound in both directions: `source_kind=example` requires
artifact kind `example` and a matching `example: true` repository payload,
while either example declaration prevents relabeling as measured or official
evidence. They never enter measured aggregates by default.

Nested input types fail closed with field-qualified validation errors before
enum membership, duplicate detection, arithmetic, path handling, or binding
lookup is attempted.

Each Fairy Tale run may record per-card telemetry:

- canonical card path relative to `skills/fairy-tale/`,
- fire count,
- helpful / neutral / harmful / unknown contribution,
- attributed tokens or a reason attribution is unavailable, and
- evidence references.

Baseline runs cannot claim Fairy Tale card utilization. Contribution is not
inferred from a fire count.

## Routing Ledger Binding

`routing_eval_bindings` makes the scoreboard a parity gate for the routing
evaluator. For each binding, validation recomputes and compares:

- pass and total counts,
- accuracy,
- aggregate cost,
- all token totals, and
- the complete per-card utilization map.

Routing ledgers are identified by explicit artifact kind
`routing_eval_ledger` and stable `results` / `summary` routing structure, never
by a filename, directory prefix, or by the presence of fields whose absence
must fail. The declaration and content signature are checked in both
directions. Every run with either identity requires exactly one binding,
including byte-identical mirrors or renamed copies. The ledger must provide a
non-empty model, lowercase 64-hex skill/system/case SHA-256 identities, a
pinned lowercase repository commit, valid routing rows, and a matching summary
before any aggregate is accepted. Generic `model` and `repo_commit` metadata
and execution metadata such as `run_policy` and `token_note` are not routing
class signals, alone or together. Classification requires a complete routing
signature in at least two of three independent groups (digest, row, summary);
an ordinary benchmark payload remains a `run_output`.

The committed sample consumes
`docs/skill-budget/routing-eval-20260702.json`. That legacy run is measured but
unpaired and has no elapsed field, so the scoreboard records both limits
instead of manufacturing a comparison.

## Governance

Use measured paired entries when promoting or pruning feedback. An example,
unpaired run, or unknown card contribution can motivate another measurement,
but cannot establish benefit. A regression note is required for every run,
including an explicit `unknown` when no valid comparison exists. See
[Feedback Governance](feedback-governance.md) and the
[Benchmark Validation Plan](benchmark-validation-plan.md).

The Markdown review view shows the bound source identity and locator and
preserves each run's regression status and note, validation evidence, and
complete card path / fire count / contribution / token attribution / evidence
references. A positive comparison delta is never rendered without the
governance evidence needed to evaluate harm or prune a card.

## Sources

- Claude Code skills, official documentation, checked 2026-07-17:
  https://code.claude.com/docs/en/skills
- Repository benchmark comparison contract:
  `docs/benchmark-validation-plan.md`
- Repository feedback promotion and pruning contract:
  `docs/feedback-governance.md`
