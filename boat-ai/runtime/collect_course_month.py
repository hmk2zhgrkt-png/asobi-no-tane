#!/usr/bin/env python3
"""Bounded, resumable official-K historical course archive, one calendar month.

Input: official BOAT RACE K LZH race performance; labels are observed entry
course/finish, NEVER current-race predictive features. Each month independently
saves compressed UTF-8 CSV and coverage audit; missing days are not fabricated.
Original experiment 2026-05-01..14 is preserved separately.
"""
import argparse, csv, datetime as dt, gzip, hashlib, io, json
from pathlib import Path
from historical_course_dataset import build, COLUMNS

START=dt.date(2023,11,1)
END=dt.date(2026,10,31)
def bounds(month):
    if len(month)!=7 or month[4]!='-':raise ValueError('Expected YYYY-MM')
    begin=dt.date.fromisoformat(month+'-01')
    if not START<=begin<=END:raise ValueError('Outside approved three-year range')
    if begin.month==12:next_month=dt.date(begin.year+1,1,1)
    else:next_month=dt.date(begin.year,begin.month+1,1)
    end=min(next_month-dt.timedelta(days=1),END)
    return begin,end

def collect(month,out):
    begin,end=bounds(month)
    rows,coverage=build(begin,end,official_lzh=True,max_days=35)
    dest=Path(out);dest.mkdir(parents=True,exist_ok=True)
    data=io.StringIO(newline='')
    writer=csv.DictWriter(data,fieldnames=COLUMNS,lineterminator='\n')
    writer.writeheader();writer.writerows(rows)
    # Gzip compress for Git history; deterministic byte content.
    packed=gzip.compress(data.getvalue().encode('utf-8-sig'),mtime=0)
    target=dest/f'{month}.csv.gz'
    target.write_bytes(packed)
    audit={
       'month':month,'start':begin.isoformat(),'end':end.isoformat(),
       'days_requested':len(coverage),
       'days_downloaded':sum(x['status']=='ok' for x in coverage),
       'days_missing':sum(x['status']!='ok' for x in coverage),
       'clean_six_boat_races':len(rows)//6,
       'racer_rows':len(rows),
       'file':str(target.name),
       'sha256':hashlib.sha256(packed).hexdigest(),
       'days':coverage,
       'data_source':'BOAT RACE official K performance LZH',
       'label_only':True,
       'caution':'Actual entry, ST and finish known only after race; no same-race outcome leakage allowed.'
    }
    (dest/f'{month}.audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if audit['days_downloaded']==0:raise RuntimeError('No days downloaded; refuse empty-month success')
    print(json.dumps({k:v for k,v in audit.items() if k!='days'},ensure_ascii=False))
    return audit

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--month',required=True)
    p.add_argument('--out',default='boat-ai/runtime/course_history_3y')
    a=p.parse_args();collect(a.month,a.out)
