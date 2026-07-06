#!/bin/bash
# ScreenKnowledge セットアップ (macOS)
# Phase 1完了時に実機検証し、必要な調整を行うこと（docs/10 スコープ11）。
set -euo pipefail

echo "=== ScreenKnowledge セットアップ ==="

# 1. uv のインストール（未導入時）
if ! command -v uv >/dev/null 2>&1; then
    echo "uv をインストールします..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# 2. 依存関係の準備（このスクリプトの親ディレクトリ = screen-knowledge で実行）
cd "$(dirname "$0")/.."
uv sync

# 3. 環境診断（画面収録権限が未許可の場合はここで案内が出る）
uv run sk doctor

echo ""
echo "次の手順: docs/01-setup-guide.md を参照してください"
echo "  1. システム設定 > プライバシーとセキュリティ > 画面収録 で許可"
echo "  2. uv run sk apikey set   でAPIキーを設定"
echo "  3. uv run sk start        で記録を開始"
