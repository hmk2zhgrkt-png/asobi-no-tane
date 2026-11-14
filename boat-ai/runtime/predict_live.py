#!/usr/bin/env python3
"""120 ordered trifecta probabilities; needs six pre-race feature rows and complete verified odds."""
import argparse,itertools,json
from pathlib import Path
import joblib,numpy as np,pandas as pd
PERMS=list(itertools.permutations(range(6),3))
def run(entries,model_dir,odds,out):
 x=pd.read_csv(entries,encoding='utf-8-sig');od=pd.read_csv(odds,encoding='utf-8-sig')
 features=None;scores=[]
 for rank in (1,2,3):
  blob=joblib.load(Path(model_dir)/f'with_motor_rank{rank}.joblib')
  f=list(blob['features'])
  if features is not None and features!=f:raise ValueError('Feature schema mismatch')
  features=f
  missing=[c for c in features if c not in x.columns]
  if missing:raise ValueError('Missing model inputs: '+','.join(missing))
  v=x[features].apply(pd.to_numeric,errors='coerce').replace([np.inf,-np.inf],np.nan)
  scores.append(blob['model'].predict_proba(v)[:,1])
 meta=json.loads((Path(model_dir)/'学習検証結果.json').read_text(encoding='utf-8'))
 temperature=float(meta['with_motor']['calibration_temperature'])
 if not np.isfinite(temperature) or temperature<=0:raise ValueError('Invalid calibration temperature')
 x=x.copy()
 for i,s in enumerate(scores):x[f'_p{i}']=s
 outrows=[]
 for key,g in x.groupby(['date','venue','race'],sort=True):
  g=g.sort_values('boat')
  if g.boat.astype(int).tolist()!=[1,2,3,4,5,6]:raise ValueError(f'{key}: invalid lineup')
  s=np.maximum(g[['_p0','_p1','_p2']].to_numpy(float),1e-8)
  p1=s[:,0]/s[:,0].sum();p=[]
  for i,j,k in PERMS:
   t=p1[i]*s[j,1]/max(s[:,1].sum()-s[i,1],1e-8)
   t*=s[k,2]/max(s[:,2].sum()-s[i,2]-s[j,2],1e-8)
   p.append(t)
  p=np.maximum(np.asarray(p,float),1e-12);p=np.power(p,1/temperature);p/=p.sum()
  matched=od[(od.date==key[0])&(od.venue==key[1])&(od.race==key[2])]
  if len(matched)!=1:raise ValueError(f'{key}: missing odds')
  r=matched.iloc[0]
  observed=pd.to_datetime(r['observed_jst'],errors='coerce');cutoff=pd.to_datetime(g.iloc[0]['cutoff_jst'],errors='coerce')
  if pd.isna(observed) or pd.isna(cutoff):raise ValueError('Timestamp missing')
  if observed.tzinfo is None:observed=observed.tz_localize('Asia/Tokyo')
  if cutoff.tzinfo is None:cutoff=cutoff.tz_localize('Asia/Tokyo')
  if observed>cutoff:raise ValueError('Odds captured post-cutoff')
  for c,prob in zip(PERMS,p):
   combination='-'.join(str(z+1) for z in c)
   val=pd.to_numeric(r['3連単_'+combination],errors='coerce')
   if pd.isna(val) or val<=1:raise ValueError('Odds unavailable: '+combination)
   outrows.append(dict(date=key[0],venue=key[1],race=key[2],trifecta=combination,probability=prob,odds=val,expected_roi_proxy_pct=prob*val*100))
 df=pd.DataFrame(outrows).sort_values(['date','venue','race','probability'],ascending=[True,True,True,False])
 df.to_csv(out,index=False,encoding='utf-8-sig')
 print('Predicted',len(df),'tickets')
if __name__=='__main__':
 p=argparse.ArgumentParser()
 p.add_argument('--input',required=True);p.add_argument('--model-dir',required=True)
 p.add_argument('--model-name',choices=['with_motor'],required=True);p.add_argument('--odds',required=True);p.add_argument('--output',required=True)
 a=p.parse_args();run(a.input,a.model_dir,a.odds,a.output)
