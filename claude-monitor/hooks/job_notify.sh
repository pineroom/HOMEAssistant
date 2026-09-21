#!/usr/bin/env bash
# MQTT へジョブ更新を送る。TOOL は必須。未設定・未知は送らない（Claude Code に落とさない）。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"

if [[ -z "${TOOL:-}" ]]; then
  echo "job_notify.sh: TOOL is required" >&2
  exit 2
fi

PAYLOAD="${1:-}"
if [[ -z "$PAYLOAD" ]]; then
  echo "job_notify.sh: JSON payload is required" >&2
  exit 2
fi

MQTT_HOST="${MQTT_HOST:-192.168.0.30}"
MQTT_PORT="${MQTT_PORT:-1883}"
MQTT_USER="${MQTT_USER:-claude}"
MQTT_TOPIC="${MQTT_TOPIC:-claude/job_update}"

NORMALIZED="$(
  PAYLOAD="$PAYLOAD" TOOL="$TOOL" SURFACE="${SURFACE:-}" KIND="${KIND:-}" PYTHONPATH="$PYTHONPATH" python3 - <<'PY'
import json
import os
import sys

sys.path.insert(0, os.environ["PYTHONPATH"].split(":")[0])
from lib.jobs import normalize_job

raw = json.loads(os.environ["PAYLOAD"])
raw["tool"] = os.environ["TOOL"]
if os.environ.get("SURFACE"):
    raw["surface"] = os.environ["SURFACE"]
if os.environ.get("KIND"):
    raw["kind"] = os.environ["KIND"]
print(json.dumps(normalize_job(raw), ensure_ascii=False))
PY
)"

if [[ -z "${MQTT_PASS:-}" ]]; then
  echo "job_notify.sh: MQTT_PASS is unset; printing payload only" >&2
  echo "$NORMALIZED"
  exit 0
fi

if ! command -v mosquitto_pub >/dev/null 2>&1; then
  echo "job_notify.sh: mosquitto_pub not found; printing payload only" >&2
  echo "$NORMALIZED"
  exit 0
fi

mosquitto_pub \
  -h "$MQTT_HOST" \
  -p "$MQTT_PORT" \
  -u "$MQTT_USER" \
  -P "$MQTT_PASS" \
  -t "$MQTT_TOPIC" \
  -m "$NORMALIZED"
