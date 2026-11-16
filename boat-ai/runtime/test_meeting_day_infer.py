#!/usr/bin/env python3
"""Validate strict two-racer prior-day K evidence for current meeting day."""
import csv,datetime as dt,gzip,hashlib,io,json,tempfile
from pathlib import Path
from meeting_day_infer import infer_meeting_day
from historical_course_dataset import COLUMNS

date="2026-11-16";venue=15
def row(boat):
    d=dict.fromkeys(COLUMNS,'')
    d.update({'date':'2026-11-15','race_code':'202611151501',
              'venue_code':'15','race_number':'1','boat':str(boat),
              'racer_id':str(4000+boat),'motor_number':'5',
              'actual_course':str(boat),'finish_place':str(boat),
              'actual_st':'0.13','source':'fixture',
              'prior_observation_cutoff':'2026-11-15'})
    return d
with tempfile.TemporaryDirectory() as tmp:
    p=Path(tmp);buf=io.StringIO(newline='')
    w=csv.DictWriter(buf,fieldnames=COLUMNS,lineterminator='\n')
    w.writeheader()
    for boat in range(1,7):w.writerow(row(boat))
    compressed=gzip.compress(buf.getvalue().encode('utf-8-sig'),mtime=0)
    (p/'2026-11.csv.gz').write_bytes(compressed)
    (p/'2026-11.audit.json').write_text(json.dumps({'sha256':hashlib.sha256(compressed).hexdigest(),
                                                    'racer_rows':6}))
    card={}
    for boat in range(1,7):
        card[f'艇{boat}_登録番号']=str(4000+boat)
        for slot in (1,2):
            key=f'艇{boat}_節D1走{slot}_'
            if slot==1:
                card[key+'R番号']='1'
                card[key+'着順']=str(boat)
                card[key+'進入']=str(boat)
    found,evidence=infer_meeting_day(card,date,venue,p)
    assert found==2 and evidence['independent_racers_matched']==6
    assert not evidence['same_day_outcomes_used']
    for boat in range(2,7):
        for suffix in ('R番号','着順','進入'):
            card[f'艇{boat}_節D1走1_'+suffix]=''
    found,_=infer_meeting_day(card,date,venue,p)
    assert found is None,'Only one racer is not sufficient to infer meeting day'
    # A mismatched finishing position must not count as independent evidence.
    card['艇2_節D1走1_R番号']='1'
    card['艇2_節D1走1_着順']='1'
    card['艇2_節D1走1_進入']='2'
    found,_=infer_meeting_day(card,date,venue,p)
    assert found is None
    # Corrupt official source must fail and not silently accept.
    (p/'2026-11.csv.gz').write_bytes(compressed+b'bad')
    try:infer_meeting_day(card,date,venue,p)
    except ValueError:pass
    else:raise AssertionError('Checksum failure not rejected')
print('PASS official result-evidenced day=2, no inferred day from one boat or invalid K audit')
