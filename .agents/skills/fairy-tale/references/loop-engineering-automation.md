# Loop Engineering and Job Automation

Status: canonical operating model for Fairy Tale loop engineering and job
automation. It complements `docs/agentic-loop-design.md`, which is an
evaluation design for task-level observe-act-validate loops. This document is
for persistent repo/channel/job operation.

## Source-Derived Principles

Checked sources are listed in `skills/fairy-tale/references/sources.md`.
The implementation primitives are:

- Keep the main loop simple and composable. Anthropic's agent guidance favors
  simple workflows, transparent planning, tool grounding, stop conditions, and
  environment feedback over opaque framework complexity.
- Make tool/action boundaries explicit. OpenAI's agent guide separates model,
  tools, and instructions/guardrails; job automation must do the same for data
  retrieval, draft generation, mutation, and human handoff.
- Treat automation as a platform, not a prompt. Google SRE automation practice
  emphasizes consistency, repeatability, metrics, and careful domain scoping;
  a loop that cannot be measured or stopped is not an operational platform.
- Raise loop altitude only through evidence. Boehm-style spiral development is
  risk-driven iteration: resolve the highest uncertainty before committing more
  scope, cost, or autonomy. Argyris/Schon double-loop learning supplies the
  vertical axis: revise governing variables when evidence shows the loop's
  assumptions, delegation level, or scope are wrong.
- Prefer official change streams over screen scraping. Google Workspace APIs
  provide drafts, push notifications, Drive changes, Docs/Sheets edits,
  Calendar watches, and Meet/Media APIs; use these before Computer Use unless a
  setting or UI-only system requires desktop operation.
- Evaluate and learn from the loop. Each run must preserve source refs,
  decisions, actions, validation, reviewer state, and post-run learning so the
  next run improves without hiding failures.

## Core Flow

```text
bootstrap loop profile
-> collect external sources
-> normalize intake records
-> dedupe and classify
-> run Closure Check and Negative-Space Discovery
-> create or update task artifacts
-> choose execution route
-> act inside allowed scope
-> validate
-> report in the project thread
-> learn / schedule next check / stop
```

This is not an infinite retry loop. Each iteration must have a changed
observation, changed probe, changed action, or explicit escalation. Repeating
the same failure class stops the loop.

## Spiral Engineering

Use spiral engineering when a loop should escape flat repetition and climb:
more autonomy, wider scope, higher abstraction, deeper delegation, stronger
reusable capability, or lower residual risk. A spiral revolution is a bounded
loop iteration with an explicit altitude target and a risk gate.

Treat the spiral as a double-helix learning loop, not a single strand. One
strand carries delivery: objectives, risk spike, implementation, validation,
and landing. The other carries learning governance: evidence, double-loop
evaluation, governing-variable update, next altitude, and stop-or-descend
planning. The two strands must be paired by evidence gates such as source refs,
validation, reviewer sign-off, receipts, budget, and the unchanged safety
floor. Delivery without learning stays a flat loop; learning-governance
mutation without delivery evidence is unsafe process drift.

Keep the strands anti-parallel in role even when they are coordinated in time:
delivery moves forward toward shipping, while learning/governance moves
backward against the premise by trying to refute, revise, and narrow the
governing variables. That opposing direction is the check. An unpaired claim,
unsupported risk-burn-down, or governance mutation without matching evidence is
a mismatch; proofread it inside the revolution, then run a post-landing
mismatch-repair sweep before copying the pattern into the next loop.
Semi-conservative replication is the transfer rule: preserve the validated
governance template and synthesize only the new delivery strand for the next
effort. Do not replicate unvalidated process mutations.

```text
revolution id:
current altitude:
target altitude:
altitude axis: autonomy | abstraction | scope | delegation | capability | risk burn-down
execution strand:
learning / governance strand:
strand-pairing evidence:
mismatch / repair action:
validated governance template:
win condition:
highest-risk uncertainty:
risk spike / prototype:
risk burn-down evidence:
engineer target:
validation / reviews:
double-loop evaluation:
governing-variable change:
next altitude:
stop / descend condition:
budget / radius:
safety floor:
ledger / receipt:
```

