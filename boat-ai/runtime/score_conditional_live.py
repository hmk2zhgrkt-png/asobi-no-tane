#!/usr/bin/env python3
"""Research-only 3-model race comparison including conditional positions.

No wager, no replacement of existing 28-feature model, and no postrace
realized course. All racing labels used to construct ratings are dated strictly
before the subject race. Report actual scoring time so postclose replays
are never presented as prospective predictions.
"""
import argparse,csv,datetime as dt,itertools,json
from pathlib import Path
import joblib,numpy as np
from train_course_3y import COMBOS,FEATURES
from own_elo import FEATURES as ELO_FEATURES
from course_model_sidecar import course_features
from score_own_elo_live import build_elo
from conditional_roles_3y import small_features,compare_proba,old_pl_proba,apply_tuning
from exhibition_f_bonus import adjust_combo_probs,details as f_details

JST=dt.timezone(dt.timedelta(hours=9))
def normalize(p):
    x=np.asarray(p,dtype=float)
    if len(x)!=120 or not np.isfinite(x).all() or np.any(x<0):raise ValueError('Invalid all120 probabilities')
    return x/x.sum()
def choices(p):
    codes=['-'.join(str(x+1) for x in combo) for combo in COMBOS]
    return [{'trifecta':codes[i],'probability':float(p[i])} for i in np.argsort(-p)[:5]]
def main(history,live,features,report_path,pred_file,model_file,out_path):
    report=json.loads(Path(report_path).read_text(encoding='utf-8'))
    date=report['date'];venue=int(report['venue_code']);race=int(report['race'])
    if not report['model_ran']:raise ValueError('Incumbent scoring failed')
    with open(features,encoding='utf-8-sig',newline='') as f:entries=list(csv.DictReader(f))
    with open(pred_file,encoding='utf-8-sig',newline='') as f:base=list(csv.DictReader(f))
    if len(entries)!=6 or any(e['date']!=date or int(e['race'])!=race or e['venue']!=report['venue'] for e in entries):
        raise ValueError('Race inputs changed')
    if sorted(int(e['boat']) for e in entries)!=list(range(1,7)):raise ValueError('Six entrant identifiers needed')
    ordered=sorted(entries,key=lambda e:int(e['boat']))
    model=joblib.load(model_file)
    if model.get('features')!=FEATURES+list(ELO_FEATURES) or not model.get('research_only'):
        raise ValueError('Wrong 3-year research model artifact')
    base_course=course_features(history,date,[dict(e,venue_code=venue) for e in ordered])
    elo,ratings,count,latest=build_elo(history,live,date,ordered)
    full=np.hstack([base_course,elo]).astype(np.float32)
    z=small_features(full).reshape(1,6,-1)
    reference,first=old_pl_proba(model['reference_models'],full)
    conditional=compare_proba(z,first,model['second'],model['third'])[0].astype(float)
    selected=apply_tuning(reference,conditional.reshape(1,120),model['selection'])[0]
    st=[float(e['exhibition_st']) for e in ordered]
    perms=[tuple(int(q+1) for q in triplet) for triplet in COMBOS]
    # Current incumbent already includes the user-requested F adjustment.
    incumbent_prob={row['trifecta']:float(row['probability']) for row in base}
    if len(incumbent_prob)!=120:raise ValueError('Incomplete incumbent predictions')
    incumbent=normalize([incumbent_prob['-'.join(map(str,p))] for p in perms])
    # The historical conditional model has no exhibition features; apply the
    # explicitly UNVALIDATED bonus consistently only as a research sensitivity.
    research_f=normalize(adjust_combo_probs(perms,selected,st))
    models={'incumbent_28feature':incumbent,'conditional_prior_course_plus_own_elo':research_f}
    for alpha in (.25,.5,.75):
        models[f'EXP_blend_28feature_{alpha:g}']=normalize((1-alpha)*incumbent+alpha*research_f)
    scored=dt.datetime.now(JST)
    cutoff=dt.datetime.fromisoformat(report['deadline_jst'])
    result={'status':'RESEARCH_ONLY_NO_AUTOMATIC_DEPLOYMENT',
       'date':date,'venue':report['venue'],'venue_code':venue,'race':race,
       'scored_at_jst':scored.isoformat(),
       'screenshot_observed_at_jst':report['preclose_snapshot_asof_jst'],
       'cutoff_jst':cutoff.isoformat(),
       'prospective_scored_before_cutoff':bool(scored<cutoff),
       'source_last_result_date':latest.isoformat() if latest else None,
       'official_history_races':count,
       'elo_built_independently_from_official_history':True,
       'no_current_day_finish_data_in_features':True,
       'experimental_f_rule':f_details(st),
       'validated_3y_holdout_is_not_28feature_head_to_head':True,
       'production_changed':False,
       'automatic_live_betting_allowed':False,
       'research_candidate':'Own Elo + conditional second/third + validation-selected blend and temperature',
       'models':{name:{'top5':choices(p),
                'all120':{'-'.join(map(str,perms[i])):float(p[i]) for i in range(120)},
                'sum_probability':float(p.sum())} for name,p in models.items()}}
    target=Path(out_path);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='models'},ensure_ascii=False))
    print('RESEARCH_TOP5',json.dumps({k:v['top5'] for k,v in result['models'].items()},ensure_ascii=False))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--history',default='boat-ai/runtime/course_history_3y')
    p.add_argument('--live',default='boat-ai/runtime/course_history_daily')
    p.add_argument('--features',default='boat-ai/runtime/latest_results/features6.csv')
    p.add_argument('--report',default='boat-ai/runtime/latest_results/report.json')
    p.add_argument('--predictions',default='boat-ai/runtime/latest_results/predictions120.csv')
    p.add_argument('--model',default='boat-ai/runtime/course_training_3y/conditional_roles_research_only.joblib')
    p.add_argument('--out',default='boat-ai/runtime/latest_results/conditional_elo_research.json')
    a=p.parse_args()
    main(a.history,a.live,a.features,a.report,a.predictions,a.model,a.out)
