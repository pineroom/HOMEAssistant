import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from aggregator.cursor_limits import (
    cookie_header_value,
    decode_vscdb_value,
    fetch_cursor_limits,
    limits_from_payloads,
    normalize_percent,
    usage_bar,
)


class CursorLimitsTests(unittest.TestCase):
    def test_normalize_percent_fraction_and_absolute(self):
        self.assertEqual(normalize_percent(0.74), 74.0)
        self.assertEqual(normalize_percent(74), 74.0)
        self.assertEqual(normalize_percent(0), 0.0)
        self.assertEqual(normalize_percent(100), 100.0)

    def test_usage_bar_matches_claude_style(self):
        self.assertEqual(usage_bar(0), "-" * 20)
        self.assertEqual(usage_bar(100), "*" * 20)
        self.assertIn("_", usage_bar(74))
        self.assertTrue(usage_bar(74).startswith("*"))

    def test_plan_and_grok_windows(self):
        summary = {
            "billingCycleEnd": "2026-09-26T14:02:00.000Z",
            "individualUsage": {
                "plan": {
                    "enabled": True,
                    "autoPercentUsed": 0.0,
                    "apiPercentUsed": 74.0,
                }
            },
        }
        sand = {
            "hasNonZeroIncludedLimit": True,
            "usagePercent": 40,
            "nextResetTimestampUtc": "2026-09-28T07:57:50.647Z",
        }
        result = limits_from_payloads(summary, sand)
        self.assertTrue(result["available"])
        labels = [row["label"] for row in result["windows"]]
        self.assertEqual(labels, ["Cursor Models", "Other Models", "Grok Bot"])
        by_id = {row["id"]: row for row in result["windows"]}
        self.assertEqual(by_id["cursor-models"]["percent_label"], "0.0%")
        self.assertEqual(by_id["other-models"]["percent_label"], "74.0%")
        self.assertEqual(by_id["grok-bot"]["percent_label"], "40.0%")
        self.assertRegex(by_id["other-models"]["reset"], r"09/26 \d{2}:\d{2}")

    def test_cookie_encodes_user_and_token(self):
        payload = base64_json({"sub": "user_abc"})
        token = f"eyJhbGciOiJub25lIn0.{payload}.sig"
        value = cookie_header_value(token)
        self.assertIn("user_abc", urllib_unquote(value))
        self.assertIn("::", urllib_unquote(value))

    def test_vscdb_utf16_and_json_string(self):
        self.assertTrue(decode_vscdb_value("eyJhbGciOiJub25lIn0").startswith("eyJ"))
        encoded = json.dumps("eyJhbGciOiJub25lIn0")
        self.assertEqual(decode_vscdb_value(encoded), "eyJhbGciOiJub25lIn0")
        utf16 = "eyJhbGciOiJub25lIn0".encode("utf-16-le")
        self.assertEqual(decode_vscdb_value(utf16), "eyJhbGciOiJub25lIn0")

    def test_fetch_uses_requester_and_caches(self):
        summary = {
            "billingCycleEnd": "2026-10-02T00:00:00.000Z",
            "individualUsage": {"plan": {"autoPercentUsed": 12, "apiPercentUsed": 8}},
        }
        sand = {"hasNonZeroIncludedLimit": True, "usagePercent": 3, "nextResetTimestampUtc": "2026-09-28T00:00:00Z"}
        calls = []

        def requester(url, cookie, data=None):
            calls.append(url)
            if "sand" in url:
                return sand
            return summary

        with mock.patch("aggregator.cursor_limits.load_session_token", return_value=("tok", "vscdb")):
            first = fetch_cursor_limits(requester=requester, now=datetime(2026, 9, 21, tzinfo=timezone.utc))
            second = fetch_cursor_limits(
                previous=first,
                requester=requester,
                now=datetime(2026, 9, 21, 0, 1, tzinfo=timezone.utc),
            )
        self.assertTrue(first["available"])
        self.assertEqual(first["windows"][0]["percent"], 12.0)
        self.assertEqual(second["windows"][2]["percent"], 3.0)
        self.assertEqual(len(calls), 2)

    def test_read_token_from_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.vscdb"
            conn = sqlite3.connect(path)
            conn.execute("CREATE TABLE ItemTable (key TEXT, value BLOB)")
            conn.execute(
                "INSERT INTO ItemTable VALUES (?, ?)",
                ("cursorAuth/accessToken", "eyJhbGciOiJub25lIn0.abc.sig"),
            )
            conn.commit()
            conn.close()
            from aggregator.cursor_limits import read_access_token_from_vscdb

            self.assertTrue(read_access_token_from_vscdb(path).startswith("eyJ"))


def base64_json(payload: dict) -> str:
    import base64

    raw = json.dumps(payload, separators=(",", ":")).encode("ascii")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def urllib_unquote(value: str) -> str:
    import urllib.parse

    return urllib.parse.unquote(value)


if __name__ == "__main__":
    unittest.main()
