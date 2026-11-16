#!/usr/bin/env python3
"""Preclose audit fixtures with protected retrospective exclusion."""
import csv,datetime as dt,json,tempfile
from pathlib import Path
from itertools import permutations
from audit_forward_models import rank_metrics,audit
from archive_preclose import save as archive_base
from archive_research import save as archive_alt
combos=['-'.join(map(str,x)) for x in permutations(range(1,7),3)]
pr={k:1/120 for k in combos}
assert rank_metrics(pr,'1-2-3')['top5'] in (True,False)
with tempfile.TemporaryDirectory() as tmp:
    d=Path(tmp);root=d/'latest';root.mkdir();out=d/'archive'
    (root/'report.json').write_text(json.dumps({
        'date':'2026-11-16','venue':'丸亀','venue_code':15,'race':11,'model_ran':True,
        'preclose_snapshot_asof_jst':'2026-11-16T20:06:00+09:00',
        'deadline_jst':'2026-11-16T20:14:00+09:00','meeting_day':None
    }))
    with (root/'features6.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,['date','venue','race','boat','exhibition_st'])
        w.writeheader()
        for b in range(1,7):
            w.writerow(dict(date='2026-11-16',venue='丸亀',race=11,boat=b,
                            exhibition_st=-.02 if b==1 else .05))
    with (root/'predictions120.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,['trifecta','probability'])
        w.writeheader()
        for k,v in pr.items():w.writerow(dict(trifecta=k,probability=v))
    prospective=dt.datetime(2026,11,16,20,10,tzinfo=dt.timezone(dt.timedelta(hours=9)))
    base=archive_base(root,out,scored_at=prospective)
    assert base['prospective_model_generated_before_cutoff']
    second_preclose=archive_base(root,out,scored_at=prospective+dt.timedelta(minutes=1))
    assert second_preclose['prospective_model_generated_before_cutoff']
    post=archive_base(root,out,scored_at=prospective+dt.timedelta(minutes=8))
    assert not post['prospective_model_generated_before_cutoff']
    research={
        'date':'2026-11-16','venue':'丸亀','venue_code':15,'race':11,
        'scored_at_jst':prospective.isoformat(),'cutoff_jst':'2026-11-16T20:14:00+09:00',
        'prospective_scored_before_cutoff':True,
        'models':{k:{'all120':pr,'top5':[]} for k in [
            'incumbent_28feature','conditional_prior_course_plus_own_elo',
            'EXP_blend_28feature_0.25','EXP_blend_28feature_0.5','EXP_blend_28feature_0.75']}}
    model=d/'research.json';model.write_text(json.dumps(research))
    archive_alt(model,out)
    model.write_text(json.dumps(dict(research,scored_at_jst=(prospective+dt.timedelta(minutes=1)).isoformat(),
                                    prospective_scored_before_cutoff=True)))
    archive_alt(model,out)
    model.write_text(json.dumps(dict(research,scored_at_jst=(prospective+dt.timedelta(minutes=8)).isoformat(),
                                    prospective_scored_before_cutoff=False)))
    archive_alt(model,out)
    with (d/'results.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,['date','venue_code','race','actual_trifecta'])
        w.writeheader();w.writerow(dict(date='2026-11-16',venue_code=15,race=11,actual_trifecta='1-2-3'))
    j=audit(out,d/'results.csv')
    assert j['prospective_research_race_count']==1
    assert j['prospective_base_race_count']==1
    assert j['source_checks']['multiple_versions_of_same_race_deduplicated']==2
    assert j['source_checks']['retrospective_research_excluded']==1
    assert j['source_checks']['base_events_scored_after_cutoff']==1
    assert j['F01_to_F04_exhibition_exploratory']['sufficient_to_estimate_benefit'] is False
    assert len(j['matched_prospective_research_scorecard'])==5
    print('PASS: 120-way archive, real inferred cutoff, no postclose inclusion, conditional vs incumbent matched, F sample-size guard')
