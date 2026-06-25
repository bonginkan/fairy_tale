# Release Notes

## 0.2.10

- Added the Spiral Engineering harness so loop revolutions can raise an
  explicit altitude axis: autonomy, abstraction, scope, delegation, reusable
  capability, or residual-risk burn-down.
- Grounded spiral mode in risk-driven iteration and double-loop learning:
  identify the highest-risk uncertainty, burn it down before expansion,
  engineer only the risk-cleared target, then evaluate whether governing
  variables should change before the next revolution.
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
