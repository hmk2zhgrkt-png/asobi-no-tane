#!/usr/bin/env python3
"""Time split A/B: historical baseline vs baseline + motor form (top-one only)."""
import argparse,json
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score,log_loss
KEY=['date','venue','race','boat','racer_id','motor']
BASE=['racer_all_win_rate','racer_all_top3_rate','racer_venue_win_rate','racer_venue_top3_rate','racer_boat_win_rate','racer_boat_top3_rate','racer_30d_win_rate','racer_30d_top3_rate','motor_60d_win_rate','motor_60d_top3_rate','motor_prior_valid']
PRE=['exhibition_time_pre','exhibition_st','entry_course_pre','wind_speed_m_pre','wave_cm_pre','tilt_pre']
MOTOR=['cycle_prior_runs','cycle_prior_top2_mean','cycle_prior_exh_mean','last5_prior_runs','last5_prior_top2_mean','last5_prior_exh_mean','stint_prior_runs','stint_prior_top2_mean','stint_prior_exh_mean','last_stint_exh','stint_last_exh_change']

def run(a):
    motor=pd.read_csv(a.motor,encoding='utf-8-sig')
    base=pd.read_csv(a.baseline,encoding='utf-8-sig')
    pre=pd.read_csv(a.preclose,encoding='utf-8-sig',usecols=KEY+PRE)
    labels=pd.read_csv(a.labels,encoding='utf-8-sig',usecols=['date','venue','race','boat','finish_position'])
    x=motor.merge(base[KEY+BASE],on=KEY,how='left',validate='one_to_one').merge(pre,on=KEY,how='left',validate='one_to_one').merge(labels,on=['date','venue','race','boat'],how='left',validate='one_to_one')
    x=x[x.finish_position.isin(range(1,7))].copy()
    x=x[x.groupby(['date','venue','race']).boat.transform('size').eq(6)].copy()
    x['y']=(x.finish_position==1).astype(int)
    tr=x.date<'2026-09-01';va=(x.date>='2026-09-01')&(x.date<'2026-10-01');te=x.date>='2026-10-01'
    if not(tr.sum() and va.sum() and te.sum()):raise ValueError('Missing time window')
    out={};pred=x.loc[te,KEY+['y']].copy()
    for name,columns in [('baseline',BASE+PRE),('baseline_plus_motor',BASE+PRE+MOTOR)]:
        features=x[columns].apply(pd.to_numeric,errors='coerce').replace([np.inf,-np.inf],np.nan)
        model=HistGradientBoostingClassifier(max_iter=85,max_depth=5,learning_rate=0.07,l2_regularization=5,min_samples_leaf=85,random_state=42,early_stopping=False)
        model.fit(features.loc[tr],x.loc[tr,'y'])
        scores=model.predict_proba(features.loc[te])[:,1]
        pred[name+'_p']=scores
        tmp=pred.copy();tmp['p']=scores/tmp.assign(raw=scores).groupby(['date','venue','race']).raw.transform('sum')
        tmp=tmp[tmp.groupby(['date','venue','race']).y.transform('sum')==1]
        top=tmp.loc[tmp.groupby(['date','venue','race']).p.idxmax()]
        win=tmp[tmp.y==1]
        out[name]=dict(boat_auc=float(roc_auc_score(x.loc[te,'y'],scores)),
          boat_binary_logloss=float(log_loss(x.loc[te,'y'],scores,labels=[0,1])),
          race_top1_accuracy=float(top.y.mean()),
          race_winner_mean_negative_log_likelihood=float(-np.log(win.p.clip(1e-8)).mean()),
          evaluated_races=len(top),training_boats=int(tr.sum()),validation_boats=int(va.sum()),test_boats=int(te.sum()))
    Path(a.summary).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    pred.to_csv(a.predictions,index=False,encoding='utf-8-sig')
    print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for opt in ['motor','baseline','preclose','labels','summary','predictions']:p.add_argument('--'+opt,required=True)
    run(p.parse_args())
