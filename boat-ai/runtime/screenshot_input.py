#!/usr/bin/env python3
"""Structured bridge from user-provided race screenshots to model CSV rows.

ChatGPT reads the user's attached screenshots, transcribes visible values into
screenshot_input.json, then commits this file before requesting a race. This
module does NOT pretend GitHub Actions can see ChatGPT image attachments.
Unseen values are left absent; no synthetic odds or weather observations.
"""
import datetime as dt
import itertools
import json
import math
import re
from pathlib import Path

JST=dt.timezone(dt.timedelta(hours=9))
COMBOS={"-".join(map(str,c)) for c in itertools.permutations(range(1,7),3)}

def _stamp(value):
    stamp=dt.datetime.fromisoformat(value)
    if stamp.tzinfo is None:raise ValueError("Screenshot observed_at_jst must include timezone")
    return stamp.astimezone(JST)

def _finite(x, low, high):
    if isinstance(x,bool) or x is None:raise ValueError("Missing screenshot numeric field")
    v=float(x)
    if not math.isfinite(v) or not low<=v<=high:raise ValueError(f"Screenshot field out of range: {x}")
    return v

def _six(values,low,high,field):
    if not isinstance(values,(list,tuple)) or len(values)!=6:raise ValueError(field+" must contain exactly six boat values")
    return [_finite(v,low,high) for v in values]

def read_screenshot(path,date,venue,race):
    if not path or not Path(path).exists():return None
    obj=json.loads(Path(path).read_text(encoding="utf-8"))
    expected={"date":str(date),"venue":int(venue),"race":int(race)}
    if any(obj.get(k)!=v for k,v in expected.items()):
        # Ignore other-race screenshot, preventing accidental leakage across races.
        return None
    if obj.get("source")!="chat_screenshot" or obj.get("transcribed_by")!="assistant":
        raise ValueError("Screenshot must be explicitly transcribed from the conversation")
    observed=_stamp(obj["observed_at_jst"])
    if observed.date()!=date:raise ValueError("Screenshot timestamp date must match race")
    if observed>dt.datetime.now(JST)+dt.timedelta(seconds=10):
        raise ValueError("Screenshot timestamp lies in the future")
    data=obj.get("fields",{})
    if not isinstance(data,dict):raise ValueError("Missing screenshot fields object")
    result={"observed":observed,"cutoff":obj.get("cutoff_jst",""),"previews":{},"odds_count":0,"complete_odds":False,"notes":[]}
    code=f"{date:%Y%m%d}{int(venue):02d}{int(race):02d}"
    base={"レースコード":code,"取得日時":observed.isoformat()}
    if "exhibition_time" in data or "tilt" in data:
        tkz=dict(base)
        if "exhibition_time" in data:
            for i,v in enumerate(_six(data["exhibition_time"],5.5,9.0,"exhibition_time"),1):
                tkz[f"艇{i}_展示タイム"]=str(v)
        if "tilt" in data:
            for i,v in enumerate(_six(data["tilt"],-2,3,"tilt"),1):
                tkz[f"艇{i}_チルト"]=str(v)
        result["previews"]["previews/tkz"]=tkz
    if "exhibition_st" in data or "entry_course" in data:
        st=dict(base)
        if "exhibition_st" in data:
            for i,v in enumerate(_six(data["exhibition_st"],-1,1,"exhibition_st"),1):
                st[f"艇{i}_スタート展示"]=str(v)
        if "entry_course" in data:
            courses=[int(v) for v in _six(data["entry_course"],1,6,"entry_course")]
            if set(courses)!=set(range(1,7)):raise ValueError("Entry courses must be a 1-6 permutation")
            for i,v in enumerate(courses,1):st[f"艇{i}_コース"]=str(v)
        result["previews"]["previews/stt"]=st
    if "wind_speed_m" in data or "wave_cm" in data:
        weather=dict(base)
        if "wind_speed_m" in data:weather["風速(m)"]=str(_finite(data["wind_speed_m"],0,35))
        if "wave_cm" in data:weather["波の高さ(cm)"]=str(_finite(data["wave_cm"],0,150))
        result["previews"]["previews/sui"]=weather
    if "odds" in data:
        odds=data["odds"]
        if not isinstance(odds,dict) or not odds:raise ValueError("Screenshot odds must be a nonempty map")
        invalid=set(odds)-COMBOS
        if invalid:raise ValueError(f"Invalid trifecta combination: {sorted(invalid)[:3]}")
        row=dict(base)
        for key,value in odds.items():
            row["3連単_"+key]=str(_finite(value,1.001,20000))
        result["odds_count"]=len(odds)
        result["complete_odds"]=len(odds)==120
        result["previews"]["previews/od3"]=row
    return result

def overlay_screenshot(base,screenshot,kind,code,close):
    """Merge only visibly transcribed fields, retaining verified original others."""
    current=screenshot["previews"].get(kind)
    if current is None:return base
    if screenshot["observed"]>close:raise ValueError("Screenshot observations after cutoff cannot be preclose inputs")
    existing=[row for row in base if row.get("レースコード")==code]
    # Never mix older publisher odds with newer screenshot prices. Partial
    # screenshot odds remain partial even if a stale full feed exists.
    merged={} if kind=='previews/od3' else (dict(existing[0]) if len(existing)==1 else {})
    merged.update(current)
    if kind=="previews/tkz" and "締切時刻" not in merged:
        merged["締切時刻"]=close.strftime("%H:%M")
    return [merged]

def odds_coverage(odds):
    return sum(1 for k in COMBOS if odds.get("3連単_"+k) not in (None,""))
