# Fairy Tale Sample Use Case: generalization_tacit_contract

Date: 2026-06-16

## Status

This is a designed evaluation use case, not a measured benchmark result.
Use it to test whether Fairy Tale's generalization harness improves transfer
from local observations to reusable invariants. Do not copy this file into the
README benchmark table until a controlled run produces stable measured
improvement.

## Conditions For A Controlled Run

- Model: `gpt-5.5` or the current target model under test
- API: OpenAI Responses API or the equivalent agent API path
- Reasoning effort: run at least `medium`; optionally sweep `high` / `xhigh`
- Difference: same user prompt, with or without Fairy Tale skill process
  guidance
- Tools: no external web required; local scratch scripts are allowed only when
  the agent creates a checkable model or validator
- Scoring: rubric below, scored by reviewer or judge from the final answer and
  any attached validation artifacts
- Important: this use case evaluates process quality, not proprietary model
  equivalence

## Capability Being Tested

The target capability is cross-domain generalization:

1. Recover unstated but binding contracts from artifacts.
2. Convert observations into a transferable invariant.
3. Build a checkable world model before proposing broad changes.
4. Preserve legacy behavior while adding new behavior.
5. Separate confirmed facts, likely assumptions, risky assumptions, and open
   questions.
6. Validate success reasons rather than treating lucky local passes as rules.

This use case intentionally hides the same principle across four surfaces:
agentic coding, privacy/legal operations, UI behavior, and runtime incident
diagnosis.

The latent invariant is:

> Add a policy layer without changing the old contract. Existing callers,
> stored records, user-visible flows, audit semantics, and security boundaries
> remain authoritative unless the prompt explicitly deprecates them.

A strong answer should discover that invariant. A weak answer may solve each
surface independently but miss the shared rule.

## Source Notes Used To Build The Use Case

- Fairy Tale Generalization Harness: executable world models and tacit intent
- Fairy Tale Benchmark Feedback: `implicit_contract_gap`,
  `existing_behavior_regression`, `missing_adjacent_symbol`,
  `self_selected_validation_gap`
- ARC-AGI-3-inspired process patterns:
  - executable/checkable world model before planning
  - confirmed/refuted/no-op memory separation
  - raw-log analysis before summary-only conclusions
  - success-reason verification before rule promotion
- Tacit intent recovery patterns:
  - infer from adjacent files, old tests, generated schemas, docs, naming,
    issue wording, and logs
  - ask only for irreversible or externally visible missing assumptions

---

## User Prompt

~~~text
あなたはTypeScript/Python混在monorepoのprincipal engineer兼AI governance reviewerです。
以下は架空のenterprise AI intake platformの変更相談です。

目的:
既存のAI support intakeに「regional policy pack」と「delegated reviewer」を追加したい。
ただし既存顧客のAPI、過去イベント、監査ログ、UI操作、DPA上の説明は壊したくない。

重要:
- 実装コードそのものではなく、設計・テスト・リリース計画を出してください。
- 仕様に明記されていないが既存artifactから推測できる契約も拾ってください。
- 破壊的な仮定、ユーザー確認が必要な仮定、実装前に検証できる仮定を分けてください。
- 可能なら、小さな実行可能モデルまたは疑似コードで検証できる不変条件を示してください。

Repository sketch:

packages/api/src/recipient.ts
```ts
export type Recipient = {
  id: string;
  email: string;
  tenantId: string;
  role?: "owner" | "agent" | "viewer";
};

// Existing public helper. Used by API, worker, tests, and customer plugins.
export function normalizeRecipient(input: string | Recipient): Recipient {
  if (typeof input === "string") {
    return {
      id: input.toLowerCase(),
      email: input.toLowerCase(),
      tenantId: "legacy-default",
    };
  }
  return {
    ...input,
    email: input.email.toLowerCase(),
  };
}
```

packages/api/src/policy.ts
```ts
export type Region = "jp" | "eu" | "us";
export type PolicyPack = {
  region: Region;
  allowAiDraft: boolean;
  requireHumanReview: boolean;
  exportMode: "full" | "redacted";
};

export const DEFAULT_POLICY: PolicyPack = {
  region: "us",
  allowAiDraft: true,
  requireHumanReview: false,
  exportMode: "full",
};
```

