#!/usr/bin/env python3
"""Incremental official K-file daily completion cache for the live prediction AI.

Reads completed prior dates only, never today's races. Creates one compressed
monthly checkpoint with one record per six-boat complete race and an auditable
per-day provenance. Missing and cancelled days are logged, never fabricated.
The three-year 2023-11..2026-10 source remains immutable.
"""
import argparse,csv,datetime as dt,gzip,hashlib,io,json
from pathlib import Path
from official_lzh_course import official_day
from historical_course_dataset import COLUMNS

JST=dt.timezone(dt.timedelta(hours=9))
MIN_DATE=dt.date(2026,11,1)

def month_bounds(target):
    start=dt.date(target.year,target.month,1)
    return max(start,MIN_DATE),target

def build(target,base,fetch=official_day):
    if target<MIN_DATE:raise ValueError('Cannot fetch before 2026-11-01')
    today=dt.datetime.now(JST).date()
    if target>=today:raise ValueError('Target must be strictly prior to today (JST)')
    month=target.strftime('%Y-%m')
    dest=Path(base);dest.mkdir(parents=True,exist_ok=True)
    compressed=dest/(month+'.csv.gz')
    auditfile=dest/(month+'.audit.json')
    prior={}
    rows_by_date={}
    if auditfile.is_file() and compressed.is_file():
        audit=json.loads(auditfile.read_text(encoding='utf-8'))
        if hashlib.sha256(compressed.read_bytes()).hexdigest()!=audit['sha256']:
            raise ValueError('Previous live history checkpoint checksum mismatch')
        if audit['month']!=month:raise ValueError('History checkpoint month mismatch')
        prior={e['date']:e for e in audit['days']}
        with gzip.open(compressed,'rt',encoding='utf-8-sig',newline='') as f:
            for row in csv.DictReader(f):
                if row['date']>=today.isoformat():
                    raise ValueError('Existing checkpoint contains current/future labels')
                rows_by_date.setdefault(row['date'],[]).append(row)
    start,end=month_bounds(target)
    for delta in range((end-start).days+1):
        day=start+dt.timedelta(days=delta)
        key=day.isoformat()
        if prior.get(key,{}).get('status')=='ok':continue
        try:
            rows,stats=fetch(day)
            if not rows:raise ValueError('No complete races (unavailable or cancelled)')
            if any(r['date']!=key for r in rows):raise ValueError('Wrong date in official results')
            rows_by_date[key]=rows
            prior[key]={'date':key,'status':'ok',**stats}
        except (ValueError,RuntimeError,OSError,FileNotFoundError,ImportError) as exc:
            prior[key]={'date':key,'status':'unavailable','error':str(exc)[:260]}
    allrows=[r for d in sorted(rows_by_date) if d<=end.isoformat() for r in rows_by_date[d]]
    allrows.sort(key=lambda r:(r['date'],r['race_code'],int(r['boat'])))
    if len(allrows)%6:raise ValueError('Missing racer rows in cache')
    buf=io.StringIO(newline='')
    writer=csv.DictWriter(buf,fieldnames=COLUMNS,lineterminator='\n')
    writer.writeheader();writer.writerows(allrows)
    content=gzip.compress(buf.getvalue().encode('utf-8-sig'),mtime=0)
    checksum=hashlib.sha256(content).hexdigest()
    days=[prior[k] for k in sorted(prior) if k<=end.isoformat()]
    report={'month':month,'asof':end.isoformat(),'file':compressed.name,
            'sha256':checksum,'days_requested':(end-start).days+1,
            'days_downloaded':sum(z['status']=='ok' for z in days),
            'days_missing':sum(z['status']!='ok' for z in days),
            'racer_rows':len(allrows),'clean_six_boat_races':len(allrows)//6,
            'days':days,'source':'official BOATRACE completed K-LZH',
            'pre_race_safe_cutoff':'all dates strictly before execution day JST',
            'model_retrained':False}
    compressed.write_bytes(content)
    auditfile.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return report

def iter_cache_rows(base,target_date):
    """Yield checksum-verified monthly live history labels strictly before race date."""
    target=dt.date.fromisoformat(str(target_date))
    for f in sorted(Path(base).glob('*.csv.gz')):
        auditfile=f.with_name(f.name.replace('.csv.gz','.audit.json'))
        if not auditfile.exists():raise ValueError('Missing K cache audit '+f.name)
        audit=json.loads(auditfile.read_text(encoding='utf-8'))
        if hashlib.sha256(f.read_bytes()).hexdigest()!=audit['sha256']:
            raise ValueError('K cache checksum mismatch '+f.name)
        count=0
        with gzip.open(f,'rt',encoding='utf-8-sig',newline='') as inp:
            for row in csv.DictReader(inp):
                count+=1
                if row['date']<target.isoformat():
                    yield row
        if count!=audit['racer_rows']:
            raise ValueError('K cache row-count mismatch '+f.name)

def racer_motor_updates(base,target_date,venue_name_lookup):
    """Return actual completed-race deltas from cache up through target_date-1.

    Official K result archives do not have pre-race relative exhibition, so
    motor exhibition data is null. The historical K motor number must also
    be validated against current cycle later in auto_predict.
    """
    target=dt.date.fromisoformat(str(target_date))
    racers=[];motors=[];seen=set();source_days=set()
    for f in sorted(Path(base).glob('*.csv.gz')):
        audit_path=f.with_name(f.name.replace('.csv.gz','.audit.json'))
        if not audit_path.exists():raise ValueError('Missing cache audit for '+f.name)
        audit=json.loads(audit_path.read_text(encoding='utf-8'))
        if hashlib.sha256(f.read_bytes()).hexdigest()!=audit['sha256']:
            raise ValueError('Bad cache checksum '+f.name)
        with gzip.open(f,'rt',encoding='utf-8-sig',newline='') as inp:
            for row in csv.DictReader(inp):
                d=row['date']
                if d>=target.isoformat():continue
                code=row['race_code'];boat=int(row['boat'])
                key=(code,boat)
                if key in seen:raise ValueError('Duplicate racer record '+str(key))
                seen.add(key);source_days.add(d)
                rid=int(row['racer_id']);venue=int(row['venue_code']);place=int(row['finish_place'])
                name=venue_name_lookup[venue-1];motor=int(row['motor_number'])
                racers.append([d,str(rid),name,boat,place])
                motors.append([d,name,motor,rid,place,None,int(row['race_number'])])
    return racers,motors,sorted(source_days)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--through',help='Last completed date YYYY-MM-DD, defaults to yesterday JST')
    p.add_argument('--base',default='boat-ai/runtime/course_history_daily')
    args=p.parse_args()
    target=dt.date.fromisoformat(args.through) if args.through else dt.datetime.now(JST).date()-dt.timedelta(days=1)
    result=build(target,args.base)
    print(json.dumps({k:v for k,v in result.items() if k!='days'},ensure_ascii=False))
