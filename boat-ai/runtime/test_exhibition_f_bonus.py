#!/usr/bin/env python3
"""Exhibition F positive experiment contract tests (F.04 means -0.04 sec)."""
import itertools,math
from exhibition_f_bonus import eligible_boats,adjust_combo_probs,details
combos=list(itertools.permutations(range(1,7),3))
uniform=[1/120]*120
st=[-0.01,-0.02,-0.04,-0.041,0.01,-0.4]
assert eligible_boats(st)==[1,2,3],eligible_boats(st)
res=adjust_combo_probs(combos,uniform,st)
assert len(res)==120 and abs(sum(res)-1)<1e-12
scores=dict(zip(combos,res))
assert scores[(1,4,5)]>scores[(4,1,5)], 'Positive eligible first place bonus should outrank same eligible as second'
assert scores[(3,5,6)]>scores[(4,5,6)], 'F.04 positive; F.041 neutral'
assert scores[(4,5,6)]==scores[(5,4,6)]==scores[(6,5,4)], 'Ineligible F .041/.40 and normal ST are neutral'
unchanged=adjust_combo_probs(combos,uniform,[0,0,-0.041,.02,.05,.10])
assert max(unchanged)-min(unchanged)<1e-15
nonuniform=[i+1 for i in range(120)]
base=adjust_combo_probs(combos,nonuniform,[0]*6)
assert all(abs(a-b/sum(nonuniform))<1e-15 for a,b in zip(base,nonuniform))
assert details(st)['backtested'] is False and details(st)['no_bets']
try:adjust_combo_probs(combos[:-1],uniform[:-1],st)
except ValueError:pass
else:raise AssertionError('Incomplete 120 combinations not rejected')
print('PASS F.01–F.04 mild positive, no F.041/F.40 penalty, 120 normalized, baseline preserved, no betting')
