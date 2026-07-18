# E3 Minimum-Sufficient Execution

E3 is a bounded execution-scope state machine based on the Estimate, Execute,
and Expand method described in arXiv:2607.13034. Fairy Tale implements the
method independently as a strict JSON lifecycle and a thin `fairy e3` command.

E3 reduces redundant inspection and tool use while preserving verified success.
It does not reduce the requested outcome, required validation, review breadth,
Closure Check, Tier A recall, authority checks, or safety checks.

## Activation

Activate E3 when a task:

1. requires tool-using execution;
2. has explicit executable acceptance checks;
3. has at least two plausible scope levels; and
4. can finish correctly at a narrow level if verification passes.

Examples include a localized code or configuration change, a bounded data
repair, and an operational task with a deterministic check. Do not activate E3
for plain Q&A, brainstorming, divergent generation, or independent review and
sign-off work whose frame is deliberately broad.

## State Machine

### Estimate

Record `difficulty`, `scope`, `risk`, and `confidence`. Use zero or one cheap
search/metadata probe. A contradiction between the request and probe lowers
confidence and marks the run as an expansion candidate, but the initial scope
is still executed and verified before expansion.

### Execute

Attempt zero uses the estimated scope exactly. Every attempt:

- covers all acceptance checks exactly once;
- registers every evidence reference before a check cites it;
- records raw latency, token, tool-call, and inspected-item observations;
- uses risk-scaled verification;
- carries the complete ordered evidence cache; and
- stops immediately after verified success.

### Expand

Only failed verification can create another attempt. Each expansion adds
exactly one level, retains the prior scope as a strict subset, reuses all
evidence, and stays within both the recorded cap and level 3.

## Commands

Create a ledger:

```bash
./fairy e3 init \
  --task-id fix-one-setting \
  --objective "Update one setting and verify its behavior." \
  --acceptance behavior-check="The focused behavior passes." \
  --difficulty 1 \
  --scope config/app.json \
  --risk low \
  --confidence 0.9 \
  --rationale "The target and acceptance check are explicit." \
  --output e3-execution.json \
  --markdown-output e3-execution.md
```

Record an attempt from a small JSON input:

```json
{
  "scope_additions": [],
  "new_evidence": [
    "run:focused-check"
  ],
  "cost": {
    "latency_ms": 180.0,
    "tokens": 120,
    "tool_calls": 2,
    "inspected_items": 1
  },
  "verification": {
    "tier": "local",
    "result": "pass",
    "checks": [
      {
        "id": "behavior-check",
        "result": "pass",
        "evidence": [
          "run:focused-check"
        ],
        "notes": "The focused behavior passed."
      }
    ],
    "notes": "Verified at the initial scope."
  }
}
```

```bash
./fairy e3 record \
  --ledger e3-execution.json \
  --attempt e3-attempt.json \
  --markdown-output e3-execution.md
./fairy e3 validate --ledger e3-execution.json
./fairy e3 render \
  --ledger e3-execution.json \
  --output e3-execution.md
```

The canonical schema is
[`e3-execution-ledger.schema.json`](../schemas/e3-execution-ledger.schema.json).
The routed skill contract is the
[E3 Minimum-Sufficient Execution Harness](../skills/fairy-tale/references/cards/e3-minimum-sufficient-execution-harness.md).

## ACRR

The paper defines Agent Cost Reduction Ratio as:

```text
(actual cost - minimum-sufficient cost) / minimum-sufficient cost
```

Most normal tasks have no exact minimum-sufficient oracle cost. `fairy e3`
therefore does not emit ACRR. It records raw latency, tokens, tool calls, and
inspected items for every attempt instead. A controlled evaluator may compute
ACRR outside the plugin only when successful runs and an exact oracle minimum
are independently established.

## Source And License Boundary

- Paper: Junjie Yin and Xinyu Feng, "Do AI Agents Know When a Task Is Simple?
  Toward Complexity-Aware Reasoning and Execution," arXiv:2607.13034, v1,
  2026-07-14.
- The public companion repository was checked for provenance and licensing at
  commit `44e2bfd438a39ad81e6135851f5c691c61179460`. It did not declare a
  repository license when checked on 2026-07-18.
- Fairy Tale's implementation is independently written from the paper's
  published method and does not copy companion source code.

The paper's evaluation uses a controlled simulator and an exact oracle
minimum-sufficient cost. Its reported ACRR and cost reductions are research
results, not automatic claims about ordinary Fairy Tale tasks.
