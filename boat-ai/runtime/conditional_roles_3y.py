#!/usr/bin/env python3
"""Train truly conditional 2nd/3rd place models on official result archives.

All input columns are available BEFORE the race: frame, lagged racer/course
history and independent lagged Elo. Actual race results choose targets only.
The first-place model is the existing previously-trained Elo research model.
Stage 2 estimates P(second=j | first=i), stage 3 estimates
P(third=k | first=i, second=j); all 120 paths are explicitly normalized.
No training using realized entry course, start exhibition or same-day outcomes.

Training 2023-11..2026-06, model/hyperparameter selection Jul-Aug,
final heldout Sept-Oct untouched by this run. Absolutely no overwrite of
the current 28-feature real-time production model.
"""
import argparse,itertools,json
from pathlib import Path
import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from train_course_3y import (
    build_training_arrays,iter_verified_rows,TRAIN_END,VALID_END,TEST_END,COMBOS,FEATURES
)
from own_elo import FEATURES as ELO_FEATURES,elo_feature_rows

INDEXES=[30,31,32,38,40,42,46,48,50,52]  # prior-only historical outcomes
SMALL_NAMES=['boat_fraction','prior_30d_win','prior_30d_top2','prior_30d_top3',
             'prior_90d_win','prior_90d_top3','prior_90d_course_win',
             'prior_365d_win','prior_365d_top3','prior_365d_course_win',
             'prior_365d_course_top3','elo_center','elo_field_advantage','elo_log_starts']
# Venue*planned-course interactions: strictly pre-race one-hot features.
# This lets the *learned* conditional 2nd/3rd model represent different
# 1..6 course profiles across ALL 24 venues, not just a fixed 1-boat bonus.
SMALL_NAMES += [f'venue_{venue:02d}_course_{course}' for venue in range(1,25)
                for course in range(1,7)]

def small_features(X):
    # Course history array order verified at startup. Past actual course
    # history only. The current race's realized entry course never used.
    boat=np.argmax(X[:,:6],axis=1).astype(np.float32)/5.0
    venue_flag=X[:,6:30]
    course_flag=X[:,:6]
    if not np.all(np.isclose(venue_flag.sum(axis=1),1)) or not np.all(np.isclose(course_flag.sum(axis=1),1)):
        raise ValueError('Missing or ambiguous venue / planned course one-hot')
    venue_course=(venue_flag[:,:,None]*course_flag[:,None,:]).reshape(-1,24*6)
    z=np.column_stack([boat,X[:,INDEXES],X[:,-4],X[:,-3],X[:,-1],venue_course]).astype(np.float32)
    if z.shape[1]!=len(SMALL_NAMES):raise ValueError('Feature schema mismatch')
    return z

def two_features(w,c):
    """Candidate and relative strength conditioned on *given* first-place boat."""
    return np.column_stack([c,c[:,0]-w[:,0],c[:,4]-w[:,4],
                c[:,11]-w[:,11],c[:,12]-w[:,12],
                w[:,0],w[:,11]]).astype(np.float32)

def three_features(w,s,c):
    """Candidate and both selected opponents; actual labels used ONLY in training."""
    return np.column_stack([c,
                c[:,0]-w[:,0],c[:,0]-s[:,0],
                c[:,4]-w[:,4],c[:,4]-s[:,4],
                c[:,11]-w[:,11],c[:,11]-s[:,11],
                c[:,12]-w[:,12],c[:,12]-s[:,12],
                w[:,0],s[:,0],w[:,11],s[:,11]]).astype(np.float32)

def fit_models(z,position):
    # z: (number-of-training-races, six boats, feature count)
    n=len(z);y=position
    first=(y==1).argmax(axis=1)
    second=(y==2).argmax(axis=1)
    cand=np.broadcast_to(np.arange(6),(n,6))
    w=np.repeat(z[np.arange(n),first],6,axis=0)
    c=z.reshape(-1,z.shape[-1])
    mask=(cand!=first[:,None]).ravel()
    X2=two_features(w,c)[mask]
    y2=(y.reshape(-1)[mask]==2).astype(np.int8)
    w3=np.repeat(z[np.arange(n),first],6,axis=0)
    s3=np.repeat(z[np.arange(n),second],6,axis=0)
    mask3=((cand!=first[:,None])&(cand!=second[:,None])).ravel()
    X3=three_features(w3,s3,c)[mask3]
    y3=(y.reshape(-1)[mask3]==3).astype(np.int8)
    if y2.sum()!=n or y3.sum()!=n:
        raise ValueError('Conditional training positives must equal number of races')
    def fit(x,y):
        model=make_pipeline(StandardScaler(),LogisticRegression(
            solver='lbfgs',C=0.08,max_iter=160,tol=3e-4,random_state=42))
        model.fit(x,y)
        return model
    return fit(X2,y2),fit(X3,y3)

