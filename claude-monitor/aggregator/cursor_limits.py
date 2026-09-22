"""Cursor Models / Other Models / Grok Bot の制限表示。Cloud Agents API では取れない。"""

from __future__ import annotations

import base64
import json
import os
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

USAGE_SUMMARY_URL = "https://cursor.com/api/usage-summary"
SAND_USAGE_URL = "https://cursor.com/api/dashboard/get-sand-usage-status"
CACHE_SECONDS = 300
BAR_WIDTH = 20

WINDOW_SPECS = (
    {"id": "cursor-models", "label": "Cursor Models"},
    {"id": "other-models", "label": "Other Models"},
    {"id": "grok-bot", "label": "Grok Bot"},
)
LIMIT_JOB_PREFIX = "cursor-limit-"


def empty_window(spec: dict[str, str], note: str = "取得不可") -> dict[str, Any]:
    return {
        "id": spec["id"],
        "label": spec["label"],
        "percent": None,
        "percent_label": "-",
        "bar": "-" * BAR_WIDTH,
        "reset": "-",
        "note": note,
    }


def unavailable(note: str = "取得不可", **extra: Any) -> dict[str, Any]:
    return {
        "available": False,
        "note": note,
        "windows": [empty_window(spec, note) for spec in WINDOW_SPECS],
        **extra,
    }


def normalize_percent(value: Any) -> Optional[float]:
    if value is None or value is False:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    if number < 0:
        number = 0.0
    if number <= 1.0:
        number *= 100.0
    return round(min(number, 100.0), 1)


def usage_bar(percent: Optional[float], width: int = BAR_WIDTH) -> str:
    if percent is None:
        return "-" * width
    filled = int(round(max(0.0, min(100.0, percent)) / 100.0 * width))
    filled = max(0, min(width, filled))
    if filled <= 0:
        return "-" * width
    if filled >= width:
        return "*" * width
    return "*" * (filled - 1) + "_" + "-" * (width - filled)


