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
