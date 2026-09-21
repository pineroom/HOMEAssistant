import unittest

from lib.classification import ClassificationError, infer_cursor_surface, normalize_tool


class NormalizeToolTests(unittest.TestCase):
    def test_aliases(self):
        self.assertEqual(normalize_tool("cursor"), "Cursor")
        self.assertEqual(normalize_tool("claude-code"), "Claude Code")
        self.assertEqual(normalize_tool("Codex"), "Codex")

    def test_empty_and_unknown_are_not_claude(self):
        for raw in (None, "", "  ", "unknown", "Grok"):
            with self.assertRaises(ClassificationError):
                normalize_tool(raw)

    def test_model_name_is_not_a_tool(self):
        with self.assertRaises(ClassificationError):
            normalize_tool("claude-4-sonnet-thinking")


class CursorPayloadTests(unittest.TestCase):
    def test_cursor_markers(self):
        from lib.classification import is_cursor_payload

        self.assertTrue(is_cursor_payload({"hook_event_name": "sessionStart", "composer_mode": "agent"}, {}))
        self.assertTrue(is_cursor_payload({}, {"TOOL": "Cursor"}))
        self.assertFalse(is_cursor_payload({"hook_event_name": "SessionStart"}, {}))
        self.assertFalse(is_cursor_payload({}, {}))


class SurfaceTests(unittest.TestCase):
    def test_infer_surfaces(self):
        self.assertEqual(infer_cursor_surface(env_type="cloud"), "cloud")
        self.assertEqual(infer_cursor_surface(env_type="machine"), "worker")
        self.assertEqual(infer_cursor_surface(env_type="pool"), "worker")
        self.assertEqual(infer_cursor_surface(is_background_agent=True), "cloud")
        self.assertEqual(infer_cursor_surface(name="Grok Bot nightly"), "grok-bot")
        self.assertEqual(infer_cursor_surface(), "local")


if __name__ == "__main__":
    unittest.main()
