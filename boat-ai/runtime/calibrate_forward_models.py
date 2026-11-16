#!/usr/bin/env python3
"""Honest calibration and user-requested F-bonus ablation on future snapshots.

Only use predictions actually scored before race cutoff and observed results
uploaded afterward. A preclose screenshot reprocessed after race is excluded.
A minimum of 300 chronological calibration events + 100 untouched future
events is mandatory. Until then report NOT_READY, never fit on today's races,
never modify the incumbent or authorize real or paper wagers.
"""
import argparse,datetime as dt,json,math
from pathlib import Path
import numpy as np
from audit_forward_models import load_results,rank_metrics

TEMPERATURES=(.75,.85,1.0,1.15,1.30,1.50,1.75)

def archive_events(archive,results):
    labels=load_results(results)
    latest={}
    for f in Path(archive).rglob('*.json'):
        if f.name.startswith('research-'):continue
        r=json.loads(f.read_text(encoding='utf-8'))
        key=(r['date'],int(r['venue_code']),int(r['race']))
        if key not in labels or not r.get('prospective_model_generated_before_cutoff'):
            continue
        scored=dt.datetime.fromisoformat(r['model_scored_at_jst'])
        cutoff=dt.datetime.fromisoformat(r['cutoff_jst'])
        if scored>=cutoff:continue
        previous=latest.get(key)
        if previous is None or scored>previous[0]:
            latest[key]=(scored,r)
    for key,(_,r) in sorted(latest.items()):
        yield key,r,labels[key]['actual_trifecta']

def temperature_adjust(prob,temperature):
    p=np.asarray(prob,dtype=float)
    if p.shape!=(120,) or not np.isfinite(p).all() or (p<0).any():
        raise ValueError('Invalid probability shape')
    x=np.maximum(p,1e-12)**(1/temperature)
    return x/x.sum()

def metrics(records,name,temp=1):
    if not records:return None
    values=[]
    for _,record,truth in records:
        scores=record[name]
        adjusted=temperature_adjust([scores[k] for k in sorted(scores)],temp)
        values.append(rank_metrics(dict(zip(sorted(scores),adjusted)),truth))
    return {'n':len(values),
      'top5':sum(x['top5'] for x in values)/len(values),
      'logloss':sum(x['logloss'] for x in values)/len(values),
      'multiclass_brier':sum(x['multiclass_brier'] for x in values)/len(values)}

def audit(archive,results):
    recs=list(archive_events(archive,results))
    n=len(recs)
    info={'status':'WAITING_FOR_ENOUGH_PROSPECTIVE_SAMPLES',
          'prospective_completed_races':n,
          'need_training_races':300,
          'need_independent_future_test_races':100,
          'third_party_exhibition_archives_used':False,
          'production_temperature_updated':False,
          'user_requested_F_bonus_backtested':False,
          'real_bets':False,
          'reference':'Existing 28-feature predictions plus original pre-F adjustment, both archived at true inference time'}
    if n<400:
        info['remaining_races_to_first_full_evaluation']=400-n
        info['reason']='Do not choose calibration or F adjustment strength from a few results'
        return info
    train=recs[:int(n*.75)]
    test=recs[int(n*.75):]
    if len(train)<300 or len(test)<100:
        info['reason']='Insufficient chronological train/test after split'
        return info
    candidates=[(metrics(train,'all120',t)['logloss'],t) for t in TEMPERATURES]
    _,temp=min(candidates)
    raw=metrics(test,'all120')
    calibrated=metrics(test,'all120',temp)
    base=metrics(test,'baseline_without_F_adjustment')
    f_races=[r for r in test if any(-.040000001<=float(x['exhibition_st'])<0 for x in r[1]['features6'])]
    f_exposure=sum(1 for _,r,_ in test for x in r['features6'] if -.040000001<=float(x['exhibition_st'])<0)
    info.update({'status':'RESEARCH_ONLY_EVALUATED',
       'train_races':len(train),'later_holdout_races':len(test),
       'validation_selected_temperature':temp,
       'test_existing':raw,'test_temperature_adjusted':calibrated,
       'test_without_F_bonus':base,
       'test_with_F_bonus':raw,
       'test_subset_with_eligible_F_races':len(f_races),
       'test_F_positive_boat_exposures':f_exposure,
       'F_bonus_has_sufficient_exposure':f_exposure>=200,
       'user_requested_F_bonus_backtested':True,
       'historical_3year_K_has_exhibition_start':False,
       'should_deploy_calibration':calibrated['logloss']<raw['logloss'] and calibrated['top5']>=raw['top5'],
       'automatic_deployment':False,
       'notes':'Prospective temporal evaluation only; F effect can remain confounded. Changes require additional robustness verification.'})
    return info

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--archive',default='boat-ai/runtime/preclose_archive')
    p.add_argument('--results',default='boat-ai/runtime/validation_results.csv')
    p.add_argument('--out',default='boat-ai/runtime/course_training_3y/prospective_28_calibration.json')
    args=p.parse_args()
    out=audit(args.archive,args.results)
    dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False))
