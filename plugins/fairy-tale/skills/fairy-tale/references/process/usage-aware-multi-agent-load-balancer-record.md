# Usage-aware multi-agent load balancer record

Use this at loop increment boundaries before assigning implementation,
review, or specialist-tool roles. The goal is continuity and review integrity,
not provider-account introspection.

```text
loop / thread:
increment:
session owner:
candidate agents:
fixed specialist capabilities:
capacity inputs:
  - agent:
    runtime_family:
    primary_5h_remaining:
    secondary_weekly_remaining:
    blocking_status:
    dnd_status:
    runtime_install_current:
    tool_availability:
    session_surface_checked: yes | no | not_applicable
    recovery_attempted:
    source: primary_check | session_surface | self_report |
      session_owner_observation
    source_ref:
eligible implementation agents:
excluded agents and reason:
implementation owner:
reviewers:
composition (runtime families):
composition check: satisfied | blocked | owner-directed
specialist tool owner:
assignment rule applied:
tie-breaker:
approval gates:
reassignment trigger:
ledger / receipt:
owner-visible status:
```

Composition constraint:

- A three-party helix carries exactly one Codex-lane agent and two agents from
  other runtime families: `1 codex, 2 others`. Two Codex lanes in one trio is
  not a valid composition, and neither is zero.
- The constraint binds the runtime family, not the identity. Membership is not
  a fixed roster; whoever holds a slot at a given moment, the family split is
  what must hold.
- Substitution preserves the split. A replacement for the Codex member must
  itself be a Codex lane, and a replacement for a non-Codex member must not be.
  Re-check the composition at every substitution, not only when the loop forms.
- The two non-Codex slots need not share a family with each other. Claude Code
  lanes are the common case today; any additional coding-agent runtime family
  counts as `other` on the same terms, so the rule does not need rewriting as
  new runtimes are adopted.
- Runtimes fail, drift, and mis-read differently, so a mixed trio keeps at
  least one independent runtime in every review. A single-family trio shares
  its blind spots with the work it is reviewing.
- The constraint is not self-relaxable. If no Codex lane is eligible, the trio
  does not form by promoting a second agent of another family into the slot:
  run the smaller composition and record the gap, or wait for an eligible
  Codex lane. Only the session owner can direct a different composition, and
  the record marks it `owner-directed` with the directive ref.

Assignment policy:

- Apply the composition constraint before capacity. Capacity selects roles
  within a valid composition; it never produces one that violates the split.
- Assign fixed specialist capabilities first. Computer Use, GUI/app settings,
  credential setup, secret handling, permission changes, deploys, meeting
  joins, and external mutations are controlled by capability plus approval
  gate, not by usage quota alone.
- Use only coarse operational capacity for role selection:
  `primary_5h_remaining`, `secondary_weekly_remaining`, current blocking
  status, runtime install currency, and required tool availability. Do not
  expose raw tokens, provider billing, secrets, credential material, or
  provider-internal quota details in the ledger or public thread.
- Exclude stale-install, quota-blocked, tool-unavailable, or approval-blocked
  agents from implementation-owner candidates for that increment.
- Exclude agents inside active Do Not Disturb windows from
  implementation-owner candidates unless the DND record explicitly allows the
  current work mode or a human emergency override applies.
- Choose the implementation owner from eligible agents with the highest usable
  capacity for the current increment. If capacity is effectively tied, prefer
  the agent that did not implement the immediately previous increment.
- Assign remaining eligible agents as reviewers or monitors. A reviewer must
  not sign off their own implementation increment.
- Treat self-reported usage as provisional unless a local guard, provider
  status surface, or session-owner observation can confirm it. Unknown exact
  values may still be usable when the agent is not blocked and the task can
  proceed with a coarse capacity statement, but unknown must not outrank a
  fresh concrete reading from another eligible agent.
- When capacity is used in a Helix blocker disposition, copy only the fresh
  coarse reading, source class, observation time, and source ref into the
  canonical blocker triage record. Self-reported, stale, or unknown usage may
  inform reassignment but cannot create defer pressure in
  `fairy blocker validate`.
