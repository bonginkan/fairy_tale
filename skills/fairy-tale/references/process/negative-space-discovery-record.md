# Negative-space discovery record

Use this during review, product/UX work, requirements discovery,
underspecified implementation, and "is this complete?" checkpoints. It is a
bounded divergence pass before convergence, not permission to expand scope.

```text
task / artifact:
trigger:
do_not_run reason, if any:

Tier A entailed companions:
  - missing companion:
    evidence:
    why entailed, not taste:
    risk if absent:
    surface form:

Tier B journey gaps:
  - candidate:
    affected user:
    user moment:
    near-term consequence:
    evidence:
    validation probe:
    refutation / discard result:
    surface form:

Tier C speculative neighbors:
  - private candidate:
    why private:

ranked surface output 1-3:
silence decision:
later learning signal:
```

Tier policy:

- Tier A = recall-first completeness. Default loud and never silently dropped.
  `do_not_run`, back-off, discard, scoped-task mode, and silence-as-valid do not
  suppress Tier A. In incident or explicit-scope work, surface Tier A as a
  critical companion finding instead of automatically expanding implementation.
- Tier B = gated discovery. Surface only when there is a named user, moment,
  evidence, and near-term consequence.
- Tier C = private log. Mature-product or best-practice analogies are silent by
  default unless the user asks for broader ideation.

Task-type gate (apply before the noise/recall guards):

- The closure check and divergence/negative-space pass apply to review,
  requirements/design, architecture decisions, refactor/migration/deprecation,
  e2e, security, legal, and stateful create/update/delete or workflow-gated
  tasks. For a **workflow-less simple divergent-generation request** ("propose N
  options/patterns/ideas", "brainstorm", "name candidates", "generate
  variations") they do NOT run at all — produce the requested output directly,
  and Tier-A/closure protection below does not apply (there is nothing to
  protect because the pass never ran). This gate is overridden — the pass and
  its guards re-engage — when the user explicitly asks to review, critique,
  audit, or check for gaps ("批判的に見て", "抜け漏れ確認して", "レビューして"),
  or for any mixed request that includes a review/decision step.

Noise guard:

- Do not run the divergence pass for purely mechanical deterministic tasks,
  explicit non-goals, fully enumerated requirements, or repeated rejected
  suggestions, except that Tier A and closure-check findings remain protected.
- Discard candidates that are vibes-only, intentional absence/MVP/non-goal,
  duplicate, already covered by issue/TODO/roadmap, require unapproved scope
  expansion, fail Dialectic Refutation Gate, or are Tier C.
- Output ranked 1-3 findings/questions or silence. No "also you could" lists.
  No recursive divergence.

Recall guard:

- If Tier A exists, silence is not valid.
- Silence is a true negative only if later evidence does not reveal a missed
  gap.
- Tighten Tier B gates when `rejected_scope_creep`, `rejected_wrong_user`, or
  `rejected_no_evidence` rises. Loosen Tier B gates or add a new Tier A pattern
  when `later_confirmed_false_negative` or post-silence gaps rise.

Common Tier A examples:

```text
SWE:
  endpoint -> authz / input validation / error path
  create or state change -> edit/delete/undo/recovery as applicable
  schema change -> migration / backfill
  new behavior -> focused tests/docs when local convention requires
  user-facing state change -> observability / audit / error path

UX/product:
  destructive action -> confirmation + undo/recovery + irreversible-result copy
  async operation -> progress/queued/failure state + retry/idempotency
  empty surface -> empty state + next action
  permissioned surface -> disabled/hidden/denied rule + reason copy
  form/input -> validation + preserve input + actionable error
  setting/toggle -> current state + apply feedback + side-effect disclosure
  import/export -> format limits + partial failure + retry/re-download
  collaboration/audit -> actor + timestamp + visibility/conflict behavior
```

Precision/taste learning signals:

```text
accepted_now:
valuable_but_deferred:
converted_to_issue:
already_known:
rejected_scope_creep:
rejected_wrong_user:
rejected_no_evidence:
later_confirmed_false_negative:
silence_true_negative:
novelty:
usefulness:
reviewer_agreement_on_user_moment:
```

