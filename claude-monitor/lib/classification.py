"""Claude Monitor のツール分類。未知ソースを Claude Code に落とさない。"""

from __future__ import annotations

from typing import Optional

ALLOWED_TOOLS = ("Claude Code", "Codex", "Cursor")
ALLOWED_SURFACES = ("local", "cloud", "worker", "grok-bot")
ALLOWED_KINDS = ("adhoc", "routine", "automation")

_TOOL_ALIASES = {
    "claude code": "Claude Code",
    "claudecode": "Claude Code",
    "claude-code": "Claude Code",
    "claude_code": "Claude Code",
    "codex": "Codex",
    "cursor": "Cursor",
}

# モデル名に claude が含まれても tool は変えない。
_MODEL_IS_NOT_TOOL = True


class ClassificationError(ValueError):
    """tool が空、または許可リスト外。"""


def normalize_tool(raw: Optional[str]) -> str:
    """表示用ツール名へ正規化する。空や未知は例外。Claude Code には落とさない。"""
    if raw is None:
        raise ClassificationError("tool is required")
    text = str(raw).strip()
    if not text:
        raise ClassificationError("tool is required")
    if text in ALLOWED_TOOLS:
        return text
    alias = _TOOL_ALIASES.get(text.lower())
    if alias:
        return alias
    raise ClassificationError(f"unknown tool: {text}")


def normalize_surface(raw: Optional[str], default: str = "local") -> str:
    if raw is None or not str(raw).strip():
        return default
    text = str(raw).strip().lower().replace("_", "-")
    aliases = {
        "self-hosted": "worker",
        "machine": "worker",
        "pool": "worker",
        "grok": "grok-bot",
        "grokbot": "grok-bot",
        "background": "cloud",
    }
    mapped = aliases.get(text, text)
    if mapped not in ALLOWED_SURFACES:
        raise ClassificationError(f"unknown surface: {raw}")
    return mapped


def normalize_kind(raw: Optional[str], default: str = "adhoc") -> str:
    if raw is None or not str(raw).strip():
        return default
    text = str(raw).strip().lower()
    if text not in ALLOWED_KINDS:
        raise ClassificationError(f"unknown kind: {raw}")
    return text


def infer_cursor_surface(
    *,
    env_type: Optional[str] = None,
    is_background_agent: Optional[bool] = None,
    name: Optional[str] = None,
    source: Optional[str] = None,
) -> str:
    """Cursor ジョブの surface を API / Hook 情報から決める。"""
    if source in ALLOWED_SURFACES:
        return source
    lowered_name = (name or "").lower()
    if "grok" in lowered_name:
        return "grok-bot"
    env = (env_type or "").strip().lower()
    if env in {"machine", "pool"}:
        return "worker"
    if env == "cloud" or is_background_agent is True:
        return "cloud"
    return "local"


CURSOR_PAYLOAD_KEYS = (
    "composer_mode",
    "is_background_agent",
    "cursor_version",
    "generation_id",
)


def is_cursor_payload(payload: Optional[dict], environ: Optional[dict] = None) -> bool:
    """Cursor 経由の Hook かを判定する。Claude Code Hook の誤発火をここで止める。"""
    env = environ if environ is not None else __import__("os").environ
    if (env.get("TOOL") or "").strip().lower() == "cursor":
        return True
    if env.get("CURSOR_TRACE_ID") or env.get("CURSOR_AGENT"):
        return True
    if not payload:
        return False
    event = str(payload.get("hook_event_name") or payload.get("event") or "")
    if event and event[:1].islower() and event[:1].isalpha():
        return True
    return any(payload.get(key) is not None for key in CURSOR_PAYLOAD_KEYS)


def assert_tool_not_inferred_from_model(tool: str, model: Optional[str]) -> str:
    """モデル名（claude-4-sonnet 等）で tool を上書きしない。"""
    normalized = normalize_tool(tool)
    if _MODEL_IS_NOT_TOOL:
        return normalized
    return normalized
