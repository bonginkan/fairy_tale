# fairy_tale

[日本語版 README](README_ja.md)

![Fairy Tale wide logo](assets/fairy-tale-wide-logo-gpt-image-2.png)

Research workspace for turning public Fable/Mythos-class agent reports into
reproducible workflow-augmentation skills and plugin packages.

Think of this project as the nightingale's scorebook.

In Andersen's tale, the court becomes enchanted by a jeweled mechanical bird,
only to learn that the living song matters more than the glittering machine.
Fairy Tale does not try to steal the bird, open the cage, or pretend to be the
emperor's locksmith. It studies public descriptions and field reports of
unusually good agent work, separates melody from myth, and writes down the
repeatable patterns as skills, checks, adapters, and sample results.

This repository does not attempt to bypass access controls, export controls, or
model safeguards. It studies public official information and public user reports
to define reusable workflow enhancements that can be run with Codex, Claude Code,
or other agent-skill-compatible coding assistants.

## Quick Start

Install the Claude Code plugin directly from GitHub:

```text
/plugin marketplace add bonginkan/fairy_tale
/plugin install fairy-tale@fairy-tale-marketplace
```

Codex's current plugin marketplace documentation supports GitHub shorthand
marketplaces such as `owner/repo`. Add the repository as a marketplace, then
install `fairy-tale` from the plugin directory:

```text
codex plugin marketplace add bonginkan/fairy_tale
```

If your Codex build does not expose the plugin CLI yet, use the plugin
directory UI and add `bonginkan/fairy_tale` as a marketplace source.

For skill-only use without a plugin, install just the canonical skills:

```bash
mkdir -p "$HOME/.codex/skills"
curl -fsSL https://raw.githubusercontent.com/bonginkan/fairy_tale/main/install.sh | sh -s -- --agent codex
```

Use `--agent claude` for `~/.claude/skills`, `--agent agents` for
`~/.agents/skills`, or `--target /absolute/skills/dir` for an explicit target.
The installer fails closed if the target directory is missing unless `--create`
is supplied.

Before publishing benchmark claims or making the repository public, read
[SECURITY.md](SECURITY.md), [CONTRIBUTING.md](CONTRIBUTING.md), and
[Feedback governance](docs/feedback-governance.md).

## Goals

- Describe the strongest reported Fable 5 / Mythos 5 capabilities in operational terms.
- Convert those capabilities into repeatable agent workflows.
- Package the workflow as:
  - a generic Agent Skill under `skills/fairy-tale/`
  - a Codex repo skill under `.agents/skills/fairy-tale/`
  - a Claude Code project skill under `.claude/skills/fairy-tale/`
  - a distributable Codex plugin under `plugins/fairy-tale/`
  - a distributable Claude Code plugin under `plugins/fairy-tale/`
- Track OSS pioneers and reusable ideas without importing unsafe behavior.

## Current status

The first songbook is usable:

- Fairy Tale skills are packaged for generic agents, Codex, and Claude Code.
- The plugin package supports Codex and Claude Code manifests.
- Research notes, defensive security constraints, best-practice gates, OSS watch
  notes, adapter plans, and sample comparison outputs are checked in.
- The project is prepared for public release with Apache-2.0 licensing, brand
  asset boundaries, and defensive-use constraints documented.

## Benchmark Snapshot

These are reproducible local measurements, not final leaderboard claims.
Benchmark rows must keep known Fable/Mythos data, known or measured GPT-5.5
data, and measured GPT-5.5 + Fairy Tale data separate. When a measured Fairy
Tale result is a sample estimate, report the confidence interval or half-width.

| Domain | Benchmark | Fable/Mythos | GPT-5.5 | **GPT-5.5 + Fairy Tale** | Delta |
| --- | --- | --- | --- | --- | --- |
| Biology | BioMysteryBench-preview, n=5 | 46.1% / 83.9% | 60.0% | **80.0%** | **+20.0 pp** |
| Legal | Harvey LAB-compatible random sample, n=100 | 13.3% | 2.1% | **11.0%** | **+8.9 pp** |

Notes:

- Biology Fable/Mythos values are image-reported BioMysteryBench hard /
  human-solved scores. GPT-5.5 is a local medium baseline, 3/5. **Fairy Tale**
  is a local medium run, 4/5, with 95% Wilson CI 37.6-96.4%.
- Legal Fable/Mythos and GPT-5.5 values are image-reported Legal Agent
  Benchmark scores. **Fairy Tale** is a local Harvey LAB-compatible random
  sample, 11/100, with 95% Wilson CI 6.25-18.63% and one-sided p vs 2.1%
  baseline = 8.90e-6.

### Legal Feedback Retry

The legal feedback mechanism was tested on 15 tasks selected from prior misses
in the n=100 legal sample. The retry used the same model, effort, judge, and
task IDs, adding `fairy-tale-legal-feedback` to the existing legal harness.

