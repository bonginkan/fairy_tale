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
