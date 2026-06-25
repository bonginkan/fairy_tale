# Similarity Refactoring Adapter

Date: 2026-06-14 JST

## Scope

`kongyo2/similarity` appears useful as a refactoring amplifier for Fairy Tale.
It is not a model; it is an external TypeScript structural-similarity analyzer
that can feed an AI coding assistant with concrete duplicate-code candidates.

Repository:

- https://github.com/kongyo2/similarity

Package:

- `@kongyo2/similarity-ts`

License:

- MIT

## What it adds

The project detects structural similarity in TypeScript functions, types, and
classes. It is designed to see through renames and common style alternatives
such as function declarations versus arrow functions, promise chains versus
`async`/`await`, `forEach` versus `for-of`, template literals versus string
concatenation, interface versus type alias shapes, and similar refactoring
equivalences.

The repository reports a labeled benchmark of 71 pairs with 100% accuracy for
v0.4.0 at the default threshold. Treat that as repository-provided evidence,
not as an independently reproduced claim.

## Fairy Tale integration

The adapter is:

- `adapters/similarity-ts.adapter.json`

Use it as part of a `Refactoring Similarity Harness`:

```text
run similarity report -> cluster candidates -> inspect semantic risk
-> write refactor plan -> edit one cluster -> run tests -> repeat
```

The tool should increase refactoring quality by giving the agent a grounded
candidate list before it starts rewriting. This matches the Fable-class pattern:
use tools to gather evidence, then let the model synthesize and validate.

## Recommended process

1. Run the analyzer in JSON mode.
2. Group results by mode: functions, types, classes, overlap.
3. Drop low-value or intentionally duplicated patterns.
4. For each candidate cluster, identify behavioral invariants and public API
   boundaries.
5. Refactor one cluster at a time.
6. Run tests/typecheck after each cluster.
7. Feed false positives and missed duplicates back into a local benchmark.

## Claim boundaries

Allowed:

- It can provide high-signal refactoring candidates.
- It can reduce the scouting burden before an AI refactor.
- It can become an evaluation component for Fairy Tale refactoring workflows.

Not allowed:

- Similarity score alone proves semantic equivalence.
- A detected pair must always be merged.
- The tool alone reproduces Fable 5's refactoring performance.
