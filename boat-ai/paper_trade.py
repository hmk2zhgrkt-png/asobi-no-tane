#!/usr/bin/env python3
"""Paper-only purchase/settlement; consumes model probability CSV with verified preclose odds."""
import argparse,json
from pathlib import Path
import pandas as pd
KEY=['date','venue','race','trifecta']
FIELDS=KEY+['probability','odds','expected_roi_proxy_pct','stake_yen','status','actual','payout_per_100_yen','return_yen']
def read_ledger(p):
    if not Path(p).exists(): return pd.DataFrame(columns=FIELDS)
    x=pd.read_csv(p,encoding='utf-8-sig',dtype={'date':str,'trifecta':str})
    if x.duplicated(KEY).any():raise ValueError('duplicate ledger entries')
    return x
def choose(args):
    x=pd.read_csv(args.predictions,encoding='utf-8-sig',dtype={'date':str,'trifecta':str})
    must=KEY+['probability','odds','expected_roi_proxy_pct']
    if any(c not in x for c in must):raise ValueError('verified odds required for every eligible pick')
    if x.duplicated(KEY).any():raise ValueError('duplicate predictions')
    for c in must[4:]:x[c]=pd.to_numeric(x[c],errors='coerce')
    x=x[(x.date==args.date)&x.probability.between(0,1)&x.odds.gt(1)&(x.expected_roi_proxy_pct>=120)]
    old=read_ledger(args.ledger);day=old[old.date==args.date]
    spent=pd.to_numeric(day.stake_yen,errors='coerce').fillna(0).sum()
    room=int((1000-spent)//100)
    existing=set(tuple(v) for v in day[['date','venue','race']].itertuples(index=False,name=None))
    race_slots=max(0,2-len(existing))
    x=x[~x.apply(lambda r:(r.date,r.venue,r.race) in existing,axis=1)]
    chosen=[];race_groups=[]
    for key,g in x.groupby(['date','venue','race']):
        r=g.sort_values('expected_roi_proxy_pct',ascending=False).head(3)
        race_groups.append((float(r.iloc[0].expected_roi_proxy_pct),key,r))
    for _,_,group in sorted(race_groups,key=lambda z:z[0],reverse=True)[:race_slots]:
        for _,r in group.iterrows():
            if room<=0:break
            picked={c:r[c] for c in must};picked.update(stake_yen=100,status='pending',actual='',payout_per_100_yen='',return_yen='')
            chosen.append(picked);room-=1
    if chosen:
        pd.concat([old,pd.DataFrame(chosen)],ignore_index=True).to_csv(args.ledger,index=False,encoding='utf-8-sig')
    print(json.dumps({'mode':'PAPER_ONLY','new_tickets':len(chosen),'stake_yen':len(chosen)*100,
                      'tickets':[v['trifecta'] for v in chosen]},ensure_ascii=False))
def settle(args):
    x=read_ledger(args.ledger)
    results=pd.read_csv(args.results,encoding='utf-8-sig',dtype={'date':str,'trifecta':str})
    required=['date','venue','race','actual','payout_per_100_yen']
    if any(c not in results for c in required):raise ValueError('missing result columns')
    if results.duplicated(['date','venue','race']).any():raise ValueError('duplicate result races')
    m=results.set_index(['date','venue','race']);num=0
    x=x.astype({'actual':'object','status':'object'})
    for i,r in x.iterrows():
        if r.status!='pending':continue
        key=(r.date,r.venue,r.race)
        if key not in m.index:continue
        actual=m.loc[key,'actual'];payout=float(m.loc[key,'payout_per_100_yen'])
        if payout<0:raise ValueError('invalid payout')
        x.loc[i,'actual']=actual;x.loc[i,'payout_per_100_yen']=payout
        x.loc[i,'return_yen']=payout*float(r.stake_yen)/100 if str(r.trifecta)==str(actual) else 0.0
        x.loc[i,'status']='settled';num+=1
    x.to_csv(args.ledger,index=False,encoding='utf-8-sig')
    sub=x[x.status=='settled'];bet=pd.to_numeric(sub.stake_yen).sum();rec=pd.to_numeric(sub.return_yen).sum()
    print(json.dumps({'settled_now':num,'total_stake_yen':float(bet),'return_yen':float(rec),'roi_pct':float(rec/bet*100) if bet else None},ensure_ascii=False))
def main():
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('decide');a.add_argument('--predictions',required=True);a.add_argument('--ledger',required=True);a.add_argument('--date',required=True)
    b=s.add_parser('settle');b.add_argument('--ledger',required=True);b.add_argument('--results',required=True)
    a=p.parse_args();choose(a) if a.action=='decide' else settle(a)
if __name__=='__main__':main()
