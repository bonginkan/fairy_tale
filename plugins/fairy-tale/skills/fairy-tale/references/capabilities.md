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
- legal redline and document-review strength,
- finance, chart, table, and expected-value analysis,
- scientific hypothesis generation and life-sciences tool orchestration,
- strong but domain-sensitive safeguards and fallbacks.

Workflow translation:

- define the benchmark-shaped task and rubric before starting,
- reproduce the enabling conditions instead of copying the benchmark prompt,
- compare against a baseline process,
- track cost, elapsed time, fallback/refusal events, and validation artifacts,
- preserve failures, timeouts, and hallucinated validation as first-class
  results.

## Domain-sensitive routing

Applying a coding-oriented workflow directly to a broad academic benchmark can
create routing and scoring errors. Fable/Mythos reports span separate
capability families: agentic coding, legal redlines, finance and document
reasoning, vision/spatial reconstruction, life sciences, biology/medicine,
long-memory games, and defensive cyber. A single harness should not be used for
all of them.

Workflow translation:

- classify the task family before choosing a process,
- use coding and refactoring harnesses only for software-shaped work,
- use a strict answer contract for closed-ended benchmark tasks,
- use legal, bio/health, finance/document, and spatial harnesses for those
  domains,
- require controlled evidence before making cross-domain capability claims.

## Effort inversion

Higher effort can improve verification on hard tasks, but it can also create
overthinking, unnecessary context gathering, truncation, cost blowups, or
incorrect coupling of independent terms. OpenAI documents `medium` as the
default balanced starting point for `gpt-5.5`, and `xhigh` as appropriate only
when evals show clear benefit. Anthropic similarly advises considering all
Fable effort levels and notes that higher effort can overplan routine tasks.

Workflow translation:

- sweep `medium`, `high`, and `xhigh` on the same task slice before choosing,
- keep model, API, prompt, sample, scorer, and output budget fixed,
- log reasoning token usage, incomplete responses, latency, cost, and
  item-level deltas,
- diagnose inversions instead of accepting them as noise,
- use the lowest effort that wins or ties within confidence bounds.

## High-end analytical work

Official reports highlight finance, document, chart, table, conceptual
reasoning, root-cause analysis, and expected-value analysis.

Workflow translation:

- build an evidence map,
- separate data extraction from judgment,
- use intermediate tables,
- state assumptions and uncertainty,
- verify calculations.

## Legal reasoning and redline work

Official Fable materials include customer claims that legal redlines matched or
beat existing models, while LegalBench-style third-party reporting shows strong
aggregate legal scores but also warns that performance varies sharply by legal
task type. Legal work therefore needs its own harness rather than generic
coding-agent scaffolding.

Workflow translation:

- identify jurisdiction, authority type, date, procedural posture, and task
  type,
- separate facts, issue, rule, application, conclusion, caveats, and citations,
- preserve confidentiality and avoid legal-advice overclaiming,
- evaluate by subtask, not only aggregate accuracy,
- record citation validity, jurisdiction correctness, privilege handling, and
  refusal calibration when relevant.

## Bio, medicine, and health

Official materials describe life-science and biology strengths while also
documenting safety classifiers that may refuse or reroute biology, chemistry,
and life-science tasks. Public reporting also indicates false positives on
benign biology. Bio/health work must distinguish reasoning capability from
safety routing and domain boundaries.

Workflow translation:

- classify the task as benign explanation, clinical guidance, lab protocol,
  molecular mechanism, dual-use biology, or hazardous content,
- use conservative boundaries for actionable wet-lab or medical content,
- separate established facts from hypotheses and clinical recommendations,
- record fallback/refusal events as benchmark data,
- require uncertainty and escalation language for health claims.

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
custom Three.js worlds, 3D games, Fusion/CAD demos, Blender scene/modeling
workflows, Unreal Engine game/editor workflows, Unity-style game workflows, and
native 3D/Metal game projects. These reports are uneven: some show impressive
spatial execution, while others show overconfident or mechanically implausible
outputs.

Workflow translation:

- make the spatial contract explicit: units, axes, camera, scale, materials,
  collision, lighting, interaction, and performance,
- choose the right substrate: Three.js for portable browser scenes, Blender for
  asset generation/procedural geometry, Unreal or Unity for full engine
  workflows, native GPU APIs for platform-specific games, and CAD APIs for
  dimensional mechanical work,
- build and validate incrementally from primitives to full scene,
- inspect actual rendered frames and interaction behavior,
- separate visual beauty, geometric validity, physical plausibility, and
  manufacturability.

## Narrative expression, EQ, and UI affect

Official prompting guidance emphasizes intent, readability, progress grounding,
and clear user-facing communication in long agentic runs. Public reports suggest
stronger performance in style-specific documents, editorial critique, polished
long-form writing, rich email templates, and UI/UX prototypes. Independent
writing commentary is more cautious: raw capability improves polish and
structure, but specific voice fidelity still depends on an explicit voice
profile.

Workflow translation:

- start with a voice and affect brief, not only a topic,
- model emotional competence as perception -> understanding -> response
  management, not as generic politeness,
- keep a reusable voice profile for people, brands, products, or fictional
  narrators,
- design UI as an emotional conversation: the layout, motion, copy, density,
  and recovery states should all express the intended relationship,
- validate against target-user reading: clarity, dignity, trust, delight, and
  next-action obviousness.

## ARC-style mechanism discovery

Jun's ARC-AGI-3-Lab run reached 24 cleared levels by expanding the harness while
solving. The distinctive pattern was not brute force. It was instrumented
mechanism discovery: build bridge/replay/ledger tools, inspect action diffs and
animation layers, extract hidden rules, then compile stable rules into targeted
search or choreography.

Workflow translation:

- create observability before deep reasoning,
- treat each action as a micro-experiment with predicted and measured effects,
- inspect every frame/layer when animation or hidden state may matter,
- write down false hypotheses and no-op results,
- elevate repeated mechanics into reusable grammars,
- switch from exploration to BFS/planning only after the grammar is stable,
- preserve recovery handles for long runs, scorecards, and remote sessions.

## External theoretical reconstruction

OpenMythos provides a public MIT-licensed theoretical reconstruction of a
Mythos-like recurrent-depth transformer. Fairy Tale should use it as an
external adapter, not as vendored truth. The useful capability is not "we have
Claude Mythos"; it is a controlled way to probe architectural hypotheses such
as looped depth, input reinjection, MLA/GQA attention, and MoE recurrence.

Workflow translation:

- fork or pin the external source,
- describe it with an adapter manifest,
- validate the manifest before use,
- run small probes first,
- record commit/config/input/output evidence,
- compare against baselines before claiming an advantage,
- keep claim boundaries explicit.

## Refactoring similarity amplification

`kongyo2/similarity` is a TypeScript structural-similarity analyzer with a
Rust/WASM native core and TypeScript CLI wrapper. It is useful for reproducing
one piece of Fable-class refactoring behavior: grounded duplicate discovery
before the model writes a refactor plan.

Workflow translation:

- run structural similarity before large refactors,
- cluster functions/types/classes/overlap separately,
- treat findings as candidates, not proofs,
- write invariants and test targets for each cluster,
- refactor one cluster at a time,
- use false positives and missed duplicates as benchmark data.

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
