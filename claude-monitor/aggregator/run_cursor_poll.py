#!/usr/bin/env python3
"""Cloud Agents をポールして jobs_state に合流する。launchd / aggregator から呼ぶ。"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aggregator.cursor_poller import poll
from aggregator.jobs_store import merge_poller_jobs, sanitize_jobs
from lib.jobs import prune_jobs


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"jobs": [], "usage": {}}
    return json.loads(path.read_text())


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")


def main() -> int:
    state_path = Path(os.environ.get("CLAUDE_MONITOR_STATE", ROOT / "aggregator" / "jobs_state.json"))
    include_usage = os.environ.get("CURSOR_INCLUDE_USAGE", "1") == "1"
    state = load_state(state_path)
    jobs = sanitize_jobs(state.get("jobs") or [])
    result = poll(include_usage=include_usage)
    jobs = merge_poller_jobs(jobs, result["jobs"])
    jobs = prune_jobs(jobs)
    usage = dict(state.get("usage") or {})
    usage["cursor"] = result["usage"]
    state = {"jobs": jobs, "usage": usage}
    save_state(state_path, state)
    print(json.dumps({"job_count": len(jobs), "cursor_jobs": sum(1 for job in jobs if job.get("tool") == "Cursor")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
