# Fairy Tale Process Templates

## Glass Slipper Gate

Define before long execution:

```text
objective:
success criteria:
allowed files/targets:
max elapsed time:
max searches:
max tool calls:
max subagents:
max spend/token budget:
stop conditions:
validation:
rollback:
```

## Evidence map

```text
claim:
source type: official | primary | local | third-party | user-report
source:
confidence: high | medium | low
action:
risk:
verification:
```

## Best-practice gate

Use this before changing the skill, plugin, adapter, memory, hook, eval, or OSS
release surface.

```text
surface:
best-practice source:
source checked date:
source type: official | upstream | local | maintained-oss | user-report
local applicability:
change to make:
negative case / misuse prevented:
validation:
owner decision needed:
```

## Eval card

Use this before claiming a process advantage or benchmark-style improvement.

```text
capability claim:
baseline process:
candidate process:
task dataset / fixtures:
success metric:
negative cases:
budget: time | tokens | cost | tool calls
tooling and memory:
run command / procedure:
artifacts:
result:
failure modes:
reproduction note:
```

## Tool contract card

Use this before exposing a tool, adapter, hook, MCP, or external runtime.

```text
tool/adapter:
source:
license:
when to use:
when not to use:
inputs:
outputs:
caveats:
examples:
permissions:
sensitive files excluded:
validation:
forbidden claims/actions:
```

## Context and memory recovery note

Use this after long-running work or before compaction.

```text
objective:
current state:
files/artifacts touched:
evidence captured:
validation status:
open risks:
next safe action:
what not to redo:
```

## OSS release gate

Use this before making the repository public or publishing the plugin.

```text
release target:
license chosen:
third-party acknowledgements checked:
security policy:
contribution policy:
private research removed or separated:
dependency/license review:
repository health check:
public claims backed by artifacts:
version/tag:
```

## Scout report

```text
scope:
searched/read:
findings:
uncertainties:
recommended next step:
do not proceed if:
```

## Migration checkpoint

```text
checkpoint:
files touched:
behavioral invariant:
validation performed:
remaining risk:
next checkpoint:
```

## Defensive security finding

```text
target authorization:
affected component:
suspected issue:
defensive evidence:
impact:
safe reproduction boundary:
patch recommendation:
disclosure status:
```

## Cyber frontier defense record

Use this for authorized vulnerability triage, LLM app security review, secure
refactoring, and defensive validation.

```text
authorization:
allowed targets:
forbidden targets:
system assets:
trust boundaries:
entry points:
privileged actions:
tenant/data boundaries:
secrets and credentials:
external services / tools:
finding class: OWASP Web | OWASP LLM | cloud/IAM | supply chain | tenant isolation | data privacy | secrets | business logic | agent/tool risk | other
finding status: confirmed | likely | speculative | informational | duplicate
affected component:
preconditions:
impacted data/action:
existing control expected:
why control fails:
safe evidence:
severity rationale:
patch recommendation:
regression tests:
detection/monitoring:
owner:
rollout/rollback:
responsible disclosure:
forbidden exploit detail excluded:
```

## LLM application security checklist

```text
prompt injection fixtures:
retrieved content marked untrusted:
system/developer instructions separated:
sensitive output blocked/redacted:
HTML/Markdown output sanitized:
tool calls server-side authorized:
high-risk mutations require human approval:
tenant filters enforced server-side:
embedding/vector search tenant-scoped:
KB ingestion poisoning controls:
model/tool dependency inventory:
audit logs redact sensitive content:
unbounded spend/loop controls:
rollback path:
```

## Benchmark delta record

Use this when trying to reproduce reported benchmark-style advantages.

```text
benchmark/task family:
target capability:
baseline model/process:
candidate model/process:
rubric:
task budget:
effort/reasoning setting:
tools and memory:
fallback/refusal events:
validation artifacts:
cost and elapsed time:
result delta:
failure modes:
next experiment:
```

## Evaluated feedback record

Use this after a benchmark miss or work-product failure.

