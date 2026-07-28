# Implementation contract closure

The [Implementation contract closure record](../skills/fairy-tale/references/process/implementation-contract-closure-record.md)
is filled at the design-to-implementation boundary of an increment that touches
persisted state, concurrency, or client-held identity. This document describes
the gate that makes it load-bearing.

```bash
./fairy contract sample                                   # a passing skeleton
./fairy contract validate --record record.json --inventory ops.txt          # first closure
./fairy contract validate --record record.json --inventory ops.txt \
    --base previous.json                                                    # after a fix
```

## What the gate derives (rather than trusts)

- **Cross product.** The concurrency matrix is checked against every unordered
  pair of the operation inventory, self-pairs included. A hand-listed subset
  fails; the pair nobody thought of is exactly the one that becomes a late
  review round.
- **Hazard kind, not mere overlap.** Read/write intersections are candidates.
  Write/write hazards may be `serialized`, `commutative` (with commutativity
  evidence and a test per application order) or `disjoint_keyspace` (with
  differing partition predicates). Read/write hazards may additionally be a
  `read_only_snapshot` (with a consistency / generation / staleness contract).
  Safe overlaps are never forced into needless serialization.
- **Impossibility is a system property.** `single_writer_invariant`, `lock`,
  `state_machine_exclusion`, `lifecycle_exclusion` — timing arguments and UI
  flow are not admissible, and a disjoint keyspace is a safe overlap, not an
  impossibility.
- **Serialization means shared, and it is derived.** The named object must be
  a declared identity that BOTH operations have in their reads AND writes; the
  record cannot attest to it with a boolean. A hazard-free pair may not declare
  itself serialized either — needless serialization is a defect, not caution.
- **The canonical inventory is external, named, and in-tree.** The record cites
  a path and a sha256; the gate requires the file actually supplied to be that
  path, to live inside the repository, and to hash to the declared value. A
  substituted or out-of-tree inventory is rejected, so the artifact that
  defines coverage is reviewed in the same diff as the record. The artifact is
  parsed fail-closed: non-UTF-8, empty, duplicated or malformed ids are RED
  before any hash comparison.
- **Lineage is immutable and explicit.** A revision declares the exact_base it
  supersedes; the supplied base must be at that revision, from the same repo
  and increment, strictly older, and its contract surface must actually differ.
  A backdated copy of the current record is not a predecessor.
- **Shape before semantics, with no install step.** The CLI evaluates the
  shipped schema itself — a clean checkout runs the gate with no third-party
  dependency — so a record the schema rejects never reaches the semantic pass.
  CI additionally cross-checks that evaluator against `jsonschema`, so the two
  cannot diverge. Timestamps must be timezone-qualified: a naive value is
  rejected rather than silently assumed to be UTC.
- **Uncertainty is a column.** Every externally visible write states success,
  failure and UNKNOWN behaviour, what the peer observes, who reclaims the
  residue, and how that residue is discoverable.
- **Re-closure is a diff.** With `fix_reclosure`, the record is compared to its
  previous version — identities, operations, read/write sets, failure/UNKNOWN
  behaviour, dispositions, serialization points and platform invariants — and
  every cell reachable from that change must carry re-validation newer than the
  fix, with evidence. The change surface cannot be under-declared because it is
  not declared at all.

## Limits, stated rather than hidden

- `disjoint_keyspace` is checked structurally (same identity, differing
  predicates, evidence present). Proving predicate disjointness semantically
  stays a reviewer judgement.
- The canonical operation inventory is authored, not derived from the code by
  this gate. Coverage is enforced both ways against an in-tree, named,
  hash-bound artifact, so trimming it is a reviewable change in the same diff —
  but a reviewer, not the gate, is what notices that the artifact still matches
  the code surface.
- Platform invariants are enumerated and sourced by the author. A rule nobody
  knows about is not caught by this gate; it is caught by review or by
  production.
