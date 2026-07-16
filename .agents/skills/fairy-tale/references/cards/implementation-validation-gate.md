# Implementation Validation Gate

- Use for any implementation task with a clear behavioral target, not only
  SWE-Bench-style coding.
- Before editing, identify the smallest existing test, command, harness,
  rendered output, smoke script, or runtime check that can expose the target
  behavior.
- Run a bounded pre-edit abstraction/clone pass over the touched concept:
  search existing helpers, types, components, policies, data objects, symbols,
  and call sites before adding another implementation. Prefer the repository's
  native structural/similarity tool; otherwise use scoped symbol/text search
  plus reviewer inspection.
- A candidate clone triggers the Refactoring Similarity Harness. Confirm
  family identity from the same owned invariant and contract, then enumerate
  that complete family across the codebase, including distant members. Do not
  stop at the neighboring files that exposed it.
- Prefer reuse when an existing abstraction owns the same concept. For a
  confirmed clone family, extract the smallest coherent shared function,
  module, type, component, policy, or data abstraction; migrate every member
  and remove superseded private paths in the same validated increment.
- Rule-of-three is a search signal, not a threshold. Two copies of one invariant
  may require consolidation; similar syntax with different ownership,
  lifecycle, failure semantics, or change cadence may remain separate only as
  evidence-backed `keep-intentionally` entries.
- Public, persisted, or compatibility-sensitive members stay in the same
  consolidation plan but use migration/deprecation rather than unsafe immediate
  deletion. Generated, vendored, forensic, migration-history, or intentionally
  mirrored members are excluded only with explicit ownership/parity evidence.
- Discovery expands to the complete confirmed family, not arbitrary cleanup.
  Do not hunt recursively through unrelated features; if inspection actually
  exposes another distinct family, give it a separate family entry and apply
  the same closure rule rather than hiding it as follow-up evidence.
- Before changing an existing public or internal contract, map the current
  call sites, visible tests, exported symbols, constructor shape, return shape,
  dependency-injection shape, and adjacent generated files/helpers. Preserve
  backward compatibility with wrappers, defaults, or narrow adapters unless the
  task explicitly deprecates the old contract.
- If no direct test exists, create a temporary or project-appropriate focused
  check before claiming the implementation is complete.
- After editing, run the focused check and at least one adjacent compatibility
  check for the touched surface when feasible.
- Repeat the abstraction/clone search after editing. Completion requires no new
  duplicate maintenance path and no unclassified member of a discovered
  family. Measure minimality by coherent semantic surface and fewer independent
  implementations, not by the fewest changed lines; subtractive diffs are
  first-class evidence.
- Include edge-case coverage for each touched surface when feasible: empty,
  nil/null, default or legacy path, boundary size, duplicate or ordering case,
  mapping/migration case, error path, and test-double/mock construction shape.
- Treat visible failing tests or harness checks as patch failures unless the
  task explicitly changes that old behavior. Preserve old behavior with a
  narrower condition instead of dismissing the red check as expected.
- Treat missing-argument errors, undefined symbols, missing modules,
  constructor/type errors, or equality invariant failures as contract breaks.
  Fix them before adding more feature logic.
- Treat tests as an oracle, not a target to repaint. Do not rewrite tests or
  fixtures just to match the patch. If tests must change, require red-green or
  external-behavior evidence, and reject tautological assertions or mocks that
  force the unit under test to succeed.
- Preserve long-horizon maintainability: avoid broad special-case chains,
  unrelated diffs, and added complexity in already large functions when the
  mapped shared abstraction can satisfy the requirement.
- Avoid dependency, lockfile, generated-output, vendored-code, and broad config
  churn unless that surface is explicitly required and validated.
- If broad validation is blocked by unrelated infrastructure, record the exact
  blocker and still run the narrowest meaningful check that exercises the
  changed behavior.
- Completion requires a validation ledger: commands/checks run, pass/fail
  result, remaining blockers, discovered-family closure or explicit
  `keep-intentionally`/migration evidence, before/after independent maintenance
  paths, and why the final design is the minimum coherent one.
