<div align="center">

# 🪶 fairy_tale

![Fairy Tale wide logo](assets/fairy-tale-wide-logo-gpt-image-2.png)

***The nightingale's scorebook for Fable / Mythos-class agent work.***

[日本語はこちらから](./README_ja.md)

</div>

> *"The real nightingale's song, simple as it was, was the truest of all."*
> — after H. C. Andersen, *The Nightingale*

Research workspace for turning public Fable / Mythos-class agent reports into
reproducible workflow-augmentation skills and plugin packages.

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

---

## 🚪 Quick start

```bash
git clone https://github.com/bonginkan/fairy_tale.git
cd fairy_tale
```

Then, inside Claude Code:

```text
/plugin marketplace add .
/plugin install fairy-tale@fairy-tale-marketplace
```

For Codex, generic agents, or running it as a project skill without the
plugin, point your agent at the corresponding `SKILL.md` under
`skills/`, `.agents/skills/`, or `.claude/skills/`. Before publishing any
measurement, read [SECURITY.md](SECURITY.md),
[CONTRIBUTING.md](CONTRIBUTING.md), and
[docs/governance/feedback-governance.md](docs/governance/feedback-governance.md).

## 🎯 Goals

- Describe the strongest reported Fable 5 / Mythos 5 capabilities in operational terms.
- Convert those capabilities into repeatable agent workflows.
- Package the workflow as:
  - a generic Agent Skill under `skills/fairy-tale/`
  - a Codex repo skill under `.agents/skills/fairy-tale/`
  - a Claude Code project skill under `.claude/skills/fairy-tale/`
  - a distributable Codex plugin under `plugins/fairy-tale/`
  - a distributable Claude Code plugin under `plugins/fairy-tale/`
- Track OSS pioneers and reusable ideas without importing unsafe behavior;
  the active watchlist lives in
  [docs/ecosystem/oss-watch.md](docs/ecosystem/oss-watch.md), and the broader
  capability synthesis in
  [docs/research/research-summary.md](docs/research/research-summary.md).

External-adapter design notes:
[OpenMythos external adapter](docs/adapters/openmythos-external-adapter.md)
covers theoretical-reconstruction substrates, and
[Similarity refactoring adapter](docs/adapters/similarity-refactoring-adapter.md)
covers TypeScript structural-similarity refactor scouting. Feedback
governance, including pruning and contradiction handling, is in
[docs/governance/feedback-governance.md](docs/governance/feedback-governance.md).

## 📖 Current status

The first songbook is usable:

- Fairy Tale skills are packaged for generic agents, Codex, and Claude Code.
- The plugin package supports Codex and Claude Code manifests.
- Research notes, defensive security constraints, best-practice gates, OSS watch
  notes, adapter plans, and sample comparison outputs are checked in.
- The project is prepared for public release with Apache-2.0 licensing, brand
  asset boundaries, and defensive-use constraints documented.

## 🎼 Benchmark Snapshot

These are reproducible local measurements, not final leaderboard claims.
Benchmark rows must keep known Fable/Mythos data, known or measured GPT-5.5
data, and measured GPT-5.5 + Fairy Tale data separate. When a measured Fairy
Tale result is a sample estimate, report the confidence interval or half-width.
The reproduction protocol, sampling rules, and reporting requirements are
defined in
[docs/benchmarks/benchmark-validation-plan.md](docs/benchmarks/benchmark-validation-plan.md);
domain-level gaps and future targets are tracked in
[docs/research/domain-gap-analysis.md](docs/research/domain-gap-analysis.md)
and [docs/research/arc-agi-3-lab-analysis.md](docs/research/arc-agi-3-lab-analysis.md).

