#!/usr/bin/env python3
"""Safe sidecar: combine trained 3y course-history candidate and existing 28-feature inference.

Does NOT replace the incumbent model, alter its rankings, claim performance
improvement over incumbent or place bets. No live-race outcomes used to form
predictors. The K-file entry course is an observed *postrace* label and used
only for histories preceding the race's date. The new candidate was trained
with gate/boat proxy, so live exhibition entry course is NOT silently swapped
into its features; the verified exhibition course is recorded separately.
"""
import csv,datetime as dt,json,itertools,math
from collections import defaultdict
from pathlib import Path
import joblib
import numpy as np
from train_course_3y import FEATURES,iter_verified_rows,History

PERMS=list(itertools.permutations(range(1,7),3))
def course_features(root,date,entry_rows):
    date=dt.date.fromisoformat(str(date))
    if len(entry_rows)!=6 or set(int(e['boat']) for e in entry_rows)!=set(range(1,7)):
        raise ValueError('Expected six distinct numbered entrants')
    histories=defaultdict(History)
    courses=defaultdict(History)
    target_racers={int(e['racer_id']) for e in entry_rows}
    from itertools import chain
    from live_course_history import iter_cache_rows
    live_cache=Path(__file__).with_name('course_history_daily')
    additional=iter_cache_rows(live_cache,date) if live_cache.is_dir() else ()
    for row in chain(iter_verified_rows(root),additional):
        day=dt.date.fromisoformat(row['date'])
        if day>=date:break
        rid=int(row['racer_id'])
        if rid not in target_racers:continue
        ordinal=day.toordinal();place=int(row['finish_place'])
        hist=histories[rid];hist.append(ordinal,place)
        courses[(rid,int(row['actual_course']))].append(ordinal,place)
    x=[]
    for e in sorted(entry_rows,key=lambda r:int(r['boat'])):
        boat=int(e['boat']);venue=int(e['venue_code']);racer=int(e['racer_id'])
        if not 1<=venue<=24:raise ValueError('Invalid venue')
        row=[float(k==boat) for k in range(1,7)]+[float(k==venue) for k in range(1,25)]
        for window in (30,90,365,1096):
            for hist in (histories.get(racer),courses.get((racer,boat))):
                n,w,t2,t3=hist.stats(date.toordinal(),window) if hist else (0,0,0,0)
                row.extend(((w+1)/(n+6),(t2+2)/(n+6),(t3+3)/(n+6),math.log1p(n)))
        x.append(row)
    if len(x[0])!=len(FEATURES):raise ValueError('Trained feature schema mismatch')
    return np.asarray(x,dtype=np.float32)

def candidate_120(models,x):
    if len(models)!=3 or x.shape!=(6,len(FEATURES)):raise ValueError('Wrong candidate features')
    scores=np.stack([m.predict_proba(x)[:,1] for m in models],axis=1)
    if not np.isfinite(scores).all() or (scores<=0).any():raise ValueError('Unstable scores')
    out=[]
    for a,b,c in PERMS:
        a-=1;b-=1;c-=1
        w=scores[a,0]/scores[:,0].sum()
        second=scores[b,1]/(scores[:,1].sum()-scores[a,1])
        third=scores[c,2]/(scores[:,2].sum()-scores[a,2]-scores[b,2])
        out.append(w*second*third)
    z=np.asarray(out,dtype=float)
    z/=z.sum()
    if not np.isfinite(z).all() or abs(z.sum()-1)>1e-9:raise ValueError('Bad normalization')
    return z

