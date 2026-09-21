#!/usr/bin/env bash
# Cloud Agents API ポールを Mac mini に入れる。キーは Git に置かない。
set -euo pipefail

SRC="$(cd "$(dirname "$0")/.." && pwd)"
DST="${CLAUDE_MONITOR_HOME:-$HOME/claude-monitor}"
PLIST_SRC="$SRC/aggregator/com.claude.cursor-poller.plist.example"
PLIST_DST="$HOME/Library/LaunchAgents/com.claude.cursor-poller.plist"

mkdir -p "$DST/aggregator" "$DST/lib" "$HOME/Library/LaunchAgents"
cp "$SRC"/aggregator/*.py "$DST"/aggregator/
cp "$SRC"/lib/*.py "$DST"/lib/
cp "$SRC"/hooks/mqtt_publish.py "$DST"/hooks/
chmod +x "$DST"/aggregator/*.py

if [[ -f "$PLIST_SRC" ]]; then
  sed "s|/Users/REPLACE|$HOME|g" "$PLIST_SRC" > "$PLIST_DST"
  echo "wrote $PLIST_DST"
fi

python3 - <<'PY'
from pathlib import Path
import os
root = Path(os.environ.get("CLAUDE_MONITOR_HOME", Path.home() / "claude-monitor"))
found = False
for path in (root / ".env", root / "hooks" / "mqtt.env", root / "state" / "mqtt.env"):
    if not path.is_file():
        continue
    for line in path.read_text().splitlines():
        if line.strip().startswith("CURSOR_API_KEY=") and line.split("=", 1)[-1].strip().strip("'").strip('"'):
            found = True
print("CURSOR_API_KEY: SET" if found else "CURSOR_API_KEY: MISSING")
PY

echo
echo "クラウド処理を出すには、~/claude-monitor/.env に次を追記してください（値は Git に置かない）:"
echo "  CURSOR_API_KEY=..."
echo "キーは Cursor の Dashboard → Cloud Agents / Integrations の API key です。"
echo
echo "1回ポール:"
echo "  PYTHONPATH=$DST python3 $DST/aggregator/run_cursor_poll.py"
echo
echo "定期実行:"
echo "  launchctl unload $PLIST_DST 2>/dev/null || true"
echo "  launchctl load $PLIST_DST"
