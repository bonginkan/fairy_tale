# Loop engineering operating record

Use this before starting or modifying any persistent agent loop, scheduled
engineering loop, repo/project-channel operation, or long-running autonomous
workflow. The record defines the harness around the agent; do not rely on a
prompt-only loop for production behavior.

```text
loop name:
repo / artifact scope:
project channel:
run thread:
owner mention policy:
do-not-disturb policy:
active loop queue:
thread isolation policy:
stale-loop sweep cadence:
silent-loop auto-resume policy:
primary operator:
reviewers / monitors:
cadence / trigger:
source adapters:
dedupe keys:
intake normalization schema:
allowed actions:
blocked actions:
approval gates:
credential / secret boundary:
idempotency key:
run ledger / receipt path:
status reporting cadence:
validation checks:
rollback / repair path:
stop conditions:
escalation conditions:
learning signals:
next pilot run:
```

Required invariants:

- Bind the loop to a concrete repo or artifact scope and a visible project
  channel/thread before enabling periodic execution.
- Keep owner visibility and owner mentions separate. Routine status and
  checkpoint updates should be posted where the owner can see them without
  mention. Mention the owner only at thread start and tri-MISA agreement,
  approval, final sign-off, or major escalation milestones.
- Check human-set Do Not Disturb operating windows before assigning roles,
  starting new mutations, posting non-urgent mentions, or escalating routine
  blockers. DND constrains timing and routing; it never grants additional
  permission.
- If one session owner coordinates multiple loop threads, keep a bounded
  active-loop queue and run a stale-loop sweep before deep work on any one
  loop. Do not let the loudest or most recent thread silently starve other
  loops that are waiting for assignment, review, close, or escalation.
- Give active loops an auditable silent-loop watchdog when missed mentions or
  missing handoffs could stall the run. Track the expected actor, next expected
  action, last touch, silence threshold, concrete scheduled wake actuator, and
  auto-resume action. When the loop enters wait, register a `ScheduleWakeup`
  or equivalent cron/launchd watchdog for `auto_resume_at`; policy text alone
  is not enough because a fully silent loop has no active agent to evaluate the
  timer. If the wake fires and the loop is not DND-paused, parked,
  approval-blocked, or closed, post one bounded local checkpoint in that same
  thread, re-mention the required local agent(s), and set a new checkpoint or
  blocker. Do not use auto-resume to weaken DND, approval, security,
  credential, deploy, external mutation, or owner-escalation gates.
- Keep thread-local loop state isolated. Cross-loop references must be stable
  source refs, issue/PR links, or explicit handoff records; do not import
  unresolved context from another channel into the current loop thread.
- Store source references, triage decisions, actions, validation, and reviewer
  state in a run ledger or receipt. Do not rely on chat memory alone.
- Keep source collection, task selection, execution, review, and learning as
  separate stages so each can be audited and replaced.
- Start in read-only or draft mode. Escalate to write/send/join only after the
  approval boundary and credential scope are explicit.
- A loop that repeats the same failure class without a changed probe,
  validation result, or escalation is stopped, not retried indefinitely.

