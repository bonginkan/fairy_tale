# fairy_tale (日本語版)

![Fairy Tale wide logo](assets/fairy-tale-wide-logo-gpt-image-2.png)

公開されている Fable / Mythos クラスのエージェント報告を、再現可能な
ワークフロー強化スキルおよびプラグインパッケージへ翻訳するための研究
ワークスペース。

このプロジェクトはナイチンゲールのスコアブック (楽譜帳) のようなものだと
考えてほしい。

アンデルセン童話では、宝石をちりばめた機械仕掛けの小鳥に宮廷が魅了されたあと、
本物の小鳥の生きた歌こそが価値を持つことに気付く。Fairy Tale は機械仕掛けの
鳥を盗もうとせず、籠を開けようとせず、皇帝の鍵師のふりもしない。優れた
エージェント作業についての公開記述と実地レポートを調査し、神話 (myth) と
旋律 (melody) を切り分け、再現可能なパターンをスキル・チェック・アダプタ・
サンプル成果物として書き残す。

このリポジトリはアクセス制御、輸出規制、モデルの安全装置を迂回しようとは
しない。公式に公開された情報と公開ユーザー報告を研究対象とし、Codex、
Claude Code、その他のエージェント-スキル互換コーディングアシスタントで
実行できる、再利用可能なワークフロー強化を定義する。

英語版は [README.md](README.md) を参照。

## クイックスタート

利用するエージェントに合わせて統合方式を選び、インストールを検証する。

1. リポジトリをクローンする。

   ```bash
   git clone https://github.com/bonginkan/fairy_tale.git
   cd fairy_tale
   ```

2. Fairy Tale skill の使い方を選ぶ。

   - Claude Code (ローカル marketplace 経由の plugin、推奨):

     ```text
     /plugin marketplace add .
     /plugin install fairy-tale@fairy-tale-marketplace
     ```

   - Claude Code (plugin を使わない project skill): このディレクトリで Claude
     Code を起動すれば、`.claude/skills/fairy-tale/SKILL.md` が自動的に
     読み込まれる。
   - Codex: `.agents/skills/fairy-tale/SKILL.md` をリポジトリ skill として使うか、
     `plugins/fairy-tale/.codex-plugin/plugin.json` 経由で Codex plugin を
     インストールする。
   - 汎用エージェント: `skills/fairy-tale/SKILL.md` を、必要に応じて
     `skills/fairy-tale-legal-feedback/SKILL.md` も参照させる。

3. (任意) Rust workspace を検証する。

   ```bash
   cargo metadata --no-deps --format-version 1
   ```

4. (任意) ベンチマーク アダプタをエンドツーエンドで試す。生成物はローカルの
   `tmp/` 配下に隔離し、数値を公表する前に
   `docs/benchmarks/benchmark-validation-plan.md` に従う。

   ```bash
   python scripts/biomystery_runner.py --help
   python scripts/swebench_pro_prepare.py --help
   ```

測定結果を公開する前に、[SECURITY.md](SECURITY.md)、
[CONTRIBUTING.md](CONTRIBUTING.md)、
[docs/governance/feedback-governance.md](docs/governance/feedback-governance.md) を再読する。

## 目的 (Goals)

- 報告されている Fable 5 / Mythos 5 の最強クラス能力を、運用上の用語で記述する。
- それらの能力を再現可能なエージェントワークフローへ変換する。
- ワークフローを次の形でパッケージ化する。
  - `skills/fairy-tale/` 配下の汎用 Agent Skill
  - `.agents/skills/fairy-tale/` 配下の Codex リポジトリスキル
  - `.claude/skills/fairy-tale/` 配下の Claude Code プロジェクトスキル
  - `plugins/fairy-tale/` 配下の配布用 Codex プラグイン
  - `plugins/fairy-tale/` 配下の配布用 Claude Code プラグイン