def compare_rows(base_rows,entry_rows,model_file,history_root,date,venue,race):
    lookup={r['trifecta']:float(r['probability']) for r in base_rows}
    if set(lookup)!={'-'.join(map(str,p)) for p in PERMS} or len(base_rows)!=120:
        raise ValueError('Existing 120-way prediction missing/duplicate')
    if not all(math.isfinite(v) and v>=0 for v in lookup.values()):
        raise ValueError('Invalid existing probabilities')
    if len(entry_rows)!=6 or any(str(e['date'])!=str(date) or int(e['venue_code'])!=int(venue) or int(e['race'])!=int(race) for e in entry_rows):
        raise ValueError('Historical competitor records do not match the race')
    loaded=joblib.load(model_file)
    if (list(loaded['features'])!=FEATURES or loaded.get('train_end')!='2026-06-30' or
        not loaded.get('no_production_deployment',False)):
        raise ValueError('Candidate artifact not verified as independent research model')
    x=course_features(history_root,date,entry_rows)
    new=candidate_120(loaded['models'],x)
    combo=['-'.join(map(str,p)) for p in PERMS]
    old=np.array([lookup[c] for c in combo],dtype=float);old/=old.sum()
    # Apply user-directed exhibition F.01..F.04 experiment to research candidate;
    # incumbent probabilities were already adjusted by auto_predict.
    from exhibition_f_bonus import adjust_combo_probs,details as exhibition_f_details
    st_values=[float(e['exhibition_st']) for e in sorted(entry_rows,key=lambda e:int(e['boat']))]
    new=np.asarray(adjust_combo_probs(PERMS,new,st_values),dtype=float)
    weights={'incumbent':old,'course_model_research_only':new}
    for alpha in (0.25,0.5,0.75):
        weights[f'experimental_blend_{alpha:g}']=old*(1-alpha)+new*alpha
    out=[]
    for label,p in weights.items():
        ranks=np.argsort(-p)
        out.append({'name':label,'top5':[{'trifecta':combo[i],'score':round(float(p[i]),10)} for i in ranks[:5]],
            'sum_probability':float(p.sum()),'historical_backtest_with_incumbent':False})
    return {'date':str(date),'venue_code':int(venue),'race':int(race),
       'status':'RESEARCH_ONLY_NOT_VALIDATED_AGAINST_INCUMBENT',
       'three_year_source_end':'2026-10-31','existing_28_feature_model_unchanged':True,
       'candidate_training_end':'2026-06-30',
       'model_input_note':'Trained with starting boat/frame proxy; NOT same-race realized course or pre-race exhibition course',
       'source_data_lag_note':'Source: immutable K through 2026-10-31 + checksum-verified completed K cache if present; absent days remain unavailable',
       'exhibition_f_positive_experiment':exhibition_f_details(st_values),
       'alternatives':out,
       'no_paper_or_real_bets':True}

def run(history_root,model_file,features_file,predictions_file,report_file,out_path):
    with open(features_file,encoding='utf-8-sig',newline='') as f:
        entries=list(csv.DictReader(f))
    with open(predictions_file,encoding='utf-8-sig',newline='') as f:
        base=list(csv.DictReader(f))
    report=json.loads(Path(report_file).read_text(encoding='utf-8'))
    if not report.get('model_ran',False):
        raise ValueError('Incumbent model did not score this race')
    if not (str(entries[0]['date'])==str(report['date']) and
            str(entries[0]['race'])==str(report['race']) and
            str(entries[0]['venue'])==str(report['venue'])):
        raise ValueError('Incumbent report and archived features are not the same race')
    enriched=[dict(e,venue_code=int(report['venue_code'])) for e in entries]
    result=compare_rows(base,enriched,model_file,history_root,
                        report['date'],report['venue_code'],report['race'])
    target=Path(out_path);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return result

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('--history-root',default='boat-ai/runtime/course_history_3y')
    p.add_argument('--candidate-model',default='boat-ai/runtime/course_training_3y/candidate_research_only.joblib')
    p.add_argument('--features',default='boat-ai/runtime/latest_results/features6.csv')
    p.add_argument('--predictions',default='boat-ai/runtime/latest_results/predictions120.csv')
    p.add_argument('--report',default='boat-ai/runtime/latest_results/report.json')
    p.add_argument('--out',default='boat-ai/runtime/course_training_3y/incumbent_sidecar_comparison.json')
    a=p.parse_args()
    report=run(a.history_root,a.candidate_model,a.features,a.predictions,a.report,a.out)
    print(json.dumps(report,ensure_ascii=False))
