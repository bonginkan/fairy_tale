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
- Then classify negative space into three tiers:
  - Tier A, entailed companions: recall-first, default-loud, never silently
    dropped. Missing continuation for materially incomplete artifacts, required
    auth/validation/error paths, migrations, recovery, and core UX states live
    here.
  - Tier B, journey gaps: balanced precision/recall. Surface only when a
    concrete user, moment, evidence, and near-term consequence pass the gate.
  - Tier C, speculative neighbors: precision-first. Keep mature-product or
    best-practice analogies private unless asked.
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

