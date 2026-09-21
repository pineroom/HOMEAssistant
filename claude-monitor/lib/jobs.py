"""ジョブ更新の正規化、抽出、24時間削除。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional

from .classification import (
    ClassificationError,
    infer_cursor_surface,
    normalize_kind,
    normalize_surface,
    normalize_tool,
)

ACTIVE_STATUSES = ("待機中", "実行中", "権限承認待ち")
TERMINAL_STATUSES = ("完了", "エラー", "拒否")
ADHOC_RETENTION = timedelta(hours=24)

CURSOR_STAGE_TOTAL = 4

CURSOR_EVENT_STAGES = {
    "sessionstart": (1, "待機中"),
    "beforesubmitprompt": (2, "実行中"),
    "userpromptsubmit": (2, "実行中"),
    "pretooluse": (3, "実行中"),
    "posttooluse": (3, "実行中"),
    "posttoolusefailure": (3, "実行中"),
    "stop": (4, "完了"),
    "sessionend": (4, "完了"),
}

CLOUD_AGENT_ACTIVE = {"ACTIVE", "CREATING", "RUNNING", "WAITING_FOR_BACKGROUND_WORK"}
CLOUD_AGENT_ERROR = {"ERROR"}
CLOUD_RUN_ACTIVE = {"CREATING", "RUNNING"}
CLOUD_RUN_ERROR = {"ERROR", "EXPIRED"}
CLOUD_RUN_CANCELLED = {"CANCELLED"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def parse_time(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def format_time(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat()


def format_stage(index: int, total: int = CURSOR_STAGE_TOTAL) -> str:
    index = max(1, min(int(index), total))
    return f"{index}/{total}"


def stage_from_cursor_event(event_name: Optional[str], reason: Optional[str] = None) -> tuple[str, str]:
    key = (event_name or "").replace("_", "").lower()
    index, status = CURSOR_EVENT_STAGES.get(key, (2, "実行中"))
    if key in {"stop", "sessionend"}:
        reason_key = (reason or "").lower()
        if reason_key in {"error"}:
            status = "エラー"
        elif reason_key in {"aborted", "window_close", "user_close", "cancelled"}:
            status = "拒否"
        else:
            status = "完了"
    return format_stage(index), status


def status_from_cloud_agent(agent_status: Optional[str], run_status: Optional[str] = None) -> tuple[str, str]:
    run = (run_status or "").upper()
    agent = (agent_status or "").upper()
    if run in CLOUD_RUN_ERROR or agent in CLOUD_AGENT_ERROR:
        return format_stage(4), "エラー"
    if run in CLOUD_RUN_CANCELLED:
        return format_stage(4), "拒否"
    if run in CLOUD_RUN_ACTIVE or agent in CLOUD_AGENT_ACTIVE:
        return format_stage(3), "実行中"
    return format_stage(4), "完了"


def normalize_job(raw: dict[str, Any]) -> dict[str, Any]:
    job_id = str(raw.get("job_id") or raw.get("id") or "").strip()
    if not job_id:
        raise ClassificationError("job_id is required")

    tool = normalize_tool(raw.get("tool"))
    kind = normalize_kind(raw.get("kind"))
    model = raw.get("model") or None
    if model is not None:
        model = str(model).strip() or None

    if tool == "Cursor":
        surface = infer_cursor_surface(
            env_type=(raw.get("env") or {}).get("type") if isinstance(raw.get("env"), dict) else raw.get("env_type"),
            is_background_agent=raw.get("is_background_agent"),
            name=raw.get("name"),
            source=raw.get("surface") or raw.get("source"),
        )
        surface = normalize_surface(surface)
    else:
        surface = None

    stage = raw.get("stage")
    status = raw.get("status") or "実行中"
    if not stage:
        if raw.get("hook_event_name") or raw.get("event"):
            stage, inferred = stage_from_cursor_event(
                raw.get("hook_event_name") or raw.get("event"),
                raw.get("reason") or raw.get("status_reason"),
            )
            if not raw.get("status"):
                status = inferred
        else:
            stage = format_stage(int(raw.get("stage_index") or 2))

    started = parse_time(raw.get("started") or raw.get("createdAt"))
    finished = parse_time(raw.get("finished") or raw.get("updatedAt") if status in TERMINAL_STATUSES else raw.get("finished"))
    if status in TERMINAL_STATUSES and finished is None:
        finished = parse_time(raw.get("updatedAt")) or _now()
    if status in ACTIVE_STATUSES:
        finished = None

    job = {
        "job_id": job_id,
        "tool": tool,
        "kind": kind,
        "name": str(raw.get("name") or job_id).strip(),
        "status": status,
        "stage": stage,
        "model": model,
        "started": format_time(started),
        "finished": format_time(finished),
    }
    if surface:
        job["surface"] = surface
    if raw.get("url"):
        job["url"] = raw["url"]
    return job


def merge_job(jobs: Iterable[dict[str, Any]], incoming: dict[str, Any]) -> list[dict[str, Any]]:
    normalized = normalize_job(incoming)
    merged: list[dict[str, Any]] = []
    replaced = False
    for job in jobs:
        if job.get("job_id") == normalized["job_id"]:
            updated = dict(job)
            updated.update({k: v for k, v in normalized.items() if v is not None})
            if not updated.get("started"):
                updated["started"] = job.get("started")
            merged.append(normalize_job(updated))
            replaced = True
        else:
            merged.append(job)
    if not replaced:
        if not normalized.get("started"):
            normalized["started"] = format_time(_now())
        merged.append(normalized)
    return merged


def is_adhoc_expired(job: dict[str, Any], now: Optional[datetime] = None) -> bool:
    now = now or _now()
    if job.get("kind") != "adhoc":
        return False
    if job.get("status") not in {"完了"}:
        return False
    finished = parse_time(job.get("finished"))
    if finished is None:
        return False
    return now - finished >= ADHOC_RETENTION


def prune_jobs(jobs: Iterable[dict[str, Any]], now: Optional[datetime] = None) -> list[dict[str, Any]]:
    return [job for job in jobs if not is_adhoc_expired(job, now)]


def select_jobs(
    jobs: Iterable[dict[str, Any]],
    *,
    tool: str,
    kind: str = "adhoc",
) -> list[dict[str, Any]]:
    wanted = normalize_tool(tool)
    return [
        job
        for job in jobs
        if job.get("tool") == wanted and (job.get("kind") or "adhoc") == kind
    ]


def claude_adhoc_jobs(jobs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return select_jobs(jobs, tool="Claude Code", kind="adhoc")


def cursor_adhoc_jobs(jobs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return select_jobs(jobs, tool="Cursor", kind="adhoc")


def codex_adhoc_jobs(jobs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return select_jobs(jobs, tool="Codex", kind="adhoc")
