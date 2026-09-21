#!/usr/bin/env python3
"""Cursor ジョブを MQTT へ直接送る。既存 job_notify.sh は使わない。"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.jobs import normalize_job

ENV_RELATIVE = (".env", "hooks/mqtt.env", "state/mqtt.env")


def parse_env_line(line: str):
    line = line.strip().lstrip("\ufeff")
    if not line or line.startswith("#") or "=" not in line:
        return None
    if line.startswith("export "):
        line = line[len("export ") :].strip()
    key, value = line.split("=", 1)
    key = key.strip()
    value = value.strip().strip("'").strip('"')
    if not key:
        return None
    return key, value


def env_file_candidates(extra_roots=None, include_defaults=True):
    roots = []
    if include_defaults:
        roots.append(ROOT)
        roots.append(Path(os.environ.get("CLAUDE_MONITOR_HOME", Path.home() / "claude-monitor")))
    for extra in extra_roots or ():
        roots.append(Path(extra))
    seen = set()
    paths = []
    for root in roots:
        for relative in ENV_RELATIVE:
            path = (root / relative).resolve()
            if path in seen:
                continue
            seen.add(path)
            paths.append(path)
    return paths


def load_env_files(extra_roots=None, include_defaults=True) -> None:
    for path in env_file_candidates(extra_roots, include_defaults=include_defaults):
        if not path.is_file():
            continue
        for line in path.read_text().splitlines():
            parsed = parse_env_line(line)
            if not parsed:
                continue
            key, value = parsed
            existing = os.environ.get(key)
            if existing is None or not str(existing).strip():
                os.environ[key] = value


def cursor_api_key_diagnostics(extra_roots=None, include_defaults=True) -> dict:
    files = []
    for path in env_file_candidates(extra_roots, include_defaults=include_defaults):
        has_key = False
        exists = path.is_file()
        if exists:
            for line in path.read_text().splitlines():
                parsed = parse_env_line(line)
                if parsed and parsed[0] == "CURSOR_API_KEY" and parsed[1]:
                    has_key = True
                    break
        files.append({"path": str(path), "exists": exists, "has_key": has_key})
    key = (os.environ.get("CURSOR_API_KEY") or "").strip()
    return {"set": bool(key), "files": files}


def to_mqtt_payload(job: dict) -> dict:
    """実機 aggregator が agent/type/progress を読む場合に備えて別名も付ける。"""
    normalized = normalize_job(job)
    out = dict(normalized)
    out["agent"] = normalized["tool"]
    out["type"] = normalized["kind"]
    out["id"] = normalized["job_id"]
    if normalized.get("model"):
        out["model_id"] = normalized["model"]
        out["llm"] = normalized["model"]
    status = normalized.get("status") or ""
    if status in {"完了", "エラー", "拒否"}:
        out["progress"] = 100
    else:
        stage = str(normalized.get("stage") or "2/4")
        try:
            index = int(stage.split("/")[0])
        except ValueError:
            index = 2
        out["progress"] = {1: 10, 2: 30, 3: 70, 4: 100}.get(index, 30)
    return out


def find_mosquitto_pub():
    candidates = [
        shutil.which("mosquitto_pub"),
        "/opt/homebrew/bin/mosquitto_pub",
        "/usr/local/bin/mosquitto_pub",
    ]
    for path in candidates:
        if path and os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def publish_job(job: dict) -> None:
    load_env_files()
    payload_obj = to_mqtt_payload(job)
    payload = json.dumps(payload_obj, ensure_ascii=False)
    host = os.environ.get("MQTT_HOST", "192.168.0.30")
    port = os.environ.get("MQTT_PORT", "1883")
    user = os.environ.get("MQTT_USER", "claude")
    password = os.environ.get("MQTT_PASS") or os.environ.get("MQTT_PASSWORD")
    topic = os.environ.get("MQTT_TOPIC", "claude/job_update")
    binary = find_mosquitto_pub()
    if not password or not binary:
        print(payload)
        if not password:
            print("mqtt_publish: MQTT_PASS is unset", file=sys.stderr)
        if not binary:
            print("mqtt_publish: mosquitto_pub not found", file=sys.stderr)
        return
    subprocess.run(
        [
            binary,
            "-h",
            host,
            "-p",
            str(port),
            "-u",
            user,
            "-P",
            password,
            "-t",
            topic,
            "-m",
            payload,
        ],
        check=True,
    )


if __name__ == "__main__":
    raw = json.loads(sys.argv[1])
    publish_job(raw)
