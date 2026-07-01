# General E2E Completion Harness

- Use this when driving an end-to-end test of a real deployed system to
  completion: not "ran once and it rendered," but "every surface that exists was
  exercised, its boundaries probed, failures tracked, and the environment left
  clean." Domain-agnostic (web or voice, custom-auth or OAuth).
- Apply the eight gates from `references/general-e2e-completion.md`:
  reachability without stopping at the auth wall (mint the session from the
  system's own signing secret, raw bytes, never recording the value); closure-
  check the test inventory against the actual code/deploy surfaces; presence is
  not exercise (mutation/auth/stateful surfaces need a create->read-back->delete
  round-trip); the entailed boundary-companion battery (auth_reject, authz_rbac,
  idor_impersonation, visibility_scope, idempotency, allowlist_boundary); real
  backend with stateful continuity, no mocks; RED -> reproduced and tracked;
  residue zero with legible evidence, production untouched; and **GUI present ->
  GUI dogfood is mandatory** (any rendered surface needs a browser dogfood pass,
  console-checked and repro-graded, or a tracked-outstanding gap -- see
  `references/gui-dogfood-qa.md`).
- Record each run against `schemas/e2e-coverage-ledger.schema.json` and validate
  with `scripts/e2e_coverage_check.py` (fails closed on uncovered discovered
  surfaces, render-only mutation surfaces, missing companions, untracked REDs,
  nonzero residue, mocked backend, relaxed safety floor, a leaked secret, or a GUI
  system without a dogfood pass -- a missing `gui` block, a `route`/`panel`/`flow`
  surface declared `has_gui:false`, a performed dogfood lacking a console check /
  taxonomy / browser-artifact evidence or with fewer tracked REDs than issues_found,
  or an outstanding dogfood without a tracker).
  This is the Closure Check and entailed-companion (Tier-A) discipline applied to
  e2e scope; run it as a double-helix (execution strand drives surfaces, review
  strand refutes coverage).

