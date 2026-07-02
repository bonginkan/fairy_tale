# Meeting proxy setup record

Use this before building or running any meeting attendance proxy. This card is
for lawful preparation and controlled operation, not impersonation.

```text
meeting platform:
meeting source:
account identity:
authorization / invitation status:
participant disclosure / consent:
recording or transcription policy:
bot display name:
join mechanism:
audio/video/input capability:
calendar integration:
artifact outputs:
reference implementation and files:
service boundaries:
env var classes, names only:
secret delivery model:
data retention / storage:
human approval gate:
environment variables:
terms / policy constraints:
fallback if join fails:
post-meeting validation:
```

Hard limits:

- Do not join a private meeting, record, transcribe, or speak as the user unless
  the authorization, account identity, and consent policy are explicit.
- Prefer agenda preparation, live notes when authorized, summary drafting, and
  action-item extraction over active participation.
- When referencing an external meeting-agent repo, first inspect its auth,
  consent, recording, environment-variable, and data-retention model.
- If `agent-lime` is the reference implementation, record the orchestrator,
  media-gateway, speech-agent, calendar, Vexa, STT/TTS, storage, webhook,
  internal-token, and deployment secret/env split before claiming the setup
  path is actionable. Record variable names and classes only; never copy secret
  values.

