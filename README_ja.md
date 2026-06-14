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
サポートされている。CLI または plugin directory から marketplace を追加し、
`fairy-tale` をインストールする。

```text
codex plugin marketplace add bonginkan/fairy_tale
```

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

測定結果を公開する前に [SECURITY.md](SECURITY.md)、
[CONTRIBUTING.md](CONTRIBUTING.md)、[Feedback governance](docs/feedback-governance.md)
を確認する。

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
