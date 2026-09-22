#!/usr/bin/env bash
# ~/.cursor/hooks.json に Cursor Monitor Hook を書く。既存ファイルは .bak する。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOOKS_DIR="${HOME}/.cursor"
DEST="${HOOKS_DIR}/hooks.json"
TEMPLATE="${ROOT}/hooks/cursor.hooks.json"

mkdir -p "$HOOKS_DIR"
if [[ -f "$DEST" ]]; then
  cp "$DEST" "${DEST}.bak-$(date +%Y%m%d-%H%M%S)"
fi

# Cursor は環境変数展開しないため、実パスに置換する。
sed "s|\${CLAUDE_MONITOR_HOME}|${ROOT}|g" "$TEMPLATE" > "$DEST"
chmod +x "${ROOT}/hooks/"*.sh "${ROOT}/hooks/"*.py
echo "Wrote ${DEST}"
echo "Hook command: ${ROOT}/hooks/cursor_notify.sh"