```text
source run:
task/sample IDs:
baseline score:
candidate score:
confidence interval:
failure class:
evidence:
new rule:
misuse prevented:
retry sample:
retry result:
promote to default: yes | no | needs confirmation
```

## Step-level skill adaptation record

Use this when a failed trajectory or repeated work-product miss may justify a
skill update. Localize the fault before changing the skill library.

```text
source run / task:
trajectory or artifact:
active skills / guidance:
candidate fault chain (2-4 steps):
first actionable fault step:
observed failure:
improvement principle:
responsible skill links:
decision: revise_existing | generate_new | no_update
target skill:
missing coverage:
candidate update:
deduplication / drift check:
qualification retry:
regression slice:
result delta:
accepted: yes | no
promotion target:
```

## Generalization audit record

Use this when a miss suggests poor generalization, false analogy, unlucky
success, or failure to convert local observations into a transferable rule.

```text
source run / task:
local facts observed:
latent invariant that should transfer:
false analogy / over-compression:
under-compression / failure to commit:
lucky success risk:
evidence that would falsify the inferred rule:
executable/checkable world model:
verifier command / probe:
confirmed rules:
refuted rules / no-ops:
neighboring task retry:
promotion decision:
```

## Tacit intent recovery record

Use this before acting on an underspecified user request, issue, ticket, or
benchmark task where unstated constraints may determine correctness.

```text
explicit user request:
artifact context inspected:
inferred objective:
likely implicit requirements:
risky assumptions:
irreversible / external-facing choices:
questions required before action:
reversible default chosen:
implicit contract checks:
validation artifact:
remaining unknowns:
```

## Closure check record

Use this before answering from a visible set of artifacts, numbered items,
images, files, clipped logs, quoted excerpts, partial text, or adversarially
framed evidence. The goal is to prevent the model from treating the presented
frame as a closed world without evidence.

```text
visible items:
stated / observed count:
count source: user | filename | numbering | metadata | environment | inference
verified exhaustive count: yes | no | unknown
incompleteness triggers:
  - mid-sentence / mid-clause / semantic continuation
  - missing sequence number / asymmetric pattern / N+1 pressure
  - clipped log / excerpt / crop / omitted attachment
  - adversarial or evaluative presenter incentive
  - metadata outside visible text may carry signal
inside-frame answer:
frame-completeness hypothesis:
materiality:
Tier A continuation / omitted-context hypothesis:
what would confirm:
what would refute:
surface form: finding | question | no surface
do not assert missing item exists:
```

Rules:

- `observed N` and `stated N` are not automatically `verified exhaustive N`.
- Do not skip the check because a count was stated, numbered, implied, or known.
  A confident-looking count can itself be part of the presented frame.
- If text, sequence, or artifact boundaries are materially incomplete, generate
  a Tier A continuation or omitted-context hypothesis. Surface the hypothesis
  without claiming the missing artifact exists.
- Run both the inside-frame answer and the frame-completeness check. Do not let
  a precise answer inside the visible frame replace boundary inspection.

## Negative-space discovery record

Use this during review, product/UX work, requirements discovery,
underspecified implementation, and "is this complete?" checkpoints. It is a
bounded divergence pass before convergence, not permission to expand scope.

```text
task / artifact:
trigger:
do_not_run reason, if any:

Tier A entailed companions:
  - missing companion:
    evidence:
    why entailed, not taste:
    risk if absent:
    surface form:

Tier B journey gaps:
  - candidate:
    affected user:
    user moment:
    near-term consequence:
    evidence:
    validation probe:
    refutation / discard result:
    surface form:

Tier C speculative neighbors:
  - private candidate:
    why private:

ranked surface output 1-3:
silence decision:
later learning signal:
```

Tier policy:

- Tier A = recall-first completeness. Default loud and never silently dropped.
  `do_not_run`, back-off, discard, scoped-task mode, and silence-as-valid do not
  suppress Tier A. In incident or explicit-scope work, surface Tier A as a
  critical companion finding instead of automatically expanding implementation.
- Tier B = gated discovery. Surface only when there is a named user, moment,
  evidence, and near-term consequence.
