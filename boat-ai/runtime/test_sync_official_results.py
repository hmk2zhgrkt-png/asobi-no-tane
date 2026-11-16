#!/usr/bin/env python3
"""Strict official next-day label and user-reported discrepancy regression."""
import csv,datetime as dt,gzip,hashlib,io,json,tempfile
from pathlib import Path
from historical_course_dataset import COLUMNS as K_COLUMNS
from sync_official_results import COLUMNS,sync

date='2026-11-16';venue=15
def finished(race,order):
    result=[]
    for boat in range(1,7):
        x=dict.fromkeys(K_COLUMNS,'')
        x.update(date=date,race_code=f'20261116{venue:02d}{race:02d}',
            venue_code=str(venue),race_number=str(race),boat=str(boat),
            racer_id=str(4000+boat),motor_number='5',actual_course=str(boat),
            finish_place=str(order.index(boat)+1),actual_st='0.15',
            source='official fixture',prior_observation_cutoff=date)
        result.append(x)
    return result
with tempfile.TemporaryDirectory() as tmp:
    p=Path(tmp);cache=p/'cache';cache.mkdir()
    rows=finished(11,[1,4,6,2,3,5])+finished(12,[2,1,3,4,5,6])
    buf=io.StringIO(newline='')
    w=csv.DictWriter(buf,fieldnames=K_COLUMNS,lineterminator='\n')
    w.writeheader();w.writerows(rows)
    gz=gzip.compress(buf.getvalue().encode('utf-8-sig'),mtime=0)
    (cache/'2026-11.csv.gz').write_bytes(gz)
    (cache/'2026-11.audit.json').write_text(json.dumps({'sha256':hashlib.sha256(gz).hexdigest(),'racer_rows':len(rows)}))
    archive=p/'archive';archive.mkdir()
    from itertools import permutations
    perms=['-'.join(map(str,x)) for x in permutations(range(1,7),3)]
    for race in (11,12):
        folder=archive/f'20261116-15-{race:02d}';folder.mkdir()
        entry={'date':date,'venue':'丸亀','venue_code':15,'race':race,
            'model_scored_at_jst':'2026-11-16T20:00:00+09:00',
            'cutoff_jst':'2026-11-16T20:14:00+09:00',
            'prospective_model_generated_before_cutoff':True,
            'all120':{k:1/120 for k in perms}}
        (folder/'preclose.json').write_text(json.dumps(entry))
    ledger=p/'validation.csv'
    with ledger.open('w',newline='') as out:
        w=csv.DictWriter(out,fieldnames=COLUMNS,lineterminator='\n')
        w.writeheader()
        rec=dict.fromkeys(COLUMNS,'')
        rec.update(date=date,venue='丸亀',venue_code=15,race=11,actual_trifecta='1-4-6',
                   payout_per_100_yen='',model_ran='true',hit_rate_rank=20,
                   paper_stake_yen=0,paper_return_yen=0,result_source='user_report')
        w.writerow(rec)
    info=sync(cache,archive,ledger,dt.date(2026,11,17))
    assert info['confirmed_user_reports_without_overwriting']==1
    assert info['newly_recorded_official_results']==1
    with ledger.open(newline='') as inp:
        records=list(csv.DictReader(inp))
    assert len(records)==2
    assert records[1]['actual_trifecta']=='2-1-3'
    assert records[1]['payout_per_100_yen']==''
    assert records[0]['hit_rate_rank']=='20', 'Do not overwrite user prediction'
    again=sync(cache,archive,ledger,dt.date(2026,11,17))
    assert again['newly_recorded_official_results']==0, 'Idempotence'
    records[0]['actual_trifecta']='3-1-4'
    with ledger.open('w',newline='') as out:
        w=csv.DictWriter(out,fieldnames=COLUMNS);w.writeheader();w.writerows(records)
    try:sync(cache,archive,ledger,dt.date(2026,11,17))
    except ValueError:pass
    else:raise AssertionError('User-reported versus official K disagreement must fail')
print('PASS next-day official results append, no payout/stake inventions, duplicate idempotence, disagreements reject')
