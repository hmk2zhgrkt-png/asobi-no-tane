#!/usr/bin/env python3
"""Three-year time-safe BOAT RACE first/second/third positional model experiment.

Uses 36 hash-audited month archives (labels: actual post-race course, finishing
place). Each race's predictive data contains ONLY boat/frame, venue and
historical results from PREVIOUS DATES. Race-day actual course never enters X.
The pre-start course is proxied by frame because historic exhibition entry
snapshots are not in official K result archives.

Train 2023-11..2026-06, validation 2026-07..08, untouched final holdout
2026-09..10. Baseline and candidate are fit/evaluated identically.
Three 1-vs-rest logistic estimators produce normalized Plackett-Luce 3-way
trifecta probabilities, 120 each, without any odds or wagers.

NOT a retrain/backtest of the incumbent 28-feature real-time model.
"""
import argparse,bisect,csv,gzip,hashlib,itertools,json,math
from collections import defaultdict
from pathlib import Path
import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

TRAIN_END="2026-06-30"
VALID_END="2026-08-31"
TEST_END="2026-10-31"
WINDOWS=(30,90,365,1096)
COMBOS=np.array(list(itertools.permutations(range(6),3)),dtype=np.int8)
BOAT_FEATURES=[f"boat_{i}" for i in range(1,7)]
VENUE_FEATURES=[f"venue_{i}" for i in range(1,25)]
HIST_FEATURES=[f"{window}d_{group}_{stat}"
    for window in WINDOWS for group in ("all","course")
    for stat in ("win","top2","top3","log_starts")]
BASE_FEATURES=BOAT_FEATURES+VENUE_FEATURES
FEATURES=BASE_FEATURES+HIST_FEATURES
N_BASE=len(BASE_FEATURES)

class History:
    """Append-only time-ordered history, prefix sums allow 4 windows O(log n)."""
    def __init__(self):
        self.ordinals=[];self.wins=[0];self.top2=[0];self.top3=[0]
    def append(self,ordinal,place):
        self.ordinals.append(ordinal)
        self.wins.append(self.wins[-1]+int(place==1))
        self.top2.append(self.top2[-1]+int(place<=2))
        self.top3.append(self.top3[-1]+int(place<=3))
    def stats(self,day,days):
        # day itself is excluded, even for multiple races by same racer.
        lo=bisect.bisect_left(self.ordinals,day-days)
        hi=bisect.bisect_left(self.ordinals,day)
        n=hi-lo
        return (n,self.wins[hi]-self.wins[lo],
                self.top2[hi]-self.top2[lo],self.top3[hi]-self.top3[lo])

def iter_verified_rows(root):
    root=Path(root)
    manifest=json.loads((root/"manifest.json").read_text(encoding="utf-8"))
    if manifest["audited_months"]!=36 or manifest["no_audit_months"]:
        raise ValueError("All 36 calendar months required; no audit missing")
    for month in manifest["by_month"]:
        name=month["month"]
        audit=json.loads((root/f"{name}.audit.json").read_text(encoding="utf-8"))
        f=root/f"{name}.csv.gz"
        if hashlib.sha256(f.read_bytes()).hexdigest()!=audit["sha256"]:
            raise ValueError(f"Hash mismatch {name}")
        count=0
        with gzip.open(f,"rt",encoding="utf-8-sig",newline="") as inp:
            for row in csv.DictReader(inp):
                count+=1
                yield row
        if count!=month["racer_rows"] or count!=audit["racer_rows"]:
            raise ValueError(f"Count mismatch {name}")

