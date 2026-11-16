#!/usr/bin/env python3
"""Append verified completed BOAT RACE K outcomes for archived model races.

Inputs: ONLY checksum-audited results from strictly previous JST dates and
only previously archived predicted races. Keep user reports unchanged if
they agree; mismatch fails closed rather than silently changing records.
Payout unknown means EMPTY, never a made-up amount. No paper/real stakes.
"""
import argparse,csv,datetime as dt,json
from collections import defaultdict
from pathlib import Path
from live_course_history import iter_cache_rows
from audit_forward_models import rank_metrics

JST=dt.timezone(dt.timedelta(hours=9))
COLUMNS=['date','venue','venue_code','race','actual_trifecta',
         'payout_per_100_yen','model_ran','hit_rate_rank','model_probability',
         'hit_rate_top3_hit','paper_stake_yen','paper_return_yen','result_source']

def archived_events(folder):
    events={}
    for path in Path(folder).rglob('*.json'):
        obj=json.loads(path.read_text(encoding='utf-8'))
        key=(obj['date'],int(obj['venue_code']),int(obj['race']))
        if path.name.startswith('research-'):
            continue # baseline archive is enough; avoid multi-model ambiguity
        stamp=dt.datetime.fromisoformat(obj['model_scored_at_jst'])
        cutoff=dt.datetime.fromisoformat(obj['cutoff_jst'])
        prospective=bool(obj.get('prospective_model_generated_before_cutoff') and stamp<cutoff)
        previous=events.get(key)
        if (previous is None or
            (prospective and not previous[2]) or
            (prospective==previous[2] and stamp>previous[0])):
            events[key]=(stamp,obj,prospective)
    return events

def official_race_results(cache,target_date,needed):
    target=dt.date.fromisoformat(str(target_date))
    races=defaultdict(list)
    for row in iter_cache_rows(cache,target):
        key=(row['date'],int(row['venue_code']),int(row['race_number']))
        if key in needed:
            races[key].append(row)
    results={}
    for key,boatrows in races.items():
        if len(boatrows)!=6 or {int(r['boat']) for r in boatrows}!=set(range(1,7)) or {int(r['finish_place']) for r in boatrows}!=set(range(1,7)):
            continue
        ordered=sorted(boatrows,key=lambda x:int(x['finish_place']))
        results[key]='-'.join(str(int(r['boat'])) for r in ordered[:3])
    return results

def sync(cache,archive,results_path,today=None):
    now=today or dt.datetime.now(JST).date()
    events={key:value for key,value in archived_events(archive).items()
            if dt.date.fromisoformat(key[0])<now}
    official=official_race_results(cache,now,events)
    file=Path(results_path)
    with file.open(encoding='utf-8-sig',newline='') as inp:
        r=csv.DictReader(inp)
        if list(r.fieldnames)!=COLUMNS:
            raise ValueError('Unexpected validation ledger schema')
        previous=list(r)
    seen={(r['date'],int(r['venue_code']),int(r['race'])):r for r in previous}
    if len(seen)!=len(previous):raise ValueError('Duplicate result entries')
    added=[]
    confirmed=0
    for key,actual in sorted(official.items()):
        if key in seen:
            if seen[key]['actual_trifecta']!=actual:
                raise ValueError(f'Official result differs from user-reported result for {key}; investigate manually')
            confirmed+=1
            continue
        _,entry,prospective=events[key]
        scores=rank_metrics(entry['all120'],actual)
        rec=dict(zip(COLUMNS,['']*len(COLUMNS)))
        rec.update({'date':key[0],'venue':entry['venue'],'venue_code':key[1],'race':key[2],
           'actual_trifecta':actual,'payout_per_100_yen':'',
           'model_ran':'true','hit_rate_rank':scores['rank'],
           'model_probability':scores['assigned_probability'],
           'hit_rate_top3_hit':str(scores['top3']).lower(),
           'paper_stake_yen':0,'paper_return_yen':0,
           'result_source':'official_K_verified_preclose_model' if prospective else 'official_K_verified_postclose_replay'})
        added.append(rec)
    if added:
        with file.open('w',encoding='utf-8',newline='') as handle:
            w=csv.DictWriter(handle,fieldnames=COLUMNS,lineterminator='\n')
            w.writeheader()
            w.writerows(previous+added)
    stats={'archive_races_before_today':len(events),'verified_k_results':len(official),
           'confirmed_user_reports_without_overwriting':confirmed,
           'newly_recorded_official_results':len(added),
           'new_preclose_model_results':sum('preclose_model' in r['result_source'] for r in added),
           'new_retrospective_result_rows':sum('postclose_replay' in r['result_source'] for r in added),
           'mismatched_results_automatically_rewritten':0,
           'unverified_payouts_added':0,'paper_or_real_bets_added':0}
    print(json.dumps(stats,ensure_ascii=False))
    return stats

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--history',default='boat-ai/runtime/course_history_daily')
    p.add_argument('--archive',default='boat-ai/runtime/preclose_archive')
    p.add_argument('--ledger',default='boat-ai/runtime/validation_results.csv')
    p.add_argument('--today',help='JST today YYYY-MM-DD; testing only')
    a=p.parse_args()
    sync(a.history,a.archive,a.ledger,dt.date.fromisoformat(a.today) if a.today else None)
