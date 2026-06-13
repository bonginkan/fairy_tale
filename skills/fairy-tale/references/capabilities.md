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