- OSS のパイオニアや再利用可能なアイデアを追跡しつつ、安全でない挙動は取り込まない。
  現行の監視対象は [docs/ecosystem/oss-watch.md](docs/ecosystem/oss-watch.md)、
  能力面の総括は [docs/research/research-summary.md](docs/research/research-summary.md) を参照。

外部アダプタ設計メモ:
[OpenMythos 外部アダプタ](docs/adapters/openmythos-external-adapter.md) は
理論再構成基盤を、
[Similarity リファクタリングアダプタ](docs/adapters/similarity-refactoring-adapter.md) は
TypeScript 構造類似度に基づくリファクタリング探索を扱う。フィードバックの
剪定と矛盾処理を含むガバナンスは
[docs/governance/feedback-governance.md](docs/governance/feedback-governance.md)
を参照。

## 現状 (Current status)

最初のソングブックは利用可能:

- Fairy Tale skill は汎用エージェント、Codex、Claude Code 向けにパッケージ済み。
- プラグインパッケージは Codex と Claude Code 両方のマニフェストに対応。
- 研究ノート、防御的セキュリティ制約、ベスト プラクティスゲート、OSS 監視
  ノート、アダプタ計画、サンプル比較出力をリポジトリに含めている。
- Apache-2.0 ライセンス、ブランド資産境界、防御利用制約を整備し、公開リリースに
  備えている。

## ベンチマーク スナップショット

これらは再現可能なローカル計測結果であり、最終的なリーダーボード主張ではない。
ベンチマーク行では、既知の Fable / Mythos 値、既知または測定済みの GPT-5.5 値、
測定済みの GPT-5.5 + Fairy Tale 値を分けて記載する。測定 Fairy Tale 結果が
サンプル推定の場合は、信頼区間または半幅を併記する。再現プロトコル、
サンプリング規則、報告要件は
[docs/benchmarks/benchmark-validation-plan.md](docs/benchmarks/benchmark-validation-plan.md)
に定義されている。ドメイン別のギャップと将来ターゲットは
[docs/research/domain-gap-analysis.md](docs/research/domain-gap-analysis.md)
および
[docs/research/arc-agi-3-lab-analysis.md](docs/research/arc-agi-3-lab-analysis.md)
で追跡している。

| ドメイン | ベンチマーク | Fable/Mythos | GPT-5.5 | **GPT-5.5 + Fairy Tale** | 差分 |
| --- | --- | --- | --- | --- | --- |
| Biology | BioMysteryBench-preview, n=5 | 46.1% / 83.9% | 60.0% | **80.0%** | **+20.0 pp** |
| Legal | Harvey LAB-compatible random sample, n=100 | 13.3% | 2.1% | **11.0%** | **+8.9 pp** |

補足:

- Biology の Fable/Mythos 値は、画像で報告された BioMysteryBench の hard /
  human-solved スコア。GPT-5.5 はローカル medium ベースライン (3/5)。
  **Fairy Tale** はローカル medium 実行 (4/5)、95% Wilson CI 37.6-96.4%。
- Legal の Fable/Mythos と GPT-5.5 は、画像で報告された Legal Agent Benchmark
  スコア。**Fairy Tale** はローカル Harvey LAB 互換ランダムサンプル (11/100)、
  95% Wilson CI 6.25-18.63%、ベースライン 2.1% に対する片側 p = 8.90e-6。

### Legal フィードバック再試行

Legal フィードバック機構は、先行する n=100 Legal サンプルでの過去のミスから
選んだ 15 タスクで検証した。再試行では、同一モデル・同一エフォート・同一ジャッジ・
同一タスク ID を維持し、既存の Legal ハーネスに `fairy-tale-legal-feedback` を
追加した。タスク単位のフィードバック導出と closure-sweep の設計は
[docs/research/legal-feedback-analysis.md](docs/research/legal-feedback-analysis.md)
を参照。

