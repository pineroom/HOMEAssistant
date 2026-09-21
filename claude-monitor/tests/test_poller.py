import unittest
from datetime import datetime, timezone

from aggregator.cursor_poller import agent_to_job, poll, summarize_usage, usage_totals
from aggregator.jobs_store import merge_poller_jobs


class PollerTests(unittest.TestCase):
    def test_cloud_and_worker_surfaces(self):
        cloud = agent_to_job(
            {
                "id": "bc-cloud",
                "name": "Investigate monitor",
                "status": "ACTIVE",
                "env": {"type": "cloud"},
                "model": {"id": "composer-2.5"},
                "createdAt": "2026-09-21T00:00:00Z",
                "updatedAt": "2026-09-21T00:10:00Z",
            }
        )
        worker = agent_to_job(
            {
                "id": "bc-worker",
                "name": "Grok Bot routine",
                "status": "IDLE",
                "env": {"type": "machine"},
                "createdAt": "2026-09-21T00:00:00Z",
                "updatedAt": "2026-09-21T00:20:00Z",
            }
        )
        self.assertEqual(cloud["tool"], "Cursor")
        self.assertEqual(cloud["surface"], "cloud")
        self.assertEqual(cloud["status"], "実行中")
        self.assertEqual(cloud.get("model"), "composer-2.5")
        self.assertEqual(worker["surface"], "grok-bot")
        self.assertEqual(worker["status"], "完了")

    def test_poll_uses_fetcher(self):
        agents = [
            {
                "id": "bc-1",
                "name": "Local-looking name",
                "status": "ACTIVE",
                "env": {"type": "cloud"},
                "createdAt": "2026-09-21T00:00:00Z",
            }
        ]
        result = poll(api_key="dummy", fetcher=lambda _key: agents)
        self.assertEqual(len(result["jobs"]), 1)
        self.assertEqual(result["jobs"][0]["tool"], "Cursor")

    def test_poll_enriches_model_from_latest_run(self):
        listed = [
            {
                "id": "bc-1",
                "name": "Aiエージェントシステム移植",
                "status": "IDLE",
                "env": {"type": "cloud"},
                "latestRunId": "run-1",
                "createdAt": "2026-09-21T00:00:00Z",
            }
        ]

        def agent_fetcher(_key, _agent_id):
            return dict(listed[0])

        def run_fetcher(_key, _agent_id, _run_id):
            return {"id": "run-1", "model": {"id": "composer-2.5"}}

        result = poll(
            api_key="dummy",
            fetcher=lambda _key: listed,
            agent_fetcher=agent_fetcher,
            run_fetcher=run_fetcher,
            enrich=True,
        )
        self.assertEqual(result["jobs"][0]["model"], "composer-2.5")
        self.assertEqual(result["jobs"][0]["surface"], "cloud")

    def test_merge_keeps_cloud_model_when_poll_omits_it(self):
        existing = [
            {
                "job_id": "bc-1",
                "tool": "Cursor",
                "kind": "adhoc",
                "name": "Aiエージェントシステム移植",
                "status": "完了",
                "stage": "4/4",
                "surface": "cloud",
                "model": "composer-2.5",
            }
        ]
        incoming = [
            {
                "job_id": "bc-1",
                "tool": "Cursor",
                "kind": "adhoc",
                "name": "Aiエージェントシステム移植",
                "status": "完了",
                "stage": "4/4",
                "surface": "cloud",
            }
        ]
        merged = merge_poller_jobs(existing, incoming)
        self.assertEqual(merged[0]["model"], "composer-2.5")

    def test_merge_does_not_relabel_claude(self):
        existing = [
            {
                "job_id": "claude-1",
                "tool": "Claude Code",
                "kind": "adhoc",
                "name": "HA yaml",
                "status": "実行中",
                "stage": "2/4",
            }
        ]
        poller_jobs = [
            {
                "job_id": "bc-1",
                "tool": "Cursor",
                "kind": "adhoc",
                "name": "Cloud work",
                "status": "実行中",
                "stage": "3/4",
                "surface": "cloud",
            }
        ]
        merged = merge_poller_jobs(existing, poller_jobs)
        tools = {job["job_id"]: job["tool"] for job in merged}
        self.assertEqual(tools["claude-1"], "Claude Code")
        self.assertEqual(tools["bc-1"], "Cursor")

    def test_usage_totals(self):
        totals = usage_totals(
            {
                "runs": [
                    {"usage": {"inputTokens": 10, "outputTokens": 4, "cacheReadTokens": 1, "cacheWriteTokens": 2}},
                    {"usage": {"inputTokens": 5, "outputTokens": 1, "cacheReadTokens": 0, "cacheWriteTokens": 0}},
                ]
            }
        )
        self.assertEqual(totals["input_tokens"], 15)
        summary = summarize_usage(
            [
                {
                    "id": "bc-1",
                    "createdAt": datetime.now(timezone.utc).isoformat(),
                    "model": {"id": "composer-2.5"},
                }
            ],
            {"bc-1": {"usage": {"inputTokens": 9, "outputTokens": 3, "cacheReadTokens": 0, "cacheWriteTokens": 0}}},
        )
        self.assertEqual(summary["sessions"], 1)
        self.assertEqual(summary["rate_limits"]["note"], "取得不可")


if __name__ == "__main__":
    unittest.main()
