# Helix Speedrun (RTA) Harness: elapsed time is usage

Use for every Helix increment and every agent-to-agent loop the owner has asked to finish, from the directive to the merge or the handover.

- **The value.** Elapsed time in a loop is usage, and usage is the one budget
  every agent in the team draws from. A turn spent waiting for a reviewer who
  could have been reassigned, re-verifying a head that has not changed,
  re-deriving a process that already succeeded, or posting ceremony, is usage
  taken from work nobody else can do. A route that can finish in ten minutes
  and takes three hours is wrong even though it finished. The harness measures
  the route so the next run is shorter; it does not turn a target into a
  deadline, and it never buys time from the safety floor.
- **The finish line is fixed; the route is free.** The category is `any%`
  by default: the increment reaches the owner's stated acceptance — a dev
  merge carrying the loop profile's required sign-offs, or the handover of the
  named deliverable — and nothing more. `100%` (production promotion, the full
  validation ledger) exists only when the owner names it. Within the category
  the implementer chooses any order, any batching, and any sanctioned warp;
  the owner has pre-approved the warps below in this card, so no agent asks
  for permission it already holds.
- **The clock starts at "let there be light".** Read the real time when the
  directive arrives, at each split below, and when the increment is merged or
  delivered; record what was read in the Helix run split record and validate
  it with `helix_split_check.py`. Splits: `directive_received`,
  `target_located`, `contract_closed` (when the increment touches persisted
  state), `impl_pushed`, `review_requested`, `findings_returned` per round,
  `signoffs_complete`, `validation_read`, `finished`. A split that was not
  read is `not read`, never estimated.

**Sanctioned warps.** Each names the check it skips and what still catches the
failure. A warp outside this list is not a warp until the owner adds it.

- **W1 Static first.** No test run and no CI read until the head that carries
  the required sign-offs with no blocker open; the review reads the diff, its
  semantics, and the distribution surface. Still caught by: the single
  validation on the shipping head (Helix Loop Communication card).
- **W2 One-round-complete review.** A reviewer returns the whole finding set
  in one pass, having run the Closure Check on its own review before sending.
  A later round re-reads only the changed hunks and the previously flagged
  items; it does not reopen the unchanged diff. Still caught by: the shipping
  validation, and the floor findings that are never round-limited.
- **W3 Batch fix.** The implementer answers a round with one new head that
  addresses every finding, not one head per finding. Still caught by: the
  staleness rule — every sign-off is re-collected on the new head.
- **W4 Round cap.** After the profile's round cap (default two review rounds
  per increment), a non-floor finding defaults to issue deferral instead of a
  further round; a third round needs a named cause in the split record. In a
  loop with two or more reviewers the deferral goes through the Helix blocker
  triage record and its independent concurrence. In a two-party loop the
  validator's second-reviewer concurrence cannot arise; the reviewer files the
  issue, the owner-facing readback names it, and the owner's reply is the
  concurrence. Still caught by: the floor, which is never deferrable in either
  shape, and the recorded issue.
- **W5 Bounded wait, then reassign.** Silence past the profile's soft stall
  gets one re-notification; past the hard stall the role moves to an idle
  eligible sibling, who reviews the same exact head. The owner's standing
  interchangeability rule is the authorisation; the split record names the
  transfer. Still caught by: the sign-off count, which does not drop.
- **W6 Recipe replay.** A process that succeeded before is replayed from its
  captured recipe (Token Consumption Optimizer card), not re-derived.
  Authority, permission, and production gates are never replayed as outcomes.
- **W7 Consensus merge.** Required sign-offs on the exact head plus green
  checks merge without a further owner question, through whatever path the
  repository's ruleset and the owner's standing grant allow. Still caught by:
  the safety floor, which no consensus overrides.
- **W8 Measure where it is fast.** When the same gate runs locally in minutes
  and in CI in seconds, the run reads CI once and does not wait for the local
  run. Still caught by: the gate itself, which runs either way.
- **W9 Post budget.** A handoff is the state block and its refs; detail lives
  in the artifact. No acknowledgement for passive status, no restating a
  verdict already posted, no progress report that carries no state change.
- **W10 Parallel read-only prep.** While review runs, the implementer scouts,
  drafts, and stages the next increment without writing to the shared artifact
  until the sign-offs land. The turn boundary holds for writes only.

**Banned glitches — a run that uses one is void, whatever its time.**

- Evidence claimed but not read: a check, run, or sign-off reported from a
  prediction rather than a tool result.
- A sign-off carried across a changed head, or a self sign-off.
- Skipping the one validation on the shipping head.
- Any safety-floor item: secrets or credentials, data loss, production
  deploy or rollout, authority, permission, access or guard files.
- Silencing the Closure Check or a Tier A entailed companion to save a round.
- Shrinking the scope to hit the target. Filing a non-floor finding as an
  issue under W4 is tracking, not shrinking; dropping an acceptance item is.

**Pace and attribution.**

- Default targets, until the owner sets others or recorded runs replace
  them: `any%` small increment 60 minutes, medium 180, large 360; a document
  deliverable 45. `100%` has no default and needs an owner-set target. The
  validator refuses a run that names no target source.
- An over-pace run is data, not a failure. The record attributes the excess to
  phases and causes — reviewer wait, owner wait, re-verification,
  re-derivation, round spiral, ceremony, tool latency, scope growth — with
  minutes, so the next route removes the largest sink first. A record that is
  over pace and attributes nothing does not validate.
- Sum of best: the shortest recorded split per phase for a category is the
  next run's pace, replacing the defaults once three runs exist.
- Compose with, never replace: the Helix Loop Communication card owns the
  turn-level contract and the validate-once rule, the blocker triage record
  owns deferral semantics, the Implementation contract closure record owns
  pre-closure, and the Owner-Priority card owns deadlines that carry authority.
  This card owns only the value, the warp list, and the clock.
