# Refactoring Similarity Harness

- Run structural similarity tools before broad refactors when the target is a
  TypeScript codebase.
- Treat reports as candidate clusters: functions, types, classes, and partial
  overlap.
- Convert each cluster into a refactor plan with invariants, call sites, tests,
  and rollback notes.
- Refactor one cluster at a time and validate after each slice.
- For `kongyo2/similarity`, use `adapters/similarity-ts.adapter.json` and
  `references/similarity-refactoring-adapter.md`.

