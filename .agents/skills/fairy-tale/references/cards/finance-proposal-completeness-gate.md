# Finance Proposal Completeness Gate

Fail-closed completeness gate for financial artifacts: proposals, pricing
models, business cases, unit-economics sheets, and forecasts. Fire it from
**artifact content, not only task wording** — any reviewed artifact that
contains revenue, margin, profit, ROI, POC conversion, churn, active months,
channel economics, implementation/operations costs, or weighted financial
claims routes here. Do not fire for OCR/layout-only extraction with no
financial judgment. Sequence: Domain Router → Evidence Table Harness → this
gate → Closure / Negative-Space Check → reviewer sign-off.

- **Arithmetic passing is not completeness.** A model can recompute perfectly
  while material unit economics are absent. The Evidence Table extracts facts
  that are present; this gate forces enumeration of economically **entailed**
  rows that may be absent. Both checks are required; neither substitutes for
  the other.
- **Claim ledger, one record per central financial claim.** Record: claim ID
  and page/cell/chart source; metric definition (revenue, gross margin,
  contribution margin, operating profit, or forecast); period, currency,
  unit, and tax basis; displayed value, formula, recomputed value, and
  rounding rule; revenue drivers (price, volume, start month, active months,
  conversion, churn); every evidenced or structurally entailed cost driver;
  assumptions, evidence status, sensitivity, and cross-claim dependencies;
  unresolved counts. A central claim without a ledger record is a BLOCK.
- **Cost disposition is a closed enum, fail-closed.** Every evidenced or
  entailed cost driver carries exactly one disposition: `amount` (a finite
  number with its own anchored source, on the claim's period), `included-in`
  (must reference a cost line, claim, or formula input that EXISTS in the
  same ledger — and a host driver must itself be a resolved amount — plus a
  substantive allocation basis, a covered scope, an anchored source, and the
  claim's period), `not-applicable-with-evidence` (requires a citable,
  identifier-bearing anchor — not prose length), or `TBD`. A `TBD` on an
  entailed driver is an open blocker: it must surface in the unresolved
  count, be enumerated in `blockers`, and BLOCK promotion — it is never
  silently priced at zero. A generic "all figures are assumptions"
  disclaimer does not convert a missing cost treatment into an accepted
  zero. Duplicate or unnamed driver rows block. Uncertainties are
  structured records with a bounded impact; a decision-reversing
  uncertainty blocks outright.
- **Unit Economics Assumption Closure (required sub-gate).** The stated
  business model entails cost rows whether or not the artifact mentions
  them: partner- or channel-led sales entails channel economics (fees,
  revenue share, partner enablement); implementation or managed service
  entails setup/onboarding, support, security, and incident-response
  treatment; recurring models entail a feasible conversion/churn cohort
  schedule consistent with active-months claims. The model registry is
  CLOSED: a malformed or unrecognized business model blocks, because an
  unknown motion cannot certify that nothing extra is entailed. Each
  entailed row must be dispositioned. `not-applicable` needs evidence (e.g.
  direct sales with no partner in the motion) — an unsupported applicability
  assertion is a BLOCK, and a supported one must not be false-blocked.
- **Aggregate margins inherit component coverage.** An aggregate or blended
  margin computed from component margins is only as complete as its weakest
  component: if any component has unresolved cost coverage, the aggregate is
  BLOCK even when its arithmetic reconciles.
- **Heterogeneous reviewer roles with recorded verdict and coverage.**
  Same-rubric sign-offs share blind spots. Require two roles over the SAME
  immutable artifact, inspected independently: an arithmetic/reconciliation
  reviewer (recomputation, units, periods, rounding, sign conventions inside
  numerators) and a business-model-completeness/negative-space reviewer
  (entailed rows, dispositions, cohort feasibility). Each sign-off records
  an explicit verdict and the claim IDs it covered; every required role must
  cover every claim (an extra role never substitutes), a reviewer `block`
  verdict blocks the gate, and any change to the ledger or artifact
  invalidates both sign-offs.
- **Closure state is explicit.** The ledger records `blockers` and
  `uncertainties` lists; every open `TBD` must be enumerated in `blockers`,
  and a ledger that declares open blockers can never pass.
- **Deterministic validation — nothing is self-attested.**
  `scripts/finance_completeness_check.py` RE-EXECUTES each claim's formula
  over its stated `inputs` (restricted arithmetic evaluator) and recomputes
  aggregates from component values via required normalized `weights`; a
  recorded `recomputed_value` must equal the checker's own execution. Every
  formula input must be BOUND to the ledger via `input_bindings` — a cost
  driver, a revenue driver, an expression over those, or a declared
  assumption — and ALL numeric anchors must reconcile: bindings against
  input values, assumption entries against their recorded `value`, and
  amount cost drivers must actually be consumed by the bound math on
  margin/profit claims. The binding space is CLOSED over the executed
  formula: inputs the formula never reads and bindings for keys outside the
  inputs both block, so consumption can never be faked through phantom
  bindings; assumptions no binding consumes block too. Claim sources must be
  locators (page/cell/section/URL), never tokens. Recurring-model claims
  must use conversion and active-months wherever volume enters the bound
  arithmetic; conversion/churn domains are validated; margins must be
  ratio-unit quotients over a revenue-bound denominator with a numerator
  derived from it, in plausible range. Reference is not effect: every input
  is perturbation-tested (a `*0` coefficient blocks) and a cost-bound input
  that moves a margin/profit UP is a sign inversion. Dependency and
  aggregate graphs must be acyclic with no self/duplicate references.
  Constant formulas, non-executable formulas, missing inputs, and
  non-finite values block. A strict schema rejects unknown keys
  anywhere in the record so a typo can never weaken a rule, while requiring
  every #74 record field (recomputed value, assumptions with values,
  evidence status, sensitivity, cross-claim dependencies, closure state).
  Coverage of the checker's canonical reason-class list is proven by
  executed RED fixtures alone — never by a hand-maintained claim.
  Sanitized cross-industry fixtures live in
  `fixtures/finance-completeness/cases.jsonl` (agency, SaaS, marketplace,
  managed service, hardware, channel sales), including one RED fixture per
  known bypass class. Promotion bar: full recall on material omissions and
  arithmetic errors, zero unsupported applicability assertions, zero false
  blocks on supported `not-applicable` rows. Do not hardcode any single
  motivating artifact.

Provenance: gate contract specified in issue #74 (fail-closed unit-economics
closure for document review). Metric vocabulary (gross margin, contribution
margin, operating profit) follows standard managerial-accounting usage; the
gate constrains *completeness and disposition*, not any org-specific
accounting policy, so it stays portable across organizations.
