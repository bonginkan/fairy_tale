# Implementation contract closure

The [Implementation contract closure record](../skills/fairy-tale/references/process/implementation-contract-closure-record.md)
is filled at the design-to-implementation boundary of an increment that touches
persisted state, concurrency, or client-held identity. This document describes
the gate that makes it load-bearing.

```bash
./fairy contract sample                                   # a passing skeleton
# The integration branch belongs to the project, so read it FROM the project;
# the trusted base must BE the merge base with it:
INTEGRATION_REF=$(python3 -c 'import json; print(json.load(open(".fairy/contract-surface.json"))["integration_ref"])')
BASE=$(git merge-base "$INTEGRATION_REF" HEAD)

./fairy contract validate --record record.json --inventory ops.txt \
    --trusted-base "$BASE"                          # first closure
./fairy contract validate --record record.json --inventory ops.txt \
    --trusted-base "$BASE" --base previous.json     # after a fix
```

`--integration-ref` may be passed, but only to restate what the authority
already says: a different value is a finding, not a choice. Omitting it means
the authority's `integration_ref` is used.

From an **extracted release package**, gate another project by pointing the
same command at that project — its authority, its code surface and its tracked
inventory are what get read:

```bash
python3 <extracted>/scripts/implementation_contract_closure.py validate \
    --repo-root /path/to/project --record /path/to/project/record.json \
    --inventory /path/to/project/docs/operations.txt --trusted-base "$BASE"
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
- **The authority files are a boundary, not a name.** `.fairy/contract-surface.json`
  and `.fairy/contract-closure-lineage.json` are resolved by exact path
  component (no case alias), refused if any component is a symlink or resolves
  outside the repository, and parsed fail-closed — a root array, a missing key
  or a wrong-typed field is a finding, never silent disablement. Their bytes must also match the SAME files read from an
  immutable Git object (`--trusted-base <rev>`), which must resolve to a commit
  that is an ancestor of HEAD and not HEAD itself — a working tree cannot vouch
  for itself, and `--trusted-base .` is not a revision. Narrowing the surface or
  rewriting lineage therefore has to land as its own reviewed change first.
- **The operation set is derived from the code, by the PROJECT.** The globs and
  pattern live in `.fairy/contract-surface.json`, which the gate reads itself —
  a record cannot declare, narrow or redirect its own discovery scope. The walk
  is in-process (no command from any file is executed), refuses absolute globs,
  `..` segments and symlinks that resolve outside the repository, and accepts
  only captures shaped like an operation id, so file content is never reflected
  into a finding.
- **The cited inventory artifact is external, named, and in-tree.** The record cites
  a path and a sha256; the gate requires the file actually supplied to be that
  path, to live inside the repository, and to hash to the declared value. A
  substituted or out-of-tree inventory is rejected, so the artifact that
  defines coverage is reviewed in the same diff as the record. The artifact is
  parsed fail-closed: non-UTF-8, empty, duplicated or malformed ids are RED
  before any hash comparison.
- **Initial and revision are decided by the project, not the record.**
  `.fairy/contract-closure-lineage.json` lists the accepted records per
  increment: `initial` is legal only while that list is empty, a revision must
  supersede the LAST accepted record by sha256 and exact_base, and
  `base_record_ref` must be the file actually diffed. A changed record cannot
  relabel itself initial, and a synthetic predecessor is not lineage.
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
- Discovery is only as good as the project's own globs and pattern. The gate
  proves the record matches what they find, refuses a pattern that finds
  nothing, and confines the walk to the repository — but a handler outside the
  project's declared surface is invisible to it. Those globs live in a
  repository-owned file so that narrowing them is a reviewed change to the
  project, not a private choice inside a record.
- The lineage ledger is a repository file. It removes self-declared lineage,
  but a repository with write access to itself can still rewrite its own
  history; that edit is a reviewable diff, not something the gate can prevent.
- Platform invariants are enumerated and sourced by the author. A rule nobody
  knows about is not caught by this gate; it is caught by review or by
  production.
