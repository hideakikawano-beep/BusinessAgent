# ScreenKnowledge セットアップ (Windows)
# Phase 1完了時に実機検証し、必要な調整を行うこと（docs/10 スコープ11）。
$ErrorActionPreference = "Stop"

Write-Host "=== ScreenKnowledge セットアップ ===" -ForegroundColor Cyan

# 1. uv のインストール（未導入時）
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv をインストールします..."
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

# 2. 依存関係の準備（このスクリプトの親ディレクトリ = screen-knowledge で実行）
Set-Location (Split-Path $PSScriptRoot -Parent)
uv sync

# 3. 環境診断
uv run sk doctor

Write-Host ""
Write-Host "次の手順: docs/01-setup-guide.md を参照してください" -ForegroundColor Green
Write-Host "  1. uv run sk apikey set   でAPIキーを設定"
Write-Host "  2. uv run sk start        で記録を開始"
