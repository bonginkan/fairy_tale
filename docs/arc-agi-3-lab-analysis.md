# ARC-AGI-3-Lab Process Analysis

Date: 2026-06-14 JST

## Scope

This note summarizes the observed process from Jun's local
`ARC-AGI-3-Lab` run. Source files were read-only because that repo currently
has unrelated working-tree changes.

Primary local sources:

- `/Users/thepioneer/Documents/GitHub/ARC-AGI-3-Lab/MISA_PROGRESS.md`
- `/Users/thepioneer/Documents/GitHub/ARC-AGI-3-Lab/recordings/levels.json`
- `/Users/thepioneer/Documents/GitHub/ARC-AGI-3-Lab/misa_bridge.py`
- `/Users/thepioneer/Documents/GitHub/ARC-AGI-3-Lab/misa_replay.py`
- `/Users/thepioneer/Documents/GitHub/ARC-AGI-3-Lab/misa_official_score.py`

## Observed result

`recordings/levels.json` records 24 cleared levels across the current local
ledger. This is a local progress ledger, not a freshly submitted official
scorecard verification.

## Distinctive process

The run did not look like generic brute force. It looked like a compact
scientific loop:

1. Build observability before solving.
2. Sweep all available environments to classify mechanics.
3. Use micro-probes to measure action effects.
4. Inspect animation layers, not only final frames.
5. Convert repeated observations into a mechanism grammar.
6. Compile stable grammars into search or choreography.
7. Preserve replay and recovery handles for long sessions.

## Key mechanisms extracted

### Instrument first

`misa_bridge.py` kept live environments open behind a small HTTP API and added
frame capture, recording, score tracking, and keepalive/recovery logic.
`misa_replay.py` made solved prefixes replayable. This converted a fragile
interactive game session into a reproducible lab.

### Treat no-op as evidence

Many games were parked after systematic no-op discovery. This avoided spending
the whole budget on an opaque target and made later breakthroughs easier because
negative hypotheses were already recorded.

### Inspect all layers

The su15 investigation shows the core lesson: final frames can hide the
mechanism. Reading all frame layers revealed click-driven animation behavior
that looked like no response when only the last layer was inspected.

### Mechanism grammar before search

Search was useful only after rules stabilized. `tu93` became solvable when
enemy phase, pellet-gate rules, and safe timing were explicit enough to compile
into joint-state BFS. `g50t` advanced after fluid, squeeze, one-way valve,
dice-freeze, and mode-switch rules were identified. `wa30` needed choreography
with autonomous helpers. `re86` reduced to geometric placement constraints.

### Recovery is part of reasoning

Long-running problem solving depends on recovery handles. The session included
scorecard/session loss, replay recovery, a persistent level ledger, and
keepalive corrections. These are not operational extras; they are what make
long-horizon cognition possible without losing state.

## Reusable harness

This becomes the `Mechanism Grammar Harness`:

```text
instrument -> sweep -> segment -> probe -> inspect layers -> record no-ops
-> infer grammar -> compile solver -> replay/verify -> update memory
```

Use it for ARC-style games, unfamiliar tools, simulations, visual puzzles, and
other systems where rules must be inferred from observable behavior.
