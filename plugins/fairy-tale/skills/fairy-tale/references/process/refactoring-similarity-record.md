# Refactoring similarity record

Use this when an ordinary patch or broad refactor exposes a possible clone
family. It records family closure without creating a second excess taxonomy.

```text
target project:
change intent / touched concept:
repository-native detector or fallback search:
command/options:
raw report artifact:
family id:
owned invariant / behavioral contract:
ownership / lifecycle / failure semantics / change cadence:
complete codebase search scope:
candidate members (path + symbol + call sites):
member classification using existing Excess taxonomy:
  - consolidate in this increment:
  - deprecate-with-migration:
  - keep-intentionally + evidence:
  - generated/vendor/history/forensic/mirror exclusion + ownership/parity evidence:
unmapped-member check:
shared abstraction boundary:
migrated call sites:
superseded private paths removed:
public/persisted compatibility or migration plan:
before independent maintenance paths:
after independent maintenance paths:
behavior baseline / focused tests:
adjacent compatibility checks:
post-edit similarity/search artifact:
residual classified members:
rollback:
false-positive / false-negative note:
```
