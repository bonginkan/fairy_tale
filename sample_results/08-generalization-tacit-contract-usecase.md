# Fairy Tale Sample Use Case: generalization_tacit_contract

Date: 2026-06-16

## Status

This file contains both the designed evaluation use case and one controlled
with/without sample run from 2026-06-16. The measured section is an `n=1`
reference sample, not a benchmark result. Do not copy it into the README
benchmark table until repeated controlled runs produce stable measured
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

## Measured n=1 Comparison

Date: 2026-06-16

### Run Conditions

- Model: `gpt-5.5`
- API: OpenAI Responses API
- Reasoning effort: `medium`
- Text verbosity: default API verbosity
- Samples: one prompt x two conditions
- Without condition: direct principal engineer / AI governance reviewer system guidance
- With condition: same user prompt plus Fairy Tale Generalization Harness process guidance
- Judge: `gpt-5.5`, same API path, strict rubric evaluation
- Artifact IDs:
  - without: `resp_07bf8a29715651e7006a30ca8bba00819b82b88183e553ba11`
  - with: `resp_0505e3b6edc360f4006a30cb0ede78819a8554ad725d02eec7`
  - judge: `resp_04ffe53cff62b8d8006a30cb88104c819a9c1427e54246c2e0`

### Comparison Evaluation

## 1. カテゴリ別スコア表

| Category | Points | WITHOUT FAIRY TALE | WITH FAIRY TALE |
|---|---:|---:|---:|
| World model quality | 15 | 15 | 15 |
| Shared latent invariant | 15 | 14 | 15 |
| Tacit contract recovery | 20 | 20 | 20 |
| Executable/checkable verifier | 15 | 15 | 15 |
| Validation matrix | 15 | 15 | 15 |
| Assumption governance | 10 | 7 | 7 |
| Minimal compatible design | 10 | 10 | 10 |
| **Total** | **100** | **96** | **97** |

## 2. 合計スコアと差分

| Answer | Total |
|---|---:|
| WITHOUT FAIRY TALE | 96 / 100 |
| WITH FAIRY TALE | 97 / 100 |
| **Delta** | **+1** |

**判定:** 両方とも強い generalization signal。WITH FAIRY TALE は shared invariant の表現がより直接的で、全 surface への対応づけがわずかに明確。

---

## 3. 簡潔な item-level comparison

- **World model quality**
  - 両方とも entities / actions / state transitions / new policy constraints / unsafe assumptions を網羅。
  - WITHOUT は状態遷移と unsafe assumptions が非常に詳細。
  - WITH は policy fields、reviewer capability、effective policy source/version などが整理されている。

- **Shared latent invariant**
  - WITHOUT は「既存の公開契約を additive に拡張」「コード、event、UI、法務文書で同じ意味」と明示。
  - WITH は「new governance controls must be additive, tenant-scoped, auditable, and truthfully represented, without weakening or reshaping existing public contracts」と、rubric の “compose policy layer without breaking old contracts” により近い形で表現。

- **Tacit contract recovery**
  - 両方とも以下を回収している:
    - `normalizeRecipient(input: string | Recipient): Recipient`
    - import path `packages/api/src/recipient`
    - event envelope の exact top-level keys
    - `metadata=None` → `{}`
    - `ReviewModal` keyboard behavior
    - sibling tenant approval 禁止
    - regional policy ≠ data residency
  - 差はほぼない。

- **Executable/checkable verifier**
  - 両方とも sibling approval を false にする tenant hierarchy model を含む。
  - 両方とも event top-level key invariant を assert している。
  - WITHOUT は `metadata=None` 互換性も assert しておりやや広いが、採点上は満点範囲。

- **Validation matrix**
  - 両方とも surface / tacit contract / new behavior / test or probe / failure prevented の形式を満たす。
  - WITH は reviewer capability、old events、monitoring などがやや整理されている。
  - WITHOUT も十分に網羅的。

- **Assumption governance**
  - 両方とも unsafe assumptions や確認事項を列挙。
  - ただし rubric が求める **confirmed / likely / risky / release-blocking questions** の明示的な分離は不完全。
  - WITHOUT は「ユーザー確認が必要」「実装前に検証できる仮定」「release gate」があり、かなり近い。
  - WITH も「Unsafe assumptions」「needs explicit decision」「customer remediation」はあるが、分類軸は明示されていない。

- **Minimal compatible design**
  - 両方とも broad rewrite ではなく、wrapper、metadata nesting、feature flag、focused tests、separate policy/reviewer modules を提案。
  - 両方満点相当。

---

## 4. 改善・後退した generalization mechanisms

### 改善した点: WITH FAIRY TALE

- **Invariant abstraction**
  - 「additive, tenant-scoped, auditable, truthfully represented」という抽象化がよりコンパクトで、複数 surface に転用しやすい。

- **Policy composition**
  - `resolveEffectivePolicy`、`policySourceTenantId`、`policyVersion` など、policy layer を既存 contract の外側に compose する設計が明確。

- **Compatibility wrapper pattern**
  - `emit_governance_case_event` wrapper や `normalizeRecipientWithContext` の代替案により、互換層の作り方が具体的。

- **Release generalization**
  - shadow mode、canary、monitoring があり、隠れた contract を本番前に観測する姿勢が強い。

### 後退または弱くなった点: WITH FAIRY TALE

- **一部の既存挙動の詳細**
  - WITHOUT の方が `normalizeRecipient` の string/object behavior、`metadata=None`、ReviewModal の focus details をより細かく列挙している。
  - WITH も十分だが、項目単位の detail はやや圧縮されている。

- **Assumption governance**
  - WITH も WITHOUT も明示分類は不完全。
  - WITH は「risky」「release-blocking question」としてのラベル分けがないため、rubric 上は伸び切らない。

### ほぼ同等だった点

- tacit contract recovery
- verifier の有効性
- validation matrix
- minimal compatible design

---

## 5. Caveats

- **n=1 の評価**
  - この比較は単一タスク・単一回答ペアに対する評価であり、モデル全体の一般化性能を統計的に示すものではない。

- **非ベンチマーク**
  - これは標準化された benchmark ではなく、設計された Fairy Tale generalization / tacit-contract use case に対する rubric-based judgment。
  - スコア差 **+1** は小さく、実運用上は同等に近い強い回答と見るべき。

- **採点の主な制約**
  - 両回答とも非常に長く、網羅性は高いが、rubric は verbosity 自体を評価しない。
  - 減点の中心は、assumption governance が rubric 指定の分類軸を完全には満たしていない点。

### Output: without_fairy_tale

~~~text
## 1. ワールドモデル

### エンティティ

| Entity | 説明 |
|---|---|
| Tenant | 顧客テナント。親子関係を持つ可能性がある。`tenantId`, `parentTenantId` だけでなく、階層として扱う必要がある。 |
| Case / Intake | AI support intake の対象。tenant に所属する。 |
| Recipient | 既存 API の宛先表現。`id`, `email`, `tenantId`, optional `role`。policy や reviewer とは直接結合しない。 |
| PolicyPack | tenant 単位で有効化される regional policy。`jp`, `eu`, `us`。 |
| Delegated Reviewer | case tenant 自身、またはその親 tenant 側に属する承認者。兄弟 tenant からの承認は禁止。 |
| Approval | reviewer による承認記録。誰が、どの tenant 権限で、何を承認したか。 |
| Event / Audit Log | 既存 `emit_case_event` の top-level schema は維持。新情報は `metadata` に追加。 |
| Export Artifact | customer-facing send/export 対象。policy により redaction が必要。 |
| ReviewModal | 既存 keyboard accessibility を壊してはいけない UI primitive。 |
| DPA / Customer-facing Description | 実装済み制御だけを正確に説明する必要がある。 |

---

### 主要アクション

| Action | 説明 |
|---|---|
| Enable regional policy pack | tenant に policy pack を設定する。 |
| Generate AI draft | AI draft を生成する。JP/EU でも生成自体は可能。 |
| Request send/export | customer-facing な送信または export を試行する。 |
| Approve by delegated reviewer | delegated reviewer が human approval を行う。 |
| Block by policy | policy または authorization により送信/export を止める。 |
| Redacted export | `policy.exportMode === "redacted"` の場合、export に redaction を適用する。 |
| Emit audit event | AI-drafted / human-approved / blocked-by-policy を監査可能に記録する。 |

---

### 状態遷移

```text
DraftRequested
  -> AIDraftGenerated
      metadata.aiDrafted = true

AIDraftGenerated
  -> PendingHumanReview
      if policy.requireHumanReview == true
      and action is customer-facing send/export

PendingHumanReview
  -> Approved
      if reviewer is authorized delegated reviewer

PendingHumanReview
  -> Blocked
      if reviewer is sibling tenant / unauthorized / missing

Approved
  -> ExportedOrSent
      if exportMode == "full"

Approved
  -> RedactedExported
      if exportMode == "redacted"

AIDraftGenerated
  -> ExportedOrSent
      only if policy.requireHumanReview == false

Any customer-facing action
  -> Blocked
      if policy denies action or required approval is absent
```

---

### 既存契約

明文化されている契約だけでなく、既存 artifact から推測される tacit contract もある。

#### `normalizeRecipient`

既存契約:

```ts
normalizeRecipient(input: string | Recipient): Recipient
```

推測される契約:

- 必須引数を増やしてはいけない。
- import path `packages/api/src/recipient` を壊してはいけない。
- string input の場合:
  - `id` は lowercase email。
  - `email` は lowercase email。
  - `tenantId` は `"legacy-default"`。
- object input の場合:
  - `tenantId` を保持する。
  - `email` は lowercase。
- policy や reviewer の判定を `Recipient` normalize に混ぜない。

---

#### `emit_case_event`

既存契約:

```python
{
  "caseId": ...,
  "tenantId": ...,
  "actorId": ...,
  "action": ...,
  "metadata": ...
}
```

推測される契約:

- top-level keys は増やさない。
- `metadata=None` のときは `{}`。
- 既存 consumer は exact key set に依存している可能性がある。
- policy / approval / audit 情報は top-level ではなく `metadata` 配下に追加する。

---

#### `ReviewModal`

既存契約:

- `open=false` では render されない。
- `open=true` では `role="dialog"` が存在する。
- `aria-modal="true"` を維持する。
- close button は keyboard reachable である。
- reviewer selector を追加しても close button の keyboard 操作を妨げてはいけない。

---

#### DPA / customer-facing contract

既存文言:

```text
Provider will support region-specific configurations where enabled in the product.
```

推測される契約:

- 「region-specific configurations」は現在の実装範囲では review / export policy を指す。
- data residency、storage location、processing location を保証しているわけではない。
- JP customer に「data stays in Japan」と説明するのは現時点では不正確。

---

### 新 policy constraints

| Constraint | 内容 |
|---|---|
| Tenant-level enablement | regional policy pack は tenant 単位で有効化。 |
| JP/EU human review | JP/EU policy では customer-facing send/export 前に delegated reviewer approval が必要。 |
| AI draft generation | JP/EU でも AI draft 自体は可能。 |
| Delegated reviewer boundary | reviewer は same tenant または parent/ancestor tenant。sibling tenant は不可。 |
| Redacted export | `policy.exportMode === "redacted"` なら export は redacted。 |
| Audit visibility | action が AI-drafted / human-approved / blocked-by-policy のどれに該当するか監査ログで分かること。 |
| Backward compatibility | 既存 API、event schema、UI keyboard behavior、DPA 上の説明を壊さないこと。 |

---

### unsafe assumptions

#### 破壊的な仮定

これらは採用してはいけない。

1. `normalizeRecipient(input, policy)` のように必須引数を増やす。
2. `packages/api/src/recipient` の export path を変更する。
3. event top-level に `policy` や `approval` を追加する。
4. `parentTenantId` が同じなら同一承認グループとみなす。
5. regional policy pack を data residency 制御として説明する。
6. reviewer selector を modal の先頭に置き、close button の keyboard 到達性を壊す。
7. policy 判定を Recipient normalization に混ぜる。

#### ユーザー確認が必要な仮定