| Metric | Before Feedback | **After Fairy Tale Feedback** | Change |
| --- | ---: | ---: | ---: |
| All-pass rate | 0.0% | **20.0%** | **+20.0 pp** |
| Criterion pass rate | 83.21% | **90.61%** | **+7.40 pp** |
| One-miss failures | 10 | **5** | **-5** |
| Large collapses below 70% criteria | 5 | **4** | **-1** |

Strongest recovery: `corporate-ma/draft-stock-purchase-agreement` improved
from 17/117 to 102/117 criteria (+72.6 pp). Remaining weakness: several
contract/redline tasks still end at one missing criterion, so the next legal
loop should target final criterion closure rather than broad scaffolding.

Feedback retry note: **Fairy Tale** feedback used the same model, effort,
judge, and task IDs as the before-feedback slice. After-feedback all-pass was
3/15 with 95% Wilson CI 7.05-45.19%; criterion score was 1004/1108.

BioMysteryBench-preview was run through `scripts/biomystery_runner.py`.
The Fairy Tale run uses generic evidence gates for expression signatures,
context-only BLAST evidence, and bacterial marker-sequence identity. The current
remaining miss is the Brachypodium stress-type item (`hb053`), where the model
still selects a non-heat stress label without stronger heat-specific evidence.

## Important boundaries

- Security workflows are defensive-only.
- No exploit weaponization, persistence, stealth, credential theft, or bypass guidance.
- Use budgets and validation gates before launching parallel agents.
- Treat user reports as anecdotal unless independently reproduced.
- Preserve provenance for all research claims.
- See [SECURITY.md](SECURITY.md) for vulnerability reporting and defensive-use
  boundaries.

## Primary docs

- [Research summary](docs/research-summary.md)
- [Benchmark validation plan](docs/benchmark-validation-plan.md)
- [Domain gap analysis](docs/domain-gap-analysis.md)
- [Cybersecurity strengthening](docs/cybersecurity-strengthening.md)
- [ARC-AGI-3 lab analysis](docs/arc-agi-3-lab-analysis.md)
- [Best practices](docs/best-practices.md)
- [OpenMythos external adapter](docs/openmythos-external-adapter.md)
- [Similarity refactoring adapter](docs/similarity-refactoring-adapter.md)
- [Legal feedback analysis](docs/legal-feedback-analysis.md)
- [Feedback governance](docs/feedback-governance.md)
- [OSS watch](docs/oss-watch.md)
- [Core Fairy Tale skill](skills/fairy-tale/SKILL.md)
- [Legal feedback skill](skills/fairy-tale-legal-feedback/SKILL.md)
- [Fairy Fusion adapter](adapters/fairy-fusion.adapter.json)
- [Feedback pruning adapter](adapters/feedback-pruning.adapter.json)
- [Fairy adapter runner](crates/fairy-adapter-runner/)
- [BioMystery runner](scripts/biomystery_runner.py)
- [SWE-Bench Pro preparer](scripts/swebench_pro_prepare.py)
- [SWE-Bench Pro runner](scripts/swebench_pro_run.py)
- [ExploitBench runner](scripts/exploitbench_run.py)
- [Benchmark feedback ledger](scripts/benchmark_feedback_ledger.py)
- [Legal feedback analyzer](scripts/legal_feedback_analyzer.py)
- [Feedback pruner](scripts/feedback_pruner.py)
- [Skill-only installer](install.sh)
- [Skill package builder](scripts/package_skills.py)
- [Fairy Fusion reviewer](scripts/fairy_fusion_review.py)
- [SWE-Bench Pro adapter](adapters/swe-bench-pro.adapter.json)
- [ExploitBench adapter](adapters/exploitbench.adapter.json)
- [Contributing guide](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Release notes](RELEASE_NOTES.md)

## Claude Code plugin

This repo includes a Claude Code marketplace catalog at
`.claude-plugin/marketplace.json`. In Claude Code, add the GitHub marketplace
and install the plugin:

```text
/plugin marketplace add bonginkan/fairy_tale
/plugin install fairy-tale@fairy-tale-marketplace
```

For local development, `git clone` this repository and use
`/plugin marketplace add .`.

The same `plugins/fairy-tale/` package also remains a Codex plugin via
`plugins/fairy-tale/.codex-plugin/plugin.json` and the repo marketplace at
`.agents/plugins/marketplace.json`.

## License

Original source code, skills, adapters, schemas, scripts, and documentation in
this repository are licensed under the Apache License, Version 2.0
(`Apache-2.0`), unless a file or directory states otherwise. See [LICENSE](LICENSE)
and [NOTICE](NOTICE).

The Fairy Tale name, logo, and other brand assets are not licensed under
Apache-2.0. They may be used only to refer accurately to this project, without
implying endorsement, sponsorship, official status, or affiliation.

Third-party repositories, benchmark materials, reports, datasets, and assets
referenced by this repository remain under their own licenses and terms.

## Referenced GitHub repositories

These repositories informed the current skill, adapter, and plugin architecture.
The maintained list is in [Referenced GitHub repositories](docs/referenced-repositories.md).