packages/worker/src/events.py
```python
def emit_case_event(case_id, tenant_id, actor_id, action, metadata=None):
    return {
        "caseId": case_id,
        "tenantId": tenant_id,
        "actorId": actor_id,
        "action": action,
        "metadata": metadata or {},
    }
```

packages/web/src/components/ReviewModal.tsx
```tsx
export function ReviewModal({ open, onClose, children }) {
  if (!open) return null;
  return (
    <div role="dialog" aria-modal="true">
      <button aria-label="Close" onClick={onClose}>x</button>
      {children}
    </div>
  );
}
```

contracts/dpa-ai-addendum.md excerpt:
```text
Provider may process Customer Data to provide AI intake, routing, draft
generation, analytics, and service improvement. Provider will support
region-specific configurations where enabled in the product. Customer remains
responsible for final decisions based on AI Outputs.
```

Existing tests:
```text
recipient.test.ts
- normalizeRecipient("USER@EXAMPLE.COM") returns tenantId "legacy-default"
- normalizeRecipient({ email: "A@B.COM", tenantId: "t1" }) preserves tenantId
- plugins can import normalizeRecipient from packages/api/src/recipient

events.test.py
- emit_case_event(..., metadata=None) returns metadata {}
- event keys are caseId, tenantId, actorId, action, metadata

ReviewModal.test.tsx
- close button can be clicked with keyboard
- role="dialog" exists when open
```

New requested behavior:
- Customers can enable a regional policy pack per tenant.
- In JP/EU policy packs, AI drafts may still be generated, but a delegated
  reviewer must approve before customer-facing send/export.
- A delegated reviewer may belong to the same tenant or a parent tenant, but
  never a sibling tenant.
- Export must be redacted when policy.exportMode is "redacted".
- Audit logs must show whether an action was AI-drafted, human-approved, or
  blocked by policy.
- Existing integrations that call normalizeRecipient(input) must keep working.
- Existing event consumers must keep working.
- Existing ReviewModal keyboard behavior must keep working.

Observed failure from a previous attempt:
```text
FAIL recipient.test.ts
TypeError: normalizeRecipient() missing required argument 'policy'

FAIL customer-plugin-smoke.test.ts
Cannot import normalizeRecipient from packages/api/src/recipient

FAIL events.test.py
AssertionError: event keys changed:
expected ['caseId','tenantId','actorId','action','metadata']
actual ['caseId','tenantId','actorId','action','metadata','policy','approval']

FAIL ReviewModal.test.tsx
Expected close button to be keyboard reachable after reviewer selector appears

Production incident note:
After enabling jp policy for tenant t-parent, two child tenants could approve
each other's exports because parentTenantId was treated as a flat group id.

Legal/compliance note:
Customer success told a JP customer "regional policy pack means data stays in
Japan", but engineering only implemented review/export rules. No storage or
processing location control exists yet.
```

Tasks:

1. Build a concise world model:
   - entities
   - actions
   - state transitions
   - existing contracts
   - new policy constraints
   - unsafe assumptions

2. Identify the shared latent invariant across code, events, UI, and legal/compliance.

3. Propose the smallest compatible design:
   - public API changes or wrappers
   - event schema strategy
   - delegated reviewer authorization rule
   - ReviewModal accessibility/keyboard preservation
   - DPA/customer-facing wording correction

4. Write a validation matrix:
   columns = Surface / Tacit contract / New behavior / Test or probe / Failure prevented

5. Provide one executable or checkable model in TypeScript or Python-like pseudocode
   that verifies the delegated reviewer rule and one compatibility invariant.

6. List:
   - confirmed facts
   - likely inferred requirements
   - risky assumptions
   - questions that must be asked before release
~~~

---

## What A Weak Without-Fairy-Tale Answer Often Does

The control answer may look useful on the surface. It may propose a policy
object, an approval workflow, and a few tests. The failure is usually not lack
of ideas; it is poor generalization from the artifacts.

Likely weak behaviors:

1. Changes `normalizeRecipient(input, policy)` and breaks old callers.
2. Adds `policy` and `approval` as top-level event fields, breaking consumers
   that expect the old key set.
3. Treats `parentTenantId` as a membership group and permits sibling approvals.
4. Fixes the modal visually but misses keyboard focus order and close button
   reachability after adding a reviewer selector.
5. Says "regional policy pack" implies data residency, even though the repo only
   has review/export policy.
6. Writes a broad migration plan without a small falsifiable model.
7. Lists assumptions but does not separate confirmed, inferred, risky, and
   release-blocking unknowns.
