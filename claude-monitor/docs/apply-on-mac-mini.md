# Claude Monitor 実機への適用メモ

既存の `~/claude-monitor` は GitHub リポジトリそのものではない。新規ファイルだけコピーする。

## いま見えている症状

Cursor の処理が「Claude Code 実行中・最近の処理」に出る。Cursor カードはまだ HA に無い。

原因は次の2点。

1. Cursor が `~/.claude/settings.json` の Claude Code Hook も実行する
2. Lovelace の Claude カードがまだ Cursor を除外しておらず、Cursor 用カードも未追加

貼り付けた `settings.json` では、5本の Hook がすべて `--agent "Claude Code"` か `TOOL_LABEL='Claude Code'` になっている。JSON を手で直す必要はない。下の1本を実行する。

## コピーと Claude Hook の包み込み

Mac mini の Terminal に、次をそのまま貼る。

```bash
cd ~/HOMEAssistant-cursor-overlay
git pull
chmod +x claude-monitor/scripts/apply_on_mac_mini.sh
./claude-monitor/scripts/apply_on_mac_mini.sh
```

このスクリプトがやること:

1. overlay の新規ファイルを `~/claude-monitor` へコピーする（既存の `job_notify.sh` と `ha_agent_hook.py` は上書きしない）
2. `~/.claude/settings.json` を `.bak-日時` に退避する
3. `hooks` 配下の command 5本の先頭に `wrap_claude_hook.sh` を付ける
4. `statusLine` は触らない

包んだあとの command は次の形になる。

```text
/Users/matsufusa/claude-monitor/hooks/wrap_claude_hook.sh /Users/matsufusa/claude-monitor/hooks/ha_agent_hook.py notify --agent "Claude Code" ...
/Users/matsufusa/claude-monitor/hooks/wrap_claude_hook.sh TOOL_LABEL='Claude Code' JOB_ID=claude-code-current /Users/matsufusa/claude-monitor/hooks/await_approval.sh
```

Cursor 由来なら Cursor 通知へ回し、本物の Claude Code セッションだけ元コマンドを実行する。

確認:

```bash
python3 -c 'import json,pathlib; d=json.loads(pathlib.Path.home().joinpath(".claude/settings.json").read_text());
[print(h["command"]) for ev in d["hooks"].values() for g in ev for h in g.get("hooks",[])]'
```

Cursor を完全終了して再起動し、ローカルエージェントで短い依頼を1件出す。

## Lovelace

`lovelace/cursor_usage_card.yaml` と `lovelace/cursor_jobs_card.yaml` を `claude-monitor-live` の Claude カードの近くに追加する。既存の Claude カードの抽出は `tool == 'Claude Code'` に差し替える。`tool != Codex` は使わない。