- Tier C = private log. Mature-product or best-practice analogies are silent by
  default unless the user asks for broader ideation.

Noise guard:

- Do not run the divergence pass for purely mechanical deterministic tasks,
  explicit non-goals, fully enumerated requirements, or repeated rejected
  suggestions, except that Tier A and closure-check findings remain protected.
- Discard candidates that are vibes-only, intentional absence/MVP/non-goal,
  duplicate, already covered by issue/TODO/roadmap, require unapproved scope
  expansion, fail Dialectic Refutation Gate, or are Tier C.
- Output ranked 1-3 findings/questions or silence. No "also you could" lists.
  No recursive divergence.

Recall guard:

- If Tier A exists, silence is not valid.
- Silence is a true negative only if later evidence does not reveal a missed
  gap.
- Tighten Tier B gates when `rejected_scope_creep`, `rejected_wrong_user`, or
  `rejected_no_evidence` rises. Loosen Tier B gates or add a new Tier A pattern
  when `later_confirmed_false_negative` or post-silence gaps rise.

Common Tier A examples:

```text
SWE:
  endpoint -> authz / input validation / error path
  create or state change -> edit/delete/undo/recovery as applicable
  schema change -> migration / backfill
  new behavior -> focused tests/docs when local convention requires
  user-facing state change -> observability / audit / error path

UX/product:
  destructive action -> confirmation + undo/recovery + irreversible-result copy
  async operation -> progress/queued/failure state + retry/idempotency
  empty surface -> empty state + next action
  permissioned surface -> disabled/hidden/denied rule + reason copy
  form/input -> validation + preserve input + actionable error
  setting/toggle -> current state + apply feedback + side-effect disclosure
  import/export -> format limits + partial failure + retry/re-download
  collaboration/audit -> actor + timestamp + visibility/conflict behavior
```

Precision/taste learning signals:

```text
accepted_now:
valuable_but_deferred:
converted_to_issue:
already_known:
rejected_scope_creep:
rejected_wrong_user:
rejected_no_evidence:
later_confirmed_false_negative:
silence_true_negative:
novelty:
usefulness:
reviewer_agreement_on_user_moment:
```

## Excess / redundancy / legacy-surface discovery record

Use this during review, refactoring, deprecation, skill/policy updates, and
cleanup work. It is the subtractive pair to Negative-Space Discovery: the goal
is to find surfaces that may be too much, stale, redundant, or legacy-bound
without turning every smell into an immediate deletion.

```text
task / artifact:
trigger:
source refs:
candidate surface:
surface type: dead-code | duplicate | deprecated | legacy-reader | stale-doc | unused-config | redundant-test | overlapping-skill | other
evidence:
  - static usage:
  - dynamic/runtime usage:
  - data usage / persisted references:
  - public API / compatibility:
  - docs / release notes / migration state:
classification: remove-now | deprecate-with-migration | consolidate-later | keep-intentionally
why this classification:
false-positive deletion risk:
required companion work:
  - migration:
  - compatibility shim / legacy reader:
  - tests:
  - docs:
  - release notes:
  - rollback:
surface form: issue | migration question | PR finding | direct edit
reviewer / owner decision:
later learning signal:
```

Tier policy:

- `remove-now`: only for private/internal surfaces with high-confidence zero
  use, no persisted data dependency, no public API contract, and a focused
  validator proving behavior is preserved. The PR must include tests or a
  narrowly equivalent validation artifact.
- `deprecate-with-migration`: for public, user-visible, cross-agent,
  persisted-data, or compatibility-sensitive surfaces. Mark the new path,
  migration plan, warning/communication surface, and removal condition before
  deleting anything.
- `consolidate-later`: for real duplication where immediate consolidation
  would broaden the current task, require unrelated churn, or need a migration
  window. Create an issue or migration question with evidence instead of
  editing opportunistically.
- `keep-intentionally`: for compatibility shims, forensic/audit traces,
  documented extension points, skill/runtime adapters, and legacy readers that
  still protect users or data. Record why it stays so future reviewers do not
  rediscover the same false positive.

False-positive guard:

