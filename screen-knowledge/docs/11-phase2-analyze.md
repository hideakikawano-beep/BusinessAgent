# Phase 2: セッション化・AI解析・予算管理・日次ログ

## ゴール

**「今日何をしたか」が毎朝Markdownで手に入る。** フレームがセッションにまとまり、Claude APIで解析され、日次作業ログが生成される。コストは予算内に必ず収まる。

## 前提

- Phase 1完了（キャプチャ・DB・トレイが稼働）
- 実装前に `CLAUDE.md` → `docs/02-architecture.md` → `docs/03-data-model.md` → 本書を読むこと
- **モデルID・価格の最新確認**: `claude-api` スキル（利用可能なら）or Models API で `config.example.yaml` の `api.analysis_model` / `synthesis_model` / `pricing` を検証。変更があればconfigとdocs/00を更新
- ANTHROPIC_API_KEYまたはkeyring設定（実APIスモーク用。ユニットテストは不要）

## スコープ

1. **sessionizer** (`sessionize/sessionizer.py`): 5分毎にscheduler workerから実行。`session_id IS NULL` のframesを走査し、docs/02の境界規則でセッション確定 → sessions行作成＋frames.session_id付与。マーク区間（marks）と重なるセッションは `is_marked=1`。`min_session_ticks` 未満は `status='skipped'`
   - `group_frames()` は**純関数**として実装（テスト容易性の要）
   - 中断許容: 別アプリへの60秒以内の離脱は同一セッションに吸収（離脱フレームも同session_idに含める）
2. **keyframeサンプラ** (`sessionize/sampler.py`): `select_keyframes()`。必ず先頭・末尾を含み、残りはpHash多様性で選抜（貪欲: 既選択との最小距離が最大のものから）。画像なし（image_path NULL）フレームは対象外。**除外リストの再チェック**（解析時点のconfigで再評価し、該当フレームを除く — docs/04の統制）
3. **Anthropicクライアント** (`analyze/anthropic_client.py`): SDKの薄いラッパ。APIキー解決（keyring/env/config）、リトライ方針（RateLimitError→指数バックオフ、5xx→リトライ2回、4xx→即失敗）、usage記録フック
4. **structured outputs** (`analyze/schemas.py`): docs/02の `SessionAnalysis`（Pydantic）。**`additionalProperties: false` 相当・数値min/max不使用・再帰なし**（API制約）。`Step.image_ref` は送信画像の番号（1..N）で、収集後に実frame_idへマップ
5. **プロンプト** (`analyze/prompts.py`): 解析用システムプロンプト（固定・日本語出力指示・「画像Nを参照」形式の指定）。**バイト安定に保つ**（タイムスタンプ等を埋めない）
6. **Analyzer** (`analyze/analyzer.py`): 通常API経路。keyframeを `api_image_long_edge_px` に縮小しWebP/base64で送信、`client.messages.parse(..., output_format=SessionAnalysis)`、結果を `session_analyses` へ。`max_tokens` は解析=4096
7. **BatchRunner** (`analyze/batch_runner.py`): 
   - `submit`: `status='queued'` の未マークセッションを50件毎のバッチに分割し `client.messages.batches.create`。paramsは `MessageCreateParamsNonStreaming` + `output_config={"format": {"type": "json_schema", "schema": ...}}`、`custom_id=f"session-{id}"`。sessions.batch_id更新・status='submitted'
   - `collect`: `processing_status == "ended"` を確認後 `results()` を**custom_idで突合**（順序不定）。succeeded→Pydantic検証→session_analyses / errored(invalid_request)→failed / errored(その他)・expired→queuedへ戻す
   - `catch_up`: 起動時。前日以前のcaptured/queuedを（30件超ならbatch、以下なら通常APIで）処理、submittedはpoll。提出から `batch_fallback_after_h` 超過かつ未完了→残りを通常APIへ
8. **BudgetGuard** (`analyze/budget.py`): 全API呼び出しの前に `allow()`（月初からの `api_usage.cost_usd` 合計＋概算がmonthly_usd未満か）。応答後 `record_usage()`（pricingテーブル×batch_discountでcost算出）。超過時: 解析系を停止しセッションはqueuedのまま・トレイに「予算上限到達」表示・キャプチャは継続
9. **日次ログ** (`knowledge/daily_log.py`): その日の session_analyses（analyzed分）から `synthesis_model` で `vault/daily/YYYY-MM-DD.md` 生成（docs/03のフォーマット）。テキストのみ・画像は送らない。`max_tokens=8192`・ストリーミング推奨。既存ファイルがあれば上書き再生成（updated_at更新）
10. **スケジューラ統合**: scheduler workerに登録 — sessionizer(5分毎) / 22:00 submit / 15分毎 poll / 収集完了後にその日の日次ログ生成 / 起動時catch_up。マーク済みセッションはクローズ検知時に即時 `Analyzer` 実行
11. **CLI追加**: `sk process today`（今日の全未処理を通常APIで即時処理→日次ログまで） / `sk process now`（現在openなセッションを強制クローズして処理） / `sk collect`（submitted分の回収） / `sk usage`（今月のコスト内訳表示）。トレイ「今日の分を処理」を有効化し、状態行に月間コスト表示
12. **スモークスクリプト** (`scripts/smoke_analyze.py`): 合成画像2枚で1セッション相当を実APIで解析（$0.05未満）。手動実行専用

