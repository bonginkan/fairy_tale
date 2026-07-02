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
    primary_5h_remaining:
    secondary_weekly_remaining:
    blocking_status:
    dnd_status:
    runtime_install_current:
    tool_availability:
    source: primary_check | self_report | session_owner_observation
    source_ref:
eligible implementation agents:
excluded agents and reason:
implementation owner:
reviewers:
specialist tool owner:
assignment rule applied:
tie-breaker:
approval gates:
reassignment trigger:
ledger / receipt:
owner-visible status:
```

Assignment policy:

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
- If the implementation owner becomes quota-blocked, stale, tool-blocked, or
  DND-blocked mid-run, stop at the next safe boundary, record the blocker,
  rerun the load balancer, and reassign or pause before further mutation.
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

Non-normative example:

```text
session owner: CC MISA
specialist tool owner: CC MISA for Computer Use / GUI settings
implementation candidates: Codex MISA, MISA 3, CC MISA when not fixed-specialist
assignment: implementation owner = highest usable capacity; others review
review guard: implementation owner never signs off its own increment
```

