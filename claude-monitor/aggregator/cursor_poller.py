"""Cloud Agents API をポールし、Cursor ジョブ更新のリストを返す。"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from lib.classification import infer_cursor_surface
from lib.jobs import ADHOC_RETENTION, extract_model, normalize_job, parse_time, status_from_cloud_agent

DEFAULT_API = "https://api.cursor.com/v1/agents"


class CursorAPIError(RuntimeError):
    pass


def _request(url: str, api_key: str) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise CursorAPIError(f"{exc.code} {url}: {body}") from exc
    except urllib.error.URLError as exc:
        raise CursorAPIError(f"request failed {url}: {exc}") from exc


def list_agents(api_key: str, base_url: str = DEFAULT_API, limit: int = 100) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    cursor = None
    while True:
        url = f"{base_url}?limit={limit}&includeArchived=true"
        if cursor:
            url += f"&cursor={cursor}"
        payload = _request(url, api_key)
        items.extend(payload.get("items") or [])
        cursor = payload.get("nextCursor")
        if not cursor:
            break
    return items


def fetch_usage(api_key: str, agent_id: str, base_url: str = DEFAULT_API) -> dict[str, Any]:
    return _request(f"{base_url}/{agent_id}/usage", api_key)


def agent_to_job(agent: dict[str, Any]) -> dict[str, Any]:
    env = agent.get("env") or {}
    env_type = env.get("type") if isinstance(env, dict) else None
    surface = infer_cursor_surface(
        env_type=env_type,
        is_background_agent=agent.get("is_background_agent"),
        name=agent.get("name"),
        source=agent.get("source") or agent.get("origin"),
    )
    if surface == "local" and (env_type in {"cloud", "background"} or agent.get("target") == "cloud"):
        surface = "cloud"
    stage, status = status_from_cloud_agent(agent.get("status"), agent.get("run_status") or agent.get("runStatus"))
    job = {
        "job_id": agent.get("id"),
        "tool": "Cursor",
        "kind": "adhoc",
        "name": agent.get("name") or agent.get("id"),
        "status": status,
        "stage": stage,
        "surface": surface,
        "model": extract_model(agent),
        "started": agent.get("createdAt"),
        "url": agent.get("url"),
    }
    if status in {"完了", "エラー", "拒否"}:
        job["finished"] = agent.get("updatedAt")
    return normalize_job(job)


def usage_totals(usage_payload: dict[str, Any]) -> dict[str, int]:
    totals = usage_payload.get("total") or usage_payload.get("totals") or {}
    if not totals and isinstance(usage_payload.get("usage"), dict):
        totals = usage_payload["usage"]
    runs = usage_payload.get("runs") or []
    if not totals and runs:
        totals = {
            "inputTokens": sum(int((row.get("usage") or {}).get("inputTokens") or 0) for row in runs),
            "outputTokens": sum(int((row.get("usage") or {}).get("outputTokens") or 0) for row in runs),
            "cacheReadTokens": sum(int((row.get("usage") or {}).get("cacheReadTokens") or 0) for row in runs),
            "cacheWriteTokens": sum(int((row.get("usage") or {}).get("cacheWriteTokens") or 0) for row in runs),
        }
    return {
        "input_tokens": int(totals.get("inputTokens") or totals.get("input_tokens") or 0),
        "output_tokens": int(totals.get("outputTokens") or totals.get("output_tokens") or 0),
        "cache_read_tokens": int(totals.get("cacheReadTokens") or totals.get("cache_read_tokens") or 0),
        "cache_write_tokens": int(totals.get("cacheWriteTokens") or totals.get("cache_write_tokens") or 0),
    }


def summarize_usage(agents: list[dict[str, Any]], usage_by_id: dict[str, dict[str, Any]], now: Optional[datetime] = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    window_start = now - timedelta(hours=24)
    sessions = 0
    totals = {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0}
    models: list[str] = []
    last_used = None
    for agent in agents:
        started = parse_time(agent.get("createdAt") or agent.get("updatedAt"))
        if started is None or started < window_start:
            continue
        sessions += 1
        last_used = max(filter(None, [last_used, started, parse_time(agent.get("updatedAt"))]), default=started)
        usage = usage_totals(usage_by_id.get(agent.get("id"), {}))
        for key in totals:
            totals[key] += usage[key]
        model = agent.get("model")
        if isinstance(model, dict):
            model = model.get("id")
        if model and model not in models:
            models.append(str(model))
    return {
        "sessions": sessions,
        "input_tokens": totals["input_tokens"],
        "output_tokens": totals["output_tokens"],
        "cache_tokens": totals["cache_read_tokens"] + totals["cache_write_tokens"],
        "models": models[:5],
        "last_used": last_used.isoformat() if last_used else None,
        "rate_limits": {
            "available": False,
            "note": "取得不可",
        },
        "retention": ADHOC_RETENTION.total_seconds(),
    }


def poll(
    api_key: Optional[str] = None,
    *,
    include_usage: bool = False,
    fetcher=None,
    usage_fetcher=None,
) -> dict[str, Any]:
    api_key = api_key or os.environ.get("CURSOR_API_KEY")
    if not api_key:
        raise CursorAPIError("CURSOR_API_KEY is required")
    agents = fetcher(api_key) if fetcher else list_agents(api_key)
    jobs = [agent_to_job(agent) for agent in agents if agent.get("id")]
    usage_by_id: dict[str, dict[str, Any]] = {}
    if include_usage:
        for agent in agents:
            agent_id = agent.get("id")
            if not agent_id:
                continue
            try:
                usage_by_id[agent_id] = (
                    usage_fetcher(api_key, agent_id) if usage_fetcher else fetch_usage(api_key, agent_id)
                )
            except CursorAPIError:
                usage_by_id[agent_id] = {}
    return {
        "jobs": jobs,
        "usage": summarize_usage(agents, usage_by_id),
    }


def main() -> int:
    include_usage = os.environ.get("CURSOR_INCLUDE_USAGE") == "1"
    result = poll(include_usage=include_usage)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
