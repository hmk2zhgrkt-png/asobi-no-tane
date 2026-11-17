#!/usr/bin/env python3
"""Read live preclose wind-from compass for EXACT boat race from BoatraceCSV.

This is optional. Source may lag, return a postclose revision, or be missing.
Never use unverified post-cutoff row, a different race, or a direction guessed
from a picture's unlabelled arrow. No current-day outcome data used.
"""
import datetime as dt
from venue_conditions import ALIASES
from source_fetch import fetch_csv,SourceUnavailable

JST=dt.timezone(dt.timedelta(hours=9))
def select_preclose_wind(rows,code,date,cutoff,now=None,max_age_minutes=35):
    now=now or dt.datetime.now(JST)
    date=dt.date.fromisoformat(str(date))
    if not cutoff.tzinfo or not now.tzinfo:raise ValueError("Timezone required")
    valid=[]
    for row in rows:
        if str(row.get("レースコード",""))!=str(code):continue
        raw=str(row.get("風向","")).strip()
        if raw not in ALIASES:continue
        try:stamp=dt.datetime.fromisoformat(str(row.get("取得日時","")))
        except (TypeError,ValueError):continue
        if stamp.tzinfo is None or stamp.astimezone(JST).date()!=date:continue
        if not (stamp<=now and stamp<=cutoff):continue
        if (cutoff-stamp).total_seconds()>max_age_minutes*60:continue
        valid.append((stamp,ALIASES[raw]))
    if not valid:return None
    valid.sort(key=lambda x:x[0])
    newest=valid[-1]
    if any(d!=newest[1] for stamp,d in valid if stamp==newest[0]):
        raise ValueError("Conflicting same-time wind data")
    return {'wind_from':newest[1],'source_observed_at_jst':newest[0].astimezone(JST).isoformat(),
            'source':'BoatraceCSV previews/sui, race code and cutoff verified',
            'source_url':'https://boatracecsv.github.io/docs/data/'}

def lookup(date,venue,race,cutoff,now=None):
    code=f'{date:%Y%m%d}{int(venue):02d}{int(race):02d}'
    try:rows,_=fetch_csv('previews/sui',date)
    except (ValueError,SourceUnavailable,OSError,TimeoutError):
        return None
    return select_preclose_wind(rows,code,date,cutoff,now)
