#!/usr/bin/env python3
"""Leakage/symmetry regression for independent Elo: not site-owned metrics."""
from own_elo import Elo,elo_feature_rows,INITIAL,expected
def race(day,code,winner_id=4001):
    participants=[]
    for boat in range(1,7):
        participants.append({'date':day,'race_code':code,'boat':boat,
                             'racer_id':4000+boat,
                             'finish_place':boat if winner_id==4001 else 7-boat})
    return participants
day1=race('2026-01-01','202601011801')
day1_again=race('2026-01-01','202601011802')
day2=race('2026-01-02','202601021801')
features=list(elo_feature_rows(day1+day1_again+day2))
assert len(features)==18
assert features[:6]==features[6:12], 'Same-day history leakage'
assert features[0]!=features[12], 'Next day prior Elo must change'
assert abs(expected(1500,1500)-.5)<1e-15
ratings=Elo()
before=ratings.snapshot(day1)
assert all(abs(x[0])<1e-14 for x in before)
ratings.update_race(day1)
assert ratings.ratings[4001]>1500 and ratings.ratings[4006]<1500
assert abs(sum(ratings.ratings.values())-6*INITIAL)<1e-8
assert all(len(x)==4 for x in features)
try:list(elo_feature_rows(day2+day1))
except ValueError:pass
else:raise AssertionError('Unsorted date should fail')
print('PASS independent 15-pair Elo, symmetric updates, strictly previous calendar day, no date leakage')
