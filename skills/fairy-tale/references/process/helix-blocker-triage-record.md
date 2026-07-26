# Helix blocker triage record

Use this at an implementation/review decision point when findings need
risk-aware priority, issue-only deferral, or a bounded implementer objection.
Create the strict JSON record described by the source-checkout blocker triage
document and validate it with:

```bash
./fairy blocker validate --record <record.json>
```

```text
loop:
  repo / artifact / exact head / evaluated_at:
  implementer / two reviewers:
  explicit deadline / source / source ref:
  coarse usage / freshness / trusted source ref:
blockers:
  id / summary:
  failure sequence / preconditions:
  probability / impact / risk rationale:
  protected floor:
  fix estimate / evidence:
  finding reviewer / finding ref:
  objection / rebuttal / tie-break:
  disposition / priority / concurrence:
  issue / human report:
final readback:
  deferred / retained / not-blocker ids:
  human report ref:
```

The machine validator owns the decision semantics. Safety-floor findings
(secret/credential, data loss, production, authority/permission, security, and
required acceptance) are never deferrable. A defer decision needs low residual
risk, reviewer concurrence, a canonical issue, and an owner-visible final
report. An implementer may directly refute the failure sequence once; the
finding reviewer responds once, and a distinct reviewer tie-breaks rejection.
Unresolved discussion remains fail-closed.
