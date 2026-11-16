#!/usr/bin/env python3
"""Build audit-ready historical (racer, actual entry course, finishing place) records.

Input is BoatraceCSV daily programs/race_cards and results/realtime:
both joined strictly by 12-digit race code. The actual course and final place
are outcome labels, NEVER same-race pre-start prediction features.
Daily missing files are reported, not imputed; disqualified/incomplete races
are excluded. Can use --source-root for pre-downloaded historical data.

Official race files: https://boatrace.jp/owpc/pc/extra/data/download.html
BoatraceCSV schema: https://github.com/BoatraceCSV/boatracecsv.github.io/blob/main/docs/data/results.md
"""
import argparse
import collections
import csv
import datetime as dt
import io
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ORIGINS=(
 "https://boatracecsv.github.io/data/",
 "https://raw.githubusercontent.com/BoatraceCSV/boatracecsv.github.io/main/data/",
 "https://cdn.jsdelivr.net/gh/BoatraceCSV/boatracecsv.github.io@main/data/",
)
COLUMNS=("date","race_code","venue_code","race_number","boat","racer_id","motor_number","actual_course",
         "finish_place","actual_st","prior_observation_cutoff","source")
ID_REGEX=re.compile(r"^\d{12}$")

def get_daily(kind,date,root=None,opener=urlopen):
    rel=f"{kind}/{date:%Y/%m/%d}.csv"
    if root:
        file=Path(root)/rel
        if not file.is_file():raise FileNotFoundError(file)
        raw=file.read_bytes()
    else:
        errors=[]
        for urlroot in ORIGINS:
            try:
                with opener(Request(urlroot+rel,headers={"User-Agent":"boat-ai-course-training/1.0"}),timeout=9) as resp:
                    raw=resp.read()
                break
            except (HTTPError,URLError,OSError,TimeoutError) as ex:
                errors.append(type(ex).__name__+":"+str(getattr(ex,"code","network")))
        else:raise FileNotFoundError("All sources unavailable for "+rel+" ("+",".join(errors)+")")
    text=raw.decode("utf-8-sig")
    reader=csv.DictReader(io.StringIO(text))
    required=("レースコード",)
    if not reader.fieldnames or any(k not in reader.fieldnames for k in required):
        raise ValueError("Malformed CSV: "+rel)
    data=list(reader)
    if not data:raise ValueError("Empty CSV: "+rel)
    return data

def join_day(cards,results,date):
    """Return one row per racer in clean races; skip any ambiguous/incomplete race."""
    card_by=collections.defaultdict(list)
    result_by=collections.defaultdict(list)
    for card in cards:card_by[card.get("レースコード")].append(card)
    for result in results:result_by[result.get("レースコード")].append(result)
    joined=[];audit=collections.Counter()
    for code,found in card_by.items():
        if not ID_REGEX.fullmatch(str(code or "")) or code[:8]!=f"{date:%Y%m%d}":
            audit["bad_race_code"]+=1;continue
        if len(found)!=1 or len(result_by.get(code,[]))!=1:
            audit["missing_or_ambiguous_result"]+=1;continue
        card,res=found[0],result_by[code][0]
        try:
            racer={b:int(card[f"艇{b}_登録番号"]) for b in range(1,7)}
            motor={b:int(card[f"艇{b}_モーター番号"]) for b in range(1,7)}
            courses={int(res[f"{n}コース_艇番"]):n for n in range(1,7)}
            ranks={int(res[f"{n}着_艇番"]):n for n in range(1,7)}
            if (set(racer)!=set(courses) or set(racer)!=set(ranks) or
                len(set(racer.values()))!=6 or len(set(courses.values()))!=6 or
                len(set(ranks.values()))!=6 or min(racer.values())<1000):
                raise ValueError("Incomplete/duplicate boats")
            venue=int(code[8:10]);rno=int(code[10:12])
            if not (1<=venue<=24 and 1<=rno<=12):raise ValueError("Bad venue/race")
            rows=[]
            for boat in range(1,7):
                course=courses[boat]
                st=res.get(f"{course}コース_スタートタイミング","")
                # ST is an observed outcome, not a predictive feature.
                rows.append(dict(date=date.isoformat(),race_code=code,venue_code=venue,race_number=rno,
                                 boat=boat,racer_id=racer[boat],motor_number=motor[boat],
                                 actual_course=course,finish_place=ranks[boat],actual_st=st,
                                 prior_observation_cutoff=date.isoformat(),
                                 source="BoatraceCSV:race_cards+realtime"))
            joined.extend(rows)
            audit["complete_races"]+=1
        except (ValueError,KeyError,TypeError):
            audit["invalid_result_or_card"]+=1
    audit["joined_racer_rows"]=len(joined)
    return joined,dict(audit)

def build(start,end,root=None,max_days=45):
    if end<start or (end-start).days>=max_days:raise ValueError("Refuse invalid/excessive requested date range")
    allrows=[];report=[]
    for n in range((end-start).days+1):
        day=start+dt.timedelta(days=n)
        try:
            cards=get_daily("programs/race_cards",day,root=root)
            results=get_daily("results/realtime",day,root=root)
            rows,stats=join_day(cards,results,day)
            allrows.extend(rows)
            report.append(dict(date=day.isoformat(),status="ok",**stats))
        except (FileNotFoundError,ValueError,UnicodeError) as err:
            report.append(dict(date=day.isoformat(),status="unavailable",reason=str(err)[:350]))
    allrows.sort(key=lambda r:(r["date"],r["race_code"],r["boat"]))
    return allrows,report

def write(rows,days,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    with (out/"historical_course_labels.csv").open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=COLUMNS)
        writer.writeheader();writer.writerows(rows)
    summary={"days_requested":len(days),"days_successful":sum(d["status"]=="ok" for d in days),
             "days_unavailable":sum(d["status"]=="unavailable" for d in days),
             "complete_races":len(rows)//6,"racer_rows":len(rows),
             "coverage_by_day":days,
             "caution":"Actual course/finish/ST are postrace labels, never pre-race features."}
    (out/"audit.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    return summary

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--start",required=True)
    ap.add_argument("--end",required=True)
    ap.add_argument("--source-root",default=None)
    ap.add_argument("--max-days",type=int,default=45)
    ap.add_argument("--out",required=True)
    args=ap.parse_args()
    rows,days=build(dt.date.fromisoformat(args.start),dt.date.fromisoformat(args.end),args.source_root,args.max_days)
    summary=write(rows,days,args.out)
    print(json.dumps({k:v for k,v in summary.items() if k!="coverage_by_day"},ensure_ascii=False))
