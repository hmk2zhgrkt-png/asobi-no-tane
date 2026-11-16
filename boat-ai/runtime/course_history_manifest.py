#!/usr/bin/env python3
"""Audit all archived monthly actual-course datasets, with immutable sha256 checks."""
import argparse, datetime as dt, gzip, hashlib, io, csv, json
from pathlib import Path

def months():
    d=dt.date(2023,11,1);last=dt.date(2026,10,1)
    while d<=last:
        yield d.strftime('%Y-%m')
        d=dt.date(d.year+1,1,1) if d.month==12 else dt.date(d.year,d.month+1,1)

def build(root):
    base=Path(root)
    found=[];missing=[]
    for month in months():
        auditpath=base/f'{month}.audit.json'
        if not auditpath.exists():
            missing.append(month)
            continue
        audit=json.loads(auditpath.read_text(encoding='utf-8'))
        assert audit['month']==month
        filename=base/f'{month}.csv.gz'
        # Zero-day months are archived as errors, not treated as recovered.
        if audit['days_downloaded']>0:
            if not filename.is_file():
                raise ValueError(f'Expected {month} archive with positive downloaded days')
            packed=filename.read_bytes()
            if hashlib.sha256(packed).hexdigest()!=audit['sha256']:
                raise ValueError('Archive SHA256 mismatch: '+month)
            with gzip.open(filename,'rt',encoding='utf-8-sig',newline='') as reader:
                count=sum(1 for _ in csv.DictReader(reader))
            if count!=audit['racer_rows'] or count%6:
                raise ValueError('Archive racer row mismatch: '+month)
            if audit['clean_six_boat_races']!=count//6:
                raise ValueError('Archive race count mismatch: '+month)
        found.append({key:audit[key] for key in
          ('month','days_requested','days_downloaded','days_missing','clean_six_boat_races','racer_rows','sha256')})
    result={'period_start':'2023-11-01','period_end':'2026-10-31',
      'total_months':36,'audited_months':len(found),'no_audit_months':missing,
      'days_requested':sum(z['days_requested'] for z in found),
      'days_downloaded':sum(z['days_downloaded'] for z in found),
      'days_missing':sum(z['days_missing'] for z in found),
      'clean_six_boat_races':sum(z['clean_six_boat_races'] for z in found),
      'racer_rows':sum(z['racer_rows'] for z in found),
      'by_month':found,'replay_only':True,'production_model_retrained':False,
      'caution':'Actual entry and finish are postrace labels; never mix into preclose model inputs.'}
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--root',default='boat-ai/runtime/course_history_3y')
    a=p.parse_args()
    manifest=build(a.root)
    dest=Path(a.root)/'manifest.json'
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in manifest.items() if k not in ('by_month','no_audit_months')},ensure_ascii=False))
