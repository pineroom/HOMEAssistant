# Claude Monitor 実機への適用メモ

既存の `~/claude-monitor` は GitHub リポジトリそのものではない。新規ファイルだけコピーする。

## いま見えている症状

Cursor の処理が「Claude Code 実行中・最近の処理」に出る。Cursor カードはまだ HA に無い。

原因は次の2点。

1. Cursor が `~/.claude/settings.json` の Claude Code Hook も実行する
2. Lovelace の Claude カードがまだ Cursor を除外しておらず、Cursor 用カードも未追加

## コピー

```bash
SRC=~/HOMEAssistant-cursor-overlay/claude-monitor
DST=~/claude-monitor
cd "$SRC" && git pull
cp "$SRC"/lib/*.py "$DST"/lib/
cp "$SRC"/hooks/mqtt_publish.py "$DST"/hooks/
cp "$SRC"/hooks/claude_hook_guard.py "$DST"/hooks/
cp "$SRC"/hooks/wrap_claude_hook.sh "$DST"/hooks/
cp "$SRC"/hooks/cursor_notify.sh "$DST"/hooks/
cp "$SRC"/hooks/ha_agent_hook.py "$DST"/hooks/ha_agent_hook_cursor.py
cp "$SRC"/scripts/inspect_jobs.py "$DST"/scripts/
cp "$SRC"/lovelace/*.yaml "$DST"/lovelace/
chmod +x "$DST"/hooks/*.sh "$DST"/hooks/*.py "$DST"/scripts/*.py
```

既存の `hooks/job_notify.sh` は上書きしない。

## Claude Code Hook を Cursor から外す

```bash
python3 "$DST/scripts/inspect_jobs.py"
cat ~/.claude/settings.json
```

`settings.json` の hooks.command が例えば `.../hooks/job_notify.sh` なら、次のように包む。

```bash
/Users/matsufusa/claude-monitor/hooks/wrap_claude_hook.sh python3 /Users/matsufusa/claude-monitor/hooks/ha_agent_hook.py
```

（実際の command は `cat ~/.claude/settings.json` の値に合わせる。）

Cursor を再起動してから、ローカルエージェントで短い依頼を1件出す。

## Lovelace

`lovelace/cursor_usage_card.yaml` と `lovelace/cursor_jobs_card.yaml` を `claude-monitor-live` の Claude カードの近くに追加する。既存の Claude カードの抽出は `tool == 'Claude Code'` に差し替える。`tool != Codex` は使わない。
