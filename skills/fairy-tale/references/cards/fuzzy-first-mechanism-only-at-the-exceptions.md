# Fuzzy-First: build on the model's judgement, correct at the failures

Use when building or changing a product feature that calls an LLM, and when
reviewing one. The same test applies to this harness's own rules; that is the
last section.

The model's fuzzy competence is the implementation of the *behaviour*. It
generalises to phrasings and situations no rule anticipated, and that is what it
is for. This card is about code that constrains, pre-empts, or second-guesses
that behaviour — not about the feature's plumbing, which is ordinary software and
written as such: transport, storage, retries, rendering, telemetry, tests.

Code that stands between the user and the model's judgement is for two things:
properties that must hold whatever the model does — see *What stays in code
regardless*, which needs no failure to justify it — and points where the model
has been *observed* to fail, reproduced. Put there for any other reason, it
replaces something that handles everything with something that handles what its
author thought of.

- Leave the working path alone. "The model's answer is not verifiable" is not
  a failure; a wrong answer is. (Required properties are the exception throughout:
  they are judged against the property, not against how the answer reads — and
  where the property is itself about the output, such as a redaction rule or a
  schema a caller depends on, it is checked on the output every time.) Wrapping a working
  behaviour in rules to make it legible usually costs more cases than it
  saves.
- Correct the failure mode the evidence supports, at its narrowest. Not the
  one literal input — a fix that only recognises the exact sentence that broke
  will miss the next phrasing of the same fault — and not the category it
  belongs to either. Where the evidence shows a property is violated, fix the
  property; the test is that the fix lands on what was shown to fail and
  nothing further.
- Prompt before code. Try instructions, examples, and the registered content
  first; add a branch, a classifier, or a validator only when that has been
  tried and the failure recurs — required properties excepted, as above.
  Neither form gives a guarantee on input nobody foresaw: guidance is read by
  something that generalises, and code applies a rule that does not describe
  the case. What differs is the failure they produce — a judgement that may be
  off, against a branch that refuses, passes silently, or does something
  arbitrary — and code makes that choice at write time, for cases its author
  never saw. Measured here: a gate that refused changes it should have allowed
  (#120), and gates that passed what they were written to stop (#117, #120).
- Do not put an enumeration in front of the model. Keyword lists, intent tables,
  hand-written synonym sets, regexes over user speech: each covers what its
  author imagined while the model was already handling the rest. If a list feels
  necessary, ask what property it stands for and whether the model can simply be
  told it.
- Do not let a hard classifier overrule the model's reading. A confidence
  threshold, a category gate, or a "cannot determine" branch in front of a
  model that would have answered turns a good answer into a refusal — and
  refusals are what users report.
- Weigh the cost on the common path. A check that catches a rare failure and
  taxes every ordinary request — an extra hop, a clarifying question, a
  refusal — is usually a net loss even when it works.

## Keep the conversation

A model holds what was said. A feature that issues one stateless call per turn
throws that away and makes the next prompt re-supply it, so the failures are the
ones the prompt author did not anticipate: a decision from two turns ago lost, a
question re-asked, an answer contradicting an earlier one. Fragmenting a
conversation is not neutral — it manufactures those.

- Carry the dialogue. A turn that follows from what was just said should reach
  the model with what was just said, including the correction the user made and
  the reason the previous attempt missed.
- Storing the turns and replaying them, or holding a provider-side conversation
  handle, is how the dialogue reaches the model across a stateless API. That is
  transport, and it keeps what was said.
- Compressing the dialogue into a summary, a slot-filled record, or a narrow
  schema is a different act: it buys separation and costs what the conversation
  carried implicitly, including the parts nobody thought to model. Take that
  trade deliberately, and keep the turns themselves where you can.
- Keep a step stateless when carrying the context would defeat what the step is
  for, or would move context across a boundary it must not cross — another
  tenant, another channel, another customer's data. That is a property to check,
  not a list to match against.
- When something breaks across a boundary, ask first whether the boundary had to
  be there. Much of what looks like a memory failure is a conversation someone
  cut in half.

## What stays in code regardless

Authorization and access boundaries, privacy and retention rules, money,
identity, and anything with a contractual or legal definition. These are not
cases where the model is weak — they are decisions that must hold independently
of any inference, and instructing a model is not an implementation of them.
Fuzzy-first governs behaviour, never the guarantees underneath it: these are
required properties, so they are implemented before any failure is observed, and
an existing safety, authority, or privacy floor is never relaxed on the grounds
that nothing has gone wrong yet.

## Reviewing

- Ask whether the mechanism should exist before measuring whether it is
  internally sound. A mechanism can be correct in every detail and still be
  the wrong thing: findings against its internals are void once the premise is
  refused, so the premise comes first.
- Ask what it costs the requests that were already fine, and what observed
  failure prompted it. "No failure has been seen" is a reason not to build it
  — except for the required properties above, which are implemented without
  waiting for one and are never removed on that argument.
- Do not ask for determinism where fuzziness is working. Requiring an exact
  rule, a closed vocabulary, or a machine check for behaviour the model
  already gets right converts a working path into a brittle one.
- Say so when a failure has repeated and nothing was done. The question in
  that direction is what the smallest correction at the failure point would be
  — usually a sentence of instruction or a registered example, not a system to
  prevent the class. Leaving a known recurring failure to be rediscovered each
  time is a finding, and a review that refuses an unnecessary gate must still
  ask for a necessary correction.
- Review itself is where separation is the point: read the artifact without
  inheriting the implementer's thread, and treat sharing that thread as the
  thing that needs a reason.

## The two directions

| Direction | Looks like | Cost |
| --- | --- | --- |
| Over-mechanised | rules, gates, enumerations and stateless hops around competent behaviour | breaks cases that worked; the tax is permanent |
| Under-corrected | a known, repeated failure left to the model each time | the same wrong output, repeatedly |

Neither is safe by default. For a required property the question does not arise —
it is implemented either way. Everywhere else, the question is whether a
*specific observed failure* justifies the specific mechanism proposed, and
whether the smallest form of it lands only on that failure.

## The same test on this harness

Rules, gates, schemas and checkers added to the agents' own process face the same
question, plus one of their own: a gate has to encode a property of the artifact,
not a judgement. "This diff must bump the version" fails because releasing is a
decision, not something a diff knows — rules that restate judgements fire on the
wrong cases forever.
