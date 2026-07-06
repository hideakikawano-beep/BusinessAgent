"""`sk` CLI (typer). Phase 1 commands are implemented; later-phase commands
print a friendly notice. User-facing output is Japanese. Never print the key.
"""

from __future__ import annotations

import datetime as dt
import platform
import sys
import threading
from pathlib import Path

import typer

from . import config as config_mod
from . import paths
from .db import SCHEMA_VERSION, Database, fts5_trigram_available

app = typer.Typer(
    name="sk",
    help="ScreenKnowledge — PC作業の自動ナレッジ化ツール",
    no_args_is_help=True,
)

KEYRING_SERVICE = "screen-knowledge"
KEYRING_USER = "anthropic"


def _todo(phase: str) -> None:
    typer.echo(f"このコマンドは {phase} で有効になります。")
    raise typer.Exit(code=0)


def _open_db() -> Database:
    paths.ensure_layout()
    db = Database(paths.db_file())
    db.migrate()
    return db


def _stored_today(db: Database, now: dt.datetime) -> int:
    n = db.scalar(
        "SELECT COUNT(*) FROM frames WHERE image_path IS NOT NULL AND date(captured_at)=date(?)",
        (now.isoformat(),),
    )
    return int(n or 0)


def _month_cost(db: Database, now: dt.datetime) -> float:
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    v = db.scalar(
        "SELECT COALESCE(SUM(cost_usd), 0) FROM api_usage WHERE ts >= ?", (start.isoformat(),)
    )
    return float(v or 0.0)


# ---- Phase 1 ----------------------------------------------------------------


@app.command()
def start() -> None:
    """デーモンを起動（トレイ常駐）。"""
    from .capture.adapters.base import TrayMenuItem, TrayMenuSpec
    from .capture.adapters.factory import make_adapters
    from .capture.daemon import CaptureDaemon
    from .logsetup import get_logger

    cfg = config_mod.load_config()
    db = _open_db()
    log = get_logger()

    try:
        adapters = make_adapters(cfg)
    except RuntimeError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc

    daemon = CaptureDaemon(cfg, db, adapters)
    stop_event = threading.Event()

    def pause_for(minutes: int | None) -> None:
        now = dt.datetime.now().astimezone()
        if minutes is None:
            daemon.pause(None)
        else:
            daemon.pause(now + dt.timedelta(minutes=minutes))

    def pause_today() -> None:
        now = dt.datetime.now().astimezone()
        daemon.pause(now.replace(hour=23, minute=59, second=59, microsecond=0))

    def quit_app() -> None:
        stop_event.set()
        adapters.tray.stop()

    menu = TrayMenuSpec(
        status_line="ScreenKnowledge: 起動中",
        items=[
            TrayMenuItem("一時停止 (15分)", lambda: pause_for(15)),
            TrayMenuItem("一時停止 (1時間)", lambda: pause_for(60)),
            TrayMenuItem("一時停止 (今日中)", pause_today),
            TrayMenuItem("一時停止 (無期限)", lambda: pause_for(None)),
            TrayMenuItem("再開", daemon.resume),
            TrayMenuItem("今の作業をマニュアル化 開始/終了", lambda: daemon.toggle_mark()),
            TrayMenuItem("今日の分を処理 (Phase 2)", None),
            TrayMenuItem("ビューアを開く (Phase 4)", None),
            TrayMenuItem("終了", quit_app),
        ],
    )

    worker = threading.Thread(target=daemon.run_forever, args=(stop_event,), daemon=True)
    worker.start()
    purge_thread = threading.Thread(
        target=_purge_scheduler, args=(cfg, db, stop_event), daemon=True
    )
    purge_thread.start()

    status_thread = threading.Thread(
        target=_status_updater, args=(daemon, adapters, db, stop_event), daemon=True
    )
    status_thread.start()

    if cfg.hotkey.enabled_windows and adapters.hotkey is not None:
        ok = adapters.hotkey.register(cfg.hotkey.combo, lambda: daemon.toggle_mark())
        if not ok:
            log.warning("ホットキーの登録に失敗しました: %s", cfg.hotkey.combo)

    typer.echo("ScreenKnowledge を起動しました。トレイアイコンから操作できます。")
    try:
        adapters.tray.run(menu)  # blocks main thread
    finally:
        stop_event.set()
        worker.join(timeout=5)
        db.close()


