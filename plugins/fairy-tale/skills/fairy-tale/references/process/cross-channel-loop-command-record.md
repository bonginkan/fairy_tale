# Cross-channel loop command record

Use this when a session owner or commander coordinates more than one loop,
repo, channel, or run thread. The goal is continuity and thread-local clarity:
no loop is silently neglected, and no thread receives unrelated unresolved
state from another loop.

```text
session owner:
active loop queue:
focused loop:
loop priority:
intake owner:
intake dedupe key:
project channel / run thread:
repo / artifact scope:
last owner touch:
last agent action:
next expected action:
next expected touch:
stale threshold:
auto resume after:
auto resume at:
auto resume retries:
auto resume action:
scheduled wake actuator:
scheduled wake source_ref:
blocked / waiting reason:
thread isolation policy:
allowed cross-loop refs:
blocked cross-loop refs:
pending handoffs:
duplicate intake repair:
dnd / quota / tool blockers:
owner-visible status:
next sweep at:
repair action:
ledger / receipt:
```

Operating rules:

- Maintain an active-loop queue for every loop the session owner is holding.
  Each entry must name the loop, thread, scope, next expected action, last
  touch, blocker state, and owner-visible status.
- Assign exactly one intake owner before creating issues, PRs, run threads, or
  canonical tracking artifacts for a new loop task. Other agents may propose
  findings, but they should comment on or hand off to the canonical intake
  instead of creating parallel trackers.
- Use an intake dedupe key before any issue or PR creation: root requester,
  repo/artifact scope, task class, source ref, and current increment. If a
  duplicate artifact is created, consolidate the useful evidence into the
  canonical artifact, close the duplicate, and record the repair.
- Before starting deep work, merging, assigning roles, or posting a major
  update in one loop, run a bounded stale-loop sweep. Flag loops whose
  expected next action has aged beyond the loop's threshold, even if the
  current thread is more active.
- A stale-loop sweep identifies overdue work; a silent-loop watchdog restores
  motion when the expected actor or mention path went quiet. When the loop
  enters a wait state, register a concrete scheduled wake for `auto_resume_at`
  using the runtime's `ScheduleWakeup` mechanism when available, otherwise a
  narrowly scoped cron/launchd watchdog. Record the actuator id, source ref,
  and cancellation condition in the loop ledger. If no actuator can be
  registered, do not claim time-based auto-resume; record a manual-review
  blocker instead.
- When the scheduled wake fires, re-read the thread and ledger first. If the
  expected action already happened, or the loop is DND-paused, parked,
  approval-blocked, security-blocked, credential-blocked, deploy-blocked,
  externally blocked, or closed, cancel/no-op and record why. Otherwise post a
  bounded checkpoint in the loop's own thread: local scope, stale expected
  action, assigned actor or load-balancer reroute, last artifact/source ref,
  next safe action, and the next checkpoint time.
- Limit auto-resume to the loop's retry budget for that silent period. Use
  backoff or a hard retry cap; if all eligible agents remain silent after the
  cap, record an explicit loop blocker with evidence instead of spinning.
- Ambiguous timers, missing source refs, or unclear expected actors fail closed
  to manual review. Do not infer permission from silence.
- Decide attention by explicit owner priority, blocker severity, wait time,
  approval gates, DND state, usage capacity, and tool availability. Do not use
  channel loudness, recent mentions, or the commander's current context as the
  scheduling policy.
- Preserve per-thread topic purity. If another loop is relevant, reference it
  only by stable source ref, issue/PR URL, run id, or a short sanitized handoff
  summary. Do not ask agents in the current thread to reason over another
  thread's unresolved state.
- If another loop needs action, update that loop's own thread, issue, PR, or
  run ledger. Do not steer unrelated agents by dropping cross-channel context
  into the wrong session.
- If the commander detects cross-thread contamination, stop at the next safe
  boundary, restate the current loop's scope, move the foreign context to the
  correct ledger or thread, and record the repair.
- On resume or context compaction, rebuild the active-loop queue before
  continuing a single loop. A loop is not considered cleanly resumed until
  other held loops have a current status, next action, or explicit pause.
- This card does not merge repo targets, weaken approval gates, bypass DND,
  or authorize secrets, deploys, external sends, meeting joins, credential
  changes, or permission changes.

