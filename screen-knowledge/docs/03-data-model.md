# 03. データモデル — SQLiteスキーマ・保存レイアウト・設定リファレンス

> **スキーマの単一情報源。** テーブル・カラムの変更は必ずここを先に更新し、`db.py` のマイグレーションと各フェーズdocを追随させる。

## 保存レイアウト（~/ScreenKnowledge/）

```
~/ScreenKnowledge/
├── config.yaml                     # 初回起動時に config.example.yaml から生成
├── data/
│   └── index.sqlite3               # 下記スキーマ（WALモード）
├── shots/
│   └── YYYY/MM/DD/<frame_id>.webp  # 生スクショ。retention.screenshot_days 後に自動削除
├── vault/                          # 生成物（ただのMarkdown+画像。手動編集OK）
│   ├── manuals/
│   │   ├── <slug>.md
│   │   ├── assets/<slug>/<frame_id>.webp   # マニュアル用画像コピー（purge免除）
│   │   └── .history/<slug>-rev<N>.md       # 更新前の旧リビジョン
│   ├── knowledge/
│   │   ├── inbox.md                # notable_factsの追記先（あとで手動整理する前提）
│   │   └── <topic>.md
│   └── daily/
│       └── YYYY-MM-DD.md
└── logs/
    └── daemon.log                  # ローテーション（例: 5MB×3世代）
```

## SQLite DDL（全文）

Phase 1の `db.py` マイグレーションで**全テーブルを作成する**（後続フェーズのテーブルも空で作る。スキーマ変更をフェーズ間で分散させない）。

```sql
-- 接続毎PRAGMA（参考）: journal_mode=WAL, synchronous=NORMAL, busy_timeout=5000, foreign_keys=ON

CREATE TABLE settings (
  key   TEXT PRIMARY KEY,   -- schema_version / daemon_heartbeat / paused_until / mark_active ...
  value TEXT NOT NULL
);

CREATE TABLE frames (
  id            INTEGER PRIMARY KEY,
  captured_at   TEXT NOT NULL,             -- ISO8601 ローカル時刻+オフセット
  app_name      TEXT NOT NULL DEFAULT '',
  window_title  TEXT NOT NULL DEFAULT '',  -- 取得不可（mac権限なし等）は ''
  monitor_index INTEGER,
  phash         TEXT,                      -- 64bit pHash の16進16文字。未計算はNULL
  image_path    TEXT,                      -- shots/からの相対パス。NULL=重複により画像なし
  stored_reason TEXT,                      -- 'threshold'|'window_change'|'keyframe'|'marked'
  skipped_reason TEXT,                     -- 'excluded'|'idle'|'error:<msg>'。NULL=正常
  is_marked     INTEGER NOT NULL DEFAULT 0,
  session_id    INTEGER REFERENCES sessions(id)   -- sessionizerが後から付与
);
CREATE INDEX idx_frames_time    ON frames(captured_at);
CREATE INDEX idx_frames_session ON frames(session_id);

CREATE TABLE marks (                       -- 「マニュアル化」トグルの区間記録
  id         INTEGER PRIMARY KEY,
  started_at TEXT NOT NULL,
  ended_at   TEXT,                         -- NULL=マーク中
  note       TEXT
);

CREATE TABLE sessions (
  id                 INTEGER PRIMARY KEY,
  started_at         TEXT NOT NULL,
  ended_at           TEXT NOT NULL,
  app_name           TEXT NOT NULL,        -- 支配的なアプリ
  title_sample       TEXT,                 -- 代表タイトル（先頭 or 最頻）
  frame_count        INTEGER NOT NULL,
  stored_frame_count INTEGER NOT NULL,
  is_marked          INTEGER NOT NULL DEFAULT 0,
  status             TEXT NOT NULL DEFAULT 'captured',
                     -- captured → queued → submitted → analyzed / failed / skipped
  batch_id           TEXT,
  fail_reason        TEXT
);
CREATE INDEX idx_sessions_status  ON sessions(status);
CREATE INDEX idx_sessions_started ON sessions(started_at);

CREATE TABLE session_analyses (
  id                 INTEGER PRIMARY KEY,
  session_id         INTEGER NOT NULL UNIQUE REFERENCES sessions(id),
  model              TEXT NOT NULL,
  analyzed_at        TEXT NOT NULL,
  task_label         TEXT NOT NULL,
  task_category      TEXT NOT NULL,
  summary            TEXT NOT NULL,
  steps_json         TEXT NOT NULL,        -- SessionAnalysis.steps のJSON
  notable_facts_json TEXT NOT NULL DEFAULT '[]',
  worth_documenting  INTEGER NOT NULL,
  confidence         TEXT NOT NULL,        -- high|medium|low
  input_tokens       INTEGER,
  output_tokens      INTEGER
);

CREATE TABLE manuals (
  id                       INTEGER PRIMARY KEY,
  slug                     TEXT NOT NULL UNIQUE,
  title                    TEXT NOT NULL,
  file_path                TEXT NOT NULL,          -- vault/ からの相対パス
  status                   TEXT NOT NULL DEFAULT 'draft',  -- draft|published|archived
  revision                 INTEGER NOT NULL DEFAULT 1,
  summary                  TEXT NOT NULL DEFAULT '',       -- マッチャーのカタログ用
  source_session_ids_json  TEXT NOT NULL DEFAULT '[]',
  created_at               TEXT NOT NULL,
  updated_at               TEXT NOT NULL
);

CREATE TABLE daily_logs (
  date       TEXT PRIMARY KEY,             -- YYYY-MM-DD（ローカル）
  file_path  TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE api_usage (
  id                INTEGER PRIMARY KEY,
  ts                TEXT NOT NULL,
  kind              TEXT NOT NULL,         -- analysis|synthesis|matcher|daily|smoke|other
  model             TEXT NOT NULL,
  is_batch          INTEGER NOT NULL DEFAULT 0,
  request_id        TEXT,
  batch_id          TEXT,
  input_tokens      INTEGER NOT NULL,
  output_tokens     INTEGER NOT NULL,
  cache_read_tokens INTEGER NOT NULL DEFAULT 0,
  cost_usd          REAL NOT NULL          -- 記録時に config.api.pricing から算出
);
CREATE INDEX idx_usage_ts ON api_usage(ts);

-- Phase 4（作成はPhase 1で行い、Phase 4まで未使用）
-- trigramトークナイザ: 日本語の部分文字列検索に必須。SQLite >= 3.34。
-- 利用不可環境では sk doctor が警告し、LIKE検索へ縮退する。
CREATE VIRTUAL TABLE search_fts USING fts5(
  title, body,
  doc_type UNINDEXED,   -- manual|knowledge|daily|session
  ref_id   UNINDEXED,
  tokenize='trigram'
);
```