def generate_feature_rows(rows):
    """Yield (date, race-code, boat, feature, position) with strict prior-day stats."""
    allhist=defaultdict(History)
    coursehist=defaultdict(History)
    buffer=[];current_date=None
    def flush(group):
        if not group:return []
        day=group[0]["date"]
        ordinal=__import__("datetime").date.fromisoformat(day).toordinal()
        out=[]
        for r in group:
            boat=int(r["boat"]);venue=int(r["venue_code"]);racer=int(r["racer_id"])
            if not 1<=boat<=6 or not 1<=venue<=24:raise ValueError("Invalid boat or venue")
            base=[float(k==boat) for k in range(1,7)]
            base.extend(float(k==venue) for k in range(1,25))
            h_all=allhist.get(racer)
            h_course=coursehist.get((racer,boat)) # boat=planned pre-start course proxy
            hist=[]
            for window in WINDOWS:
                for past in (h_all,h_course):
                    n,w,t2,t3=past.stats(ordinal,window) if past else (0,0,0,0)
                    # Bayesian smoothing; no postrace current-day fields in X.
                    hist.extend(((w+1)/(n+6),(t2+2)/(n+6),
                                 (t3+3)/(n+6),math.log1p(n)))
            out.append((day,r["race_code"],boat,base+hist,int(r["finish_place"])))
        # The entire date's labels are applied only after its features are fixed.
        for r in group:
            ordinal=__import__("datetime").date.fromisoformat(r["date"]).toordinal()
            racer=int(r["racer_id"]);course=int(r["actual_course"])
            place=int(r["finish_place"])
            if not 1<=course<=6 or not 1<=place<=6:raise ValueError("Invalid label")
            allhist[racer].append(ordinal,place)
            coursehist[(racer,course)].append(ordinal,place)
        return out
    for row in rows:
        if current_date is not None and row["date"]<current_date:raise ValueError("Unsorted historical days")
        if current_date is not None and row["date"]!=current_date:
            yield from flush(buffer)
            buffer=[]
        current_date=row["date"]
        buffer.append(row)
    yield from flush(buffer)

def build_training_arrays(root):
    feat=[];place=[];keys=[];boats=[];dates=[]
    for day,code,boat,x,y in generate_feature_rows(iter_verified_rows(root)):
        feat.append(x);place.append(y);keys.append(code);boats.append(boat);dates.append(day)
    X=np.asarray(feat,dtype=np.float32)
    y=np.asarray(place,dtype=np.int8)
    keys=np.asarray(keys,dtype="U12")
    boats=np.asarray(boats,dtype=np.int8)
    dates=np.asarray(dates,dtype="U10")
    if X.shape[1]!=len(FEATURES) or len(X)!=908112:raise ValueError("Feature rows/schema mismatch")
    if len(set(keys))!=151352:raise ValueError("Race count mismatch")
    if np.any(dates>TEST_END):raise ValueError("Future sample")
    return X,y,keys,boats,dates

def train(X,y,subset,include_history):
    cols=slice(None) if include_history else slice(0,N_BASE)
    result=[]
    for finishing_position in (1,2,3):
        target=(y[subset]==finishing_position).astype(np.int8)
        pipe=make_pipeline(StandardScaler(),
            LogisticRegression(max_iter=180,solver="lbfgs",C=0.15,
                               random_state=42,tol=2e-4))
        pipe.fit(X[subset,cols],target)
        result.append(pipe)
    return result

def assess(models,X,y,keys,boats,subset,include_history):
    cols=slice(None) if include_history else slice(0,N_BASE)
    m=X[subset,cols]
    scores=np.stack([model.predict_proba(m)[:,1] for model in models],axis=1)
    actual=y[subset];races=keys[subset];frames=boats[subset]
    if len(scores)%6:raise ValueError("Missing racer")
    # Input sorted in date+race+boat order, six distinct participants/race.
    if not (np.all(races.reshape(-1,6)==races.reshape(-1,6)[:,0,None]) and
            np.all(np.sort(frames.reshape(-1,6),axis=1)==np.arange(1,7)[None,:])):
        raise ValueError("Racer rows not 6-per-race in boat order")
    outcomes=actual.reshape(-1,6)
    pr=scores.reshape(-1,6,3)
    w=pr[:,:,0];second=pr[:,:,1];third=pr[:,:,2]
    # PL-like sequential factorization: 1st probability, 2nd among remaining,
    # 3rd among remaining. The conditional third is normalized per ordered pair.
    f=w/np.maximum(w.sum(axis=1,keepdims=True),1e-15)
    ww=f[:,COMBOS[:,0]]
    remaining2=second.sum(axis=1,keepdims=True)-second[:,COMBOS[:,0]]
    ss=second[:,COMBOS[:,1]]/np.maximum(remaining2,1e-15)
    remaining3=third.sum(axis=1,keepdims=True)-third[:,COMBOS[:,0]]-third[:,COMBOS[:,1]]
    tt=third[:,COMBOS[:,2]]/np.maximum(remaining3,1e-15)
    p=ww*ss*tt
    p/=p.sum(axis=1,keepdims=True)
    actual_indices=np.argsort(outcomes,axis=1)[:,:3]
    coded=actual_indices[:,0]*36+actual_indices[:,1]*6+actual_indices[:,2]
    combo_codes=COMBOS[:,0]*36+COMBOS[:,1]*6+COMBOS[:,2]
    index_by_code={int(v):i for i,v in enumerate(combo_codes)}
    trueidx=np.array([index_by_code[int(z)] for z in coded])
    sorted_indices=np.argsort(-p,axis=1)
    ranks=np.argmax(sorted_indices==trueidx[:,None],axis=1)+1
    winning=p[np.arange(len(p)),trueidx]
    first_winner=(outcomes==1).argmax(axis=1)
    first_prob=f[np.arange(len(f)),first_winner]
    return {"races":int(len(outcomes)),
       "winner_top1_accuracy":float(np.mean(np.argmax(f,axis=1)==first_winner)),
       "winner_log_loss":float(np.mean(-np.log(np.maximum(first_prob,1e-15)))),
       "trifecta_top1_hit_rate":float(np.mean(ranks<=1)),
       "trifecta_top3_hit_rate":float(np.mean(ranks<=3)),
       "trifecta_top5_hit_rate":float(np.mean(ranks<=5)),
       "trifecta_top10_hit_rate":float(np.mean(ranks<=10)),
       "trifecta_log_loss":float(np.mean(-np.log(np.maximum(winning,1e-15)))),
       "mean_trifecta_true_rank":float(np.mean(ranks)),
       "prob_sum_max_abs_error":float(np.max(np.abs(p.sum(axis=1)-1)))}