1. 「parent tenant」は direct parent のみか、ancestor 全体を含むか。
2. delegated reviewer の資格は何で判定するか。
   - role?
   - explicit grant?
   - group membership?
   - IdP claim?
3. customer-facing send/export の範囲。
   - email send
   - ticket reply
   - CSV export
   - API export
   - webhook
4. redaction の具体ルール。
   - PII
   - sensitive category
   - attachments
   - free text
   - audit metadata
5. JP/EU policy の default values。
   - `allowAiDraft`
   - `requireHumanReview`
   - `exportMode`
6. 既存 tenant に policy 未設定の場合、完全に legacy behavior のままでよいか。
7. DPA 文言修正を既存顧客へ notice する必要があるか。

#### 実装前に検証できる仮定

1. plugin が deep import `packages/api/src/recipient` に依存している数。
2. event consumer が exact top-level keys に依存しているか。
3. `metadata` 配下の additive fields を既存 consumer が無視できるか。
4. ReviewModal の focus order / keyboard 操作が既存 test で十分か。
5. tenant hierarchy の正規データが cycle-free か。
6. parent/child 関係の source of truth が単一か。
7. export pipeline が redaction を必ず通る centralized choke point を持つか。

---

## 2. 共有 latent invariant

最重要の共有不変条件は以下です。

> **既存の公開契約を additive に拡張しつつ、tenant 境界・human approval・policy decision・customer-facing 説明が、コード、event、UI、法務文書で同じ意味を持つこと。**

より短く言うと:

> **互換性を壊さず、実際に提供している governance control だけを正確に表現する。**

この invariant は全 surface にまたがります。

| Surface | invariant |
|---|---|
| API | 既存呼び出しは同じ結果を返す。policy を Recipient normalize に混ぜない。 |
| Events | top-level schema は不変。audit semantics は metadata に additive に入れる。 |
| Authorization | tenant boundary は階層で判定し、sibling を許可しない。 |
| UI | reviewer UI を足しても既存 modal keyboard contract を壊さない。 |
| Legal/Compliance | regional policy を data residency と誤認させない。 |

---

## 3. 最小互換設計

### 3.1 Public API changes / wrappers

#### やること

`normalizeRecipient` は一切 breaking change しない。

```ts
normalizeRecipient(input: string | Recipient): Recipient
```

維持するもの:

- function name
- export path
- required arg count
- string input behavior
- object input behavior
- legacy `tenantId: "legacy-default"`

#### 追加するもの

policy / approval 判定は別モジュールに分離する。

例:

```text
packages/api/src/policyResolver.ts
packages/api/src/reviewerAuthorization.ts
packages/api/src/exportPolicy.ts
```

概念 API:

```ts
resolvePolicyForTenant(tenantId): PolicyPack
requiresHumanReview(policy, action): boolean
canDelegatedReviewerApprove(caseTenantId, reviewerTenantId): boolean
applyExportPolicy(exportPayload, policy): ExportPayload
```

重要:

- `Recipient.role` に安易に `"delegatedReviewer"` を追加しない。
- delegated reviewer は explicit grant / reviewer assignment として別 entity にする。
- 既存 `Recipient` は宛先表現として維持する。

---

### 3.2 Event schema strategy

#### 方針

既存 event top-level schema は固定。

```python
{
  "caseId": case_id,
  "tenantId": tenant_id,
  "actorId": actor_id,
  "action": action,
  "metadata": metadata or {},
}
```

`policy` や `approval` は top-level に追加しない。

#### 新しい audit metadata 例

```json
{
  "audit": {
    "aiDrafted": true,
    "humanApproval": {
      "status": "approved",
      "reviewerId": "u-reviewer",
      "reviewerTenantId": "t-parent",
      "approvalId": "appr-123"
    },
    "policyDecision": {
      "result": "allowed",
      "reason": "jp_policy_human_review_approved",
      "policyRegion": "jp",
      "exportMode": "redacted"
    }
  }
}
```

blocked の場合:

```json
{
  "audit": {
    "aiDrafted": true,
    "humanApproval": {
      "status": "missing"
    },
    "policyDecision": {
      "result": "blocked",
      "reason": "human_review_required",
      "policyRegion": "jp"
    }
  }
}
```

#### イベント方針

- top-level key set は常に:
  - `caseId`
  - `tenantId`
  - `actorId`
  - `action`
  - `metadata`
- `metadata=None` は `{}` のまま。
- 新 audit fields は `metadata.audit` に additive。
- 監査検索用に必要なら downstream indexer 側で `metadata.audit.*` を index する。
- schema version を入れるなら `metadata.audit.schemaVersion` に置く。

---

### 3.3 Delegated reviewer authorization rule

#### 正しいルール

case の tenant を `caseTenantId`、reviewer の所属 tenant を `reviewerTenantId` とする。

承認可能なのは:

1. `reviewerTenantId === caseTenantId`
2. `reviewerTenantId` が `caseTenantId` の ancestor tenant

承認不可:

1. sibling tenant
2. child tenant から parent tenant case への承認
3. unrelated tenant
4. tenant hierarchy が不明、cycle 検出、欠損している場合

#### 重要な修正点

production incident の原因は:

```text
same parentTenantId == same approval group
```

として扱ったこと。

これは sibling tenant を同一グループ扱いしてしまう。

正しくは:

```text
reviewerTenantId is in ancestor chain of caseTenantId
```

を判定する。

例:

```text
t-parent
  ├── t-child-a
  └── t-child-b
```

| case tenant | reviewer tenant | result |
|---|---:|---|
| `t-child-a` | `t-child-a` | allow |
| `t-child-a` | `t-parent` | allow |
| `t-child-a` | `t-child-b` | deny |
| `t-parent` | `t-child-a` | deny |
| `t-child-b` | `t-child-a` | deny |

---

### 3.4 ReviewModal accessibility / keyboard preservation

#### 方針

`ReviewModal` は primitive として既存 contract を維持する。

維持するもの:

- `role="dialog"`
- `aria-modal="true"`
- close button
- close button の keyboard 到達性
- `open=false` で null
- children composition

#### reviewer selector 追加時の注意

- close button を DOM order の先頭付近に維持する。
- reviewer selector を close button より前に挿入しない。
- focus trap を導入する場合、close button を trap 内の tabbable 要素に含める。
- initial focus を reviewer selector に置く場合でも、`Shift+Tab` で close button に戻れること。
- Escape close が既存 behavior と矛盾しないなら追加可能。ただし既存 test とは別 test として追加。
- selector loading / disabled state 時に close button まで disabled にしない。

#### テスト追加

- reviewer selector 表示後も close button が `Tab` / `Shift+Tab` で到達可能。
- close button が keyboard activation できる。
- `role="dialog"` と `aria-modal="true"` が維持される。
- selector が validation error を出しても focus が modal 外へ漏れない。

---

### 3.5 DPA / customer-facing wording correction

#### 問題

Customer success が:

```text
regional policy pack means data stays in Japan
```

と説明しているが、engineering は data residency / storage location / processing location control を実装していない。

これは compliance risk。

#### 修正文言案

DPA addendum または product docs:

```text
Regional policy packs provide region-specific product controls, such as
human review requirements and export redaction rules, where enabled in the
product. Regional policy packs do not by themselves control or guarantee
data storage location, processing location, or data residency unless a
separate data residency feature is expressly enabled and documented.
Customer remains responsible for final decisions based on AI Outputs.
```

日本語 customer-facing 説明:

```text
regional policy pack は、地域別のレビュー要件や export redaction などの
製品内ポリシー制御を提供する機能です。この機能単独では、データの保存場所、
処理場所、またはデータレジデンシーを保証するものではありません。
データレジデンシーが必要な場合は、別途明示的に提供・文書化された機能の
有効化が必要です。
```

#### release gate

- 営業資料、CS FAQ、DPA、管理画面 tooltip を同じ意味に揃える。
- JP customer への既存説明について legal / CS と remediation plan を決める。
- 「regional」表示に residency を連想させる copy がないか確認する。

---

## 4. Validation matrix

| Surface | Tacit contract | New behavior | Test or probe | Failure prevented |
|---|---|---|---|---|
| `normalizeRecipient` | required arg を増やさない | policy とは分離 | 既存 tests をそのまま実行 | `missing required argument 'policy'` |
| `normalizeRecipient` | import path 維持 | customer plugin が import 可能 | plugin smoke test | plugin breakage |
| `normalizeRecipient` | string input は `legacy-default` | legacy tenant 解釈を維持 | golden test | 既存 API 挙動変更 |
| Recipient type | 宛先表現であり policy entity ではない | reviewer grant は別 entity | type-level review | role union 拡張による plugin break |
| Policy resolution | policy 未設定 tenant は legacy default | tenant 単位で regional policy 有効化 | config lookup test | 既存顧客への意図しない JP/EU 適用 |
| JP/EU policy | draft 生成は許可 | send/export 前に review required | workflow test | AI draft の過剰ブロック |
| Approval | sibling tenant は不可 | same tenant or ancestor のみ許可 | hierarchy authorization property test | production incident 再発 |
| Approval | 不明 hierarchy は安全側 | unknown/cycle は deny | corrupted hierarchy test | privilege escalation |
| Export | exportMode に従う | `redacted` なら必ず redaction | export pipeline integration test | PII/機微情報漏洩 |
| Event schema | top-level keys 固定 | audit は `metadata.audit` | exact key test | event consumer breakage |
| Event metadata | `metadata=None` は `{}` | 新 fields は additive | existing events test | null handling regression |
| Audit log | decision provenance が必要 | AI-drafted / approved / blocked を記録 | audit search probe | 監査不能 |
| ReviewModal | dialog role 維持 | reviewer selector を追加 | RTL accessibility test | modal semantics regression |
| ReviewModal | close button keyboard reachable | selector 表示後も reachable | tab order test | observed UI failure |
| DPA | 実装済み制御のみ説明 | residency 非保証を明記 | legal copy review | JP customer 誤説明 |
| CS docs | regional ≠ residency | FAQ/tooltip 統一 | doc diff review | sales/compliance mismatch |
| Release | 既存 tenant を壊さない | feature flag / tenant allowlist | canary rollout | broad customer incident |
| Observability | blocked reason が必要 | policy decision metrics | dashboard probe | silent policy failures |

---

## 5. Checkable model: delegated reviewer rule と compatibility invariant

Python-like pseudocode です。実装そのものではなく、設計検証用モデルです。

```python
TOP_LEVEL_EVENT_KEYS = ["caseId", "tenantId", "actorId", "action", "metadata"]

tenant_parent = {
    "t-parent": None,
    "t-child-a": "t-parent",
    "t-child-b": "t-parent",
    "t-grandchild-a1": "t-child-a",
    "t-unrelated": None,
}

def ancestor_chain(tenant_id, parent_map):
    """
    Returns ancestors from direct parent upward.
    Deny-safe on cycles or unknown tenants.
    """
    if tenant_id not in parent_map:
        return None

    seen = set()
    chain = []

    current = tenant_id
    while True:
        if current in seen:
            return None  # cycle: unsafe, deny
        seen.add(current)

        parent = parent_map.get(current)
        if parent is None:
            return chain

        if parent not in parent_map:
            return None  # broken hierarchy: unsafe, deny

        chain.append(parent)
        current = parent

def can_delegated_reviewer_approve(case_tenant_id, reviewer_tenant_id, parent_map):
    if case_tenant_id not in parent_map:
        return False
    if reviewer_tenant_id not in parent_map:
        return False

    if reviewer_tenant_id == case_tenant_id:
        return True

    ancestors = ancestor_chain(case_tenant_id, parent_map)
    if ancestors is None:
        return False

    return reviewer_tenant_id in ancestors

def emit_case_event_model(case_id, tenant_id, actor_id, action, metadata=None):
    return {
        "caseId": case_id,
        "tenantId": tenant_id,
        "actorId": actor_id,
        "action": action,
        "metadata": metadata or {},
    }

# Delegated reviewer rule checks
assert can_delegated_reviewer_approve("t-child-a", "t-child-a", tenant_parent) is True
assert can_delegated_reviewer_approve("t-child-a", "t-parent", tenant_parent) is True
assert can_delegated_reviewer_approve("t-grandchild-a1", "t-child-a", tenant_parent) is True
assert can_delegated_reviewer_approve("t-grandchild-a1", "t-parent", tenant_parent) is True

# Sibling and child-to-parent must be denied
assert can_delegated_reviewer_approve("t-child-a", "t-child-b", tenant_parent) is False
assert can_delegated_reviewer_approve("t-parent", "t-child-a", tenant_parent) is False
assert can_delegated_reviewer_approve("t-child-a", "t-unrelated", tenant_parent) is False

# Compatibility invariant: event top-level keys do not change
event = emit_case_event_model(
    "case-1",
    "t-child-a",
    "actor-1",
    "export_blocked",
    metadata={
        "audit": {
            "aiDrafted": True,
            "humanApproval": {"status": "missing"},
            "policyDecision": {
                "result": "blocked",
                "reason": "human_review_required",
                "policyRegion": "jp",
            },
        }
    },
)

assert list(event.keys()) == TOP_LEVEL_EVENT_KEYS
assert event["metadata"]["audit"]["policyDecision"]["result"] == "blocked"

# Existing None metadata behavior
legacy_event = emit_case_event_model("case-2", "t1", "actor-2", "created", metadata=None)
assert list(legacy_event.keys()) == TOP_LEVEL_EVENT_KEYS
assert legacy_event["metadata"] == {}
```

