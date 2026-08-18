# Fuzzy-First: the model carries the work, mechanism handles the exceptions

Use when deciding whether to add a rule, gate, schema, enumeration, or checker
to something a model already does — and while reviewing anything that adds one.

The default is the model's fuzzy competence. It generalises to inputs no rule
anticipated, and most of what it does needs no scaffolding. Mechanism is for the
places where that competence has been *observed* to fail. Adding it anywhere
else replaces a path that works on everything with one that works on the cases
someone thought of.

- Start from what already works. If the fuzzy path handles a case, leave it
  fuzzy. "It is not verifiable" is not a failure; a failure is a case that came
  out wrong.
- Mechanise a demonstrated exception, not a category. Point at the case that
  broke, reproduce it, and fix at that point. A rule wide enough to cover the
  failure *and* its neighbours takes the neighbours' generality away.
- Prefer prose to code. Say it in the prompt or the card first; reach for a
  script, a schema, or a gate only when prose has been tried and the failure
  recurs. Prose degrades gracefully on unforeseen input; code fails closed on
  it, and the failure lands on cases nobody complained about.
- Enumerations are the usual mistake. A list of spellings, known-bad strings,
  extensions, or field names covers what its author imagined and silently
  misses the rest — while the fuzzy reader handled all of them. Where a list
  seems necessary, ask what the property is and whether the model can just be
  told it.
- A gate encodes a decision as a property of the artifact. Before adding one,
  check that it *is* a property: "this diff must bump the version" fails
  because releasing is a judgement, not something the diff knows. Rules that
  restate judgements fire on the wrong cases forever.
- Cost falls on the common path. A mechanism that catches a rare failure and
  taxes every ordinary run — extra steps, refusals, ceremony — is usually a
  net loss even when it works.

Reviewing an added mechanism:

- Ask whether it should exist before measuring whether it is internally sound.
  A mechanism can be correct in every detail and still be the wrong thing:
  findings against its internals are void once the premise is refused, so the
  premise comes first.
- Ask what it costs the cases that were already fine, and what evidence of
  failure prompted it. "No observed failure" is a reason not to build it.
- Do not ask for determinism where fuzziness is working. Requiring an exact
  rule, a closed vocabulary, or a machine check for a behaviour the model
  already gets right converts a working path into a brittle one.

The two failure directions, kept in view:

| Direction | Looks like | Cost |
| --- | --- | --- |
| Over-mechanised | rules, gates and enumerations around competent behaviour | breaks cases that worked; the tax is permanent |
| Under-corrected | a known, repeated failure left to the model each time | the same wrong output, repeatedly |

Neither is safe by default. The question is always whether a *specific observed
failure* justifies the specific mechanism proposed — and if it does, whether
the smallest form of it lands only on that failure.
