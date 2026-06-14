# Security Policy

Fairy Tale is a workflow-augmentation project. Security-related content in this
repository is for defensive review, validation, and governance only.

## Reporting Vulnerabilities

Please report suspected vulnerabilities privately to the repository owner before
public disclosure. Include:

- affected file, script, skill, adapter, or workflow;
- reproducible defensive evidence;
- expected and observed behavior;
- potential impact and preconditions;
- any safe patch or mitigation idea.

Do not include exploit weaponization, persistence, stealth, credential theft,
or instructions for unauthorized systems.

## Scope

In scope:

- repository code, scripts, schemas, skills, adapters, and plugin manifests;
- unsafe security guidance accidentally introduced into documentation or skills;
- dependency or packaging issues that affect this repository's users;
- prompt-injection or tool-authority risks in the documented agent workflows.

Out of scope:

- third-party repositories, datasets, services, or benchmark harnesses that are
  only referenced here;
- attempts to access, bypass, or reconstruct restricted models;
- attacks against systems without authorization.

## Defensive Boundaries

Security workflows must remain defensive-only. Reports and patches should
describe affected components, trust boundaries, preconditions, impact, and
mitigation without publishing operational exploit instructions.
