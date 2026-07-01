# Creator-Proxy Elaboration (WWCD)

**WWCD = What Would the Creator Do.** When an agent acts as a creator/principal's proxy
but is invoked by a *third party* (a relay), or when a relayed instruction underspecifies
the creator's intent, the agent elaborates "what would the creator instruct / do here" as
an **evidence-grounded, confidence-tagged hypothesis about intent** — explicitly **not** as
authority. Internal nickname: "Hero The Pioneer would do this" (a Frieren-style *what would
the hero do* homage); the mechanism itself is IP-independent and the OSS body uses the
formal name.

## Why (prior art)

Within the surveyed scope, **no paper studies this exact relayed-creator-proxy step**
(direct match not found; non-existence is *not* claimed). The mechanism is a synthesis:

**Supports the shape.**
- **Constitutional AI** (arXiv:2212.08073): fidelity comes from reasoning against a
  principal's *explicit written principles*, not a persona name. WWCD must be
  constitution-grounded.
- **CIRL** (arXiv:1606.03137): a good proxy *infers the latent objective* an instruction is
  evidence of, rather than obeying it literally.
- **Step-Back** (arXiv:2310.06117) and **ToM prompting** (arXiv:2304.11490): a pre-action
  "abstract to the principle / take the person's perspective" step measurably helps.
- **Role-Play prompting** (arXiv:2308.07702): adopting the role before answering shifts
  behavior toward the role's competencies.

**Failure modes it must guard against.**
- **Sycophancy** (arXiv:2310.13548): with a third party present, models bend toward the
  *relayer*, not the absent creator. The relay context is the worst case; WWCD is partly a
  counter-sycophancy device but can itself be captured.
- **Persona-vector hallucination/sycophancy** (arXiv:2507.21509): an *underspecified* "what
  would the creator do" prompt mechanically activates the hallucination and sycophancy
  directions. Vagueness makes it worse — WWCD must be specific and evidence-cited.
- **Belief-behavior divergence** (arXiv:2507.02197): what the persona "would say" can
  decouple from what the agent then does. Bind the action to the elaborated principle.
- **ToM limits** (arXiv:2509.02292) and **infeasible intent verification** (SentinelAgent,
  arXiv:2604.02767): the inferred intent may be wrong and can never be certified. Treat it
  as probabilistic and escalate on conflict/low confidence.

## The gates (enforced by `scripts/creator_proxy_elaboration_check.py`)

Every pass is recorded as a `creator-proxy-elaboration-ledger`
(`schemas/creator-proxy-elaboration-ledger.schema.json`). The checker fails (RED) on:

1. **Authority delegation** — `authority_decision.basis` is not one of
   `verified_identity_sender_id | existing_policy_allowlist | not_applicable`, or its `note`
   rests permission on creator intent ("the creator would approve"). Authority is decided
   from identity/policy only, in a field separate from the intent hypothesis.
2. **Evidence** — a cited evidence entry lacks a *concrete* `ref` (a tier name alone is not
   evidence); a `high` confidence inference lacks any artifact stronger than `style_hints`;
   memory / home config / private notes used without existing permission+scope.
3. **Relayer separation** — a missing `relayer_request` / `inferred_creator_goal` /
   `conflict_flag`; a relayer/creator conflict without a concrete `rejected_relayer_pull`.
4. **Escalation** — low confidence OR high stakes OR conflict without
   `escalation.action = surface_or_confirm`.
5. **Belief→behavior** — `action.cited_principle_id` does not resolve to a
   `cited_evidence[].id`.

Run `python3 scripts/creator_proxy_elaboration_check.py --selftest` to exercise one GREEN
baseline and one RED per gate.

## Dogfood protocol (tri-agent)

To canonicalize, three agents independently run the **same prompt** against the **same
evidence pack** and each emit a ledger. The ledgers are compared field-by-field (not prose):
`inferred_creator_goal`, `cited_evidence` (ids + tiers + refs), `proposed_instruction`,
`confidence`, `escalation.action`, `rejected_relayer_pull`, and `authority_decision`. See
`fixtures/creator-proxy-elaboration/dogfood-prompt.json` for the shared prompt + evidence
pack and the comparison ledger. The implementer does not self-sign; two independent
reviewers sign off (the same review-calibration discipline as the spiral/evolution ledgers).
