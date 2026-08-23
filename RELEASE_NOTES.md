# Release Notes

## 0.2.42 — The tests wait for the verdict, and a port starts as a copy

- **A review loop now says when its tests run.** The Helix card already bound
  sign-offs to an exact head and returned a blocker to the same increment, but
  it said nothing about the implementation's tests, so the general rule applied
  inside the loop as well: validate continuously, run the focused check after
  editing. Against a head that an open blocker is about to move, that run
  decides nothing and spends the turn, and a push-triggered CI result arrives
  unrequested and reads like evidence. The card now holds the test run and the
  CI read until the increment's required sign-offs stand against the current
  exact head with no blocker open; the review stays static until then, and once
  the turn closes the validation runs once on that head. A failure reopens the
  same increment, and the existing staleness rule re-collects the sign-offs on
  the new head instead of re-running the gate. No new state name was added: the
  rule is written in the sign-off and blocker vocabulary the card already owns.
  The Fable card's `Validate continuously.` carries a one-line scope reference
  to it rather than a second copy of the rule, and the general validation gate
  is unchanged — this is a rule about a loop, not about every workflow (#126).
- **A port starts as a copy, not as a re-typing.** The Fable card said what a
  port must carry and what success means, and never said how the bytes move.
  The failure that leaves open is silent: a body re-typed or hand-edited
  instead of copied loses lines, and nothing fails to show it — what remains is
  a smaller port that still looks deliberate. The first operation is now a copy
  command naming the source's exact line range, placed at the destination
  before anything is edited; only the wiring the target requires is edited
  afterwards. The content rules are untouched and still govern what that copy
  must be adapted to carry (#126).

## 0.2.41 — A trigger decision is not a stop, and a port is not an invitation

- **The generic trigger now reaches the behaviour it was always meant to
  reach.** `./fairy fusion --auto-check` returned `trigger` and the canonical
  surfaces stopped there, leaving the rest — bounded review, one synthesis,
  compact hint, main agent continues — described only for the benchmark path.
  The Fairy Fusion card and the auto-trigger doc now state what a caller does
  with one. The scope is the reasons an existing integration already handles
  this way: a repeated failure signature, a missing validation ledger, and an
  empty or meaningless artifact. An explicit request needs no redirection rule
  because the request is its own grounds, and `review_conflict` stays with the
  caller's own policy because there is no established handling for it to reach.
  The precedent is read as written: `scripts/swebench_pro_run.py` runs this
  control flow under its own flags — the retry loop only with `--fusion-auto`
  and `--fusion-retry-on-stuck`, and reviewers only with `--fusion-execute`.
  No new mechanism: the automatic check still only decides, `automatic_execution`
  stays `false`, and the recursion cap stays 1 (#124).
- **A port carries what was asked for and the adaptations it needs, nothing
  else.** The Fable Harness card now says that unrequested features, redesigns
  and improvements noticed on the way are surfaced as separate findings rather
  than implemented, and that success is behavioural and contract equivalence at
  the target rather than extra capability. The target-compatibility adaptations
  a port needs are part of the port, not extras — dropping one to look minimal
  is a failed port — and they include a required property the target imposes
  that the source never had, such as authorization, privacy, retention, money,
  identity, or contractual behaviour. Its route hint now reaches a short direct
  port as well as a long migration, so the rule is not gated behind the word
  "long", and the plan-and-checkpoints step is sized to the task so a short
  port does not acquire long-migration ceremony by routing there.
- The Closure harness is unchanged: `no automatic implementation scope
  expansion` already covers the surfacing side, so the rule lives in one place.

## 0.2.40 — Fuzzy-First: build on the model's judgement, correct at the failures

- **Fuzzy-First** turns the default around for product features that call an LLM.
  The model's judgement implements the behaviour; code that stands between the
  user and that judgement exists for properties that must hold whatever the model
  does, and for points where the model has been observed to fail. The card is
  explicit that the feature's plumbing — transport, storage, retries, rendering —
  is ordinary software and outside this test.
- The correction target is the smallest failure mode the evidence supports:
  neither the literal input that broke, which the next phrasing evades, nor the
  category it belongs to, which takes the neighbours' generality away. Prompt and registered content come
  before a branch — not because guidance is safe on input nobody foresaw, since
  neither form gives a guarantee there, but because the failures differ and code
  fixes its choice at write time for cases its author never saw.
- Enumerations and hard classifiers are refused in front of the model: keyword
  lists, intent tables, synonym sets and confidence gates each cover what their
  author imagined while the model handled the rest, and a "cannot determine"
  branch converts an answer into a refusal.
- **Keep the conversation.** One stateless call per turn manufactures the
  failures a prompt author did not anticipate. Persisting turns or holding a
  provider conversation handle is transport and keeps what was said; compressing
  the dialogue into a summary or a slot-filled record is a separate trade.
  Statelessness is right where carrying context would defeat the step or cross a
  boundary it must not — another tenant, channel, or customer.
- Authorization, privacy and retention, money, identity and anything with a
  contractual definition stay in code regardless, implemented without waiting for
  a failure and never removed on the argument that none has been seen — carved
  out inside the review checklist, not only in the section it protects.
- Both failure directions carry a reviewer action: refuse an unnecessary
  mechanism, and ask for the smallest correction when a failure keeps recurring.
- **Closure, Negative-Space and Excess** gains a removal mode (#123). When the
  goal is to cut an over-grown surface back, the additive half argues the wrong
  way every time: each candidate acquires a list of things it entails, and the
  subtraction becomes an expansion. In that mode the excess pass leads, the
  closure check asks what a removal breaks and which required property would
  lose its implementation, Tier A names what the removal takes with it, and
  Tier B/C additive surfacing is off while their subtraction form stays. An
  effort that removes and adds together, or whose mode was never established,
  is not in removal mode — the recall guard wins when the reading is ambiguous.

## 0.2.39 — Release packaging

- Version bump only. The plugin is served from a version-keyed cache, so hosts
  holding `0.2.38` kept serving it and `claude plugin update` answered "already at
  the latest version" while the skills had moved three revisions ahead. A CI gate
  proposed alongside it was dropped: releasing is a decision, not a property of a
  diff.

## 0.2.38 — Helix: target location, owner priority, one effort per branch

- A wrong target is not corrected by working carefully inside it. **Locate the
  Target Before Solving** puts target resolution ahead of content: the subject of
  a directive names the target and an explicit naming governs wherever it
  appears, ambient signals corroborate rather than decide, a conflict fails
  closed to the owner, reviewers resolve the target independently before reading
  content, and a new or corrected directive re-opens the target of work already
  approved, applied, or copied onward.
- **Owner-Priority Review and Time-Awareness** gives exactly one named reviewer a
  disposition role bounded so it orders findings without deleting them, and
  bounded again so it cannot downgrade the floor. Deadlines are read from a clock
  and need a recorded source; the minimum coherent set is pre-registered by name
  at the start of the window, because deciding at the end makes whatever passed
  the definition.
- **Multiple Directives Are One Effort** stops a set of instructions being solved
  one at a time. The directive set is read from its refs and changes three ways —
  addition, replacement, and correction of where an earlier directive is carried
  out. The working branch is fixed at owner-goal scope, and fixing means not
  moving it rather than cutting a fresh one per effort.
- **GitHub Is the Exchange Surface** moves reviewable work off chat attachments.
  Identity comes from the forge's own refs rather than hand-built hashes and
  version labels, and an artifact long enough to split across messages belongs in
  a file instead.
- The Edison Ship Gate gains six bounds: the claim is judged against the union of
  merge-base contracts and pinned directive/acceptance rather than either half; the
  provenance test is increment-relative rather than personal; a normal-path break
  separates substance (a nameable failure sequence with a reachable locator) from
  the execution evidence that sustains the block; a split on floor membership is
  refuted asymmetrically; a pre-existing floor finding is placed by reach rather
  than vintage; and "no retained fix-now" means none outstanding rather than none
  newly raised this round. Its next-cycle clause is bounded to technical findings
  about the increment's behaviour, and deferred work stays on the effort's branch.
- The blocker triage record moves to schema 1.2 so the rules above are machine
  gates rather than prose. `roles` carries exactly one `priority_reviewer_id`,
  drawn from the reviewers and never the implementer. `deadline` carries the clock
  readings actually taken and the pre-registered `minimum_shape` as named items
  with a hash. `loop` carries a structured `target` (repo, path, layer, canonical
  owner, directive refs, propagation path, duplication policy), a `claim_envelope`
  pairing the merge-base baseline with pinned mutable sources, and the
  `working_branch` with the ref that fixed it. `protected_floor` gains
  `unapproved_branch_change`, which is unconditional and not deferrable at any
  level of concurrence.
- The Default workflow gains a pre-scout step: resolve the target before framing
  the quest. The residency check now requires markers in all four new cards and in
  the handoff card, and the routing fixtures carry the target-location cases —
  explicit path against ambient channel, mid-effort correction, late-joining
  reviewer — with negative controls for an uncontested target and for a separate
  owner goal on the same system.

## 0.2.37 — Edison Ship Gate: the dev-deploy threshold

- A loop that converges only on a perfect increment does not converge. The new
  Edison Ship Gate ships an increment to a dev / non-production target once its
  normal path is verified, and turns everything off the safety floor into a
  next-cycle issue instead of a blocker. Work on the deferred items continues;
  the deploy stops waiting for them, so the humans who find what no harness
  enumerates get to hit the artifact.
- The relaxation is bought with evidence, never asserted. The blocker triage
  record (schema 1.1) carries `loop.ship_stage`: the stage, its basis (owner
  directive, non-production target, or early development), and the happy path
  recorded as verified against a concrete executed check. An unverified normal
  path leaves the production thresholds in force.
- Under the gate the defer envelope widens to a residual risk score of 200 and
  to high impact without measured pressure; critical impact stays fix-now.
- The evidence itself needs a witness who is not its beneficiary:
  `ship_stage.evidence_attestation` names the registered reviewer — never the
  implementer — who confirmed that the basis denotes a real authorized target
  or directive and that the normal-path check ran on this exact head. A
  missing, self-written, or unsupported attestation leaves the production
  thresholds in force.
- The floor does not move. Every finding now records a `finding_class` and a
  `floor_basis`: only *precautionary* hardening on the security floor may be
  deferred — the finding must be classed `hardening`, so a reachable defect
  cannot reach the issue queue by relabelling its basis — only at a verified,
  attested dev stage, and only with every registered reviewer concurring. A
  demonstrated reachable defect, every other floor, and any finding classed
  against the shipped normal path remain fix-now at every stage.
- A ship decision is a readiness statement, not an authority grant: `go`
  confers no deploy, merge, or access authority and overrides no repository
  gate or owner policy. The rendered readback prints that boundary.
- Records persisted under schema 1.0 upgrade rather than expire.
  `fairy blocker migrate` maps them onto the production stage with an
  unverified normal path and no attestation — never granting an envelope the
  old record did not earn — and validates the result before writing it.
- `final_readback.ship_decision` makes the outcome auditable: `go` cannot carry
  a retained fix-now finding, a dev `go` needs the verified normal path, and a
  dev increment with a verified normal path and nothing retained **cannot be
  held** — holding a green increment is now a RED finding rather than
  diligence.
- Dev debt is deferred, never discharged: every dev-stage deferral re-blocks at
  production promotion, and the rendered readback prints that promotion debt
  with its issues.
- SKILL.md stages validation in the head window and routes the new card; the
  Residency Guard procedure moves to `references/residency-guard.md` so the
  mode-pattern router still fits inside the post-compaction head window.

## 0.2.36 — Lane recovery, turn boundary, truncated receipts

- Silence stops being read as unavailability. The usage-aware load balancer
  record separates *unresponsive* from *unavailable*, makes the agent's own
  session surface the terminal evidence, and records `unknown` when that
  surface cannot be inspected.
- Bounded in-lane recovery becomes the default path for an agent that looks
  unresponsive: resume, restart, or relaunch it in its own session lane and
  re-issue the pending handoff. Recovery is owned by the lane owner or an
  authorised actor, resumes from the last safe checkpoint, and runs inside a
  recorded retry budget that ends in escalation rather than another restart.
- A cross-lane role transfer becomes an explicit authorised reassignment after
  bounded recovery fails, never an automatic fallback for silence. Session
  lanes are partitioned so task placement stays stable.
- The Helix communication card defines the turn boundary: no next-increment
  write until the required sign-offs are recorded against the current exact
  head, partial review is not a boundary, a blocker returns to the same
  increment, and a head change staleness-invalidates prior sign-offs.
- A truncated inbound message is treated as incomplete. The remainder is
  recovered from the transport's own history or message API, bounded by
  thread, sender, and time window, with no inference and no unrelated tail.

## 0.2.35 — Implementation contract closure

- Adds the Implementation contract closure record and its machine gate
  (`./fairy contract validate`): the concurrency matrix is checked against the
  cross product of the operation inventory, admissible dispositions follow the
  hazard kind (so commutative, snapshot and key-partitioned overlaps are not
  over-blocked), impossibility must be a system property, and fix re-closure is
  derived from a versioned diff of the record instead of a declaration.
- The integration branch and the discovery scope come from the project's
  authority, never from the record or the caller, and the trusted base must be
  the merge base with that branch — containment is not enough.
- `--repo-root` separates the project under test from the installation running
  the gate, so an extracted release package gates another project against
  **that** project's authority, code surface and tracked inventory. A CI
  end-to-end control builds the package and does exactly this.
- Every run prints one machine `VERDICT` line, including runs stopped early by
  an unreadable record or a swapped inventory.
- Adds fix-induced re-closure to the Helix blocker triage record.
- Runtime package version is 0.2.35.

## 0.2.34 — Contract closure authority

- Adds the project-owned authority the gate measures against —
  `.fairy/contract-surface.json` (discovery globs, operation pattern,
  integration ref) and `.fairy/contract-closure-lineage.json` (accepted
  records per increment) — and ships both in the release package, whose build
  fails if either is omitted.
- Runtime package version is 0.2.34.

## 0.2.33

- **Risk-aware Helix blocker convergence** (#94): adds the strict
  `helix_blocker_triage` record and `fairy blocker` validator/renderer. Every
  finding binds a concrete failure sequence and preconditions to probability,
  impact, fix estimate, and evidence. Only explicit sourced deadlines and
  fresh coarse usage from a primary check or session-owner observation may
  create convergence pressure. Secret/credential, data-loss, production,
  authority/permission, security, and required-acceptance floors remain
  non-deferrable. A low residual-risk non-floor finding may move to an issue
  only with independent reviewer concurrence, a same-repository issue, an
  owner-visible report, and exact final readback. Implementers receive one
  evidence-backed failure-sequence objection, followed by one finding-reviewer
  rebuttal and, after rejection, one distinct-reviewer tie-break; unresolved
  state remains fail-closed. Draft 2020-12 schema controls, runtime hostile
  controls, an auditable sample, CLI/package/install parity, Helix/loop/usage
  routing, and derived Markdown preservation are included. Runtime package
  version is 0.2.33.

## 0.2.32

- **E3 minimum-sufficient execution system** (#91): adds a machine-executable
  Estimate, Execute, and bounded Expand state machine for tool-using tasks with
  explicit acceptance checks and multiple plausible scope levels. The strict
  JSON ledger records the initial difficulty/scope/risk/confidence estimate,
  at most one cheap probe, risk-scaled verification, complete ordered evidence
  reuse, monotonic one-level expansion, and a hard stop on verified success.
  Validation, Closure Check, Tier A recall, authority, and safety remain
  non-suppressible, and each attempt must record evidence-backed outcomes for
  every required gate before verified success. A failed aggregate needs an
  actual failed check; `not_run` alone cannot unlock expansion. Canonical JSON
  and optional Markdown views use the shared rollback-capable bundle writer,
  including the pre-existing Task Card consumer. The distributed Draft
  2020-12 schema enforces the expressible evidence, aggregate-result, and
  default safety-gate floor with semantic instance controls; dynamic
  acceptance/custom-gate coverage remains bound to the authoritative
  `fairy e3 validate` command. Each attempt retains raw
  latency, token, tool-call, and inspected-item observations. `fairy e3`
  deliberately does not emit ACRR;
  that metric remains limited to external controlled evaluations with an exact
  oracle minimum. `fairy e3` thin dispatch, schema,
  Markdown review view, seven lifecycle cases, self-controls, skill routing,
  paper provenance and license boundary, package references, and plugin
  mirrors are included. Runtime package version is 0.2.32.

## 0.2.31

- **Cross-file distributable Markdown reference gate** (#7): broadens CI and
  install-smoke validation from `SKILL.md` alone to every Markdown file in all
  three distributed skills. Inline-code and standard Markdown-link
  destinations resolve through one shared package-contained resolver with
  exact portable path names, symlink rejection, ambiguity detection, and
  positive/hostile controls for links, nested code spans, dangling targets,
  package escapes, and case aliases. Previously dangling repo-only references
  now use installed-skill paths or explicit public source URLs. The README
  records the literal local adapter-manifest validation command. Runtime
  package version is 0.2.31.

## 0.2.30

- **Measured workflow impact scoreboard** (#13): adds a strict JSON scoreboard
  for benchmark and normal-task runs, with isolated baseline / Fairy Tale
  comparison contracts, pass counts and scores, elapsed time, cost, complete
  token totals, regression notes, immutable artifact identity, and per-card
  utilization / contribution telemetry. Example runs are excluded from
  measured aggregates by default, with bidirectional source-label / artifact
  marker validation preventing illustrative artifacts from being relabeled as
  measured evidence; unpaired runs cannot claim uplift; private paths are
  redacted. The committed sample consumes the routing-evaluation
  ledger by SHA-256 and recomputes its pass rate, cost, tokens, and complete
  card utilization map. Every run artifact binds to a typed source-registry
  record with the same path and SHA-256; official, measured, example, and
  context evidence cannot be interchanged. Routing structure is recognized
  independently of its required prompt/case/scorer identity fields, and those
  fields fail closed when absent or malformed without treating generic
  model/results/summary or execution-policy metadata as routing evidence.
  An exact routing content type is a shape-independent hard class signal;
  legacy artifacts without it require both routing outcome/card/path result
  fields and routing outcome/path/utilization summary fields. Generic
  reproducibility digests and category/classification metadata do not classify
  an artifact. Producer field
  coverage is checked separately through an explicit, disjoint generic versus
  routing-specific partition, including partial routing signatures.
  Malformed nested values produce field-scoped validation errors before
  derived operations. The derived
  Markdown review view preserves regression and complete card outcome/token
  evidence alongside deltas. `fairy scoreboard` thin dispatch, strict
  schema/runtime parity controls, feedback-governance link, adapter, package
  references, and plugin mirrors are included. Runtime package version is
  0.2.30.

## 0.2.29

- **Bounded Fairy Fusion automatic trigger decisions** (#12): adds
  `fairy fusion --auto-check --state-json ...` as a strict, deterministic
  decision command for repeated failure signatures, missing required
  Validation Ledgers, empty or meaningless expected artifacts, review
  conflicts, and explicit requests. The result records trigger reasons,
  reviewer cap, recursion depth and one-level cap, intended review artifact
  path, observed state, and canonical input SHA-256. Automatic checks are
  decision-only: they never launch reviewers, call a provider, retry work, or
  recurse beyond depth 1. Closed Draft 2020-12 input/output schemas, malformed
  and positive self-controls, unified `fairy` dispatch, shared SWE failure
  normalization, source-checkout docs, harness/process-card updates, adapter
  contract updates, package references, and plugin mirrors are included.
  Runtime package version is 0.2.29.

## 0.2.28

- **Repository Fairy profiles** (#11): adds the optional, closed
  `.fairy/profile.json` contract for repository-specific required validations,
  prohibited actions, recommended steps, and artifact paths. Task Card creation
  discovers the nearest Git-root profile, projects required validations and
  prohibitions into the executable task contract, and captures the complete
  profile with a recomputable canonical SHA-256 snapshot. Validation Ledger
  initialization copies the exact snapshot, link validation rejects drift, and
  both Markdown views preserve all profile rules. `fairy doctor` now validates
  the caller repository profile before residency and adapter checks. Discovery
  follows Git's authoritative root and requires the exact portable
  `.fairy/profile.json` names, so nested marker and case-alias drift fail
  closed; absence remains a compatible GREEN fallback. Profile commands remain
  declarative and are never executed as
  hooks. Shared profile/snapshot schemas, a Fairy Tale repository sample,
  positive and hostile controls, 16 artifact cases, mirrored docs, and package
  references are included. Runtime package version is 0.2.28.

## 0.2.27

- **Unified Fairy CLI** (#8): adds the executable repository entrypoint
  `fairy`. `fairy doctor` runs the existing residency and Rust adapter
  validators through one aggregate, fail-closed command; `fairy validate`
  runs the deterministic repository suite with discoverable `--list`,
  `--dry-run`, and repeatable `--only` selection. The validation registry is
  now the CI execution path instead of a second workflow-maintained command
  list. `fairy task-card` and `fairy ledger` delegate to the canonical #9/#10
  artifact engine, preserving direct script compatibility and caller-relative
  artifact paths. The CLI resolves repository checks relative to its own
  executable, continues through independent checks so one failure does not
  hide another, and exits non-zero on any failed or unexecutable step. The
  skill-only installer remains host-neutral and does not install executables or
  mutate `PATH`; the CLI is explicitly source-checkout tooling. Deterministic
  self-controls, CI doctor execution, English/Japanese quick-start examples,
  and command-boundary documentation are included. Runtime package version is
  0.2.27.

## 0.2.26

- **Task Card and Validation Ledger artifacts** (#9, #10): adds a canonical
  JSON artifact engine at `scripts/task_artifacts.py` for bounded coding,
  research, security, and benchmark work. Task Cards require objective,
  success criteria, allowed targets, constraints, explicit elapsed/tool/
  subagent/search/token-or-cost budgets, stop conditions, validation plan, and
  a ledger path; no organization-specific or universal budget defaults are
  imposed. Validation Ledgers link back to the Task Card by path and task ID,
  record checks as `pass` / `fail` / `blocked` / `not_run` with commands,
  artifact paths, blockers, and remaining risks, and fail closed on completion
  while any planned check is missing or non-passing. The lifecycle supports
  init, explicit add/replace, complete/blocked finalization, link validation,
  and Markdown rendering while keeping JSON as the sole source of truth.
  Strict Draft 2020-12 schemas, 12 acceptance cases, deterministic self-
  controls, CI wiring, user docs, and plugin companion parity are included.
  The future unified `fairy` CLI may delegate to this engine rather than clone
  its contracts. Runtime package version is 0.2.26.

## 0.2.25

- **Helix Loop Communication Harness** (#68): adds an organization-neutral
  turn contract for active agent-to-agent implementation/review loops. Active
  handoffs begin with the transport profile's counterpart address (raw mention,
  stable name, and literal ID for Discord/OpenAB) and carry a repo-qualified
  issue/PR, branch and exact head, checks, blocker, next action, expected
  responder/checkpoint, owner-needed state, and source/run refs. Action-bearing
  handoffs and state changes require an artifact-bound acknowledgement; a
  missing acknowledgement gets one bounded re-notification before the loop
  profile's escalation or reassignment path. Bare issue numbers, silence-as-
  success, infinite mention retries, and authority inferred from mention text
  are rejected. Cadence, stall thresholds, DND, watchdogs, roles, merge
  authority, and same-account policy remain inputs from the existing Loop
  Engineering profile rather than universal constants; a hard stall triggers
  readback/escalation, never process timeout or forced termination. The card
  records `bonginkan/north-star-os#45/#46` as internal deployment evidence
  (private repository; access required and not independently public-verifiable)
  while explicitly excluding their fixed bot names, role split, and
  30/20/45-minute values from the universal contract. Adds positive handoff
  and incidental-mention negative routing controls. Runtime package version is
  0.2.25.

## 0.2.24

- **Active DRY and clone-family consolidation gate** (#78): changes minimum
  implementation practice from the fewest edited lines to the minimum coherent
  design. The Implementation Validation Gate now searches for an existing
  abstraction before editing, triggers a codebase-wide family enumeration when
  a clone is found, consolidates every confirmed member in the same validated
  increment, reruns the search after editing, and treats fewer independent
  maintenance paths and subtractive diffs as completion evidence. The
  Refactoring Similarity Harness is now language-neutral and applies to ordinary
  patches as well as broad refactors; repository-native tools remain preferred,
  with symbol/call-site/text search plus reviewer inspection as the fallback.
  Rule-of-three is a signal rather than a mandate; different ownership,
  lifecycle, failure semantics, or change cadence can justify an explicit
  `keep-intentionally` result. Public/persisted surfaces use migration or
  deprecation in the same consolidation plan, while generated/vendor/history/
  forensic/mirrored exclusions require ownership and parity evidence. The
  existing Excess taxonomy is reused rather than cloned. The process record now
  captures family identity, complete membership, classifications, migrated call
  sites, removed private paths, compatibility treatment, before/after
  maintenance paths, validation, and residual members. Adds ordinary-patch and
  semantic-look-alike routing controls. The active SWE benchmark runner and
  benchmark-feedback skill/ledger use the same pre/post family-closure contract
  instead of retaining a smaller-local-abstraction prompt clone. The defensive
  patch card also routes semantic clones to the same gate while retaining its
  scoped patch-first rollout contract. Extracted-card provenance now
  containment-checks snapshot/card paths and allows reviewed
  post-extraction evolution only when the current-body hash is bound to a live
  same-repository GitHub issue's stable node ID and a title/body anchor. Runtime
  package version is 0.2.24.

## 0.2.23

- **UI Design Best-Practices Harness (build-grade expansion)** (#76): extends
  the existing design-review lens into a construction contract for real UI
  work. The harness now starts from the governing design system and maps
  primitive -> semantic -> component/state tokens; inherits bounded spacing
  and type scales instead of imposing a universal numeric grid; treats every
  already-supported theme as a Tier A companion without inventing new themes;
  and fixes grid, alignment, measure, density, responsive transformation,
  information architecture, progressive disclosure, and action hierarchy
  before component placement. New business-surface contracts separate
  normative accessibility outcomes, conditional WAI techniques, and scoped
  authored completeness prompts for forms, tables/data views, dashboards, and
  pricing/checkout disclosure and recovery.
  The accessibility floor now names WCAG 2.2 focus order/visibility, reflow at
  320 CSS px width or 256 CSS px height as applicable, non-text contrast at
  3:1, text contrast, target size, labels, errors, keyboard use, and reduced
  motion. State coverage is a component x
  viewport x supported-theme matrix. Rendered acceptance now records stable
  screenshot baselines/diffs (framework-neutral; Playwright is an example)
  with render-environment, revision/hash, diff/mask, and update-approval
  provenance; baseline replacement never substitutes for defect review.
  Code-only review discloses `visual not measured`, and design-class GUI
  Dogfood QA findings loop back into the brief/token/component/state contract
  before rerender. Sources expand to W3C WAI, DTCG 2025.10, USWDS, NN/g, and
  Playwright, all checked 2026-07-16. Adds a production billing form/table
  routing fixture while retaining both existing UI routes and the pure
  divergent-layout negative control. Runtime package version is 0.2.23.

## 0.2.22

- **Finance Proposal Completeness Gate (new card + fail-closed checker)** (#74):
  adds `references/cards/finance-proposal-completeness-gate.md` — a fail-closed
  completeness gate for artifacts carrying financial claims (proposals, pricing
  models, business cases, forecasts), fired from artifact content rather than
  task wording. Arithmetic that reconciles is not completeness: every central
  claim needs a ledger record (metric definition, period/currency/unit/tax
  basis, displayed vs recomputed value, revenue drivers, cost drivers); every
  evidenced or structurally entailed cost driver carries exactly one
  disposition out of `amount` / `included-in` / `not-applicable-with-evidence`
  / `TBD`, with `TBD` blocking (never an accepted zero) and `not-applicable`
  requiring citable evidence. The Unit Economics Assumption Closure sub-gate
  derives entailed rows from the stated business model (channel economics for
  partner-led sales; setup/onboarding, support, security, incident response
  for implementation/managed service; feasible conversion/churn cohort
  schedules for recurring models). Aggregate margins inherit component
  coverage; sign-off requires heterogeneous reviewer roles
  (arithmetic/reconciliation + completeness/negative-space) bound to the same
  immutable artifact hash. Enforcement is deterministic and never
  self-attested: `scripts/finance_completeness_check.py` re-executes each
  formula over its stated inputs (restricted AST evaluator), recomputes
  aggregates from required normalized weights, rejects unknown schema keys,
  non-finite values, duplicate/unnamed drivers, dangling or basis-less
  `included-in` targets, uncited `not-applicable` evidence, and
  malformed/unregistered business models (closed model registry). Every
  formula input is bound to the ledger via `input_bindings` (cost driver /
  revenue driver / expression / declared assumption) with numeric
  reconciliation; `included-in` requires an in-ledger target, allocation
  basis, anchored source, and matching period; claims require assumptions,
  evidence status, sensitivity, and cross-claim dependencies; cohort
  schedules must be complete, domain-valid, and numerically consistent with
  the claims' revenue drivers, and recurring revenue/forecast claims must
  use conversion/active-months in their bound arithmetic; assumptions that
  feed arithmetic record their numbers and are reconciled; amount costs must
  be consumed by the bound math on margin/profit claims; margins must be
  ratio-shaped and ratio-unit; sign-offs record verdict + per-claim coverage
  per required role and reject malformed entries, unknown roles, and role
  substitution; closure state (blockers/uncertainties) is explicit and open
  blockers can never pass; uncertainties are structured, impact-bounded
  records and a decision-reversing uncertainty blocks outright. The binding
  space is closed over the executed formula (phantom inputs/bindings and
  unconsumed assumptions block); claim sources must be locators; amounts
  carry their own anchored source and period; included-in requires a covered
  scope and a resolved host; margins are ratio-unit quotients over a
  revenue-bound denominator. Reference is not effect, and perturbation
  reaches the LEDGER anchors end-to-end through bindings (a *0 hidden inside
  a binding blocks; cost anchors must move margins/profit DOWN; one binding
  never mixes revenue and cost anchors); dependency/aggregate graphs must be
  acyclic with weights in (0,1] and period-consistent components; amounts
  carry an explicit stated basis; included-in carries the absorbed amount OR
  an allocation basis (per the issue contract); the ledger records its
  observed frame, a count-checked central-claim inventory, and an artifact
  verdict (approve/pass_with_warnings/block) plus explicit minimum closure
  conditions; anchors are direction-tested (cost up => margin down, revenue
  drivers up => revenue up, cohort factors never in divisors); aggregate
  weights must match component revenue shares and components share the
  claim's basis; the central-claim inventory names exact claim IDs;
  materiality thresholds come from a closed, capped unit registry with a
  locator-anchored basis; uncertainty impact bounds are numeric with
  cumulative materiality evaluated against that threshold; uncertainty
  reversal flags are required booleans; every sign-off entry is
  individually complete with non-empty claim-anchored coverage. Coverage
  is refutable by execution: every class in the checker's canonical
  REASON_CLASSES list (106 classes) must be covered by an executed RED
  fixture in the acceptance run — deleting a rule or its fixture turns CI
  red; no hand-maintained coverage claims. Round 8 adds: operating-profit
  revenue direction, per-expression cohort divisor/duplication semantics
  (correct recurring margins no longer false-block), aggregate weights
  anchored to EXECUTED revenue (setup fees included), recurring
  conversion/churn required, cross-page conflict records with anchored
  resolutions, evidence-anchored numeric impacts (default cap 10%),
  string-typed coverage, and the issue-canonical PASS /
  PASS_WITH_WARNINGS / BLOCK verdict enum. Round 9: cohort compounding is
  caught across alias boundaries (multiplicative composition of
  factor-bearing branches) while additive streams stay green; executed
  revenue dedupes aliased streams so weights cannot be faked; materiality
  caps restored to the #74 defaults (5 margin points / relative 10%); a
  `segment` identity axis keeps legitimate cross-segment differences from
  false-blocking as conflicts. Round 10: cohort usage is judged by symbolic
  degree on the fully substituted derivation (additive streams green,
  alias-split compounding red, margins analyzed per numerator/denominator);
  identical or value-overlapping revenue streams can never enter one claim
  twice; segments are casefolded canonical identities from an anchored
  ledger registry. Round 11: nonlinear cohort quotients and same-factor
  sums inside one expression block; stream identity is fully declarative
  (distinct anchor-set signatures — scaled/padded copies block, equal-value
  distinct-anchor streams pass; no proximity heuristics); segment
  canonicalization collapses whitespace and rejects registries whose
  entries collapse to one canonical name. Round 12: cohort factors carry an
  exact coefficient-one contract (2*conversion blocks, rate fractions
  green); stream identity is DECLARED via an anchored `revenue_streams`
  registry (source-backed ids, not inferred anchor sets) with exact
  canonical-expression dedup; segment and stream canonicalization apply
  Unicode NFKC. Round 13: cohort coefficients are position-aware share
  contracts (numerator constants <=1, divisor constants >=1 — /2 rates
  green, /0.5 and masked 2x red); additive cohort offsets (1+conversion)
  block; canonical expressions fold neutral elements (*1 mints nothing);
  stream ids are non-empty, unique across aggregate components, and
  malformed stream_ids maps are reasoned blocks (never exceptions); ONE
  canonical-identity normalizer (NFKC + whitespace + casefold) serves
  registry, membership, and conflict grouping. Round 14: finite constant
  subexpressions and arithmetic identity elements (`+0`, `-0`, `*1`, `/1`)
  share one canonical expression, constant ratios such as `100/200` retain
  valid fractional-share semantics, `stream_ids` is closed over executed
  revenue inputs, and aggregate revenue plus leaf stream identity resolve
  transitively so a nested aggregate cannot launder duplicate revenue or
  bypass weight anchoring. Round 15 normalizes finite constant factors across
  multiplication and division, so equivalent shares such as `x*0.5`, `x/2`,
  and `x*100/200` cannot mint distinct streams. Round 16 routes cancelling
  root unary-sign chains through the same coefficient normalization, so
  `-(-x/2)` is also `x/2`. Selftest carries 148 red/green/hostile controls
  (every PR #75 round-1..16 review probe and an add/remove metamorphic flip);
  one hundred fifty-six sanitized
  cross-industry acceptance fixtures
  (positive controls for bounded uncertainties, per-unit recurring margins,
  amount-only included-in, pass-with-warnings, resolved conflicts, correct
  recurring margins, segment-differentiated margins, and additive cohort
  streams) in
  `fixtures/finance-completeness/cases.jsonl` (agency, SaaS, marketplace,
  managed service, hardware, channel sales), all wired into CI. `redundancy`
  added to the listing recall-floor triggers. Router row +
  Choose-a-route bullet + description trigger wired in SKILL.md, and three
  routing-eval fixtures (finance-01/02 + OCR-only negative control
  finance-03). Vocabulary is standard managerial-accounting usage; the gate
  constrains completeness and disposition, not any org-specific accounting
  policy.

## 0.2.21

- **Token Consumption Optimizer Harness (new card + record)**: adds
  `references/cards/token-consumption-optimizer-harness.md` and the
  `references/process/token-recipe-record.md` template — the success-side
  dual of the Evaluated Feedback Loop. After a validated success likely to
  recur, capture the exact working process as a recipe (goal, trigger,
  preconditions, steps, verification, gotchas, baseline cost); on the next
  matching task, replay the recipe instead of re-deriving the process
  (replay-before-re-derive), with a staleness guard on preconditions,
  full-strength validation on every replay (verification is never memoized),
  judgment/process separation (memoize procedures, never conclusions),
  authority/permission/approval and production safety gates re-judged on
  every replay (a recipe records a gate's position, never its outcome), and
  measured suppression against the first-run baseline (unproductive recipes
  get pruned via the excess pass). Hot recipes promote to skills or utility
  scripts; composes with API-level prompt caching. Router row +
  Choose-a-route bullet + description trigger wired in SKILL.md, process.md
  index row, sources grounded in Anthropic agent-skills best practices and
  prompt-caching docs (checked 2026-07-07), and two routing-eval fixtures
  (tok-01/tok-02).

## 0.2.20

- **UI Design Best-Practices Harness (new card)**: adds
  `references/cards/ui-design-best-practices-harness.md` — the design-side
  counterpart to GUI Dogfood QA. Design brief before pixels; canon
  compliance / anti-reinvention (reuse existing tokens and the governing
  design system); NN/g's ten usability heuristics as the review lens;
  measurable simplicity metrics (clicks-to-action, time-on-task, task
  success); WCAG 2.2 numeric floors (SC 1.4.3 contrast 4.5:1 / 3:1 large,
  SC 2.5.8 target 24x24 CSS px); full state coverage as Tier A entailed
  companions; rendered-artifact validation with a "visual not measured"
  disclosure for code-only review. Router row + Choose-a-route bullet +
  description trigger wired in SKILL.md, UI/UX design canon section in
  sources.md (primary/near-primary vs. secondary field reference tiers),
  and two routing-eval fixtures (ui-01 build / ui-02 design review) paired
  against the "propose N layouts" negative control.

## 0.2.19

- **process.md per-record split (#57 WI3)**: the 49 record templates in
  `references/process.md` moved byte-identically into
  `references/process/<slug>.md`; process.md is now a 7.5KB index (was
  55.8KB), so a task loads only the record it needs. Shares the
  byte-preserving extraction/verify core with the mode-pattern split
  (snapshot + byte-range/sha256 manifest, repo-relative paths, `--verify`
  in CI); mode-card guarantees unchanged (28/28). New `process_index`
  gate (dangling/orphan/duplicate RED), process records in the two-way
  inventory parity, and residency markers scanned across the index +
  records.

## 0.2.18

- **Listing-overhead reduction (#58 Increment 3)**: skill descriptions slimmed
  recall-first (fairy-tale ~250 -> ~154 est tokens; total listing cost -25%)
  with a machine-enforced trigger-recall floor; new
  `skill_listing_overhead_check.py` gates description budgets, required
  triggers, same-home local+plugin double registration (classified
  stale / diverged / intentional-override), and the SessionStart hook's
  essential-marker floor (in CI). Residency `--inject` and installed-root
  checks now aggregate `references/cards/`, fixing the false
  "residency degraded" warning on post-#57 installs. Secondary-skill
  name-only override documented; standing instruction kept intentionally
  (all lines are protected safety/routing markers).

## 0.2.17

- **SKILL.md router restructure (#57 Increment 2)**: the 28 mode-pattern harness
  bodies moved byte-identically into `references/cards/<slug>.md`; SKILL.md is now
  a 215-line compaction-safe router (was 765 lines), so the whole body — including
  the routing table — survives the 5,000-token post-compaction re-attach window.
  Verbatim move, no semantic edits. Ships the deterministic extractor with
  committed pre-extraction snapshot + byte-range manifest and a `--verify`
  byte-parity gate (in CI), a `router_cards` integrity gate (dangling / orphan /
  duplicate refs RED), card-aware two-way inventory parity, residency markers
  checked across SKILL.md + cards, and the token/line budget checker enforced
  fully in CI.

## 0.2.16

- Added the **Creator-Proxy Elaboration (WWCD)** harness: acting as a relayed
  creator/principal proxy by elaborating the creator's intent as an
  evidence-grounded, confidence-tagged HYPOTHESIS -- never as authority. Ships the
  ledger schema (`creator-proxy-elaboration-ledger`), a teeth-beyond-presence
  enforcement checker (`creator_proxy_elaboration_check.py`, `--selftest` = 3 GREEN controls + 21 RED gates), a worked example record, and the tri-agent dogfood prompt +
  evidence pack. Authority stays a separate identity/policy decision (never derived
  from WWCD); evidence refs must resolve; high-risk action surfaces cannot be
  self-labeled below high stakes.

## 0.2.15

- Added the **GUI strand** to the helix e2e layer, distilling two browser-dogfood
  skills (NousResearch hermes-agent `dogfood`, Vercel `agent-browser` dogfood) into
  `references/gui-dogfood-qa.md`: test the GUI as a user (black-box), check the
  console after every interaction, repro-grade the evidence (interactive → video +
  step screenshots / static → one annotated shot), and tag findings by severity and
  category. Scope is white-box (surfaces from code/deploy), execution is black-box.
- Made **GUI present → GUI dogfood mandatory** an enforced gate (the 8th gate of
  `general-e2e-completion.md`). The e2e-coverage ledger now answers the GUI question
  for every run via a required `gui` block; `scripts/e2e_coverage_check.py` fails
  closed on a missing `gui` block, a `route`/`panel`/`flow` surface declared
  `has_gui:false` (closure contradiction; an API `endpoint`/`job` is not GUI), a
  performed dogfood lacking a console check / taxonomy / browser-artifact evidence
  or carrying fewer tracked REDs than `issues_found`, or an outstanding dogfood
  without a tracker URL. A GUI dogfood is either performed or carried as an
  explicitly tracked-outstanding gap (the GUI analog of RED → tracked), never
  silently skipped.

## 0.2.14

- Added a scope gate / task-type gate so a workflow-less, simple
  divergent-generation prompt (e.g. "propose N variants of X" with no review,
  migration, security, or legal framing) skips the Closure check and
  negative-space machinery instead of over-firing on it. The heavy harness stays
  fully active when the request is explicitly critical ("批判的に", "抜け漏れ",
  "レビュー") or carries review / migration / security / legal context.
- Pinned the new gate phrases as residency markers so the carve-out cannot
  silently regress, and added the loop-engineering-automation residency file set
  to the residency checker.

## 0.2.11

- Consolidated the overlapping Generalization and Latent Structure harness
  routes into one implicit-contract discovery harness for hidden rules,
  executable/checkable world models, tacit intent, false analogies, and
  latent-structure ledgers.
- Added an implicit-contract discovery family router to `process.md` so
  generalization, tacit-intent, latent-structure, closure, negative-space, and
  excess/redundancy records are selected deliberately instead of duplicating the
  same reasoning across multiple ledgers.
- Preserved the Closure / Negative-Space / Excess safety harness as a separate
  review and consolidation gate, with routing guidance to hand hidden-rule work
  to the consolidated implicit-contract harness.
- Updated residency markers so the new router is checked in distributed skill
  copies.

## 0.2.10

- Added the Spiral Engineering harness so loop revolutions can raise an
  explicit altitude axis: autonomy, abstraction, scope, delegation, reusable
  capability, or residual-risk burn-down.
- Grounded spiral mode in risk-driven iteration and double-loop learning:
  identify the highest-risk uncertainty, burn it down before expansion,
  engineer only the risk-cleared target, then evaluate whether governing
  variables should change before the next revolution.
- Added a double-helix structure for spiral revolutions: an execution strand
  for delivery and risk burn-down, a learning/governance strand for
  double-loop updates, and evidence-pairing gates that prevent flat loops or
  unsupported self-modification.
- Added anti-parallel proofread / mismatch-repair rules and semi-conservative
  governance-template handoff so spiral improvements can compound without
  copying unvalidated process mutations.
- Added safety-floor rules so spiral engineering cannot weaken DND, approval,
  security, credential, deploy, external-mutation, meeting-join, owner-mention,
  branch/merge, or secret boundaries.
- Updated loop-engineering references, source grounding, residency markers,
  SessionStart injection, release metadata, and plugin manifests so spiral
  engineering tasks keep the Fairy Tale harness active.

## 0.2.9

- Added a Silent-Loop Auto-Resume Watchdog for active loops that go quiet
  because of missed agent mentions or omitted handoffs, including
  `last_loop_activity`, `next_expected_touch`, `auto_resume_after`, bounded
  checkpoint recovery, retry caps/backoff, and explicit loop-blocker fallback.
- Required a concrete scheduled wake actuator (`ScheduleWakeup`, or a narrowly
  scoped cron/launchd watchdog when approved) before claiming time-based
  auto-resume, so a fully silent loop can recover without relying on an
  already-active agent to notice the timer.
- Clarified that auto-resume happens only in the local loop thread and does not
  bypass DND, parked, approval-blocked, closed, security, credential, deploy,
  external-mutation, or owner-escalation gates.
- Updated loop-engineering references, residency markers, SessionStart
  injection, and plugin metadata so silent-loop auto-resume tasks keep the
  Fairy Tale harness active.

## 0.2.8

- Added Cross-Channel Loop Command guidance for session owners coordinating
  multiple repo/channel loops, including active-loop queues, stale-loop
  sweeps, single intake ownership, thread-local topic isolation, and explicit
  handoff/repair rules.
- Updated loop-engineering references, residency markers, SessionStart
  injection, and plugin metadata so cross-channel loop command tasks keep the
  Fairy Tale harness active.

## 0.2.7

- Added Do Not Disturb operating-window guidance for loop agents, including
  human-set per-agent windows, timezone-qualified records, assignment
  exclusion, non-urgent mention suppression, safe-boundary handoff, and
  auto-resume checks.
- Updated loop-engineering, load-balancer, residency, SessionStart injection,
  and plugin metadata so DND management tasks keep the Fairy Tale harness
  active.

## 0.2.6

- Added a Usage Reading Reference to the Usage-Aware Multi-Agent Load Balancer
  so Codex and Claude Code capacity checks use concrete local rate-limit
  surfaces when available while keeping raw tokens, billing, secrets, and
  provider internals out of public ledgers.
- Updated residency markers and SessionStart injection so usage reading tasks
  keep the Fairy Tale harness active.

## 0.2.5

- Added the Usage-Aware Multi-Agent Load Balancer harness for assigning
  session-owner, implementation-owner, reviewer, and specialist-tool roles
  from coarse operational capacity, runtime install currency, blocking status,
  and fixed capability gates.

## 0.2.4

- Added the Excess / Redundancy / Legacy-Surface Discovery harness as the
  subtractive pair to Negative-Space Discovery, with false-positive deletion
  guards, migration/deprecation tiers, and source-grounded review criteria.

## 0.2.3

- Added the Loop Engineering and Job Automation Harness for persistent
  repo/channel operation, periodic external-channel ingestion, and draft-first
  business workflow automation.
- Added process cards for loop operating records, external-channel ingestion,
  job automation delegation, and meeting proxy setup.
- Added a source-grounded operating model for Fairy Tale self-pilot, email
  drafting, Google Drive/Docs/Sheets edits, Calendar/Meet workflows, and
  approval/credential boundaries.
- Added an `agent-lime`-derived non-secret meeting proxy setup checklist for
  Vexa, Calendar, media gateway, speech agent, STT/TTS, Firestore, webhook,
  internal-token, and Cloud Run env/secret boundaries.
- Updated residency checks and plugin discovery metadata so loop engineering
  and job automation updates are detected across repo copies and packaged
  plugin artifacts.
- Included the loop engineering operating model in standalone skills packages
  and updated SessionStart residency injection so loop engineering and job
  automation task families activate the Fairy Tale harness at runtime.
- Tightened owner mention policy so routine loop status stays owner-visible
  without mentions, while mentions are reserved for thread start,
  tri-MISA agreement, approval, final sign-off, and major escalation milestones.
- Added install-smoke coverage and skill-local companion references so
  `install.sh --agent codex|claude|agents` installs every Markdown reference
  needed by `skills/fairy-tale/SKILL.md`.

## 0.2.2

- Added closure/frame-completeness checks before negative-space discovery so
  agents do not treat a visible or stated item count as exhaustive without
  evidence.
- Added negative-space discovery, recall/noise guards, Tier A/B/C handling,
  precision/taste learning signals, and problem-finding cards to the Fairy Tale
  process templates.
- Updated skill and plugin discovery descriptions so closure and latent-need
  review tasks can trigger the Fairy Tale skill.

## Public Release Preparation

This release prepares Fairy Tale for public distribution as an Apache-2.0
workflow-augmentation package.

Highlights:

- Added root Apache-2.0 licensing and NOTICE terms.
- Clarified that Fairy Tale studies public reports and reproducible workflow
  patterns, not restricted model weights or bypass techniques.
- Packaged Fairy Tale skills for generic agents, Codex, and Claude Code.
- Added Codex and Claude Code plugin manifests.
- Included defensive security constraints, best-practice gates, benchmark
  validation notes, OSS watch notes, adapters, runners, and sample comparison
  outputs.
- Added a wide Fairy Tale logo asset for repository branding.

Known boundaries:

- Benchmark rows are reproducible local measurements, not final leaderboard
  claims.
- Third-party repositories, datasets, benchmark materials, reports, and assets
  remain under their own licenses and terms.
- Security workflows are defensive-only.