- Treat mistaken removal as the worst failure mode. If usage evidence is
  partial, silence is not a valid delete signal.
- Do not remove `@deprecated` or equivalent public surfaces until migration is
  complete and the removal condition is independently checked.
- Do not remove backward-compatibility readers, legacy parsers, or data
  migration paths until data-side references are verified absent or a migration
  has run and been validated.
- Do not perform forensic-clean removal of audit, receipt, provenance, or
  migration traces unless the owner explicitly asks and retention policy allows
  it.
- If any compatibility, migration, data, or ownership fact is missing, stop at
  an issue, migration question, or review finding.

Evidence grounding:

- Local policy has priority for this repo: deprecated surfaces require a
  completed migration before deletion; legacy readers require data-side
  absence or a validated migration; audit/provenance traces are intentionally
  retained unless removal is explicitly approved.
- External sources in `references/sources.md` ground the surrounding practice:
  semantic versioning treats deprecation and incompatible removal differently;
  Java enhanced deprecation separates removal intent and migration
  communication; large-scale changes rely on tooling, migration, and
  coordination; refactoring is behavior-preserving; removing dead code is valid
  only after the code is actually dead.

Learning signals:

```text
accepted_remove_now:
accepted_deprecate:
accepted_consolidate:
accepted_keep:
converted_to_issue:
rejected_false_positive:
rejected_missing_usage_evidence:
rejected_compatibility_risk:
later_confirmed_excess_miss:
later_confirmed_bad_deletion:
```

## Loop engineering operating record

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

## Spiral engineering revolution record

Use this when a loop should climb rather than merely repeat. A spiral
revolution is a bounded loop iteration that raises an explicit altitude axis:
autonomy, abstraction, scope, delegation, reusable capability, or risk
burn-down. It is grounded in risk-driven spiral development and double-loop
learning: first reduce the uncertainty that blocks ascent, then decide whether
the loop's governing variables should change.

Model the revolution as a double-helix learning loop. The execution strand
carries the deliverable path: objectives, risk spike, implementation,
validation, and landing. The learning/governance strand carries the process
path: evidence, double-loop evaluation, governing-variable update, next
altitude, and stop-or-descend planning. Evidence gates pair the strands; if one
strand moves without the other, the revolution is either a flat loop or unsafe
meta drift.
Keep the strands anti-parallel in function: execution moves forward toward
delivery, while learning/governance moves backward against the premise to
refute, revise, and constrain the governing variables. Semi-conservative
handoff means the validated governance strand becomes the template for the next
effort while a new delivery strand is synthesized; unvalidated process mutation
does not replicate.

```text
loop / thread:
revolution id:
current altitude:
target altitude:
altitude axis:
execution strand:
learning / governance strand:
strand-pairing evidence:
mismatch / repair action:
validated governance template:
win condition:
highest-risk uncertainty:
risk owner:
risk spike / prototype:
risk burn-down evidence:
engineer target:
validation / review gate:
budget radius:
double-loop evaluation:
governing-variable update:
next altitude:
terminal landing condition:
descend / replan condition:
safety floor:
ledger / receipt:
```

Operating rules:

- Do not relabel ordinary repeated issue work as spiral engineering. A spiral
  revolution must name what rises: autonomy, abstraction, scope, delegation,
  reusable capability, or residual-risk reduction.
- Keep the execution strand and learning/governance strand paired. Artifact
  delivery without double-loop evaluation remains a flat loop; a
  governing-variable update without execution, risk, validation, review, and
  receipt evidence is unsafe process drift and must be blocked.
- Treat unpaired bases as mismatch signals. Unsupported claims, risk burn-down
  without evidence, missing reviewer sign-off, missing receipt, or safety-floor
  weakening must be proofread within the revolution or caught by a post-landing
  mismatch-repair sweep. If repair cannot be completed, descend or replan.
- Replicate only validated governance templates. When a spiral branches into a
  new effort, preserve the proven loop profile and synthesize the new delivery
  strand from it; do not copy speculative autonomy, scheduler, permission, or
  self-modification changes.
