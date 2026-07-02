# Do Not Disturb operating-window record

Use this when a human sets, clears, or updates quiet hours for an agent inside a
loop. DND is an operating constraint for assignment, notification, and safe
handoff; it is not an authorization mechanism and does not weaken security,
approval, or credential gates.

```text
agent:
scope: global | repo | thread | increment
timezone:
window_start:
window_end:
recurrence:
effective_from:
effective_until / expires_at:
set_by_human:
source_ref:
mode: no_new_work | review_only | emergency_only | silent_notifications
allowed_during_dnd:
blocked_during_dnd:
override_authority:
emergency_threshold:
handoff_target:
resume_at:
resume_policy:
queued_items:
ledger / receipt:
```

Set / clear policy:

- DND must be human-set, timezone-qualified, and auditable. A bot may relay a
  DND record only when the source human and source ref are preserved.
- Missing timezone, ambiguous recurrence, expired records, stale records, or
  conflicting windows are provisional. Ask or stop at the next safe boundary
  instead of silently overriding a fresh human instruction.
- Clearing DND requires the same authority class as setting it, or an explicit
  expiry / resume policy in the original DND record.
- Public ledgers record only the DND state, window identifier, timezone,
  source ref, and routing decision. Do not expose private calendars, personal
  schedule details, raw provider usage, tokens, billing, or secrets.

Operating rules:

- At assignment boundaries, exclude agents inside an active DND window from
  implementation-owner candidates unless the human record explicitly permits
  the current mode or an emergency override applies.
- If an assigned agent enters DND mid-run, stop at the next safe boundary,
  record state, avoid starting new mutation, and rerun the load balancer for
  handoff or pause/resume.
- Suppress owner mentions, direct pings, and non-urgent escalations while the
  target agent is in DND. Queue routine status or post owner-visible updates
  without waking the DND agent when channel rules allow.
- During DND, blockers are handled by self-contained investigation,
  established patterns, or the smallest reversible safe action. If the blocker
  needs the DND agent, pause or reassign instead of waking them by default.
- Hard safety, security, consent, secret, permission, deploy, external-send,
  and meeting-join limits remain intact. DND never authorizes email sends,
  Drive edits, meeting joins, production deploys, credential changes, or
  permission changes.
- When every eligible agent is DND-blocked, quota-blocked, stale, or
  tool-unavailable, the loop records the blocker and pauses rather than
  retrying indefinitely.
- When the window ends, resume by rechecking runtime install, usage capacity,
  source freshness, reviewer state, and approval gates before continuing.