def _purge_scheduler(cfg: config_mod.Config, db: Database, stop_event: threading.Event) -> None:
    from .capture.storage import FrameStore
    from .logsetup import get_logger

    log = get_logger()
    store = FrameStore(cfg, db)
    while not stop_event.is_set():
        now = dt.datetime.now().astimezone()
        last = db.get_setting("last_purge_at")
        due = last is None
        if last is not None:
            try:
                due = (now - dt.datetime.fromisoformat(last)).total_seconds() >= 86400
            except ValueError:
                due = True
        if due:
            try:
                store.purge(
                    cfg.retention.screenshot_days,
                    cfg.retention.max_disk_gb,
                    metadata_days=cfg.retention.frame_metadata_days,
                )
                db.set_setting("last_purge_at", now.isoformat())
            except Exception:
                log.exception("purge failed")
        stop_event.wait(3600)


def _status_updater(daemon, adapters, db: Database, stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        now = dt.datetime.now().astimezone()
        if daemon.is_paused(now):
            state = "一時停止中"
        elif daemon.is_marked():
            state = "マニュアル化 記録中"
        else:
            state = "記録中"
        count = _stored_today(db, now)
        cost = _month_cost(db, now)
        text = f"ScreenKnowledge: {state} / 本日{count}枚 / 今月${cost:.2f}"
        try:
            adapters.tray.update_status(text)
        except Exception:
            pass
        stop_event.wait(10)


@app.command()
def status() -> None:
    """稼働状態・今日の記録数・今月のAPIコストを表示。"""
    db = _open_db()
    now = dt.datetime.now().astimezone()
    hb = db.get_setting("daemon_heartbeat")
    if hb:
        try:
            age = (now - dt.datetime.fromisoformat(hb)).total_seconds()
            running = age < 60
            hb_txt = f"{age:.0f}秒前" + ("（稼働中）" if running else "（停止の可能性）")
        except ValueError:
            hb_txt = "不明"
    else:
        hb_txt = "記録なし（未起動）"

    paused = db.get_setting("paused_until")
    marked = db.get_setting("mark_active") == "1"
    typer.echo("ScreenKnowledge 状態")
    typer.echo(f"  ハートビート: {hb_txt}")
    typer.echo(f"  一時停止: {'はい (' + paused + ')' if paused else 'いいえ'}")
    typer.echo(f"  マニュアル化マーク: {'記録中' if marked else 'オフ'}")
    typer.echo(f"  本日の保存枚数: {_stored_today(db, now)}")
    typer.echo(f"  今月のAPIコスト: ${_month_cost(db, now):.2f}")
    db.close()


@app.command()
def doctor() -> None:
    """環境診断（OS権限・SQLite/FTS5・ディスク・APIキー・自動起動）。"""
    import shutil

    ok = "✓"
    ng = "✗"
    info = "!"
    problems = 0

    typer.echo("ScreenKnowledge 環境診断")

    supported = sys.platform in ("win32", "darwin")
    typer.echo(f"  {ok if supported else ng} OS: {platform.platform()}")
    if not supported:
        typer.echo("    → Windows / macOS のみ対応しています。")
        problems += 1

    # data dir writable
    try:
        paths.ensure_layout()
        probe = paths.root() / ".sk_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        typer.echo(f"  {ok} データディレクトリ書き込み: {paths.root()}")
    except Exception as exc:
        typer.echo(f"  {ng} データディレクトリ書き込み不可: {exc}")
        problems += 1

    # sqlite / FTS5 trigram
    db = _open_db()
    trigram = db.read(fts5_trigram_available)
    if trigram:
        typer.echo(f"  {ok} SQLite FTS5 (trigram) 利用可能 / schema v{SCHEMA_VERSION}")
    else:
        typer.echo(f"  {info} SQLite FTS5 trigram 未対応 → 検索はLIKEに縮退 (Phase 4)")

    # disk space
    try:
        free_gb = shutil.disk_usage(paths.root()).free / 1024**3
        enough = free_gb >= 5
        typer.echo(f"  {ok if enough else info} ディスク空き: {free_gb:.1f} GB")
        if not enough:
            typer.echo("    → 15GB以上を推奨します。")
    except Exception as exc:
        typer.echo(f"  {info} ディスク空き取得不可: {exc}")

    # screen recording permission (macOS)
    if sys.platform == "darwin":
        try:
            from .capture.adapters.factory import make_adapters

            cfg = config_mod.load_config()
            adapters = make_adapters(cfg)
            from .capture.adapters.base import PermissionStatus

            st = adapters.screenshot.preflight()
            if st == PermissionStatus.OK:
                typer.echo(f"  {ok} 画面収録権限: 許可済み")
            elif st == PermissionStatus.MISSING_SCREEN_RECORDING:
                typer.echo(f"  {ng} 画面収録権限が未許可です")
                typer.echo("    → システム設定 > プライバシーとセキュリティ > 画面収録 で許可")
                problems += 1
            else:
                typer.echo(f"  {info} 画面収録権限: 判定不能（実行後に再確認してください）")
        except Exception as exc:
            typer.echo(f"  {info} 画面収録権限の確認に失敗: {exc}")

    # API key
    cfg = config_mod.load_config()
    key = config_mod.resolve_api_key(cfg)
    if key:
        typer.echo(f"  {ok} APIキー設定済み ({key[:6]}…) source={cfg.api.key_source}")
    else:
        typer.echo(f"  {info} APIキー未設定（Phase 1は不要 / Phase 2で `sk apikey set`）")

    db.close()
    if problems:
        typer.echo(f"\n{problems} 件の要対応項目があります。")
        raise typer.Exit(code=1)
    typer.echo("\n問題は見つかりませんでした。")


@app.command()
def purge(dry_run: bool = typer.Option(False, "--dry-run")) -> None:
    """保持期間・容量上限を超えたスクリーンショットを削除。"""
    from .capture.storage import FrameStore

    cfg = config_mod.load_config()
    db = _open_db()
    store = FrameStore(cfg, db)
    report = store.purge(
        cfg.retention.screenshot_days,
        cfg.retention.max_disk_gb,
        metadata_days=cfg.retention.frame_metadata_days,
        dry_run=dry_run,
    )
    prefix = "[dry-run] " if dry_run else ""
    typer.echo(
        f"{prefix}画像削除 {report.deleted_files} 件 "
        f"({report.freed_bytes / 1024**2:.1f} MB) / メタ行削除 {report.deleted_meta_rows} 件"
    )
    db.close()


@app.command()
def backup() -> None:
    """SQLiteバックアップとvaultのzipを作成。"""
    import zipfile

    db = _open_db()
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = paths.root() / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    db_dest = backup_dir / f"index-{stamp}.sqlite3"
    db.backup(db_dest)

    vault_zip = backup_dir / f"vault-{stamp}.zip"
    vault = paths.vault_dir()
    with zipfile.ZipFile(vault_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in vault.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(vault))
    typer.echo(f"バックアップを作成しました:\n  {db_dest}\n  {vault_zip}")
    db.close()


apikey_app = typer.Typer(help="APIキー管理（OSキーチェーン保存）")
app.add_typer(apikey_app, name="apikey")


@apikey_app.command("set")
def apikey_set() -> None:
    import keyring

    key = typer.prompt("Anthropic APIキーを貼り付けてください", hide_input=True)
    key = key.strip()
    if not key.startswith("sk-"):
        typer.echo("警告: 通常のAPIキーは 'sk-' で始まります。入力内容を確認してください。")
    keyring.set_password(KEYRING_SERVICE, KEYRING_USER, key)
    typer.echo("APIキーをOSのキーチェーンに保存しました。")


@apikey_app.command("status")
def apikey_status() -> None:
    cfg = config_mod.load_config()
    key = config_mod.resolve_api_key(cfg)
    if key:
        typer.echo(f"APIキー設定済み ({key[:6]}…) source={cfg.api.key_source}")
    else:
        typer.echo("APIキーは未設定です。`sk apikey set` で設定してください。")


autostart_app = typer.Typer(help="ログオン時自動起動の設定")
app.add_typer(autostart_app, name="autostart")


def _autostart_command() -> str:
    return f'"{sys.executable}" -m screen_knowledge start'


@autostart_app.command("enable")
def autostart_enable() -> None:
    if sys.platform == "win32":
        import subprocess

        subprocess.run(
            ["schtasks", "/create", "/tn", "ScreenKnowledge", "/tr",
             _autostart_command(), "/sc", "onlogon", "/f"],
            check=True,
        )
        typer.echo("Windowsのログオン時自動起動を有効にしました。")
    elif sys.platform == "darwin":
        plist = Path.home() / "Library/LaunchAgents/com.screenknowledge.daemon.plist"
        plist.parent.mkdir(parents=True, exist_ok=True)
        plist.write_text(
            f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.screenknowledge.daemon</string>
  <key>ProgramArguments</key>
  <array><string>{sys.executable}</string><string>-m</string><string>screen_knowledge</string><string>start</string></array>
  <key>RunAtLoad</key><true/>
</dict></plist>
""",
            encoding="utf-8",
        )
        typer.echo(f"launchd に登録しました: {plist}\n（次回ログイン時に有効になります）")
    else:
        typer.echo("このOSでは自動起動をサポートしていません。")


@autostart_app.command("disable")
def autostart_disable() -> None:
    if sys.platform == "win32":
        import subprocess

        subprocess.run(["schtasks", "/delete", "/tn", "ScreenKnowledge", "/f"], check=False)
        typer.echo("自動起動を無効にしました。")
    elif sys.platform == "darwin":
        plist = Path.home() / "Library/LaunchAgents/com.screenknowledge.daemon.plist"
        plist.unlink(missing_ok=True)
        typer.echo("launchd から削除しました。")
    else:
        typer.echo("このOSでは自動起動をサポートしていません。")


# ---- Phase 2+ (friendly placeholders) --------------------------------------

process_app = typer.Typer(help="解析の手動実行 (Phase 2)")
app.add_typer(process_app, name="process")


@process_app.command("today")
def process_today() -> None:
    _todo("Phase 2 (docs/11-phase2-analyze.md)")


@process_app.command("now")
def process_now() -> None:
    _todo("Phase 2 (docs/11-phase2-analyze.md)")


@app.command()
def collect() -> None:
    """提出済みバッチの結果を回収 (Phase 2)。"""
    _todo("Phase 2 (docs/11-phase2-analyze.md)")


@app.command()
def usage() -> None:
    """今月のAPIコスト内訳を表示 (Phase 2)。"""
    _todo("Phase 2 (docs/11-phase2-analyze.md)")


@app.command()
def manualize(last: bool = typer.Option(False, "--last")) -> None:
    """直近のセッションを手動でマニュアル化 (Phase 3)。"""
    _todo("Phase 3 (docs/12-phase3-knowledge.md)")


manuals_app = typer.Typer(help="マニュアル管理 (Phase 3)")
app.add_typer(manuals_app, name="manuals")


@manuals_app.command("list")
def manuals_list() -> None:
    _todo("Phase 3 (docs/12-phase3-knowledge.md)")


@app.command()
def serve(port: int = typer.Option(None, "--port")) -> None:
    """検索・閲覧UIを起動 (Phase 4)。"""
    _todo("Phase 4 (docs/13-phase4-viewer.md)")


@app.command()
def search(
    query: str,
    type_: str = typer.Option(None, "--type"),
    json_: bool = typer.Option(False, "--json"),
) -> None:
    """vault横断の全文検索 (Phase 4)。"""
    _todo("Phase 4 (docs/13-phase4-viewer.md)")


@app.command()
def reindex() -> None:
    """検索インデックスを再構築 (Phase 4)。"""
    _todo("Phase 4 (docs/13-phase4-viewer.md)")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
