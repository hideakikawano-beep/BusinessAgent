# 01. セットアップガイド（非エンジニア向け）

> **対象読者**: ScreenKnowledgeを自分のPCに導入する利用者。コマンドは1行ずつコピペで実行できる形で書く。
> **実装メモ**: 本ガイドの各手順はPhase 1完了時に実機で通しで検証し、スクリーンショット・実際の出力例を追記すること。

## 0. インストール前チェックリスト（必ず最初に確認）

このツールは**画面のスクリーンショットを自動保存し、その一部を外部API（Anthropic Claude API）に送信**する。業務PCで使う前に、以下を社内（情報システム・セキュリティ担当）に確認すること。

- [ ] 業務PCの画面キャプチャを常時取得・ローカル保存してよいか（保存先はPC内 `~/ScreenKnowledge/` のみ、既定30日で自動削除）
- [ ] 画面画像（顧客情報が写り込む可能性あり）を Anthropic Claude API に送信してよいか
  - 参考: Anthropic の商用APIはデータを既定でモデル学習に使用しないとされるが、**最新の利用規約・データ保持ポリシーを必ず原文で確認**すること（要確認）
  - 送信されるデータの明細は [docs/04-security-privacy.md](04-security-privacy.md) 参照
- [ ] Anthropic APIの利用（個人 or 会社アカウント）と月額課金（目安 $10〜25/月）の扱い
- [ ] 除外すべきアプリ・画面（人事・給与・個人利用など）のリストアップ → `config.yaml` の `exclude` に設定

**1つでも不明・NGがある場合は導入しない。** グレーな場合は「手動記録モードのみ」（常時キャプチャを止め、マーク中のみ記録する運用）から始める選択肢もある（docs/04参照）。

## 1. 必要なもの

- Windows 10/11 または macOS（Apple Silicon / Intel）
- Anthropic APIキー（[console.anthropic.com](https://console.anthropic.com) で発行）
  - **コンソール側でも月額の支出上限（Spend Limit）を設定しておくこと**（二重の安全策）
- ディスク空き容量 15GB以上（スクリーンショット保存用、既定上限10GB）

## 2. インストール

### Windows

1. `scripts/setup.ps1` を右クリック →「PowerShellで実行」
2. スクリプトが行うこと: uv（Pythonパッケージ管理ツール）のインストール → Python 3.12と依存パッケージの取得 → `sk doctor` による環境診断

手動で行う場合:

```powershell
# uvのインストール
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
# このディレクトリ（screen-knowledge）で依存関係を準備
uv sync
# 環境診断
uv run sk doctor
```

### macOS

1. `scripts/setup.command` をダブルクリック
2. **「画面収録」権限の許可が必要**: システム設定 → プライバシーとセキュリティ → 画面収録 → ターミナル（またはPythonバイナリ）を許可
   - 許可しないと**エラーは出ないのに壁紙しか写らない**。`sk doctor` がこの状態を検知して警告する
   - （要確認）権限はPythonバイナリ単位で付与されるため、`.venv` を作り直すと再許可が必要になる場合がある

手動で行う場合:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
uv run sk doctor
```

## 3. APIキーの設定

```bash
uv run sk apikey set
# → プロンプトにAPIキーを貼り付け。OSのキーチェーン（Windows資格情報マネージャー / macOSキーチェーン）に保存される
uv run sk apikey status   # 確認（キーの先頭数文字のみ表示）
```

`config.yaml` への平文保存（`api.key_source: config`）は非推奨。環境変数 `ANTHROPIC_API_KEY` も利用可（`api.key_source: env`）。

## 4. 設定ファイル

初回の `sk start` で `~/ScreenKnowledge/config.yaml` が `config.example.yaml` から自動生成される。最低限見直すべき項目:

| 項目 | 内容 |
|---|---|
| `exclude.apps` / `exclude.title_keywords` | 撮影しないアプリ・画面タイトルのキーワード。**手順0で洗い出したものを必ず追加** |
| `budget.monthly_usd` | 月次API予算上限（既定$25） |
| `retention.screenshot_days` | 生スクショの保持日数（既定30日） |

## 5. 起動と日常の使い方

```bash
uv run sk start     # デーモン起動（タスクトレイ/メニューバーに常駐）
uv run sk status    # 稼働状態・今日の記録数・今月のAPIコストを表示
```

トレイ/メニューバーのアイコンからできること:

- **一時停止/再開**（15分 / 1時間 / 今日中 / 無期限）— 見られたくない作業の前にワンクリック
- **今の作業をマニュアル化 開始/終了** — マークした区間は細かく記録され、確実にマニュアルになる
- **今日の分を処理** — 夜間バッチを待たずに解析を実行
- **ビューアを開く** — 検索・閲覧画面（Phase 4以降）
- **終了**

### 自動起動（推奨）

```bash
uv run sk autostart enable    # ログオン時に自動起動（Win: タスクスケジューラ / mac: launchd）
uv run sk autostart disable
```

## 6. 生成物の場所

| 場所 | 内容 |
|---|---|
| `~/ScreenKnowledge/vault/daily/` | 日次作業ログ（YYYY-MM-DD.md） |
| `~/ScreenKnowledge/vault/manuals/` | 操作マニュアル（スクショ付きMarkdown） |
| `~/ScreenKnowledge/vault/knowledge/` | ナレッジノート |
| `~/ScreenKnowledge/shots/` | 生スクリーンショット（保持期間後に自動削除） |
| http://127.0.0.1:8756 | 検索・閲覧UI（Phase 4以降、`sk serve` またはトレイから） |

vault配下はただのMarkdown＋画像なので、ObsidianやVS Codeで直接開いてもよい。

## 7. トラブルシューティング

| 症状 | 対処 |
|---|---|
| 何も記録されない | `sk doctor` を実行。macOSは画面収録権限、共通はディスク容量・一時停止状態を確認 |
| スクショが壁紙だけ（macOS） | 画面収録権限が未許可。システム設定で許可後、デーモン再起動 |
| 解析が進まない | `sk status` で予算上限到達・APIキー無効を確認。`sk process today` で手動実行 |
| 費用が心配 | `sk status` の月間コスト表示と、Anthropicコンソールの請求画面を確認。`budget.monthly_usd` を下げる |
| 完全に削除したい | デーモン停止 → `~/ScreenKnowledge/` を削除（生成物ごと消えるので注意）→ `sk autostart disable` |
