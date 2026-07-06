# Phase 1: キャプチャ基盤 — デーモン・トレイ・保存・統制

## ゴール

**「安全に記録できる」。** トレイ常駐デーモンがスクリーンショットとメタデータを記録し、プライバシー統制（除外・一時停止・自動削除）が機能し、状態が観測できる。**このフェーズではAPIを一切呼ばない。**

## 前提

- 実装前に `CLAUDE.md` → `docs/02-architecture.md` → `docs/03-data-model.md` を読むこと
- 依存フェーズ: なし（最初のフェーズ）
- 対象OS: Windows / macOS 両対応。実機が片方しかない場合、もう片方のアダプタは実装＋docstringに検証待ちと明記し、docs/00の要確認表を更新する

## スコープ

1. **config** (`config.py`, `paths.py`): pydantic-settingsでconfig.yaml読込。無ければ `config.example.yaml` の内容で生成。`paths.py` は `~/ScreenKnowledge/` 解決の唯一の場所（テストで差替え可能に）
2. **db** (`db.py`): 接続管理（PRAGMA群）、docs/03の**全テーブル**を作るマイグレーション（schema_versionで管理）、単一ライターヘルパ `Database.write(fn)`、read-only接続ファクトリ
3. **OSアダプタ** (`capture/adapters/`): docs/02の凍結Protocol準拠
   - Windows: mss + `GetForegroundWindow`/`GetWindowText`/`GetWindowThreadProcessId` + psutil(exe名) + `GetLastInputInfo`(アイドル) + **起動時にPer-Monitor-V2 DPI awareness設定**（ctypes; 失敗時 `shcore.SetProcessDpiAwareness(2)` にフォールバック）
   - macOS: mss + `NSWorkspace.frontmostApplication`(アプリ名) + `CGWindowListCopyWindowInfo`(タイトル・bounds) + `CGEventSourceSecondsSinceLastEventType`(アイドル) + `CGPreflightScreenCaptureAccess`/`CGRequestScreenCaptureAccess`(preflight; シンボル名は要確認)
   - `capture_monitor_of`: アクティブウィンドウのboundsを含むモニタのみ撮影（mss.monitors[1..N]と照合、判定不能時はプライマリ）。**mss.monitors[0]（全モニタ結合）は使わない**
4. **キャプチャループ** (`capture/daemon.py`, `dedupe.py`, `storage.py`): docs/02「キャプチャの判定フロー」の実装。pHashはグレースケール縮小画像で計算し「最後に保存したフレーム」と比較。WebP保存（`store_long_edge_px` に縮小、品質~80）。会議アプリ低頻度化。日次保存上限。`capture.interval_seconds: 0` は「常時キャプチャ無効・マーク中のみ記録」と解釈
5. **トレイ** (`capture/adapters/` の TrayAdapter 2実装): pystray(Win) / rumps(mac)。**メインスレッド=トレイ、キャプチャ等はワーカースレッド**（特にmacはGUIがメインスレッド必須）。メニュー: 状態表示（記録中/一時停止/エラー/今日の保存枚数）、一時停止(15分/1時間/今日中/無期限)/再開、今の作業をマニュアル化 開始/終了（marksテーブルに記録・キャプチャ間隔を `marked_interval_seconds` に切替）、今日の分を処理（P2まではdisabled表示）、ビューアを開く（P4まではdisabled）、終了
6. **purge** (`storage.py`): `retention.screenshot_days` 超過 と `max_disk_gb` 超過（古い順）の画像削除＋`frame_metadata_days` 超過のメタ行削除。**vault/manuals/assets/ は対象外**（shotsのみ）。日次実行＋`sk purge [--dry-run]`
7. **ホットキー（Windowsのみ）**: pynputで `hotkey.combo` にマークトグルを割当（`enabled_windows: true` 時）。macOSは実装せずP3送り
8. **CLI** (`cli.py`): `sk start` / `sk status`（ハートビート鮮度・今日の記録数・一時停止状態） / `sk doctor` / `sk purge [--dry-run]` / `sk apikey set|status`（keyring保存。P1では検証まで: キー形式チェックのみ） / `sk autostart enable|disable`（Win: schtasks or スタートアップ / mac: launchd plist。方式は要確認→docs/00更新） / `sk backup`
9. **doctor** (`sk doctor`): OS判定 → 画面収録権限preflight＋**自己診断**（1枚撮影し、前面ウィンドウがあるのに画像がほぼ単色/壁紙のみなら権限なしと推定） → SQLiteのFTS5+trigram可用性 → ディスク空き → 自動起動状態 → APIキー設定有無。日本語でpass/failと対処法を出力
10. **ログ**: `logs/daemon.log`（RotatingFileHandler 5MB×3）。tick例外はログ＋`skipped_reason='error:...'` でデーモン継続
11. **セットアップスクリプト** (`scripts/setup.ps1`, `scripts/setup.command`): uvインストール→`uv sync`→`sk doctor`→docs/01を開く。実機で検証しdocs/01に実出力を追記

