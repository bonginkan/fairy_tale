# Implementation contract closure

The [Implementation contract closure record](../skills/fairy-tale/references/process/implementation-contract-closure-record.md)
is filled at the design-to-implementation boundary of an increment that touches
persisted state, concurrency, or client-held identity. This document describes
the gate that makes it load-bearing.

```bash
./fairy contract sample                                   # a passing skeleton
./fairy contract validate --record record.json            # first closure
./fairy contract validate --record record.json --base previous.json   # after a fix
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
- **Serialization means shared.** A serialized pair names one object that both
  sides read AND write. Two writers creating different new documents share
  nothing and both commit.
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
- The canonical operation inventory is supplied by the record author; the gate
  enforces both-way coverage against it, but cannot know that the supplied
  inventory itself is complete.
- Platform invariants are enumerated and sourced by the author. A rule nobody
  knows about is not caught by this gate; it is caught by review or by
  production.
