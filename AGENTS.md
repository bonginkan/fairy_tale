# AGENTS.md

## プロジェクト概要

`fairy_tale` は、Fable / Mythos クラスのエージェント公開レポートを、再現可能な
ワークフロー強化スキル・アダプタ・プラグインに翻訳する研究ワークスペース。
モデル本体ではなく、運用パターンとベンチマーク再現のための足場を提供する。

## 言語方針

- 説明・作業メモ・完了報告・レビューコメントは原則日本語で書く。
- コード、コマンド、ファイル名、識別子、API 名、英語の公式用語は原語のままでよい。
- 英語の外部資料を参照した場合は、必要に応じて日本語で要点を残す。

## リポジトリ地図

- `skills/fairy-tale/`, `skills/fairy-tale-legal-feedback/` — 配布用の canonical skill。
- `.agents/skills/`, `.claude/skills/` — Codex / Claude Code 向けの同期コピー。
- `plugins/fairy-tale/` — Codex / Claude Code プラグインパッケージ。
- `.claude-plugin/` — Claude Code 用 marketplace 定義。
- `adapters/*.adapter.json` — ベンチマーク・外部ツール用アダプタ定義。
- `schemas/` — アダプタおよび成果物の JSON Schema。
- `crates/fairy-adapter-runner/` — アダプタ実行用 Rust crate (workspace ルートは `Cargo.toml`)。
- `scripts/` — ベンチマーク準備・実行・レビュー支援 Python スクリプト。
- `docs/` — 研究ノート、ガバナンス、ベスト プラクティス、ベンチマーク検証計画。
- `sample_results/` — 公開済みサンプル成果物。
- `resources/`, `assets/` — ブランド資産と参照素材 (Apache-2.0 ではない、`NOTICE` 参照)。

## 作業前に読むもの

- `README.md` — プロジェクト全体像、ベンチマーク表、配布形態。
- `CONTRIBUTING.md` — 寄稿原則、ライセンス、検証要件。
- `SECURITY.md` — 防御的セキュリティ運用境界。
- `skills/fairy-tale/SKILL.md` — Fairy Tale ワークフローの正本。
- `docs/governance/best-practices.md` — 採用してよい / してはいけないパターン。
- `docs/benchmarks/benchmark-validation-plan.md` — ベンチマーク再現と報告方法。
- `docs/governance/feedback-governance.md` — フィードバック取り扱いの統制。
- 関連タスクに応じて `docs/` 配下の対象トピック (legal, cybersecurity, oss-watch など)。

## よく使うコマンド

- Rust workspace 整合: `cargo metadata --no-deps --format-version 1`
- Rust ビルド / テスト (該当 crate): `cargo build -p fairy-adapter-runner` / `cargo test -p fairy-adapter-runner`
- Python スクリプトは `scripts/` 配下を直接呼び出す。仮想環境や入出力は `tmp/` 配下に隔離する。
- Claude Code プラグイン読み込み: `/plugin marketplace add .` → `/plugin install fairy-tale@fairy-tale-marketplace`

## 安全上の注意と境界

- 制限モデルへのアクセス、迂回、再構築の試行は禁止。Fable / Mythos の公開情報は
  ワークフロー証跡として扱い、モデル重みや内部仕様の推定には使わない。
- セキュリティ作業は防御目的かつ承認済みに限定。攻撃の武器化、永続化、隠蔽、
  認証情報窃取、検出回避ガイドの提供は禁止。
- 研究的主張には provenance を必ず残す。公開レポートは独立再現まで anecdotal 扱い。
- `tmp/`, `sample_results/` 配下の生成物・ダウンロード物は意図せず公開しない。
  `.gitignore` 済みパスは追跡しない。
- `assets/`, `resources/` のブランド資産は Apache-2.0 ではない (`NOTICE` 参照)。
  改変・再配布前に必ずライセンス境界を確認する。
- `LICENSE`, `NOTICE`, `SECURITY.md`, `CODEOWNERS` の改変はレビュー必須。

## 人間に確認すること

- ベンチマーク数値・delta の公表値変更 (`README.md` の Snapshot 行を含む)。
- 新しいベンチマーク・外部データセットの取り込み判断。
- セキュリティ系スキル・スクリプトの追加または挙動変更。
- ライセンス、ブランド資産、`SECURITY.md`、`CODEOWNERS` への変更。
- リリースノート (`RELEASE_NOTES.md`) およびプラグイン配布物の公開。

## 完了前チェック

- Rust 変更時: `cargo metadata --no-deps --format-version 1` が通る。必要に応じて
  対象 crate の `cargo build` / `cargo test` を実行する。
- Skill / プラグイン変更時: canonical (`skills/`) と同期コピー (`.agents/skills/`,
  `.claude/skills/`)、および `plugins/fairy-tale/` のマニフェストが整合している。
- アダプタ / スキーマ変更時: 対応する `schemas/` と `adapters/` の整合を確認。
- ベンチマーク・研究的主張を更新した場合: 既知値・測定値・サンプル推定の区別と
  provenance、信頼区間の表記が `docs/benchmarks/benchmark-validation-plan.md` に沿っている。
- 公開境界 (License / NOTICE / SECURITY / brand assets) を踏んでいないか確認。
