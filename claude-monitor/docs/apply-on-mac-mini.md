# Claude Monitor 実機への適用メモ

既存の `~/claude-monitor` は GitHub リポジトリそのものではない。新規ファイルだけコピーする。

## 診断結果（2026-09-21）

- MQTT は通っている（`MQTT_PASS` SET、`mosquitto_pub` あり）
- `jobs_state.json` に `Cursor: 1` がある
- 実機ジョブの `kind` は `null`。Claude Code 欄に 1+1 が出ないのはラップ成功
- HA に Cursor カードがまだ無いので画面上は見えない

## Lovelace（次にやること）

`claude-monitor-live` を編集し、Markdown カード「Cursor 実行中・最近の処理」を追加する。本文は `lovelace/cursor_jobs_card.yaml` の `content:` 以下。`kind` が空でも `tool == 'Cursor'` なら表示する。

## コピー

```bash
cd ~/HOMEAssistant-cursor-overlay
git pull
./claude-monitor/scripts/apply_on_mac_mini.sh
python3 ~/claude-monitor/scripts/inspect_jobs.py
```
