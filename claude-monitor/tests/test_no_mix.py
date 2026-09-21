"""Cursor と Claude Code の表が混線しないことを固定する。"""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from aggregator.jobs_store import apply_updates, sanitize_jobs
from lib.classification import ClassificationError
from lib.jobs import is_generic_job_name, merge_job, normalize_job
from lib.lovelace_filters import claude_recent_rows, cursor_recent_rows, tools_in_rows

ROOT = Path(__file__).resolve().parents[1]


class NoMixTests(unittest.TestCase):
    def setUp(self):
        self.claude = normalize_job(
            {
                "job_id": "claude-session-1",
                "tool": "Claude Code",
                "kind": "adhoc",
                "name": "Edit Lovelace",
                "status": "実行中",
                "stage": "2/4",
                "model": "claude-opus-4-6",
                "started": "2026-09-21T03:00:00+00:00",
            }
        )
        self.cursor_local = normalize_job(
            {
                "job_id": "conv-cursor-local",
                "tool": "Cursor",
                "kind": "adhoc",
                "name": "Add Cursor cards",
                "status": "実行中",
                "stage": "3/4",
                "surface": "local",
                "model": "claude-4-sonnet-thinking",
                "started": "2026-09-21T03:05:00+00:00",
            }
        )

    def test_null_kind_counts_as_adhoc(self):
        rows = cursor_recent_rows(
            [
                {
                    "job_id": "cursor-live-1",
                    "tool": "Cursor",
                    "kind": None,
                    "name": "Cursor 診断テスト",
                    "status": "実行中",
                    "stage": "2/4",
                    "started": "2026-09-21T03:00:00+00:00",
                }
            ]
        )
        self.assertEqual([row["name"] for row in rows], ["Cursor 診断テスト"])

    def test_mixed_store_splits_cleanly(self):
        jobs = apply_updates([], [self.claude, self.cursor_local])
        claude_rows = claude_recent_rows(jobs)
        cursor_rows = cursor_recent_rows(jobs)
        self.assertEqual([row["job_id"] for row in claude_rows], ["claude-session-1"])
        self.assertEqual([row["job_id"] for row in cursor_rows], ["conv-cursor-local"])
        self.assertEqual(tools_in_rows(claude_rows), {"Claude Code"})
        self.assertEqual(tools_in_rows(cursor_rows), {"Cursor"})
        self.assertEqual(cursor_rows[0]["model"], "claude-4-sonnet-thinking")

    def test_merge_does_not_replace_prompt_with_uuid(self):
        job_id = "ec4aa7f3-e37b-4a2a-8ec4-180508535f5a"
        first = normalize_job(
            {
                "job_id": job_id,
                "tool": "Cursor",
                "kind": "adhoc",
                "name": "1＋1を実行して",
                "status": "実行中",
                "stage": "2/4",
            }
        )
        jobs = merge_job(
            [first],
            {
                "job_id": job_id,
                "tool": "Cursor",
                "kind": "adhoc",
                "name": job_id,
                "status": "完了",
                "stage": "4/4",
            },
        )
        self.assertEqual(jobs[0]["name"], "1＋1を実行して")
        self.assertEqual(jobs[0]["status"], "完了")
        self.assertTrue(is_generic_job_name(job_id, job_id))

    def test_unknown_update_is_dropped(self):
        jobs = apply_updates([self.claude], [{"job_id": "mystery", "tool": "", "name": "???"}])
        self.assertEqual([job["job_id"] for job in jobs], ["claude-session-1"])

    def test_sanitize_drops_unlabeled_legacy_jobs(self):
        legacy = [{"job_id": "old", "kind": "adhoc", "name": "maybe cursor", "status": "実行中"}]
        self.assertEqual(sanitize_jobs(legacy), [])

    def test_cannot_merge_without_tool(self):
        with self.assertRaises(ClassificationError):
            merge_job([], {"job_id": "x", "name": "no tool"})

    def test_job_notify_requires_tool(self):
        script = ROOT / "hooks" / "job_notify.sh"
        result = subprocess.run(
            ["bash", str(script), json.dumps({"job_id": "x", "name": "n"})],
            capture_output=True,
            text=True,
            env={k: v for k, v in os.environ.items() if k != "TOOL"},
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TOOL is required", result.stderr)

    def test_job_notify_cursor_payload(self):
        script = ROOT / "hooks" / "job_notify.sh"
        env = os.environ.copy()
        env["TOOL"] = "Cursor"
        env["SURFACE"] = "local"
        env.pop("MQTT_PASS", None)
        result = subprocess.run(
            [
                "bash",
                str(script),
                json.dumps({"job_id": "conv-1", "name": "Local agent", "status": "実行中", "stage": "2/4"}),
            ],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(payload["tool"], "Cursor")
        self.assertEqual(payload["surface"], "local")


if __name__ == "__main__":
    unittest.main()