| Domain  | Benchmark                                  | Fable/Mythos  | GPT-5.5 | **GPT-5.5 + Fairy Tale** | Delta        |
| ------- | ------------------------------------------ | ------------- | ------- | ------------------------ | ------------ |
| Biology | BioMysteryBench-preview, n=5               | 46.1% / 83.9% | 60.0%   | **80.0%**                | **+20.0 pp** |
| Legal   | Harvey LAB-compatible random sample, n=100 | 13.3%         | 2.1%    | **11.0%**                | **+8.9 pp**  |

Notes:

- Biology Fable/Mythos values are image-reported BioMysteryBench hard /
  human-solved scores. GPT-5.5 is a local medium baseline, 3/5. **Fairy Tale**
  is a local medium run, 4/5, with 95% Wilson CI 37.6-96.4%.
- Legal Fable/Mythos and GPT-5.5 values are image-reported Legal Agent
  Benchmark scores. **Fairy Tale** is a local Harvey LAB-compatible random
  sample, 11/100, with 95% Wilson CI 6.25-18.63% and one-sided p vs 2.1%
  baseline = 8.90e-6.

### 🪞 Legal Feedback Retry

The legal feedback mechanism was tested on 15 tasks selected from prior misses
in the n=100 legal sample. The retry used the same model, effort, judge, and
task IDs, adding `fairy-tale-legal-feedback` to the existing legal harness.
Per-task feedback derivation and the closure-sweep design are recorded in
[docs/research/legal-feedback-analysis.md](docs/research/legal-feedback-analysis.md).

| Metric                             | Before Feedback | **After Fairy Tale Feedback** |       Change |
| ---------------------------------- | --------------: | ----------------------------: | -----------: |
| All-pass rate                      |            0.0% |                     **20.0%** | **+20.0 pp** |
| Criterion pass rate                |          83.21% |                    **90.61%** | **+7.40 pp** |
| One-miss failures                  |              10 |                         **5** |       **-5** |
| Large collapses below 70% criteria |               5 |                         **4** |       **-1** |

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

## 🛡️ Important boundaries

> [!WARNING]
> Fairy Tale is a study of the song, not a key to the cage.
>
> - Security workflows are defensive-only. The defensive scope, threat-model
>   assumptions, and review gates live in
>   [docs/governance/cybersecurity-strengthening.md](docs/governance/cybersecurity-strengthening.md).
> - No exploit weaponization, persistence, stealth, credential theft, or bypass guidance.
> - Use budgets and validation gates before launching parallel agents. Adopted
>   workflow patterns and gate criteria are documented in
>   [docs/governance/best-practices.md](docs/governance/best-practices.md).
> - Treat user reports as anecdotal unless independently reproduced.
> - Preserve provenance for all research claims.
> - See [SECURITY.md](SECURITY.md) for vulnerability reporting and defensive-use
>   boundaries.

## 🧩 Claude Code plugin

This repo includes a Claude Code marketplace catalog at
`.claude-plugin/marketplace.json`. In Claude Code, add the local marketplace and
install the plugin:

```text
/plugin marketplace add .
/plugin install fairy-tale@fairy-tale-marketplace
```

The same `plugins/fairy-tale/` package also remains a Codex plugin via
`plugins/fairy-tale/.codex-plugin/plugin.json`.

## 📜 License

Original source code, skills, adapters, schemas, scripts, and documentation in
this repository are licensed under the Apache License, Version 2.0
(`Apache-2.0`), unless a file or directory states otherwise. See [LICENSE](LICENSE)
and [NOTICE](NOTICE).

The Fairy Tale name, logo, and other brand assets are not licensed under
Apache-2.0. They may be used only to refer accurately to this project, without
implying endorsement, sponsorship, official status, or affiliation.

Third-party repositories, benchmark materials, reports, datasets, and assets
referenced by this repository remain under their own licenses and terms.

## 🗺️ Referenced GitHub repositories

The full bibliography of upstream skills, adapters, harnesses, and references
is documented in
[docs/ecosystem/referenced-repositories.md](docs/ecosystem/referenced-repositories.md).

---

<div align="center">

*Sing only the parts of the song that can be sung again.*

</div>
