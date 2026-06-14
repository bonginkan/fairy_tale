# OpenMythos External Adapter

Date: 2026-06-14 JST

## Scope

`bonginkan/OpenMythos` is a fork of `kyegomez/OpenMythos`, an MIT-licensed
public theoretical reconstruction of a Mythos-like recurrent-depth transformer.
Fairy Tale treats it as an external substrate, not as vendored source and not
as evidence of Anthropic's internal architecture.

Fork:

- https://github.com/bonginkan/OpenMythos

Upstream:

- https://github.com/kyegomez/OpenMythos

Local clone hint:

- `../OpenMythos`

## Adapter strategy

The adapter lives in `adapters/openmythos.adapter.json` and follows
`schemas/fairy-tale-adapter.schema.json`.

Adapter validation and future orchestration are Rust-based in
`crates/fairy-adapter-runner`. OpenMythos itself is currently a Python/PyTorch
project, so the boundary is:

- Rust owns adapter discovery, validation, evidence orchestration, and future
  process runners.
- OpenMythos remains an external runtime invoked only through a pinned adapter
  contract.

The boundary is deliberate:

1. Fairy Tale owns orchestration, evidence capture, validation gates, and
   prompt/process patterns.
2. OpenMythos owns the external architecture experiment: `OpenMythos`,
   `MythosConfig`, recurrent loop depth, MLA/GQA attention, and MoE internals.
3. Any result is recorded as an external reconstruction probe, not a claim that
   the real Fable/Mythos architecture has been reproduced.

## Reproduction loop

Use this loop when exploring OpenMythos from Fairy Tale:

```text
select adapter -> record fork commit -> choose small config -> run shape probe
-> vary loop depth / attention mode -> compare baseline -> record artifacts
-> update evidence map
```

Validate adapter manifests with:

```bash
cargo run -p fairy-adapter-runner -- validate adapters/openmythos.adapter.json
```

## Evidence requirements

Minimum evidence for a claim:

- adapter manifest revision,
- OpenMythos fork commit,
- exact `MythosConfig`,
- dependency/runtime notes,
- input task or prompt bundle,
- output artifact,
- baseline comparison if a superiority claim is made.

## Safety and claim boundaries

Allowed:

- architectural probes,
- small-scale inference tests,
- loop-depth comparisons,
- attention implementation comparisons,
- process-level comparison against Fairy Tale harnesses.

Not allowed:

- claiming access to Anthropic model internals,
- claiming equivalence to Claude Mythos/Fable,
- bypassing Fable/Mythos access restrictions,
- training large models without an explicit compute and cost budget.

## Current OpenMythos surface

Observed public API:

- `OpenMythos`
- `MythosConfig`
- `mythos_1b`, `mythos_3b`, `mythos_10b`, `mythos_50b`,
  `mythos_100b`, `mythos_500b`, `mythos_1t`
- `MythosTokenizer`

Core hypothesis:

- Prelude transformer layers run once.
- A recurrent block runs for configurable loop depth.
- Coda transformer layers run once.
- Attention can use MLA or GQA.
- The recurrent block uses MoE and input reinjection.