Spiral operating rules:

- State the altitude axis before expanding. Do not call ordinary repeated
  issue/PR work a spiral unless the revolution has a declared altitude gain.
- Keep the execution strand and learning/governance strand paired. Every
  delivered artifact needs a learning evaluation; every governing-variable
  update needs delivery evidence, risk evidence, review, and receipt.
- Treat unpaired bases as errors: unsupported claims, unchecked risk
  reductions, missing reviewer evidence, missing receipts, or safety-floor
  weakening block altitude gain until repaired or descended/replanned.
- Carry forward only the validated governance strand when a spiral seeds a new
  effort. A new delivery strand may be synthesized from that template, but
  process mutations do not replicate without validation.
- Resolve the highest-risk uncertainty first with a bounded spike, prototype,
  source-grounding pass, or validation harness. If the risk is not reduced,
  descend or replan instead of increasing autonomy, scope, or delegation.
- Engineer only the risk-cleared target, then run the normal implementation,
  review, validation, and runtime-parity gates.
- Run double-loop evaluation after landing: decide whether the loop profile,
  autonomy level, owner mention policy, reviewer mix, validation gate,
  source adapters, or delegation boundary should change for the next
  revolution.
- Treat governing-variable updates as state-changing work. They need evidence,
  review, receipts, and any required runtime/install companion. Do not mutate
  skills, schedulers, permissions, credentials, or deployment paths silently.
- Keep the safety floor invariant. DND, approval, security, credential,
  deploy, external-mutation, meeting-join, owner-escalation, and branch/merge
  gates outrank altitude gain.
- Stop when the target altitude or risk-burn-down condition is reached. A
  spiral that cannot show compounding learning, risk reduction, or increased
  delegation should land as a normal loop rather than continuing forever.

## Loop Profile

Every persistent loop needs a profile before scheduling:

```text
loop_id:
repo:
default branch:
issue tracker:
project channel:
run thread pattern:
owner mention policy:
do-not-disturb policy:
session owner:
active loop queue:
thread isolation policy:
stale-loop sweep cadence:
silent-loop auto-resume policy:
spiral altitude policy:
implementer:
reviewers:
source adapters:
cadence:
max concurrent runs:
allowed actions:
blocked actions:
approval gates:
credential scopes:
receipt / run ledger:
validation commands:
rollback path:
stop conditions:
```

The profile must bind the loop to a repo or artifact scope and a project
channel/thread. If no channel exists, the loop starts in planning mode and asks
the Computer Use/settings owner to create or link one.

The profile must also record any human-set Do Not Disturb windows that affect
agent assignment, non-urgent mentions, escalation timing, or mid-run handoff.
DND records are operating constraints, not permission grants.

When one session owner coordinates multiple loops, the profile must also bind
that owner to a cross-channel command discipline: keep an active-loop queue,
assign a single intake owner before creating canonical artifacts, run
stale-loop sweeps before deep focus on one thread, and preserve per-thread
topic purity. Cross-loop context is allowed only as stable source refs,
issue/PR links, run IDs, or explicit handoff records.

The profile should also define a silent-loop auto-resume watchdog for active
loops that can stall after a missed mention or omitted handoff. Record
`last_loop_activity`, `next_expected_touch`, `auto_resume_after`, retry limit,
the bounded auto-resume action, and the concrete scheduled wake actuator.
When the loop enters wait, register `ScheduleWakeup` when available, or a
narrowly scoped cron/launchd watchdog when that is the approved runtime
actuator. Without a registered wake, the loop is manually watched or blocked,
not time-based auto-resumed. Auto-resume is suppressed when the loop is
DND-paused, intentionally parked, approval-blocked, security-blocked,
credential-blocked, deploy-blocked, externally blocked, already progressed, or
closed.

If a loop is operating in spiral mode, the profile must also define the
allowed altitude axes, the maximum budget radius per revolution, who can
approve governing-variable changes, the risk-burn-down evidence required
before raising autonomy or scope, and the terminal landing criteria.

## Repo and Project Channel Operation