def format_reset(value: Any, now: Optional[datetime] = None) -> str:
    if value in (None, ""):
        return "-"
    text = str(value).strip()
    parsed: Optional[datetime] = None
    try:
        numeric = float(text)
        if numeric > 10_000_000_000:
            numeric /= 1000.0
        parsed = datetime.fromtimestamp(numeric, tz=timezone.utc)
    except (TypeError, ValueError):
        iso = text
        if iso.endswith("Z"):
            iso = iso[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(iso)
        except ValueError:
            return "-"
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    local = parsed.astimezone()
    return local.strftime("%m/%d %H:%M")


def percent_label(percent: Optional[float]) -> str:
    if percent is None:
        return "-"
    return f"{percent:.1f}%"


def filled_window(spec: dict[str, str], percent: Optional[float], reset: str, note: str = "") -> dict[str, Any]:
    return {
        "id": spec["id"],
        "label": spec["label"],
        "percent": percent,
        "percent_label": percent_label(percent),
        "bar": usage_bar(percent),
        "reset": reset or "-",
        "note": note,
    }


def decode_vscdb_value(raw: Any) -> str:
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        if b"\x00" in raw[:8] and not raw.startswith(b"eyJ"):
            text = raw.decode("utf-16-le", errors="ignore")
        else:
            text = raw.decode("utf-8", errors="ignore")
    else:
        text = str(raw)
    text = text.strip().strip("\x00").strip()
    if text.startswith('"') and text.endswith('"'):
        try:
            text = json.loads(text)
        except json.JSONDecodeError:
            text = text.strip('"')
    return str(text).strip()


def jwt_claims(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    payload = parts[1]
    payload += "=" * (-len(payload) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
    except (ValueError, json.JSONDecodeError, UnicodeError):
        return {}


def cookie_header_value(token: str) -> str:
    token = token.strip()
    if not token:
        return ""
    if "%3A%3A" in token or "%3a%3a" in token:
        return token
    if "::" in token:
        return urllib.parse.quote(token, safe="")
    sub = jwt_claims(token).get("sub")
    if sub:
        return urllib.parse.quote(f"{sub}::{token}", safe="")
    return urllib.parse.quote(token, safe="")


def vscdb_paths() -> list[Path]:
    override = os.environ.get("CURSOR_VSCDB")
    if override:
        return [Path(override)]
    home = Path.home()
    xdg = os.environ.get("XDG_CONFIG_HOME")
    paths = [
        home / "Library/Application Support/Cursor/User/globalStorage/state.vscdb",
    ]
    if xdg:
        paths.append(Path(xdg) / "Cursor/User/globalStorage/state.vscdb")
    paths.append(home / ".config/Cursor/User/globalStorage/state.vscdb")
    return paths


def read_access_token_from_vscdb(path: Path) -> str:
    if not path.is_file():
        return ""
    conn = None
    for uri in (f"file:{path}?mode=ro", f"file:{path}?mode=ro&immutable=1"):
        try:
            conn = sqlite3.connect(uri, uri=True)
            break
        except sqlite3.Error:
            continue
    if conn is None:
        return ""
    try:
        row = conn.execute(
            "SELECT value FROM ItemTable WHERE key = ? LIMIT 1",
            ("cursorAuth/accessToken",),
        ).fetchone()
    except sqlite3.Error:
        return ""
    finally:
        conn.close()
    if not row:
        return ""
    return decode_vscdb_value(row[0])


def load_session_token() -> tuple[str, str]:
    env_cookie = (os.environ.get("CURSOR_SESSION_COOKIE") or "").strip()
    if env_cookie:
        return env_cookie, "env"
    for path in vscdb_paths():
        token = read_access_token_from_vscdb(path)
        if token:
            return token, "vscdb"
    return "", "missing"


def _request_json(url: str, cookie: str, *, data: Optional[bytes] = None, timeout: int = 15) -> dict[str, Any]:
    headers = {
        "Accept": "application/json",
        "Cookie": f"WorkosCursorSessionToken={cookie}",
        "User-Agent": "claude-monitor-cursor-limits",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
        headers["Origin"] = "https://cursor.com"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{exc.code} {url}: {body[:200]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"request failed {url}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"unexpected payload from {url}")
    return payload


def individual_plan(summary: dict[str, Any]) -> dict[str, Any]:
    individual = summary.get("individualUsage") or {}
    if not isinstance(individual, dict):
        return {}
    plan = individual.get("plan") or individual.get("overall") or {}
    return plan if isinstance(plan, dict) else {}


def parse_plan_windows(summary: dict[str, Any], now: Optional[datetime] = None) -> list[dict[str, Any]]:
    plan = individual_plan(summary)
    reset = format_reset(summary.get("billingCycleEnd") or summary.get("endOfMonth"), now=now)
    cursor_pct = normalize_percent(plan.get("autoPercentUsed"))
    other_pct = normalize_percent(plan.get("apiPercentUsed"))
    if cursor_pct is None and other_pct is None:
        cursor_pct = normalize_percent(plan.get("totalPercentUsed"))
    return [
        filled_window(WINDOW_SPECS[0], cursor_pct, reset),
        filled_window(WINDOW_SPECS[1], other_pct, reset),
    ]


def parse_grok_window(sand: Optional[dict[str, Any]], now: Optional[datetime] = None) -> dict[str, Any]:
    spec = WINDOW_SPECS[2]
    if not sand:
        return empty_window(spec)
    if sand.get("hasNonZeroIncludedLimit") is False:
        return empty_window(spec, "枠なし")
    percent = normalize_percent(sand.get("usagePercent") or sand.get("usedPercent"))
    reset = format_reset(sand.get("nextResetTimestampUtc") or sand.get("resetsAt"), now=now)
    if percent is None:
        return empty_window(spec)
    return filled_window(spec, percent, reset)


def limits_from_payloads(
    summary: Optional[dict[str, Any]],
    sand: Optional[dict[str, Any]] = None,
    *,
    now: Optional[datetime] = None,
    auth_source: str = "",
) -> dict[str, Any]:
    if not summary:
        return unavailable("取得不可", auth_source=auth_source)
    plan_windows = parse_plan_windows(summary, now=now)
    grok = parse_grok_window(sand, now=now)
    windows = plan_windows + [grok]
    available = any(row.get("percent") is not None for row in windows)
    note = "" if available else "取得不可"
    return {
        "available": available,
        "note": note,
        "auth_source": auth_source,
        "windows": windows,
    }


def _cache_fresh(previous: Optional[dict[str, Any]], now: datetime) -> bool:
    if not previous or not previous.get("available"):
        return False
    fetched = previous.get("fetched_at")
    if not fetched:
        return False
    try:
        stamp = datetime.fromisoformat(str(fetched).replace("Z", "+00:00"))
    except ValueError:
        return False
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return now - stamp <= timedelta(seconds=CACHE_SECONDS)


def fetch_cursor_limits(
    *,
    previous: Optional[dict[str, Any]] = None,
    now: Optional[datetime] = None,
    requester=None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if _cache_fresh(previous, now):
        return previous
    token, auth_source = load_session_token()
    if not token:
        stale = dict(previous or unavailable("Cursor.app にログインしてください"))
        stale["note"] = "Cursor.app にログインしてください"
        stale["auth_source"] = auth_source
        return stale if previous and previous.get("windows") else unavailable(
            "Cursor.app にログインしてください", auth_source=auth_source
        )
    cookie = cookie_header_value(token)
    get_json = requester or _request_json
    try:
        summary = get_json(USAGE_SUMMARY_URL, cookie)
    except Exception as exc:  # noqa: BLE001
        if previous and previous.get("available"):
            kept = dict(previous)
            kept["note"] = f"更新失敗のため前回値: {exc}"
            return kept
        return unavailable(str(exc), auth_source=auth_source)
    sand = None
    try:
        sand = get_json(SAND_USAGE_URL, cookie, data=b"{}")
    except Exception:  # noqa: BLE001
        sand = None
    result = limits_from_payloads(summary, sand, now=now, auth_source=auth_source)
    result["fetched_at"] = now.isoformat()
    return result


def is_limit_job(job: dict[str, Any]) -> bool:
    job_id = str(job.get("job_id") or job.get("id") or "")
    return job_id.startswith(LIMIT_JOB_PREFIX)


def limits_to_jobs(limits: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    """HA の jobs 配列に載せる。name/stage/model/status だけ使う（aggregator が既知フィールドしか残さないため）。"""
    by_id = {row.get("id"): row for row in (limits or {}).get("windows") or []}
    jobs = []
    for index, spec in enumerate(WINDOW_SPECS, 1):
        row = by_id.get(spec["id"]) or empty_window(spec)
        jobs.append(
            {
                "job_id": f"{LIMIT_JOB_PREFIX}{index}-{spec['id']}",
                "tool": "Cursor",
                "kind": "adhoc",
                "name": spec["label"],
                "status": row.get("reset") or "-",
                "stage": row.get("percent_label") or "-",
                "model": row.get("bar") or "-" * BAR_WIDTH,
                "surface": "local",
            }
        )
    return jobs


def upsert_limit_jobs(jobs: list[dict[str, Any]], limits: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    kept = [job for job in jobs if not is_limit_job(job)]
    return kept + limits_to_jobs(limits)


def windows_from_jobs(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [job for job in jobs if is_limit_job(job)]
    rows.sort(key=lambda job: str(job.get("job_id") or ""))
    return [
        {
            "label": job.get("name"),
            "percent_label": job.get("stage") or "-",
            "bar": job.get("model") or "-" * BAR_WIDTH,
            "reset": job.get("status") or "-",
        }
        for job in rows
    ]
