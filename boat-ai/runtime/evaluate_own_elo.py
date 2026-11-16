#!/usr/bin/env python3
"""Evaluate home-built Elo against the EXISTING 3-year pre-race history model.

Uses exactly identical 2023-11..2026-06 training, Jul-Aug validation, and
Sep-Oct untouched final holdout. Old comparison model is loaded unchanged
from earlier already trained archive. Only past-day race results influence Elo.
No real-time model replacement; this tests improvements beyond 3y course model,
NOT the current 28-feature LightGBM which requires preclose snapshots.
"""
import argparse,json,math
from pathlib import Path
import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from train_course_3y import (
    TRAIN_END,VALID_END,TEST_END,FEATURES,
    build_training_arrays,iter_verified_rows,assess
)
from own_elo import FEATURES as ELO_FEATURES,elo_feature_rows

def fit_elo(X,y,mask):
    models=[]
    for finishing_place in (1,2,3):
        target=(y[mask]==finishing_place).astype(np.int8)
        model=make_pipeline(StandardScaler(),
           LogisticRegression(solver='lbfgs',C=0.15,tol=2e-4,
                              max_iter=180,random_state=42))
        model.fit(X[mask],target)
        models.append(model)
    return models

def subset_by_first_boat(dates,y,boats,period_mask,boat1_won):
    if len(dates)%6 or np.any(boats.reshape(-1,6)!=np.arange(1,7)[None,:]):
        raise ValueError('Expected fixed 1-6 ordering within races')
    # one boolean per race, expanded to all six boats.
    outcome=(y.reshape(-1,6)[:,0]==1)
    race_period=period_mask.reshape(-1,6).all(axis=1)
    return np.repeat(race_period & (outcome==boat1_won),6)

def main(root,out,baseline_file):
    X,y,keys,boats,dates=build_training_arrays(root)
    if not np.all(np.sort(boats.reshape(-1,6),axis=1)==np.arange(1,7)[None,:]):
        raise ValueError('Invalid racer rows for Elo comparison')
    elo=np.asarray(list(elo_feature_rows(iter_verified_rows(root))),dtype=np.float32)
    if elo.shape!=(len(y),len(ELO_FEATURES)):
        raise ValueError(f'Elo rows do not match archived feature rows: {elo.shape}')
    expanded=np.concatenate([X,elo],axis=1)
    if not np.isfinite(expanded).all():
        raise ValueError('Non-finite Elo inputs')
    tr=(dates<=TRAIN_END)
    va=(dates>TRAIN_END)&(dates<=VALID_END)
    te=(dates>VALID_END)&(dates<=TEST_END)
    base=joblib.load(baseline_file)
    if base.get('features')!=FEATURES or base.get('train_end')!=TRAIN_END:
        raise ValueError('Saved baseline is not the June-2026 course model')
    baseline_models=base['models']
    candidate_models=fit_elo(expanded,y,tr)
    result={'status':'COMPLETED_RESEARCH',
      'provenance':'BOAT RACE official K result archives, independently computed Elo. No third-party Elo used.',
      'races_total':int(len(y)//6),
      'races_train':int(tr.sum()//6),
      'races_validation':int(va.sum()//6),
      'races_final_holdout':int(te.sum()//6),
      'train_last_date':TRAIN_END,
      'validation_dates':['2026-07-01',VALID_END],
      'final_holdout_dates':['2026-09-01',TEST_END],
      'elo_update_rule':'Each race compares 15 pairwise finish orders; K=24 distributed across 5 comparisons; whole-day updates after all pre-date features captured.',
      'strict_prior_day':True,
      'same_day_race_results_in_inputs':False,
      'first_race_initial_elo':1500,
      'elo_features':list(ELO_FEATURES),
      'baseline':'frame+venue+prior racer/course 3yr logistic, saved before Elo research',
      'candidate':'same history features PLUS independent Elo, same training dates and classifier hyperparameters',
      'models':{},
      'comparisons':{},
      'incumbent_28_feature_lightgbm_tested':False,
      'no_production_deployment':True,
      'no_bets':True}
    for tag,model,data in [('baseline_prior_course',baseline_models,X),('prior_course_plus_elo',candidate_models,expanded)]:
        result['models'][tag]={
          'validation':assess(model,data,y,keys,boats,va,True),
          'final_holdout':assess(model,data,y,keys,boats,te,True),
          'holdout_boat1_wins':assess(model,data,y,keys,boats,subset_by_first_boat(dates,y,boats,te,True),True),
          'holdout_boat1_loses':assess(model,data,y,keys,boats,subset_by_first_boat(dates,y,boats,te,False),True)}
    for period in ('validation','final_holdout','holdout_boat1_wins','holdout_boat1_loses'):
        a=result['models']['baseline_prior_course'][period]
        b=result['models']['prior_course_plus_elo'][period]
        result['comparisons'][period]={
          'races':a['races'],
          'top5_delta_percentage_points':100*(b['trifecta_top5_hit_rate']-a['trifecta_top5_hit_rate']),
          'top1_delta_percentage_points':100*(b['trifecta_top1_hit_rate']-a['trifecta_top1_hit_rate']),
          'trifecta_logloss_reduction':a['trifecta_log_loss']-b['trifecta_log_loss'],
          'winner_logloss_reduction':a['winner_log_loss']-b['winner_log_loss']}
    val=result['comparisons']['validation']
    test=result['comparisons']['final_holdout']
    result['conclusion']={
      'improved_top5_on_both_validation_and_test':val['top5_delta_percentage_points']>0 and test['top5_delta_percentage_points']>0,
      'reduced_trifecta_logloss_on_both':val['trifecta_logloss_reduction']>0 and test['trifecta_logloss_reduction']>0,
      'automatic_deployment':False,
      'production_decision':'Independent 28-feature baseline still needs fair same-race evaluation; do not swap or blend based on this alone.'}
    dest=Path(out);dest.mkdir(parents=True,exist_ok=True)
    (dest/'own_elo_evaluation.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    joblib.dump({'models':candidate_models,'features':FEATURES+list(ELO_FEATURES),
                'train_end':TRAIN_END,'no_production_deployment':True,
                'model_kind':'own_elo_3yr_research'},
                dest/'own_elo_research_only.joblib',compress=3)
    print(json.dumps({'races_train':result['races_train'],
                      'races_final_holdout':result['races_final_holdout'],
                      'comparisons':result['comparisons'],
                      'conclusion':result['conclusion']},ensure_ascii=False))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--root',default='boat-ai/runtime/course_history_3y')
    p.add_argument('--out',default='boat-ai/runtime/course_training_3y')
    p.add_argument('--baseline',default='boat-ai/runtime/course_training_3y/candidate_research_only.joblib')
    args=p.parse_args()
    main(args.root,args.out,args.baseline)
