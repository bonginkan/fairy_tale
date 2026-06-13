# Distilled Capabilities

The observed capabilities are process capabilities, not model access.

## Autonomous long-task execution

Official materials describe Fable/Mythos as able to work autonomously longer
than prior Claude models. Public reports suggest the capability is powerful but
can burn tokens rapidly if allowed to fan out without limits.

Workflow translation:

- require a task budget,
- run a pilot,
- cap parallel agents,
- checkpoint frequently,
- validate before continuing.

## Codebase-wide engineering

Official launch materials cite large-codebase migration, production-code
benchmarks, and strong agentic coding results.

Workflow translation:

- map the codebase before edits,
- define invariants,
- search call sites,
- perform scoped transformations,
- keep rollback paths,
- run validation after each slice.

## Benchmark superiority as process advantage

Official and third-party benchmark discussions point to several distinct
mechanisms behind reported advantage:

- longer uninterrupted task horizons,
- stronger use of adaptive reasoning and effort controls,
- better codebase and tool generalization,
- vision-grounded extraction and reconstruction,
- persistent file-based memory during long tasks,
- fewer turns on spreadsheet, analytics, and vibe-coding tasks,
- strong but domain-sensitive safeguards and fallbacks.

Workflow translation:

- define the benchmark-shaped task and rubric before starting,
- reproduce the enabling conditions instead of copying the benchmark prompt,
- compare against a baseline process,
- track cost, elapsed time, fallback/refusal events, and validation artifacts,
- preserve failures, timeouts, and hallucinated validation as first-class
  results.

## High-end analytical work

Official reports highlight finance, document, chart, table, conceptual
reasoning, root-cause analysis, and expected-value analysis.

Workflow translation:

- build an evidence map,
- separate data extraction from judgment,
- use intermediate tables,
- state assumptions and uncertainty,
- verify calculations.

## Vision-grounded reconstruction

Official reports emphasize scientific figure extraction and rebuilding web apps
from screenshots. User reports include interactive explanatory sites and
self-QA.

Workflow translation:

- extract visual facts,
- reconstruct candidate structure,
- inspect rendered output,
- compare against target,
- iterate until visual and functional checks pass.

## Spatial and 3D generation

Official demos include a browser-based CAD editor that produced a complete
3D-printable model, a physics-derived solar-system simulation, Factorio
automation, and a music-synchronized fluid simulation. Public reports include
custom Three.js worlds, 3D games, Fusion/CAD demos, and native 3D/Metal game
projects. These reports are uneven: some show impressive spatial execution,
while others show overconfident or mechanically implausible outputs.

Workflow translation:

- make the spatial contract explicit: units, axes, camera, scale, materials,
  collision, lighting, interaction, and performance,
- use established 3D/CAD/rendering libraries rather than inventing engines,
- build and validate incrementally from primitives to full scene,
- inspect actual rendered frames and interaction behavior,
- separate visual beauty, geometric validity, physical plausibility, and
  manufacturability.

## Defensive cyber capability

Project Glasswing reports strong vulnerability discovery and validation
capability. This repository only uses defensive translations.

Workflow translation:

- authorized targets only,
- vulnerability triage harness,
- post-validation stages,
- patch-first output,
- responsible disclosure,
- no exploit weaponization.

## Workflow self-improvement

Public users reported success asking Fable 5 to inspect Claude Code configs,
session history, local commands, workflows, and skills, then synthesize an
integrated setup.

Workflow translation:

- inventory current workflow,
- identify repeated manual operations,
- propose minimal reusable commands/skills,
- preserve token budget,
- add memory/config only when it reduces repeated future work.
