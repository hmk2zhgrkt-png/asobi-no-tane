# 競艇AI：過去の直前データ取得

This directory only holds public-data collection code. It does not change the existing あそびのタネ web app.

Workflow: **Actions → Boat AI - fetch historical pre-race snapshots → Run workflow**.

Default range: 2025-11-01 through 2026-10-31. It downloads publicly available `stt` (start exhibition), `sui` (weather/wave), `tkz` (exhibition times), and `od3` (120 trifecta odds) CSV files. A ZIP artifact contains actual verified files and `取得監査.csv` reporting missing/failed days.

These CSV snapshots have timestamps, but **must still be checked to precede race cutoff** before training. This workflow does not download data for dates where no public file exists and never fills missing records. It is a retrieval step, **not** AI retraining or an automatic betting system.

Data source: https://boatracecsv.github.io/docs/data/previews.html
