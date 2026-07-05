# Phase 4: 検索・閲覧UI — FTS5・タイムライン・ビューア

## ゴール

**いつでも検索して取り出せる。** ブラウザで開くローカルUIから、日本語全文検索・日別タイムライン・マニュアル閲覧ができる。

## 前提

- Phase 1〜3完了（vaultに生成物が存在する）
- 実装前に `CLAUDE.md` → `docs/02-architecture.md`（書き込み規律・SearchIndex契約） → `docs/03-data-model.md`（search_fts）

## スコープ

1. **SearchIndex** (`viewer/search.py`): `search_fts`（external contentではなく通常のFTS5テーブルとして運用: title/body/doc_type/ref_id）への upsert / reindex_all / search
   - インデックス対象: manuals（title+本文）、knowledge（ファイル毎）、daily（日別）、sessions（task_label+summary）
   - **書き込みはデーモン側**: vault書き込み（P2/P3の生成完了時）にupsertをフックする。ビューアプロセスは読むだけ
   - `sk reindex`: vault走査（mtime比較）＋session_analyses全量から再構築。**手動編集されたmdの取り込み経路**でもある
   - `search()`: FTS5 `MATCH` + `snippet()` でハイライト。trigram不可の環境（doctor検知）では `LIKE '%q%'` に縮退（`search_degraded=True` を返しUIに注記表示）
2. **FastAPIアプリ** (`viewer/app.py`): `create_app(cfg, db_ro)`。Jinja2テンプレート＋最小CSS（ビルドステップなし・外部CDN参照なし）
   - `GET /` : 検索ボックス＋最近の日次ログ・マニュアル一覧
   - `GET /search?q=&type=` : 横断検索結果（doc_typeフィルタ・スニペット表示）
   - `GET /timeline/{date}` : その日のセッション一覧（時刻・task_label・カテゴリ・サムネイル）。前日/翌日ナビ
   - `GET /manuals` / `GET /manuals/{slug}` : 一覧・Markdown→HTML表示（画像は下記assets経由）。draft/publishedバッジ表示
   - `GET /assets/{path}` : vault/manuals/assets/ と shots/ の画像配信。**パストラバーサル対策必須**（resolveして基点配下か検証）。purge済み画像は404→UI側でプレースホルダ表示
   - `GET /status` : ハートビート鮮度・今日の記録数・今月コスト・予算バー・直近エラー
   - バインドは `127.0.0.1` 固定（`viewer.allow_lan: true` の場合のみ `0.0.0.0`、その際UIに警告バナー）。認証なしであることをdocs/04に整合
3. **DB接続**: `db.py` のread-onlyファクトリ（`file:...?mode=ro&immutable=0`）。リクエスト毎に接続を開閉（長い読みトランザクションを持たない）
4. **CLI追加**: `sk serve [--port]`（uvicorn起動） / `sk search "query" [--type] [--json]`（上位ヒットをターミナル表示。--jsonはPhase 5のClaude Codeスキル連携用） / `sk reindex`
5. **トレイ統合**: 「ビューアを開く」を有効化（serve未起動ならサブプロセスで起動→ブラウザopen）

## スコープ外

認証・HTTPS（localhost専用と明記） / mdのWeb編集UI（直接ファイル編集→reindexで対応） / 全文検索の形態素解析（trigramで足りる）

## 受入基準

1. **日本語部分一致（load-bearing test）**: 「請求書発行」を含むマニュアルを投入後、`/search?q=請求書` がヒットし、スニペットに `<mark>` ハイライトが付く
2. `/timeline/{date}` にセッションが時刻順で並び、サムネイルが表示される。画像がpurge済みのフレームは壊れ画像にならずプレースホルダになる
3. デーモンが書き込み中（キャプチャ稼働状態を模擬したライタースレッド）でも、ビューア操作5分間で `SQLITE_BUSY` 系エラーが発生しない（並行テスト）
4. `viewer.allow_lan` が false のとき、127.0.0.1 以外へのバインドが起きない（テストでbind先を検証）
5. `sk search` がWeb UIと同一の上位結果を返す（5つのカンドクエリで一致）
6. trigram不可を模擬した環境でLIKE縮退が動き、UIに縮退注記が出る。`sk doctor` にFTS5+trigram検査がある（P1実装の確認・必要なら強化）
7. `/assets/` に `../` を含むパスを与えても基点外のファイルが読めない
8. `uv run pytest` 全通過・`ruff check` クリーン

## テスト計画

- `viewer/test_search.py`: 日本語・英語混在コーパスでのFTS投入→検索（trigram前提のテストは実SQLiteで実施し、trigram不可ならskipマーク＋LIKE縮退テストを実行）・upsert冪等・reindexのmtime差分
- `viewer/test_api.py`: FastAPI TestClientで各ルート（シードDB＋tmp vault fixture）・アセットのトラバーサル拒否・404プレースホルダ・allow_lan
- 並行テスト: 書き込みスレッド（100ms毎にframes insert）＋TestClient連打で例外なし
- テンプレートはスナップショットではなく「含むべき要素」のassert（壊れやすさ回避）

## 実装の落とし穴（必読）

- FTS5 `MATCH` のクエリ構文エラー（ユーザー入力に `"` 等）→ 入力をエスケープ（フレーズ検索として `"..."` で包む）し、構文エラー時はLIKEにフォールバック
- trigramは3文字未満のクエリで機能しない → 2文字以下はLIKE検索に切替（日本語2文字語は頻出）
- Markdown→HTMLは標準的なmdライブラリ（例: `markdown`）で行い、**生成物は自己データなのでXSS過剰対策よりリンク・画像の正動作を優先**。ただし `html.escape` をタイトル等の変数展開に適用
- uvicornはデーモンとは**別プロセス**（`sk serve`）。トレイからの起動はsubprocess.Popen＋既起動チェック（ポート接続試行）
- サムネイルは保存済みWebPをそのまま `<img>` に使い、縮小はCSS（追加のサムネイル生成ジョブを作らない）

## 完了時の状態

「あの操作どうやるんだっけ」→ ブラウザで検索 → マニュアルが出る。「先週何やったっけ」→ タイムラインで振り返る。ツールの当初要望（いつでも取り出せる）がここで完成。

**完了時にやること**: docs/00フェーズ表更新、要確認#5の両OS実測記入、90-verificationのPhase 4チェック実施・記録。