このモデルで防ぐもの:

- sibling tenant approval の再発。
- event top-level schema 破壊。
- `metadata=None` behavior の regression。

---

## 6. 実装・テスト・リリース計画

### Phase 0: Contract freeze

- `normalizeRecipient` の signature / export path を freeze。
- `emit_case_event` の top-level keys を freeze。
- `ReviewModal` の accessibility contract を freeze。
- DPA / docs の禁止表現を定義。
  - 禁止: 「data stays in Japan」
  - 許可: 「review/export policy controls」

成果物:

- API compatibility tests
- event schema golden tests
- plugin smoke test
- accessibility regression tests
- legal copy review checklist

---

### Phase 1: Policy model を追加

追加する設計要素:

- tenant policy config
- policy resolver
- action classifier
  - internal action
  - customer-facing send/export
- export policy evaluator
- redaction enforcement point

注意:

- `DEFAULT_POLICY` は legacy default として維持。
- policy 未設定 tenant には既存 behavior を適用。
- JP/EU policy は feature flag / allowlist でのみ有効化。

テスト:

- tenant policy lookup
- unset policy fallback
- JP/EU requireHumanReview
- US/default no required review
- redacted export enforcement

---

### Phase 2: Delegated reviewer authorization

追加する設計要素:

- tenant hierarchy service / repository
- explicit reviewer grant
- approval record
- authorization function

deny-safe 条件:

- unknown tenant
- broken hierarchy
- cyclic hierarchy
- missing reviewer grant
- sibling tenant
- child-to-parent approval

テスト:

- same tenant allow
- parent/ancestor allow
- sibling deny
- unrelated deny
- child-to-parent deny
- corrupted hierarchy deny
- production incident reproduction test

---

### Phase 3: Audit event enrichment

方針:

- `emit_case_event` は top-level schema unchanged。
- audit fields は `metadata.audit` に入れる。
- blocked action も event 化する。
- downstream indexer は `metadata.audit.policyDecision.result` を index。

テスト:

- exact top-level keys
- `metadata=None` remains `{}`
- AI drafted event has `aiDrafted=true`
- approved event has approval status/reviewer
- blocked event has policy reason
- existing consumers ignore additive metadata

---

### Phase 4: UI integration

方針:

- `ReviewModal` primitive を壊さず、reviewer selector は child として追加。
- close button の DOM order と keyboard reachability を維持。
- approval required の場合のみ reviewer selection / approval UI を表示。
- blocked reason を UI に表示。

テスト:

- close button keyboard click
- dialog role exists
- reviewer selector 表示後も close reachable
- Shift+Tab で close に戻れる
- Escape close がある場合は regression test
- screen reader accessible name / label

---

### Phase 5: Legal / compliance alignment

作業:

- DPA addendum 修正案を legal review。
- product docs / admin UI / CS
~~~

### Output: with_fairy_tale

~~~text
## 1. コンパクト world model

### Entities

| Entity | 既存/新規 | 要点 |
|---|---:|---|
| `Recipient` | 既存 | `id`, `email`, `tenantId`, optional `role: owner/agent/viewer`。`normalizeRecipient(input)` は公開 helper。 |
| `Tenant` | 暗黙既存 | `tenantId` を持つ。今回 `parentTenantId` / tenant hierarchy が重要になる。 |
| `PolicyPack` | 既存拡張対象 | `region: jp/eu/us`, `allowAiDraft`, `requireHumanReview`, `exportMode: full/redacted`。 |
| `Case` / intake | 暗黙既存 | AI draft、review、send/export、audit event の対象。 |
| AI draft | 既存機能 | JP/EU でも生成可能。ただし customer-facing send/export 前に承認が必要。 |
| Delegated reviewer | 新規 | case tenant と同一 tenant、または parent/ancestor tenant に所属する reviewer。sibling tenant は不可。 |
| Approval | 新規 | reviewer、対象 case、対象 tenant、policy version/source、承認時刻を持つべき。 |
| Case event / audit log | 既存 | envelope keys は `caseId`, `tenantId`, `actorId`, `action`, `metadata`。top-level 追加は既存 consumer を壊す。 |
| `ReviewModal` | 既存 UI | `role="dialog"`、close button が keyboard 操作可能であることが契約。 |
| DPA / customer wording | 既存契約 | “region-specific configurations where enabled” はあるが、data residency は未実装。 |

---

### Actions

| Action | 説明 |
|---|---|
| `normalizeRecipient(input)` | string または Recipient を既存形式に normalize。policy を必須引数にしてはいけない。 |
| enable policy pack | tenant 単位、または明示された継承ルールに基づいて regional policy を有効化。 |
| generate AI draft | `allowAiDraft` が true なら生成。JP/EU でも生成は許可され得る。 |
| request send/export | customer-facing action。policy によって承認必須・redaction 必須の gate を通す。 |
| approve by delegated reviewer | reviewer tenant が case tenant と同一、または parent/ancestor の場合のみ許可。 |
| block by policy | 承認なし、権限なし、redaction 未適用などの場合 block し audit に残す。 |
| emit audit event | top-level envelope は維持し、policy/approval 情報は `metadata` 内に additive に入れる。 |
| ReviewModal 操作 | reviewer selector 追加後も close button が keyboard reachable であること。 |

---

### State transitions

```text
Case created
  -> AI draft generated
      metadata.auditOutcome = "ai_drafted"

AI draft generated
  -> Pending human review
      if effectivePolicy.requireHumanReview === true

Pending human review
  -> Approved
      if reviewer is same tenant or parent/ancestor tenant
      metadata.auditOutcome = "human_approved"

Pending human review
  -> Blocked
      if reviewer is sibling/child/unrelated tenant, or no approval before send/export
      metadata.auditOutcome = "policy_blocked"

Approved
  -> Exported/Sent
      if exportMode === "redacted", redaction must be applied before external export

US/default/no-review-required path
  -> Exported/Sent
      existing behavior preserved unless explicit policy says otherwise
```

---

### Existing contracts recovered from artifacts

#### Public API

- `normalizeRecipient(input: string | Recipient): Recipient` is public.
- Import path `packages/api/src/recipient` is used by customer plugins.
- String input maps to:
  - `id = input.toLowerCase()`
  - `email = input.toLowerCase()`
  - `tenantId = "legacy-default"`
- Object input preserves `tenantId`.
- Existing callers must not be forced to pass `policy`.

#### Event envelope

- `emit_case_event(..., metadata=None)` returns `metadata: {}`.
- Top-level keys are exactly:

```python
["caseId", "tenantId", "actorId", "action", "metadata"]
```

- Adding `policy` or `approval` top-level fields breaks existing consumers.

#### UI behavior

- `ReviewModal` must render `role="dialog"` when open.
- Close button must remain keyboard reachable/clickable.
- Adding reviewer selector must not create an inaccessible focus trap or steal focus permanently.

#### Legal/customer-facing wording

- Current DPA says provider supports region-specific configurations where enabled.
- It does **not** promise data residency.
- Customer remains responsible for final decisions based on AI outputs.
- CS claim “regional policy pack means data stays in Japan” is currently false relative to implementation.

---

### New policy constraints

1. Customers can enable regional policy pack per tenant.
2. JP/EU:
   - AI drafts may be generated.
   - customer-facing send/export requires delegated reviewer approval.
3. Delegated reviewer authorization:
   - same tenant: allowed.
   - parent/ancestor tenant: allowed, if product confirms ancestor semantics.
   - sibling tenant: denied.
   - child tenant approving parent: denied unless separately designed.
4. `policy.exportMode === "redacted"`:
   - export must be redacted.
   - should be audit-visible.
5. Audit logs must show:
   - AI-drafted,
   - human-approved,
   - blocked by policy.

---

### Unsafe assumptions

| Assumption | Risk |
|---|---|
| `parentTenantId` can be treated as a flat group id | Already caused sibling approval incident. Must not repeat. |
| Regional policy pack implies data residency | Legally/customer-facing incorrect. Engineering does not implement storage/processing location control. |
| Adding required `policy` argument to `normalizeRecipient` is safe | Breaks API, plugins, tests. |
| Adding top-level event fields is safe | Breaks event consumers expecting exact keys. |
| Reviewer can be represented by extending `Recipient.role` | May break role exhaustiveness or customer plugin assumptions. Prefer separate delegation model. |
| Local UI test passing means accessibility is preserved | Need keyboard traversal/focus tests with selector present. |
| Parent policy automatically applies to all children | Not specified. Needs explicit product/legal decision. |

---

## 2. Shared latent invariant across code, events, UI, and legal/compliance

**Shared invariant: new governance controls must be additive, tenant-scoped, auditable, and truthfully represented, without weakening or reshaping existing public contracts.**

Concretely:

- API: add context-aware wrappers, do not break `normalizeRecipient(input)`.
- Events: add governance details inside `metadata` or via versioned/new events, do not mutate existing envelope.
- UI: add reviewer workflow, do not remove keyboard access to existing controls.
- Tenant hierarchy: add delegated approval, do not collapse hierarchy into a flat group.
- Legal: advertise only implemented controls; do not claim data residency from review/export policy.

---

## 3. Smallest compatible design

### 3.1 Public API strategy

Do **not** change:

```ts
normalizeRecipient(input: string | Recipient): Recipient
```

Keep import path:

```ts
packages/api/src/recipient
```

Add separate wrappers/utilities instead:

```ts
type RecipientContext = {
  tenantId?: string;
  policy?: PolicyPack;
  source?: "api" | "worker" | "plugin" | "ui";
};

function normalizeRecipientWithContext(
  input: string | Recipient,
  context?: RecipientContext
): {
  recipient: Recipient;
  effectivePolicy?: PolicyPack;
};
```

or even smaller:

```ts
const recipient = normalizeRecipient(input);
const policy = resolveTenantPolicy(recipient.tenantId);
```

Preferred: **do not couple recipient normalization with policy resolution**. Recipient normalization is identity/email cleanup; policy is tenant governance.

Compatibility rules:

- No required new parameter.
- No import path move.
- No role union change for delegated reviewer.
- Add reviewer delegation as a separate domain object, for example:

```ts
type ReviewerDelegation = {
  reviewerUserId: string;
  reviewerTenantId: string;
  targetTenantId: string;
  scope: "case_export_approval";
};
```

---

### 3.2 Policy resolution

Add explicit effective policy resolver:

```ts
function resolveEffectivePolicy(tenantId: string): {
  policy: PolicyPack;
  sourceTenantId: string;
  inherited: boolean;
  version: string;
};
```

Design choices:

