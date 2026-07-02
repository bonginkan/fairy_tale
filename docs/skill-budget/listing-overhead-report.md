# Skill listing overhead — #58 Increment 3 report

Session-constant cost context (code.claude.com/docs/en/skills, fetched 2026-07-02): every
installed skill's `description` (+ `when_to_use`) is loaded into the shared skill-listing
budget of every session — 1% of the model's context window, entries truncated at 1,536
characters, least-used descriptions dropped first when the budget overflows. Unlike the
skill body (paid only on invocation), this cost is paid whether or not the skill fires.

## Description slimming — before/after (measured; before = commit `37bf950`)

| skill | before chars/bytes (~tokens) | after chars/bytes (~tokens) | recall floor |
|---|---|---|---|
| fairy-tale | 1,002 / 1,002 (~250) | **618 / 618 (~154)** | 16 required triggers kept |
| fairy-tale-benchmark-feedback | 300 / 300 (~75) | **248 / 248 (~62)** | 3 kept |
| fairy-tale-legal-feedback | 199 / 199 (~50) | 199 / 199 (~50) — unchanged (keep-intentionally: already minimal) | 3 kept |
| japanese-wordplay-humor-detection | 204 / 588 (~147) | **172 / 494 (~124)** | 5 kept |
| **total** | **~522 est tokens** | **~390 est tokens (−25%)** | — |

Slimming is **recall-first**: `scripts/skill_listing_overhead_check.py` enforces a per-skill
character budget (C1) AND a required-trigger floor (C2) — dropping any representative trigger
(loop / spiral / double-helix / evolutionary / e2e / GUI dogfood / WWCD / usage-aware /
closure / negative-space / excess / migration / research / benchmark / legal / defensive
security, plus per-skill sets) is RED. Raising a budget or editing the trigger floor is a
reviewed change.

## Double-registration audit

`skill_listing_overhead_check.py --agent-home <home>` detects a skill registered twice in the
SAME agent home (local `skills/` copy AND a plugin install), which double-pays the listing
budget. Classification is explicit and machine-checked:

- `stale-duplicate` — local copy byte-identical to the plugin copy → RED, remove the local copy
  (plugin is canonical).
- `diverged-duplicate` — copies differ → RED, reconcile or mark deliberate.
- `intentional-override` — local dir contains a `.local-override` marker file → allowed (warns).

Only homes passed explicitly are scanned; the `.claude` / `.codex` / `.agents` three-host
coexistence on one machine is never a false positive.

## Secondary skills — name-only recommendation

`fairy-tale-benchmark-feedback` and `fairy-tale-legal-feedback` are routed to FROM the core
fairy-tale skill, so their listing descriptions are mostly redundant in sessions that have the
core skill. Hosts that want more listing headroom can set them to name-only in settings:

```json
{ "skillOverrides": { "fairy-tale-benchmark-feedback": "name-only", "fairy-tale-legal-feedback": "name-only" } }
```

This is a docs-level recommendation only (no runtime config is changed by this repo).

## SessionStart hook — measured, kept intentionally

The `--inject` standing instruction is **800 bytes** and every line is either a safety floor
(budget, evidence, defensive-only, fan-out cap, validate-before-done) or the routing trigger
list, all protected by `STANDING_INSTRUCTION_MARKERS` and the checker's `hook_floor` gate.
Trimming further would trade protected safety/routing markers for ~0.1k tokens once per
session — classified **keep-intentionally** under the excess pass. What DID change: the
inject path (and installed-root checks) now aggregate `references/cards/*.md`, fixing the
false "residency degraded" warning emitted on every session start against the post-#57
restructured install.
