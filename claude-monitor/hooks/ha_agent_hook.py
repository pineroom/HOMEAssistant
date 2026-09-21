#!/usr/bin/env python3
"""Claude Code / Cursor の Hook stdin をジョブ更新に変換する。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
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

JOB_ID_KEYS = (
    "conversation_id",
    "session_id",
    "generation_id",
    "job_id",
    "id",
    "composer_id",
    "conversationId",
    "sessionId",
)


def log_line(message: str) -> None:
    path = ROOT / "state" / "cursor_hook.log"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        path.open("a", encoding="utf-8").write(f"ha_agent_hook: {stamp} {message}\n")
    except OSError:
        pass


def read_payload() -> dict:
    raw = sys.stdin.read().strip().lstrip("\ufeff")
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
    for key in JOB_ID_KEYS:
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


def progress_for_job(job: dict) -> int:
    status = job.get("status") or ""
    if status in {"完了", "エラー", "拒否"}:
        return 100
    stage = str(job.get("stage") or "2/4")
    try:
        index = int(stage.split("/")[0])
    except ValueError:
        index = 2
    return {1: 10, 2: 30, 3: 70, 4: 100}.get(index, 30)


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


def publish_via_live_notify(job: dict) -> None:
    """実機の `ha_agent_hook.py notify --agent ...` が使えるなら同じ経路でも送る。"""
    live = Path(__file__).resolve().parent / "ha_agent_hook.py"
    if live.resolve() == Path(__file__).resolve() or not live.is_file():
        return
    try:
        text = live.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    if "notify" not in text:
        return
    env = os.environ.copy()
    env["JOB_ID"] = job["job_id"]
    cmd = [
        sys.executable,
        str(live),
        "notify",
        "--agent",
        job["tool"],
        "--type",
        job.get("kind") or "adhoc",
        "--name",
        job["name"],
        "--status",
        job["status"],
        "--progress",
        str(progress_for_job(job)),
    ]
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=20, check=False)
    log_line(f"live_notify exit={result.returncode} stderr={result.stderr.strip()[:300]}")
    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)


def publish(job: dict) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from mqtt_publish import publish_job as publish_mqtt

    mqtt_error = None
    try:
        publish_mqtt(job)
        log_line(f"mqtt ok job_id={job.get('job_id')} name={job.get('name')}")
    except Exception as exc:  # noqa: BLE001 — 実機では live notify へフォールバックする
        mqtt_error = exc
        log_line(f"mqtt failed: {exc}")
    try:
        publish_via_live_notify(job)
        return
    except Exception as exc:  # noqa: BLE001
        log_line(f"live_notify failed: {exc}")
        if mqtt_error is not None:
            raise mqtt_error


def main() -> int:
    try:
        payload = read_payload()
        job = build_job(payload)
    except (ClassificationError, json.JSONDecodeError, KeyError) as exc:
        log_line(f"drop update: {exc}")
        print(f"ha_agent_hook: drop update: {exc}", file=sys.stderr)
        return 0
    if os.environ.get("HA_AGENT_HOOK_STDOUT") == "1":
        print(json.dumps(job, ensure_ascii=False))
        return 0
    try:
        publish(job)
    except subprocess.CalledProcessError as exc:
        log_line(f"publish failed: {exc}")
        print(f"ha_agent_hook: publish failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
