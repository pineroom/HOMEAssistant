# Claude Monitor 実機への適用メモ

既存の `~/claude-monitor` は GitHub リポジトリそのものではない。新規ファイルだけコピーする。

## 1+1 が Claude Code 欄に出ない場合

ラップ後は **正常** です。Cursor の処理を Claude Code として送らなくなったため、既存の「Claude Code 実行中・最近の処理」には出ません。

まだ足りないのは次の2点です。

1. Cursor 用カードが HA に無い
2. Cursor 通知が MQTT まで届いているか未確認

## コピーと診断

Mac mini の Terminal に、次をそのまま貼る。

```bash
cd ~/HOMEAssistant-cursor-overlay
git pull
chmod +x claude-monitor/scripts/apply_on_mac_mini.sh
./claude-monitor/scripts/apply_on_mac_mini.sh
~/claude-monitor/scripts/diagnose_cursor_notify.sh
```

`diagnose_cursor_notify.sh` はテストジョブ「Cursor 診断テスト」を1件送り、hook ログと MQTT の状態を出します。

Cursor を完全終了（`Cmd + Q`）して再起動してから、もう一度短い依頼を出してください。

## Lovelace

`claude-monitor-live` を編集し、Claude カードの近くに Markdown カードを2枚足す。

1枚目のタイトル: `Cursor 使用量`  
本文は `lovelace/cursor_usage_card.yaml` の `content:` 以下。

2枚目のタイトル: `Cursor 実行中・最近の処理`  
本文は `lovelace/cursor_jobs_card.yaml` の `content:` 以下。

既存の Claude カードが `Codex` 以外を全部拾っているなら、抽出を `tool == 'Claude Code'`（または `agent == 'Claude Code'`）に差し替える。
