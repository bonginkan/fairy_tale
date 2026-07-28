# Implementation contract closure record

Use this before writing implementation code for an increment that touches
persisted state, concurrency, or client-held identity. A design agreement that
fixes the happy path and a hand-listed subset of races is not a closed
contract: the unlisted cells come back as single findings, one review round
each, and each local patch adds state that opens the next cell.

Fill every cell before implementing. A blank cell is the finding you have not
received yet. The record is machine-checked — the gate, not the prose, is what
closes it:

```bash
./fairy contract validate --record <record.json> \
    --inventory <canonical-operations.txt> [--base <previous-record.json>]
```

The validator derives closure instead of trusting it: it generates the cross
product of the operation inventory, decides admissible dispositions from each
pair's hazard kind, resolves a serialization point to an identity BOTH sides
read and write, DERIVES the operation set from the code surface using the
PROJECT's own discovery config (`.fairy/contract-surface.json`, not anything
the record declares) and compares it both ways with the record, so neither
trimming the record nor narrowing its scope can hide a handler that exists,
and — with the project's lineage ledger deciding whether this is an initial
record or a revision — diffs a revision against the last accepted record it
must supersede (named by path, hash and exact_base, strictly older, contract
surface actually different) to compute what the change re-opened. There is no field in which a record
can declare itself closed, and no boolean it can assert about itself.

```text
increment / exact base:            (record: `./fairy contract sample` prints a passing skeleton)
operation inventory (derived from the route/command/event surface, not recalled):
platform invariants relied on (transaction read/write ordering, pagination
  defaults, framework state-update semantics, ...) + where each is verified:

A. identity and state machine — one row per identity, persisted AND client-held
   identity | owner | states | transitions (trigger) | who may clear it |
   what binds it to a generation

B. failure and uncertainty matrix — one row per externally visible write
   write | success | failure | UNKNOWN (response loss, partial commit) |
   what the peer observes in each | who reclaims the residue |
   how that residue is discoverable

C. concurrency matrix — the CROSS PRODUCT of the operations in the inventory
   op x op | can overlap? | shared serialization point (named object both
   sides read AND write) | loser's outcome | both commit orders tested

closure statement:
  operation inventory derived, not recalled:
  every B and C cell filled; impossible cells carry a reason:
  every serialization point is one shared object, not a timing argument:
blocking unresolved cells:
```

Rules that make the record load-bearing:

- Implementation does not start while a B or C cell is blank. "We will find
  that in review" is the failure this record exists to prevent.
- An impossible cell states the property that makes it impossible. "The UI
  never issues both" is not a property of the system; a lock, a state machine,
  or a single-writer invariant is.
- A serialization point is a document, row, or lock that BOTH sides read and
  write. Two writers that create different new objects share nothing and both
  commit.
- Client-held identity is in scope. Draft keys, editor generations, in-flight
  request ownership, and "which composer does this response belong to" are
  contract, not implementation detail.
- Every uncertainty cell names a reclaimer AND how the residue is found. A
  reclaimer that scans only records cannot find bytes whose record never
  landed; a bounded scan without a cursor never reaches past its first page.

Re-closure after a fix (this is where round count is actually spent): when a
fix introduces new state, a new identity, a new status, or a new stored intent,
that state re-opens every A row and B/C cell it touches. Re-close those cells
and cover them with tests before requesting re-review — repairing only the
reported symptom is what turns one finding into a chain of them.
