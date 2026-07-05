# Phase 5: 連携（任意・すべて既定OFF）

## ゴール

生成物を外部ツールへ届ける。**3つのサブモジュールは独立しており、必要なものだけ個別に実装・有効化できる。** すべて `integrations.*.enabled: false` が既定で、無効時はimportも外部通信も発生しないこと。

## 前提

- Phase 1〜4完了
- 各サブモジュールの実装は独立したセッションで可（このdocの該当節＋docs/02, 03を読めば足りる）

---

## 5a. Notion同期（`integrations/notion.py`）

**目的**: 完成したマニュアル・日次ログをNotionデータベースへ一方向同期（チーム共有）。

- 対象: `manuals`（statusがpublishedのみ既定。configで draft含む に変更可）と `daily`（直近N日）
- 方式: Notion API（`notion-client` 依存を追加）。configに `token` / `manuals_database_id`（＋daily用DB ID）
- 冪等: `sync_state` テーブル（local_path, content_hash, notion_page_id, synced_at）を追加し、content_hash不変ならスキップ。**2回目の実行が変更0件になること**
- 競合規則: **ローカルが正**。Notion側の編集は上書きされる旨をREADMEに明記
- 画像: Notion external URLは使えない（ローカルのため）→ 既定は「画像なし（テキストのみ＋『画像はローカル参照』注記）」。（要確認）Notion APIのファイルアップロードが利用可能ならオプション対応
- 機密: 同期前に確認プロンプト（`sk notion sync --yes` で省略）。docs/04の「共有前確認」原則に従いpublishedのみが既定
- CLI: `sk notion sync [--dry-run] [--yes]`
- **受入基準**: モックHTTP（respx）でcreate/update/skipの冪等テスト。enabled=falseでnotionモジュールがimportされない（遅延import）

## 5b. Claude Codeスキル（BusinessAgentリポジトリ統合）

**目的**: BusinessAgentの役割エージェント（sales-director等）が、ユーザー自身の作業ナレッジを参照できるようにする。

- 成果物: 親リポジトリの `.claude/skills/screen-knowledge/SKILL.md`
- 内容: 「ユーザーの操作手順・作業履歴・社内オペレーションに関する質問では、ローカルのScreenKnowledge vaultを検索する」という指示＋手段:
  1. `sk search "クエリ" --json` が使える環境（ローカルPCでClaude Code実行時）ではそれを使う
  2. 使えない場合は `~/ScreenKnowledge/vault/` 配下をGrep/Read（パスはconfigから）
  3. リモート実行（Claude Code on the Web等）ではvaultに到達できない旨を答え、ローカル実行を案内する
- **受入基準**: ローカルのClaude Codeセッションで「◯◯の手順は?」と聞くとスキルが発火しvaultのマニュアルを引用して答える（手動検証）。SKILL.mdのfrontmatter（name/description）が規約準拠

## 5c. Slack日報投稿（`integrations/slack.py`）

**目的**: 日次ログの要約を毎朝Slackに投稿（自分宛DMや分報チャンネル）。

- 方式: Incoming Webhook（既定・依存追加なし）。configに `webhook_url` / `post_at`
- 内容: 前営業日の `vault/daily/*.md` のサマリー＋タイムライン先頭数件＋「続きはローカルで」1行。**4000字以内に切り詰め**
- スケジューラ: デーモンのscheduler workerに `post_at` ジョブ追加。失敗は3回リトライ（指数バックオフ）→ログのみ（デーモンは死なない）
- 機密: 投稿前プレビューを初回のみ強制（`--yes` 以降は自動）。顧客名等が入り得る旨をdocs/04整合で注記
- CLI: `sk slack post [--date YYYY-MM-DD] [--dry-run]`
- **受入基準**: モックHTTPで整形・切り詰め・リトライのテスト。enabled=falseで通信ゼロ

---

## 共通の受入基準

1. 3モジュールとも `enabled: false`（既定）では import されず、外部通信が発生しない（テスト: モジュールロード監視）
2. 追加依存はサブモジュール単位のoptional dependency（`[project.optional-dependencies]` の `notion` / `slack` グループ）とし、未インストールでも本体が動く
3. `uv run pytest` 全通過・`ruff check` クリーン
4. docs/00フェーズ表更新、90-verification Phase 5チェック実施

## 実装の落とし穴

- 遅延import（関数内import）で optional dependency 未導入時のImportErrorを「有効化時のみ」発生させ、明確なエラーメッセージ（`uv sync --extra notion` の案内）を出す
- Webhook URL・Notion tokenはconfigに平文で置かれる（keyring対応は任意拡張）。docs/04の表に追記すること
- Slackの文字数制限・Markdown方言（mrkdwn）変換に注意（`**bold**`→`*bold*` 等の最小変換で良い）
