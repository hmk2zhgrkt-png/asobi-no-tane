#!/usr/bin/env python3
"""Create immutable, auditable before/after-close inference snapshots.

Model inference time and input observation time are independently recorded.
A preclose screenshot DOES NOT make a model scored after cutoff prospective.
Store 120-way arrays and all source/missing-field indicators for later fair
paired incumbent-vs-Elo-vs-course evaluation; no odds or wagers invented.
"""
import argparse,csv,datetime as dt,hashlib,json,math
from pathlib import Path

JST=dt.timezone(dt.timedelta(hours=9))
def rows(path):
    with open(path,encoding='utf-8-sig',newline='') as handle:
        return list(csv.DictReader(handle))
def save(root,dest,scored_at=None):
    root=Path(root);report=json.loads((root/'report.json').read_text(encoding='utf-8'))
    if not report.get('model_ran',False):
        raise ValueError('Cannot record a failed model')
    features=rows(root/'features6.csv')
    predictions=rows(root/'predictions120.csv')
    if len(features)!=6 or len(predictions)!=120:raise ValueError('Missing 6 entrants or 120 predictions')
    date=report['date'];venue=int(report['venue_code']);race=int(report['race'])
    if any(x['date']!=date or int(x['race'])!=race or x['venue']!=report['venue'] for x in features):
        raise ValueError('Mismatched feature identities')
    probs={p['trifecta']:float(p['probability']) for p in predictions}
    from itertools import permutations
    if set(probs)!={'-'.join(map(str,p)) for p in permutations(range(1,7),3)}:
        raise ValueError('Incomplete/duplicated 120-way probabilities')
    if not all(math.isfinite(p) and 0<=p<=1 for p in probs.values()) or abs(sum(probs.values())-1)>1e-6:
        raise ValueError('Non-normalized 120-way data')
    stamp=scored_at or dt.datetime.now(JST)
    obs=dt.datetime.fromisoformat(report['preclose_snapshot_asof_jst'])
    cutoff=dt.datetime.fromisoformat(report['deadline_jst'])
    if obs.tzinfo is None or cutoff.tzinfo is None or obs>cutoff:
        raise ValueError('Misidentified purported preclose screenshot')
    if stamp.tzinfo is None:raise ValueError('Scoring clock must include timezone')
    signed={'status':'ARCHIVED_SOURCE_VALIDATED','date':date,'venue':report['venue'],
            'venue_code':venue,'race':race,
            'snapshot_at_jst':obs.isoformat(),
            'model_scored_at_jst':stamp.astimezone(JST).isoformat(),
            'cutoff_jst':cutoff.isoformat(),
            'prospective_model_generated_before_cutoff':stamp<cutoff,
            'source_result_race_known_before_predict':False, # not inferable from file alone
            'source':'real screenshot + official racecard + verified motor cycle and prior K',
            'model':'incumbent_28_feature_lightgbm',
            'features6':features,
            'all120':probs,
            'baseline_without_F_adjustment':{
                p['trifecta']:float(p.get('pre_exhibition_f_bonus_probability') or p['probability'])
                for p in predictions},
            'source_report':report,
            'result_known_to_model':False,
            'real_bets':False}
    for model_file,key in [('course_model_research.json','course_model'),('own_elo_research.json','own_elo')]:
        path=root/model_file
        if path.exists():
            obj=json.loads(path.read_text(encoding='utf-8'))
            if (obj.get('date')==date and int(obj.get('venue_code',-1))==venue and int(obj.get('race',-1))==race):
                # TOP5 only; cannot backtest full 120 ranks on this output.
                signed[key]={'top5':(next((x['top5'] for x in obj['alternatives']
                            if x['name']=='course_model_research_only'),[]) if key=='course_model'
                            else obj.get('top5',[])),
                    'full120_available':False}
    packed=json.dumps(signed,ensure_ascii=False,sort_keys=True,separators=(',',':'))
    digest=hashlib.sha256(packed.encode()).hexdigest()[:14]
    suffix=f"{date.replace('-','')}-{venue:02d}-{race:02d}"
    folder=Path(dest)/suffix
    folder.mkdir(parents=True,exist_ok=True)
    filename=f"{obs.strftime('%H%M%S')}-{digest}.json"
    path=folder/filename
    if path.exists() and path.read_text(encoding='utf-8')!=packed+'\n':
        raise ValueError('Immutable snapshot digest collision')
    path.write_text(packed+'\n',encoding='utf-8')
    print(json.dumps({'saved':str(path),'prospective':signed['prospective_model_generated_before_cutoff'],
        'source_asof':obs.isoformat(),'scored_at':stamp.isoformat(),
        'race':[date,venue,race],'models':list(k for k in ('course_model','own_elo') if k in signed)},
        ensure_ascii=False))
    return signed

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--result-dir',default='boat-ai/runtime/latest_results')
    p.add_argument('--archive',default='boat-ai/runtime/preclose_archive')
    a=p.parse_args()
    save(a.result_dir,a.archive)
