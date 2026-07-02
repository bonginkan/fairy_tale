# Job automation delegation record

Use this for email drafting, Google Drive/Docs/Sheets edits, calendar actions,
meeting preparation, CRM/admin updates, or other business-process automation.

```text
job family:
requester / authority:
target account or workspace:
tool/API:
oauth scopes or permissions:
input sources:
draft artifact:
proposed external action:
approval mode: draft_only | approve_before_send | approve_before_edit | pre-authorized_policy
mutation target:
audit trail:
rollback or correction path:
privacy / confidentiality constraints:
rate limit / quota:
success criteria:
stop conditions:
```

Default policy:

- Email starts as a draft or proposed reply. Sending requires explicit approval
  or a narrow owner-approved policy naming send conditions.
- Drive/Docs/Sheets starts as a proposed patch, suggestion, comment, or
  exported artifact when possible. Direct mutation requires explicit approval,
  scopes, and rollback notes.
- Calendar and meeting actions require account identity, invite/consent
  status, and visibility rules before any join, RSVP, or external message.
- If credentials, OAuth scopes, domain-wide delegation, service accounts, or
  environment variables are missing, produce setup steps and stop before
  action.

