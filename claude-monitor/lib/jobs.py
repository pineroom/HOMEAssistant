"""ジョブ更新の正規化、抽出、24時間削除。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional
import re

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

UUID_NAME_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def is_generic_job_name(name: Any, job_id: Any = None) -> bool:
    """UUID や job_id そのものは表示名として使わない。"""
    text = str(name or "").strip()
    if not text:
        return True
    if job_id is not None and text == str(job_id).strip():
        return True
    return bool(UUID_NAME_RE.match(text))


PLACEHOLDER_MODELS = {"", "default", "auto", "inherit", "none", "null", "string", "-"}
MODEL_KEYS = ("model", "model_id", "modelId", "chat_model", "llm", "selectedModel")
NESTED_MODEL_CONTAINERS = ("latestRun", "latest_run", "run", "config", "settings")


def normalize_model_label(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    if isinstance(raw, dict):
        raw = raw.get("id") or raw.get("name") or raw.get("slug") or raw.get("model")
    text = str(raw).strip()
    if not text or text.lower() in PLACEHOLDER_MODELS:
        return None
    return text[:80]


def extract_model(payload: Optional[dict[str, Any]], *, _depth: int = 0) -> Optional[str]:
    if not payload or not isinstance(payload, dict) or _depth > 3:
        return None
    for key in MODEL_KEYS:
        label = normalize_model_label(payload.get(key))
        if label:
            return label
    for key in NESTED_MODEL_CONTAINERS:
        nested = payload.get(key)
        if isinstance(nested, dict):
            label = extract_model(nested, _depth=_depth + 1)
            if label:
                return label
    return None


def display_stage(job: dict[str, Any]) -> str:
    """HA 実機は stage が空でも status/progress から 1/4〜4/4 を出す。"""
    stage = job.get("stage")
    if stage and str(stage) not in {"None", "-", "null"}:
        return str(stage)
    progress = job.get("progress")
    try:
        progress_i = int(progress)
    except (TypeError, ValueError):
        progress_i = None
    status = str(job.get("status") or "")
    if status in TERMINAL_STATUSES or progress_i == 100:
        return format_stage(4)
    if status == "権限承認待ち" or (progress_i is not None and progress_i >= 70):
        return format_stage(3)
    if status == "待機中" or progress_i in {1, 10}:
        return format_stage(1)
    if status == "実行中" or (progress_i is not None and progress_i >= 30):
        return format_stage(2)
    return "-"


def display_model(job: dict[str, Any]) -> str:
    return extract_model(job) or "-"


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
    model = extract_model(raw)

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
            incoming_fields = {k: v for k, v in normalized.items() if v is not None}
            if is_generic_job_name(incoming_fields.get("name"), normalized["job_id"]) and not is_generic_job_name(
                job.get("name"), job.get("job_id")
            ):
                incoming_fields.pop("name", None)
            updated.update(incoming_fields)
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
