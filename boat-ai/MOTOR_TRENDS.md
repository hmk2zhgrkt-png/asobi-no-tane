# 現行モーター・節間推移の特徴量（第一段階）

`motor_trends.py` は公式データ等の**利用が許可された履歴CSV**から、予想時点より前のモーター成績だけを使った特徴量を算出します。外部サイトへの自動アクセスはしません。

```bash
python boat-ai/motor_trends.py --input race_observations.csv --output motor_trends.json
```

入力必須列: `race_id,race_start,venue_code,motor_cycle,motor_number,meeting_id,boat,finish,exhibition_time`。race_start はタイムゾーン付き ISO8601。6艇揃ったレースのみ対応。motor_cycle は各場の**モーター交換を基準に区切った一意のID**で、番号単独で異なる世代の機械を混合しません。meeting_id は同じ開催節で一意にしてください。

出力:
- `cycle_prior_runs`, `cycle_prior_top2_rate`: 現行モーター期間の過去成績
- `last5_prior_runs`, `last5_prior_top2_rate`: 直近5走の成績
- `last5_prior_relative_exhibition`: 過去の展示タイムと同一レース6艇平均との差（秒、マイナスほど速い）
- `meeting_prior_runs`, `meeting_prior_top2_rate`, `meeting_prior_relative_exhibition`: 今節の**前走まで**の成績・展示
- `meeting_last_relative_exhibition`, `meeting_relative_exhibition_change`: 今節の前走展示差とその推移

予想対象レースの結果・展示は、そのレースの特徴量を作る時点では使いません（情報漏洩対策）。

**重要な限界**: 展示タイムと着順は、調整以外に選手能力・風・波・進入・相手関係にも左右されます。現段階の値は機力そのものの推定値ではありません。現場の整備情報や出足・伸び/周り足などは、正規に取得できた場合だけ追加します。歴史的モーター交換日/各節ID/展示データの正規化や、既存の学習済みAIへの結合・再学習は未実装です。
