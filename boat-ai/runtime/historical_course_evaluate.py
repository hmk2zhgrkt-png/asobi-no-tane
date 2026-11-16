#!/usr/bin/env python3
"""Proof-of-concept temporal comparison: pre-race frame prior versus past actual-course history.

IMPORTANT: current race's *realized* entry course is a POST-RACE label and
MUST NOT be used as an input. Without recorded pre-start exhibition courses,
boat number is used only as a clearly identified *planned-course proxy*.
This is not the user's production 28-feature model and not an enhancement to it.

No predictions are converted to wagers.
"""
import argparse
import collections
import csv
import datetime as dt
import json
import math
from pathlib import Path
from sklearn.linear_model import LogisticRegression

def to_rows(path):
    with open(path,encoding="utf-8-sig",newline="") as f:rows=list(csv.DictReader(f))
    return rows

def _prior_features(rows):
    day_groups=collections.defaultdict(list)
    for r in rows:day_groups[r["date"]].append(r)
    history=collections.defaultdict(lambda:[0,0,0,0])
    observations=[]
    for day in sorted(day_groups):
        current=day_groups[day]
        for r in current:
            boat=int(r["boat"]);racer=int(r["racer_id"])
            # Pre-race default: use gate/boat as proxy for course, NEVER actual_course.
            n,w,top2,top3=history[(racer,boat)]
            observations.append(dict(date=day,race_code=r["race_code"],boat=boat,
              racer_id=racer,place=int(r["finish_place"]),
              features=[boat/6,(w+1)/(n+6),(top2+2)/(n+6),(top3+3)/(n+6),math.log1p(n)]))
        for r in current:
            key=(int(r["racer_id"]),int(r["actual_course"]))
            z=history[key];p=int(r["finish_place"])
            z[0]+=1;z[1]+=p==1;z[2]+=p<=2;z[3]+=p<=3
    return observations

def evaluate(rows):
    if not rows:return dict(status="NO_DATA",reason="No joined actual entry course/finish rows")
    days=sorted({r["date"] for r in rows})
    if len(days)<6:return dict(status="INSUFFICIENT_DATA",reason="Require at least six distinct dates to prevent random within-race leakage",days=len(days),racer_rows=len(rows))
    pivot=max(3,round(len(days)*0.7))
    if pivot>=len(days):return dict(status="INSUFFICIENT_DATA",reason="No held-out days")
    first_test=days[pivot]
    observations=_prior_features(rows)
    # Group-level integrity must hold: six runners, one winner, no duplicates.
    grouped=collections.defaultdict(list)
    for r in observations:grouped[r["race_code"]].append(r)
    valid=[g for g in grouped.values() if len(g)==6 and sum(x["place"]==1 for x in g)==1 and len({x["boat"] for x in g})==6]
    train=[x for group in valid for x in group if x["date"]<first_test]
    test=[group for group in valid if group[0]["date"]>=first_test]
    if len(train)<180 or len(test)<10:return dict(status="INSUFFICIENT_DATA",reason="Need >=30 training races and >=10 held-out races",training_racers=len(train),heldout_races=len(test),days=len(days))
    # Frame-only benchmark, Laplace-smoothed by pre-start boat number.
    boat_win=collections.Counter(x["boat"] for x in train if x["place"]==1)
    boat_runs=collections.Counter(x["boat"] for x in train)
    baseline={b:(boat_win[b]+1)/(boat_runs[b]+6) for b in range(1,7)}
    # Candidate uses only prior historical finishes in matched ACTUAL courses and
    # assigned pre-start boat/frame. It NEVER sees today's actual entry.
    features=[x["features"] for x in train]
    labels=[int(x["place"]==1) for x in train]
    model=LogisticRegression(max_iter=300,random_state=42)
    model.fit(features,labels)
    # Score normalized across six boats, identical held-out races.
    def score_races(method):
        loss=0.0;hit=0;count=0
        for group in test:
            if method=="benchmark":raw=[baseline[x["boat"]] for x in group]
            else:raw=model.predict_proba([x["features"] for x in group])[:,1].tolist()
            total=sum(raw)
            probs=[max(1e-9,v/total) for v in raw]
            winner=next(i for i,r in enumerate(group) if r["place"]==1)
            loss+=-math.log(probs[winner])
            hit+=int(probs.index(max(probs))==winner)
            count+=1
        return {"heldout_races":count,"winner_log_loss":round(loss/count,6),"winner_top1_accuracy":round(hit/count,6)}
    a,b=score_races("benchmark"),score_races("course")
    return {"status":"EVALUATED","train_dates":[days[0],days[pivot-1]],
            "holdout_dates":[first_test,days[-1]],
            "train_races":len(train)//6,
            "benchmark_frame_only":a,"experimental_frame_plus_prior_actual_course":b,
            "log_loss_improvement":round(a["winner_log_loss"]-b["winner_log_loss"],6),
            "model_retrained_production":False,
            "prediction_course_input":"pre-start gate as proxy; verified exhibition course needed for real integration",
            "leakage_rule":"Same-race actual entry course and finish are labels ONLY; prior actual-course history uses earlier dates",
            "caution":"Small pilot only. Production 28-feature model NOT compared. No paper bets."}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    report=evaluate(to_rows(a.source))
    dest=Path(a.out);dest.mkdir(parents=True,exist_ok=True)
    (dest/"evaluation.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False))
