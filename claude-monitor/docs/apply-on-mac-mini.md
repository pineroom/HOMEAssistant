# Claude Monitor 実機への適用メモ

段階は `stage` が空でも status/progress から 1/4〜4/4 を出す。
モデルは Hook の `model` / `model_id` を覚え、完了時も保持する。

Markdown カードの YAML は `lovelace/cursor_jobs_card.yaml` をコードエディタに全部貼る。

クラウド処理は Dashboard でキーを作っただけでは出ない。`~/claude-monitor/.env` へ書く:

```bash
pbpaste | ~/claude-monitor/scripts/set_cursor_api_key.sh
PYTHONPATH=~/claude-monitor python3 ~/claude-monitor/aggregator/run_cursor_poll.py
```

Cloud 行のモデルは一覧 API に含まれない。ポールがエージェント詳細と最新 run を読んで補う。それでも無ければ `-`。

`run_cursor_poll: CURSOR_API_KEY is required` は、プロセスがキーを読めていない。overlay ディレクトリの `.env` ではなく live の `~/claude-monitor/.env` を使う。`launchctl load` が成功してもキーは入らない。
