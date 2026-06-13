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
9. Defensive security constraints for cyber workflows.

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
must preserve negative results instead of converting public launch claims into
unqualified assumptions.

## 3D and spatial work translation

Official materials already include several spatial demonstrations: a
browser-based CAD editor and 3D-printable model, physics-derived solar-system
simulation, Factorio automation, and a music-synchronized fluid simulation.
Public reports add custom Three.js worlds, 3D game demos, Fusion/CAD examples,
and a native Swift/Metal block-survival game. There are also negative examples
where the model remained overconfident about weak 3D output.

The reproducible process is `Spatial Forge Harness`:

1. write a spatial brief before coding: units, axes, camera, scale, materials,
   lighting, controls, collision, simulation, and performance target,
2. choose a proven rendering or CAD substrate,
3. build in inspectable layers from primitive geometry to final polish,
4. render early and repeatedly,
5. validate first frame, camera framing, controls, animation, geometry, and
   viewport behavior,
6. for CAD/printable objects, separate visual plausibility from dimensional,
   mechanical, and manufacturability correctness.

## Derived process names

- `Fairy Tale Loop`: high-level plan -> scoped scouts -> synthesis -> validation -> memory update.
- `Fable Harness`: token-budgeted long-task execution harness.
- `Mythos Defensive Harness`: defensive security review harness with validation gates.
- `Glass Slipper Gate`: stop condition for runaway agent fan-out or uncertain results.
- `Benchmark Delta Harness`: controlled comparison of baseline and candidate
  process under benchmark-like conditions.
- `Spatial Forge Harness`: 3D/CAD/simulation workflow with spatial contracts
  and rendered-output validation.
