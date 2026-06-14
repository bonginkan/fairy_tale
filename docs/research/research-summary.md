# Research Summary: Fable/Mythos-Class Workflows

Date: 2026-06-14 JST

## Scope

This note summarizes public official information and public user reports about
Claude Fable 5 / Mythos 5, then translates the observed strengths into
repeatable workflow patterns. It intentionally avoids access bypass,
safeguard bypass, or offensive cyber reproduction.

## Official information

Anthropic announced Claude Fable 5 and Claude Mythos 5 on June 9, 2026.
Anthropic describes Mythos 5 as the same underlying model as Fable 5, with
some safeguards lifted for approved trusted-access users. Fable 5 was made
generally available at launch; Mythos 5 was limited to Project Glasswing and
planned trusted-access programs.

Officially reported strengths include:

- Longer autonomous work than prior Claude models.
- Software engineering at codebase-wide scale.
- Strong document, chart, table, and problem-solving performance.
- Strong vision, including scientific figure reading and screenshot-to-code.
- Legal redline and document-review strength reported by early enterprise
  users.
- Finance, spreadsheet, and expected-value analysis reported by early
  enterprise users.
- Life-science, biology, genomics, and drug-design assistance reported in
  Anthropic's Mythos/Glasswing materials, subject to safety boundaries and
  fallback behavior in Fable.
- Improved memory and tool use through supported features such as adaptive
  thinking, task budgets, memory tools, code execution, programmatic tool
  calling, context editing, compaction, and vision.
- Mythos-class defensive security performance through Project Glasswing.

Anthropic later stated that the US government issued an export-control
directive suspending access to Fable 5 and Mythos 5 by foreign nationals.
Anthropic disabled access for customers to comply and stated that other
Anthropic models were unaffected.

Key official sources:

- https://www.anthropic.com/news/claude-fable-5-mythos-5
- https://platform.claude.com/docs/en/about-claude/models/introducing-claude-fable-5-and-claude-mythos-5
- https://www.anthropic.com/glasswing
- https://www.anthropic.com/news/expanding-project-glasswing
- https://www.anthropic.com/news/fable-mythos-access
- https://www-cdn.anthropic.com/d00db56fa754a1b115b6dd7cb2e3c342ee809620.pdf
- https://www.anthropic.com/claude/fable
- https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5

## Public user reports

Public reports are anecdotal and must be treated as hypotheses, not proof.
Still, recurring patterns are useful for workflow design.

Reported strengths:

- Workflow self-improvement: users asked Fable 5 to audit Claude Code
  configuration, session history, local commands, workflows, and skills; it
  produced coordinated local commands and shared memory structures.
- Self-QA behavior: a user reported that Fable 5 built an interactive
  Riemann Hypothesis explainer, computed underlying mathematical data,
  cross-checked values, opened a browser, and tested interactions without
  being explicitly asked.
- Code and analytical step-change: several public summaries describe coding
  and analytical work as a noticeable jump, while also warning about token
  burn and broad guardrails.
- Low-effort strength: some users reported that lower effort was sufficient
  for substantial coding outcomes, implying that maximum effort should not be
  the default.
- Agent fan-out risk: multiple users reported rapid quota or credit burn
  when Fable 5 was allowed to spawn many parallel agents or run broad tasks
  without budgets.

Representative public reports:

- https://www.reddit.com/r/ClaudeCode/comments/1u37glf/if_you_do_one_thing_with_fable_5_access_do_this/
- https://www.reddit.com/r/ClaudeCode/comments/1u2v2sl/terrible_start_to_the_day_with_fable_5/
- https://www.reddit.com/r/ClaudeAI/comments/1u2rv2i/i_asked_fable_5_in_claude_code_to_explain_the/
- https://www.linkedin.com/posts/paul--_anthropic-released-claude-fable-5-reddit-activity-7470369702138232832-nfpG
- https://blog.cloudflare.com/cyber-frontier-models/

## Capability translation

The skill should not imitate a model. It should reproduce the process patterns:

1. Goal shaping before action.
2. Strict budget envelope before autonomy.
3. Parallel scouts only when scoped.
4. Heavy reasoning only after scout summaries.
5. Evidence maps and provenance.
6. Validation before claiming completion.
7. Context compression with recovery handles.
8. Memory and configuration updates after success.
9. Defensive security constraints, triage, patch validation, and detection
   coverage for cyber workflows.

## Benchmark advantage translation

Benchmark superiority appears to come from enabling conditions, not from a
single prompt trick. The strongest recurring pattern is that Fable/Mythos-class
work is allowed to operate with a larger task envelope: more elapsed time,
adaptive effort, persistent notes, broad but scoped tool use, visual inspection,
and explicit validation. This maps to a reusable `Benchmark Delta Harness`:

1. define the benchmark-shaped task family and rubric,
2. record the baseline model/process,
3. reproduce relevant conditions: effort, task budget, memory, tools, fallback
   behavior, and elapsed-time allowance,
