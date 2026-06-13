---
name: fairy-tale
description: Distills Fable/Mythos-class public workflow patterns into budgeted, evidence-driven, validation-gated agent execution for coding, research, documentation, UI/3D, creative writing, emotionally aware conversation, ARC-style puzzle discovery, and defensive security tasks. Use when the user asks for Mythos/Fable-style performance, autonomous long-task execution, workflow self-improvement, codebase-wide migration, high-signal research synthesis, narrative/UI expression, mechanism discovery, or defensive vulnerability-review process design.
---

# Fairy Tale

Use this skill to emulate the *process* patterns reported for Fable/Mythos-class
work, not to access or bypass those models.

## Non-negotiables

- Do not bypass model access controls, export controls, or safeguards.
- Security work is defensive-only and must stay within authorized targets.
- Set a budget before starting: time, context, tool calls, money, write scope.
- Do not spawn broad parallel agents without an explicit fan-out cap.
- Preserve sources and provenance.
- Validate before claiming completion.

## Default workflow

1. **Frame the quest**
   - Restate the user's objective, constraints, risk, and success criteria.
   - Identify whether the task is coding, research, workflow improvement,
     migration, visual reconstruction, documentation, narrative/UI expression,
     mechanism discovery, or defensive security.

2. **Set the Glass Slipper Gate**
   - Define stop limits: max subtasks, max files, max web searches, max tool
     calls, max elapsed time, and escalation conditions.
   - Prefer a small pilot before full autonomy.

3. **Scout before synthesis**
   - Use cheap/scoped scouts for code search, logs, web research, or config
     inspection.
   - Scouts return compact findings with file paths, links, and uncertainties.
   - The main agent performs synthesis only after scout summaries exist.

4. **Build the evidence map**
   - Track claims as `claim -> source -> confidence -> action`.
   - Separate official facts, third-party reports, user anecdotes, and local
     observations.

5. **Choose a route**
   - For code migration: map ownership, invariants, call sites, tests, and
     rollback plan before editing.
   - For research: prioritize primary sources, then high-signal field reports.
   - For workflow improvement: inspect existing commands, skills, agents,
     memories, hooks, and sessions before adding new structure.
   - For defensive security: use only authorized code and produce verification
     steps, not exploit instructions.

6. **Execute in checkpoints**
   - Work in small completed slices.
   - After each slice, update the evidence map and remaining risk.
   - Stop if the task exceeds the Glass Slipper Gate.

7. **Validate**
   - Run available checks or perform manual verification.
   - For UI/visual work, inspect actual outputs.
   - For security findings, require reproducible defensive evidence and
     responsible-disclosure framing.

8. **Consolidate**
   - Produce durable artifacts: summary, changed files, config update, skill
     improvement, checklist, or issue.
   - Record what should be reused next time.

## Mode patterns

### Fable Harness: long coding or migration tasks

- Start with repository map and invariants.
- Generate a migration plan with checkpoints.
- Edit only scoped files.
- Validate continuously.
- Prefer lower effort or smaller scopes before expensive broad autonomy.

### Mythos Defensive Harness

- Confirm authorization and target scope.
- Build an asset map and suspected-risk taxonomy.
- Use static analysis, tests, and source inspection before conclusions.
- Validate suspected vulnerabilities defensively.
- Do not provide weaponization, stealth, persistence, credential theft, or
  public exploit instructions.

### Workflow self-improvement

- Inspect current agent config, skills, commands, hooks, and usage patterns.
- Search for comparable OSS workflows only when useful.
- Ask targeted questions before changing user workflow.
- Add the smallest reusable command/skill/memory structure that reduces future
  repeated prompting.

### High-signal research synthesis

- Separate primary sources from user reports.
- Build a claim table before writing conclusions.
- Include uncertainty and reproducibility notes.
- Convert findings into a reusable procedure or artifact.

### Benchmark Delta Harness

- Identify which benchmark capability is being targeted: agentic coding,
  knowledge work, vision, long-memory, scientific reasoning, defensive cyber,
  or multimodal UI/3D.
- Recreate the enabling conditions, not the headline score: task budget,
  effort level, context strategy, tools, fallback behavior, memory, validation,
  and elapsed-time allowance.
- Use a baseline model/process on the same task when possible.
- Measure deltas with artifacts: pass/fail tests, rendered screenshots,
  benchmark rubrics, human review notes, cost, and elapsed time.
- Record negative results; do not claim Fable/Mythos-style superiority without
  a reproducible harness.

### Spatial Forge Harness: 3D, CAD, and simulation work

- Require an explicit spatial brief: coordinate system, units, camera,
  interactions, geometry constraints, physics assumptions, and performance
  target.
- Prefer proven engines or libraries for the domain, such as Three.js for
  browser 3D, Unreal Engine or Unity for full game/editor workflows, Blender
  Python or Geometry Nodes for asset and scene generation, platform-native
  renderers for native apps, or CAD APIs for mechanical modeling.
- Build the scene in layers: primitives -> lighting/materials -> controls ->
  physics/simulation -> validation overlays -> polish.
- Verify by rendering the actual output, checking nonblank frames, camera
  framing, interaction, animation, and obvious geometry defects.
- For CAD or printable objects, distinguish visual plausibility from mechanical
  correctness; require dimensional checks before claiming functional design.

### Narrative Empathy Harness: prose, conversation, and UI feel

- Build a voice and affect brief before writing: audience, relationship,
  emotional state, desired aftertaste, register, pacing, taboos, and examples.
- Separate raw model polish from voice fidelity; use a voice profile when the
  output must sound like a specific person or brand.
- For daily conversation, infer the user's practical and emotional need, then
  respond with useful action plus calibrated warmth.
- For UI, translate emotion into concrete interaction choices: information
  density, hierarchy, microcopy, rhythm, motion, color, empty states, and error
  recovery.
- Validate by reading as the target user: does it reduce cognitive load, preserve
  dignity, and make the next action obvious?

### Mechanism Grammar Harness: ARC-style hidden-rule discovery

- Instrument before solving: frame capture, replay, score ledger, action logs,
  and recovery handles.
- Sweep broadly, classify mechanics, park opaque cases, and return when a new
  hypothesis or tool becomes available.
- Convert observations into a mechanism grammar: objects, coordinates, actions,
  animation layers, hidden state, autonomy, phase, resources, and win triggers.
- Use controlled probes and record negative evidence; "no-op" is a fact, not a
  failure.
- Once the grammar is stable, compile it into search, planning, choreography, or
  verification code.

## Supporting references

Read only when needed:

- `references/capabilities.md` for distilled Fable/Mythos capabilities.
- `references/process.md` for checklists and templates.
- `references/sources.md` for official and public-report sources.
