#!/usr/bin/env bash
# Cursor 通知が HA まで届くかを実機で切り分ける。
set -euo pipefail

DST="${CLAUDE_MONITOR_HOME:-$HOME/claude-monitor}"
echo "== files =="
ls -l "$DST/hooks/cursor_notify.sh" "$DST/hooks/ha_agent_hook_cursor.py" "$DST/hooks/mqtt_publish.py" "$HOME/.cursor/hooks.json" || true
echo
echo "== ~/.cursor/hooks.json =="
python3 -m json.tool "$HOME/.cursor/hooks.json" 2>/dev/null | head -n 80 || cat "$HOME/.cursor/hooks.json"

echo
echo "== mqtt env keys (values hidden) =="
python3 - <<'PY'
from pathlib import Path
import os
root = Path(os.environ.get("CLAUDE_MONITOR_HOME", Path.home() / "claude-monitor"))
found = False
for path in (root / "hooks" / "mqtt.env", root / "state" / "mqtt.env", root / ".env"):
    if not path.is_file():
        continue
    found = True
    print(f"file: {path}")
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        print(f"  {key.strip()}: {'SET' if value.strip() else 'EMPTY'}")
if not found:
    print("mqtt.env not found")
PY

echo
echo "== mosquitto_pub =="
command -v mosquitto_pub || echo "NOT FOUND"

echo
echo "== live notify --help =="
python3 "$DST/hooks/ha_agent_hook.py" notify --help 2>&1 | head -n 50 || true

echo
echo "== hook log (last 80 lines) =="
if [[ -f "$DST/state/cursor_hook.log" ]]; then
  tail -n 80 "$DST/state/cursor_hook.log"
else
  echo "(no log yet — 1+1 のとき Hook が走っていない可能性が高い)"
fi

echo
echo "== test publish: Cursor 診断テスト =="
JOB_ID="cursor-diag-$(date +%H%M%S)"
printf '%s\n' "{\"conversation_id\":\"$JOB_ID\",\"generation_id\":\"gen-$JOB_ID\",\"hook_event_name\":\"beforeSubmitPrompt\",\"prompt\":\"Cursor 診断テスト\",\"composer_mode\":\"agent\"}" | "$DST/hooks/cursor_notify.sh"
echo "published job_id=$JOB_ID"

echo
echo "== inspect jobs =="
python3 "$DST/scripts/inspect_jobs.py" || true

echo
echo "HA の claude-monitor-live を再読み込みし、Cursor カードか jobs に『Cursor 診断テスト』が出るか見てください。"
echo "出ない場合はこのコマンドの出力全体を貼ってください。"
