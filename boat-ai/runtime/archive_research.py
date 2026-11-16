#!/usr/bin/env python3
"""Immutable research-model snapshots with independent inference timestamp."""
import argparse,datetime as dt,hashlib,json
from pathlib import Path
JST=dt.timezone(dt.timedelta(hours=9))
def save(model_json,archive):
    o=json.loads(Path(model_json).read_text(encoding='utf-8'))
    date=str(o['date']);venue=int(o['venue_code']);race=int(o['race'])
    stamp=dt.datetime.fromisoformat(o['scored_at_jst'])
    cutoff=dt.datetime.fromisoformat(o['cutoff_jst'])
    if not stamp.tzinfo or not cutoff.tzinfo:raise ValueError('Offset-aware clock required')
    if o['prospective_scored_before_cutoff']!=(stamp<cutoff):
        raise ValueError('Inconsistent prospective status')
    if set(o['models'])!={'incumbent_28feature','conditional_prior_course_plus_own_elo',
         'EXP_blend_28feature_0.25','EXP_blend_28feature_0.5','EXP_blend_28feature_0.75'}:
        raise ValueError('Unexpected model selection')
    for name,v in o['models'].items():
        if len(v['all120'])!=120 or abs(sum(v['all120'].values())-1)>1e-7:
            raise ValueError('Incomplete model '+name)
    packed=json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':'))
    digest=hashlib.sha256(packed.encode()).hexdigest()[:14]
    folder=Path(archive)/f"{date.replace('-','')}-{venue:02d}-{race:02d}"
    folder.mkdir(parents=True,exist_ok=True)
    f=folder/f"research-{stamp.astimezone(JST).strftime('%H%M%S')}-{digest}.json"
    if f.exists() and f.read_text(encoding='utf-8')!=packed+'\n':
        raise ValueError('Archive collision')
    f.write_text(packed+'\n',encoding='utf-8')
    print(json.dumps({'saved':str(f),'prospective':o['prospective_scored_before_cutoff'],
        'models':list(o['models'])},ensure_ascii=False))
    return f
if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--model-json',default='boat-ai/runtime/latest_results/conditional_elo_research.json')
    p.add_argument('--archive',default='boat-ai/runtime/preclose_archive')
    a=p.parse_args()
    save(a.model_json,a.archive)
