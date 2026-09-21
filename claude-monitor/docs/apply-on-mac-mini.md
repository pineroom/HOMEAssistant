# Claude Monitor 実機への適用メモ

既存の `~/claude-monitor` は GitHub リポジトリそのものではない。新規ファイルだけコピーする。

## Lovelace カードの貼り方

Jinja 本文だけを「セクションを編集」に貼ると YAML エラーになる。
`{% set jobs ... %}` はセクション定義ではなく、**Markdown カード**の `content` に入れる。

1. 「セクションを編集」は × で閉じる
2. Claude Code カードがあるセクションで **カードを追加**
3. **Markdown** を選ぶ
4. 右下の **コードエディタを表示** を開き、次を **先頭から全部** 貼る

```yaml
type: markdown
title: Cursor 実行中・最近の処理
content: |
  {% set jobs = state_attr('sensor.claude_jobs', 'jobs') or [] %}
  {% set ns = namespace(rows=[]) %}
  {% for job in jobs %}
    {% set tool = job.tool | default(job.agent) %}
    {% set kind = job.kind or job.type or 'adhoc' %}
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
  {% for job in rows | sort(attribute='started', reverse=true) %}
  {% set surface = job.surface | default('local') %}
  {% set surface_label = {'local': 'ローカル', 'cloud': 'Cloud', 'worker': 'Worker', 'grok-bot': 'Grok Bot'}[surface] | default(surface) %}
  | {{ job.name }} | {{ surface_label }} | {{ job.status }} | {{ job.stage }} | {{ job.model or '-' }} |
  {% endfor %}
  {% endif %}
```

5. 保存する

既存の Claude Code カードを複製し、`tool == 'Cursor'` に変える方法でもよい。
