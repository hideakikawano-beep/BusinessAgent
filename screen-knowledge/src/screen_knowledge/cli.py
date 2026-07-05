"""`sk` CLI (typer). Commands are enabled per phase.

User-facing output is Japanese. Never print the API key.
"""

from __future__ import annotations

import typer

app = typer.Typer(
    name="sk",
    help="ScreenKnowledge — PC作業の自動ナレッジ化ツール",
    no_args_is_help=True,
)


# ---- Phase 1 ----------------------------------------------------------------

@app.command()
def start() -> None:
    """デーモンを起動（トレイ常駐）。"""
    raise NotImplementedError("Phase 1")


@app.command()
def status() -> None:
    """稼働状態・今日の記録数・今月のAPIコストを表示。"""
    raise NotImplementedError("Phase 1")


@app.command()
def doctor() -> None:
    """環境診断（OS権限・SQLite/FTS5・ディスク・APIキー・自動起動）。"""
    raise NotImplementedError("Phase 1")


@app.command()
def purge(dry_run: bool = typer.Option(False, "--dry-run")) -> None:
    """保持期間・容量上限を超えたスクリーンショットを削除。"""
    raise NotImplementedError("Phase 1")


@app.command()
def backup() -> None:
    """SQLiteバックアップとvaultのzipを作成。"""
    raise NotImplementedError("Phase 1")


apikey_app = typer.Typer(help="APIキー管理（OSキーチェーン保存）")
app.add_typer(apikey_app, name="apikey")


@apikey_app.command("set")
def apikey_set() -> None:
    raise NotImplementedError("Phase 1")


@apikey_app.command("status")
def apikey_status() -> None:
    raise NotImplementedError("Phase 1")


autostart_app = typer.Typer(help="ログオン時自動起動の設定")
app.add_typer(autostart_app, name="autostart")


@autostart_app.command("enable")
def autostart_enable() -> None:
    raise NotImplementedError("Phase 1")


@autostart_app.command("disable")
def autostart_disable() -> None:
    raise NotImplementedError("Phase 1")


# ---- Phase 2 ----------------------------------------------------------------

process_app = typer.Typer(help="解析の手動実行")
app.add_typer(process_app, name="process")


@process_app.command("today")
def process_today() -> None:
    """今日の未処理セッションを通常APIで即時解析し、日次ログまで生成。"""
    raise NotImplementedError("Phase 2")


@process_app.command("now")
def process_now() -> None:
    """現在openなセッションを強制クローズして解析。"""
    raise NotImplementedError("Phase 2")


@app.command()
def collect() -> None:
    """提出済みバッチの結果を回収。"""
    raise NotImplementedError("Phase 2")


@app.command()
def usage() -> None:
    """今月のAPIコスト内訳を表示。"""
    raise NotImplementedError("Phase 2")


# ---- Phase 3 ----------------------------------------------------------------

@app.command()
def manualize(last: bool = typer.Option(False, "--last")) -> None:
    """直近のセッションを手動でマニュアル化（マークし忘れ救済）。"""
    raise NotImplementedError("Phase 3")


manuals_app = typer.Typer(help="マニュアル管理")
app.add_typer(manuals_app, name="manuals")


@manuals_app.command("list")
def manuals_list() -> None:
    raise NotImplementedError("Phase 3")


# ---- Phase 4 ----------------------------------------------------------------

@app.command()
def serve(port: int = typer.Option(None, "--port")) -> None:
    """検索・閲覧UIを起動（127.0.0.1のみ）。"""
    raise NotImplementedError("Phase 4")


@app.command()
def search(
    query: str,
    type_: str = typer.Option(None, "--type"),
    json_: bool = typer.Option(False, "--json"),
) -> None:
    """vault横断の全文検索。"""
    raise NotImplementedError("Phase 4")


@app.command()
def reindex() -> None:
    """検索インデックスを再構築（手動編集したmdの取り込みにも使用）。"""
    raise NotImplementedError("Phase 4")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
