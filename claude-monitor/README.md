# Claude Monitor — Cursor 追加分

Mac mini の `~/claude-monitor` にコピーして使う。既存の MQTT 集約（ブローカー `192.168.0.30`、HA `192.168.0.216`）を壊さず、`tool=Cursor` を第3ツールにする。

## 混線防止

- `tool` は `Claude Code` / `Codex` / `Cursor` のみ
- 空・未知は破棄。Claude Code には落とさない
- Lovelace の Claude カードは `tool == 'Claude Code'`。`tool != Codex` は使わない

## 導入

```bash
rsync -a claude-monitor/ ~/claude-monitor-cursor-overlay/
# または既存ツリーへ hooks / aggregator / lib / lovelace をマージ
cd ~/claude-monitor
./scripts/install_cursor_hooks.sh
```

既存 `aggregator.py` から:

```python
from aggregator.jobs_store import apply_updates, merge_poller_jobs, sanitize_jobs
from aggregator.cursor_poller import poll
```

Cloud Agent 用:

```bash
export CURSOR_API_KEY=...   # launchd の環境変数のみ。Git に置かない
export CURSOR_INCLUDE_USAGE=1
python3 aggregator/run_cursor_poll.py
```

HA の `claude-monitor-live` に `lovelace/*.yaml` を追加する。

## 試験

```bash
cd claude-monitor
PYTHONPATH=. python3 -m unittest discover -s tests -v
```
