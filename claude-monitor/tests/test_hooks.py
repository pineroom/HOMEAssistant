import importlib.util
import os
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def load_hook_module():
    path = ROOT / "hooks" / "ha_agent_hook.py"
    spec = importlib.util.spec_from_file_location("ha_agent_hook", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hook = load_hook_module()


class HookTests(unittest.TestCase):
    def test_cursor_notify_env_forces_cursor(self):
        with mock.patch.dict(os.environ, {"TOOL": "Cursor"}, clear=False):
            job = hook.build_job(
                {
                    "conversation_id": "conv-local-1",
                    "hook_event_name": "sessionStart",
                    "model": "claude-4-sonnet-thinking",
                    "is_background_agent": False,
                    "composer_mode": "agent",
                }
            )
        self.assertEqual(job["tool"], "Cursor")
        self.assertEqual(job["surface"], "local")
        self.assertEqual(job["stage"], "1/4")
        self.assertEqual(job["status"], "待機中")
        self.assertEqual(job["model"], "claude-4-sonnet-thinking")

    def test_missing_tool_is_not_claude_code(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(hook.ClassificationError):
                hook.detect_tool({"session_id": "abc"})

    def test_stop_completed(self):
        with mock.patch.dict(os.environ, {"TOOL": "Cursor"}):
            job = hook.build_job(
                {
                    "conversation_id": "conv-2",
                    "hook_event_name": "stop",
                    "reason": "completed",
                }
            )
        self.assertEqual(job["status"], "完了")
        self.assertEqual(job["stage"], "4/4")

    def test_cursor_notify_script_exists(self):
        text = (ROOT / "hooks" / "cursor_notify.sh").read_text()
        self.assertIn("TOOL=Cursor", text)
        self.assertIn("ha_agent_hook_cursor.py", text)
        self.assertIn('{"continue":true}', text)

    def test_generation_id_is_enough_for_job_id(self):
        with mock.patch.dict(os.environ, {"TOOL": "Cursor"}):
            job = hook.build_job(
                {
                    "generation_id": "gen-only-1",
                    "hook_event_name": "beforeSubmitPrompt",
                    "prompt": "1+1 を計算して",
                }
            )
        self.assertEqual(job["job_id"], "gen-only-1")
        self.assertEqual(job["name"], "1+1 を計算して")
        self.assertEqual(job["status"], "実行中")

    def test_progress_for_completed(self):
        self.assertEqual(hook.progress_for_job({"status": "完了", "stage": "4/4"}), 100)
        self.assertEqual(hook.progress_for_job({"status": "実行中", "stage": "2/4"}), 30)

    def test_mqtt_payload_aliases_agent(self):
        path = ROOT / "hooks" / "mqtt_publish.py"
        spec = importlib.util.spec_from_file_location("mqtt_publish", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        payload = module.to_mqtt_payload(
            {
                "job_id": "conv-1",
                "tool": "Cursor",
                "kind": "adhoc",
                "name": "1+1 を計算して",
                "status": "実行中",
                "stage": "2/4",
            }
        )
        self.assertEqual(payload["tool"], "Cursor")
        self.assertEqual(payload["agent"], "Cursor")
        self.assertEqual(payload["type"], "adhoc")
        self.assertEqual(payload["progress"], 30)


if __name__ == "__main__":
    unittest.main()
