#!/usr/bin/env python3
"""Experimental actual-entry-course adjustment of existing 120-way model probabilities.

NOT model training. Validated 6-racer input must precede race. Uses each racer's
3-year actual entry-course 1st/2nd/3rd place share, not starting-gate number.
Applies restrained empirical-Bayes shrinkage and normalizes all 120 outcomes.
No calibrated hit-rate claim, no implicit betting permissions.
"""
import csv
import datetime as dt
import itertools
import json
import math
from pathlib import Path

COMBOS = {"-".join(map(str, x)) for x in itertools.permutations(range(1, 7), 3)}
STRENGTH = 0.5
PRIOR_STARTS = 100
MIN_FACTOR,MAX_FACTOR = 0.75,1.25

def validate_context(context,date,venue,race,entries=None):
    if (str(context.get("date")),int(context.get("venue",-1)),int(context.get("race",-1)))!=(str(date),int(venue),int(race)):
        return None
    items=context.get("entries")
    if not isinstance(items,list) or len(items)!=6:raise ValueError("Need six racer course histories")
    by_boat={}
    for item in items:
        boat=int(item["boat"]);course=int(item["entry_course"]);racer=int(item["racer_id"])
        if boat in by_boat or not 1<=boat<=6 or not 1<=course<=6 or racer<1000:
            raise ValueError("Invalid racer/course identity")
        n=int(item["starts"])
        if n<0:raise ValueError("Negative course starts")
        w,two,three=[float(item[k])/100 for k in ("win_pct","top2_pct","top3_pct")]
        if not all(math.isfinite(z) for z in (w,two,three)) or not 0<=w<=two<=three<=1:
            raise ValueError("Course rates must be monotonic")
        by_boat[boat]=(course,racer,n,w,two,three)
    if set(by_boat)!=set(range(1,7)) or {z[0] for z in by_boat.values()}!=set(range(1,7)):
        raise ValueError("Entry courses must be a permutation")
    if entries:
        for item in entries:
            boat=int(item["boat"])
            course,racer,_,_,_,_=by_boat[boat]
            if int(item["racer_id"])!=racer or int(item["entry_course"])!=course:
                raise ValueError(f"Course snapshot racer/entry differs from live input boat {boat}")
    return by_boat

def factors(by_boat):
    # Exact place shares estimated from cumulative 1st, top2, top3 percentages.
    # After 1st is removed, second and third places are conditional on *not*
    # finishing earlier. No use of first-place win% as a second-place rate.
    role={}
    for boat,(course,racer,n,w,two,three) in by_boat.items():
        second=(two-w)/max(1e-5,1-w)
        third=(three-two)/max(1e-5,1-two)
        role[boat]=(w,second,third)
    population=[sum(role[b][k] for b in role)/6 for k in range(3)]
    out={}
    for boat,(course,racer,n,w,two,three) in by_boat.items():
        credibility=n/(n+PRIOR_STARTS)
        out[boat]=tuple(
            max(MIN_FACTOR,min(MAX_FACTOR,
                (1+credibility*(role[boat][k]-population[k])/max(0.03,population[k]))**STRENGTH))
            for k in range(3)
        )
    return out

def rescore(rows,context,date,venue,race,entries=None):
    by_boat=validate_context(context,date,venue,race,entries)
    if by_boat is None:return None
    if len(rows)!=120 or {str(r["trifecta"]) for r in rows}!=COMBOS:
        raise ValueError("Expected exactly 120 trifecta predictions")
    fs=factors(by_boat)
    weighted=[]
    for row in rows:
        a,b,c=[int(x) for x in str(row["trifecta"]).split("-")]
        p=float(row["probability"])
        if not math.isfinite(p) or p<0:raise ValueError("Invalid base model probability")
        weighted.append(p*fs[a][0]*fs[b][1]*fs[c][2])
    norm=sum(weighted)
    if not norm>0:raise ValueError("Zero normalized probabilities")
    output=[]
    for row,val in zip(rows,weighted):
        copy=dict(row)
        copy["pre_course_probability"]=float(row["probability"])
        copy["probability"]=val/norm
        odds=str(row.get("observed_odds","")).strip()
        copy["estimated_roi_proxy_pct"]=copy["probability"]*float(odds)*100 if odds and odds.lower() not in ("nan","none") else None
        output.append(copy)
    return output

def report(rows):
    ranked=sorted(rows,key=lambda r:r["probability"],reverse=True)
    return {"course_adjusted_top5":[{"trifecta":r["trifecta"],"probability":r["probability"]}
                                    for r in ranked[:5]],
            "probability_sum":sum(r["probability"] for r in rows),
            "method":"bounded, smoothed, per-racer actual-course finish-role adjustment",
            "model_retrained":False,"backtested":False,
            "confidence_note":"Exploratory post-model sensitivity, not a trained or calibrated probability model"}

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--predictions",required=True)
    p.add_argument("--course-context",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    context=json.loads(Path(a.course_context).read_text(encoding="utf-8"))
    with open(a.predictions,encoding="utf-8-sig",newline="") as f:rows=list(csv.DictReader(f))
    updated=rescore(rows,context,context["date"],context["venue"],context["race"])
    if updated is None:raise ValueError("No matching course context")
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    with (out/"course_adjusted_120.csv").open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(updated[0]))
        writer.writeheader();writer.writerows(updated)
    (out/"course_adjusted_top5.json").write_text(
        json.dumps(report(updated),ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report(updated),ensure_ascii=False))