- Default remains `DEFAULT_POLICY`.
- Tenant-level policy is explicit.
- Parent inheritance must be explicit or documented.
- Audit should record:
  - `policy.region`
  - `policy.exportMode`
  - `policy.requireHumanReview`
  - `policySourceTenantId`
  - `policyVersion`

For JP/EU packs, the configured pack should likely be:

```ts
{
  region: "jp" | "eu",
  allowAiDraft: true,
  requireHumanReview: true,
  exportMode: "redacted" // if product/legal requires; otherwise configurable
}
```

But note: `exportMode` is independent in the current type, so tests should not assume all JP/EU are automatically redacted unless product confirms.

---

### 3.3 Event schema strategy

Keep existing function and top-level shape:

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

Add governance data inside `metadata`:

```json
{
  "caseId": "c1",
  "tenantId": "t-child",
  "actorId": "u-reviewer",
  "action": "export_blocked",
  "metadata": {
    "governance": {
      "schemaVersion": 1,
      "auditOutcome": "policy_blocked",
      "aiDrafted": true,
      "humanApproved": false,
      "blockedReason": "reviewer_not_authorized",
      "policy": {
        "region": "jp",
        "requireHumanReview": true,
        "exportMode": "redacted",
        "sourceTenantId": "t-parent",
        "version": "2025-xx"
      },
      "approval": {
        "reviewerTenantId": "t-sibling",
        "targetTenantId": "t-child",
        "authorized": false
      }
    }
  }
}
```

Use wrapper for new events:

```python
def emit_governance_case_event(..., governance=None, metadata=None):
    base_metadata = metadata or {}
    if governance is not None:
        base_metadata["governance"] = governance
    return emit_case_event(..., metadata=base_metadata)
```

Important:

- Do not add top-level `policy`.
- Do not add top-level `approval`.
- Old events without `metadata.governance` are valid legacy events.
- Audit readers should handle missing governance metadata as `legacy_unknown`, not failure.

---

### 3.4 Delegated reviewer authorization rule

Minimum safe rule:

```text
A reviewer may approve an action for targetTenantId only if:

reviewerTenantId == targetTenantId
OR
reviewerTenantId is an ancestor of targetTenantId in the tenant hierarchy.

Never allow:
- sibling tenant,
- cousin tenant,
- child tenant approving parent,
- unrelated tenant,
- cyclic hierarchy traversal.
```

Implementation guidance:

- Use an actual tenant tree traversal.
- Do not compare only `parentTenantId`.
- Do not treat all tenants with same parent as equivalent.
- Add cycle detection.
- Add maximum traversal depth or visited set.
- Record decision reason:

```ts
type DelegatedReviewerDecision =
  | { allowed: true; reason: "same_tenant" | "ancestor_tenant" }
  | { allowed: false; reason: "sibling_tenant" | "child_tenant" | "unrelated_tenant" | "cycle_detected" | "unknown_tenant" };
```

Also require reviewer assignment/capability, not just tenant relationship:

```text
tenant relationship allowed
AND reviewer has delegated approval permission
AND approval scope matches action
```

The hierarchy rule is necessary but not sufficient.

---

### 3.5 Send/export gate

Before customer-facing send/export:

```text
1. Resolve effective policy.
2. If policy.requireHumanReview:
     require valid approval for this case/action/policy version.
3. If approval missing/invalid:
     block and audit as policy_blocked.
4. If policy.exportMode == "redacted":
     apply redaction.
     verify redaction applied before export.
5. Emit audit event with governance metadata.
```

Important invariant:

```text
No customer-facing export may occur under a redacted policy unless redactionApplied == true.
```

---

### 3.6 ReviewModal accessibility and keyboard preservation

Do not restructure modal in a way that hides or bypasses the close button.

Recommended behavior:

- Keep:

```tsx
<div role="dialog" aria-modal="true">
  <button aria-label="Close">x</button>
  ...
</div>
```

- Add reviewer selector with explicit label:

```tsx
<label htmlFor="reviewer">Delegated reviewer</label>
<select id="reviewer" ... />
```

- Ensure:
  - close button remains in tab order,
  - selector is reachable,
  - focus trap, if present, cycles through all interactive controls,
  - `Esc` close can be added, but do not rely on it as the only close path,
  - initial focus behavior is deterministic and tested.

Tests:

- `role="dialog"` exists.
- close button found by role/name and can be clicked via keyboard.
- tab order includes close button and reviewer selector.
- after selector appears, close button is still reachable.
- screen reader labels exist for selector.

---

### 3.7 DPA / customer-facing wording correction

Current implementation supports:

- region-specific workflow policy,
- human review requirements,
- export redaction behavior,
- audit metadata.

Current implementation does **not** support:

- data residency,
- storage only in Japan,
- processing only in Japan,
- model execution location guarantees.

Suggested wording:

```text
Regional policy packs configure region-specific AI workflow controls, such as
human review requirements, export redaction settings, and audit metadata where
enabled in the product. Regional policy packs do not, by themselves, control or
guarantee the geographic location of data storage, subprocessors, model
execution, or processing unless separately stated in the applicable agreement or
product documentation.
```

Customer remediation:

- Correct CS enablement materials before launch.
- Notify affected JP customer that “data stays in Japan” is not currently implemented.
- Do not market JP policy pack as residency.
- If residency is required, treat it as a separate product/legal/security project.

---

## 4. Validation matrix

| Surface | Tacit contract | New behavior | Test or probe | Failure prevented |
|---|---|---|---|---|
| `normalizeRecipient` API | Signature remains `normalizeRecipient(input)` | Policy support added outside normalization | Unit test old cases; TypeScript API snapshot; plugin smoke import from `packages/api/src/recipient` | Missing `policy` argument; broken customer plugins |
| Recipient import path | Plugins import existing path | No move/rename; wrappers exported additively | Build packaged artifact and run customer-plugin smoke test | `Cannot import normalizeRecipient` |
| String recipient normalization | string maps to lowercase id/email and `tenantId: legacy-default` | No policy lookup for string-only legacy callers | Existing tests unchanged | Legacy default tenant behavior broken |
| Object recipient normalization | Preserves `tenantId`; lowercases email | No implicit tenant override from policy | Existing test plus object with parent tenant | Tenant misassignment |
| Policy resolution | `DEFAULT_POLICY` is US/full/no review | Tenant can enable regional pack | Tests for no-config tenant returning default | Existing US customers unexpectedly gated |
| JP/EU review gate | Not existing | Send/export requires valid human approval | State-machine tests: no approval => blocked; approval => allowed | Unreviewed customer-facing export |
| AI draft generation | Existing AI draft behavior | JP/EU may still generate drafts | Test JP/EU `allowAiDraft=true` creates draft but marks pending review | Over-blocking draft generation |
| Export redaction | Existing full export may exist | `exportMode=redacted` forces redaction | Export integration test validates redactionApplied before emit/send | Unredacted regulated export |
| Event envelope | Top-level keys exactly `caseId`, `tenantId`, `actorId`, `action`, `metadata` | Governance metadata nested under `metadata.governance` | Existing event key test; replay old consumers against new events | Broken event consumers |
| Event metadata default | `metadata=None` returns `{}` | Wrapper still delegates to old function | Existing Python unit test | Null metadata errors |
| Audit classification | Not previously required | Must show `ai_drafted`, `human_approved`, `policy_blocked` | Audit query tests for all three outcomes | Non-compliant audit trail |
| Old events | Lack governance metadata | Readers must treat as legacy/unknown | Replay sample historical events | Backfill/replay failures |
| Delegated reviewer hierarchy | Parent/child relationship implicit | Same tenant or ancestor only | Tenant tree fixtures: same allowed, parent allowed, sibling denied, child denied | Cross-child approval incident |
| Tenant hierarchy robustness | No flat group semantics | Detect cycles/unknown tenants | Tests for cycle and missing tenant | Infinite loop or accidental allow |
| Reviewer capability | `Recipient.role` has limited union | Delegation modeled separately | Auth tests require both hierarchy and explicit permission | Any parent user can approve |
| ReviewModal role | `role="dialog"` when open | Reviewer selector added | Existing RTL test | Dialog semantics lost |
| ReviewModal keyboard | Close button keyboard reachable | Selector must not trap/steal focus | RTL/user-event tab test with selector visible | Prior failure: close unreachable |
| Legal/DPA wording | Region config exists, final decision remains customer responsibility | Clarify no data residency guarantee | Legal review checklist; CS script approval | False residency claim |
| Release rollout | Existing tenants unaffected | Feature flagged tenant policy pack | Canary tenant; shadow audit before enforcement | Broad accidental enforcement |
| Production monitoring | Existing logs/events consumed | New blocked/approved metrics | Dashboards: blocked count, approval denial reasons, redactionApplied | Silent policy failures |

---

## 5. Checkable model: delegated reviewer rule + event compatibility invariant

Python-like executable pseudocode:

```python
EVENT_KEYS = ["caseId", "tenantId", "actorId", "action", "metadata"]

def emit_case_event(case_id, tenant_id, actor_id, action, metadata=None):
    return {
        "caseId": case_id,
        "tenantId": tenant_id,
        "actorId": actor_id,
        "action": action,
        "metadata": metadata or {},
    }


# tenant_id -> parent_tenant_id
TENANTS = {
    "t-parent": None,
    "t-child-a": "t-parent",
    "t-child-b": "t-parent",
    "t-grandchild": "t-child-a",
    "t-unrelated": None,
}


def is_ancestor(possible_ancestor_id, tenant_id, tenants):
    """
    True only if possible_ancestor_id is on tenant_id's parent chain.
    Siblings are not ancestors of each other.
    """
    visited = set()
    current = tenants.get(tenant_id)

    while current is not None:
        if current in visited:
            raise ValueError("cycle_detected")
        visited.add(current)

        if current == possible_ancestor_id:
            return True

        current = tenants.get(current)

    return False


def reviewer_tenant_allowed(reviewer_tenant_id, target_tenant_id, tenants):
    if reviewer_tenant_id not in tenants or target_tenant_id not in tenants:
        return False

    if reviewer_tenant_id == target_tenant_id:
        return True

    return is_ancestor(reviewer_tenant_id, target_tenant_id, tenants)


def test_delegated_reviewer_rule():
    # Same tenant is allowed.
    assert reviewer_tenant_allowed("t-child-a", "t-child-a", TENANTS) is True

    # Parent/ancestor is allowed.
    assert reviewer_tenant_allowed("t-parent", "t-child-a", TENANTS) is True
    assert reviewer_tenant_allowed("t-parent", "t-grandchild", TENANTS) is True
    assert reviewer_tenant_allowed("t-child-a", "t-grandchild", TENANTS) is True

    # Sibling is never allowed.
    assert reviewer_tenant_allowed("t-child-a", "t-child-b", TENANTS) is False
    assert reviewer_tenant_allowed("t-child-b", "t-child-a", TENANTS) is False

    # Child cannot approve parent.
    assert reviewer_tenant_allowed("t-child-a", "t-parent", TENANTS) is False

    # Unrelated tenant is denied.
    assert reviewer_tenant_allowed("t-unrelated", "t-child-a", TENANTS) is False


def test_event_envelope_compatibility():
    event = emit_case_event(
        "case-1",
        "t-child-a",
        "user-1",
        "export_blocked",
        metadata={
            "governance": {
                "schemaVersion": 1,
                "auditOutcome": "policy_blocked",
                "approval": {
                    "reviewerTenantId": "t-child-b",
                    "targetTenantId": "t-child-a",
                    "authorized": False,
                },
            }
        },
    )

    # Compatibility invariant: no new top-level keys.
    assert list(event.keys()) == EVENT_KEYS

    # New fields are additive and nested.
    assert "governance" in event["metadata"]
    assert "policy" not in event
    assert "approval" not in event


if __name__ == "__main__":
    test_delegated_reviewer_rule()
    test_event_envelope_compatibility()
    print("ok")
```

This model falsifies the most important incident-prone invariant:

```text
siblings sharing the same parent must not be able to approve each other's exports
```

and one compatibility invariant:

```text
new governance data must not change event top-level keys
```

---

