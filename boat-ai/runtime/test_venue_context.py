#!/usr/bin/env python3
"""Regression for Kyoutei Navi venue course priors."""
import itertools, math
from venue_context import VENUES, adjust_120, context

assert len(VENUES)==24
perm=list(itertools.permutations(range(1,7),3))
assert len(perm)==120
base=[1/120]*120
entry={i:i for i in range(1,7)}
for venue in VENUES:
    meta=context(venue)
    assert len(meta["course_win_rates_pct"])==6
    assert 98 < sum(meta["course_win_rates_pct"]) < 102
    adjusted=adjust_120(venue,entry,perm,base)
    assert len(adjusted)==120
    assert abs(sum(adjusted)-1.0)<1e-12
    assert all(math.isfinite(x) and x>0 for x in adjusted)
assert sum(adjust_120('徳山',entry,perm,base)[i] for i,x in enumerate(perm) if x[0]==1) > sum(adjust_120('戸田',entry,perm,base)[i] for i,x in enumerate(perm) if x[0]==1)
try:
    adjust_120('児島',{1:1,2:2},perm,base)
except ValueError: pass
else: raise AssertionError('Missing course must fail closed')
print('PASS: 24 venues, 120 normalized probabilities, distinct courses, expected venue effect')
