#!/usr/bin/env python3
"""Fetch public third-party Kakuyomu ranking samples for the static website.
Metadata only. Attribution: https://rank-kakuyomu.click/api-spec (CC BY 4.0).
"""
import json, os, random, time, urllib.request, urllib.error
from datetime import date, timedelta, datetime, timezone
from pathlib import Path

BASE="https://rank-kakuyomu.click"
OUT=Path(__file__).resolve().parent.parent/"novel-needs"/"snapshots.json"
GENRES={"general":"総合","fantasy":"異世界ファンタジー","action":"現代ファンタジー","romance":"恋愛","drama":"現代ドラマ","sf":"SF"}
def request(path):
    req=urllib.request.Request(BASE+path,headers={"User-Agent":"NovelNeedsResearch/1.0 (personal, metadata-only; source https://rank-kakuyomu.click/api-spec)","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=25) as res:
        return json.load(res)
def latest_date(data):
    if isinstance(data,str): return data
    for k in ("date","latest_date","latestDate","latest"):
        if isinstance(data.get(k),str): return data[k]
    if isinstance(data.get("data"),dict): return latest_date(data["data"])
    raise ValueError("unknown latest-date schema")
def items(data):
    if isinstance(data,list):return data
    if not isinstance(data,dict):return []
    for key in ("rankings","works","items","results","data","ranking","entries"):
        if key in data:
            v=items(data[key])
            if v:return v
    return []
def norm_tags(values):
    if isinstance(values,str):
        return [x.strip() for x in values.replace("・",",").replace("|",",").split(",") if x.strip()]
    if not isinstance(values,list):return []
    return [t if isinstance(t,str) else str(t.get("name") or t.get("label") or t.get("tag_name") or "") for t in values if isinstance(t,(str,dict))]
def normalize(raw, d, key):
    result=[]
    for i,entry in enumerate(items(raw),start=1):
        if not isinstance(entry,dict):continue
        w=entry.get("work") if isinstance(entry.get("work"),dict) else entry
        title=w.get("title") or w.get("name")
        if not isinstance(title,str) or not title.strip(): continue
        wid=w.get("work_id") or w.get("id") or entry.get("work_id")
        url=w.get("url") or ("https://kakuyomu.jp/works/"+str(wid) if wid and str(wid).isdigit() else "")
        result.append({"title":title[:250],"genre":str(w.get("genre_name") or w.get("genre") or GENRES[key]),"tags":norm_tags(w.get("tags") or w.get("tag_labels") or w.get("tagLabels") or [])[:30],"rank":entry.get("rank") or w.get("rank") or i,"date":d,"platform":"カクヨム","url":url,"source":BASE})
    return result

def main():
    prior={}
    if OUT.exists():
        try:prior=json.loads(OUT.read_text(encoding="utf8"))
        except (ValueError,OSError):pass
    try:
        latest=latest_date(request("/api/v1/dates/latest"))
        reference=date.fromisoformat(latest)
    except Exception as exc:
        print("Cannot get latest date:",exc)
        if OUT.exists():return
        raise
    dates=[(reference-timedelta(days=delta)).isoformat() for delta in (0,7,30)]
    snapshots=prior.get("snapshots",{}) if isinstance(prior.get("snapshots"),dict) else {}
    errors=[]
    for d in dates:
        for key in GENRES:
            cache_key=f"{d}|weekly|{key}"
            # Fetch current snapshot on every scheduled run; keep older records.
            if d!=latest and cache_key in snapshots:continue
            try:
                rows=normalize(request(f"/api/v1/dates/{d}/rankings/weekly/{key}"),d,key)
                if not rows:raise ValueError("no recognized works")
                snapshots[cache_key]=rows
                print(cache_key,len(rows))
            except Exception as exc:
                errors.append(f"{cache_key}: {exc}")
                print("Failed:",cache_key,exc)
            time.sleep(0.55)
    # Retain bounded history (90d) for trend comparisons.
    cutoff=(reference-timedelta(days=90)).isoformat()
    snapshots={k:v for k,v in snapshots.items() if k[:10]>=cutoff}
    if not snapshots and not OUT.exists():raise RuntimeError("No usable rankings. "+"; ".join(errors))
    result={"provider":"データで楽しむカクヨム","provider_url":BASE+"/api-spec","license":"CC BY 4.0","collected_at":datetime.now(timezone.utc).isoformat(),"latest_date":latest,"snapshots":snapshots,"errors":errors[:20]}
    OUT.write_text(json.dumps(result,ensure_ascii=False,separators=(",",":")),encoding="utf8")
    print(f"Saved {len(snapshots)} dated ranking sets; {len(errors)} errors")
if __name__=="__main__":main()