4. run the candidate process on the same artifact,
5. score with objective evidence whenever possible,
6. record cost, time, hallucinated validation, fallback/refusal events, and
   failure cases.

This matters because not every independent benchmark confirms a broad win.
Endor Labs reported middling Fable 5 results on its code-fixing benchmark and
highlighted timeouts plus memorization-like behavior. The process therefore
must keep failures and weak runs as debugging evidence instead of converting
public launch claims into unqualified assumptions.

## Domain gap and effort findings

Fairy Tale should not be treated as a universal benchmark booster until each
task family has its own harness and reproduction evidence. HLE is a
closed-ended academic benchmark, while much of the current Fairy Tale process
was tuned around agentic coding and workflow-improvement reports. Legal,
bio/health, finance/document, and spatial workflows also need distinct output
contracts and failure taxonomies.

The corrective process is `Domain Router + Effort Inversion Debugger`:

1. route by task family before choosing a harness,
2. use Knowledge Crystallization for HLE-style closed-ended tasks,
3. use Legal Reasoning for legal redlines and legal benchmarks,
4. use Bio/Health Safety for biology, medicine, chemistry-adjacent, and health
   tasks,
5. use Evidence Table for finance, spreadsheets, charts, and document work,
6. sweep effort settings on the same sample before assuming `xhigh` is better,
7. diagnose effort inversions with item-level deltas, token budgets,
   incomplete responses, answer-format errors, and domain-specific failure
   classes.

OpenAI documents `gpt-5.5` `medium` as the default balanced starting point and
`xhigh` as appropriate only when evals show clear benefit. Anthropic's Fable
prompting guide similarly recommends considering all effort levels: higher
effort can improve verification on hard work, but can also overplan routine or
ambiguous tasks. Fairy Tale should therefore prove the effort setting per task
family instead of defaulting to maximum effort.

Legal and knowledge benchmarks should be treated as separate capability
families. Vals AI reports Claude Fable 5 as the top LegalBench model at the
time checked, but also notes large variation across legal task types.
HazyResearch LegalBench consists of 162 tasks from 40 contributors, and
LegalAgentBench evaluates practical legal agents with intermediate-process
signals. The reproduction target should therefore include jurisdiction,
authority, citation, privilege/confidentiality, and subtask-level scoring,
not generic legal prose quality.

## 3D and spatial work translation

Official materials already include several spatial demonstrations: a
browser-based CAD editor and 3D-printable model, physics-derived solar-system
simulation, Factorio automation, and a music-synchronized fluid simulation.
Public reports add custom Three.js worlds, 3D game demos, Fusion/CAD examples,
Blender scenes/modeling workflows, Unreal Engine game/editor workflows,
Unity-style workflows, and a native Swift/Metal block-survival game. There are
also negative examples where the model remained overconfident about weak 3D
output.

The reproducible process is `Spatial Forge Harness`:

1. write a spatial brief before coding: units, axes, camera, scale, materials,
   lighting, controls, collision, simulation, and performance target,
2. choose a proven rendering or CAD substrate: Three.js for browser scenes,
   Blender for procedural assets/scenes, Unreal or Unity for full engine
   workflows, native GPU APIs for platform-specific games, or CAD APIs for
   dimensional mechanical objects,
3. build in inspectable layers from primitive geometry to final polish,
4. render early and repeatedly,
5. validate first frame, camera framing, controls, animation, geometry, and
   viewport behavior,
6. for CAD/printable objects, separate visual plausibility from dimensional,
   mechanical, and manufacturability correctness.

## Narrative, EQ, and interface expression

The same capability cluster appears in prose and UI work. Official prompting
guidance emphasizes understanding why a user asks, producing readable
user-facing communication after long runs, and grounding progress claims in
evidence. Public reports add style-specific documents, editorial critique,
creative-writing improvements, rich email templates, and UI/UX one-shots.
Writing reports are mixed: Fable-class raw drafts can be more polished, but
specific authorial voice still requires a structured voice profile.

The reproducible process is `Narrative Empathy Harness`:

1. define audience, relationship, emotional state, practical need, and desired
   aftertaste before writing,
2. extract or provide a voice profile when the output must sound like a person,
   brand, product, or fictional narrator,
3. separate emotion perception, emotion understanding, and response management,
4. translate UI affect into layout density, hierarchy, motion, color, microcopy,
   empty states, and error recovery,
5. validate from the target user's perspective: clarity, dignity, trust,
   delight, and next-action obviousness.

## ARC-AGI-3-Lab translation

Jun's local ARC-AGI-3-Lab run reached 24 cleared levels while expanding the
repo's bridge, replay, recording, and score-recovery tooling. The distinctive
pattern was instrumented rule discovery rather than unbounded brute force:

1. build observability first: long-lived bridge, `/frame`, recordings, replay,
   level ledger, and scorecard recovery,
