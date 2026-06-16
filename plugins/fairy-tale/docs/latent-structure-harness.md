# Latent Structure Harness

The Latent Structure Harness is a domain-neutral scaffold for tasks where the
visible prompt is not enough. It targets hidden rules, implicit contracts,
black-box environments, ambiguous specs, benchmark misses, and generalization
gaps across coding, ARC-style puzzle discovery, legal work, research, UI,
spatial tasks, and other domains.

It is not a benchmark-specific gate. The core ledger does not know answer keys,
hidden tests, ARC task ids, SWE-Bench instance ids, or legal rubric labels.
Domain wrappers may consume the ledger, but the ledger itself only records what
the agent observed, what it tried, what failed, what invariant it inferred, and
what validation supports promotion of that invariant.

## When To Use It

Use this harness when any of these are true:

- The task likely depends on an unstated repository, product, legal, interface,
  or game-world contract.
- The model is passing local visible checks while failing hidden or held-out
  behavior.
- The environment is partly black-box and requires probes or replay.
- A prior benchmark miss shows local consistency but poor generalization.
- The agent is about to apply an analogy from a familiar domain to an
  unfamiliar one.

## Ledger Sections

The ledger schema is `schemas/latent-structure-ledger.schema.json`.

- `observations`: facts with source and confidence.
- `negative_evidence`: failed, no-op, or absent-pattern evidence that blocks a
  tempting but false rule.
- `hypotheses`: candidate latent rules.
- `inferred_invariants`: rules promoted far enough to constrain action.
- `risky_assumptions`: assumptions with risk and resolution state.
- `probes_run`: controlled probes, searches, replays, or other attempts to test
  the rule.
- `compiled_validators`: executable tests, replay scripts, checklists, or other
  validators.
- `actions`: edits or outputs that depend on promoted invariants.
- `validation_results`: post-action evidence.
- `promotion_decision`: whether the rule remains a candidate, is promoted, or
  is rejected.

## CLI

Create an empty ledger:

```bash
python3 scripts/latent_structure_harness.py init \
  --task "preserve an implicit repository contract" \
  --task-family coding \
  --trigger implicit_contract \
  --risk medium \
  --output tmp/latent-structure-ledger.json
```

Create a complete demo ledger:

```bash
python3 scripts/latent_structure_harness.py demo \
  --output tmp/latent-structure-demo.json
```

Validate before action:

```bash
python3 scripts/latent_structure_harness.py validate \
  --ledger tmp/latent-structure-ledger.json \
  --stage pre-act
```

Validate before final answer or promotion:

```bash
python3 scripts/latent_structure_harness.py validate \
  --ledger tmp/latent-structure-ledger.json \
  --stage final
```

Print a compact summary:

```bash
python3 scripts/latent_structure_harness.py summarize \
  --ledger tmp/latent-structure-ledger.json \
  --json
```

## Gate Semantics

The `pre-act` gate is meant to stop local-pattern overfitting before an agent
edits, answers, or commits to a plan. It requires at least one observation, one
hypothesis or inferred invariant, and a probe or planned validator for
medium/high-risk tasks or latent-structure triggers. Open high-risk assumptions
fail this gate.

The `final` gate is stricter. It requires inferred invariants with evidence,
completed probes when the task calls for them, passed validators or explicit
validation results, no unresolved medium/high-risk assumptions, and a promotion
decision with a reason and evidence when promoted.

The harness can still pass with warnings when negative evidence is absent. That
warning is intentional: some domains have limited probe access, but agents
should still see the gap instead of silently hardening a lucky pattern.

## Domain Use

- Coding: preserve adjacent interfaces, mocks, migrations, and legacy behavior
  that the prompt did not spell out.
- ARC-style tasks: record object grammar, hidden state, no-op moves, and replay
  probes before compiling a search or planner.
- Legal and policy work: distinguish explicit text from inferred intent,
  conflicting authority, and accepted assumptions.
- Research: separate observed data, failed hypotheses, and promoted mechanisms.
- UI and spatial work: turn screenshots, geometry, camera, and interaction
  observations into scoped invariants before making broad changes.

## Non-Goals

- It does not score a benchmark by itself.
- It does not prove final correctness.
- It does not replace official tests, hidden validation, user clarification, or
  domain-specific tooling.
- It does not encode benchmark-specific answer keys or shortcuts.
