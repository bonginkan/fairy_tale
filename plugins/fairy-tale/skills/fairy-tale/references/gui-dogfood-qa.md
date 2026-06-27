# GUI Dogfood QA

The **GUI strand** of the e2e layer on the helix arc (Loop → Spiral → Double-Helix
→ Evolution): driving a real graphical interface the way a user would — exploring
every screen, exercising every control, watching the console — and turning what
breaks into a structured, reproducible bug report. Where `general-e2e-completion.md`
proves the **backend/API** strand (mint a session, round-trip the store, probe the
boundary battery), this card proves the **front-end** strand. When the system under
test has a GUI, the two strands are **both** required for an e2e to be complete:
an API that round-trips cleanly behind a dashboard that throws on load is not a
completed e2e.

It is distilled from two browser-dogfood skills and reconciled with fairy_tale's
closure / presence-vs-exercise discipline:
- NousResearch **hermes-agent** `skills/dogfood/SKILL.md` (the 5-phase
  plan → explore → collect → categorize → report loop; "silent JS errors are
  high-value findings").
- Vercel **vercel-labs/agent-browser** `skill-data/dogfood` (repro-graded evidence;
  "test as a user, never read the app's source"; depth over count).

## The mandate: GUI present → GUI dogfood is mandatory

A completed e2e for a system that exposes **any** GUI surface — a page `route`, a
`panel`/rendered view, or a user-facing `flow` (an API `endpoint` or background
`job` is not GUI) — must include a GUI dogfood pass, or carry it as an explicitly
**tracked outstanding** gap (the GUI analog of RED → tracked). It can never be
silently skipped. The e2e-coverage ledger therefore answers the GUI question for
every run: `gui.has_gui` is mandatory, and a `route`/`panel`/`flow` surface in the
inventory with `has_gui:false` is a closure contradiction the gate rejects.

This is the Negative-Space Closure Check pointed at the front end: "the API tests
passed" is never silently "the product works."

## How it reconciles with the code-aware closure check

The dogfood skills insist you **test as a user and do not read the app's source**.
fairy_tale's closure check insists you **enumerate surfaces from code and deploy**.
These are not in conflict — they are two phases:

- **Scope from code (closure).** Enumerate the real surfaces (routes, panels,
  views) from the code/deploy so the inventory is complete and nothing is silently
  omitted. This defines *what must be exercised*.
- **Exercise as a user (black-box).** During the dogfood *run*, drive those surfaces
  through the browser as a real user — click, type, navigate, watch the console —
  judging behavior by what the UI does, not by what the source says it should do.
  Reading the source to "explain away" a UI bug is exactly the failure mode the
  black-box rule prevents.

Scope is white-box; execution is black-box. Both, in order.

## The loop (explore and document in one pass)

1. **Initialize.** Output dir (`screenshots/`, `videos/`, `report.md`), a named
   browser session, the report header.
2. **Reach.** Sign in if needed (the same mint-session reachability as the API
   strand when an interactive login blocks a headless run — never relaxing the
   safety floor, never recording the secret value). Save auth state for reuse.
3. **Orient.** Initial annotated screenshot + interactive snapshot; map the nav.
4. **Explore + document together.** Walk the surfaces from the inventory. At each:
   snapshot → annotated screenshot → **check the console after navigation and after
   every significant interaction** (silent JS errors / failed requests are
   high-value and invisible in the UI) → exercise controls (click, type, keyboard,
   scroll, forms with **both valid and invalid** input) → re-check console + visual
   state. When you find an issue, **stop and document it immediately** before moving
   on — never batch findings for the end (a mid-run interruption must not lose them).
5. **Wrap up.** Reconcile the report's severity counts with the actual issues; close
   the session.

## Evidence is repro-graded (match the proof to the issue)

- **Verify reproducibility first.** Before collecting evidence, reproduce the issue
  at least once more. A finding that does not reproduce consistently is not a valid
  issue — it is noise.
- **Interactive / behavioral issue** (functional, UX, console-error-on-action):
  full repro — start a **repro video** *before* reproducing, walk the steps at human
  pace (`type` character-by-character, `sleep` between actions so the video is
  watchable), screenshot each step, capture the broken state with an annotated
  screenshot, stop the video. Write numbered repro steps that each reference their
  screenshot.
- **Static / visible-on-load issue** (typo, placeholder text, clipped/misaligned
  text, console-error-on-load): a **single annotated screenshot** is sufficient — no
  video, no multi-step repro. Do not over-evidence a typo.
- **Residue zero.** Never delete output mid-run; but any *test data* created in the
  app during the pass is cleaned up and verified gone, exactly as the API strand
  requires. Production/main is never touched.

## Severity and category (the calibration to apply)

| Severity | Definition |
|----------|------------|
| critical | Blocks a core workflow, causes data loss, or crashes the app |
| high     | Major feature broken or unusable, no workaround |
| medium   | Feature works but with noticeable problems, a workaround exists |
| low      | Minor cosmetic or polish issue |

Categories: **functional** · **visual/UI** · **ux** · **content** · **performance**
· **console/errors** · **accessibility**. Read the source taxonomies for the
per-category checklists (broken links / silent-fail / lost state; layout / clipping
/ contrast; missing feedback / destructive-action confirmation / dead ends; typos /
placeholder left in; slow loads / layout shift / excessive requests; JS exceptions /
4xx-5xx / CORS / unhandled rejections; missing alt text / focus management).

## Depth over count

Aim for **5–10 well-documented issues with full repro**, not twenty vague ones.
Depth of evidence is the deliverable: a report a responsible team can act on without
re-investigating. Spend more time on core features, less on peripheral pages; if a
cluster of issues appears in one area, dig deeper there.

## Report contract

A human-readable `report.md` (distinct from the JSON ledger):
- **Executive summary** — total issue count, severity breakdown, scope tested.
- **Per issue** — id (ISSUE-001…), severity + category badge, URL, numbered repro
  steps each referencing its screenshot, expected vs. actual, console errors,
  screenshot/video refs.
- **Summary table** + **testing notes** (what was and was not tested, blockers).

Every RED a dogfood pass surfaces is filed to a tracker (issue/PR) the same way the
API strand files a RED — a GUI bug "noted" but untracked cannot be reported as
handled.

## Output contract (ledger)

The GUI pass is recorded in the same `e2e-coverage/NNNN-<target>.json` run record,
under `gui` (validated by `scripts/e2e_coverage_check.py`, `schemas/e2e-coverage-
ledger.schema.json`):

- `gui.has_gui` (mandatory boolean) — does the system expose a GUI surface? A
  `route`/`panel`/`flow` surface in the inventory with `has_gui:false` fails closed
  (an API `endpoint` or background `job` is not GUI).
- If `has_gui:false` → `gui.no_gui_reason` (substantive; "headless voice/API
  service, no rendered surface" — a vague reason fails).
- If `has_gui:true` → `gui.dogfood`, which is either:
  - **performed**: `performed:true`, `console_checked:true` (the dogfood
    signature), `issue_taxonomy_applied:true`, `issues_found` (≥0) with **≥
    `issues_found` tracked `red_findings`** (every surfaced issue is a tracked RED —
    RED → tracked), and `evidence` with at least one **browser artifact** (annotated
    screenshot `.png`/`.jpg` or repro video `.webm`) — a GUI "exercise" with no
    visual/video evidence is presence wearing an exercise label; **or**
  - **outstanding**: `performed:false` with `outstanding_ref` (a tracker URL). This
    is a *valid but not complete* state — the GUI dogfood is tracked, not done. A
    completion claim requires `performed:true`.

The gate fails closed on: a missing `gui` block, a `route`/`panel`/`flow` surface
with `has_gui:false`, a missing/vague `no_gui_reason`, a performed dogfood without a
console check / taxonomy / browser-artifact evidence, a performed dogfood with fewer
tracked REDs than `issues_found`, or an outstanding dogfood without a tracker URL.

## How it connects

- Run it as a **double-helix**: the execution strand drives the GUI surfaces; the
  review strand refutes coverage ("which screen, control, or console error went
  unexercised?"). Reviews follow the same 2-distinct-reviewer / refute-pass contract
  as the other ledgers.
- The closure-check is the **Closure Check / Negative-Space** card (`process.md`)
  pointed at the *visible* product; presence-vs-exercise is "a panel that renders is
  not a panel that works." Accumulate reusable oracles (console-clean-after-action,
  invalid-input-rejected, destructive-action-confirmed) across apps.