def compare_proba(z,first_model,second_model,third_model,batch=320):
    """Vectorized true conditional 120 probabilities, n x 120, batched."""
    n=len(z);dim=z.shape[-1];out=np.empty((n,120),dtype=np.float32)
    ai=COMBOS[:,0];bi=COMBOS[:,1];ci=COMBOS[:,2]
    for start in range(0,n,batch):
        z0=z[start:start+batch];m=len(z0)
        if m==0:continue
        # first model is original Elo model trained on full original features,
        # provided separately via first_scores caller.
        first=first_model[start:start+m]
        first=first/first.sum(axis=1,keepdims=True)
        w=np.broadcast_to(z0[:,:,None,:],(m,6,6,dim)).reshape(-1,dim)
        c=np.broadcast_to(z0[:,None,:,:],(m,6,6,dim)).reshape(-1,dim)
        pair=second_model.predict_proba(two_features(w,c))[:,1].reshape(m,6,6)
        ii=np.arange(6)
        pair[:,ii,ii]=0
        pair=pair/np.maximum(pair.sum(axis=2,keepdims=True),1e-12)
        w3=np.broadcast_to(z0[:,:,None,None,:],(m,6,6,6,dim)).reshape(-1,dim)
        s3=np.broadcast_to(z0[:,None,:,None,:],(m,6,6,6,dim)).reshape(-1,dim)
        c3=np.broadcast_to(z0[:,None,None,:,:],(m,6,6,6,dim)).reshape(-1,dim)
        third=third_model.predict_proba(three_features(w3,s3,c3))[:,1].reshape(m,6,6,6)
        third[:,ii,ii,:]=0
        third[:,:,ii,ii]=0
        third=third/np.maximum(third.sum(axis=3,keepdims=True),1e-12)
        p=first[:,ai]*pair[:,ai,bi]*third[:,ai,bi,ci]
        out[start:start+m]=p/np.maximum(p.sum(axis=1,keepdims=True),1e-12)
    return out

def old_pl_proba(models,x):
    n=len(x)//6
    scores=np.stack([m.predict_proba(x)[:,1] for m in models],axis=1).reshape(n,6,3)
    a,b,c=COMBOS[:,0],COMBOS[:,1],COMBOS[:,2]
    f=scores[:,:,0];ss=scores[:,:,1];tt=scores[:,:,2]
    f=f/f.sum(axis=1,keepdims=True)
    p=f[:,a]*(ss[:,b]/(ss.sum(axis=1,keepdims=True)-ss[:,a]))*(
        tt[:,c]/(tt.sum(axis=1,keepdims=True)-tt[:,a]-tt[:,b]))
    return p/p.sum(axis=1,keepdims=True),f

def results(probs,y):
    if len(probs)!=len(y) or probs.shape[1]!=120:raise ValueError('Wrong outcomes')
    actual=np.argsort(y,axis=1)[:,:3]
    codes={tuple(int(k) for k in co):i for i,co in enumerate(COMBOS)}
    correct=np.asarray([codes[tuple(a)] for a in actual])
    sorted_idx=np.argsort(-probs,axis=1)
    ranks=(sorted_idx==correct[:,None]).argmax(axis=1)+1
    actual_p=probs[np.arange(len(y)),correct]
    return {'races':int(len(y)),'top1':float(np.mean(ranks<=1)),
        'top3':float(np.mean(ranks<=3)),'top5':float(np.mean(ranks<=5)),
        'top10':float(np.mean(ranks<=10)),
        'logloss':float(np.mean(-np.log(np.maximum(actual_p,1e-14)))),
        'mean_actual_rank':float(ranks.mean()),
        'max_sum_error':float(np.max(np.abs(probs.sum(axis=1)-1)))}

def tune(base,conditional,labels):
    # All choices locked using July-August only. Target trifecta log loss,
    # not any future heldout outcome or a particular day's errors.
    candidates=[]
    for alpha in [0,.25,.5,.75,1]:
        blended=(1-alpha)*base+alpha*conditional
        for temperature in [.85,1.0,1.15,1.30]:
            calibrated=np.maximum(blended,1e-12)**(1/temperature)
            calibrated/=calibrated.sum(axis=1,keepdims=True)
            metrics=results(calibrated,labels)
            candidates.append((metrics['logloss'],alpha,temperature,metrics))
    best=min(candidates,key=lambda x:x[0])
    return {'selected_alpha':best[1],'selected_temperature':best[2],
            'validation_logloss':best[0],'validation_top5':best[3]['top5'],
            'selection_only_from_validation':True}

def apply_tuning(base,conditional,selection):
    p=(1-selection['selected_alpha'])*base+selection['selected_alpha']*conditional
    p=np.maximum(p,1e-12)**(1/selection['selected_temperature'])
    return p/p.sum(axis=1,keepdims=True)

