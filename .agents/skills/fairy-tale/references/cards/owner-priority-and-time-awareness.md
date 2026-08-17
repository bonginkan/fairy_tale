# Owner-Priority Review and Time-Awareness

Use in any review with more than one reviewer, and whenever the owner has
stated what to prioritise or when work is due. The gate exists because a review
that ranks findings only by technical severity converges on what reviewers find
interesting rather than on what the owner asked for, and because a deadline read
from feeling rather than from a clock produces a plan nobody can check.

- **The second reviewer disposes by owner priority.** In addition to technical
  verification, one registered reviewer assigns each finding a disposition: next
  cycle, separate issue, or no-action. Technical severity does not outrank the
  owner's stated priority.
- **Priority governs order, never existence.** Every deferred finding becomes a
  recorded issue before merge, with its URL on the pull request; no-action
  carries a stated reason. A disposition without a record is not a disposition.
  Priority ranking must never delete a finding.
- **The two axes do not overlap.** Floor membership and failed-claim findings
  are technical determinations; the priority reviewer can neither downgrade them
  nor promote a non-floor finding into a blocker. `block now` is a readback of
  the technical determination, not a priority disposition.
- **Record who held the role and what it was exercised against.** Each handoff
  carries the priority reviewer's identity and the verified owner directive ref
  the priorities were read from. A priority disposition whose directive cannot be
  named afterwards is indistinguishable from a preference.
- **No directive, no priority authority.** When no owner directive is in force,
  the priority role does not arise and review proceeds on technical judgement
  alone. An empty priority must never be used to justify shipping.
- **Observe the clock; do not feel it.** Read the real time at the start of each
  round and at each disposition, and record what was read. Remaining time is
  computed from those readings. If the clock or the deadline cannot be read, the
  time-awareness authority does not arise.
- **A deadline needs a source.** A verified owner instruction, an issue
  milestone, or a scheduled demonstration or handover. Without a recorded
  deadline there is no time-awareness authority; otherwise a reviewer can invent
  a deadline and ship against it.
- **Pre-register the minimum coherent set, by name.** At the start of the
  deadline window, list the named items that must pass for the delivery to be
  coherent. Deciding at the end makes whatever passed the definition, so "it came
  together" becomes unfalsifiable. Time reorders what is attempted; it never
  redefines completion. Shrinking the set is an owner escalation, not a
  reviewer's discretion. Counts are not names: "8 of 10" is not evidence when the
  remaining 2 are the substance.
- **A deadline never lowers the floor.** Time has no bearing on floor membership
  or on whether a claim holds. If the work will not fit, re-cut the increment to
  something that fits, or escalate — never trim the floor to make the date.
- **Emit a forecast each round, and settle it afterwards.** One line: time
  remaining, which pre-registered items have passed and which have not, whether
  the remainder fits at the current rate, and what is taken next. Reconcile the
  forecast against the outcome after the deadline; a forecast never settled
  improves no future estimate.
