# Loop Engineering and Job Automation Harness

- Use this when the task asks agents to keep running across turns,
  deliberately raise autonomy or abstraction through spiral engineering,
  periodically ingest external channels, operate a repo/project channel, or
  automate email, Drive, calendar, meeting, or other job workflows.
- Treat the loop as an operating system, not an infinite retry: observe sources,
  normalize intake, triage, plan, act, validate, report, learn, and stop or
  escalate when a gate fails.
- Treat spiral engineering as risk-driven, double-helix elevation over the
  loop: the execution strand declares an altitude target and burns down the
  highest uncertainty before expansion, while the learning strand records
  double-loop evaluation before raising autonomy, scope, abstraction, or
  delegation.
- Treat evolutionary spiral operators as bounded mutation on top of a spiral:
  every variant declares a mutation budget (the safety floor is never
  changeable), is accepted only by evidence-driven selection over a baseline,
  and is inherited only when validated; record it against the evolution-variant
  ledger and validate with `scripts/evolution_variant_check.py`. Random mutation
  is never permission to self-modify production process.
- Before autonomous operation, create a loop profile with repo, project
  channel/thread, owner mention policy, do-not-disturb policy, spiral altitude
  policy, cadence, source adapters, allowed actions, approval boundaries, run
  ledger, secrets policy, reviewer roles, cross-channel session isolation,
  auto-resume watchdog policy, and rollback/stop conditions.
- Keep the main agent loop simple and put reliability in the harness:
  deterministic schedulers/watchers, scheduled wake actuators for silent-loop
  watchdogs, dedupe keys, provenance, receipts, validation checks, rate
  limits, idempotency, and explicit human checkpoints.
- For engineering loops, one run should create or reuse a visible project
  thread, mention the owner when the run starts or escalates, and keep
  GitHub/repo artifacts linked to the thread.
- For session owners that coordinate multiple loops across channels, keep an
  active-loop queue, run stale-loop sweeps before focusing on one loop, and
  keep each thread's unresolved context isolated from other loop threads. If an
  active loop goes silent past its explicit auto-resume threshold, restore
  motion in that loop's own thread with a bounded checkpoint and the required
  local agent mention; do not bypass DND, parked, approval-blocked, or closed
  states.
- For job automation, default to draft/propose mode. Email sending, Drive
  mutation, calendar/meeting actions, external posts, and credential or
  permission changes require an explicit approval gate unless the owner has
  granted a narrower written policy.
- For meeting attendance proxy work, first verify platform terms, consent,
  account identity, recording/transcription policy, and environment variables.
  Prefer agenda preparation, note capture, and action-item drafting; never
  impersonate a human or join a private meeting without explicit authorization.
- Use `references/loop-engineering-automation.md` for the full operating model and
  `references/process.md` for the loop, spiral engineering, cross-channel
  command, silent-loop auto-resume, Do Not Disturb operating-window,
  ingestion, job automation, meeting proxy, usage-aware role assignment, and
  usage reading reference cards.