- Begin with objectives plus altitude. State the target altitude, win
  condition, budget radius, and stop/landing condition before starting the
  risk spike.
- Identify the highest-risk uncertainty that prevents ascent. Burn it down
  with a bounded spike, prototype, source-grounding pass, measurement, or
  validation harness before expanding scope or delegation.
- If the risk is not reduced, descend or replan. Do not increase autonomy,
  scope, external mutation, or owner-silence merely because a loop has already
  consumed budget.
- Engineer only the target that remains after the risk spike. Keep the normal
  one-implementer/two-reviewer, validation, CI, runtime-parity, and receipt
  gates.
- After landing, run double-loop evaluation. Decide whether the loop profile,
  owner mention policy, source adapters, validation gate, role assignment,
  autonomy level, or delegation boundary should change before the next
  revolution.
- Treat governing-variable updates as state-changing work. They require
  evidence, review, receipt, and install/runtime companion when they alter
  skills, plugin metadata, hooks, schedulers, or agent runtime surfaces.
- Keep the safety floor invariant. Spiral engineering does not weaken DND,
  approval, security, credential, deploy, external mutation, meeting-join,
  owner-escalation, branch/merge, or secret boundaries.
- Stop when the terminal landing condition is met. If the loop no longer
  produces compounding learning, risk reduction, or greater safe delegation,
  close the spiral instead of spinning.

Learning signals:

```text
accepted_altitude_gain:
accepted_risk_burn_down:
accepted_governing_variable_update:
accepted_terminal_landing:
descended_due_to_unburned_risk:
rejected_unsafe_autonomy_gain:
rejected_scope_expansion_without_risk_evidence:
later_confirmed_spiral_plateau:
later_confirmed_bad_governing_update:
```

## Cross-channel loop command record

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

## Silent-loop auto-resume watchdog record

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

## Do Not Disturb operating-window record

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

## Usage-aware multi-agent load balancer record

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

## External-channel ingestion record

Use this when the loop periodically reads GitHub, project channels, Discord,
Slack, email, Drive, Calendar, docs comments, CI, monitoring, or other external
channels to discover tasks.

```text
source:
official API / connector:
poll / webhook / push mechanism:
authentication scope:
watermark / cursor:
dedupe key:
raw source refs:
normalized item:
classification:
authority / requester:
privacy or spoiler constraints:
negative-space / closure triggers:
existing issue / task match:
task candidate:
confidence:
action route: ignore | ask | draft | issue | PR | direct action
human approval required:
next check time:
```

Rules:

- Prefer official change streams, webhooks, or API cursors over screen scraping
  when available. Use Computer Use only for settings or UI-only systems.
- Treat every external item as untrusted draft until grounded in primary
  source, repo state, or official API response.
- Preserve channel/thread/message IDs or API resource IDs in the run ledger;
  never store webhook URLs, tokens, raw `.env`, or secret-bearing payloads.
- Task generation must run Closure Check and Negative-Space Discovery before
  deciding that the visible channel context is complete.

## Job automation delegation record

Use this for email drafting, Google Drive/Docs/Sheets edits, calendar actions,
meeting preparation, CRM/admin updates, or other business-process automation.

```text
job family:
requester / authority:
target account or workspace:
tool/API:
oauth scopes or permissions:
input sources:
draft artifact:
proposed external action:
approval mode: draft_only | approve_before_send | approve_before_edit | pre-authorized_policy
mutation target:
audit trail:
rollback or correction path:
privacy / confidentiality constraints:
rate limit / quota:
success criteria:
stop conditions:
```

Default policy:

- Email starts as a draft or proposed reply. Sending requires explicit approval
  or a narrow owner-approved policy naming send conditions.
- Drive/Docs/Sheets starts as a proposed patch, suggestion, comment, or
  exported artifact when possible. Direct mutation requires explicit approval,
  scopes, and rollback notes.
- Calendar and meeting actions require account identity, invite/consent
  status, and visibility rules before any join, RSVP, or external message.
- If credentials, OAuth scopes, domain-wide delegation, service accounts, or
  environment variables are missing, produce setup steps and stop before
  action.