def main(root,out):
    X,y,keys,boats,dates=build_training_arrays(root)
    tr=dates<=TRAIN_END
    va=(dates>TRAIN_END)&(dates<=VALID_END)
    te=(dates>VALID_END)&(dates<=TEST_END)
    if min(tr.sum(),va.sum(),te.sum())<1000:raise ValueError("Insufficient chronological samples")
    d=Path(out);d.mkdir(parents=True,exist_ok=True)
    scores={};fitted={}
    for name,history in (("frame_venue_baseline",False),("frame_venue_plus_prior_course_history",True)):
        models=train(X,y,tr,history)
        scores[name]={"validation":assess(models,X,y,keys,boats,va,history),
                      "final_holdout":assess(models,X,y,keys,boats,te,history)}
        fitted[name]=models
    baseline=scores["frame_venue_baseline"]["final_holdout"]
    candidate=scores["frame_venue_plus_prior_course_history"]["final_holdout"]
    # Deployable only after a more rigorous same-feature baseline and independent
    # production-model comparison. Never automatically overwrite production.
    report={"status":"EVALUATED","data_period":["2023-11-01","2026-10-31"],
      "train_period":["2023-11-01",TRAIN_END],
      "validation_period":["2026-07-01",VALID_END],
      "final_holdout_period":["2026-09-01",TEST_END],
      "training_races":int(tr.sum()//6),"validation_races":int(va.sum()//6),
      "final_holdout_races":int(te.sum()//6),"total_rows":int(len(X)),
      "models":scores,
      "comparison":{"top5_hit_rate_delta":candidate["trifecta_top5_hit_rate"]-baseline["trifecta_top5_hit_rate"],
        "trifecta_log_loss_improvement":baseline["trifecta_log_loss"]-candidate["trifecta_log_loss"],
        "winner_log_loss_improvement":baseline["winner_log_loss"]-candidate["winner_log_loss"]},
      "production_model_modified":False,"production_28_feature_model_compared":False,
      "new_model_automatic_deployment":False,
      "actual_course_current_race_used_in_features":False,
      "planned_course_proxy":"prestart boat number, not actual or exhibition course",
      "historical_actual_course_used_as_prior_history_only":True,
      "eval_kind":"strict chronological race-disjoint holdout, no current-day result in features",
      "features":FEATURES,"no_bets":True}
    (d/"evaluation.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    # Candidate artifact is for future independent validation, NOT production.
    joblib.dump({"models":fitted["frame_venue_plus_prior_course_history"],
                 "features":FEATURES,"train_end":TRAIN_END,
                 "no_production_deployment":True},d/"candidate_research_only.joblib",compress=3)
    print(json.dumps({k:v for k,v in report.items() if k not in ("features",)},ensure_ascii=False))
    return report

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",default="boat-ai/runtime/course_history_3y")
    parser.add_argument("--out",default="boat-ai/runtime/course_training_3y")
    args=parser.parse_args()
    main(args.root,args.out)
