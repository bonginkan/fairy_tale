# Refactoring Similarity Harness

- Run when an implementation's pre-edit pass finds a possible clone or when a
  broad refactor needs a codebase-wide similarity map. The harness is language-
  neutral and applies to ordinary patches as well as planned cleanup.
- Use repository-native clone/structural tools first. If none exist, combine
  scoped symbol/call-site and text search with reviewer inspection; do not add a
  second detector that duplicates an established repository tool.
- Treat reports as candidates, not proof. Define a family by its owned
  invariant and behavioral contract, then compare ownership, lifecycle,
  failure semantics, and change cadence. Rule-of-three is a signal only.
- Once a family is confirmed, enumerate every codebase member before editing,
  including distant call sites. Record each candidate in the existing Excess /
  Redundancy / Legacy-Surface taxonomy; do not invent a competing removal
  taxonomy. Distance alone cannot justify `consolidate-later` for a member of
  the confirmed family.
- Choose the smallest coherent shared function, module, type, component,
  policy object, or data abstraction. Migrate all private members and remove
  superseded paths in the same increment. Public, persisted, or compatibility-
  sensitive members use an explicit migration/deprecation path in that same
  consolidation plan.
- Keep syntactic look-alikes separate only with `keep-intentionally` evidence.
  Exclude generated, vendored, migration-history, forensic, or intentionally
  mirrored distribution surfaces only with ownership/parity evidence.
- Do not turn family closure into an unrelated repository rewrite. If the
  bounded inspection actually exposes another distinct family, create a
  separate family entry and close it under the same rule.
- Refactor one family at a time. Preserve behavior with focused tests and
  compatibility checks, then repeat the similarity/search pass. Report
  before/after independent maintenance paths, migrated call sites, removed
  paths, exclusions, rollback, and residual classified members.
- For `kongyo2/similarity`, use `adapters/similarity-ts.adapter.json` and
  `references/similarity-refactoring-adapter.md` as one TypeScript adapter, not
  as the universal implementation.
