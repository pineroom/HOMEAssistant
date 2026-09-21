#!/usr/bin/env bash
# Cursor Hook 用ラッパ。tool は常に Cursor。既存 Claude Code の job_notify は使わない。
set -euo pipefail

export TOOL=Cursor
export KIND="${KIND:-adhoc}"
HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ -f "$HOOK_DIR/ha_agent_hook_cursor.py" ]]; then
  exec python3 "$HOOK_DIR/ha_agent_hook_cursor.py"
fi
exec python3 "$HOOK_DIR/ha_agent_hook.py"