| 指標 | フィードバック前 | **Fairy Tale フィードバック後** | 変化 |
| --- | ---: | ---: | ---: |
| 全項目通過率 (all-pass) | 0.0% | **20.0%** | **+20.0 pp** |
| 基準項目通過率 (criterion pass) | 83.21% | **90.61%** | **+7.40 pp** |
| 1 項目落ち失敗 (one-miss) | 10 | **5** | **-5** |
| 基準 70% 未満の大崩壊 | 5 | **4** | **-1** |

最大の回復: `corporate-ma/draft-stock-purchase-agreement` は 17/117 から
102/117 criteria へ改善 (+72.6 pp)。残る弱点として、いくつかの契約 / redline
タスクは最後の 1 基準を満たせず終わっており、次の Legal ループは広範な
スキャフォールディングではなく最終基準クロージャを狙うべき。

フィードバック再試行に関する注記: **Fairy Tale** フィードバックは、前スライス
と同一モデル・同一エフォート・同一ジャッジ・同一タスク ID を使用。
フィードバック後 all-pass は 3/15、95% Wilson CI 7.05-45.19%、criterion スコア
は 1004/1108。

BioMysteryBench-preview は `scripts/biomystery_runner.py` で実行している。
Fairy Tale 実行では、発現シグネチャに対する汎用エビデンスゲート、文脈のみの
BLAST エビデンス、細菌マーカー配列の同一性ゲートを用いる。現時点で残るミスは
Brachypodium ストレスタイプの問題 (`hb053`) で、ヒート特異エビデンスが十分でない
状況でモデルが非ヒートストレスのラベルを選ぶ。

## 重要な境界

- セキュリティワークフローは防御専用。防御スコープ、脅威モデルの前提、
  レビューゲートは
  [docs/governance/cybersecurity-strengthening.md](docs/governance/cybersecurity-strengthening.md)
  にまとまっている。
- エクスプロイトの武器化、永続化、隠蔽、認証情報窃取、迂回ガイドの提供は禁止。
- 並列エージェントを起動する前に、予算と検証ゲートを使用する。採用済みの
  ワークフローパターンとゲート基準は
  [docs/governance/best-practices.md](docs/governance/best-practices.md)
  に記載されている。
- ユーザー報告は独立に再現されるまで anecdotal として扱う。
- すべての研究的主張に対して provenance を保持する。
- 脆弱性報告と防御利用境界については [SECURITY.md](SECURITY.md) を参照。

## Claude Code プラグイン

このリポジトリには `.claude-plugin/marketplace.json` に Claude Code 向け
マーケットプレースカタログが含まれている。Claude Code 上でローカル
マーケットプレースを追加し、プラグインをインストールする。

```text
/plugin marketplace add .
/plugin install fairy-tale@fairy-tale-marketplace
```

同じ `plugins/fairy-tale/` パッケージは、`plugins/fairy-tale/.codex-plugin/plugin.json`
を通じて Codex プラグインとしても引き続き機能する。

## ライセンス

本リポジトリのオリジナルのソースコード、スキル、アダプタ、スキーマ、スクリプト、
ドキュメントは、ファイルまたはディレクトリで別途明示されていない限り、
Apache License, Version 2.0 (`Apache-2.0`) の下でライセンスされる。
[LICENSE](LICENSE) および [NOTICE](NOTICE) を参照。

Fairy Tale の名称、ロゴ、その他のブランド資産は Apache-2.0 の対象外である。
これらは本プロジェクトを正確に参照する目的に限って使用でき、推薦、スポンサー、
公式ステータス、提携を示唆する形で使用してはならない。

本リポジトリが参照するサードパーティのリポジトリ、ベンチマーク資料、レポート、
データセット、資産は、それぞれの本来のライセンスおよび条件に従う。

## 参照 GitHub リポジトリ

スキル、アダプタ、ベンチマークハーネスなど、上流リポジトリの一覧と分類は
[docs/ecosystem/referenced-repositories.md](docs/ecosystem/referenced-repositories.md)
にまとめている。
