import json
import unittest
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]


def load_wrap_module():
    path = ROOT / "scripts" / "wrap_claude_settings.py"
    spec = importlib.util.spec_from_file_location("wrap_claude_settings", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


wrap_mod = load_wrap_module()
wrap_command = wrap_mod.wrap_command
apply = wrap_mod.apply

WRAP = "/Users/matsufusa/claude-monitor/hooks/wrap_claude_hook.sh"

SAMPLE = {
    "permissions": {"allow": ["Read"]},
    "hooks": {
        "UserPromptSubmit": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": '/Users/matsufusa/claude-monitor/hooks/ha_agent_hook.py notify --agent "Claude Code" --type adhoc --name "Claude Code セッション" --status 実行中 --progress 30',
                    }
                ]
            }
        ],
        "Stop": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": '/Users/matsufusa/claude-monitor/hooks/ha_agent_hook.py notify --agent "Claude Code" --type adhoc --name "Claude Code セッション" --status 完了 --progress 100',
                    }
                ]
            }
        ],
        "StopFailure": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": '/Users/matsufusa/claude-monitor/hooks/ha_agent_hook.py notify --agent "Claude Code" --type adhoc --name "Claude Code セッション" --status エラー',
                    }
                ]
            }
        ],
        "PostToolUse": [
            {
                "matcher": "Bash",
                "hooks": [
                    {
                        "type": "command",
                        "command": '/Users/matsufusa/claude-monitor/hooks/ha_agent_hook.py notify --agent "Claude Code" --type adhoc --name "Claude Code セッション" --status 実行中 --progress 70',
                    }
                ]
            }
        ],
        "PreToolUse": [
            {
                "matcher": "Bash|Write|Edit|MultiEdit",
                "hooks": [
                    {
                        "type": "command",
                        "command": "TOOL_LABEL='Claude Code' JOB_ID=claude-code-current /Users/matsufusa/claude-monitor/hooks/await_approval.sh",
                    }
                ]
            }
        ],
    },
    "statusLine": {
        "type": "command",
        "command": "~/.claude/statusline-ha.sh",
        "refreshInterval": 15,
    },
}


class WrapCommandTests(unittest.TestCase):
    def test_prefix_and_idempotent(self):
        original = '/Users/matsufusa/claude-monitor/hooks/ha_agent_hook.py notify --agent "Claude Code"'
        wrapped = wrap_command(original, WRAP)
        self.assertTrue(wrapped.startswith(WRAP + " "))
        self.assertEqual(wrap_command(wrapped, WRAP), wrapped)

    def test_env_prefixed_pretooluse(self):
        original = "TOOL_LABEL='Claude Code' JOB_ID=claude-code-current /Users/matsufusa/claude-monitor/hooks/await_approval.sh"
        wrapped = wrap_command(original, WRAP)
        self.assertEqual(wrapped, f"{WRAP} {original}")


class ApplySettingsTests(unittest.TestCase):
    def test_wraps_five_hooks_not_statusline(self):
        settings = json.loads(json.dumps(SAMPLE))
        changed = apply(settings, WRAP)
        self.assertEqual(changed, 5)
        self.assertEqual(settings["statusLine"]["command"], "~/.claude/statusline-ha.sh")
        self.assertEqual(apply(settings, WRAP), 0)
        pre = settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        self.assertTrue(pre.startswith(WRAP + " TOOL_LABEL="))
        prompt = settings["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
        self.assertIn('notify --agent "Claude Code"', prompt)


class WrapScriptTests(unittest.TestCase):
    def test_wrap_shell_uses_env(self):
        text = (ROOT / "hooks" / "wrap_claude_hook.sh").read_text()
        self.assertIn('env "$@"', text)

    def test_apply_script_exists(self):
        path = ROOT / "scripts" / "apply_on_mac_mini.sh"
        self.assertTrue(path.is_file())
        text = path.read_text()
        self.assertIn("wrap_claude_settings.py", text)
        self.assertIn("ha_agent_hook_cursor.py", text)
        self.assertNotIn("cp \"$SRC\"/hooks/job_notify.sh", text)
        self.assertNotIn("cp \"$SRC\"/hooks/ha_agent_hook.py \"$DST\"/hooks/ha_agent_hook.py", text)


if __name__ == "__main__":
    unittest.main()
