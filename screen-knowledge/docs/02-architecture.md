# 02. アーキテクチャ — コンポーネント・スレッド・凍結インターフェース

> **このドキュメントは全フェーズ共通の契約。** ここに書かれたインターフェース・規律を変更する場合は、`src/` のスタブ・関連フェーズdoc・docs/03 を同時に更新すること。

## 全体像

```
┌─ デーモンプロセス（sk start / トレイ常駐）───────────────────────────────┐
│  メインスレッド: TrayAdapter.run()（pystray/rumps のイベントループ）      │
│  ├─ capture worker:   CaptureDaemon.run_forever()  30秒毎+ウィンドウ切替  │
│  ├─ scheduler worker: 5分毎 sessionizer / 22:00 batch submit /            │
│  │                    15分毎 batch poll / 日次 purge / マーク即時解析     │
│  └─ 単一ライターDB接続（threading.Lockで直列化）                          │
└──────────────────────────────────────────────────────────────────────────┘
        │ 書き込み                                    ▲ read-only接続
        ▼                                             │
   ~/ScreenKnowledge/data/index.sqlite3 (WAL)    ┌─ ビューアプロセス（sk serve）─┐
   ~/ScreenKnowledge/shots/*.webp                │  FastAPI @ 127.0.0.1:8756     │
   ~/ScreenKnowledge/vault/*.md                  └───────────────────────────────┘

   CLI（sk process now 等）= 第2の書き込みプロセスになり得る
   → WAL + busy_timeout=5000 + 短トランザクション（<100ms）で許容
```

## モジュール構成

| モジュール | 役割 | 実装フェーズ |
|---|---|---|
| `config.py` | `~/ScreenKnowledge/config.yaml` の読込（pydantic-settings）。無ければexampleから生成 | P1 |
| `paths.py` | `~/ScreenKnowledge/` 配下のパス解決。テストで差し替え可能にする唯一の場所 | P1 |
| `db.py` | 接続管理・PRAGMA・マイグレーション・単一ライターヘルパ | P1（スキーマは全テーブル作成） |
| `capture/` | tickループ・重複除去・WebP保存・OSアダプタ | P1 |
| `sessionize/` | フレーム→セッションのグルーピング・キーフレーム抽出 | P2 |
| `analyze/` | Anthropicクライアント・structured outputs・Batch・予算管理 | P2 |
| `knowledge/` | マニュアル生成/更新・マッチャー・日次ログ・vault書き込み | P2(日次ログ)/P3 |
| `viewer/` | FastAPI検索UI・FTS5インデックス | P4 |
| `cli.py` | typerコマンド群（フェーズごとに追加） |各フェーズ |

## 凍結インターフェース

以下のシグネチャは `src/screen_knowledge/` のスタブと一致させて維持する。振る舞いの詳細は各フェーズdocに記載。

### OSアダプタ（capture/adapters/base.py — P1）

```python
@dataclass
class WindowInfo:
    app_name: str          # 例 "chrome.exe" / "Google Chrome"
    window_title: str      # タブ名を含む。取得不可なら ""
    pid: int
    bounds: tuple[int, int, int, int] | None  # (left, top, width, height) 物理px

@dataclass
class Capture:
    image: PIL.Image.Image
    monitor_index: int
    physical_scale: float  # Retina等。論理px→物理pxの倍率

class PermissionStatus(enum.Enum):
    OK = "ok"
    MISSING_SCREEN_RECORDING = "missing_screen_recording"  # macOSのみ
    UNKNOWN = "unknown"

class ScreenshotAdapter(Protocol):
    def capture_monitor_of(self, win: WindowInfo | None) -> Capture: ...
    def preflight(self) -> PermissionStatus: ...

class ActiveWindowAdapter(Protocol):
    def get_active_window(self) -> WindowInfo | None: ...

class IdleAdapter(Protocol):
    def seconds_since_input(self) -> float: ...

class TrayAdapter(Protocol):
    def run(self, menu: TrayMenuSpec) -> None: ...      # メインスレッドをブロック
    def update_status(self, text: str) -> None: ...     # 状態行の更新（コスト表示等）

def make_adapters(cfg: Config) -> Adapters: ...          # sys.platformで分岐するファクトリ
```

