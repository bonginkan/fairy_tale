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
  number on a stated basis), `included-in` (must reference a cost line,
  claim, or formula input that EXISTS in the same ledger, plus a substantive
  allocation basis — a bare host name is an unsubstantiated absorption
  claim), `not-applicable-with-evidence` (requires a citable, locator-shaped
  anchor — page/section/contract/URL — not prose length), or `TBD`. A `TBD`
  on an entailed driver is an open blocker: it must surface in the
  unresolved count and BLOCK promotion — it is never silently priced at
  zero. A generic "all figures are assumptions" disclaimer does not convert
  a missing cost treatment into an accepted zero. Duplicate or unnamed
  driver rows block.
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
- **Heterogeneous reviewer roles.** Same-rubric sign-offs share blind spots.
  Require two roles over the SAME immutable artifact, inspected
  independently: an arithmetic/reconciliation reviewer (recomputation,
  units, periods, rounding) and a business-model-completeness/negative-space
  reviewer (entailed rows, dispositions, cohort feasibility). Any change to
  the ledger or artifact invalidates both sign-offs.
- **Deterministic validation — nothing is self-attested.**
  `scripts/finance_completeness_check.py` RE-EXECUTES each claim's formula
  over its stated `inputs` (restricted arithmetic evaluator) and recomputes
  aggregates from component values via required normalized `weights`; a
  recorded `recomputed_value` must equal the checker's own execution. Every
  formula input must be BOUND to the ledger via `input_bindings` — a cost
  driver, a revenue driver, an expression over those, or a declared
  assumption — and numeric bindings must reconcile, so the arithmetic can
  never float free of the recorded economics. Constant formulas,
  non-executable formulas, missing inputs, non-finite values, and margins
  outside plausible range block. A strict schema rejects unknown keys
  anywhere in the record so a typo can never weaken a rule, while requiring
  every #74 record field (assumptions, evidence status, sensitivity,
  cross-claim dependencies included).
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