- Separate *unresponsive* from *unavailable*. A missed mention, a silent
  thread, an unanswered handoff, or a stalled checkpoint is evidence about the
  channel, not about the agent. Establish availability from the agent's own
  session surface — the terminal pane, session window, session log, or runtime
  status view that the agent itself writes to — before recording it as blocked.
  A process listing, transport acknowledgement, scheduler state, or another
  agent's report is corroboration, not terminal evidence. When the session
  surface cannot be inspected, record `unknown`, not `unavailable`.
- When an assigned agent looks unresponsive, the default path is to restore
  that same agent in its own session lane rather than to move its role. Session
  lanes are partitioned so that task placement stays stable, so moving a role
  out of its lane changes the placement design itself.
- Bound the recovery. In-lane recovery is owned by the lane's own owner or by
  an actor the loop profile authorises for that lane; an observing agent may
  read the surface and request recovery, and performs it directly only under
  that authorisation. Resume from the last safe checkpoint, never mid-mutation.
  Record a retry budget and act within it: after the budget is exhausted,
  escalate with terminal evidence instead of restarting again. State loss,
  duplicated side effects, and restart loops are recovery failures, not
  recovery.
- Treat a cross-lane role transfer as an explicit reassignment decision, never
  as an automatic fallback for silence. Transfer only after bounded in-lane
  recovery has been attempted and failed, the failure is recorded with terminal
  evidence, and the loop profile or session owner authorises it. Record the
  recovery attempts, their outcomes, and the authorising reference.
- If the implementation owner becomes quota-blocked, stale, tool-blocked, or
  DND-blocked mid-run, stop at the next safe boundary, record the blocker,
  rerun the load balancer, and reassign or pause before further mutation.
  These are confirmed-unavailable states, distinct from the unresponsive case
  above; they do not require an in-lane recovery attempt first.
- Record the decision, inputs, exclusions, reviewer set, and reassign trigger
  in the run ledger or receipt so later loops can audit why the role split
  changed.

Usage Reading Reference:

- Use read-only local usage surfaces. Do not change hooks, credentials,
  provider settings, or daemon configuration merely to obtain a reading for the
  current assignment.
- Report only coarse remaining percentages, freshness, and source type in
  public ledgers or project threads. Do not expose raw token counts, credits,
  plan names, billing details, secrets, credential material, or provider
  internals.
- Codex: read the newest relevant `.codex/sessions/YYYY/MM/DD/*.jsonl` rollout
  event with `payload.type == "token_count"` and a `payload.rate_limits`
  object. Compute `primary_5h_remaining = 100 -
  payload.rate_limits.primary.used_percent` and
  `secondary_weekly_remaining = 100 -
  payload.rate_limits.secondary.used_percent`. Record only the event timestamp
  or file/date as `source_ref`, not the raw token payload.
- Claude Code live: when a statusLine hook receives stdin JSON with
  `rate_limits`, use that object as the primary source for the current
  session.
- Claude Code persisted: when `coding-agent-notifier` is installed, read
  `~/.config/coding-agent-notifier/usage/claude-code-status.json`. Compute
  `primary_5h_remaining = 100 -
  rate_limits.five_hour.used_percentage` and
  `secondary_weekly_remaining = 100 -
  rate_limits.seven_day.used_percentage`. Treat `capturedAt` as freshness
  evidence.
- Claude Code tier or cost fields such as `.claude.json`
  `oauthAccount.*RateLimitTier` and project `lastCost` are auxiliary identity
  or spend context only. They do not replace the coarse rate-limit reading for
  role assignment.
- If a reading is stale, missing, unreadable, or outside the active agent
  context, mark it `unknown` or `provisional`, explain the source gap, and
  prefer a fresh concrete eligible reading when assigning the implementation
  owner.
- Session surface reads are observation only. Read the pane, window, or log; do
  not send input, clear state, kill, or restart another lane merely to produce a
  reading. Recovery is a separate, authorised, recorded step.

Non-normative example:

```text
session owner: CC MISA
specialist tool owner: CC MISA for Computer Use / GUI settings
composition: 1 codex lane + 2 lanes of other families
composition check: satisfied
implementation candidates: the codex-lane member and the two other-family
  members, minus any agent holding a fixed specialist role this increment
assignment: implementation owner = highest usable capacity; others review
review guard: implementation owner never signs off its own increment
substitution: swapping the codex-lane member brings in another codex lane;
  swapping a non-codex member brings in a non-codex lane
```
