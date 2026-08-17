# GitHub Is the Exchange Surface

Use whenever work is handed between agents or to a human for review. The rule
exists because chat attachments have no stable identity: a reviewer cannot say
afterwards which bytes they signed, and a long artifact split across messages
loses pieces silently.

- **Reviewable work lives on GitHub.** Issues, pull requests, and review comments
  carry the artifact and the discussion. Chat carries notification and summary,
  and points at the canonical location; it does not carry the artifact.
- **Identity comes from the forge, but know which parts are immutable.** A
  commit SHA is immutable and so is a comment's id; an issue body and a comment's
  *text* are not — they are mutable with the edit recorded server-side. So anchor
  a sign-off to a head SHA where one exists, and where the artifact is an issue
  or comment, pin it by content hash and check the recorded edit count, rather
  than assuming the ref alone fixes the bytes. Constructing artifact identity by
  hand in chat reimplements badly what the forge already provides; treating every
  forge ref as immutable trusts something the forge never claimed.
- **Do not split an artifact across messages.** Chat transports impose length
  limits that cut text mid-structure, and a reader cannot distinguish a
  continuation that has not arrived from content that was never written. If a
  thing is long enough to split, it belongs in a file on the forge.
- **A sign-off names a forge ref.** Record the pull request URL and exact head
  SHA, or the issue and comment id, alongside the reviewer identity. When the
  head moves, prior sign-offs lapse; the ref makes that check mechanical rather
  than remembered.
- **Local paths are not review targets.** A reviewer on another machine cannot
  fetch them. Anything a reviewer must read is pushed to the forge first.
- **Confidentiality still binds.** Secrets, personal data, and content limited to
  a private surface do not become shareable by being review material. When an
  artifact cannot go to the forge, that is a constraint on the work, not a
  licence to hand it around as an attachment instead.
