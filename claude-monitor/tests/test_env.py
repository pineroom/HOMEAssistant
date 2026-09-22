import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "hooks"))

from mqtt_publish import cursor_api_key_diagnostics, load_env_files, parse_env_line


class EnvLoadTests(unittest.TestCase):
    def test_parse_export_and_quotes(self):
        self.assertEqual(parse_env_line('export CURSOR_API_KEY="crsr_abc"'), ("CURSOR_API_KEY", "crsr_abc"))
        self.assertEqual(parse_env_line("CURSOR_API_KEY='crsr_xyz'"), ("CURSOR_API_KEY", "crsr_xyz"))
        self.assertIsNone(parse_env_line("# CURSOR_API_KEY=crsr_hidden"))

    def test_load_overwrites_empty_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text("export CURSOR_API_KEY=crsr_from_file\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"CURSOR_API_KEY": "  "}, clear=False):
                load_env_files(extra_roots=[root], include_defaults=False)
                self.assertEqual(os.environ["CURSOR_API_KEY"], "crsr_from_file")

    def test_diagnostics_does_not_include_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text("CURSOR_API_KEY=crsr_secret_value\n", encoding="utf-8")
            diag = cursor_api_key_diagnostics(extra_roots=[root], include_defaults=False)
            blob = str(diag)
            self.assertNotIn("crsr_secret_value", blob)
            env_row = next(row for row in diag["files"] if row["path"].endswith(".env"))
            self.assertTrue(env_row["exists"])
            self.assertTrue(env_row["has_key"])

    def test_set_script_writes_live_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["CLAUDE_MONITOR_HOME"] = tmp
            script = ROOT / "scripts" / "set_cursor_api_key.sh"
            proc = subprocess.run(
                ["bash", str(script)],
                input="crsr_testkey123\n",
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("CURSOR_API_KEY: SET", proc.stdout)
            self.assertNotIn("crsr_testkey123", proc.stdout)
            self.assertEqual((Path(tmp) / ".env").read_text(), "CURSOR_API_KEY=crsr_testkey123\n")


if __name__ == "__main__":
    unittest.main()