### セッションのstatus遷移

```
captured --(sessionizer完了)--> queued --(batch提出)--> submitted --(収集成功)--> analyzed
   |                              |                        |
   |                              +--(即時解析成功)--------+--> analyzed
   |                              +--(解析4xx/検証失敗)--> failed(fail_reason)
   +--(min_session_ticks未満)--> skipped
submitted --(batch期限切れ/エラー)--> queued（再提出対象に戻す）
```

## 設定キーリファレンス（config.yaml）

`config.example.yaml` が既定値の正。ここでは意味が自明でないキーのみ補足する。

| キー | 補足 |
|---|---|
| `capture.store_long_edge_px` | 保存時縮小。Retinaの3024px級をこのサイズに落とす。マニュアルの画像品質と直結（2000推奨） |
| `api.api_image_long_edge_px` | API送信時にさらに縮小（既定1024）。画像トークン ≈ (w×h)/750 |
| `dedupe.phash_threshold` | 64bit pHashのハミング距離。8=「明確な画面変化のみ保存」、小さくすると保存増 |
| `analysis.mode` | `nightly_batch`: 未マーク分は22時にBatch提出（50%割引）。`realtime`: セッションクローズ毎に通常API |
| `budget.monthly_usd` | `api_usage.cost_usd` の当月合計がこれに達したら解析系API呼び出しを停止（キャプチャ・記録は継続） |
| `hotkey.enabled_macos` | 既定false。有効化するとアクセシビリティ権限が必要（docs/12参照） |
| `api.key_source` | `keyring`（推奨）→OSキーチェーン / `env`→ANTHROPIC_API_KEY / `config`→本ファイル平文（非推奨） |

## 生成物フォーマット

### マニュアル（vault/manuals/<slug>.md）

```markdown
---
slug: hubspot-deal-update
title: HubSpotで商談ステージを更新する
status: draft          # draft=自動生成のみ / published=人が確認済み（手動で変更）
revision: 2
updated_at: 2026-07-05T14:30:00+09:00
source_sessions: [123, 145]
---

# HubSpotで商談ステージを更新する

（作業の概要 1-2文）

## 前提
- （必要な権限・状態）

## 手順
1. （ステップ説明）
   ![step-1](assets/hubspot-deal-update/1234.webp)
2. ...

## 注意点
- ...

---
*自動生成 (ScreenKnowledge) — 内容を確認してから共有してください。旧版: .history/*
```

### 日次ログ（vault/daily/YYYY-MM-DD.md）

```markdown
# 2026-07-05 (土) 作業ログ

## サマリー
（その日の3-5行要約）

## タイムライン
- 09:12–09:48 [crm] HubSpotで商談パイプライン整理（32分）
- 10:02–10:15 [email] A社への見積もり送付 ...

## 気づき・ナレッジ候補
- （notable_factsの転記。knowledge/inbox.md にも追記される）

---
*自動生成 (ScreenKnowledge) — 内容を確認してから共有してください*
```

### ナレッジ（vault/knowledge/inbox.md）

日付見出しの下に `- [ ] 気づき（出典セッションID）` 形式で追記。重複行は追記しない。手動整理して個別の `<topic>.md` に昇格させる運用。
