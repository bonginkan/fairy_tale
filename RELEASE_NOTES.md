# Release Notes

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
