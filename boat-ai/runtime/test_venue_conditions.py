#!/usr/bin/env python3
"""24 racecourse wind and tide rules: verified input, no fabricated forecasts."""
import math
from itertools import permutations
from venue_conditions import (VENUES,COURSE_HEADING,OVERVIEW_NOTES,ALIASES,
      DEGREES,prepare_conditions,classify_wind,adjust_research)
from venue_context import context
assert len(VENUES)==len(COURSE_HEADING)==len(OVERVIEW_NOTES)==24
for venue,heading in COURSE_HEADING.items():
    assert classify_wind(venue,wind_from=heading)=='向かい風'
    opposite=next(k for k,v in DEGREES.items()
                  if (v-DEGREES[heading])%360==180)
    assert classify_wind(venue,wind_from=opposite)=='追い風'
    assert classify_wind(venue,relative="tailwind")=="追い風"
    c=prepare_conditions(venue,wind_speed_m=4,wind_from=heading)
    assert c['venue_profile']['source']==context(venue)['source']
    assert c['wind_observed'] and c['relative_wind']=='向かい風'
    assert prepare_conditions(venue,wind_speed_m=4)['relative_wind'] is None
    assert prepare_conditions(venue,tide_height_cm=150)['tide_phase'] is None
    assert 'venue_profile' in c
combos=list(permutations(range(1,7),3))
course={i:i for i in range(1,7)}
before=[1/120]*120
none=prepare_conditions('宮島',wind_speed_m=3)
after,info=adjust_research('宮島',course,combos,before,none)
assert max(abs(a-b) for a,b in zip(before,after))<1e-12
assert not info['wind_effect_applied'] and not info['tide_effect_applied']
wind=prepare_conditions('宮島',wind_speed_m=4,wind_from='NE',
    tide_phase='干潮',tide_height_cm=120)
assert wind['relative_wind']=='追い風'
after,info=adjust_research('宮島',course,combos,before,wind)
assert math.isclose(sum(after),1,abs_tol=1e-10)
assert info['wind_effect_applied'] and info['tide_effect_applied']
assert after[0]!=before[0]
for venue in VENUES:
    condition=prepare_conditions(venue,wind_speed_m=4,wind_from=COURSE_HEADING[venue])
    new,meta=adjust_research(venue,course,combos,before,condition)
    assert len(new)==120 and math.isclose(sum(new),1,abs_tol=1e-10)
for bad in ('UP','left','↗','北北東'):
    try:prepare_conditions('宮島',wind_speed_m=4,wind_from=bad)
    except ValueError:pass
    else:raise AssertionError('Invalid compass should fail closed: '+bad)
for kwargs in ({'tide_phase':'unknown'},{'wind_speed_m':float('nan')},
               {'wind_from':'NE','relative_wind':'tailwind'}):
    try:prepare_conditions('宮島',**kwargs)
    except ValueError:pass
    else:raise AssertionError('Unsupported observation accepted')
print('PASS 24 venues, 8-point observed wind-from mapping, zero assumptions, tidal phase known-only, 120 probabilities')
