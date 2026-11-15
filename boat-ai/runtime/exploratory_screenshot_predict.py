#!/usr/bin/env python3
"""Score user-transcribed screenshots with the REAL trained model.
Exploratory if history features are missing. NEVER places bets.
"""
import argparse,itertools,json
from pathlib import Path
import joblib,numpy as np,pandas as pd
COMB=list(itertools.permutations(range(1,7),3))
def run(entries, odds, model_dir, dest):
    e=pd.read_csv(entries,encoding="utf-8-sig",dtype={"date":str,"venue":str,"race":str})
    o=pd.read_csv(odds,encoding="utf-8-sig",dtype={"date":str,"venue":str,"race":str,"trifecta":str})
    if len(e)!=6 or sorted(e.boat.astype(int).tolist())!=list(range(1,7)):
        raise ValueError("6 unique boats required")
    for field in ("date","venue","race"):
        if e[field].nunique()!=1:raise ValueError("mixed races")
        if not (o[field]==e[field].iloc[0]).all():raise ValueError("odds mismatch")
    if o.trifecta.duplicated().any():raise ValueError("duplicate odds")
    legal={"-".join(map(str,c)) for c in COMB}
    if not set(o.trifecta).issubset(legal):raise ValueError("invalid trifecta")
    models=[joblib.load(Path(model_dir)/("with_motor_rank%d.joblib"%i)) for i in (1,2,3)]
    features=models[0]["features"]
    if any(m["features"]!=features for m in models):raise ValueError("inconsistent feature schema")
    for f in features:
        if f not in e:e[f]=np.nan
    X=e.sort_values("boat")[features].apply(pd.to_numeric,errors="coerce").replace([np.inf,-np.inf],np.nan)
    observed=int(X.notna().sum().sum());total=int(X.size)
    s=np.maximum(np.array([m["model"].predict_proba(X)[:,1] for m in models]).T,1e-12)
    s[:,0]/=s[:,0].sum()
    p=[]
    for a,b,c in COMB:
        i,j,k=a-1,b-1,c-1
        p.append(s[i,0]*s[j,1]/(s[:,1].sum()-s[i,1])*s[k,2]/(s[:,2].sum()-s[i,2]-s[j,2]))
    t=float(json.loads((Path(model_dir)/"学習検証結果.json").read_text())["with_motor"]["calibration_temperature"])
    p=np.maximum(np.array(p),1e-12)**(1/t);p/=p.sum()
    odd={str(x.trifecta):float(x.odds) for x in o.itertuples(index=False) if pd.notna(x.odds) and float(x.odds)>1}
    out=[]
    for c,prob in zip(COMB,p):
        combo="-".join(map(str,c));price=odd.get(combo)
        out.append({"trifecta":combo,"probability":prob,"observed_odds":price,"ev_proxy_pct":prob*price*100 if price else np.nan})
    dest=Path(dest);dest.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(out).sort_values("probability",ascending=False).to_csv(dest/"all120.csv",index=False,encoding="utf-8-sig")
    pd.DataFrame(out).dropna(subset=["observed_odds"]).sort_values("ev_proxy_pct",ascending=False).head(3).to_csv(dest/"visible_odds_top3.csv",index=False,encoding="utf-8-sig")
    summary={"mode":"EXPLORATORY_NO_BETS","model_ran":True,"date":str(e.date.iloc[0]),
       "venue":str(e.venue.iloc[0]),"race":str(e.race.iloc[0]),
       "inputs_present":observed,"inputs_total":total,"known_odds":len(odd),
       "all120_prob_sum":float(p.sum()),"paper_bets_placed":0,
       "note":"This is NOT a validated EV recommendation. Missing latest motor/stint history; do not treat as automatic picks."}
    (dest/"report.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False))
if __name__=="__main__":
    q=argparse.ArgumentParser()
    for k in ("entries","odds","models","output"):q.add_argument("--"+k,required=True)
    a=q.parse_args();run(a.entries,a.odds,a.models,a.output)
