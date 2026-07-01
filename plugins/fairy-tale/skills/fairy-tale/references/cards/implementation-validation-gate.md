# Implementation Validation Gate

- Use for any implementation task with a clear behavioral target, not only
  SWE-Bench-style coding.
- Before editing, identify the smallest existing test, command, harness,
  rendered output, smoke script, or runtime check that can expose the target
  behavior.
- Before changing an existing public or internal contract, map the current
  call sites, visible tests, exported symbols, constructor shape, return shape,
  dependency-injection shape, and adjacent generated files/helpers. Preserve
  backward compatibility with wrappers, defaults, or narrow adapters unless the
  task explicitly deprecates the old contract.
- If no direct test exists, create a temporary or project-appropriate focused
  check before claiming the implementation is complete.
- After editing, run the focused check and at least one adjacent compatibility
  check for the touched surface when feasible.
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
- Preserve long-horizon maintainability: avoid duplicated logic, broad
  special-case chains, large unrelated diffs, and added complexity in already
  large functions when a small local abstraction or wrapper can satisfy the
  requirement.
- Avoid dependency, lockfile, generated-output, vendored-code, and broad config
  churn unless that surface is explicitly required and validated.
- If broad validation is blocked by unrelated infrastructure, record the exact
  blocker and still run the narrowest meaningful check that exercises the
  changed behavior.
- Completion requires a validation ledger: commands/checks run, pass/fail
  result, remaining blockers, and why the final diff is minimal.

