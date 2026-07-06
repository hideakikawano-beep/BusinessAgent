# Phase 3: ナレッジビルダー — マニュアル生成/更新・ナレッジ・ホットキー

## ゴール

**マークした作業がスクショ付き手順書になり、繰り返し作業がドラフト提案され、気づきが蓄積される。重複せず更新される。**

## 前提

- Phase 1・2完了（キャプチャ・セッション解析が稼働）
- 実装前に `CLAUDE.md` → `docs/02-architecture.md` → `docs/03-data-model.md`（特に生成物フォーマット）→ 本書

## スコープ

1. **Vault** (`knowledge/vault.py`): 生成物の書き込みを一元化
   - `write_manual(doc)`: docs/03のfront matter付きMarkdownをレンダリングし `vault/manuals/<slug>.md` へ。manualsテーブルをupsert（summary=intro要約をマッチャー用に保存）
   - `copy_asset(frame_id, slug)`: shots/の画像を `vault/manuals/assets/<slug>/<frame_id>.webp` へコピーし、md相対パスを返す。**コピー先はpurge対象外**（P1のpurgeはshots/のみ対象であることを確認）
   - 更新時: 現行mdを `.history/<slug>-rev<N>.md` に退避してから上書き、revision++
   - slug規約: task_labelの翻字（小文字英数とハイフン、最大60字、重複時は `-2` 付番）
2. **ManualBuilder** (`knowledge/manual_builder.py`): 
   - `create(analyses, with_images)`: `synthesis_model` で `ManualDoc`（structured outputs・messages.parse）を生成。入力はSessionAnalysis（steps含む）＋keyframeメタ（送信画像は不要: stepsのimage_refから実frame_idを引く）。`with_images=True` でステップ毎に `copy_asset`
   - `update(manual_id, new)`: 既存マニュアル全文＋新しい解析を渡し**全文リライト**（差分パッチはしない）。ステップ画像は新解析のものを優先しつつ、既存にしかないステップの画像は残す
   - 全生成物に自動生成フッター（docs/03フォーマット）
3. **ManualMatcher** (`knowledge/matcher.py`): `analysis_model`（Haiku系）で新しいSessionAnalysisを既存マニュアルカタログ（manuals.title+summary、statusがarchived以外）と照合し `manual_id | None` を返す。structured outputs（`{"match_manual_id": int | null, "confidence": "high|medium|low"}`）。**low confidenceはNone扱い**（誤更新より重複ドラフトの方が安全）
4. **フロー統合** (scheduler / 即時経路):
   - マーク済みセッション: 解析完了（P2の即時経路）→ matcher → 一致: `update` / 不一致: `create(with_images=True, status='draft')`
   - 未マークの繰り返し検出: 夜間収集後、直近14日の analyzed セッション（worth_documenting=true・未マニュアル化）から同種作業が**2回以上**あればグルーピングし `create`（draft）。同一夜間バッチで同じグループから複数作らない。既存マニュアルとmatcher一致するものはupdate候補にせず**スキップ**（自動更新はマーク経由のみ。誤爆防止）
   - notable_facts: 収集後に `vault/knowledge/inbox.md` へ日付見出しの下に追記。**既存行と同一の行は追記しない**
5. **macOSホットキー（任意機能）**: `hotkey.enabled_macos: true` の場合のみpynputで登録。アクセシビリティ権限が必要である旨を `sk doctor` に統合（権限なしでリスナーが無音で動かない事象を検知: 登録後に自己テスト「◯秒以内にキー入力を検知できなければ警告」）。（要確認）代替として `quickmachotkey`（Carbon RegisterEventHotKey・権限不要とされる）を調査し、使えるなら優先
6. **CLI追加**: `sk manualize --last`（直近のクローズ済みセッションを手動でマニュアル化: マークし忘れ救済） / `sk manuals list`（slug・title・status・revision・updated_at）

## スコープ外

ビューアでのマニュアル閲覧（P4） / knowledge/inbox.mdの自動整理・topic昇格（手動運用） / Notion同期（P5）

## 受入基準

1. フィクスチャ＋FakeAnthropicで、マーク済みセッションから `vault/manuals/<slug>.md` が生成され、各ステップの画像が `assets/<slug>/` に実在し、mdからの相対リンクが正しい。purge実行後もassetsが残る
2. 同じ作業の2回目のマーク実行で**新規ファイルが増えず**、matcherが一致→revisionが2になり、旧版が `.history/` に存在する
3. 繰り返し検出: 同種の未マーク作業が2回含まれるフィクスチャで夜間処理→ドラフトマニュアルが**ちょうど1件**作られる。1回のみの作業では作られない
4. notable_factsがinbox.mdに追記され、再実行しても同一行が重複しない
5. matcherがlow confidenceを返すケースで既存マニュアルが変更されず、新規ドラフトが作られる（ゴールデン: 既存ファイルのバイト不変）
6. 生成された全Markdownに自動生成フッターがある
7. （Windows実機）ホットキーでマーク開始→作業→終了→マニュアル生成の一連が動作。（macOS）enabled_macos=true時の権限フロー・自己テストが動作するか、quickmachotkey代替の調査結果をdocs/00要確認#9に記録
8. `uv run pytest` 全通過・`ruff check` クリーン

## テスト計画

- `knowledge/test_manual_builder.py`: 生成Markdownのゴールデンテスト（タイムスタンプ・IDを正規化）。update時の.history退避・revision増分・image_ref→frame_idマッピング
- `knowledge/test_matcher.py`: カンドのカタログで一致/不一致/曖昧（low→None）。FakeAnthropicで判定JSONを注入
- `knowledge/test_vault.py`: slug翻字・重複付番・asset copy・purge免除（P1のpurgeを実行して確認）
- `knowledge/test_inbox.py`: 追記・重複排除・日付見出し
- 繰り返し検出はsessionizer済みフィクスチャからの統合テスト（FakeAnthropicのシナリオ応答: matcher→builderの多段呼び出し）

## 実装の落とし穴（必読）

- **matcherとbuilderで別モデル**（コスト: 照合は安いHaiku系、本文生成はSonnet系）。どちらもconfig経由
- 全文リライト方式の理由: 差分適用はLLMで壊れやすい。旧版は.historyに必ず残るため安全
- `ManualDoc.steps[].frame_id` はNULL許容（画像がないステップを許す）。画像リンク切れを作らないこと（copy_asset成功時のみリンク）
- inbox.mdの重複判定は行の完全一致（正規化: 前後空白除去）で十分。過剰な類似判定はしない
- 繰り返し検出のグルーピングは1回のLLM呼び出しで行う（直近14日のtask_label+summary一覧を渡し、グループと代表を返させる構造化出力）。O(n²)の総当たり照合はしない
- マニュアル本文にAPIキー・トークン等が写った画像を貼らないよう、除外リスト再チェック（P2のsampler）を通過したkeyframeのみがここに到達する前提を崩さない

## 完了時の状態

「この作業、マニュアル化しておきたい」→ トレイ/ホットキーでマーク → 数分後にはスクショ付き手順書がvaultにあり、繰り返し作業は自動でドラフト提案される。ツールの中核価値がここで完成。

**完了時にやること**: docs/00フェーズ表更新、要確認#9記入、90-verificationのPhase 3チェック実施・記録。