## スコープ外

Anthropic API呼び出し全般 / sessionizer / ビューア / FTS投入 / macOSホットキー / Notion・Slack

## 受入基準

1. `sk start` がWin/macで起動し、通常作業中にframesへメタ行が毎tick記録される（≥1行/45秒）。アプリ名が入り、権限があればタイトルも入る
2. 除外アプリ・除外タイトルキーワードの画面では `skipped_reason='excluded'` の行のみ記録され、**画像ファイルがディスクに存在しない**
3. トレイの一時停止で次tickから記録が止まり、再開で復帰する（15分指定は自動復帰）
4. 同一文書での連続タイピング30秒間: メタ行は毎tick、画像保存は≤3枚。ウィンドウ切替時は必ず保存される
5. FakeClockを使ったテストで、purgeが保持期間超過ファイル・行を削除し `max_gb` を守る。vault配下は削除しない
6. macOSで画面収録権限が無い場合、`sk doctor` が誤って「ok」とせず、権限不足と付与手順を表示する
7. `sk status` が稼働中ハートビート鮮度<60秒を表示する
8. 全ユニットテストがフェイクアダプタでCI相当環境（GUI・権限なし）で通る。`uv run ruff check` がクリーン
9. docs/90-verification.md のPhase 1チェックリストを実機で通し、結果（OS・日付）を同ファイルに記録する

## テスト計画

- `tests/fakes.py`: `FakeClock`（手動進行）、`FakeAdapters`（スクリプト化したWindowInfo/アイドル秒列を返す。撮影画像はPillowで文字列を描画した合成PNG=pHash差を作れる）
- `tests/conftest.py`: tmpディレクトリを `paths` に注入するfixture（`~/ScreenKnowledge` を汚さない）
- `capture/test_dedupe.py`: `should_store_image` のテーブル駆動テスト（閾値境界・window_changed・keyframe間隔・マーク中閾値・「最後に保存したフレーム」比較）
- `capture/test_daemon.py`: tick単位の統合（除外→メタ行のみ / アイドル→記録なし / 会議アプリ→低頻度 / 例外→skipped_reason='error:'でループ継続 / 日次上限到達→画像停止・メタ継続）
- `capture/test_storage.py`: WebP保存パス規約（shots/YYYY/MM/DD/<id>.webp）・縮小・purge（事前にファイルを日付偽装で配置）
- `test_db.py`: マイグレーション冪等性・WALモード・writeヘルパの直列化（2スレッド同時書込）
- `test_config.py`: example生成・キー欠落時デフォルト・不正値バリデーション
- アダプタ実体は `@pytest.mark.os_win` / `@pytest.mark.os_mac` のスモーク（import＋1回呼び出し）とし、CIではskip

## 実装の落とし穴（必読）

- **mssはスレッドセーフでない文脈がある**: mssインスタンスはキャプチャスレッド内で生成・保持する（スレッド間で共有しない）
- **Retina**: mssは物理px。保存前縮小はここで担保。`physical_scale` はbounds照合（論理px座標のWin/mac差）にのみ使用
- **pystrayのmacOSバックエンドは使わない**（メインスレッド制約・メニュー更新制限のため）。TrayAdapterのファクトリで `sys.platform == 'darwin'` → rumps実装を返す
- **rumpsはメインスレッドでrun()必須**。`sk start` の構造: main() → workers起動 → tray.run()（ブロック）→ 終了メニューでworkersへstopイベント→join
- **タイトル取得失敗を正常系として扱う**（mac権限なし・一部アプリ）。`window_title=''` で続行
- **アイドル判定の例外**: 会議アプリ前面（`meeting.apps`/`meeting.title_keywords`）ではアイドルでも記録継続（発話中は入力がないため）
- pHash比較は `imagehash.phash()` のハミング距離。16進文字列でDB保存し、比較時に復元
- ホットキー登録失敗（他アプリと衝突等）は警告ログのみでデーモンは起動継続

## 完了時の状態

ユーザーは `sk start` で記録を開始でき、除外・一時停止・自動削除が機能し、`sk status`/`sk doctor` で健全性を確認できる。データはすべてローカル。次のPhase 2でこの記録が解析され日次ログになる。

**完了時にやること**: docs/00のフェーズ表を「完了」に更新、要確認表の該当項目（#2,3,4,5,7,10）に検証結果を記入、90-verificationに実機確認結果を記録。
