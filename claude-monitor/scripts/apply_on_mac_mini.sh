#!/usr/bin/env bash
# overlay を ~/claude-monitor へコピーし、~/.claude/settings.json の Hook を包む。
set -euo pipefail

SRC="$(cd "$(dirname "$0")/.." && pwd)"
DST="${CLAUDE_MONITOR_HOME:-$HOME/claude-monitor}"
SETTINGS="${CLAUDE_SETTINGS:-$HOME/.claude/settings.json}"
WRAP="$DST/hooks/wrap_claude_hook.sh"

mkdir -p "$DST/lib" "$DST/hooks" "$DST/scripts" "$DST/lovelace" "$DST/aggregator"
cp "$SRC"/lib/*.py "$DST"/lib/
cp "$SRC"/aggregator/*.py "$DST"/aggregator/
cp "$SRC"/hooks/mqtt_publish.py "$DST"/hooks/
cp "$SRC"/hooks/claude_hook_guard.py "$DST"/hooks/
cp "$SRC"/hooks/wrap_claude_hook.sh "$DST"/hooks/
cp "$SRC"/hooks/cursor_notify.sh "$DST"/hooks/
cp "$SRC"/hooks/ha_agent_hook.py "$DST"/hooks/ha_agent_hook_cursor.py
cp "$SRC"/scripts/inspect_jobs.py "$DST"/scripts/
cp "$SRC"/scripts/wrap_claude_settings.py "$DST"/scripts/
cp "$SRC"/scripts/diagnose_cursor_notify.sh "$DST"/scripts/
cp "$SRC"/scripts/install_cursor_poller.sh "$DST"/scripts/
cp "$SRC"/lovelace/*.yaml "$DST"/lovelace/
chmod +x "$DST"/hooks/*.sh "$DST"/hooks/*.py "$DST"/scripts/*.py "$DST"/scripts/*.sh "$DST"/aggregator/*.py 2>/dev/null || true

mkdir -p "$HOME/.cursor"
if [[ -f "$HOME/.cursor/hooks.json" ]]; then
  cp "$HOME/.cursor/hooks.json" "$HOME/.cursor/hooks.json.bak-$(date +%Y%m%d-%H%M%S)"
fi
sed "s|\${CLAUDE_MONITOR_HOME}|${DST}|g" "$SRC/hooks/cursor.hooks.json" > "$HOME/.cursor/hooks.json"
echo "wrote $HOME/.cursor/hooks.json"

echo "copied overlay files into $DST"
echo "left existing job_notify.sh / ha_agent_hook.py untouched"

python3 "$DST/scripts/wrap_claude_settings.py" --settings "$SETTINGS" --wrap "$WRAP"

if [[ ! -f "$DST/hooks/mqtt.env" && ! -f "$DST/state/mqtt.env" && ! -f "$DST/.env" ]]; then
  echo
  echo "MQTT_PASS 用の mqtt.env がまだありません。Cursor 通知を HA へ送るには必要です。"
  echo "既存の Claude 通知が動いているなら、次で探してください:"
  echo "  grep -R MQTT_PASS -n \"$DST\" \"\$HOME/Library/LaunchAgents\" 2>/dev/null | head"
fi

echo
echo "クラウド処理はローカル Hook では出ません。API ポール:"
echo "  $DST/scripts/install_cursor_poller.sh"
