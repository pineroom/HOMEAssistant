#!/usr/bin/env bash
# 既存 Claude Code Hook の先頭に置く。Cursor 由来なら Cursor 経路へ回し、Claude 通知はしない。
set -euo pipefail

HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
INPUT="$(cat)"
if printf '%s' "$INPUT" | python3 "$HOOK_DIR/claude_hook_guard.py" >/dev/null; then
  printf '%s' "$INPUT" | "$HOOK_DIR/cursor_notify.sh"
  exit 0
fi
if [[ "$#" -eq 0 ]]; then
  exit 0
fi
printf '%s' "$INPUT" | "$@"
