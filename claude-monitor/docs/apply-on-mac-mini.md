# Claude Monitor 実機への適用メモ

既存の `~/claude-monitor` は GitHub リポジトリそのものではない。新規ファイルだけコピーする。

## Lovelace カードの貼り方

「セクションを編集」ではなく **Markdown カード**のコードエディタに、次を先頭から全部貼る。
実機ジョブに `kind` が無いため、`job.kind` は使わず `job.get('kind')` にする。

```yaml
type: markdown
title: Cursor 実行中・最近の処理
content: |
  {% set jobs = state_attr('sensor.claude_jobs', 'jobs') or [] %}
  {% set ns = namespace(rows=[]) %}
  {% for job in jobs %}
    {% set tool = job.get('tool') or job.get('agent') %}
    {% set kind = job.get('kind') or job.get('type') or 'adhoc' %}
    {% if kind == 'adhoc' and tool == 'Cursor' %}
      {% set ns.rows = ns.rows + [job] %}
    {% endif %}
  {% endfor %}
  {% set rows = ns.rows %}
  {% if rows | length == 0 %}
  処理なし
  {% else %}
  | ジョブ | 経路 | 状態 | 段階 | モデル |
  | --- | --- | --- | --- | --- |
  {% for job in rows %}
  {% set surface = job.get('surface') or 'local' %}
  {% set surface_label = {'local': 'ローカル', 'cloud': 'Cloud', 'worker': 'Worker', 'grok-bot': 'Grok Bot'}.get(surface, surface) %}
  | {{ job.get('name') }} | {{ surface_label }} | {{ job.get('status') }} | {{ job.get('stage') }} | {{ job.get('model') or '-' }} |
  {% endfor %}
  {% endif %}
```
