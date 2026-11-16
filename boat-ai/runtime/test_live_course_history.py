#!/usr/bin/env python3
"""Offline regression of pre-race official K checkpoint / live feature delta."""
import datetime as dt,gzip,json,csv,tempfile
from pathlib import Path
from live_course_history import build,racer_motor_updates
from historical_course_dataset import COLUMNS
VENUES=['桐生','戸田','江戸川','平和島','多摩川','浜名湖','蒲郡','常滑','津','三国','びわこ','住之江','尼崎','鳴門','丸亀','児島','宮島','徳山','下関','若松','芦屋','福岡','唐津','大村']
d=dt.date(2026,11,1)
calls=[]
def fake(day):
    calls.append(day)
    code=f'{day:%Y%m%d}1801'
    rows=[dict(date=day.isoformat(),race_code=code,venue_code=18,race_number=1,
               boat=boat,racer_id=4000+boat,motor_number=boat,
               actual_course=boat,finish_place=boat,actual_st="0.13",
               prior_observation_cutoff=day.isoformat(),source="test fixture") for boat in range(1,7)]
    return rows,{"complete_races":1}
with tempfile.TemporaryDirectory() as temp:
    root=Path(temp)
    s=build(d+dt.timedelta(days=1),root,fake)
    assert s['days_downloaded']==2 and s['racer_rows']==12
    s2=build(d+dt.timedelta(days=1),root,fake)
    assert s2['days_downloaded']==2 and len(calls)==2, "Fetch must be idempotent"
    a,b,days=racer_motor_updates(root,dt.date(2026,11,2),VENUES)
    assert len(a)==6 and len(b)==6 and days==['2026-11-01'], "Same-day labels must be excluded"
    a,b,days=racer_motor_updates(root,dt.date(2026,11,3),VENUES)
    assert len(a)==12 and len(b)==12
    audit=json.loads((root/'2026-11.audit.json').read_text())
    assert audit['sha256'] and audit['racer_rows']==12
    # checksum corruption must fail closed
    f=root/'2026-11.csv.gz'
    f.write_bytes(f.read_bytes()+b'bad')
    try:racer_motor_updates(root,dt.date(2026,11,3),VENUES)
    except ValueError:pass
    else:raise AssertionError('Corruption was not rejected')
print('PASS: idempotent incremental official K history, cutoff, checksums, six-boat rows')
