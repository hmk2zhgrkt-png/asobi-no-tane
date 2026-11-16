#!/usr/bin/env python3
"""Score a preclose race with OWN Elo trained on 3y official K race results.

Never uses third-party Elo. Only date<target rows. Never silently replaces
incumbent AI, changes stored results, or places paper/real wagers.
"""
import argparse,csv,datetime as dt,itertools,json
from pathlib import Path
import joblib,numpy as np
from own_elo import Elo,FEATURES as ELO_FEATURES
from train_course_3y import FEATURES as COURSE_FEATURES,iter_verified_rows
from course_model_sidecar import course_features,PERMS
from live_course_history import iter_cache_rows

def build_elo(history_root,live_root,target_date,entries):
    target=dt.date.fromisoformat(str(target_date))
    ratings=Elo()
    sources=iter_verified_rows(history_root)
    additional=iter_cache_rows(live_root,target) if Path(live_root).is_dir() else ()
    from itertools import chain
    grouped=itertools.groupby(chain(sources,additional),key=lambda r:r['race_code'])
    race_count=0
    last=None
    for code,rows in grouped:
        one=list(rows)
        d=dt.date.fromisoformat(one[0]['date'])
        if d>=target:break
        if last and d<last:raise ValueError('Nonchronological history archive')
        last=d
        ratings.update_race(one)
        race_count+=1
    snapshot=[{'racer_id':int(e['racer_id'])} for e in sorted(entries,key=lambda e:int(e['boat']))]
    features=np.asarray(ratings.snapshot(snapshot),dtype=np.float32)
    return features,ratings,race_count,last

def main(args):
    report=json.loads(Path(args.report).read_text(encoding='utf-8'))
    if not report.get('model_ran'):raise ValueError('Incumbent race not model scored')
    with open(args.features,encoding='utf-8-sig',newline='') as f:
        entries=list(csv.DictReader(f))
    if len(entries)!=6 or any(str(e['date'])!=str(report['date']) or int(e['race'])!=int(report['race']) or str(e['venue'])!=str(report['venue']) for e in entries):
        raise ValueError('Wrong live race features')
    race=report['race'];date=report['date'];venue=int(report['venue_code'])
    if not all(int(e['boat'])==i for i,e in enumerate(entries,1)):
        raise ValueError('Entries are not boat-sorted')
    model=joblib.load(args.model)
    if (model.get('features')!=COURSE_FEATURES+list(ELO_FEATURES) or
        model.get('model_kind')!='own_elo_3yr_research' or
        model.get('train_end')!='2026-06-30' or
        model.get('no_production_deployment') is not True):
        raise ValueError('Own-Elo model provenance/schema incorrect')
    augmented=[dict(e,venue_code=venue) for e in entries]
    course=course_features(args.history,date,augmented)
    extra,ratings,n_races,last=build_elo(args.history,args.live,date,entries)
    X=np.hstack([course,extra])
    assert X.shape==(6,len(model['features']))
    predictions=np.stack([p.predict_proba(X)[:,1] for p in model['models']],axis=1)
    first=predictions[:,0];second=predictions[:,1];third=predictions[:,2]
    probs=[]
    for a,b,c in PERMS:
        i,j,k=a-1,b-1,c-1
        p=(first[i]/first.sum())*(second[j]/(second.sum()-second[i]))*(third[k]/(third.sum()-third[i]-third[j]))
        probs.append(p)
    probs=np.asarray(probs,dtype=float);probs/=probs.sum()
    top=np.argsort(-probs)[:5]
    result={
        'status':'RESEARCH_ONLY_PROSPECTIVE_COURSE_ELO',
        'date':date,'venue':report['venue'],'venue_code':venue,'race':race,
        'observed_at_jst':report['preclose_snapshot_asof_jst'],
        'cutoff_jst':report['deadline_jst'],
        'source':'independent own Elo from official BOAT RACE K histories',
        'historic_races_processed':n_races,
        'historic_last_date':last.isoformat() if last else None,
        'no_current_day_results_in_elo':True,
        'base_28feature_model_unchanged':True,
        'model_trained_through':'2026-06-30',
        'model_inputs':'boat/venue/prior-history + strict pre-day Elo; exhibition not used in this model',
        'top5':[{'trifecta':'-'.join(map(str,PERMS[int(i)])),'probability':float(probs[int(i)])} for i in top],
        'sum_probability':float(probs.sum()),
        'entrant_elo':[{'boat':int(e['boat']),'racer_id':int(e['racer_id']),
             'elo':round(ratings.ratings.get(int(e['racer_id']),1500),2),
             'races_observed':int(ratings.starts[int(e['racer_id'])])} for e in entries],
        'no_bets':True}
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--history',default='boat-ai/runtime/course_history_3y')
    p.add_argument('--live',default='boat-ai/runtime/course_history_daily')
    p.add_argument('--model',default='boat-ai/runtime/course_training_3y/own_elo_research_only.joblib')
    p.add_argument('--features',default='boat-ai/runtime/latest_results/features6.csv')
    p.add_argument('--report',default='boat-ai/runtime/latest_results/report.json')
    p.add_argument('--out',default='boat-ai/runtime/latest_results/own_elo_research.json')
    main(p.parse_args())
