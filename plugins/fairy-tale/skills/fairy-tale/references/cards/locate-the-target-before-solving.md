# Locate the Target Before Solving

Use at the start of any directive-driven effort, before investigating content.
The rule exists because a wrong target is not corrected by working carefully
inside it: the frame decides how every later observation is read, so depth
entrenches the error rather than exposing it.

- **The subject names the target; the verb only names the action.** A familiar
  verb — "finish it", "update your config", "roll it out" — maps to a workflow
  already known, and that workflow then quietly decides what the task was about.
  Read the subject first: the system, skill, or component the directive names.
  When subject and verb point at different places, the subject governs.
- **Authority and corroboration are different, and ambient signals are the
  second kind.** The verified owner directive and the canonical ownership of
  record decide the target. The channel a request arrived in, a thread or issue
  title, and surrounding vocabulary are corroboration: they are cheap, they are
  usually right, and they cost nothing to read before building any provenance
  apparatus — but they are renamed, reused, and set by third parties, so they
  are not unforgeable and they do not settle a question against a directive.
  Read them early; do not promote them.
- **When a directive names a target explicitly, that naming governs.** The
  subject-over-verb reading is a heuristic for when nothing is named, not a rule
  that outranks an explicit path, repository, or component — wherever in the
  sentence it appears. Where directive and ambient signal disagree, or two
  directives point apart, do not pick the stronger-feeling one: stop and ask the
  owner. Failing closed costs a message; proceeding on a contested target costs
  the effort.
- **Record the target as a structure, not a sentence.** Repository, path, layer,
  canonical owner, the directive refs it was resolved from, the propagation path
  to any mirrored copies, and the duplication policy that governs them — plus,
  for any mutable source relied on, its content hash and capture time. A target
  held only in the implementer's head cannot be checked by anyone, including the
  implementer later; a target recorded as prose cannot be checked mechanically.
- **An artifact stating where things belong is checked against itself.** If the
  work declares a canonical location, a duplication rule, or an ownership
  boundary, apply that declaration to the artifact carrying it before submitting.
  A document that violates its own locating rule is the characteristic form of
  this failure, and it is invisible from inside the content.
- **Reviewers resolve the target independently, before reading content.** The
  edit target an artifact declares is the implementer's claim, not metadata, so
  the reviewer resolves the target from the owner directive and the ambient
  signals and compares. On a mismatch, stop without reading the content: that
  mismatch is the finding. Record the directive refs used to resolve it. The
  declared target is the first element of the claim envelope, witnessed by the
  directive rather than by the artifact.
- **A new or corrected directive re-opens the target of work already delivered.**
  Sign-off settles the artifact, not the frame it was built in, and neither does
  merging, propagation, or installation. When a directive is added or corrected,
  re-resolve the target for the whole set — including increments already
  approved, already applied, and already copied onward — because reach is not
  correctness: work can be live in several places and still be in the wrong one.
  Otherwise the earliest wrong placement is the one nobody revisits, and every
  later round inherits it as settled.
- **When implementer and reviewer resolve different targets, neither wins by
  assertion.** Each states the directive refs and ambient signals their
  resolution rests on. A resolution answered by evidence — a signal misread, a
  canonical home shown elsewhere — is defeated; an unanswered one carries. If
  both are grounded, escalate to the owner rather than proceeding, because
  continuing on a contested target is how one wrong frame becomes the whole
  effort.
- **A reviewer joining mid-effort does not inherit the frame.** An inherited
  frame is harder to doubt than one you built, because it arrives already
  endorsed. Joining late is a reason to resolve the target first, not a reason
  to accept the standing one.
- **Investigation is not verification of the frame.** Searching, measuring, and
  citing primary sources all operate inside the assumed target. Treat "what is
  this about, and where does the change belong" as a claim requiring evidence,
  exactly like any other claim.
