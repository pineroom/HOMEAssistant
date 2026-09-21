#!/usr/bin/env python3
"""Cloud Agents をポールして jobs_state に合流し、MQTT でも HA へ送る。"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "hooks"))

from aggregator.cursor_limits import fetch_cursor_limits, limits_to_jobs, upsert_limit_jobs
from aggregator.cursor_poller import CursorAPIError, poll
from aggregator.jobs_store import merge_poller_jobs, sanitize_jobs
from lib.jobs import prune_jobs
from mqtt_publish import cursor_api_key_diagnostics, load_env_files, publish_cursor_limits, publish_job, publish_usage


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"jobs": [], "usage": {}}
    return json.loads(path.read_text())


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")


def publish_cursor_jobs(jobs: list) -> int:
    sent = 0
    for job in jobs:
        if job.get("tool") != "Cursor":
            continue
        try:
            publish_job(job)
            sent += 1
        except Exception as exc:  # noqa: BLE001
            print(f"run_cursor_poll: mqtt failed {job.get('job_id')}: {exc}", file=sys.stderr)
    return sent


def main() -> int:
    load_env_files()
    state_path = Path(os.environ.get("CLAUDE_MONITOR_STATE", ROOT / "aggregator" / "jobs_state.json"))
    include_usage = os.environ.get("CURSOR_INCLUDE_USAGE", "1") == "1"
    state = load_state(state_path)
    jobs = sanitize_jobs(state.get("jobs") or [])
    exit_code = 0
    result = None
    try:
        result = poll(include_usage=include_usage)
    except CursorAPIError as exc:
        print(f"run_cursor_poll: {exc}", file=sys.stderr)
        if "CURSOR_API_KEY" in str(exc):
            diag = cursor_api_key_diagnostics()
            for row in diag["files"]:
                if not row["exists"]:
                    note = "file missing"
                elif row["has_key"]:
                    note = "CURSOR_API_KEY present"
                else:
                    note = "no CURSOR_API_KEY line"
                print(f"  {row['path']}: {note}", file=sys.stderr)
            helper = ROOT / "scripts" / "set_cursor_api_key.sh"
            print(
                "キーは Dashboard で作っただけでは入りません。"
                f" ~/claude-monitor/.env へ書いてください: pbpaste | {helper}",
                file=sys.stderr,
            )
        exit_code = 1
    if result:
        jobs = merge_poller_jobs(jobs, result["jobs"])
        jobs = prune_jobs(jobs)
        cursor_usage = dict(result["usage"] or {})
        mqtt_jobs = result["jobs"]
    else:
        cursor_usage = dict((state.get("usage") or {}).get("cursor") or {})
        mqtt_jobs = []
    previous_limits = ((state.get("usage") or {}).get("cursor") or {}).get("rate_limits")
    cursor_usage["rate_limits"] = fetch_cursor_limits(previous=previous_limits)
    jobs = upsert_limit_jobs(jobs, cursor_usage.get("rate_limits"))
    usage = dict(state.get("usage") or {})
    usage["cursor"] = cursor_usage
    state = {"jobs": jobs, "usage": usage}
    save_state(state_path, state)
    mqtt_sent = publish_cursor_jobs(mqtt_jobs)
    limits_mqtt = 0
    try:
        publish_usage({"cursor": cursor_usage})
        publish_cursor_limits(cursor_usage.get("rate_limits") or {})
        for job in limits_to_jobs(cursor_usage.get("rate_limits")):
            publish_job(job)
            limits_mqtt += 1
    except Exception as exc:  # noqa: BLE001
        print(f"run_cursor_poll: usage mqtt failed: {exc}", file=sys.stderr)
    print(
        json.dumps(
            {
                "job_count": len(jobs),
                "cursor_jobs": sum(1 for job in jobs if job.get("tool") == "Cursor"),
                "polled": len(mqtt_jobs),
                "mqtt_sent": mqtt_sent,
                "limits": cursor_usage.get("rate_limits", {}).get("available"),
                "limits_note": cursor_usage.get("rate_limits", {}).get("note") or "",
                "limits_mqtt": limits_mqtt,
            },
            ensure_ascii=False,
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