## 6. Release and rollout plan

### Phase 0: Contract inventory

- Freeze current public API signatures and import paths.
- Snapshot event envelope.
- Snapshot ReviewModal keyboard behavior.
- Review DPA, public docs, CS scripts.

### Phase 1: Additive implementation behind feature flag

- Add `resolveEffectivePolicy`.
- Add `ReviewerDelegation` / approval service separately from `Recipient`.
- Add `emit_governance_case_event` wrapper using `metadata.governance`.
- Add UI reviewer selector behind flag.
- Add audit reader support for both old and new events.

### Phase 2: Shadow mode

For selected tenants:

- Resolve policy.
- Evaluate whether export would require approval.
- Evaluate redaction requirement.
- Emit internal-only/shadow audit metadata.
- Do not block yet.

Validate:

- no unexpected top-level event schema changes,
- no plugin import failures,
- no spike in UI accessibility regressions,
- no false sibling approvals.

### Phase 3: Enforcement canary

- Enable blocking for one internal/test tenant.
- Then one consenting customer tenant.
- Monitor:
  - blocked-by
~~~

### Result Interpretation

The observed delta is small: **+1 point** for the Fairy Tale condition on this
single run. The useful signal is not a broad quality jump. The prompt itself
already forced many generalization behaviors, so the control answer recovered
most tacit contracts.

The Fairy Tale condition still showed a measurable advantage in one important
place: it stated the shared invariant more directly and tied it more consistently
to the cross-surface design. For this use case, the correct interpretation is:

- Fairy Tale did not rescue a weak baseline; the baseline was already strong.
- Fairy Tale improved explicit invariant framing and transfer discipline.
- The use case remains valid for future runs because it can reveal whether a
  weaker baseline breaks API, event, UI, tenant, or compliance contracts.
- Promotion to a benchmark claim requires repeated runs, preferably with less
  leading task wording or a held-out variant.

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

## Measured n=1 Less-Leading v2 Comparison

Date: 2026-06-16

### Why v2 Exists

The first measured run was useful, but the user prompt directly asked for
several mechanisms that Fairy Tale is supposed to recover: latent invariants,
implicit contracts, and a checkable model. That made the baseline unusually
strong and reduced the space where generalization could show up.

This v2 run removes those mechanism labels from the user prompt. The prompt is
still artifact-rich, but it asks for an ordinary design-review deliverable:
what to change, what to test, release risks, and only necessary questions.
The hidden evaluator still checks whether the answer recovers the transferable
structure.

### Run Conditions

- Model: `gpt-5.5`
- API: OpenAI Responses API
- Reasoning effort: `medium`
- Samples: one less-leading prompt x two conditions
- Without condition: careful senior engineer design-review system guidance
- With condition: same user prompt plus Fairy Tale generalization harness process guidance
- Judge: `gpt-5.5`, same API path, hidden rubric
- Artifact IDs:
  - without: `resp_0ba5ef70ed227483006a30ce34d61081988543b3cfec7deaa9`
  - with: `resp_07025025e9fb8d8f006a30ce77f1808198865ce89f469ce719`
  - judge: `resp_0b6af03ac79d1054006a30cefd4618819ba1303a9ba9ae44ca`

### v2 User Prompt

~~~text
あなたは次のrepo断片を引き継いだエンジニアです。
新しいPRを作る前に、設計レビューとして「どう進めるべきか」「何をテストすべきか」「どこをリリース前に確認すべきか」をまとめてください。
コード実装そのものではなく、レビューコメント/実装方針として返してください。

状況:
enterprise AI intake platformに、tenantごとのregional policy packとdelegated reviewerを追加したい。
既存顧客の連携は壊したくないが、どこが壊れやすいかはまだ整理できていない。

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
```text
- Customers can enable a regional policy pack per tenant.
- In JP/EU policy packs, AI drafts may still be generated, but a delegated reviewer must approve before customer-facing send/export.
- A delegated reviewer may belong to the same tenant or a parent tenant, but never a sibling tenant.
- Export must be redacted when policy.exportMode is "redacted".
- Audit logs must show whether an action was AI-drafted, human-approved, or blocked by policy.
- Existing integrations that call normalizeRecipient(input) must keep working.
- Existing event consumers must keep working.
- Existing ReviewModal keyboard behavior must keep working.
```

Previous failed PR notes:
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

Incident note:
After enabling jp policy for tenant t-parent, two child tenants could approve each other's exports because parentTenantId was treated as a flat group id.

Customer note:
A JP customer was told "regional policy pack means data stays in Japan", but engineering only implemented review/export behavior. No storage or processing location control exists yet.
```

Deliverable:
- Proposed design direction.
- Tests/probes to add before merging.
- Rollout/release risks.
- Clarifying questions, only where the repo notes are insufficient.
~~~

### Hidden Evaluator Rubric

~~~text
Hidden evaluator rubric for this less-leading v2 run.

The user prompt intentionally does not name world models, tacit contracts, latent invariants, or executable verification. A strong answer should still recover them from artifacts.

Score each answer out of 100:

| Category | Points | Hidden expectation |
|---|---:|---|
| Artifact-grounded model | 15 | Identifies entities/actions/state-like lifecycle enough to reason across API, worker events, UI, tenant auth, and customer-facing wording. Does not need the phrase "world model". |
| Shared invariant recovery | 15 | Explicitly or operationally identifies: add policy/review behavior as an additive layer while preserving legacy signatures, imports, event envelope, keyboard behavior, tenant hierarchy semantics, and truthful compliance claims. |
| Tacit contract recovery | 20 | Recovers public helper signature/import path, exact event top-level shape, modal keyboard/close affordance, directional parent-child delegation, and the fact that regional policy is not data residency. |
| Checkable verifier or probes | 15 | Provides a small executable/pseudocode model or concrete test fixtures that catch sibling approval and at least one compatibility invariant. High-level "add tests" alone is insufficient. |
| Validation matrix / coverage map | 15 | Maps surfaces to old behavior, new behavior, test/probe, and failure prevented. A table is not required, but coverage must be systematic. |
| Assumption governance | 10 | Separates confirmed prompt facts, inferred requirements, risky assumptions, and questions/blockers. Does not ask unnecessary questions where artifacts already answer. |
| Minimal compatible design | 10 | Keeps existing helpers/events/modal behavior intact through wrappers/metadata/versioning/focused additions; avoids broad rewrites and customer-facing overclaims. |

Expected high-value findings:
- normalizeRecipient(input) and import path are public contracts; do not add required policy argument or move export.
- Existing string behavior returns legacy-default; do not silently reinterpret it.
- emit_case_event top-level keys are asserted; policy/approval should be nested under metadata or put in a versioned/secondary stream.
- Parent-child delegation is directional; siblings sharing a parent are not authorized.
- ReviewModal close button and keyboard reachability must remain tested after reviewer selector is added.
- Regional policy pack is review/export policy, not data residency without storage/processing controls.

Return:
1. A score table with both answers.
2. Total score and delta.
3. Item-level comparison.
4. Whether the v2 prompt meaningfully reduced hints compared with a prompt that asks directly for latent invariant/world model/checkable model.
~~~

### Comparison Evaluation

## 1. Score table

| Category | Points | Answer A | Answer B |
|---|---:|---:|---:|
| Artifact-grounded model | 15 | 15 | 15 |
| Shared invariant recovery | 15 | 15 | 15 |
| Tacit contract recovery | 20 | 20 | 20 |
| Checkable verifier or probes | 15 | 14 | 15 |
| Validation matrix / coverage map | 15 | 13 | 14 |
| Assumption governance | 10 | 8 | 10 |
| Minimal compatible design | 10 | 10 | 10 |
| **Total** | **100** | **95** | **99** |

**Delta:** Answer B +4 over Answer A.

---

## 2. Total score and delta

- **Answer A: 95/100**
- **Answer B: 99/100**
- **Delta: 4 points in favor of Answer B**

Both answers are very strong and recover the important hidden expectations. Answer B is slightly better because it more explicitly separates confirmed facts, inferred requirements, risky assumptions, and blockers, and it gives a clearer invariant/model framing with more concrete pseudo-model language.

---

## 3. Item-level comparison

### Artifact-grounded model

Both answers correctly identify the relevant surfaces:

- API helper: `normalizeRecipient`
- Worker event envelope: `emit_case_event`
- Web modal accessibility contract: `ReviewModal`
- Tenant policy and reviewer delegation
- Export redaction
- Audit logging
- Customer/legal wording around regional policy

**Result:** tie. Both deserve full credit.

---

### Shared invariant recovery

Both recover the key compatibility invariants:

- Do not change `normalizeRecipient(input)` signature.
- Do not move or remove the public import path.
- Preserve string input behavior returning `tenantId: "legacy-default"`.
- Do not change event top-level shape.
- Put policy/approval/audit data under `metadata` or a v2/secondary event.
- Preserve ReviewModal close button keyboard reachability.
- Enforce parent-child reviewer authorization directionally.
- Do not claim regional policy implies data residency.

**Result:** tie. Full credit for both.

---

### Tacit contract recovery

Both answers explicitly recover the hidden public/tacit contracts:

- `normalizeRecipient(input: string | Recipient): Recipient` is public.
- Existing plugin import path is a contract.
- Existing event keys must remain exactly `caseId`, `tenantId`, `actorId`, `action`, `metadata`.
- `metadata=None` must remain `{}`.
- Close button keyboard accessibility remains a modal contract.
- Parent/ancestor delegation is not sibling delegation.
- Regional policy pack is not data residency.

Answer B is a little more explicit about `normalizeRecipient.length`, role union breakage, and metadata-shape consumer risk, but Answer A still covers all mandatory elements.

**Result:** both full credit.

---

### Checkable verifier or probes

Answer A gives many concrete tests and fixtures, including:

```text
t-parent
  ├─ t-child-a
  └─ t-child-b
```

and explicitly requires sibling approval regression tests plus compatibility tests for `normalizeRecipient`, events, and ReviewModal.

Answer B does the same, but also states a crisp invariant:

```text
canApprove(caseTenant, reviewerTenant) is true iff
  reviewerTenant == caseTenant
  OR reviewerTenant is ancestor of caseTenant.
