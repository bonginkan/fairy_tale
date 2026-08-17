# Multiple Directives Are One Effort

Use when the owner issues more than one instruction for the same system, or
revises instructions while an effort is running. The rule exists because a
system is an organism: directives issued together share state, ordering, and
failure modes, so solving them one at a time produces fragments nobody closes
and a branch that moves until the thread is lost.

- **Directives issued together are solved together.** Treat the owner's
  instructions as one effort and deliver them solved as one reviewable delivery:
  one pull request at one exact head, not a sequence of partial submissions.
  Picking one
  off and deferring the rest is not scoping; it is leaving the effort unfinished
  while reporting progress. Volume is not a reason to split: "too large for one
  pass", "Phase 2", "a separate PR per reviewable unit", and "the rest next
  session" are refusals to finish.
- **The directive set is read from its sources, and it changes three ways.**
  Record the message or issue references the effort answers; membership is
  read off those refs rather than recalled. A later directive may *add* to the
  set, *replace* an earlier one by narrowing or withdrawing it, or *correct
  where an earlier one is carried out* while its content stands. A later
  instruction joins the set when it adds to, replaces, or redirects the same
  owner goal — not merely because it touches the same system, which would make
  the set unbounded. Record which ref supersedes which. A set that only ever
  grows keeps solving what the owner has already withdrawn; a set that never
  records relocation discards work that was right but misplaced.
- **The working branch is fixed, and fixing it means not moving it.** An effort
  runs on one branch at owner-goal scope, not per increment, because an
  increment-scoped rule still lets the branch move between increments — the
  observed failure. Fixing is not creating: prefer the established long-lived
  working branch and do not cut a new one per effort. Choosing the branch at the
  start needs no escalation; changing or adding to it afterwards does, and lapses
  existing sign-offs as head drift would. Record the branch and the ref that
  fixed it, or no one can check afterwards whether it moved.
- **An unapproved branch change is itself an unconditional blocker.** It does not
  need a downstream symptom to qualify, and it is not weighed against delivery
  pressure: the move is the defect. Clearing it requires producing the owner's
  approval *as evidence* — a citable ref, not a recollection or an inference from
  silence. Absent that ref, the remedy is to return to the *recorded* original
  branch and consolidate the work onto one, before any further review — which is
  why the branch and the ref that fixed it are recorded at the start: with no
  such record there is no original to return to and the rule is unenforceable.
  Record which remedy was taken. A review conducted across a branch that moved
  without approval is reviewing something no one authorised.
- **Deferred work stays on the effort's branch.** Sending a finding to the next
  cycle decides *when* it is done, not *where*: the next increment runs on the
  same fixed branch. A deferral is never a reason to move or fork the branch.
- **Every required reviewer reviews the whole delivery at once.** Not one
  designated reader: each required reviewer independently reads the full diff,
  every directive in the set, and the checks at that exact head, and returns all
  findings in one pass. Serial partial review manufactures the fragmentation this
  card forbids, and it prevents convergence: if findings arrive in installments,
  no round ever produces zero new fix-now findings.
- **Revisions stay whole and stay on the branch.** A revision answering findings
  addresses all outstanding findings together and returns on the same branch.
  One blocker per revision is the splitting rule wearing a review costume.
- **This does not touch finding disposition.** A reviewer sending a non-floor,
  out-of-scope finding to a next-cycle issue, and the implementer accepting it,
  remains correct — see `references/cards/edison-ship-gate.md`. This card governs
  how the owner's directives are delivered, not how review findings are
  dispositioned.
- **What is not splitting.** External dependency — another party's answer, an
  approval, data that does not exist yet — is a dependency: solve everything
  solvable and record the remainder by name, with whose answer it waits on. A
  directive that cannot be carried out without crossing the floor is not a
  dependency either: it follows the floor's own disposition, and declining it
  there is not a failure to finish. Separate ownership is also not splitting:
  when parts of the work live in repositories or configurations only their own
  owners may edit, they are structurally separate efforts, sequenced so no window
  exists in which the rule is recorded nowhere. Splitting that way does not end
  the umbrella goal: it stays open until every named child closes or the owner
  narrows it, so closing the umbrella on the first child's merge reports a
  completion that has not happened. "Later" is not a record.