2. sweep all games to map action spaces and classify mechanics,
3. park opaque cases and rotate instead of spending the whole budget on a
   single unknown rule,
4. use action-diff micro-experiments to convert visuals into object grammars,
5. inspect every animation layer when final frames hide the real mechanism,
6. write down refuted hypotheses and no-ops as durable evidence,
7. once rules stabilize, compile them into joint-state search, phase planning,
   choreography, or geometry solvers,
8. preserve recovery handles because long sessions and remote scorecards can
   disappear.

Examples from the run:

- `tu93`: enemy phase and pellet-gate rules became a joint `(player, phase)`
  BFS after live observations stabilized.
- `g50t`: fluid, squeeze, one-way valve, dice freezing, and mode switching
  became a reusable physics grammar.
- `wa30`: autonomous helper blocks required choreography and frequent frame
  reads because blocked movement broke dead reckoning.
- `re86`: geometric arm/pip intersections became a deterministic placement
  rule.

The reusable process is `Mechanism Grammar Harness`.

## OpenMythos external reconstruction

`kyegomez/OpenMythos` is an MIT-licensed public theoretical reconstruction of a
Mythos-like recurrent-depth transformer. A `bonginkan/OpenMythos` fork now
exists for pinning and future experiments. Fairy Tale should not vendor or
modify that source by default. Instead, it uses an adapter manifest:

- `adapters/openmythos.adapter.json`
- `schemas/fairy-tale-adapter.schema.json`
- `docs/adapters/openmythos-external-adapter.md`

This creates an `External Reconstruction Adapter Harness`: external repos
provide speculative implementations; Fairy Tale provides orchestration,
evidence capture, validation, claim boundaries, and comparison against baseline
processes. The adapter layer is Rust-based (`crates/fairy-adapter-runner`) so
future orchestration does not depend on Python except when an external project,
such as OpenMythos, is itself a Python/PyTorch runtime.

## Similarity-assisted refactoring

`kongyo2/similarity` is a TypeScript similarity analyzer with a Rust/WASM native
core and TypeScript CLI wrapper. It is relevant because it turns a hard
refactoring prompt into an evidence-first workflow: detect structural duplicate
candidates, then ask the agent to build a refactoring plan from the report.

The useful process is `Refactoring Similarity Harness`:

1. run the analyzer before large TypeScript refactors,
2. separate function, type, class, and overlap findings,
3. cluster candidates and discard intentional duplication,
4. write invariants and tests for each cluster,
5. refactor one cluster at a time,
6. validate after every slice,
7. record false positives and false negatives as local benchmark data.

This should be treated as a refactoring amplifier, not a substitute for semantic
review.

## Derived process names

- `Fairy Tale Loop`: high-level plan -> scoped scouts -> synthesis -> validation -> memory update.
- `Fable Harness`: token-budgeted long-task execution harness.
- `Mythos Defensive Harness`: defensive security review harness with validation gates.
- `Cyber Frontier Defense Harness`: authorized security workflow with asset
  maps, trust boundaries, safe evidence, patch-first remediation, regression
  tests, detection coverage, and root-cause triage.
- `Glass Slipper Gate`: stop condition for runaway agent fan-out or uncertain results.
- `Benchmark Delta Harness`: controlled comparison of baseline and candidate
  process under benchmark-like conditions.
- `Domain Router`: task-family selection before applying a harness.
- `Knowledge Crystallization Harness`: closed-ended academic/expert benchmark
  workflow with strict answer contracts and item-level error analysis.
- `Legal Reasoning Harness`: jurisdiction, authority, citation, confidentiality,
  and subtask-aware legal workflow.
- `Bio/Health Safety Harness`: biology, medicine, chemistry-adjacent, and health
  workflow with safety classification and fallback/refusal logging.
- `Evidence Table Harness`: finance, spreadsheet, chart, table, and document
  extraction before judgment.
- `Effort Inversion Debugger`: same-sample effort sweep and item-level diagnosis
  when higher effort underperforms lower effort.
- `Spatial Forge Harness`: 3D/CAD/simulation workflow with spatial contracts
  and rendered-output validation.
- `Narrative Empathy Harness`: prose, conversation, and UI affect workflow
  grounded in voice profiles and target-user emotional validation.
- `Mechanism Grammar Harness`: ARC-style hidden-rule discovery through
  instrumentation, micro-probes, layer inspection, and compiled solvers.
- `External Reconstruction Adapter Harness`: adapter-manifest boundary for
  probing external theoretical reconstructions such as OpenMythos without
  vendoring or overstating them.
- `Refactoring Similarity Harness`: structural-similarity report -> candidate
  clusters -> invariant-aware refactor plan -> slice validation.
- `Best-Practice Gate`: current official/upstream guidance -> local
  applicability -> eval/tool/context/OSS contract -> validation artifact.