```

This is closer to the expected “small model / verifier” recovery. It is still not fully executable, but it is operational enough and paired with concrete fixtures.

**Result:** Answer B slightly stronger.
A: 14/15, B: 15/15.

---

### Validation matrix / coverage map

Neither answer gives a literal matrix mapping each surface to old behavior, new behavior, test/probe, and failure prevented. However, both provide systematic coverage across:

- recipient compatibility
- event compatibility
- ReviewModal accessibility
- policy resolution
- approval gate
- tenant hierarchy authorization
- export redaction
- audit logging
- rollout risks
- customer messaging

Answer B’s structure is more systematic: it includes invariants, tests, release risks, rollout plan, and PR breakdown. Answer A is also comprehensive but less explicitly organized as a coverage map.

**Result:** Answer B slightly stronger.
A: 13/15, B: 14/15.

---

### Assumption governance

Answer A includes clarifying questions and identifies risk areas, but it does not clearly separate:

- confirmed prompt facts
- inferred requirements
- risky assumptions
- blockers

It does not ask unnecessary questions, and the questions are relevant, so it scores well but not perfectly.

Answer B explicitly starts with:

- confirmed facts
- inferred requirements
- dangerous assumptions

and later separates release-blocking questions from non-blocking clarifications. This maps very directly to the rubric.

**Result:** Answer B clearly stronger.
A: 8/10, B: 10/10.

---

### Minimal compatible design

Both answers recommend an additive, compatibility-preserving implementation:

- keep existing helper
- add separate policy resolver
- keep event top-level schema
- add metadata or v2 audit stream
- enforce on API/worker, not only UI
- feature flag rollout
- avoid overclaiming residency
- avoid broad rewrites

Answer B adds a useful staged PR plan, but Answer A also meets the category fully.

**Result:** tie. Full credit for both.

---

## 4. Did the v2 prompt meaningfully reduce hints?

Yes, the v2 prompt meaningfully reduced direct conceptual hints compared with a prompt that explicitly asks for “latent invariants,” “world model,” or “checkable model.”

However, the repo artifacts and failure notes still strongly point to the expected conclusions. The prompt does not name the concepts, but it gives enough concrete evidence for a strong respondent to infer them:

- Failed `normalizeRecipient(policy)` call reveals public signature invariant.
- Failed plugin import reveals import-path contract.
- Failed event-key assertion reveals event envelope invariant.
- Failed ReviewModal keyboard test reveals accessibility contract.
- Incident note reveals directional tenant hierarchy invariant.
- Customer note reveals regional-policy-vs-data-residency distinction.

So the v2 prompt is less leading at the terminology level, but still artifact-rich. It effectively tests whether the respondent can recover the invariants from evidence rather than from named abstractions. Both answers did recover them; Answer B did so with slightly more explicit assumption governance and model-like invariants.

### v2 Result Interpretation

The less-leading v2 run produced a larger measured gap than v1:

| Condition | Score |
|---|---:|
| Without Fairy Tale | 95 / 100 |
| With Fairy Tale | 99 / 100 |
| Delta | +4 |

This is still an `n=1` reference sample, not a benchmark claim. The useful
signal is qualitative: removing direct mechanism labels did not prevent the
control answer from recovering most obvious contracts, but the Fairy Tale
condition was stronger on assumption governance, model-like invariants, and
systematic validation coverage.

The remaining caveat is that the prompt still includes rich failure evidence.
That is intentional for this sample because the task targets artifact-based
generalization, not blind puzzle solving. A harder held-out variant should
remove some failure notes and test whether the process still reconstructs the
same contracts from neighboring artifacts.

### Full Output: Without Fairy Tale v2

~~~text
## 1. Proposed design direction

### Backward compatibilityを最優先にする
過去PRの失敗から、まず以下は破らない方針にすべきです。

- `normalizeRecipient(input)` の既存シグネチャは変更しない
  - `policy` などを必須引数にしない
  - customer pluginが `packages/api/src/recipient` から import できる状態を維持する
- `emit_case_event(...)` のトップレベルキーは変更しない
  - 既存キーは必ず `caseId, tenantId, actorId, action, metadata`
  - `policy` や `approval` はトップレベルに追加しない
  - 必要な監査情報は `metadata` 配下に追加する
- `ReviewModal` の既存keyboard操作を維持する
  - reviewer selector追加後もClose buttonがキーボード到達可能であること

### PolicyはRecipient正規化から分離する
`normalizeRecipient` は既存の public helper なので、policy解決やreviewer判定を混ぜるべきではありません。

推奨方針:

- `normalizeRecipient` は現状維持
- tenantごとのpolicy取得は別レイヤーに切り出す
  - 例: `getPolicyForTenant(tenantId)`
  - 未設定tenantは `DEFAULT_POLICY`
- policy適用は send/export/review workflow 側で行う
- Recipientの正規化とpolicy enforcementを結合しない

これにより、既存API・worker・tests・customer pluginの破壊リスクを抑えられます。

### Regional policy packは「review/export制御」として明確化する
現在のcontract文言とcustomer noteを見る限り、実装済みまたは今回実装予定の範囲は以下です。

- JP/EU policy:
  - AI draft生成は許可される場合がある
  - customer-facing send/export前にdelegated reviewer approvalが必須
- `policy.exportMode === "redacted"` の場合:
  - export payloadをredactedにする
- audit log:
  - AI-drafted
  - human-approved
  - blocked-by-policy
  を識別可能にする

ただし、**data residency / storage location / processing location control は未実装**です。
「regional policy pack = data stays in Japan」と誤認されるリスクがあるため、リリース前にproduct/legal/customer-facing messagingを修正すべきです。

### Delegated reviewer判定はtenant階層で厳密に行う
過去incidentでは `parentTenantId` をflat group扱いしたことで sibling tenant間のapprovalが可能になっています。

判定ルールは以下にすべきです。

- reviewer tenant == case/customer tenant: OK
- reviewer tenant is parent/ancestor of case tenant: OK
- reviewer tenant is sibling of case tenant: NG
- reviewer tenant is child of case tenant: 原則NG unless明示要件あり
- tenant hierarchyは単なる `parentTenantId` 一致ではなく、方向性のある ancestor check にする

特に以下のような誤判定を避ける必要があります。

```text
t-parent
  ├─ t-child-a
  └─ t-child-b
```

`t-child-a` のreviewerが `t-child-b` のexportをapproveできてはいけません。

### EnforcementはUIではなくserver/worker側で行う
ReviewModalやweb UIは補助であり、最終的なpolicy enforcementはAPI/worker側に置くべきです。

必須ゲート:

- send/export実行前にpolicyを解決
- policyがhuman review必須ならapproval recordを確認
- approval reviewerのtenant権限を確認
- 未承認ならblockedとしてaudit eventを出す
- export時は `exportMode` を見てredactionを強制

UIだけで制御するとAPI直叩きやworker経由で抜ける可能性があります。

### Audit eventはmetadata拡張で対応する
既存consumer互換性を維持するため、イベントのトップレベルshapeは固定します。

例として、監査情報は `metadata` 内に入れる方針が安全です。

```json
{
  "caseId": "...",
  "tenantId": "...",
  "actorId": "...",
  "action": "export_blocked",
  "metadata": {
    "audit": {
      "aiDrafted": true,
      "humanApproved": false,
      "blockedByPolicy": true,
      "policyRegion": "jp",
      "exportMode": "redacted"
    }
  }
}
```

注意点:

- metadataの追加は既存consumerが許容する前提だが、厳格schema consumerがいる可能性は確認する
- PIIやunredacted contentをmetadataに入れない
- reviewerIdを入れる場合も最小限にする

---

## 2. Tests / probes to add before merging

### Backward compatibility tests

#### `normalizeRecipient`
既存テストは維持し、追加で以下を確認します。

- `normalizeRecipient("USER@EXAMPLE.COM")` が引き続き動く
- 引数は1つで呼べる
- `tenantId: "legacy-default"` が維持される
- object入力時に `tenantId` が保持される
- `role` など既存optional fieldが壊れない
- customer plugin smoke importが通る
- public export pathが変わっていない

#### Events
既存consumer互換性として以下を固定します。

- `emit_case_event(...).keys()` が既存5キーのみ
- `metadata=None` は `{}` のまま
- policy/approval/audit情報を入れる場合もトップレベルキーは増えない
- metadata内に追加しても既存の空metadataケースが壊れない

#### ReviewModal
既存keyboard behaviorを維持するため、以下を追加します。

- reviewer selector表示後もClose buttonにTabで到達できる
- Close buttonがkeyboardでクリック可能
- dialog roleが維持される
- selector追加時にfocus trapやauto-focusがClose buttonを到達不能にしない
- `aria-modal="true"` が維持される

---

### Policy resolution tests

- policy未設定tenantは `DEFAULT_POLICY`
- tenantにJP policyを設定するとそのpolicyが返る
- tenantにEU policyを設定するとそのpolicyが返る
- tenantにUS/default policyを設定した場合のreview要否
- invalid region/configを拒否する
- policy変更後、send/export判定に反映される
- policy pack versionを持つならauditに記録される

---

### JP/EU approval gate tests

- JP policyでAI draft生成は可能
- JP policyで未承認send/exportはblocked
- JP policyで承認済みsend/exportは成功
- EU policyでも同様
- US/default policyでは既存挙動が維持される
- `requireHumanReview: true` のときはregionに関係なくgateされる
- `allowAiDraft: false` の場合はdraft生成自体がblockedされる
- blocked時にaudit logが出る
- approval済みでもpolicy変更後に再承認が必要かどうかを仕様化し、その通りテストする

---

### Delegated reviewer authorization tests

tenant treeを使ったテストを必ず入れるべきです。

```text
t-parent
  ├─ t-child-a
  └─ t-child-b
