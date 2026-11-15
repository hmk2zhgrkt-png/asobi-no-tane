#!/usr/bin/env python3
"""Persistent paper-only tickets: idempotent, day-level constraints, verified settlement."""
import argparse, csv, datetime as dt, json
from pathlib import Path
import pandas as pd
from auto_predict import csvday,JST
FIELDS=['date','venue','venue_code','race','trifecta','recorded_at_jst','source_observed_jst','model_probability','odds_at_decision','estimated_roi_pct','stake_yen','status','actual_trifecta','payout_per_100_yen','return_yen']
KEY=['date','venue_code','race','trifecta']

def read_csv(path):
    if not Path(path).exists():return pd.DataFrame(columns=FIELDS)
    data=pd.read_csv(path,encoding='utf-8-sig',dtype={'date':str,'trifecta':str,'venue_code':str})
    if data.duplicated(KEY).any():raise ValueError('Duplicated paper ticket; refuse unsafe update')
    for col in FIELDS:
        if col not in data:data[col]=pd.NA
    return data[FIELDS]

def save(data,path):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    data.to_csv(path,index=False,encoding='utf-8-sig')

def add(report_path,candidates_path,ledger_path):
    r=json.loads(Path(report_path).read_text(encoding='utf-8'))
    old=read_csv(ledger_path)
    new=[]
    if r.get('status')!='PAPER_ONLY_CANDIDATES':
        print('PAPER_SKIP: '+str(r.get('status')))
        return {'added':0,'reason':r.get('status'),'total_records':len(old)}
    now=dt.datetime.now(JST)
    cutoff=dt.datetime.fromisoformat(r['deadline_jst']).astimezone(JST)
    if now.date().isoformat()!=r['date'] or now>=cutoff-dt.timedelta(minutes=1):
        raise ValueError('No betting after cutoff')
    if dt.datetime.fromisoformat(r['preclose_snapshot_asof_jst'])>now:
        raise ValueError('Odds snapshot is future-dated')
    cands=pd.read_csv(candidates_path)
    must=['trifecta','probability','observed_odds','estimated_roi_proxy_pct']
    if any(col not in cands for col in must):raise ValueError('Malformed model output')
    existing=old[old.date.eq(r['date'])]
    raced=existing[['venue_code','race']].astype(str).drop_duplicates()
    race_key=(str(r['venue_code']).zfill(2),str(r['race']))
    present=any(tuple(x)==race_key for x in raced.itertuples(index=False,name=None))
    if present or len(raced)>=2:
        return {'added':0,'reason':'daily race limit or duplicate race','total_records':len(old)}
    old_cost=pd.to_numeric(existing.stake_yen,errors='coerce').fillna(0).sum()
    max_tickets=min(3,max(0,int((1000-old_cost)//100)))
    for _,cand in cands.sort_values('estimated_roi_proxy_pct',ascending=False).head(max_tickets).iterrows():
        if float(cand.estimated_roi_proxy_pct)<120:continue
        new.append(dict(date=r['date'],venue=r['venue'],venue_code=race_key[0],race=r['race'],
            trifecta=str(cand.trifecta),recorded_at_jst=now.isoformat(),
            source_observed_jst=r['preclose_snapshot_asof_jst'],model_probability=float(cand.probability),
            odds_at_decision=float(cand.observed_odds),estimated_roi_pct=float(cand.estimated_roi_proxy_pct),
            stake_yen=100,status='pending',actual_trifecta='',payout_per_100_yen='',return_yen=''))
    if new:
        save(pd.concat([old,pd.DataFrame(new)],ignore_index=True),ledger_path)
    return {'added':len(new),'stake_yen':len(new)*100,'reason':'PAPER_ONLY','total_records':len(old)+len(new)}

def settle(ledger_path):
    old=read_csv(ledger_path)
    if old.empty:return {'settled':0,'pending':0,'total_stake_yen':0,'return_yen':0}
    pending=old[old.status.eq('pending')].copy()
    count=0
    for date,subset in pending.groupby('date'):
        day=dt.date.fromisoformat(str(date))
        rows=csvday('results/payouts',day,required=False)
        results={r['レースコード']:r for r in rows}
        for ix,row in subset.iterrows():
            code=f'{day:%Y%m%d}{int(row.venue_code):02d}{int(row.race):02d}'
            result=results.get(code)
            if not result:continue
            actual=str(result.get('3連単_組番','')).strip()
            if not actual or actual=='nan':continue
            payout=pd.to_numeric(result.get('3連単_払戻金'),errors='coerce')
            if pd.isna(payout) or payout<0:continue
            refund=float(row.stake_yen)*float(payout)/100 if str(row.trifecta)==actual else 0
            old.loc[ix,'actual_trifecta']=actual
            old.loc[ix,'payout_per_100_yen']=float(payout)
            old.loc[ix,'return_yen']=refund
            old.loc[ix,'status']='settled';count+=1
    if count:save(old,ledger_path)
    finished=old[old.status.eq('settled')]
    stake=pd.to_numeric(finished.stake_yen,errors='coerce').fillna(0).sum()
    paid=pd.to_numeric(finished.return_yen,errors='coerce').fillna(0).sum()
    return {'settled_now':count,'settled_total':len(finished),'pending':int(old.status.eq('pending').sum()),
      'total_stake_yen':float(stake),'return_yen':float(paid),'roi_pct':float(100*paid/stake) if stake else None}

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--ledger',required=True)
    p.add_argument('--report');p.add_argument('--candidates')
    p.add_argument('--settle',action='store_true')
    a=p.parse_args()
    if a.settle:result=settle(a.ledger)
    else:
        if not(a.report and a.candidates):raise ValueError('report and candidates required')
        result=add(a.report,a.candidates,a.ledger)
    print(json.dumps(result,ensure_ascii=False))