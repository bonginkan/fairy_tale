# Edison Ship Gate: dev-deploy threshold

Use when an increment could reach a real non-production surface that humans can
exercise. The gate exists because a loop that converges only on a perfect
increment does not converge: every round discovers more entailed companions,
and the artifact never reaches the one reviewer who finds the failures no
harness enumerates — a human using it.

- **Fires on** any of: the ship target is a dev / staging / preview / internal
  environment; the work is early development or a prototype whose value is
  seeing it run; or the owner directs a ship. It does **not** fire for a
  production promotion, a release to real users, or a shared surface carrying
  real data.
- **Earns the relaxation with a verified normal path, not with a promise.**
  Record the increment's happy path as a concrete executed check with an
  evidence ref. An unverified or hand-waved happy path leaves the ordinary
  production thresholds in force — the relaxation is bought with evidence.
- **The claim's witness is not written by its author.** What the increment
  claims to close is read from sources the implementer cannot rewrite mid-review
  — the verified owner directive, the linked issue's acceptance, and contracts
  and required tests already present in the merge base. Merge-base contracts are
  fixed by commit; a directive or an issue body is not, so pin those by content
  hash with the capture time and verify the recorded edit count before relying on
  them. The pull request body is
  a copy, not the source. Narrowing the claim after review begins is a change of
  claim: existing sign-offs lapse, as on head drift. A test added by this
  increment is not a witness for it.
- **The evidence needs a witness who is not the beneficiary.** The stage basis
  and the normal-path check are locators the implementer writes, so a
  registered reviewer other than the implementer attests to having confirmed
  that the basis names a real authorized non-production target or directive
  and that the check ran on this exact head. Without that attestation the
  relaxation is not earned, whatever the record claims.
- **Readiness, not authority.** A ship decision states that the increment is
  ready for the recorded stage. It grants no deploy, merge, or access
  authority, and it overrides neither the repository's own gates nor the
  owner's standing policy: the `hold` rejection below rejects *diligence
  theatre*, never someone else's authority to withhold a deploy.
- **Ship rule.** With the normal path verified and no retained fix-now finding,
  the increment ships to the dev target. *Holding a green increment is a
  finding, not diligence.* The machine gate rejects `hold` in that state.
  "No retained fix-now" means none outstanding, not none newly raised this
  round: a round that discovers nothing new while earlier fix-now findings remain
  open does not ship.
- **Everything else becomes the next cycle, not a blocker.** Abnormal-path
  robustness, error handling, retries, load and edge behaviour, and
  precautionary security hardening are recorded as issues in the same
  repository, carried in the owner-visible readback, and worked in the next
  increment on the same working branch as the effort that deferred them —
  deferral moves work in time, never onto another branch. Work continues on
  them; the *deploy* does not wait for them. This clause disposes of technical
  findings about the increment's behaviour; it does not reach the invariants
  governing how the work is carried out, which are not findings and are not
  deferrable by it.
- **The floor does not move.** Demonstrated secret or credential exposure, data
  loss, production impact, an authority or permission boundary, a demonstrated
  reachable security defect, the increment's own required acceptance criteria,
  and any finding that breaks the verified normal path are fix-now at every
  stage. The one security exception is *hardening*: a finding of any other
  class wearing the security floor is a defect, and relabelling its basis
  precautionary does not make it deferrable. A precautionary classification
  claims only that no reachable failure sequence has been demonstrated, and any
  demonstration converts it back to fix-now.
- **Breaking the normal path has conditions, and evidence is not one of them.**
  A normal-path break is floor when all of these hold: the behaviour is recorded
  in a source the increment's author did not write; it is observable to callers
  or users rather than internal; the increment does not claim to change it; and
  it concretely fails on this exact head with a named failure sequence and a
  reachable locator. Execution evidence and an independent attestation are the
  standard for *sustaining* the block, not for establishing it: with the
  substance shown but evidence outstanding, hold and escalate immediately —
  never ship because the paperwork lagged, and never demote because it did. If
  no attester is available, escalate to the owner rather than downgrading.
- **When reviewers split on floor membership, refutation is asymmetric.** The
  side asserting the floor shows the canonical locator, the failure sequence,
  and the exact-head evidence. The objecting side is not required to produce the
  same three — that is not how absence is shown — but must refute one of them on
  evidence. One objection, one rebuttal; a sustained refutation defeats the floor
  claim, an unrefuted assertion carries it, and a split with grounds on both
  sides escalates to the owner. Neither majority nor precedence decides it.
- **Deferral stays a recorded transaction.** Same-repository issue, one
  registered reviewer concurring who is not the finding reviewer, an
  owner-visible report, and the exact final readback — unchanged from ordinary
  triage. Deferring on the *floor* costs more: every registered reviewer
  concurs, because the precautionary claim's only witness is the panel's
  reading of the failure sequence. "Issue it and move" is a promotion of the
  *threshold*, never a weakening of the *record*.
- **Promotion re-blocks.** Every dev-stage deferral re-enters as a blocking
  candidate at production, under the unrelaxed thresholds. Dev debt is
  deferred, never discharged, so shipping fast never silently ships weak.
- **Hand the failure surface to humans.** A dev deploy is only worth its
  lowered threshold if the humans who can hit it know it landed: state the
  target, what changed, what was deliberately deferred, and where feedback
  goes. Feedback that arrives after the ship decision belongs to the next
  increment; it does not reopen the shipped one unless it lands on the floor.
- **Recall is not suppressed — disposition is.** The closure check and the
  Tier A negative-space pass still run and still surface entailed companions.
  This gate changes what a surfaced companion *does*: at dev stage its default
  disposition is a next-cycle issue rather than a retained blocker. Surfacing
  fewer findings to ship faster is the failure mode, not the method.
- **Machine gate.** Record the decision with the Helix blocker triage record
  and validate it (`./fairy blocker validate --record <record.json>`). The
  record carries the ship stage, its basis, the happy-path evidence, and the
  go/hold decision, so the relaxation is auditable rather than asserted.
