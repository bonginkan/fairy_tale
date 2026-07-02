# Silent-loop auto-resume watchdog record

Use this when an active loop can stall because the next agent was not
mentioned, a handoff was omitted, or everyone stopped posting even though the
loop is not deliberately paused. The watchdog is an auditable time-based
recovery rule; it is not a scheduler that retries forever.

```text
loop / thread:
session owner:
expected actor:
next expected action:
last loop activity:
last touch source_ref:
next expected touch:
silence threshold:
auto resume after:
auto resume at:
auto resume action:
scheduled wake actuator:
scheduled wake source_ref:
scheduled wake registered at:
retry count:
retry limit:
backoff policy:
dnd / parked / approval / closed state:
bounded checkpoint:
re-mention target:
load-balancer reroute:
new checkpoint:
blocker if exhausted:
ledger / receipt:
```

Operating rules:

- Record `last_loop_activity`, `next_expected_touch`, and `auto_resume_after`
  for active loops that depend on a specific next actor or handoff.
- Before entering wait, register a concrete scheduled wake for `auto_resume_at`
  using `ScheduleWakeup` when the loop runtime offers it. If not available,
  use a narrowly scoped cron/launchd watchdog or equivalent host-approved
  scheduler that can wake without inbound chat. Record the actuator id,
  source ref, cancellation condition, and owner of the watchdog.
- If no scheduler/wakeup actuator is available or allowed, fail closed:
  record the loop as manually watched or blocked, and do not mark the loop as
  protected by time-based auto-resume.
- When the scheduled wake fires, first re-read the thread and ledger, then
  check exclusion states. Do not auto-resume a loop that is inside an active
  DND window, intentionally parked, approval-blocked, security-blocked,
  credential-blocked, deploy-blocked, externally blocked, already progressed,
  or already closed.
- If the loop is eligible, resume only inside the same thread or canonical
  ledger. The checkpoint names the local loop scope, stale expected action,
  expected actor, last artifact/source ref, next safe action, and whether a
  missed mention is the likely blocker.
- Use the bot-to-bot addressing format for the local agent(s) needed to move
  the loop. Do not wake the owner unless the loop's normal owner-escalation
  policy already allows that escalation.
- If the expected actor is DND-blocked, quota-blocked, stale-install blocked,
  or tool-unavailable, do not ping through the blocker. Rerun the load
  balancer, reassign, or park with a new allowed checkpoint.
- Keep retries bounded. One auto-resume per silent period is the default unless
  the loop profile states a stricter retry limit and backoff policy. Repeated
  silence after the limit becomes a loop blocker, not another ping.
- Do not import context from another loop while resuming. Cross-loop references
  stay as stable source refs or explicit handoff records.
- This card does not weaken DND, approval gates, security boundaries,
  credential rules, deploy gates, external mutation gates, meeting-join rules,
  or any owner-mention policy.

