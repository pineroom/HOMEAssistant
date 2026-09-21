#!/usr/bin/env python3
"""Claude Code Hook の stdin が Cursor 由来なら 0、そうでなければ 1。"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.classification import is_cursor_payload


def main() -> int:
    raw = sys.stdin.read().strip()
    payload = {}
    if raw:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {}
    if is_cursor_payload(payload, os.environ):
        print(raw)
        return 0
    print(raw)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
