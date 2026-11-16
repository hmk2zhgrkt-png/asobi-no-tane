#!/usr/bin/env python3
"""Offline deterministic regression, verifies joining and no same-day leakage."""
import datetime as dt
from historical_course_dataset import join_day,add_prior_features,write
import tempfile
from pathlib import Path

def card(code):
    return dict(レースコード=code,**{f"艇{b}_{field}":str(4000+b if field=="登録番号" else b+20)
        for b in range(1,7) for field in ("登録番号","モーター番号")})
def result(code,order,courses):
    r={"レースコード":code}
    for i,b in enumerate(order,1):r[f"{i}着_艇番"]=str(b)
    for i,b in enumerate(courses,1):
        r[f"{i}コース_艇番"]=str(b);r[f"{i}コース_スタートタイミング"]="0.12"
    return r
day=dt.date(2026,5,6)
code="202605061301"
a,audit=join_day([card(code)],[result(code,[1,3,2,5,4,6],[1,2,5,3,4,6])],day)
assert len(a)==6 and audit["complete_races"]==1
assert next(x for x in a if x["boat"]==5)["actual_course"]==3
assert next(x for x in a if x["boat"]==3)["finish_place"]==2
assert next(x for x in a if x["boat"]==1)["actual_course"]==1
broken=result(code,[1,2,2,3,4,5],[1,2,3,4,5,6])
b,stats=join_day([card(code)],[broken],day)
assert not b and stats["invalid_result_or_card"]==1
code2="202605071301"
c,_=join_day([card(code2)],[result(code2,[3,2,1,5,4,6],[1,2,5,3,4,6])],day+dt.timedelta(days=1))
features=add_prior_features(a+c)
first=[x for x in features if x["date"]==day.isoformat()]
second=[x for x in features if x["date"]==(day+dt.timedelta(days=1)).isoformat()]
assert all(x["prior_actual_course_starts"]==0 for x in first)
assert all(x["prior_actual_course_starts"]==1 for x in second)
assert next(x for x in second if x["boat"]==1)["prior_actual_course_wins"]==1
same_day_code="202605061302"
extra,_=join_day([card(same_day_code)],[result(same_day_code,[3,2,1,5,4,6],[1,2,5,3,4,6])],day)
again=add_prior_features(a+extra+c)
assert all(x["prior_actual_course_starts"]==0 for x in again if x["date"]==day.isoformat())
assert all(x["prior_actual_course_starts"]==2 for x in again if x["date"]==(day+dt.timedelta(days=1)).isoformat())
with tempfile.TemporaryDirectory() as p:
    x=write(a+c,[{"date":"2026-05-06","status":"ok"},{"date":"2026-05-07","status":"ok"}],p)
    assert x["complete_races"]==2
    assert (Path(p)/"historical_course_labels.csv").is_file()
    assert (Path(p)/"course_history_features_research_only.csv").is_file()
print("PASS: exact racer/course/finish join, invalid-row exclusions, no future or same-day leakage")