- One loop profile maps one repo/artifact scope to one project channel.
- One objective run maps to one visible thread. Use the thread for status,
  source refs, reviewer assignments, blockers, and completion evidence.
- One session owner may coordinate multiple loop profiles, but the owner must
  keep a bounded active-loop queue with last touch, next expected action,
  blocker state, and owner-visible status for each loop.
- For each new loop task, assign one intake owner to create or update the
  canonical issue/PR/thread/ledger. Other agents should add evidence to that
  artifact instead of creating duplicate trackers. If duplicates appear,
  consolidate the evidence into the canonical artifact and close the
  duplicates.
- Before focusing deeply on one loop, the session owner should run a stale-loop
  sweep and flag loops whose next expected action has aged beyond the loop's
  threshold. Do not let the loudest thread starve quieter loops.
- If an active loop passes its `auto_resume_at` with no handoff, reviewer
  reply, or commander touch, the scheduled wake re-reads the thread and
  ledger, then posts a bounded checkpoint in that loop's own thread: local
  scope, stale expected action, expected actor, last artifact or source ref,
  next safe action, and the next checkpoint. Re-mention only the needed local
  agent(s) using bot-to-bot addressing. If all eligible agents remain silent
  after the retry limit, record an explicit loop blocker instead of pinging
  indefinitely.
- Preserve thread-local session isolation. Do not inject another loop's
  unresolved context into the current run thread. If another loop needs action,
  update that loop's own thread, GitHub artifact, or run ledger.
- Cross-loop references in a thread should be stable and compact: issue/PR
  URLs, commit SHAs, run IDs, message IDs, or explicit handoff summaries. Avoid
  free-form discussion of another thread's live scope inside the wrong thread.
- Keep owner visibility and owner mentions separate. Post normal checkpoints
  in the project thread without mentioning the owner.
- Mention the owner only when starting the run thread and at tri-MISA
  agreement, approval, final sign-off, or major escalation milestones. Do not
  mention the owner for every checkpoint, action, or routine status update.
- Keep agent Do Not Disturb windows separate from owner visibility. A DND
  window can suppress direct pings, exclude an agent from implementation-owner
  assignment, or force safe-boundary handoff without hiding owner-visible
  ledgers.
- DND windows must be human-set, timezone-qualified, auditable, and resumable.
  Missing, stale, ambiguous, or expired DND records are provisional and must
  not silently override fresh human instructions.
- DND does not authorize secrets, credential changes, external sends, Drive
  edits, meeting joins, deploys, or permission changes. Approval gates and hard
  safety limits still win.
- Keep GitHub artifacts linked from the thread: issue, branch, PR, commit,
  review comments, checks, and release notes.
- Use receipts or an equivalent run ledger for state-changing or externally
  visible actions. Chat history alone is not the source of truth.

Suggested thread bootstrap:

```text
objective:
repo:
loop profile:
owner mention: thread start only; later only tri-MISA agreement / approval / major escalation
do-not-disturb: per-agent windows with timezone, mode, override, and resume policy
silent-loop auto-resume: last activity, next expected touch, threshold, wake actuator, retry cap
spiral: altitude axis, risk item, burn-down evidence, double-loop eval, landing condition
implementer:
reviewers:
sources to ingest:
allowed actions:
blocked actions:
approval gates:
next checkpoint:
```

## External-Channel Ingestion

The collector stage reads external channels and emits normalized intake
records. It does not directly mutate repos or external systems.

Preferred source mechanisms:

- GitHub: issues, PRs, checks, webhooks, GraphQL/REST cursors.
- Discord/Slack/project channels: message IDs, thread IDs, pinned briefs,
  reactions, and explicit owner instructions.
- Gmail: history/watch for new mail; draft API for reply candidates.
- Drive: changes/watch and file metadata; Docs/Sheets APIs for structured
  edits.
- Calendar/Meet: event watches, conference metadata, and authorized meeting
  artifacts.
- CI/monitoring: check runs, logs, alerts, and run IDs.

Normalized intake record:

