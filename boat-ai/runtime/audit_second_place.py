#!/usr/bin/env python3
"""Quantify actual second-place frequency for outer boats/courses without hindsight tuning.

This is a descriptive audit of archived result labels, NOT a backtest of the
incumbent 28-feature probability estimator; no historical preclose model
predictions are available. Report 5th boat and actual 5th course separately.
"""
import argparse,collections,json,math
from pathlib import Path
from train_course_3y import iter_verified_rows

def wilson(k,n,z=1.96):
    if n==0:return [None,None]
    p=k/n;den=1+z*z/n
    mid=(p+z*z/(2*n))/den
    half=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/den
    return [round(mid-half,5),round(mid+half,5)]

def analyze(rows):
    by_race=[];key=None;acc=[]
    for r in rows:
        if key is not None and r['race_code']!=key:
            if len(acc)==6:by_race.append(acc)
            acc=[]
        key=r['race_code']
        acc.append(r)
    if len(acc)==6:by_race.append(acc)
    counters=collections.defaultdict(collections.Counter)
    date_buckets=collections.defaultdict(collections.Counter)
    checked=0
    for group in by_race:
        if {int(r['boat']) for r in group}!=set(range(1,7)):continue
        if {int(r['finish_place']) for r in group}!=set(range(1,7)):continue
        first=next(r for r in group if int(r['finish_place'])==1)
        second=next(r for r in group if int(r['finish_place'])==2)
        third=next(r for r in group if int(r['finish_place'])==3)
        venue=int(first['venue_code'])
        bucket='validation_test_2026_09_10' if first['date']>='2026-09-01' else 'historical_before_2026_09'
        keys=('all',f'venue_{venue:02d}')
        for k in keys:
            c=counters[k]
            c['races']+=1
            if int(first['boat'])==1:
                c['one_first']+=1
                c[f'second_boat_{second["boat"]}']+=1
                c[f'second_actual_course_{second["actual_course"]}']+=1
                if int(second['boat'])==5:
                    c['one_first_five_second']+=1
                    if int(third['boat'])==2:c['outcome_1_5_2']+=1
            if int(second['boat'])==5:c['boat5_second_any_first']+=1
        c=date_buckets[bucket]
        if int(first['boat'])==1:
            c['one_first']+=1
            if int(second['boat'])==5:c['five_second']+=1
        checked+=1
    report={'status':'DESCRIPTIVE_ANALYSIS','races_checked':checked,
        'input':'2023-11-01..2026-10-31 official K result labels',
        'warning':'Frequencies are retrospective labels, not pre-race forecasts or errors of the production AI.',
        'by_venue':{},'time_splits':{}}
    for venue,c in counters.items():
        n=c['one_first'];k=c['one_first_five_second']
        report['by_venue'][venue]={
            'total_clean_races':c['races'],'races_with_boat1_winner':n,
            'boat5_second_given_boat1_wins_count':k,
            'boat5_second_given_boat1_wins_rate':round(k/n,6) if n else None,
            'boat5_second_given_boat1_wins_95pct_wilson':wilson(k,n),
            'finish_1_5_2_count':c['outcome_1_5_2'],
            'second_boat_counts_given_boat1_wins':[c[f'second_boat_{b}'] for b in range(1,7)],
            'second_actual_course_counts_given_boat1_wins':[c[f'second_actual_course_{b}'] for b in range(1,7)],
            'boat5_second_any_first_count':c['boat5_second_any_first']}
    for key,c in date_buckets.items():
        report['time_splits'][key]={
            'one_first_races':c['one_first'],'boat5_second':c['five_second'],
            'boat5_second_conditional_rate':round(c['five_second']/c['one_first'],6) if c['one_first'] else None,
            '95pct_wilson':wilson(c['five_second'],c['one_first'])}
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--history',default='boat-ai/runtime/course_history_3y')
    p.add_argument('--out',default='boat-ai/runtime/course_training_3y/outer_second_place_audit.json')
    args=p.parse_args()
    report=analyze(iter_verified_rows(args.history))
    target=Path(args.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'races_checked':report['races_checked'],
        'all':report['by_venue']['all'],
        'tokuyama':report['by_venue']['venue_18'],
        'time_splits':report['time_splits']},ensure_ascii=False))
