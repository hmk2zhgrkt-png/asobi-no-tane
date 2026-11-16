#!/usr/bin/env python3
"""Paired prospective 28-feature/conditional Elo scorecard & exhibition F audit.

Separate genuine preclose inference from postclose research replay.
Never infer the result or payout from model inputs. User-entered results
supply the actual finish labels, but the recorded model must be scored
BEFORE the race cutoff (not merely an earlier screenshot).
"""
import argparse,csv,datetime as dt,json,math
from collections import defaultdict
from pathlib import Path

def load_results(path):
    with open(path,encoding='utf-8-sig',newline='') as handle:
        rows=list(csv.DictReader(handle))
    d={}
    for r in rows:
        key=(r['date'],int(r['venue_code']),int(r['race']))
        if key in d:raise ValueError('Duplicate result '+str(key))
        d[key]=r
    return d

def rank_metrics(all120,actual):
    if len(all120)!=120:raise ValueError('Not 120 probabilities')
    actual=str(actual)
    if actual not in all120:raise ValueError('Unknown result '+actual)
    probs={k:float(v) for k,v in all120.items()}
    if any(not math.isfinite(p) or p<0 for p in probs.values()) or abs(sum(probs.values())-1)>1e-6:
        raise ValueError('Invalid probability distribution')
    rank=1+next(i for i,(k,p) in enumerate(sorted(probs.items(),key=lambda q:-q[1])) if k==actual)
    p=probs[actual]
    brier=sum((val-(1.0 if k==actual else 0.0))**2 for k,val in probs.items())
    return {'rank':rank,'top1':rank==1,'top3':rank<=3,'top5':rank<=5,
            'assigned_probability':p,'logloss':-math.log(max(p,1e-15)),
            'multiclass_brier':brier}

def summarize(model_entries):
    return {k:{'n_races':len(vals),
              'top1_rate':sum(x['top1'] for x in vals)/len(vals),
              'top3_rate':sum(x['top3'] for x in vals)/len(vals),
              'top5_rate':sum(x['top5'] for x in vals)/len(vals),
              'mean_logloss':sum(x['logloss'] for x in vals)/len(vals),
              'mean_brier':sum(x['multiclass_brier'] for x in vals)/len(vals)}
            for k,vals in model_entries.items() if vals}

def audit(archive,results):
    archive=Path(archive);known=load_results(results)
    comparison=defaultdict(list)
    f_early=defaultdict(lambda:{'n':0,'winner':0,'top3':0})
    contexts={'archived_base_events':0,'archived_research_events':0,
              'completed_research_events':0,'retrospective_research_excluded':0,
              'base_events_scored_after_cutoff':0,'events_with_result':0,
              'meeting_day_missing':0,
              'multiple_versions_of_same_race_deduplicated':0}
    retrospective=[]
    base_selected={};research_selected={}
    for path in sorted(archive.rglob('*.json')):
        obj=json.loads(path.read_text(encoding='utf-8'))
        key=(obj['date'],int(obj['venue_code']),int(obj['race']))
        outcome=known.get(key)
        if path.name.startswith('research-'):
            contexts['archived_research_events']+=1
            if not outcome:continue
            contexts['completed_research_events']+=1
            if not obj['prospective_scored_before_cutoff']:
                contexts['retrospective_research_excluded']+=1
                retrospective.append({'race':key,'path':str(path)})
                continue
            scored=dt.datetime.fromisoformat(obj['scored_at_jst'])
            existing=research_selected.get(key)
            if existing is not None:
                contexts['multiple_versions_of_same_race_deduplicated']+=1
            if existing is None or scored>existing[0]:
                research_selected[key]=(scored,obj)
            continue
        contexts['archived_base_events']+=1
        if not outcome:continue
        contexts['events_with_result']+=1
        if not obj['prospective_model_generated_before_cutoff']:
            contexts['base_events_scored_after_cutoff']+=1
            continue
        scored=dt.datetime.fromisoformat(obj['model_scored_at_jst'])
        previous=base_selected.get(key)
        if previous is not None:
            contexts['multiple_versions_of_same_race_deduplicated']+=1
        if previous is None or scored>previous[0]:
            base_selected[key]=(scored,obj)
    # One latest genuinely scored preclose prediction per event, never duplicate
    # the same race just because a user sent multiple progress screenshots.
    for key,(_,obj) in base_selected.items():
        if not obj['source_report'].get('meeting_day'):
            contexts['meeting_day_missing']+=1
        outcome_boats=[int(x) for x in known[key]['actual_trifecta'].split('-')]
        for row in obj['features6']:
            boat=int(row['boat']);st=float(row['exhibition_st'])
            group='F01_to_F04' if -0.040000001<=st<0 else 'other'
            f_early[group]['n']+=1
            f_early[group]['winner']+=int(boat==outcome_boats[0])
            f_early[group]['top3']+=int(boat in outcome_boats)
    for key,(_,obj) in research_selected.items():
        for name,value in obj['models'].items():
            comparison[name].append(rank_metrics(value['all120'],known[key]['actual_trifecta']))
    for group in ('F01_to_F04','other'):
        f_early[group] # Explicitly include empty control group.
    sample=sum(x['n'] for x in f_early.values())
    sufficient=(f_early['F01_to_F04']['n']>=200 and f_early['other']['n']>=200)
    return {'status':'PAIRED_FORWARD_AUDIT',
      'rules':'Only one latest genuinely preclose model score per event; replays and postrace re-scores excluded.',
      'matched_prospective_research_scorecard':summarize(comparison),
      'prospective_research_race_count':len(research_selected),
      'prospective_base_race_count':len(base_selected),
      'source_checks':contexts,
      'postclose_research_replays_excluded':retrospective[:25],
      'F01_to_F04_exhibition_exploratory':{
        'n_boat_exposures':sample,'groups':dict(f_early),
        'sufficient_to_estimate_benefit':sufficient,
        'minimum_samples_per_group':200,
        'conclusion':('Counts recorded for prospective research; independent causal improvement not established'
                      if sufficient else 'Insufficient paired preclose exhibition F samples; DO NOT claim bonus improves forecasts'),
        'official_K_data_has_exhibition_ST':False,
        'rule_applied_as_unvalidated_user_requested_experiment':True},
      'missing_data_policy':'No fictitious meeting day, preclose exhibition, current race results or motor stats are filled.',
      'no_bets':True}

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--archive',default='boat-ai/runtime/preclose_archive')
    p.add_argument('--results',default='boat-ai/runtime/validation_results.csv')
    p.add_argument('--out',default='boat-ai/runtime/course_training_3y/prospective_f_and_model_audit.json')
    x=p.parse_args()
    report=audit(x.archive,x.results)
    out=Path(x.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
