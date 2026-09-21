#!/usr/bin/env bash
# 既存 Claude Code Hook の先頭に置く。Cursor 由来なら Cursor 経路へ回し、Claude 通知はしない。
set -euo pipefail

HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HOOK_DIR/.." && pwd)"
LOG="$ROOT/state/cursor_hook.log"
mkdir -p "$ROOT/state"

INPUT="$(cat)"
if printf '%s' "$INPUT" | python3 "$HOOK_DIR/claude_hook_guard.py" >/dev/null; then
  echo "wrap: route=cursor $(date '+%Y-%m-%dT%H:%M:%S')" >> "$LOG" || true
  printf '%s' "$INPUT" | "$HOOK_DIR/cursor_notify.sh"
  exit 0
fi
echo "wrap: route=claude $(date '+%Y-%m-%dT%H:%M:%S')" >> "$LOG" || true
if [[ "$#" -eq 0 ]]; then
  exit 0
fi
# PreToolUse の `TOOL_LABEL=... JOB_ID=... cmd` も env 経由でそのまま実行する。
printf '%s' "$INPUT" | env "$@"