8. Treats the previous attempt's failures as isolated test breaks rather than
   evidence of one shared invariant: old contracts remain authoritative.

## What A Strong With-Fairy-Tale Answer Should Do

A strong Fairy Tale answer should first recover the implicit contract:

> The new policy layer must compose with existing contracts. It cannot replace
> function signatures, import paths, event envelopes, keyboard affordances,
> tenant hierarchy rules, or customer-facing compliance meanings.

Expected positive signals:

1. Builds a world model before the plan.
2. Names the latent invariant explicitly.
3. Keeps `normalizeRecipient(input)` stable and adds a new helper such as
   `resolveRecipientPolicy(recipient, tenantPolicy)` or a wrapper that preserves
   the old export.
4. Keeps the event envelope stable and places policy/approval details under
   `metadata`, or versions events without breaking old consumers.
5. Models delegated review as:
   - same tenant allowed
   - parent reviewer may approve child tenant if parent relation is explicit
   - sibling tenant never allowed
   - flat group id is insufficient evidence
6. Preserves `ReviewModal` keyboard close behavior and focus order.
7. Corrects DPA/customer-facing wording: regional policy pack is not data
   residency unless storage/processing controls exist.
8. Provides an executable/checkable model that can falsify the sibling-tenant
   bug and one legacy-compatibility invariant.
9. Separates confirmed facts, likely inferred requirements, risky assumptions,
   and questions needed before release.
10. Avoids benchmark-specific or prompt-specific hardcoding.

---

## Comparison Evaluation Rubric

Score each answer out of 100.

| Category | Points | What To Look For |
|---|---:|---|
| World model quality | 15 | Entities, actions, state transitions, existing contracts, new policy constraints, unsafe assumptions |
| Shared latent invariant | 15 | Explicitly identifies "compose policy layer without breaking old contracts" across all surfaces |
| Tacit contract recovery | 20 | Finds function signature/import path, event envelope, keyboard behavior, tenant hierarchy, and compliance wording contracts |
| Executable/checkable verifier | 15 | Includes pseudocode or small model that catches sibling approval and at least one compatibility invariant |
| Validation matrix | 15 | Maps each surface to tacit contract, new behavior, test/probe, and failure prevented |
| Assumption governance | 10 | Separates confirmed, likely, risky, and release-blocking questions |
| Minimal compatible design | 10 | Uses wrappers/versioning/metadata/focused tests instead of broad rewrites |

Suggested interpretation:

- 85-100: strong generalization signal
- 70-84: useful, but likely misses one implicit contract or verifier
- 50-69: competent domain answer, weak generalization
- below 50: likely solves visible requirements while breaking hidden contracts

## Expected Comparison Pattern

| Signal | Without Fairy Tale | With Fairy Tale |
|---|---|---|
| Latent invariant | Often implicit or absent | Explicitly named and used to structure plan |
| API compatibility | May change signatures directly | Preserves old exports and adds wrappers/new helpers |
| Event compatibility | May add top-level fields | Keeps envelope stable or versions intentionally |
| Tenant hierarchy | May confuse parent/group/sibling | Uses explicit parent-child relation and rejects sibling |
| UI accessibility | May mention "test accessibility" generally | Preserves keyboard close/focus behavior as a named invariant |
| Compliance wording | May overpromise data residency | Separates policy pack from data location controls |
| Verifier | Usually checklist only | Provides executable/checkable model |
| Assumptions | Broad notes | Confirmed/likely/risky/questions separated |

## Example Gold-Standard Evaluation Notes

Use these notes as evaluator guidance, not as hidden answer content for the
model being tested.

### High-Value Findings

- `normalizeRecipient` is a public helper with plugin import dependency.
  Changing the required argument list is a public-contract break.
- Old string input behavior returns `tenantId: "legacy-default"`. New policy
  code must not reinterpret that silently.
- Existing event consumers assert the exact top-level keys. Policy and approval
  details should live in `metadata`, behind an event version, or in a secondary
  event stream.
- `parentTenantId` cannot be treated as a flat group. Parent-child delegation is
  directional; sibling approval must fail.
- `ReviewModal` already has keyboard-tested close behavior. Adding a reviewer
  selector must not trap or reorder focus so the close button becomes
  unreachable.
- "Regional policy pack" is not "data residency." The DPA and customer-facing
  text must say review/export policy unless infrastructure actually enforces
  storage and processing regions.

