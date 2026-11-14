# iPhone GitHub Actions 版（準備・制限）

このフォルダの `run_one.py` と `.github/workflows/boat-ai-paper.yml` は **推論と仮想購入記録のクラウド実行用**です。

### 初回のみ必要な準備
1. このチャットで配布された `競艇AI_モーター節間_3連単120通り_学習済みモデル.zip` に含まれる3個の `with_motor_rank*.joblib` と `学習検証結果.json` を取り出し、4ファイルをZIPにまとめて `boat-ai/runtime/model_bundle.zip` にアップロードする。（本リポジトリにはまだモデルバイナリがありません）
2. 正規に取得した「予想時点での」6艇の統計特徴量28項目を含むCSVを `boat-ai/runtime/input/entries.csv` に置く。サンプル形式は前回配布の `入力例_過去レース6艇.csv`。
3. 120通りの締切前オッズと `observed_jst` を含むCSVを `boat-ai/runtime/input/odds.csv` に置く。例は `odds_historical_20261031.csv`。
4. Actions > Boat AI paper prediction (manual) > Run workflow を選ぶ。データが最新であると検証できた日だけ `live` を使う。結果は Actions の Artifact から取得。

**絶対に過去の特徴量を日付だけ変更して使わないこと。** `live` は `entries.csv` 各艇に `feature_verified=true`, `feature_asof_jst`（JSTのオフセットつき）を要求し、締切後・過去日付を拒否します。情報がそろわない場合は見送りになります。

この処理はスクショをOCRで自動読み取りません。ユーザーがChatGPTへスクショを送り、内容を確認して正式な入力CSVを用意するフローを前提とします。選手統計とモーター更新の**ライブ自動取得は未完成**です。利用許可のないサイトの自動巡回はしません。

予想は必ず仮想購入のみ。120%以上の推定EV、1日2レース、最大3点、日予算1000円という制限。ただし Actions は一回ごとに使い捨ての実行環境なので、`paper_ledger.csv` を毎回保存・再投入しなければ**日をまたぐ通算や同日複数実行の購入制限は保持されません**。そのためこのワークフローは**各実行単位の動作確認用**であり、実戦運用の完全な購入管理には未到達です。

現状の結果: 2026-10-31丸亀1Rの履歴再生で予測120点、仮想購入300円、確定結果4-2-1に対し払戻0円。GitHub Actionsで実際に成功した証拠は、モデルZIPが未配置のためまだありません。