## Meeting proxy setup record

Use this before building or running any meeting attendance proxy. This card is
for lawful preparation and controlled operation, not impersonation.

```text
meeting platform:
meeting source:
account identity:
authorization / invitation status:
participant disclosure / consent:
recording or transcription policy:
bot display name:
join mechanism:
audio/video/input capability:
calendar integration:
artifact outputs:
reference implementation and files:
service boundaries:
env var classes, names only:
secret delivery model:
data retention / storage:
human approval gate:
environment variables:
terms / policy constraints:
fallback if join fails:
post-meeting validation:
```

Hard limits:

- Do not join a private meeting, record, transcribe, or speak as the user unless
  the authorization, account identity, and consent policy are explicit.
- Prefer agenda preparation, live notes when authorized, summary drafting, and
  action-item extraction over active participation.
- When referencing an external meeting-agent repo, first inspect its auth,
  consent, recording, environment-variable, and data-retention model.
- If `agent-lime` is the reference implementation, record the orchestrator,
  media-gateway, speech-agent, calendar, Vexa, STT/TTS, storage, webhook,
  internal-token, and deployment secret/env split before claiming the setup
  path is actionable. Record variable names and classes only; never copy secret
  values.

## Problem-finding cards

Use these when a request, complaint, or product/review finding may be framed too
narrowly. They support negative-space discovery, but do not replace evidence
gates.

```text
contradiction card:
  desired benefit:
  worsening harm:
  user/system contradiction:
  ideal final result:
  available resources already in product/repo:
  separation move:
  candidate affordance:
  kill condition:

problem-construction card:
  raw request/complaint:
  hidden job-to-be-done:
  frame A:
  frame B:
  frame C:
  supporting cues:
  refuting cues:
  selected frame:
  smallest validation probe:
```

## Feedback pruning record

Use this before promoting, merging, or keeping accumulated feedback rules.

```text
feedback ledger:
scope:
rules considered:
contradictions:
duplicates:
superseded rules:
measured regressions:
weak or stale evidence:
rules kept:
rules needing review:
rules pruned:
next retry sample:
promotion decision:
```

## Fusion review card

Use this before launching multi-reviewer or multi-model deliberation.

```text
task:
why fusion is justified:
runner: scripts/fairy_fusion_review.py | harness-native equivalent
confidentiality/provider boundary:
panel/reviewer roles:
judge/synthesizer:
max reviewers:
max tool calls:
recursion cap:
required output schema:
consensus:
contradictions:
partial coverage:
unique insights:
blind spots:
final closure actions:
```

## Domain router card

Use this before applying a Fairy Tale harness to a benchmark or unfamiliar
task family.

```text
task family: agentic coding | refactoring | closed-ended knowledge | legal | bio/health | finance/document | spatial/UI/3D | narrative | mechanism discovery | defensive security | other
benchmark or workflow target:
why this family:
harness selected:
harness rejected:
domain-specific risks:
answer/output contract:
validation:
fallback/refusal/safety routing to record:
```

## Effort inversion record

Use this when tuning `medium`, `high`, `xhigh`, max effort, or any provider
equivalent.

```text
task family:
sample IDs:
model/API path:
prompt/version:
scorer/judge:
max output / reasoning budget:
concurrency: new items per worker
medium result:
high result:
xhigh/max result:
latency/cost:
incomplete/truncated responses:
reasoning token usage:
item-level wins/losses:
failure taxonomy:
selected effort:
cause of inversion:
fix:
```

## Knowledge crystallization record

Use this for HLE-style closed-ended academic or expert-knowledge tasks.

```text
subject:
answer type:
required exactness:
known independent terms:
answer choices / candidate forms:
minimal derivation:
final answer contract:
confidence calibration:
error class if wrong:
```

## Legal reasoning record

Use this for legal benchmarks, contract review, redlines, legal summaries, or
agentic legal workflows.

```text
jurisdiction:
authority/date:
procedural posture:
task type:
facts:
issue:
rule:
application:
conclusion:
citations/source grounding:
confidentiality/privilege concerns:
legal-advice boundary:
subtask score:
```

