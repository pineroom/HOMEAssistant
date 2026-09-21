"""MQTT ジョブと Cloud poller 結果を合流する。既存 aggregator から呼ぶ。"""

from __future__ import annotations

from typing import Any, Iterable

from lib.jobs import merge_job, normalize_job, prune_jobs
from lib.classification import ClassificationError


def apply_updates(jobs: Iterable[dict[str, Any]], updates: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    current = list(jobs)
    for update in updates:
        try:
            current = merge_job(current, update)
        except ClassificationError:
            continue
    return prune_jobs(current)


def merge_poller_jobs(jobs: Iterable[dict[str, Any]], poller_jobs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cloud / worker ジョブを既存リストへ合流する。tool は Cursor 固定。"""
    updates = []
    for job in poller_jobs:
        incoming = dict(job)
        incoming["tool"] = "Cursor"
        updates.append(incoming)
    return apply_updates(jobs, updates)


def sanitize_jobs(jobs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """既存 state を読み直すとき、不正 tool を捨てる。"""
    cleaned = []
    for job in jobs:
        try:
            cleaned.append(normalize_job(job))
        except ClassificationError:
            continue
    return prune_jobs(cleaned)
