#!/usr/bin/env bash
# Cursor API キーを live ツリーの .env に書く。値は表示しない。Git に置かない。
set -euo pipefail

DST="${CLAUDE_MONITOR_HOME:-$HOME/claude-monitor}"
ENV_FILE="$DST/.env"

read_key() {
  if [[ ! -t 0 ]]; then
    IFS= read -r KEY || true
    return
  fi
  if [[ -n "${1:-}" ]]; then
    KEY="$1"
    return
  fi
  if command -v pbpaste >/dev/null 2>&1; then
    KEY="$(pbpaste || true)"
    if [[ "$KEY" == crsr_* ]]; then
      echo "クリップボードのキーを使います。"
      return
    fi
  fi
  echo "API キーを貼り付けて Enter（入力は表示しません）:" >&2
  IFS= read -r -s KEY || true
  echo >&2
}

KEY=""
read_key "${1:-}"
KEY="$(printf '%s' "$KEY" | tr -d '\r' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
KEY="${KEY#CURSOR_API_KEY=}"
KEY="${KEY#export CURSOR_API_KEY=}"
KEY="$(printf '%s' "$KEY" | sed -e 's/^["'\'']//' -e 's/["'\'']$//')"

if [[ -z "$KEY" || "$KEY" == "YOUR_KEY" || "$KEY" == "..." ]]; then
  echo "キーが空です。Dashboard の作成ダイアログから全文をコピーしてください。" >&2
  exit 1
fi
if [[ "$KEY" != crsr_* ]]; then
  echo "先頭が crsr_ ではありません。一覧のマスク値ではなく、作成直後の全文を使ってください。" >&2
  exit 1
fi

mkdir -p "$DST"
umask 077
export SET_CURSOR_API_KEY_FILE="$ENV_FILE"
export SET_CURSOR_API_KEY_VALUE="$KEY"
python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ["SET_CURSOR_API_KEY_FILE"])
key = os.environ["SET_CURSOR_API_KEY_VALUE"]
path.parent.mkdir(parents=True, exist_ok=True)
lines = []
if path.is_file():
    for line in path.read_text().splitlines():
        stripped = line.strip().lstrip("\ufeff")
        if stripped.startswith("export CURSOR_API_KEY=") or stripped.startswith("CURSOR_API_KEY="):
            continue
        lines.append(line)
lines.append(f"CURSOR_API_KEY={key}")
path.write_text("\n".join(lines) + "\n")
os.chmod(path, 0o600)
print("CURSOR_API_KEY: SET")
print(f"length={len(key)} prefix=crsr_ (値は表示しません)")
print(f"wrote {path}")
PY
unset SET_CURSOR_API_KEY_VALUE SET_CURSOR_API_KEY_FILE KEY

echo
echo "確認:"
echo "  PYTHONPATH=$DST python3 $DST/aggregator/run_cursor_poll.py"
echo "  launchctl unload $HOME/Library/LaunchAgents/com.claude.cursor-poller.plist 2>/dev/null || true"
echo "  launchctl load $HOME/Library/LaunchAgents/com.claude.cursor-poller.plist"