## Bio/health safety record

Use this for biology, medicine, health, chemistry-adjacent, or life-science
tasks.

```text
task class: benign explanation | clinical guidance | lab protocol | molecular mechanism | dual-use biology | hazardous content | other
safety boundary:
established facts:
uncertain interpretation:
hypothesis:
clinical or lab escalation needed:
fallback/refusal event:
final-answer boundary:
```

## Evidence table record

Use this for finance, documents, charts, tables, spreadsheets, and enterprise
knowledge work.

```text
source artifact:
extracted facts:
table/cell/page references:
assumptions:
calculation steps:
judgment:
uncertainties:
artifact-backed progress claims:
```

## Spatial forge brief

Use this before 3D, CAD, simulation, or game-scene work.

```text
scene/object goal:
target runtime/toolchain: Three.js | Blender | Unreal | Unity | native GPU | CAD API | other
units and coordinate system:
camera/framing:
geometry constraints:
materials/lighting:
physics/simulation assumptions:
interaction controls:
performance target:
validation views:
visual correctness checks:
functional/mechanical checks:
known non-goals:
```

## 3D validation checklist

```text
render opens without runtime errors:
first frame is nonblank:
camera frames the intended subject:
controls work:
animation/simulation advances:
geometry is not inverted/collapsed:
materials/lights reveal shape:
text/UI does not overlap canvas controls:
mobile/desktop viewport checks:
for CAD: dimensions and manufacturability checked:
```

## Narrative empathy brief

Use this for prose, daily conversation, brand voice, emotionally sensitive
messages, or UI feel.

```text
audience:
relationship:
emotional state:
practical need:
desired aftertaste:
voice/profile source:
register:
pacing and rhythm:
metaphor/style constraints:
taboos and avoid-list:
UI/product context:
must-feel-like:
must-not-feel-like:
validation reader:
```

## Voice profile card

```text
speaker/brand/persona:
sample sources:
sentence shape:
paragraph rhythm:
preferred diction:
humor/irony level:
warmth/directness:
technicality:
recurring structures:
forbidden tells:
editing checklist:
```

## UI affect checklist

```text
primary user emotion:
first screen signal:
information density:
microcopy tone:
motion rhythm:
empty state:
error/recovery state:
confirmation state:
visual hierarchy supports mood:
next action obvious:
cognitive load reduced:
user dignity preserved:
```

## Mechanism grammar record

Use this for ARC-style hidden-rule games, unfamiliar tools, simulations, or
systems where behavior must be learned from observation.

```text
task/environment:
observability tools:
score/recovery ledger:
objects and coordinates:
available actions:
action -> diff observations:
animation layers inspected:
hidden state hypotheses:
autonomous actors / phase:
resources / timers:
win trigger hypotheses:
confirmed rules:
refuted rules / no-ops:
compiled solver/planner:
remaining opaque points:
```

## External reconstruction adapter record

Use this when connecting an outside reconstruction project such as OpenMythos.
Prefer Rust-based adapter validation/orchestration in
`crates/fairy-adapter-runner`; use Python only behind an external runtime
boundary when the external project requires it.

```text
adapter id:
adapter manifest:
upstream repo:
fork repo:
source commit:
local path:
license:
capability being tested:
configuration:
input artifact:
output artifact:
baseline:
validation checks:
claim boundary:
next probe:
```

## Refactoring similarity record

Use this before broad TypeScript refactors.

```text
adapter id:
target project:
command/options:
raw report artifact:
candidate cluster:
mode: functions | types | classes | overlap
similarity score:
semantic risk:
behavioral invariant:
call sites:
tests/typecheck:
refactor plan:
post-refactor validation:
false positive / false negative note:
```

## Accessible genius method record

Use this when applying a method from `references/genius-methods.md`. Record the
operational method, not the personality or myth around the source figure.

```text
task:
selected cards:
why these cards fit:
discarded famous methods:
modern limiter:
artifact produced:
validation:
misuse avoided:
next checkpoint:
```
