#!/usr/bin/env python3
"""~/.claude/settings.json の hooks.command を wrap_claude_hook.sh で包む。

Cursor は Claude Code の Hook も実行するため、元コマンドの先頭にラッパを付ける。
statusLine は触らない。同じラッパが既にある command は二重に包まない。
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path


def wrap_command(command: str, wrap_path: str) -> str:
    text = (command or "").strip()
    wrap = wrap_path.strip()
    if not text or not wrap:
        return command
    if text == wrap or text.startswith(wrap + " "):
        return text
    return f"{wrap} {text}"


def wrap_hooks(node: object, wrap_path: str) -> int:
    changed = 0
    if isinstance(node, dict):
        command = node.get("command")
        if node.get("type") == "command" and isinstance(command, str):
            new = wrap_command(command, wrap_path)
            if new != command:
                node["command"] = new
                changed += 1
        for value in node.values():
            changed += wrap_hooks(value, wrap_path)
    elif isinstance(node, list):
        for item in node:
            changed += wrap_hooks(item, wrap_path)
    return changed


def apply(settings: dict, wrap_path: str) -> int:
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return 0
    return wrap_hooks(hooks, wrap_path)


def collect_commands(node: object) -> list[str]:
    found: list[str] = []
    if isinstance(node, dict):
        if node.get("type") == "command" and isinstance(node.get("command"), str):
            found.append(node["command"])
        for value in node.values():
            found.extend(collect_commands(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(collect_commands(item))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--settings",
        default=str(Path.home() / ".claude" / "settings.json"),
    )
    parser.add_argument(
        "--wrap",
        default=str(Path.home() / "claude-monitor" / "hooks" / "wrap_claude_hook.sh"),
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    path = Path(args.settings).expanduser()
    wrap_path = str(Path(args.wrap).expanduser())
    if not Path(wrap_path).is_file():
        print(f"wrap script not found: {wrap_path}", file=sys.stderr)
        return 1
    if not path.is_file():
        print(f"settings not found: {path}", file=sys.stderr)
        return 1

    settings = json.loads(path.read_text())
    changed = apply(settings, wrap_path)
    if args.dry_run:
        print(json.dumps(settings, ensure_ascii=False, indent=2))
        print(f"would wrap {changed} command(s)", file=sys.stderr)
        return 0

    backup = path.with_name(f"{path.name}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(path, backup)
    path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n")
    print(f"backed up {backup}")
    print(f"wrapped {changed} command(s) in {path}")
    for command in collect_commands(settings.get("hooks") or {}):
        print(f"  {command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
