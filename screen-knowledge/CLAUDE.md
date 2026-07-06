# screen-knowledge 開発ガイド（Claude Code向け）

このディレクトリはPythonプロジェクト。親リポジトリ（BusinessAgent）はMarkdownのみのエージェント定義集であり、規約が異なる。**このディレクトリ配下の作業ではこのファイルが優先。**

## まず読むもの（フェーズ実装セッションの必読順）

1. `docs/02-architecture.md` — コンポーネント設計・スレッドモデル・**凍結インターフェース**
2. `docs/03-data-model.md` — SQLiteスキーマ・保存レイアウト・設定キー（スキーマの単一情報源）
3. 担当フェーズの `docs/1x-phaseN-*.md` — スコープ・受入基準・テスト計画

## 開発規約

- Python 3.12+ / パッケージ管理は **uv**（`uv sync` → `uv run sk ...`）
- Lint: `uv run ruff check src tests` / テスト: `uv run pytest`
- コード識別子・docstringは英語、**ユーザー向け文字列（CLI出力・トレイメニュー・生成Markdown）は日本語**
- `src/screen_knowledge/` 配下のスタブは各フェーズの契約。**シグネチャを変える場合は docs/02, docs/03 と該当フェーズdocも同時に更新する**
- OS依存コードは `capture/adapters/` に隔離する。それ以外のモジュールはOS非依存に保ち、テストは `tests/fakes.py` のフェイクアダプタで行う（CIにGUI・画面収録権限は無い前提）
- SQLiteへの書き込みはデーモンプロセスの単一ライター経由（`db.Database.write()`）。詳細は docs/02 の「書き込み規律」
- コミットは日本語1行サマリ＋必要なら本文。フェーズ完了時は受入基準の充足状況をコミット本文に列挙する

## Claude API利用の規約

- モデルID・価格は `config.example.yaml` の `api.pricing` を既定とするが、**実装セッション開始時に `claude-api` スキル（利用可能なら）または Models API で最新を確認**し、変わっていれば config と docs/00 を更新する
- 画像解析（セッション解析）= `api.analysis_model`、文章合成（マニュアル・日次ログ）= `api.synthesis_model`。モデルIDはコードにハードコードせず必ずconfig経由
- 構造化出力は `client.messages.parse(..., output_format=PydanticModel)`（通常API）/ `output_config={"format": {"type": "json_schema", ...}}`（Batch APIのparams内）。スキーマは `additionalProperties: false` 必須、数値min/max・再帰は使用不可
- Batch APIは「ほとんどのバッチは1時間以内、最大24時間」。**毎時ジョブに使わない**（夜間バッチ専用）。結果は `custom_id` で突合（順序保証なし）
- 全API応答の `usage` を `api_usage` テーブルに記録し、`BudgetGuard` を必ず通す（月次上限超過時は解析停止・キャプチャ継続）

## やってはいけないこと

- ランタイムデータ（スクショ・DB・config.yaml）をリポジトリ内に置く設計にしない（保存先は `~/ScreenKnowledge/`）
- 除外チェックを迂回するコードパスを作らない（キャプチャ時と解析時の二重チェックを維持）
- ビューアを 127.0.0.1 以外にバインドするコードを既定で書かない（`viewer.allow_lan` 明示時のみ）
- APIキーを平文ログ・エラーメッセージ・生成物に出力しない

## 動作確認

- 単体テスト: `uv run pytest`（フェイクアダプタ・FakeAnthropicでネットワーク・GUI不要）
- 実機確認: `docs/90-verification.md` のOS別チェックリスト（権限・トレイ・混在DPIは自動テスト不可）
- 実APIスモーク: `scripts/smoke_analyze.py`（$0.05未満・手動実行のみ。CIで実行しない）
