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
- **Everything else becomes the next cycle, not a blocker.** Abnormal-path
  robustness, error handling, retries, load and edge behaviour, and
  precautionary security hardening are recorded as issues in the same
  repository, carried in the owner-visible readback, and worked in the next
  increment. Work continues on them; the *deploy* does not wait for them.
- **The floor does not move.** Demonstrated secret or credential exposure, data
  loss, production impact, an authority or permission boundary, a demonstrated
  reachable security defect, the increment's own required acceptance criteria,
  and any finding that breaks the verified normal path are fix-now at every
  stage. The one security exception is *hardening*: a finding of any other
  class wearing the security floor is a defect, and relabelling its basis
  precautionary does not make it deferrable. A precautionary classification
  claims only that no reachable failure sequence has been demonstrated, and any
  demonstration converts it back to fix-now.
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