def main(root,out,baseline):
    from time import perf_counter
    start=perf_counter()
    X,y,keys,boats,dates=build_training_arrays(root)
    if not np.array_equal(boats.reshape(-1,6),np.broadcast_to(np.arange(1,7),(len(y)//6,6))):
        raise ValueError('Historical features must be sorted by boat')
    history=np.asarray(list(elo_feature_rows(iter_verified_rows(root))),dtype=np.float32)
    if history.shape!=(len(y),len(ELO_FEATURES)):raise ValueError('Elo array disagreement')
    full=np.column_stack([X,history]).astype(np.float32)
    if len(FEATURES)+len(ELO_FEATURES)!=full.shape[1]:raise ValueError('Schema')
    small=small_features(full).reshape(-1,6,len(SMALL_NAMES))
    actual=y.reshape(-1,6);date=dates.reshape(-1,6)[:,0]
    tr=date<=TRAIN_END
    va=(date>TRAIN_END)&(date<=VALID_END)
    te=(date>VALID_END)&(date<=TEST_END)
    if not tr.sum() or not va.sum() or not te.sum():raise ValueError('Missing split')
    old=joblib.load(baseline)
    if old.get('model_kind')!='own_elo_3yr_research' or old.get('features')!=FEATURES+list(ELO_FEATURES):
        raise ValueError('Wrong Elo baseline')
    pair,third=fit_models(small[tr],actual[tr])
    estimates={}
    for name,mask in (('validation',va),('holdout',te)):
        original,first=old_pl_proba(old['models'],full.reshape(-1,6,full.shape[1])[mask].reshape(-1,full.shape[1]))
        candidate=compare_proba(small[mask],first,pair,third)
        estimates[name]={'original':original,'conditional':candidate,'actual':actual[mask]}
    v=estimates['validation'];t=estimates['holdout']
    selected=tune(v['original'],v['conditional'],v['actual'])
    report={'status':'RESEARCH_EVALUATED','method':'Observed-first conditional second + observed-first-and-second conditional third; unknown first/second are exhaustively enumerated at inference',
      'training_races':int(tr.sum()),'validation_races':int(va.sum()),'holdout_races':int(te.sum()),
      'training_end':TRAIN_END,'validation_end':VALID_END,
      'holdout_dates':['2026-09-01',TEST_END],
      'reference':'Previously trained own-Elo course-history first/second/third model',
      'features':SMALL_NAMES,
      'venue_course_interaction_features':144,
      'site_specific_wind_or_tide_directions_not_in_official_K':True,
      'uses_historic_exhibition':False,'same_day_outcome_features':False,
      'heldout_selection_leakage':False,'chosen_on_validation_only':selected,
      'validation':{'reference':results(v['original'],v['actual']),
           'conditional':results(v['conditional'],v['actual']),
           'selected_blend':results(apply_tuning(v['original'],v['conditional'],selected),v['actual'])},
      'final_holdout':{'reference':results(t['original'],t['actual']),
           'conditional':results(t['conditional'],t['actual']),
           'selected_blend':results(apply_tuning(t['original'],t['conditional'],selected),t['actual'])},
      'does_not_compare_incumbent_28_feature_model':True,
      'production_model_changed':False,'no_bets':True,'wall_seconds':round(perf_counter()-start,1)}
    e=report['final_holdout']
    report['recommendation']={
      'selected_blend_beats_reference_top5':e['selected_blend']['top5']>e['reference']['top5'],
      'selected_blend_beats_reference_logloss':e['selected_blend']['logloss']<e['reference']['logloss'],
      'production_deployment_allowed':False,
      'reason':'Full preclose original 28-feature LightGBM historic snapshots unavailable'}
    dest=Path(out);dest.mkdir(parents=True,exist_ok=True)
    (dest/'conditional_roles_evaluation.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    joblib.dump({'second':pair,'third':third,'first':old['models'][0],
       'features':FEATURES+list(ELO_FEATURES),'small_features':SMALL_NAMES,
       'selection':selected,'reference_models':old['models'],
       'training_end':TRAIN_END,'research_only':True},
       dest/'conditional_roles_research_only.joblib',compress=3)
    print(json.dumps({'duration':report['wall_seconds'],'holdout':report['final_holdout'],
       'selection':selected,'recommendation':report['recommendation']},ensure_ascii=False))
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--history',default='boat-ai/runtime/course_history_3y')
    p.add_argument('--out',default='boat-ai/runtime/course_training_3y')
    p.add_argument('--baseline',default='boat-ai/runtime/course_training_3y/own_elo_research_only.joblib')
    x=p.parse_args()
    main(x.history,x.out,x.baseline)
