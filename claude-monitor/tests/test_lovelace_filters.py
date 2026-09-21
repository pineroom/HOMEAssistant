import unittest
from pathlib import Path

from lib.lovelace_filters import claude_recent_rows, cursor_recent_rows, tools_in_rows

ROOT = Path(__file__).resolve().parents[1]


class LovelaceFilterTests(unittest.TestCase):
    def test_yaml_uses_exact_tool_equals(self):
        claude = (ROOT / "lovelace" / "claude_jobs_card.yaml").read_text()
        cursor = (ROOT / "lovelace" / "cursor_jobs_card.yaml").read_text()
        content = claude.split("content:", 1)[-1]
        self.assertIn("tool == 'Claude Code'", claude)
        self.assertNotIn("!=", content)
        self.assertNotIn("not equalto", content)
        self.assertNotIn("Codex", content)
        self.assertTrue(cursor.lstrip().startswith("type: markdown"))
        self.assertIn("content: |", cursor)
        self.assertIn("job.agent", cursor)
        self.assertIn("job.kind or job.type or 'adhoc'", cursor)

    def test_usage_card_says_unavailable(self):
        usage = (ROOT / "lovelace" / "cursor_usage_card.yaml").read_text()
        self.assertIn("制限表示", usage)
        self.assertIn("取得不可", usage)
        self.assertIn("usage.cursor", usage)

    def test_python_filters_match_cards(self):
        jobs = [
            {"job_id": "c1", "tool": "Claude Code", "kind": "adhoc", "name": "A", "status": "実行中", "stage": "2/4", "started": "2026-09-21T01:00:00+00:00"},
            {"job_id": "x1", "tool": "Cursor", "kind": "adhoc", "name": "B", "status": "実行中", "stage": "3/4", "surface": "cloud", "started": "2026-09-21T02:00:00+00:00"},
        ]
        self.assertEqual(tools_in_rows(claude_recent_rows(jobs)), {"Claude Code"})
        self.assertEqual(tools_in_rows(cursor_recent_rows(jobs)), {"Cursor"})
        self.assertEqual(cursor_recent_rows(jobs)[0]["surface_label"], "Cloud")


if __name__ == "__main__":
    unittest.main()
