#!/usr/bin/env python3
"""Guard against same-race and same-day outcome leakage in 3-year training."""
import datetime as dt
import numpy as np
from train_course_3y import generate_feature_rows,assess,FEATURES,N_BASE
def row(day,race,boat,place,course=None,racer=None):
    return dict(date=day,race_code=race,boat=str(boat),venue_code="13",
                racer_id=str(racer or 4000+boat),actual_course=str(course or boat),
                finish_place=str(place))
day1=[row("2026-01-01","202601011301",b,b) for b in range(1,7)]
# The same racer's second race on same date must NOT use earlier race result.
day1b=[row("2026-01-01","202601011302",b,b) for b in range(1,7)]
day2=[row("2026-01-02","202601021301",b,b) for b in range(1,7)]
out=list(generate_feature_rows(day1+day1b+day2))
assert len(out)==18
start=N_BASE
# For each window: first group overall win, top2, top3, log starts.
assert out[0][3][start:start+4]==out[6][3][start:start+4], "Same date leakage"
assert out[12][3][start+3]>out[0][3][start+3], "Prior day history not accrued"
assert all(len(r[3])==len(FEATURES) for r in out)
# 120 exact normalized outcome combinations evaluated as probabilities.
class Fake:
    def predict_proba(self,x):
        p=np.ones(len(x))*0.15
        return np.stack([1-p,p],axis=1)
X=np.asarray([r[3] for r in out],dtype=np.float32)
y=np.asarray([r[4] for r in out],dtype=np.int8)
key=np.asarray([r[1] for r in out])
boat=np.asarray([r[2] for r in out])
res=assess([Fake(),Fake(),Fake()],X,y,key,boat,np.ones(len(out),dtype=bool),True)
assert abs(res["prob_sum_max_abs_error"])<1e-9
assert res["races"]==3
assert abs(res["trifecta_log_loss"]-np.log(120))<1e-5
print("PASS: strict previous-day course history, six boats per race, exactly 120 normalized trifectas")