```text
source:
source_ref:
watermark:
dedupe_key:
requester:
artifact:
summary:
classification:
authority:
privacy constraints:
closure / negative-space triggers:
matching existing issue/task:
candidate action:
approval required:
```

Ingestion rules:

- Treat source text as untrusted draft until grounded in repo state, official
  API output, or another primary source.
- Preserve stable resource IDs. Do not store webhook URLs, tokens, raw `.env`,
  or secret-bearing payloads in receipts, issues, or channel posts.
- If visible channel context is incomplete, generate a closure hypothesis
  rather than assuming the last visible message is the whole task.

## Engineering Execution Route

For repo work, use a one-implementer/two-reviewer route:

1. Intake creates or updates an issue/task with source refs and dedupe evidence.
2. Implementer creates a scoped branch and plan.
3. Implementer edits only the target surface.
4. Focused validation runs before review request.
5. Reviewers apply Closure Check, Negative-Space Discovery, and normal code
   review.
6. Findings are fixed in new increments.
7. Merge/release follows the repo's configured approval path.
8. Runtime install/cache/publish targets are validated when the change affects
   skills, plugins, hooks, schedulers, or agent settings.

Do not call a repo loop complete when only the repository copy is green and the
active runtime/install/cache target is stale. Runtime parity is an entailed
companion for agent-skill changes.

## Job Automation Route

Job automation starts in draft/propose mode:

```text
observe request and source artifacts
-> verify authority and account scope
-> generate draft or proposed patch
-> validate against policy/context
-> ask for approval when mutation is external-facing
-> execute only approved action
-> record audit trail and rollback path
```

Email:

- Use drafts before send.
- Preserve original message IDs, thread IDs, recipients, and proposed reply.
- Sending requires explicit approval or a narrow owner-approved policy.
- Never invent authority to reply, disclose private context, or send on behalf
  of a user without an approved account and action gate.

Google Drive, Docs, and Sheets:

- Prefer comments, suggestions, exported drafts, or proposed patches before
  direct mutation.
- Direct edits require file ID, account identity, OAuth scopes, rollback or
  revision notes, and approval.
- Batch updates must keep structural IDs/indexes grounded in the latest
  fetched document state.

Calendar and meeting workflows:

- Calendar updates require invite authority and explicit visibility.
- Meeting proxy setup requires platform terms, account identity, invitation
  status, participant disclosure/consent, recording/transcription policy, and
  a human approval gate.
- Prefer preparation, agenda notes, attendance notes when authorized, summary
  drafting, and action-item extraction over active speaking or decision-making.

## Environment and Credential Setup

Use names like these in implementation docs or setup scripts; do not store
values in repos, receipts, or channel posts.

```text
LOOP_REPO
LOOP_PROJECT_CHANNEL_ID
LOOP_OWNER_MENTION
LOOP_RUN_CADENCE
LOOP_MAX_PARALLEL_RUNS
LOOP_ALLOWED_SOURCES
LOOP_ALLOWED_ACTIONS
LOOP_APPROVAL_MODE
GITHUB_TOKEN
OPENAB_CHANNEL_ID
OPENAB_THREAD_ID
GMAIL_OAUTH_CLIENT_ID
GOOGLE_APPLICATION_CREDENTIALS
GOOGLE_WORKSPACE_DELEGATED_USER
GOOGLE_DRIVE_SCOPES
GOOGLE_CALENDAR_SCOPES
MEET_BOT_ACCOUNT
MEET_RECORDING_CONSENT_REQUIRED
```

If an environment variable, OAuth scope, account identity, or connector is
missing, produce a setup checklist and stop before mutation.

## Agent-Lime Reference Route

Use `agent-lime` as the concrete reference implementation for the meeting
proxy setup contract when the checkout is available. The reference should be
read for service boundaries and environment-variable classes, never for secret
values.

Observed reference surfaces to inspect before implementation:

- `services/orchestrator/config.py`: orchestrator boundary for Vexa, Google
  Calendar, OpenAI, Discord webhook, Firestore, STT, and internal-token
  configuration.
- `services/media-gateway/config.py`: media gateway boundary for Vexa and
  transcriber integration.