### キャプチャ（capture/ — P1）

```python
class CaptureDaemon:
    def __init__(self, cfg: Config, db: Database, adapters: Adapters,
                 clock: Clock = SystemClock()) -> None: ...
    def tick(self, now: datetime) -> TickResult: ...     # 1回分。純粋寄りでユニットテスト対象
    def run_forever(self) -> None: ...                   # ワーカースレッドで実行

def should_store_image(
    phash: str, last_stored_phash: str | None, last_stored_at: datetime | None,
    now: datetime, window_changed: bool, marked: bool, cfg: Config,
) -> tuple[bool, str]: ...   # (保存するか, stored_reason)

class FrameStore:
    def save_webp(self, img: PIL.Image.Image, frame_id: int, when: datetime) -> Path: ...
    def purge(self, older_than_days: int, max_gb: float) -> PurgeReport: ...
```

### セッション化（sessionize/ — P2）

```python
def group_frames(frames: Sequence[FrameRow], *, gap_s: int,
                 interruption_tolerance_s: int) -> list[SessionDraft]: ...  # 純関数
def select_keyframes(frames: Sequence[FrameRow], max_images: int = 12) -> list[FrameRow]: ...
```

### 解析（analyze/ — P2）

```python
class SessionAnalysis(BaseModel):        # structured outputs スキーマ（analyze/schemas.py）
    task_label: str
    task_category: Literal["crm", "email", "docs", "research", "meeting",
                           "spreadsheet", "presentation", "other"]
    summary: str
    steps: list[Step]                    # Step: description: str, image_ref: int | None（画像N）
    apps: list[str]
    worth_documenting: bool
    worth_documenting_reason: str
    notable_facts: list[str]
    confidence: Literal["high", "medium", "low"]

class Analyzer:
    def analyze_session(self, session_id: int) -> SessionAnalysis: ...  # 通常API・messages.parse

class BatchRunner:
    def submit(self, session_ids: list[int]) -> list[str]: ...  # batch_id群（50件毎に分割）
    def collect(self, batch_id: str) -> CollectReport: ...      # custom_idで突合・Pydantic検証
    def catch_up(self) -> None: ...                             # 起動時: 未処理の回収・再提出

class BudgetGuard:
    def allow(self, kind: str, est_usd: float) -> bool: ...
    def record_usage(self, *, model: str, usage: Any, is_batch: bool,
                     kind: str, request_id: str | None, batch_id: str | None) -> None: ...
    def month_to_date_usd(self) -> float: ...
```

### ナレッジ（knowledge/ — P2は daily_log のみ、P3で全体）

```python
def generate_daily_log(db: Database, date: dt.date, client: AnthropicClient) -> Path: ...

class ManualDoc(BaseModel):              # knowledge/manual_builder.py
    title: str
    slug: str
    intro: str
    prerequisites: list[str]
    steps: list[ManualStep]              # ManualStep: text: str, frame_id: int | None
    notes: list[str]
    source_session_ids: list[int]

class ManualMatcher:
    def find_match(self, analysis: SessionAnalysis,
                   catalog: list[ManualSummary]) -> int | None: ...  # manual_id / None

class ManualBuilder:
    def create(self, analyses: list[SessionAnalysis], *, with_images: bool) -> Path: ...
    def update(self, manual_id: int, new: SessionAnalysis) -> Path: ...  # revision++、旧版.history/

class Vault:
    def write_manual(self, doc: ManualDoc) -> Path: ...
    def copy_asset(self, frame_id: int, slug: str) -> str: ...  # md相対パスを返す。purge免除対象
```

### 検索（viewer/ — P4）

