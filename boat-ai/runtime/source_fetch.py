#!/usr/bin/env python3
"""Verified multi-origin BoatraceCSV reader.

Tries independent delivery paths (GitHub Pages, raw GitHub, jsDelivr), never
inventing data. Race-specific schema/completeness checks remain in auto_predict.
Boatcast is an upstream race-card provenance check ONLY; it is *not* an
interchangeable CSV representation and must not be passed to the trained model.
"""
import csv
import datetime as dt
import io
import os
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ORIGINS = (
    "https://boatracecsv.github.io/data/",
    "https://raw.githubusercontent.com/BoatraceCSV/boatracecsv.github.io/main/data/",
    "https://cdn.jsdelivr.net/gh/BoatraceCSV/boatracecsv.github.io@main/data/",
)
# Guard against accidentally accepting an HTML error page returned as HTTP 200.
REQUIRED_COLUMNS = {
    "programs/race_cards": ("レースコード", "艇1_登録番号", "艇6_登録番号"),
    "programs/title": ("レースコード", "電話投票締切予定"),
    "programs/motor_stats": ("場コード", "モーター番号"),
    "previews/tkz": ("レースコード", "取得日時", "艇1_展示タイム"),
    "previews/stt": ("レースコード", "取得日時"),
    "previews/sui": ("レースコード", "取得日時"),
    "previews/od3": ("レースコード", "取得日時", "3連単_1-2-3"),
    "results/realtime": ("レースコード",),
    "results/payouts": ("レースコード", "3連単_組番"),
}

class SourceUnavailable(RuntimeError):
    pass

def decode_csv(raw, kind):
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("No CSV header")
    needed = REQUIRED_COLUMNS.get(kind, ("レースコード",))
    if not all(key in reader.fieldnames for key in needed):
        raise ValueError("Unexpected CSV schema, missing " + ",".join(set(needed)-set(reader.fieldnames)))
    rows = list(reader)
    if not rows:
        raise ValueError("Empty CSV data")
    return rows

def fetch_csv(kind, date, opener=urlopen, origins=ORIGINS):
    date = dt.date.fromisoformat(str(date)) if not isinstance(date, dt.date) else date
    rel = f"{kind}/{date:%Y/%m/%d}.csv"
    failures = []
    for origin in origins:
        url = origin + rel
        try:
            req = Request(url, headers={"User-Agent": "boat-ai-public-model/1.1", "Accept": "text/csv,*/*"})
            with opener(req, timeout=8) as response:
                raw = response.read()
            return decode_csv(raw,kind), origin
        except (HTTPError, URLError, TimeoutError, ValueError, UnicodeError, OSError) as exc:
            failures.append(f"{origin.split('/')[2]}: {type(exc).__name__} {getattr(exc,'code',str(exc))}")
    raise SourceUnavailable(f"{kind} {date}: all {len(origins)} delivery paths failed: " + " | ".join(failures))

def boatcast_race_card_url(date, venue, race):
    date = dt.date.fromisoformat(str(date)) if not isinstance(date,dt.date) else date
    if not (1<=int(venue)<=24 and 1<=int(race)<=12):
        raise ValueError("Invalid venue/race")
    jo=str(int(venue)).zfill(2)
    return f"https://race.boatcast.jp/hp_txt/{jo}/bc_j_str3_{date:%Y%m%d}_{jo}_{int(race)}.txt"

def check_upstream_card(date,venue,race,opener=urlopen):
    """Optional diagnostic: HTTP access to upstream Boatcast. No model feature substitution."""
    url=boatcast_race_card_url(date,venue,race)
    try:
        with opener(Request(url,headers={"User-Agent":"boat-ai-public-model/1.1"}),timeout=5) as response:
            raw=response.read()
        return {"source":"race.boatcast.jp","available":bool(raw),"bytes":len(raw),
                "usable_as_model_csv":False}
    except (HTTPError, URLError, TimeoutError, OSError) as e:
        return {"source":"race.boatcast.jp","available":False,"error":type(e).__name__,
                "usable_as_model_csv":False}
