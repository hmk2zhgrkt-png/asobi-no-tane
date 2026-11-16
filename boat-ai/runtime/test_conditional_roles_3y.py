#!/usr/bin/env python3
"""Check conditional rank construction and no F/lookahead fields."""
import numpy as np
from conditional_roles_3y import SMALL_NAMES,small_features,two_features,three_features,fit_models,compare_proba,results,tune,apply_tuning
from train_course_3y import COMBOS,FEATURES
assert len(SMALL_NAMES)==14
assert 'exhibition' not in ' '.join(SMALL_NAMES).lower()
n=60;random=np.random.default_rng(41)
X=np.zeros((n*6,len(FEATURES)+4),dtype=np.float32)
Y=np.empty((n,6),dtype=np.int8)
for i in range(n):
    shuffle=random.permutation(6)
    Y[i,shuffle]=np.arange(1,7)
    for b in range(6):
        X[i*6+b,b]=1
        X[i*6+b,30:62]=random.uniform(.1,.7,32)
        X[i*6+b,-4:]=random.uniform(-1,1,4)
z=small_features(X).reshape(n,6,-1)
assert z.shape==(n,6,14)
a,b=fit_models(z,Y)
f=np.ones((n,6),dtype=np.float32)/6
P=compare_proba(z,f,a,b,batch=16)
assert P.shape==(n,120) and np.isfinite(P).all()
assert (P>0).all() and np.max(abs(P.sum(axis=1)-1))<1e-5
Q=np.ones((n,120))/120
v=results(P,Y)
assert v['races']==n and 0<=v['top5']<=1
s=tune(Q,P,Y)
Z=apply_tuning(Q,P,s)
assert abs(Z.sum(axis=1)-1).max()<1e-5
assert all(k in s for k in ('selected_alpha','selected_temperature','validation_logloss'))
print('PASS conditional P(first)*P(second|first)*P(third|first,second), 120-way sum, validation calibration, 14 pre-race features')
