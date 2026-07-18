# E3 Execution Record

Use the machine ledger for execution. This record is a planning and handoff
prompt, not a second source of truth.

```text
Task id:
Objective:
Acceptance checks:
- <id>: <executable outcome>

Initial operating point:
- difficulty: 1 | 2 | 3
- scope:
- risk: low | medium | high
- confidence: 0.0-1.0
- rationale:
- cheap probe: none | search | metadata
- probe query:
- probe evidence:
- low-confidence expansion candidate: true | false
- max expansions:

Non-suppressible safety floor:
- validation plan preserved:
- Closure Check / Tier A preserved:
- authority and safety preserved:
- repository profile / user scope preserved:

Attempt 0:
- level:
- scope:
- reused evidence:
- new evidence:
- raw cost: latency_ms / tokens / tool_calls / inspected_items
- verification tier: local | focused | full
- acceptance results:
- result: pass | fail | blocked
- notes:

Expansion attempt, only after failed verification:
- one-level increase:
- prior scope retained:
- complete evidence cache reused:
- new scope additions:
- new evidence:
- verification:

Terminal status: verified | blocked | exhausted
Summary:

Controlled evaluation note:
- `fairy e3` does not emit ACRR.
- Compute it externally only when success and an exact minimum-sufficient
  oracle cost are independently established.
```
