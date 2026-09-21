#!/usr/bin/env bash
# Cursor Hook 用ラッパ。tool は常に Cursor。stdin の Hook JSON を ha_agent_hook.py へ渡す。
set -euo pipefail

export TOOL=Cursor
export KIND="${KIND:-adhoc}"
HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$HOOK_DIR/ha_agent_hook.py"
