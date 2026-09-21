#!/usr/bin/env python3
"""Claude Code / Cursor の Hook stdin をジョブ更新に変換する。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.classification import (
    ClassificationError,
    infer_cursor_surface,
    is_cursor_payload,
    normalize_tool,
)
from lib.jobs import normalize_job, stage_from_cursor_event


def read_payload() -> dict:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    return json.loads(raw)


def detect_tool(payload: dict) -> str:
    env_tool = (os.environ.get("TOOL") or "").strip()
    if env_tool:
        return normalize_tool(env_tool)
    if is_cursor_payload(payload):
        return "Cursor"
    raise ClassificationError("TOOL is required; refusing to default to Claude Code")


def job_id_from_payload(payload: dict) -> str:
    for key in ("conversation_id", "session_id", "job_id", "id"):
        value = payload.get(key)
        if value:
            return str(value)
    raise ClassificationError("empty job id")


def job_name(payload: dict, job_id: str) -> str:
    for key in ("prompt", "user_message", "title", "name"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:80]
        if isinstance(value, dict) and value.get("text"):
            return str(value["text"]).strip()[:80]
    return job_id


def build_job(payload: dict) -> dict:
    tool = detect_tool(payload)
    job_id = job_id_from_payload(payload)
    event = payload.get("hook_event_name") or payload.get("event")
    reason = payload.get("reason") or payload.get("status")
    stage, status = stage_from_cursor_event(event, reason)
    job = {
        "job_id": job_id,
        "tool": tool,
        "kind": os.environ.get("KIND") or "adhoc",
        "name": job_name(payload, job_id),
        "status": status,
        "stage": stage,
        "model": payload.get("model"),
        "hook_event_name": event,
        "reason": reason,
    }
    if tool == "Cursor":
        job["surface"] = infer_cursor_surface(
            is_background_agent=payload.get("is_background_agent"),
            name=job["name"],
            source=os.environ.get("SURFACE"),
        )
    return normalize_job(job)


def publish(job: dict) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from mqtt_publish import publish_job as publish_mqtt

    publish_mqtt(job)


def main() -> int:
    try:
        payload = read_payload()
        job = build_job(payload)
    except (ClassificationError, json.JSONDecodeError, KeyError) as exc:
        print(f"ha_agent_hook: drop update: {exc}", file=sys.stderr)
        return 0
    if os.environ.get("HA_AGENT_HOOK_STDOUT") == "1":
        print(json.dumps(job, ensure_ascii=False))
        return 0
    try:
        publish(job)
    except subprocess.CalledProcessError as exc:
        print(f"ha_agent_hook: publish failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
