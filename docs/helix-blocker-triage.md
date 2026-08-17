# Risk-Aware Helix Blocker Triage

Use `fairy blocker` when an implementation/review Helix must decide whether a
finding blocks the current increment, can be tracked as an issue, or has been
directly refuted. The canonical JSON record is
`schemas/helix-blocker-triage.schema.json`; Markdown is a derived human
readback.

```bash
./fairy blocker validate --record examples/helix-blocker-triage.json
./fairy blocker render \
  --record examples/helix-blocker-triage.json \
  --output helix-blocker-triage.md
```

## Decision Inputs

Each finding records a concrete causal failure sequence, its preconditions,
probability, impact, fix estimate, and evidence. Risk score is
`probability_percent * impact_weight`, where the weights from negligible
through critical are 1 through 5. This score orders work; it never suppresses
the safety floor.

Only explicit owner or policy deadlines count. The record binds the deadline
to a source and computes pressure from the timezone-qualified evaluation and
deadline timestamps. Pressure begins when the recorded fix estimate plus a
24-hour review reserve reaches the time remaining at `evaluated_at`. Missing,
inferred, or already-expired deadlines do not make a finding deferrable.

Only fresh coarse usage from a primary check or session-owner observation can
create usage pressure. Fresh means observed no more than 60 minutes before the
evaluation, with primary 5-hour capacity at 15% or less or secondary weekly
capacity at 10% or less. Self-reported, stale, unknown, raw-token, billing,
credential, or provider-internal values do not grant a defer path.

## Ship Stage and the Edison Gate

Every record states the stage it is deciding for. A `production` stage records
the `production_promotion` basis and keeps the thresholds below unchanged. A
`dev_deploy` stage records an owner directive, a non-production target, or
early development as its basis, and states whether the increment's normal path
is verified against a concrete executed check.

A dev stage whose normal path is verified *and attested* earns the Edison Ship
Gate: the defer envelope widens to a residual risk score of 200 and to high
impact without measured pressure, and precautionary security hardening becomes
deferrable. An unverified normal path earns nothing — the production thresholds
stay in force. Nothing widens for a demonstrated reachable defect.

`basis_ref` and `happy_path.check_ref` are locators the implementer writes, so
the relaxation also needs `ship_stage.evidence_attestation`: the registered
reviewer — never the implementer — who confirmed that the basis names a real
authorized non-production target or directive and that the normal-path check
ran on this exact head, with the refs they checked. A missing, self-written, or
unsupported attestation leaves the production thresholds in force.

The readback carries the resulting `ship_decision`. `go` cannot carry a
retained fix-now finding, a dev `go` needs the verified normal path, and a dev
increment with a verified normal path and nothing retained cannot be held:
holding a green dev increment is the failure this gate exists to stop. Every
dev-stage deferral re-blocks at production promotion under the unrelaxed
thresholds, and the rendered readback lists that promotion debt.

A ship decision is a readiness statement, not an authority grant. `go` states
that the increment is ready for the recorded stage; it confers no deploy,
merge, or access authority and overrides neither the repository's own gates nor
the owner's standing policy. The rendered readback prints that boundary, and
the machine rejection of a green `hold` rejects diligence theatre inside the
record — never another party's authority to withhold a deploy.

## Schema Compatibility

Records persisted under schema 1.0 predate the ship stage, and 1.1 records
predate the target, claim envelope, working branch, priority holder, and clock
readings. Both upgrade through a tested path rather than expiring, 1.0 chaining
through 1.1 on the way:

```bash
./fairy blocker migrate \
  --record legacy-record.json \
  --output upgraded-record.json
```

The upgrade is faithful, not generous. Schema 1.0 decided under the unrelaxed
thresholds, so the migrated record records the production stage with an
unverified normal path and no attestation, classes unlabelled findings as
`other`, and treats an unlabelled floor finding as `demonstrated`. It cannot
hand an old record an envelope that record never earned. The result is
validated before it is written, and validating a superseded record directly
reports the upgrade path instead of a bare version mismatch.

The same rule decides what 1.2 adds. A 1.1 record never captured where the
change belonged, which sources the claim was pinned against, which branch the
effort was fixed to, who held the priority role, or what the clock read. None of
it is reconstructible, and synthesising it would forge exactly the provenance
those fields exist to carry, so the upgrade asks for it and names what is
missing rather than filling it in.

## Non-Deferrable Floor

Secret or credential exposure, data loss, production impact, authority or
permission boundaries, security, and required acceptance criteria cannot be
deferred. Each floor finding records whether a reachable failure sequence has
been `demonstrated` or is `precautionary`; only a precautionary security
finding *classed as `hardening`* at a verified, attested dev stage may be
deferred, and only with every registered reviewer concurring. A finding of any
other class carrying the security floor is a defect, and a demonstration
converts a hardening finding back to fix-now. A finding classed against the
shipped normal path is never
deferrable at any stage. A reviewer may accept a direct evidence-backed
refutation showing that the stated failure sequence does not occur; bargaining
down severity is not a refutation.

For findings outside that floor, `defer_issue` is valid only when:

- residual risk score is at most 60 (200 under the Edison gate);
- impact is negligible or low, or is medium with trusted usage/deadline
  pressure; high and critical impact remain fix-now (under the Edison gate,
  impact up to high defers and critical remains fix-now);
- at least one registered reviewer distinct from the finding reviewer concurs
  (every registered reviewer, for a deferral on the security floor);
- a same-repository GitHub issue preserves the work;
- the finding has already been included in an owner-visible human report; and
- the final readback lists every deferred blocker and the report reference.

`fix_now` is always available. Deferral is an explicit convergence choice, not
an automatic downgrade.

## Reviewer Duties

`fairy blocker validate` deterministically checks the internal consistency of
the decision record at its recorded `evaluated_at`; it does not make mutable
network calls or independently authorize a live merge. Before concurring with
a current-head defer, a reviewer must verify that:

- `evaluated_at`, usage, and deadline evidence were contemporaneous with the
  live decision;
- the ship-stage `basis_ref` resolves to a real authorized non-production
  target, owner directive, or standing policy — not a self-written label — and
  `happy_path.check_ref` names a check that ran on the recorded exact head,
  before attesting to either;
- a deferred floor finding is genuinely precautionary: no reachable failure
  sequence against the shipped surface, re-derived rather than accepted from
  the record's own rationale;
- every issue URL resolves to the recorded same-repository issue;
- every human-report locator resolves to the owner-visible report;
- related failure sequences were not split into smaller findings to evade the
  risk threshold; and
- the final readback still includes every deferred item and report locator.

Historical records remain reproducible at their recorded evaluation time.
Current exact-head reviewer sign-offs and the repository's CI/merge gates are
the live authority boundary.

## Bounded Objection

The implementer gets one on-record objection that must name
`failure_sequence` as the refuted claim and cite concrete evidence. The finding
reviewer gives one rebuttal. Acceptance ends the discussion and resolves the
item as `not_blocker`. Rejection requires one tie-break by a distinct
registered reviewer. Missing or malformed rebuttal/tie-break state remains a
blocker; it cannot become a silent pending stall.

The schema enforces closed static shapes and expressible local conditions.
Cross-object identity, role separation, risk/deadline/usage arithmetic,
objection convergence, same-repository issue binding, and exact final-readback
sets are authoritative in `fairy blocker validate`.