## スコープ外

マニュアル生成・マッチャー・knowledge/inbox（P3） / ビューア・FTS（P4） / ホットキーmac対応（P3）

## 受入基準

1. フィクスチャ `tests/fixtures/frames_day1.jsonl`（本フェーズで作成: 1日分の擬似フレーム列。アプリ切替・60秒中断・アイドル分断・会議・マーク区間を含む）に対し、sessionizerが期待どおりの境界・is_marked・skippedを返す（テーブル駆動）
2. FakeAnthropic使用で `sk process today` 相当を実行すると、全クローズ済みセッションに `session_analyses` が入り、`vault/daily/YYYY-MM-DD.md` が生成される（タイムライン・サマリー・気づきセクションを含む）
3. 予算: 月間コストが上限以上の状態では解析APIが呼ばれず、セッションはqueuedのまま、キャプチャは継続する（テストで検証）。80%到達でトレイ警告文字列が更新される
4. Batchフロー（FakeAnthropic）: submitで50件分割・batch_id記録、collectがcustom_id突合で順序に依存せず動作、expired/erroredがqueuedへ戻る、不正JSON（スキーマ違反）はそのセッションのみfailedで他は継続
5. catch_up: 「前日にsubmitted・未回収」「前日にqueued」の状態を仕込んで起動→回収・再処理される（FakeClock+FakeAnthropic）
6. 実APIスモーク: `scripts/smoke_analyze.py` が成功し、api_usageに実トークン数とcost_usd>0が記録される（手動・記録をdocs/90へ）
7. `uv run pytest` 全通過（ネットワーク不要）・`ruff check` クリーン

## テスト計画

- `tests/fakes.py` に `FakeAnthropicClient` を追加: `.messages.parse` / `.messages.create` / `.messages.batches.{create,retrieve,results}` を実装。カンドの正常応答＋故障注入（RateLimitError相当、500、スキーマ違反JSON、batch expired）。usage値を持つ
- `sessionize/test_sessionizer.py`: 境界規則のテーブル駆動（切替継続/中断吸収/ギャップ分断/アイドル分断/min_ticks/マーク重なり）
- `sessionize/test_sampler.py`: 先頭末尾必須・上限12・pHash多様性・除外再チェック
- `analyze/test_analyzer.py`: parse呼び出し・usage記録・4xxでfailed・リトライ挙動
- `analyze/test_batch_runner.py`: 分割・突合・状態遷移・fallback時刻判定（FakeClock）
- `analyze/test_budget.py`: 料金計算（pricing×discount）・月境界・allow/停止
- `knowledge/test_daily_log.py`: 生成Markdownのゴールデンテスト（タイムスタンプ正規化）

## 実装の落とし穴（必読）

- **Batchは毎時処理に使わない**（最大24時間）。夜間提出＋起動時キャッチアップが基本形。「ほとんどは1時間以内」に依存した設計にしない
- Batch resultsは**順序不定**。必ずcustom_idで突合
- 画像はbase64インライン（Files APIは使わない: ベータ依存を増やさない）。1バッチ50セッションに分割し256MB制限に余裕を持つ
- `messages.parse` はSDKヘルパ（`output_format=` にPydanticモデル）。Batch側paramsはAPI生形式 `output_config={"format": {...}}` ＋収集時に同モデルで `model_validate_json`
- スキーマ制約: `additionalProperties: false`、`minimum/maximum`・`minLength` 等は使わない（Literalとdescriptionで表現）
- 送信画像のmedia_typeは `image/webp`。縮小は送信時のみ（保存済みWebPを読み→リサイズ→再エンコード）
- プロンプトは固定文字列でキャッシュ親和的に。ただし1-2Kトークン規模ではキャッシュ最小プレフィックス（Haiku系4096）未満のため `cache_control` は付けない
- 日次ログ生成が長文になるため `client.messages.stream()`＋`get_final_message()` を使う
- 会議セッション（meeting系アプリ支配）はkeyframeを4枚に抑える（映像フレームはトークンの無駄）

## 完了時の状態

朝PCを開くと昨日の作業ログが `vault/daily/` にあり、`sk usage` でコストが見える。マークした作業は即時解析済み（マニュアル化はP3から）。

**完了時にやること**: docs/00フェーズ表更新、要確認#1,#6の実測結果記入、90-verificationのPhase 2チェック実施・記録。
