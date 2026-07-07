# Token Consumption Optimizer Harness: process memoization

Use when an operation succeeded once and is likely to recur: distill the
validated trajectory into a reusable recipe so later runs spend tokens on
execution, not re-discovery. The Evaluated Feedback Loop turns *failures* into
narrow rules; this is its dual — it turns *successes* into replayable process.

- **Capture at consolidation, while context is warm.** After a validated
  success, write a token-recipe record (`references/process/token-recipe-
  record.md`): goal, trigger, preconditions, the exact command/tool sequence
  that worked, verification steps, gotchas hit and their fixes, and the
  first-run cost as baseline. A success that is not captured will be re-derived
  at full price next time.
- **Memoize processes, not judgments.** Deterministic, repeatable operations
  (release/version bump, mirror sync, gate battery, deploy *procedure*, fix
  patterns) are recipe material. Reviews, design decisions, and verdicts must
  be re-derived each run — only their *procedure* (which gates to run, in what
  order) may be memoized, never their conclusions.
- **Authority and safety gates are never memoized.** Permission grants,
  owner/approval decisions, production/deploy go-ahead, and every safety-floor
  gate are re-judged on EVERY replay at full strength. A recipe records THAT a
  gate exists and where it sits in the sequence — never its outcome. "The
  owner approved this last run" or "prod was in scope last time" is not
  authorization for this run; replaying a permission is a security failure,
  not an optimization.
- **Recipe store.** Repo-scoped processes live in the repo (the project's
  docs/process convention); cross-repo or user-level processes live in agent
  memory. One recipe = one process; supersede in place instead of appending
  variants. Never store secrets or tokens — reference env/secret *names* only.
- **Replay before re-derive.** At task start, check the store for a matching
  recipe BEFORE exploring. On a hit, verify the recipe's preconditions cheaply
  (paths, versions, gates still exist), then execute directly. Exploration is
  the fallback for known processes, not the default.
- **Staleness guard.** Recipes are point-in-time. Verify load-bearing facts
  before any mutation step; on drift, stop replaying, re-derive the changed
  segment, and update the recipe. A recipe that silently no longer matches
  reality is worse than no recipe.
- **Validation is never memoized.** Replay skips discovery, not verification:
  the underlying harness's validation gates run at full strength on every
  replay. "It worked last time" is not evidence for this run.
- **Measure the suppression.** Record replay cost against the first-run
  baseline (tool calls, wall time, or token count where visible). A recipe
  that stops reducing cost or keeps failing preconditions is an excess-pass
  candidate — prune or supersede it.
- **Promote hot recipes to durable form.** A recipe replayed often by agents
  is a candidate for a skill (progressive disclosure: metadata always loaded,
  body on demand) or a utility script (executed, not loaded — output-only
  token cost). API-level prompt caching (cache reads at 0.1x input cost,
  5-minute TTL) reduces the cost of *stable context*; this harness reduces
  the *work itself* — they compose, not compete.

Sources (checked 2026-07-07): Anthropic agent-skills best practices (utility
scripts save tokens; concise SKILL.md; progressive disclosure; capture
repeatable procedures as skills) and prompt-caching docs (cost model, TTL) —
platform.claude.com/docs.
