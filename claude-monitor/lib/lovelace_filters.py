"""Lovelace カード用の抽出。Claude は tool == Claude Code のみ。"""

from __future__ import annotations

from typing import Any, Iterable

from .jobs import claude_adhoc_jobs, cursor_adhoc_jobs


SURFACE_LABELS = {
    "local": "ローカル",
    "cloud": "Cloud",
    "worker": "Worker",
    "grok-bot": "Grok Bot",
}

STATUS_COLORS = {
    "実行中": "blue",
    "権限承認待ち": "orange",
    "待機中": "grey",
    "完了": "green",
    "エラー": "red",
    "拒否": "red",
}


def _sort_recent(jobs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        jobs,
        key=lambda job: job.get("started") or job.get("finished") or "",
        reverse=True,
    )


def claude_recent_rows(jobs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Claude Code カード。tool != Codex では拾わない。"""
    return _sort_recent(claude_adhoc_jobs(jobs))


def cursor_recent_rows(jobs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for job in _sort_recent(cursor_adhoc_jobs(jobs)):
        row = dict(job)
        row["surface_label"] = SURFACE_LABELS.get(job.get("surface", "local"), job.get("surface") or "ローカル")
        row["status_color"] = STATUS_COLORS.get(job.get("status", ""), "grey")
        rows.append(row)
    return rows


def tools_in_rows(rows: Iterable[dict[str, Any]]) -> set[str]:
    return {row.get("tool") for row in rows if row.get("tool")}
