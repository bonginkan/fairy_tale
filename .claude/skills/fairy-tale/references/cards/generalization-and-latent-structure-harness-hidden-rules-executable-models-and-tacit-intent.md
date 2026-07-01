# Generalization and Latent Structure Harness: hidden rules, executable models, and tacit intent

This consolidates the former Generalization Harness and Latent Structure
Harness routes. Use it when the visible request is likely incomplete or local
facts are present but the transferable rule is still unclear: unfamiliar tools,
hidden-rule tasks, black-box environments, ambiguous specs, implicit repository
or product contracts, false analogies, unstated user intent, and repeated
benchmark misses.

- Start with the smallest checkable world model before expensive or externally
  visible action: state, transitions, invariants, public interfaces, old
  behavior, constraints, success conditions, and expected failure modes.
- Verify that model against observed transitions, existing tests, logs,
  examples, screenshots, user statements, negative evidence, or controlled
  probes. Refactor the model toward fewer rules only after it predicts the
  evidence.
- Keep this harness domain-neutral. It may support SWE-style coding, ARC-style
  mechanism discovery, legal, research, UI, spatial, and security work, but it
  must not encode benchmark answers, hidden tests, task ids, or
  rubric-specific shortcuts.
- Keep confirmed knowledge, refuted hypotheses, no-op observations, inferred
  invariants, risky assumptions, open assumptions, probes, validators, and
  validation results, actions, and promotion decisions in separate sections. Do
  not let lucky successes harden into rules until the success reason has been
  tested.
- Detect false analogies: if an unfamiliar task is being mapped to a known game,
  framework, legal form, or coding pattern, require at least two independent
  observations before acting on that analogy.
- For unstated user intent, infer conservatively from the repo, prior local
  patterns, domain norms, and explicit constraints. Mark each inference as
  `confirmed`, `likely`, `risky`, or `needs user/input evidence`.
- Ask a clarification question only when the unresolved assumption is
  irreversible, safety-relevant, cost-heavy, externally visible, or likely to
  change the user's intended outcome. Otherwise, make the smallest reversible
  choice and validate it.
- Before finalizing, run an implicit-contract sweep: adjacent files, exported
  APIs, legacy behavior, mocks/fixtures, edge cases, non-functional constraints,
  and user-facing output that the prompt did not spell out but the system
  relies on.
- Create or update a latent-structure ledger before acting when the task is
  medium/high risk or has a latent-structure trigger:
  `python3 scripts/latent_structure_harness.py init --task "<objective>" --task-family generic --trigger implicit_contract --output latent-structure-ledger.json`.
- Run the pre-action gate before expensive or externally visible action:
  `python3 scripts/latent_structure_harness.py validate --ledger latent-structure-ledger.json --stage pre-act`.
- Run the final gate before claiming completion or reusing the inferred rule:
  `python3 scripts/latent_structure_harness.py validate --ledger latent-structure-ledger.json --stage final`.
- If the gate fails, either gather more evidence, narrow the invariant scope,
  downgrade the promotion decision, or ask the user when the unresolved
  assumption is irreversible, safety-relevant, externally visible, or cost-heavy.