```

必要なケース:

- reviewer tenant == case tenant: approve OK
- reviewer tenant == parent tenant: approve OK
- reviewer tenant == sibling tenant: approve NG
- reviewer tenant == child tenant: approve NG
- unrelated tenant: approve NG
- parentのparentなどancestor tenantを許可するかどうか
  - 許可するならOKテスト
  - 許可しないならNGテスト
- tenant hierarchy cycleがある場合の防御
- deleted/disabled tenant reviewerはNG
- reviewer role/permissionが必要ならrole不足はNG

過去incident再発防止として、sibling approvalのregression testは必須です。

---

### Export redaction tests

- `exportMode: "redacted"` ではcustomer-facing export payloadがredactedされる
- `exportMode: "full"` では既存挙動が維持される
- audit metadataやevent payloadにunredacted dataが漏れない
- blocked export時にexport artifactが生成されない
- approval済みredacted exportでもredactionは維持される
- nested fields / attachments / free text / AI draft contentなどredaction対象の境界を確認する
- redaction失敗時はfail-closedにする

---

### Audit log tests

- AI draft生成時に `aiDrafted` が分かる
- human approval時に `humanApproved` が分かる
- policy block時に `blockedByPolicy` が分かる
- action名またはmetadataで状態を判別できる
- event top-level schemaは変わらない
- reviewer approval eventにtenant/reviewer情報が最小限入る
- export redacted/fullが監査上判別できる
- audit logにPIIやunredacted customer dataが入らない

---

### End-to-end / smoke probes

最低限、feature flag有効tenantと無効tenantでE2Eを分けて確認したいです。

- legacy tenant:
  - 既存API/plugin/event/UIが変わらない
- JP tenant:
  - draft生成
  - reviewer選択
  - approval
  - redacted export
  - audit確認
- sibling tenant:
  - approval拒否
  - auditにblocked記録
- direct API call:
  - UIを経由せずsend/exportしてもpolicy gateされる
- worker path:
  - worker経由のexport/sendでもpolicy gateされる

---

## 3. Rollout / release risks

### 互換性リスク
最も壊れやすい箇所は以下です。

- `normalizeRecipient` のsignature変更
- public import path変更
- event top-level schema変更
- metadata schemaを厳格に見ている外部consumer
- ReviewModalのfocus順序変更
- APIとworkerでpolicy enforcementが片方だけになること

対策:

- feature flag per tenant
- default off
- legacy tenantは既存挙動維持
- contract testsをCIに追加
- customer plugin smoke testをrelease gateにする

### Security / authorization risk
delegated reviewerのtenant判定は高リスクです。

特に以下はrelease前に必ず確認すべきです。

- sibling approvalが不可能
- parent/ancestor approvalの定義が明確
- reviewer role/permissionの確認
- approval recordの改ざん防止
- approval後に対象case/export内容が変わった場合の扱い
- race conditionで未承認exportが通らないこと

### Compliance / customer communication risk
JP customer noteがかなり重要です。

現状の実装範囲がreview/export policyだけなら、以下は明確にすべきです。

- data residencyは保証しない
- Japan内保存・処理を意味しない
- AI provider processing locationも制御しない
- product UI / docs / sales collateral / DPA文言の整合性を確認する

このまま「regional」と表現すると誤認リスクがあります。
必要なら名称を `regional review/export policy pack` などに寄せるべきです。

### Rollout方針
推奨:

1. schema/API互換性を守ったままコード追加
2. feature flag default off
3. internal tenantでdry-run
   - 実際にはblockしないが、block would happenのauditを出す
4. pilot tenantでJP/EU policy有効化
5. blocked/export/redaction/audit metricsを監視
6. 問題なければtenant単位で段階展開

監視したい指標:

- policy blocked count
- approval success/failure count
- sibling/unrelated approval denied count
- redacted export count
- export failures
- event consumer errors
- plugin import/runtime errors
- UI accessibility errors or support tickets

---

## 4. Release前に確認すべきポイント

- `normalizeRecipient` の既存テストがそのまま通る
- customer plugin smoke testが通る
- event top-level keysが変わっていない
- ReviewModalのkeyboard accessibilityが維持される
- JP/EU policyで未承認send/exportがserver側でblockedされる
- approval済みでのみsend/export可能
- sibling tenant approvalが不可能
- redacted exportで漏洩がない
- audit logでAI draft / approval / blockが判別できる
- audit/event metadataにunredacted customer dataが入らない
- feature flag off tenantで既存挙動が維持される
- product/legal/docsで「regional policy pack」の意味が正しく説明されている
- data residencyを保証しないなら、その旨が明記されている

---

## 5. Clarifying questions

実装前に確認したい不足情報は以下です。

1. 「parent tenant」はdirect parentのみですか、それともancestor全体を含みますか？
2. delegated reviewerには特定role/permissionが必要ですか？ 例: `owner` のみ、または reviewer permission
3. approval後にcase content、AI draft、export対象が変更された場合、再approvalが必要ですか？
4. `requireHumanReview` と region の関係はどちらが優先ですか？
   例: USでも `requireHumanReview: true` なら必須でよいですか？
5. redaction対象フィールドの正式な定義はありますか？ attachmentsやAI draft本文も対象ですか？
6. audit logは既存event streamで満たす想定ですか、それとも別の監査ストアがありますか？
7. 「regional policy pack」という名称はdata residencyを連想させますが、product/legalとしてこの名称のままでよいですか？
~~~

### Full Output: With Fairy Tale v2

~~~text
## 1. 前提整理：確認済み事実 / 推定要件 / 危険な仮定

### 確認済み事実

- `normalizeRecipient(input)` は既存の公開ヘルパーであり、API / worker / tests / customer plugins から利用されている。
- 既存連携は `normalizeRecipient(input)` の引数数・import path・戻り値の基本形に依存している。
- `emit_case_event()` の既存イベントは top-level keys が以下に固定されている前提のテストがある。
  `caseId, tenantId, actorId, action, metadata`
- `ReviewModal` は既存の keyboard 操作、特に close button の到達性が契約になっている。
- 新要件では、tenant ごとの regional policy pack と delegated reviewer が必要。
- JP/EU policy pack では AI draft 自体は生成可能だが、customer-facing send/export 前に delegated reviewer approval が必要。
- reviewer は同一 tenant または parent tenant に所属可能。ただし sibling tenant は不可。
- `policy.exportMode === "redacted"` の場合、export は redacted でなければならない。
- audit log には `AI-drafted`, `human-approved`, `blocked by policy` が分かる必要がある。
- 以前の PR は public contract 破壊で失敗している。

### 推定要件

- regional policy pack は既存 tenant にはデフォルト無効、または `DEFAULT_POLICY` 相当で後方互換にするべき。
- JP/EU の human review requirement は、UI だけでなく API / worker / export path 側でも強制されるべき。
- reviewer 承認は「その時点の case/export payload/version」に紐づくべき。承認後に内容が変わった場合の扱いを決める必要がある。
- audit log は既存 event consumers を壊さずに拡張する必要がある。top-level event schema を無断で変えるべきではない。
- tenant hierarchy は flat group ではなく、親子関係を方向付きで扱う必要がある。

### 危険な仮定

- 「JP policy pack」はデータ保存・処理のリージョン制御を意味する、という解釈は現時点の実装範囲と矛盾している。
- `parentTenantId` を「同じグループの一員」程度に扱うと、過去 incident のように sibling tenant 間 approval が発生する。
- `metadata` に何でも入れれば既存 consumer は問題ない、とは限らない。top-level keys よりは安全だが、metadata の shape に依存する consumer がいる可能性はある。
- `role?: "owner" | "agent" | "viewer"` に `"reviewer"` を追加すれば済む、とは限らない。既存 role union 変更は TypeScript consumer に影響し得る。

---

## 2. Proposed design direction

### 2.1 後方互換を最優先にする

#### `normalizeRecipient` は変更しない

`normalizeRecipient(input: string | Recipient): Recipient` の public contract は維持するべきです。

やってはいけないこと:

- 必須引数 `policy` や `tenantContext` を追加する。
- import path `packages/api/src/recipient` を削除・移動する。
- string input の `tenantId: "legacy-default"` 挙動を変える。
- 既存 `Recipient` 型に breaking な必須フィールドを追加する。

推奨方針:

- recipient normalization と policy resolution を分離する。
- 必要なら additive な helper を追加する。

例の設計方向:

- `normalizeRecipient(input)` はそのまま。
- 新規に `resolveRecipientContext(recipient, tenantId)` や `normalizeRecipientForTenant(input, options)` のような optional wrapper を追加。
- customer plugin 向けには既存 import path を維持しつつ、将来的には package entrypoint からも re-export する。ただし既存 path は deprecate する場合でも即削除しない。

---

### 2.2 Policy は tenant 単位の effective policy resolver にする

`DEFAULT_POLICY` は既存 tenant の後方互換として維持するべきです。

推奨構成:

- tenant ごとの policy override を保存する。
- `getEffectivePolicy(tenantId)` のような resolver で最終 policy を返す。
- policy 未設定 tenant は `DEFAULT_POLICY` を返す。
- regional pack の有効化は feature flag / tenant config 経由にする。
- JP/EU pack では customer-facing send/export に human approval が必要、という enforcement rule を policy resolver または gate 側で保証する。

注意点:

`PolicyPack` に `requireHumanReview` がある一方で、新要件は「JP/EU では必ず delegated reviewer approval」と読めます。
そのため、以下のどちらかに統一すべきです。

1. JP/EU pack では `requireHumanReview: true` 以外の保存を禁止する。
2. `requireHumanReview` とは別に、region-derived rule として `requiresApprovalBeforeExternalization(policy)` を計算する。

後者の方が将来拡張に強いですが、設定画面で「JP なのに requireHumanReview=false」と見えると混乱するため、validation も必要です。

---

### 2.3 Enforcement point は UI ではなく send/export pipeline に置く

UI 側で reviewer selector を表示するだけでは不十分です。

承認が必要な gate は、少なくとも以下に置くべきです。

- customer-facing send
- export
- worker 経由の非同期 export
- API 経由の direct export
- bulk export が存在する場合は bulk path
- plugin / integration 経由で customer-facing output を作る path

基本ルール:

```text
AI draft generation:
  JP/EU でも許可され得る。

customer-facing send/export:
  effective policy が human approval を要求する場合、
  valid delegated reviewer approval がなければ block。

export:
  policy.exportMode === "redacted" なら redacted export のみ許可。
```

重要なのは「draft 生成」と「外部送信・export」を分けることです。
JP/EU policy で AI draft generation まで止める実装にすると、新要件とずれます。

---

### 2.4 Delegated reviewer authorization は tenant hierarchy の不変条件で守る

過去 incident の原因は、`parentTenantId` を flat group のように扱ったことです。
ここは小さく検証可能なモデルを先に定義すべきです。

#### 推奨 invariant

対象 case の tenant を `caseTenantId`、reviewer の所属 tenant を `reviewerTenantId` とすると、approval 可能なのは次の場合のみ。

```text
reviewerTenantId === caseTenantId
OR
reviewerTenantId is an ancestor of caseTenantId
```

明示的に禁止:

```text
reviewerTenantId is a sibling of caseTenantId
reviewerTenantId is a descendant of caseTenantId
reviewerTenantId is unrelated
```

例:

```text
t-parent
  ├── t-child-a
  └── t-child-b
```

- `t-child-a` の export を `t-child-a` reviewer が承認: allow
- `t-child-a` の export を `t-parent` reviewer が承認: allow
- `t-child-a` の export を `t-child-b` reviewer が承認: deny
- `t-parent` の export を `t-child-a` reviewer が承認: deny

実装方針:

- tenant relation は方向付きの tree / DAG として扱う。
- 「同じ parentTenantId を持つか」ではなく「reviewer tenant が case tenant の ancestor か」を判定する。
- hierarchy lookup は central function に寄せる。
- authorization 判定は UI 表示だけでなく API 側で必ず行う。
- delegated reviewer は `Recipient.role` に直接混ぜるより、別の permission / assignment モデルで扱う方が安全。

---

### 2.5 Approval は対象 version に紐づける

承認済みかどうかは単純な boolean だけでは危険です。

最低限、approval record には以下の概念が必要です。

- case id
- tenant id
- reviewer id
- reviewer tenant id
- action scope: send / export / both
- approved target version または content hash
- policy version
- timestamp
- approval result

これにより、以下を防げます。

- draft 変更後に古い approval を再利用する。
- full export 用 approval を redacted export に流用する、または逆。
- policy 変更前の approval を policy 変更後にも無制限に使う。
- sibling tenant approval を後から検出できない。

---

### 2.6 Audit log は既存 event schema を壊さず拡張する

前回 PR の失敗から、`emit_case_event()` の top-level keys は変更しない方針にすべきです。

やってはいけないこと:

```text
{
  caseId,
  tenantId,
  actorId,
  action,
  metadata,
  policy,
  approval
}
```

これは既存 consumer を壊しています。

推奨方針はどちらかです。

#### 案 A: 既存 event の `metadata` に additive に格納

top-level keys は維持。

```text
metadata: {
  aiDrafted: true,
  humanApproved: false,
  blockedByPolicy: true,
  policyRegion: "jp",
  exportMode: "redacted",
  approvalId: "...",
  blockReason: "human_review_required"
}
```

メリット:

- 既存 `emit_case_event` contract を維持しやすい。
- 既存 event stream に乗せられる。

注意点:

- metadata shape に依存している consumer がいないか compatibility probe が必要。

#### 案 B: 新規 v2 event を追加

既存 `emit_case_event()` はそのままにし、新たに明示的な schema を持つ event emitter を追加。

例:

- `emit_case_audit_event_v2(...)`
- `emit_policy_decision_event(...)`

メリット:

- audit schema を強く定義できる。
- 既存 event consumer への影響が最小。

注意点:

- 監査要件上、既存 event と v2 event の二重記録・順序・欠落をどう扱うか決める必要がある。

現時点では、既存 consumers の依存度が不明なので、まずは案 A または A+B の併用が安全です。
ただし top-level keys 変更は避けるべきです。

---

### 2.7 ReviewModal は汎用 modal contract を維持する

`ReviewModal` 自体は汎用 component なので、reviewer selector の追加で keyboard reachability を壊してはいけません。

方針:

- close button は引き続き keyboard で到達可能にする。
- reviewer selector を入れても focus trap / tab order が破綻しないようにする。
- `role="dialog"` と `aria-modal="true"` は維持。
- selector 側に focus を奪わせる場合でも、close button に戻れることを保証する。
- 可能なら modal title / `aria-labelledby` / `aria-describedby` も追加検討。ただし既存 contract を壊さない additive change にする。

---

## 3. 小さく検証可能なモデル / invariants

PR 前に、次の invariants を設計ドキュメントかテスト名として明文化するとよいです。

### Recipient invariant

```text
normalizeRecipient(input) は policy / tenant config に依存しない。
string input は引き続き tenantId "legacy-default" を返す。
object input は tenantId を preserve する。
既存 import path は維持される。
```

### Event invariant

```text
emit_case_event(...).keys == ["caseId", "tenantId", "actorId", "action", "metadata"]
metadata=None の場合は {}
policy / approval 情報を追加しても top-level keys は増やさない。
```

### Reviewer authorization invariant

```text
canApprove(caseTenant, reviewerTenant) is true iff
  reviewerTenant == caseTenant
  OR reviewerTenant is ancestor of caseTenant.
