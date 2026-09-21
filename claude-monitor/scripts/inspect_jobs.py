#!/usr/bin/env python3
"""実機の jobs state から tool 内訳を出す。"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

CANDIDATES = [
    Path.home() / "claude-monitor" / "state" / "jobs_state.json",
    Path.home() / "claude-monitor" / "aggregator" / "jobs_state.json",
    Path.home() / "claude-monitor" / "state" / "jobs.json",
]


def load():
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        return json.loads(path.read_text()), path
    for path in CANDIDATES:
        if path.is_file():
            return json.loads(path.read_text()), path
    raise SystemExit("jobs state file not found")


def jobs_from(state):
    if isinstance(state, list):
        return state
    if not isinstance(state, dict):
        return []
    for key in ("jobs", "items", "value"):
        value = state.get(key)
        if isinstance(value, list):
            return value
    attrs = state.get("attributes") or {}
    if isinstance(attrs.get("jobs"), list):
        return attrs["jobs"]
    mapped = [
        value
        for value in state.values()
        if isinstance(value, dict) and (value.get("tool") or value.get("agent") or value.get("job_id"))
    ]
    return mapped


def tool_of(job: dict) -> str:
    return str(job.get("tool") or job.get("agent") or "<empty>")


def brief(job: dict) -> dict:
    return {
        "job_id": job.get("job_id") or job.get("id"),
        "tool": tool_of(job),
        "name": job.get("name"),
        "status": job.get("status"),
        "kind": job.get("kind") or job.get("type"),
        "stage": job.get("stage"),
        "model": job.get("model") or job.get("model_id"),
        "started": job.get("started"),
    }


def main() -> int:
    state, path = load()
    jobs = jobs_from(state)
    counts = Counter(tool_of(job) for job in jobs)
    print(f"file: {path}")
    print(f"jobs: {len(jobs)}")
    print("tools:")
    for tool, count in counts.most_common():
        print(f"  {tool}: {count}")
    print("cursor jobs:")
    cursor = [job for job in jobs if tool_of(job) == "Cursor"]
    if not cursor:
        print("  (none)")
    for job in cursor:
        print(brief(job))
    print("latest 8 by started:")
    ordered = sorted(jobs, key=lambda job: job.get("started") or job.get("updated") or "", reverse=True)
    for job in ordered[:8]:
        print(brief(job))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
