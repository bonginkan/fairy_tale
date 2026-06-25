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
- Store source references, triage decisions, actions, validation, and reviewer
  state in a run ledger or receipt. Do not rely on chat memory alone.
- Keep source collection, task selection, execution, review, and learning as
  separate stages so each can be audited and replaced.
- Start in read-only or draft mode. Escalate to write/send/join only after the
  approval boundary and credential scope are explicit.
- A loop that repeats the same failure class without a changed probe,
  validation result, or escalation is stopped, not retried indefinitely.

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
