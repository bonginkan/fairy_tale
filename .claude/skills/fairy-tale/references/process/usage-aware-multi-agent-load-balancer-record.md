# Usage-aware multi-agent load balancer record

Use this at loop increment boundaries before assigning implementation,
review, or specialist-tool roles. The goal is continuity and review integrity,
not provider-account introspection.

This record is prose. Nothing in the repository parses or validates a filled
copy, so every field below is a discipline for the agent filling it, not a gate
that will stop a wrong entry.

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
composition check: satisfied | blocked | owner-directed | not_applicable
composition directive ref:
specialist tool owner:
assignment rule applied:
tie-breaker:
approval gates:
reassignment trigger:
substitution reason: usage_exhaustion | confirmed_unavailable | none
handoff record ref:
ledger / receipt:
owner-visible status:
```

Composition constraint:

- A three-party helix carries exactly one Codex-lane agent and two agents from
  other runtime families: `1 codex, 2 others`. Two Codex lanes in one trio is
  not a valid composition, and neither is zero.
- The constraint scopes to increments that form a three-party helix. An
  increment that assigns roles without forming one records
  `composition check: not_applicable`; the rest of the assignment policy still
  applies. `not_applicable` states that no trio was formed, never that a
  formed trio was left unchecked.
- `composition directive ref` is filled exactly when the check reads
  `owner-directed`, and carries the verified owner directive locator. Leave it
  empty for the other three values.
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
- That reasoning carries the lower bound only: it is why the count is never
  zero. It does not derive the upper bound, and `2 codex + 1 other` would
  satisfy it while violating the split. The exact split is set by owner
  directive, so do not widen this to `any mixed trio` on the strength of the
  line above.
- `runtime_family` names the runtime the agent runs on, not its account, host,
  or persona. Record one value per agent: `codex`, `claude-code`, or another
  runtime family written as its lowercase hyphenated runtime name.
- The constraint is not self-relaxable. Never promote a second agent of another
  family into the Codex slot, and never seat two Codex lanes. When no Codex
  lane is eligible the trio does not form, and the handling is ordered:
  1. Inside an active loop, keep moving on the work that does not need the
     trio — implementation, evidence, drafts, records — and mark
     `composition check: blocked` with the reason and the missing family. A
     blocked composition is recorded and worked around, not waited on.
  2. Outside a loop, waiting for an eligible Codex lane is a valid resolution.
     Record the same fields while waiting.
  3. If the blocked composition holds up a gate that cannot proceed without the
     trio, escalate to the session owner. Only the session owner can direct a
     different composition; the record then reads `owner-directed` and carries
     the directive ref.
  Escalation is the third step. It does not replace the first two.
- A blocked composition never lowers the review requirement. Work that needs
  two independent sign-offs does not proceed on one because the trio could not
  form.

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
- Degrading quality inside a long session is not a reassignment trigger. An
  agent that judges its own context degraded hands off *to itself*: write the
  handoff record — current increment, exact head and refs, what is done, what
  is next, open blockers — reboot its own session, and resume from that record.
  The lane keeps the work; only the context is replaced. Self-assessed
  degradation is not observable from outside and is available at every moment,
  so accepting it as a transfer reason makes any transfer justifiable after the
  fact.
- Substitution is keyed to usage exhaustion, not to how the run feels. When a
  lane's usable capacity is gone, record it and rerun the load balancer. Long
  context, accumulated mistakes, and wanting a clean start are handled by
  handoff plus self-reboot inside the same lane, and `substitution reason` says
  which of the two happened.
- `usage_exhaustion` is a reading, not a word. It carries the same evidence any
  capacity claim carries — a coarse remaining figure with its source class and
  `source_ref`, self-report treated as provisional — because a reason that is
  merely asserted is unobservable from outside and available at any moment,
  which is exactly why degradation was refused above. `none` states that no
  substitution happened, never that one happened for a reason outside this
  list.
- A reboot without a handoff record is state loss wearing a recovery's name.
  Write the record first, then reboot; resume from the record, not from memory.
- The record has to outlive the context it describes, so write it where the
  reboot cannot take it: the run ledger or receipt, or the issue / PR / project
  thread the work already exchanges through. A handoff written only into the
  session being discarded satisfies the words and loses the state.
- Write it at a safe boundary and reboot there. A self-reboot is chosen, not
  imposed, so unlike an external stop it can land mid-mutation — and the same
  rule as in-lane recovery applies: resume from the last safe checkpoint, never
  mid-mutation.
- Treat a cross-lane role transfer as an explicit reassignment decision, never
  as an automatic fallback for silence. Transfer only after bounded in-lane
  recovery has been attempted and failed, the failure is recorded with terminal
  evidence, and the loop profile or session owner authorises it. Record the
  recovery attempts, their outcomes, and the authorising reference.
- If the implementation owner becomes quota-blocked, stale, tool-blocked, or
  DND-blocked mid-run, stop at the next safe boundary and record the blocker.
  These are confirmed-unavailable states, distinct from the unresponsive case
  above, but they do not all mean the same thing:
  - Quota exhaustion belongs to the lane's account and a restart does not
    refill it, and a DND window is deliberate non-interference that a restart
    would violate. Rerun the load balancer and reassign or pause.
  - A stale install or a tool that is unavailable *in this session* is often
    repaired by the restart itself — a patched file on disk does not reach a
    process that is already running. Take the bounded in-lane recovery above
    first, and reassign only if it fails within its retry budget.
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
