#!/usr/bin/env python3
"""Permitted motor rating feed -> validated six-boat, race-keyed AI feature rows.

This module DOES NOT scrape boatrace-data.com. Supply CSV only when obtained
with permission, or from a user-provided authorized export.
"""
import argparse,csv,datetime as dt,json,sys
from pathlib import Path
FIELDS=("date","venue","race","boat","motor_number","motor_grade","motor_adjusted_power","motor_top2_rate_pct")
RATINGS=("motor_adjusted_power","motor_top2_rate_pct")
GRADE={"S","A+","A","B","C","D","E","F","W"}
def validate(data, cutoff=None):
    grouped={}
    for i,row in enumerate(data,2):
        for k in FIELDS:
            if not str(row.get(k,"")).strip():raise ValueError(f"row {i}: missing {k}")
        date=dt.date.fromisoformat(row["date"])
        race=int(row["race"]);boat=int(row["boat"])
        if not(1<=race<=12 and 1<=boat<=6):raise ValueError(f"row {i}: invalid race/boat")
        if int(row["motor_number"])<=0:raise ValueError(f"row {i}: invalid motor")
        if row["motor_grade"].upper() not in GRADE:raise ValueError(f"row {i}: invalid grade")
        power=float(row["motor_adjusted_power"]);pct=float(row["motor_top2_rate_pct"])
        if not(-10<power<10 and 0<=pct<=100):raise ValueError(f"row {i}: impossible metrics")
        obs=row.get("observed_at","").strip()
        if cutoff:
            if not obs:raise ValueError(f"row {i}: missing observed_at")
            t=dt.datetime.fromisoformat(obs)
            if t.tzinfo is None or t>cutoff:raise ValueError(f"row {i}: data is not verified pre-cutoff")
        key=(date.isoformat(),str(row["venue"]).strip(),race)
        group=grouped.setdefault(key,{})
        if boat in group:raise ValueError(f"row {i}: duplicate boat {boat}")
        group[boat]=dict(row)
    for key,rows in grouped.items():
        if set(rows)!=set(range(1,7)):raise ValueError(f"{key}: incomplete six boats")
        motors=[r["motor_number"] for r in rows.values()]
        if len(set(motors))!=6:raise ValueError(f"{key}: duplicated motor number")
    return grouped

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--authorized-csv",required=True)
    ap.add_argument("--out",default="motor_features.json")
    ap.add_argument("--cutoff-iso",help="optional ISO8601 with explicit TZ; rejects post-cutoff snapshots")
    args=ap.parse_args()
    with open(args.authorized_csv,encoding="utf-8-sig",newline="") as f:rows=list(csv.DictReader(f))
    cutoff=dt.datetime.fromisoformat(args.cutoff_iso) if args.cutoff_iso else None
    if cutoff is not None and cutoff.tzinfo is None:raise ValueError("cutoff must specify timezone")
    groups=validate(rows,cutoff)
    payload=[]
    for (date,venue,race),boats in sorted(groups.items()):
        payload.extend([{"date":date,"venue":venue,"race":race,"boat":b,
             "motor_number":int(boats[b]["motor_number"]),
             "motor_grade":boats[b]["motor_grade"],
             "motor_adjusted_power":float(boats[b]["motor_adjusted_power"]),
             "motor_top2_rate_pct":float(boats[b]["motor_top2_rate_pct"]),
             "source":boats[b].get("source","authorized export"),
             "observed_at":boats[b].get("observed_at","")} for b in range(1,7)])
    Path(args.out).write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Validated {len(groups)} races / {len(payload)} boats. This is feature import, NOT trained-model scoring.")
if __name__=="__main__":main()
