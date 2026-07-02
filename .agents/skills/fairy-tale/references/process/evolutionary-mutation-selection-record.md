# Evolutionary mutation / selection record

Use this when a spiral revolution should evolve a bounded variant rather than
just climb: a controlled mutation of process, prompt, harness, validator, role
assignment, or delegation policy, selected on evidence and inherited only when
validated. It is grounded in biological evolution (variation, selection,
inheritance, lineage) and Holland's genetic-algorithm framing. Record the
variant in `evolution-variants/<id>.json` against the evolution-variant ledger
schema; `scripts/evolution_variant_check.py` validates it for content so a
presence-only or vibes-only variant fails.

The operators: a mutation budget bounds what may and may not change (the safety
floor is never changeable); evidence-driven selection accepts only variants with
concrete evidence, a preserved safety floor, and a measurable improvement or risk
burn-down; validated inheritance carries only accepted variants into the next
template while unvalidated mutations die locally; lineage keeps every variant
traceable; and extinction/quarantine red-locks harmful variants so they cannot
silently reappear.

```text
loop / thread:
variant id:
parent revolution:
mutation operator: process | prompt | harness | validator | role_assignment | delegation_policy
hypothesis:
mutation budget - changeable:
mutation budget - immutable:
mutation budget - blast radius:
fitness metric:
selection - outcome: accepted | rejected | quarantined
selection - baseline comparison:
selection - safety floor preserved:
selection - evidence:
inheritance - inherited:
inheritance - template change:
inheritance - rationale:
rollback plan:
extinction / quarantine:
lineage:
safety floor:
ledger / receipt:
reviews:
```

Operating rules:

- Declare the mutation budget before mutating. No variant runs without
  changeable, immutable, and blast-radius declared, and no safety-floor surface
  may appear as changeable — that is forbidden, not a variant.
- Select on evidence, not assertion. Acceptance needs concrete selection
  evidence and a measurable improvement or risk burn-down over an explicit
  baseline; "looks good" is rejected.
- Inherit only validated change. An accepted variant may update the governance
  template; rejected or quarantined variants stay local and are not replicated.
- Keep lineage and extinction explicit and auditable. Each harmful pattern is
  red-locked in the checker self-test so it cannot return silently.
- The safety floor is invariant under mutation. DND, approval, security,
  credential, deploy, external-mutation, meeting-join, owner-escalation,
  branch/merge, secret, and runtime-install gates outrank any variant.

