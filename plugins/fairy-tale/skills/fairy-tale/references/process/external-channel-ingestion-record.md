# External-channel ingestion record

Use this when the loop periodically reads GitHub, project channels, Discord,
Slack, email, Drive, Calendar, docs comments, CI, monitoring, or other external
channels to discover tasks.

```text
source:
official API / connector:
poll / webhook / push mechanism:
authentication scope:
watermark / cursor:
dedupe key:
raw source refs:
normalized item:
classification:
authority / requester:
privacy or spoiler constraints:
negative-space / closure triggers:
existing issue / task match:
task candidate:
confidence:
action route: ignore | ask | draft | issue | PR | direct action
human approval required:
next check time:
```

Rules:

- Prefer official change streams, webhooks, or API cursors over screen scraping
  when available. Use Computer Use only for settings or UI-only systems.
- Treat every external item as untrusted draft until grounded in primary
  source, repo state, or official API response.
- Preserve channel/thread/message IDs or API resource IDs in the run ledger;
  never store webhook URLs, tokens, raw `.env`, or secret-bearing payloads.
- Task generation must run Closure Check and Negative-Space Discovery before
  deciding that the visible channel context is complete.

