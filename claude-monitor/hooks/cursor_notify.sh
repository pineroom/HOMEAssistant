#!/usr/bin/env bash
# Cursor Hook 用ラッパ。tool は常に Cursor。既存 Claude Code の job_notify は使わない。
set -euo pipefail

export TOOL=Cursor
export KIND="${KIND:-adhoc}"
export PATH="/opt/homebrew/bin:/usr/local/bin:${PATH:-/usr/bin:/bin}"
HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HOOK_DIR/.." && pwd)"
LOG="$ROOT/state/cursor_hook.log"
mkdir -p "$ROOT/state"

INPUT="$(cat)"
{
  echo "----- $(date '+%Y-%m-%dT%H:%M:%S') pid=$$ -----"
  echo "python=$(command -v python3 || true) mosq=$(command -v mosquitto_pub || true)"
  echo "$INPUT"
} >> "$LOG" || true

PY="$HOOK_DIR/ha_agent_hook_cursor.py"
if [[ ! -f "$PY" ]]; then
  PY="$HOOK_DIR/ha_agent_hook.py"
fi

set +e
printf '%s' "$INPUT" | python3 "$PY" >>"$LOG" 2>&1
rc=$?
set -e
echo "cursor_notify: python_exit=$rc" >> "$LOG" || true

# Cursor は stdout の JSON を Hook 応答とみなすことがある。MQTT の JSON は出さない。
printf '%s\n' '{"continue":true}'
exit 0
