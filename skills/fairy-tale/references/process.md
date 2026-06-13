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
target runtime/toolchain:
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
