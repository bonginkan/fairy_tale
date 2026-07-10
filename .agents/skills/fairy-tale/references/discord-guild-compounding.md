# Discord Guild Compounding — per-server Double-Helix operations

How to run the Loop → Spiral → Double-Helix → Evolution altitude model so that
each Discord server (guild) compounds independently: every landed run leaves
the guild's bots (tako3 / takodex / taklaude, Codex + Claude Code) measurably
stronger for the next run in *that* server.

This document is the doctrine/schema SSOT. Runtime implementation lives in the
bot repo (tako: landing hook, guild registry, intake injection) and the
learning pipeline (loopandloop: ingest → eval → promotion). Do not duplicate
runtime values here.

## Strand mapping

| fairy-tale concept | physical implementation |
|---|---|
| execution strand | bot session run (ccdb or ACP lane) + validation gate (test / CI / receipt / PR) |
| learning strand | landing hook emits a guild-scoped `skill_event` (JSONL) → loopandloop ingest |
| double-loop evaluation | loopandloop Eval Pack + deterministic Verifier over accumulated trajectories |
| governing-variable update | PR against the guild's `governance.md` (proposed by pipeline, approved by a human) |
| altitude (spiral axis) | per-guild autonomy ladder recorded in `governance.md` |
| stop / descend | deterministic demotion rule (e.g. 2 consecutive failed landings → drop one altitude level) |
| Evolution | two-stage promotion: guild-local asset → cross-guild/global template, only after reproduction in ≥2 guilds |

## Guild registry (per-server memory)

One directory per guild, owned by the bot runtime:

```
_state/guilds/<guild_id>/
├── governance.md      # altitude, approval thresholds, safety floor (schema below)
├── defaults.toml      # steer/queue default, delegation lane defaults, model preferences
├── playbooks/         # promoted, verified procedures for this server
└── anti-patterns/     # verified "do not do this here" entries
```

Only *promoted* content lives here. Raw trajectories and unverified candidates
stay in the learning pipeline; the registry is the guild's canon.

## governance.md schema (per guild)

```markdown
# Guild Governance — <guild name>

## Altitude ladder (current: L<levels>)
- L0 read-only: answer/summarize only
- L1 draft: produce artifacts (patches, docs) without applying
- L2 apply-gated: open PRs / stage changes, human merges
- L3 apply: merge/deploy within safety floor, post-hoc report
current_level: L1
promotion_evidence: <links to landed runs / eval receipts that justify the level>

## Steer/queue policy
default: steer            # or queue
per_channel_overrides: {}

## Safety floor (never crossed regardless of altitude)
- no secrets in messages or artifacts
- no production deploys from this guild
- no permission/role changes
- destructive ops require explicit human approval in-channel

## Stop / descend rules (deterministic)
- 2 consecutive failed landings → descend one level, notify channel
- any safety-floor violation → descend to L0, require human review to restore
```

## skill_event contract (learning-strand emission)

Emitted by the bot at every landing (success or failure); consumed by the
learning pipeline keyed on `guild_id`:

```json
{
  "schema": "guild-skill-event.v1",
  "guild_id": "...",
  "channel_id": "...",
  "lane": "tako3|takodex|taklaude|delegate",
  "objective": "...",
  "altitude": "L1",
  "outcome": "landed|failed|aborted",
  "validation": ["test", "ci", "receipt", "human-ack"],
  "steer_events": 0,
  "queue_events": 0,
  "evidence_refs": ["pr#...", "run#..."],
  "governing_variable_proposals": []
}
```

`steer_events` matters: a falling steer count for a recurring objective is the
primary signal that promoted playbooks are actually reducing correction load.

## Promotion gates

1. **Guild-local**: candidate playbook/default extracted from ≥3 consistent
   trajectories in one guild → deterministic verifier → lands in that guild's
   registry only.
2. **Evolution (global)**: same template independently reproduced in ≥2 guilds
   → PR into the shared skill/template store. Never promote unverified
   candidates directly to global; never auto-edit `governance.md` (proposals
   ride PRs).

## Anti-patterns

- Do not apply helix ceremony to one-shot trivial asks; plain Loop suffices.
- Do not let the learning strand write to the execution path mid-run; it only
  proposes between runs.
- Do not share guild registries across servers; cross-pollination goes through
  Evolution, not copy-paste.
