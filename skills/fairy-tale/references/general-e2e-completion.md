# General E2E Completion

The discipline for driving an end-to-end test of a real system to *completion* —
not "ran it once and it rendered," but "every surface that exists was exercised,
its boundaries probed, failures tracked, and the environment left clean." This is
the e2e layer on the helix arc (Loop → Spiral → Double-Helix → Evolution): the
loop runs the checks, the spiral raises rigor, the double-helix pairs execution
with refutation, and this card says what "done" actually means.

It is distilled from running a real product e2e to completion and is **domain-
agnostic**: it applies to any deployed app/service, web or voice, custom-auth or
OAuth. Record each run against `schemas/e2e-coverage-ledger.schema.json` and
validate with `scripts/e2e_coverage_check.py` (the gate is exercise, not presence).

## The seven gates

1. **Reachability without stopping at the auth wall.** When an interactive login
   (OAuth consent, SSO) blocks a headless run, do not stop — derive the post-auth
   credential from the system's *own* signing primitive (mint the session/JWT/HMAC
   cookie from the same secret the server verifies with). Read the secret as **raw
   bytes**: a shell `$(...)` capture silently strips a trailing newline, so a
   45-byte secret becomes 44 and every signature mismatches (401). This never
   relaxes the safety floor — auth/authz are still enforced; you are standing in a
   real user's shoes, not disabling the check. **Never record the secret value**;
   the ledger describes *how*, never the value.

2. **Closure-check the test inventory itself.** A provided test sheet/list is not
   proof of scope — it is one party's view, and it omits. Enumerate the **actual**
   surfaces from code and deployment (routes, panels, endpoints, actions, jobs) and
   diff against the provided list. Every discovered surface must be covered; a
   surface present in code but absent from the inventory is the finding (Negative-
   Space Closure Check applied to e2e: "shown N" is never silently "only N").

3. **Presence ≠ exercise.** A surface that renders is not a surface that works. For
   any mutation / auth / stateful surface, do the **round-trip**: create → read it
   back from the real store → delete, with evidence of how the data registered and
   how it displayed. A screenshot of an empty panel proves nothing. Read-only
   surfaces may pass on presence; everything else must be exercised.

4. **Boundary-companion battery (entailed companions).** A mutation/auth surface
   *entails* its security boundaries; testing the happy path alone is incomplete by
   construction. The battery: **auth_reject** (missing/forged credential → 401),
   **authz_rbac** (wrong role → 403), **idor_impersonation** (cannot act as another
   user), **visibility_scope** (private data not leaked to a lower role),
   **idempotency** (replay → no duplicate), **allowlist_boundary** (disallowed
   tenant/workspace → 403). Each is evidenced or explicitly N/A with a reason.

5. **Real backend, no mocks; stateful continuity.** Hit the deployed system and
   verify real store/state effects by reading them back — a run that mocks the
   system under test is not a completion. For conversational/sequential surfaces,
   exercise the *continuation* (turn 2 appends to the same thread; it does not start
   a new one), not a single one-shot request. (The same "no mock / real call"
   principle independent voice-e2e harnesses arrive at: drive the production model,
   never a simulator.)

6. **RED → tracked, with a reproduction.** A real failure is not "noted" — it is
   reproduced concretely (the exact request/steps/observed result) and filed to a
   tracker (issue/PR). You cannot report completion over an untracked failure.

7. **Residue zero + legible evidence.** Delete every test artifact and verify the
   environment is clean (re-query → 0). Production/main is never touched. Evidence
   must be human-readable — split long screenshots into legible slices, embed them
   with the report, and keep the raw API read-backs.

## How it connects

- The closure-check is the **Closure Check / Negative-Space** card (`process.md`)
  pointed at e2e scope; the boundary battery is the **entailed companion** (Tier-A)
  set for an endpoint. Presence-vs-exercise is the e2e form of checking that a
  control is *exercised*, not merely *present*.
- Run it as a double-helix: the execution strand drives the surfaces; the review
  strand refutes coverage ("which surface or assertion is missing?"). Accumulate
  reusable oracles (the battery, the mint recipe) across apps via the ledger.

## Output contract

One ledger record per run (`e2e-coverage/NNNN-<target>.json`). The gate
(`scripts/e2e_coverage_check.py`) fails closed on: a discovered surface missing
from coverage, a mutation/auth/stateful surface marked present-but-not-exercised, a
missing/unjustified boundary companion, a RED without a repro+tracker, nonzero
residue, a mocked backend, a relaxed safety floor, or any raw secret/token pasted
into the ledger. Reviews follow the same 2-distinct-reviewer / refute-pass contract
as the spiral and evolution ledgers.