```

### Policy gate invariant

```text
If action in ["send", "export"]
and effectivePolicy requires human approval
and no valid approval exists for current target version,
then action is blocked and audit log records blockedByPolicy.
```

### Redaction invariant

```text
If effectivePolicy.exportMode == "redacted",
all export paths return redacted output.
No full export is produced for that tenant/action.
```

### Audit invariant

```text
For each gated action, audit can answer:
- Was AI draft involved?
- Was human approval present?
- Was action blocked by policy?
- Which policy/effective region/exportMode applied?
```

---

## 4. Tests / probes to add before merging

### 4.1 Backward compatibility tests

#### `recipient.test.ts`

既存テストをそのまま維持した上で追加。

- `normalizeRecipient("USER@EXAMPLE.COM")` は引き続き:
  - lowercased id
  - lowercased email
  - `tenantId: "legacy-default"`
- `normalizeRecipient({ email: "A@B.COM", tenantId: "t1" })` は `tenantId: "t1"` を preserve。
- `normalizeRecipient` は policy 未指定で呼べる。
- `normalizeRecipient.length` などに依存する consumer がある場合は引数数 compatibility も検討。
- `packages/api/src/recipient` から customer plugin が import できる smoke test を維持。
- 新しい policy helper を追加しても `normalizeRecipient` の挙動が変わらないこと。

#### Plugin compatibility smoke

前回失敗しているので必須です。

- 実際の customer plugin に近い fixture から `normalizeRecipient` を import。
- build / typecheck / runtime import が通ること。
- package boundary や tsconfig path alias 変更で壊れないこと。

---

### 4.2 Policy resolution tests

追加したいケース:

- policy 未設定 tenant は `DEFAULT_POLICY`。
- tenant ごとの policy override が効く。
- JP policy pack で send/export 前 approval が required になる。
- EU policy pack で send/export 前 approval が required になる。
- US/default policy では既存挙動が維持される。
- `exportMode: "redacted"` の場合、export gate が redaction を要求する。
- 不正な config を保存できない、または effective policy で安全側に倒す。
  - 例: `region: "jp"` かつ `requireHumanReview: false` を許すのか拒否するのか。

---

### 4.3 Delegated reviewer authorization tests

tenant hierarchy fixture を作るべきです。

```text
root
  └── t-parent
        ├── t-child-a
        └── t-child-b
```

テストケース:

- same tenant reviewer can approve。
- parent tenant reviewer can approve child tenant case。
- sibling tenant reviewer cannot approve。
- child tenant reviewer cannot approve parent tenant case。
- unrelated tenant reviewer cannot approve。
- multi-level ancestor を許すかどうか。許すなら grandparent approval test。
- parentTenantId が同じだけでは許可されないこと。
- hierarchy cache がある場合、tenant relation 更新後に古い cache で誤承認しないこと。

特に前回 incident の再発防止テスト:

```text
Given t-child-a and t-child-b share t-parent,
When reviewer from t-child-b tries to approve export for t-child-a,
Then approval is denied.
```

---

### 4.4 Approval workflow tests

ケース単位で追加。

- JP tenant:
  - AI draft generation は成功する。
  - approval なしの customer-facing send は block。
  - approval なしの export は block。
  - valid delegated reviewer approval 後に send/export 可能。
- EU tenant も同様。
- US/default tenant:
  - 既存 send/export path が変わらない。
- approval 後に draft 内容が変わった場合:
  - 古い approval が無効になる、または再承認が必要になること。
- approval の scope:
  - send approval と export approval を分けるなら、誤流用できないこと。
- policy 変更後:
  - policy version が変わった場合、既存 approval をどう扱うかのテスト。

---

### 4.5 Export redaction tests

すべての export path に対して必要です。

- API export。
- worker async export。
- bulk export がある場合。
- plugin/export integration がある場合。
- `exportMode: "redacted"` で full data が含まれない。
- `exportMode: "full"` で既存出力が変わらない。
- redaction の対象フィールド一覧が固定されている場合は snapshot / golden test。
- redaction の漏れを検出する negative test。
  - email
  - phone
  - free text PII
  - attachments / metadata があるならそれも対象確認。

---

### 4.6 Audit event tests

既存 `events.test.py` は維持。

追加:

- `emit_case_event(..., metadata=None)` は引き続き `metadata: {}`。
- top-level keys は増えない。
- AI draft ありの action で metadata に `aiDrafted` 相当が記録される。
- human approval ありの action で metadata に `humanApproved` / `approvalId` 相当が記録される。
- policy block 時に `blockedByPolicy` / `blockReason` 相当が記録される。
- redacted export 時に `exportMode: "redacted"` が監査できる。
- 既存 consumer fixture が unknown metadata fields を許容できるか確認。
- もし v2 audit event を追加するなら:
  - v1 event が引き続き発行される。
  - v2 schema validation。
  - v1/v2 の相関 id がある。

---

### 4.7 ReviewModal accessibility / regression tests

既存テストは維持。

追加:

- reviewer selector が children として入っても close button に keyboard で到達できる。
- Tab / Shift+Tab の順序が破綻しない。
- selector 操作後も close button が keyboard reachable。
- dialog role は維持。
- close button click / keyboard activation は維持。
- 可能なら accessibility test:
  - accessible name
  - focus containment
  - screen reader label

前回失敗しているので、reviewer selector を表示する integration test は必須です。

---

### 4.8 End-to-end / contract probes

local unit green だけでは不足です。

追加したい probe:

- tenant policy 未設定の既存 customer flow が変わらない。
- JP tenant の draft → approval → redacted export flow。
- JP tenant の draft → approval なし export block flow。
- sibling tenant approval attempt が block され audit に残る。
- customer plugin import/build smoke。
- event consumer fixture が既存 schema で動く。
- worker が古い event schema を期待していても落ちない。
- web modal keyboard regression。

---

## 5. Rollout / release risks

### 5.1 Data residency 誤認リスクは release-blocking

Customer note にある通り、JP customer が「regional policy pack = data stays in Japan」と説明されていた点は重大です。

現状の engineering scope は以下に見えます。

- review requirement
- export redaction
- audit metadata
- tenant policy behavior

一方で、以下は未実装です。

- storage region pinning
- processing region pinning
- AI model execution location control
- cross-region routing prevention
- backup / logs / analytics の residency control

したがって、JP/EU regional policy pack をリリースする前に、Product / Legal / Sales / Support と表現を合わせる必要があります。

リリース前に確認すべき文言:

- 「regional policy pack」は compliance workflow policy なのか。
- data residency を保証しないことを明記するのか。
- DPA の “region-specific configurations where enabled in the product” が今回機能をどうカバーするのか。
- customer-facing docs / sales materials / UI label に “data stays in Japan” と誤解される表現がないか。

ここは release-blocking と扱うべきです。

---

### 5.2 既存 integration 破壊リスク

高リスク箇所:

- `normalizeRecipient` の signature / import path。
- `Recipient` 型の required field 追加。
- `emit_case_event` の top-level schema 変更。
- `metadata` shape の暗黙依存。
- export output shape の変更。
- ReviewModal の focus behavior。

対策:

- 既存 contract tests を削除しない。
- additive helper / v2 API を使う。
- feature flag で tenant 単位に有効化。
- customer plugin smoke を CI に入れる。
- event consumer compatibility fixture を CI に入れる。

---

### 5.3 Authorization bug 再発リスク

過去 incident の再発防止として、tenant hierarchy 判定は release gate にするべきです。

特に確認:

- sibling approval が必ず deny。
- parent approval の方向が正しい。
- tenant hierarchy cache が古くても安全側に倒れる。
- UI で選べないだけでなく API でも拒否する。
- audit log に denied approval attempt が残る。

---

### 5.4 Redaction 漏れリスク

`exportMode: "redacted"` は実装漏れが起きやすいです。

注意する export surface:

- synchronous export
- async worker export
- CSV / JSON / PDF など形式別 export
- attachment export
- metadata export
- analytics export
- plugin export
- audit export 自体に PII が含まれないか

リリース前に redaction 対象フィールドの一覧と責任者を明確にするべきです。

---

### 5.5 Audit の完全性リスク

監査要件は「ログに何か出す」だけでは足りません。

確認すべきこと:

- blocked action も audit に残る。
- approval success も denial も残る。
- AI draft involved かどうかが後から判断できる。
- policy version / region / exportMode が後から判断できる。
- event delivery failure 時の扱い。
- worker retry で重複 audit が出る場合の idempotency。
- customer-facing action と audit record を相関できる id がある。

---

### 5.6 段階的 rollout 方針

推奨 rollout:

1. schema / resolver / tests を追加。ただし feature flag off。
2. existing tenants で shadow mode。
   - policy decision を計算するが block はしない。
   - audit metadata だけ観測。
3. internal tenant または test tenant で enforce。
4. selected JP/EU pilot tenant で enforce。
5. monitor:
   - blocked send/export count
   - approval latency
   - denied sibling approval attempt
   - export redaction failures
   - event consumer errors
6. rollback plan:
   - tenant policy flag を off にできる。
   - enforcement だけ off にして audit は残せる。
   - migration rollback なしでも安全に動く additive schema にする。

---

## 6. リリース前に確認すべき質問

### Release-blocking questions

1. **Regional policy pack は data residency を含むのか。**
   含むなら現状設計では不足。含まないなら Product / Legal / Sales 文言修正が必要。

2. **JP/EU policy pack では `requireHumanReview` は常に true でよいのか。**
   tenant admin が false にできる余地を残すのか、validation で禁止するのかを決める必要があります。

3. **parent tenant reviewer の範囲は direct parent のみか、ancestor 全体か。**
   “parent tenant” という表現が direct parent を意味するのか、親会社階層全体を意味するのか確認が必要です。

4. **approval はどの単位に紐づくべきか。**
   case 単位、draft version 単位、export payload hash 単位、action 単位のどれか。
   ここが曖昧だと承認後変更の抜け道ができます。

5. **redacted export の仕様。**
   どのフィールドを redacted にするのか。attachments / free text / metadata / audit fields は対象か。

6. **audit log の正式 schema と保持要件。**
   既存 event metadata で足りるのか、専用 audit event/table が必要か。保持期間や customer export 可能性も確認が必要です。

### Non-blocking but should clarify

1. delegated reviewer は既存 `Recipient.role` と統合するのか、別 permission model にするのか。
2. tenant policy は child tenant に継承されるのか、完全に tenant ごとに独立か。
3. approval UI は reviewer を検索・選択するのか、現在ユーザー自身が reviewer として承認するのか。
4. policy change 時に既存 in-flight cases をどう扱うか。
5. 既存 customer plugins が export/send を直接行える場合、どこで enforcement するか。

---

## 7. この PR の進め方の推奨

最初の PR で広範囲に作り替えるのは避けるべきです。分割を推奨します。

### PR 1: Contract preservation + policy model skeleton

- `normalizeRecipient` 不変テストを強化。
- event top-level schema 不変テストを強化。
- tenant policy resolver を追加。
- feature flag off。
- no behavior change。

### PR 2: Delegated reviewer authorization

- tenant hierarchy function を追加。
- same / parent / sibling / child / unrelated tests。
- incident regression test を追加。
- API-side authorization enforcement の土台を追加。

### PR 3: Send/export policy gate

- draft generation と externalization gate を分離。
- approval なし block。
- valid approval あり allow。
- audit metadata 追加。
- feature flag gated。

### PR 4: Redacted export

- redaction engine / export path integration。
- export path ごとの tests。
- golden/snapshot tests。
- leakage tests。

### PR 5: UI integration

- ReviewModal contract 維持。
- reviewer selector integration。
- keyboard/focus regression tests。

### PR 6: Rollout hardening

- shadow mode。
- metrics。
- event consumer probes。
- customer plugin smoke。
- docs/legal/product wording update。

---

## 8. 最終的なレビューコメントとしての結論

この機能は単なる UI 追加ではなく、tenant policy、authorization、export enforcement、audit、法務表現が絡む変更です。
実装方針としては、既存 public contracts を維持しながら additive に進めるべきです。

特に以下は必須です。

- `normalizeRecipient(input)` は絶対に breaking change しない。
- `emit_case_event()` の top-level schema は変えない。
- delegated reviewer 判定は ancestor relation で実装し、sibling approval を明示的に拒否する。
- JP/EU では draft generation は許可しつつ、send/export を approval gate で止める。
- redacted export は全 export path で強制する。
- audit は AI draft / human approval / policy block を後から判別可能にする。
- ReviewModal の keyboard accessibility は維持する。
- 「regional policy pack = data residency」と誤認されないよう、リリース前に Product / Legal / Sales と確認する。

この確認が終わるまでは、既存 tenant に対して enforcement を有効化せず、feature flag + shadow mode で段階的に進めるのが安全です。
~~~
