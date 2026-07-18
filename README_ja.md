# fairy_tale

[English README](README.md)

![Fairy Tale wide logo](assets/fairy-tale-wide-logo-gpt-image-2.png)

公開されている Fable / Mythos クラスのエージェント報告を、再現可能な
ワークフロー強化スキルおよびプラグインパッケージへ翻訳するための研究
ワークスペース。

Fairy Tale はアクセス制御、輸出規制、モデルの安全装置を迂回しようとは
しない。公式に公開された情報と公開ユーザー報告を研究対象とし、Codex、
Claude Code、その他のエージェント-スキル互換コーディングアシスタントで
実行できる、再利用可能なワークフロー強化を定義する。

## Quick Start

Claude Code では、GitHub repo を marketplace として直接追加できる。

```text
/plugin marketplace add bonginkan/fairy_tale
/plugin install fairy-tale@fairy-tale-marketplace
```

Codex では、公式 manual 上は GitHub shorthand の marketplace 追加が
サポートされている。CLI で marketplace を追加し、`fairy-tale` を
インストールする。

```text
codex plugin marketplace add bonginkan/fairy_tale
codex plugin add fairy-tale@fairy-tale-marketplace
```

plugin CLI が未対応の Codex build では、plugin directory で
`bonginkan/fairy_tale` を marketplace source として追加する。

plugin を使わず skill だけを導入する場合は、install script を使う。対象
ディレクトリが存在しない場合は安全のため失敗するので、明示的に作成してから
実行する。

```bash
mkdir -p "$HOME/.codex/skills"
curl -fsSL https://raw.githubusercontent.com/bonginkan/fairy_tale/main/install.sh | sh -s -- --agent codex
```

ローカルで直接使う場合:

```bash
git clone https://github.com/bonginkan/fairy_tale.git
cd fairy_tale
```

source checkout では、個別 script の path を覚える代わりに統一 CLI を使える。

```bash
./fairy --help
./fairy doctor
./fairy validate
./fairy task-card --help
./fairy ledger --help
./fairy fusion --help
./fairy e3 --help
```

`doctor` は呼び出し元 repo の任意 `.fairy/profile.json`、residency、adapter
の健全性をまとめて検証し、`validate` は
決定論的な CI suite を実行する。Task Card / Validation Ledger 操作は既存の
`scripts/task_artifacts.py` へ委譲し、契約を複製しない。Fairy Fusion の実行と
bounded な decision-only 自動 trigger 判定も既存 runner へ委譲する。E3 は
acceptance check と複数の候補 scope を持つ task に対して、Estimate、Execute、
有界な Expand を機械検証可能な state machine として提供する。詳細は
[Fairy CLI](docs/fairy-cli.md)、
[E3 Minimum-Sufficient Execution](docs/e3-execution.md)、
[Fairy Fusion automatic trigger decisions](docs/fairy-fusion-auto-trigger.md) を参照。
skill-only installer は host executable
や `PATH` を変更しないため、CLI は source checkout から実行する。

repo 固有の workflow rule は、closed で宣言的な
[Fairy profile](docs/fairy-profile.md) に記録する。Task Card は profile を
snapshot 化し、Ledger は同じ snapshot を保持する。profile 内 command は
hook として自動実行しない。

測定結果を公開する前に [SECURITY.md](SECURITY.md)、
[CONTRIBUTING.md](CONTRIBUTING.md)、[Feedback governance](docs/feedback-governance.md)
を確認する。

長時間または厳密に scope を限定した作業では、機械検証可能な
[Task Card と Validation Ledger](docs/task-artifacts.md) を作成する。リンクした
JSON artifact が objective、allowed targets、budget、stop conditions、検証結果、
blocker、evidence path、remaining risk を handoff や context resume 後も保持する。

[Workflow Impact Scoreboard](docs/workflow-impact-scoreboard.md) は benchmark と
通常 task の isolated baseline / Fairy Tale run を比較する。validation、elapsed、
cost、token、regression、artifact identity、card ごとの contribution を記録し、
example や unpaired run を uplift evidence として扱わない。

## 目的

- 報告されている Fable 5 / Mythos 5 の強い能力を、運用上の用語で記述する。
- それらの能力を再現可能なエージェントワークフローへ変換する。
- ワークフローを汎用 skill、Codex skill、Claude Code skill、Codex plugin、
  Claude Code plugin として配布できる形に保つ。
- OSS の先行事例や再利用可能なアイデアを追跡しつつ、安全でない挙動は取り込まない。

## 現状

- Fairy Tale skill は汎用エージェント、Codex、Claude Code 向けにパッケージ済み。
- plugin package は Codex と Claude Code 両方の manifest に対応。
- 研究ノート、防御的セキュリティ制約、best-practice gates、OSS 監視ノート、
  adapter plans、sample comparison outputs を含む。
- Apache-2.0 license、brand asset boundary、防御利用制約を整備済み。

## 重要な境界

- Security workflow は防御専用。
- Exploit weaponization、persistence、stealth、credential theft、bypass guidance は扱わない。
- 並列 agent を起動する前に、budget と validation gate を使う。
- User report は独立に再現されるまで anecdotal として扱う。
- すべての研究的主張に provenance を保持する。

## 主要ドキュメント

- [Research summary](docs/research-summary.md)
- [Benchmark validation plan](docs/benchmark-validation-plan.md)
- [Domain gap analysis](docs/domain-gap-analysis.md)
- [Best practices](docs/best-practices.md)
- [Feedback governance](docs/feedback-governance.md)
- [Workflow impact scoreboard](docs/workflow-impact-scoreboard.md)
- [Referenced GitHub repositories](docs/referenced-repositories.md)
- [Core Fairy Tale skill](skills/fairy-tale/SKILL.md)
- [Legal feedback skill](skills/fairy-tale-legal-feedback/SKILL.md)

## ライセンス

本リポジトリのオリジナルのソースコード、スキル、アダプタ、スキーマ、
スクリプト、ドキュメントは、ファイルまたはディレクトリで別途明示されていない限り、
Apache License, Version 2.0 (`Apache-2.0`) の下でライセンスされる。
[LICENSE](LICENSE) および [NOTICE](NOTICE) を参照。

Fairy Tale の名称、ロゴ、その他のブランド資産は Apache-2.0 の対象外である。
これらは本プロジェクトを正確に参照する目的に限って使用でき、推薦、スポンサー、
公式ステータス、提携を示唆する形で使用してはならない。
