# Spiral engineering revolution record

Use this when a loop should climb rather than merely repeat. A spiral
revolution is a bounded loop iteration that raises an explicit altitude axis:
autonomy, abstraction, scope, delegation, reusable capability, or risk
burn-down. It is grounded in risk-driven spiral development and double-loop
learning: first reduce the uncertainty that blocks ascent, then decide whether
the loop's governing variables should change.

Model the revolution as a double-helix learning loop. The execution strand
carries the deliverable path: objectives, risk spike, implementation,
validation, and landing. The learning/governance strand carries the process
path: evidence, double-loop evaluation, governing-variable update, next
altitude, and stop-or-descend planning. Evidence gates pair the strands; if one
strand moves without the other, the revolution is either a flat loop or unsafe
meta drift.
Keep the strands anti-parallel in function: execution moves forward toward
delivery, while learning/governance moves backward against the premise to
refute, revise, and constrain the governing variables. Semi-conservative
handoff means the validated governance strand becomes the template for the next
effort while a new delivery strand is synthesized; unvalidated process mutation
does not replicate.

```text
loop / thread:
revolution id:
current altitude:
target altitude:
altitude axis:
execution strand:
learning / governance strand:
strand-pairing evidence:
mismatch / repair action:
validated governance template:
win condition:
highest-risk uncertainty:
risk owner:
risk spike / prototype:
risk burn-down evidence:
engineer target:
validation / review gate:
budget radius:
double-loop evaluation:
governing-variable update:
next altitude:
terminal landing condition:
descend / replan condition:
safety floor:
ledger / receipt:
```

Operating rules:

- Do not relabel ordinary repeated issue work as spiral engineering. A spiral
  revolution must name what rises: autonomy, abstraction, scope, delegation,
  reusable capability, or residual-risk reduction.
- Keep the execution strand and learning/governance strand paired. Artifact
  delivery without double-loop evaluation remains a flat loop; a
  governing-variable update without execution, risk, validation, review, and
  receipt evidence is unsafe process drift and must be blocked.
- Treat unpaired bases as mismatch signals. Unsupported claims, risk burn-down
  without evidence, missing reviewer sign-off, missing receipt, or safety-floor
  weakening must be proofread within the revolution or caught by a post-landing
  mismatch-repair sweep. If repair cannot be completed, descend or replan.
- Replicate only validated governance templates. When a spiral branches into a
  new effort, preserve the proven loop profile and synthesize the new delivery
  strand from it; do not copy speculative autonomy, scheduler, permission, or
  self-modification changes.
- Begin with objectives plus altitude. State the target altitude, win
  condition, budget radius, and stop/landing condition before starting the
  risk spike.
- Identify the highest-risk uncertainty that prevents ascent. Burn it down
  with a bounded spike, prototype, source-grounding pass, measurement, or
  validation harness before expanding scope or delegation.
- If the risk is not reduced, descend or replan. Do not increase autonomy,
  scope, external mutation, or owner-silence merely because a loop has already
  consumed budget.
- Engineer only the target that remains after the risk spike. Keep the normal
  one-implementer/two-reviewer, validation, CI, runtime-parity, and receipt
  gates.
- After landing, run double-loop evaluation. Decide whether the loop profile,
  owner mention policy, source adapters, validation gate, role assignment,
  autonomy level, or delegation boundary should change before the next
  revolution.
- Treat governing-variable updates as state-changing work. They require
  evidence, review, receipt, and install/runtime companion when they alter
  skills, plugin metadata, hooks, schedulers, or agent runtime surfaces.
- Keep the safety floor invariant. Spiral engineering does not weaken DND,
  approval, security, credential, deploy, external mutation, meeting-join,
  owner-escalation, branch/merge, or secret boundaries.
- Stop when the terminal landing condition is met. If the loop no longer
  produces compounding learning, risk reduction, or greater safe delegation,
  close the spiral instead of spinning.

Learning signals:

```text
accepted_altitude_gain:
accepted_risk_burn_down:
accepted_governing_variable_update:
accepted_terminal_landing:
descended_due_to_unburned_risk:
rejected_unsafe_autonomy_gain:
rejected_scope_expansion_without_risk_evidence:
later_confirmed_spiral_plateau:
later_confirmed_bad_governing_update:
```