### Acceptable Design Direction

```text
normalizeRecipient(input) remains unchanged.
resolveRecipientContext(input, tenantPolicy) composes policy on top.
emit_case_event() keeps the same top-level keys.
approval and policy facts are stored under metadata.policyDecision.
canApprove(reviewer, caseTenant, tenantGraph) uses directional ancestry.
ReviewModal keeps close button keyboard reachable and introduces focus tests.
DPA wording distinguishes regional workflow policy from data residency.
```

### Minimal Checkable Model

```ts
type Tenant = { id: string; parentId?: string };
type Reviewer = { tenantId: string };

function isAncestor(parentId: string, childId: string, tenants: Map<string, Tenant>): boolean {
  let current = tenants.get(childId);
  while (current?.parentId) {
    if (current.parentId === parentId) return true;
    current = tenants.get(current.parentId);
  }
  return false;
}

function canApprove(reviewer: Reviewer, caseTenantId: string, tenants: Map<string, Tenant>): boolean {
  return reviewer.tenantId === caseTenantId || isAncestor(reviewer.tenantId, caseTenantId, tenants);
}

const tenants = new Map<string, Tenant>([
  ["parent", { id: "parent" }],
  ["child-a", { id: "child-a", parentId: "parent" }],
  ["child-b", { id: "child-b", parentId: "parent" }],
]);

console.assert(canApprove({ tenantId: "parent" }, "child-a", tenants) === true);
console.assert(canApprove({ tenantId: "child-a" }, "child-a", tenants) === true);
console.assert(canApprove({ tenantId: "child-a" }, "child-b", tenants) === false);

function legacyEventShape(event: Record<string, unknown>): boolean {
  return JSON.stringify(Object.keys(event).sort()) === JSON.stringify([
    "action",
    "actorId",
    "caseId",
    "metadata",
    "tenantId",
  ].sort());
}
```

### Strong Validation Matrix Example

| Surface | Tacit contract | New behavior | Test or probe | Failure prevented |
|---|---|---|---|---|
| API helper | `normalizeRecipient(input)` signature and import path are public | Add policy composition without changing helper | Existing recipient tests + plugin smoke import + new wrapper tests | Missing-argument and import failures |
| Events | Top-level event envelope is stable | Record AI draft/review/block state | Existing event key test + metadata policyDecision test | Consumer schema break |
| Tenant auth | Parent-child approval is directional | Parent can approve child; sibling cannot | `canApprove` model with parent/child/sibling fixtures | Cross-child export approval incident |
| UI modal | Close button remains keyboard reachable | Add delegated reviewer selector | Keyboard tab order and close test | Accessibility regression |
| DPA wording | Product config is not data residency | Correct customer-facing explanation | Contract text review checklist | Compliance overclaim |

## Run Procedure

1. Run the prompt without Fairy Tale skill guidance.
2. Run the exact same prompt with Fairy Tale active.
3. Score both outputs with the rubric above.
4. Record item-level misses, not only total score.
5. If Fairy Tale improves score, classify which mechanisms caused the gain:
   - world model
   - tacit contract recovery
   - executable verifier
   - assumption separation
   - validation matrix
6. If Fairy Tale does not improve score, inspect whether the answer overfit to
   coding and missed legal/UI/operations transfer.

## Reporting Template

```text
Run date:
Model:
Effort:
Without Fairy Tale score:
With Fairy Tale score:
Delta:
Primary improvement:
Remaining misses:
Was the latent invariant explicit? yes/no
Did the answer include a verifier? yes/no
Did it avoid overclaiming data residency? yes/no
Did it preserve old contracts? yes/no
Promotion decision:
```

## Why This Use Case Belongs In `sample_results`

The previous sample results mostly compare domain-specific output quality:
legal, finance/document, bio/health, spatial/3D, agentic coding/security,
cybersecurity, and narrative expression. This use case targets a different
question: whether the process can generalize a learned failure pattern across
surfaces.

The intended measured delta is not "more detailed answer." The intended delta
is whether the answer prevents a class of failures that caused previous
SWE-style misses:

- API compatibility breaks
- missing adjacent contracts
- self-selected validation gaps
- edge-case invariant misses
- compliance overclaim from underspecified wording

If Fairy Tale works here, the with-condition should show fewer independent
checklists and more transferable invariants backed by executable or checkable
evidence.
