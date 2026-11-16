#!/usr/bin/env python3
"""Re-score integrity tests. Does not require sklearn, model artifacts or web."""
import copy,itertools,math,json
from pathlib import Path
from course_adjust import validate_context,factors,rescore,report
ctx=json.loads(Path(__file__).with_name('course_context.json').read_text())
rows=[{'trifecta':'-'.join(map(str,p)),'probability':1/120,'observed_odds':''} for p in itertools.permutations(range(1,7),3)]
results=rescore(rows,ctx,'2026-11-16',13,2)
assert len(results)==120 and len({r['trifecta'] for r in results})==120
assert abs(sum(r['probability'] for r in results)-1)<1e-10
assert all(math.isfinite(r['probability']) and r['probability']>0 for r in results)
assert rescore(rows,ctx,'2026-11-16',13,3) is None
assert report(results)['model_retrained'] is False
assert len(report(results)['course_adjusted_top5'])==5
assert len(factors(validate_context(ctx,'2026-11-16',13,2)))==6
bad=copy.deepcopy(ctx);bad['entries'][3]['entry_course']=5
try:validate_context(bad,'2026-11-16',13,2)
except ValueError:pass
else:raise AssertionError('Duplicate course must fail')
bad=copy.deepcopy(ctx);bad['entries'][2]['racer_id']=9999
try:validate_context(bad,'2026-11-16',13,2,entries=[{'boat':3,'racer_id':4117,'entry_course':3}])
except ValueError:pass
else:raise AssertionError('Wrong racer identity must fail')
bad=copy.deepcopy(ctx);bad['entries'][0]['top2_pct']=25
try:validate_context(bad,'2026-11-16',13,2)
except ValueError:pass
else:raise AssertionError('Monotonic place rates required')
print("PASS: course-specific 1st/2nd/3rd adjustment, 120 normalized, race/racer/course validation")