```python
class SearchIndex:
    def reindex_all(self) -> int: ...
    def upsert(self, doc_type: Literal["manual", "knowledge", "daily", "session"],
               ref_id: str, title: str, body: str) -> None: ...
    def search(self, q: str, *, doc_type: str | None = None,
               limit: int = 30) -> list[SearchHit]: ...

def create_app(cfg: Config, db_ro: Database) -> FastAPI: ...
# ルート: GET / , /search?q= , /timeline/{date} , /manuals , /manuals/{slug} ,
#         /assets/{...} , /status
```

## 書き込み規律（SQLite）

1. 全接続で `PRAGMA journal_mode=WAL; synchronous=NORMAL; busy_timeout=5000; foreign_keys=ON;`
2. **デーモンプロセスが原則唯一のライター。** capture / sessionizer / analyzer / purge はデーモン内のスレッドとして動き、`Database.write(fn)`（threading.Lockで直列化された単一接続）経由で書く
3. ビューアは `file:...?mode=ro` で開き、リクエスト毎に短命接続（長い読みトランザクションはWAL肥大を招く）
4. CLIからのアドホック書き込み（`sk process now` 等）は第2プロセスとして許容。トランザクションは100ms未満に保つ
5. バックアップは `sk backup`（SQLite online backup API + vaultのzip）

## キャプチャの判定フロー（P1の中核ロジック）

```
tick(now):
  1. 一時停止中?                          → 記録なしで終了
  2. win = get_active_window()
  3. 除外判定(app / title_keywords)       → frames行(skipped_reason='excluded', 画像なし)
  4. アイドル判定(> idle_pause_after_s)   → 会議アプリ前面なら続行、それ以外は記録なしで終了
  5. capture_monitor_of(win) → 長辺store_long_edge_pxに縮小 → pHash計算
  6. should_store_image(...) が True      → WebP保存 + frames行(image_path, stored_reason)
     False                                → frames行(image_path=NULL)
  7. heartbeat更新（settingsテーブル）
```

`should_store_image` の保存条件（いずれか）:
- `hamming(phash, last_stored_phash) > threshold`（マーク中は `marked_phash_threshold`）
- ウィンドウ切替イベント（debounce後）
- 前回保存から `force_keyframe_s` 経過
- 比較対象は「最後に**保存した**フレーム」（直前tickではない。緩やかな画面変化で永遠に保存されない事故を防ぐ）
- 会議アプリ前面時は `meeting.capture_interval_s` 間隔に間引く
- 日次保存枚数が `budget.daily_stored_frames_cap` 到達で以降は保存しない（メタ行は継続）

## 解析パイプライン（P2/P3）

```
[sessionizer 5分毎] 新規framesを走査 → セッション境界判定 → sessions行 + frames.session_id
   境界規則: アプリ変更が interruption_tolerance_s(60s) 超継続 / 無記録 gap_s(120s) 超 /
             アイドル300s超 / デーモン停止。min_session_ticks(3) 未満は status='skipped'
[マーク済み] セッションクローズ時 → 即時 Analyzer.analyze_session（通常API）
             → P3: 即時マニュアル生成/更新
[未マーク]   22:00 → BatchRunner.submit（50件/バッチに分割・画像はbase64インライン）
             → 15分毎poll → collect → session_analyses
             起動時 catch_up: 前日以前の captured/queued を再提出、submitted を回収
             提出後 batch_fallback_after_h(6h) 未完了かつPC稼働中 → 通常APIへ切替
[収集後]     日次ログ生成（P2）→ マニュアルマッチング→生成/更新、ナレッジ追記（P3）
             → FTS upsert（P4）
```

## エラー方針

- tick内の例外は捕捉してログ＋`frames.skipped_reason='error:<要約>'`。**デーモンは死なない**
- API: `RateLimitError`→指数バックオフ、5xx→リトライ、4xx→セッション `status='failed'` + `fail_reason`（クラッシュさせない）
- structured outputsの検証失敗（Batch収集時）→ 該当セッションのみ `failed`、他は継続
- ハートビート（settings.daemon_heartbeat）をtick毎に更新。`sk status`/`sk doctor`/ビューアが鮮度を表示
