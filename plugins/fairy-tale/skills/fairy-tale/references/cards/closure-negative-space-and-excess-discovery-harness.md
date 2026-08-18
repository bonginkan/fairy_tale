# Closure, Negative-Space, and Excess Discovery Harness

- Use this during review, requirements discovery, product/UX work,
  underspecified requests, clipped or partial artifacts, numbered item sets,
  multi-image/file tasks, refactor/deprecation review, and any task where the
  visible frame may be incomplete, bloated, stale, or adversarially shaped.
- **Do NOT use this harness for a workflow-less, simple divergent-generation
  request** ("propose N options / patterns / ideas", "brainstorm", "name
  candidates", "generate variations") that carries no review, decision, or
  workflow component — produce the options directly. A numbered set that is the
  *requested output of a generation* ("give me 5 X") is not the "numbered item
  set" this harness audits; the harness audits numbered sets that are *given to
  you as possibly-incomplete input*. The harness re-engages for a generative
  request only on an explicit "review / critique / audit / 抜け漏れ / 批判的に".
- First run a non-suppressible closure check: stated or observed `N` is not
  automatically verified exhaustive `N`. Do not skip the audit because a count
  was stated, numbered, implied, or apparently known.
- **In a removal or simplification effort, the negative-space half works
  against the goal.** When the task is to cut features back — too much has
  accumulated, the surface is to get smaller — surfacing entailed companions
  argues for adding, and a harness that answers "what is missing" every time
  turns a subtraction into an expansion. Run the excess pass as the main pass,
  and let the closure check ask the subtraction question instead: what does
  removing this break, who still depends on it, and which required property
  (authorization, privacy, retention, contractual behaviour) would lose its
  implementation. Tier A in this mode names what a removal takes with it, not
  what an addition owes. Companion surfacing returns when the effort turns back
  to adding.
- Mixed or unclear, keep surfacing. An effort that removes and adds in the same
  increment — replacing a mechanism with a smaller one, or dropping one gate
  while adding a card — is not in removal mode, and neither is an effort whose
  mode has not been established. This bullet is the only route by which Tier A
  companions can go unspoken, so an ambiguous reading of it produces exactly the
  false negative the tier exists to prevent: when in doubt the recall guard wins
  and companions are surfaced.

- Then classify negative space into three tiers:
  - Tier A, entailed companions: recall-first, default-loud, never silently
    dropped. Missing continuation for materially incomplete artifacts, required
    auth/validation/error paths, migrations, recovery, and core UX states live
    here.
  - Tier B, journey gaps: balanced precision/recall. Surface only when a
    concrete user, moment, evidence, and near-term consequence pass the gate.
  - Tier C, speculative neighbors: precision-first. Keep mature-product or
    best-practice analogies private unless asked.
  - In removal mode the tiers keep their names and change what they are about:
    Tier A is what a removal takes with it, and Tier B/C additive surfacing —
    journey gaps to fill, neighbouring features to add — is off, because it
    answers a question the effort is not asking. What Tier B/C still carry is
    the subtraction form: a user left mid-journey by the cut, a neighbour that
    breaks when this goes.
- Noise guards apply to Tier B/C exploration only: bounded one-pass output,
  ranked 1-3 findings/questions or silence, no "also you could" lists, and no
  automatic implementation scope expansion.
- Recall guards protect Tier A and the closure check: if Tier A exists,
  silence is not valid. Silence becomes a true negative only if later evidence
  does not reveal a missed gap.
- Run the paired Excess / Redundancy / Legacy-Surface pass when the review asks
  whether something should be removed, deprecated, consolidated, or left alone.
  It classifies findings as `remove-now`, `deprecate-with-migration`,
  `consolidate-later`, or `keep-intentionally`. Treat false-positive deletion
  as the worst failure mode: compatibility, migration, tests, docs, release
  notes, and data/search evidence must precede any removal.
- Track learning signals separately: `accepted_now`, `valuable_but_deferred`,
  `converted_to_issue`, `already_known`, `rejected_scope_creep`,
  `rejected_wrong_user`, `rejected_no_evidence`,
  `later_confirmed_false_negative`, and silence quality.
- Use the Closure Check, Negative-Space Discovery, Excess / Redundancy /
  Legacy-Surface Discovery, contradiction, and problem-construction cards in
  `references/process.md`.

