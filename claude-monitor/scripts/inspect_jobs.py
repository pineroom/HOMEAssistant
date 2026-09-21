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


def load() -> dict:
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
    for key in ("jobs", "items", "value"):
        value = state.get(key) if isinstance(state, dict) else None
        if isinstance(value, list):
            return value
    if isinstance(state, dict):
        attrs = state.get("attributes") or {}
        if isinstance(attrs.get("jobs"), list):
            return attrs["jobs"]
    return []


def main() -> int:
    state, path = load()
    jobs = jobs_from(state)
    counts = Counter(str(job.get("tool") or "<empty>") for job in jobs)
    print(f"file: {path}")
    print(f"jobs: {len(jobs)}")
    print("tools:")
    for tool, count in counts.most_common():
        print(f"  {tool}: {count}")
    print("latest 8:")
    for job in jobs[-8:]:
        print(
            {
                "job_id": job.get("job_id") or job.get("id"),
                "tool": job.get("tool"),
                "name": job.get("name"),
                "status": job.get("status"),
                "kind": job.get("kind"),
            }
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