- `services/speech-agent/config.py`: speech/TTS boundary for Vexa and STT/TTS
  operation.
- `scripts/deploy-changed-services.sh`: Cloud Run deployment pattern, including
  which settings are plain environment variables and which must be delivered as
  secrets.

Observed execution pattern:

- `docker-compose.yml` wires Postgres, `vexaai/vexa-lite`, `stt-adapter`,
  `media-gateway`, `speech-agent`, `orchestrator`, and dashboards.
- `services/orchestrator/google_calendar_client.py` polls Calendar with a
  lookahead window, extracts Google Meet URLs/native meeting IDs, and records
  invitee emails.
- `services/orchestrator/calendar_scheduler.py` wakes on Calendar poll
  intervals, optionally filters by a trigger invitee email, skips already
  active bots, and calls Vexa to join the meeting.
- The default canonical path is transcription and notes first: Vexa provides
  meeting join/transcript plumbing, the STT adapter or media gateway handles
  audio-to-text, and `speech-agent` is a separately gated speaking/TTS boundary
  rather than the default operating mode.

Non-secret setup checklist derived from the reference:

```text
reference repo path:
orchestrator service configured:
media gateway service configured:
speech agent service configured:
Vexa endpoint variable names:
Vexa secret variable names:
Google Calendar credential variables:
Calendar poll/lookahead variables:
trigger invitee filter variable:
OpenAI model/API variables:
Discord webhook variable names:
Firestore/project variables:
STT/TTS provider variables:
internal service token variables:
Cloud Run env vars:
Cloud Run secrets:
calendar watch / event source:
meeting join/leave mechanism:
transcription pipeline:
speaking/TTS gate:
recording/transcription consent gate:
data retention / storage policy:
failure and leave behavior:
```

Meeting proxy setup is not actionable until those classes are mapped. If
`agent-lime` is unavailable on the current host, record that fact and keep the
route at setup-contract level; do not invent equivalent internals. If another
agent has inspected `agent-lime`, cite the review artifact or file paths used
and treat the result as a checklist to verify when the checkout becomes
available.

## Fairy Tale Self-Pilot

Pilot objective: run this loop against Fairy Tale itself.

Roles:

- MISA 3 owns canonical methodology and implementation branch.
- Codex MISA reviews SWE/repo/install parity and source grounding.
- CC MISA reviews workflow/config/Computer Use setup and creates the visible
  project thread when UI action is required.

Bootstrap:

```text
loop_id: fairy-tale-loop-pilot
repo: bonginkan/fairy_tale
project channel/thread: created or linked by CC MISA
owner mention: Jun at thread start; later only tri-MISA agreement, approval,
               final sign-off, or major escalation milestones
cadence: manual until scheduler and channel binding are verified
sources: this Discord thread, GitHub issues/PRs/checks, residency checks,
         skill/plugin install targets, and source updates
allowed actions: issue/branch/PR/docs/config within repo scope
blocked actions: secrets, deploy, merge without reviewer gates, external send,
                 direct Drive edits, meeting joins
approval gates: email send, Drive direct mutation, meeting proxy, credential
                changes, production deploy, permission changes
```

First pilot tasks:

1. Create the project thread with Jun mention and role assignment.
2. Post the loop profile and source map.
3. Ingest open Fairy Tale repo state and current skill/runtime parity.
4. Generate candidate tasks only when dedupe and negative-space gates pass.
5. Execute one small repo-scoped improvement through branch, PR, review, and
   runtime parity validation.
6. Record learning signals and update the loop profile before any scheduler is
   enabled.

## Stop and Escalation Gates

Stop immediately when:

- authority, sender identity, repo scope, or account identity is unclear;
- credentials, scopes, or connectors are missing;
- a secret would need to be displayed or stored;
- the loop is repeating the same failure class;
- rate limits or usage budgets are near the configured floor;
- an external send/edit/join/deploy would occur without approval;
- source context is materially incomplete and cannot be resolved safely.

Escalate to the owner or designated reviewer with source refs, current state,
blocked action, and the smallest approval question.
