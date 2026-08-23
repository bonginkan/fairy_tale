# Fable Harness: long coding or migration tasks

- Use for a long coding or migration task, or a direct port however small.
  Start with repository map and invariants.
- Generate a migration plan with checkpoints, sized to the task. A long
  migration earns the full plan; a short direct port does not acquire one by
  routing here.
- Edit only scoped files.
- Validate continuously. Inside an agent-to-agent review loop the test and CI
  runs wait for the increment's sign-offs; see
  `references/cards/helix-loop-communication-harness.md`.
- Prefer lower effort or smaller scopes before expensive broad autonomy.
- Begin a port or migration with a copy command that names the source's exact
  line range, and place that copy at the destination before editing anything.
  Then edit only what the target requires to wire it in — imports, paths,
  names, types, and the required properties below. Re-typing or hand-editing
  the whole body instead is not a stricter version of the same work: it drops
  lines the copy would have carried, and nothing fails to show it.
- Port the requested behaviour plus only the target-compatibility adaptations
  that port needs. Those adaptations are required, not extras: dropping one to
  look minimal is a failed port, not a restrained one. They include any
  required property the target imposes that the source never had —
  authorization, privacy, retention, money, identity, contractual behaviour —
  which is part of porting there, not capability added on the way.
- Surface unrequested features, redesigns, and improvements noticed on the way
  separately; do not implement them as part of the port.
- Success is behavioural and contract equivalence at the requested target, not
  extra capability.

