#!/usr/bin/env python3
"""Only paper decisions. Never generate fake modern features or bypass timestamp checks."""
import argparse,csv,datetime as dt,subprocess,sys,json
from pathlib import Path
from itertools import permutations
ROOT=Path(__file__).resolve().parents[1]
HERE=Path(__file__).resolve().parent
def main():
 p=argparse.ArgumentParser()
 p.add_argument('--entries',required=True);p.add_argument('--odds',required=True);p.add_argument('--out',required=True)
 p.add_argument('--mode',choices=['historical-demo','live'],required=True)
 p.add_argument('--results')
 a=p.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
 with open(a.entries,encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
 if len(rows)!=6 or sorted(int(r['boat']) for r in rows)!=list(range(1,7)):raise ValueError('Exactly 6 boats required')
 keys={(r['date'],r['venue'],str(r['race'])) for r in rows}
 if len(keys)!=1:raise ValueError('Only one race allowed')
 date,venue,race=next(iter(keys))
 with open(a.odds,encoding='utf-8-sig',newline='') as f:odds=list(csv.DictReader(f))
 if len(odds)!=1 or (str(odds[0].get('date')),str(odds[0].get('venue')),str(odds[0].get('race')))!=(date,venue,race):
  raise ValueError('Odds race does not match entries')
 required=['3連単_'+'-'.join(map(str,c)) for c in permutations(range(1,7),3)]
 if any(not odds[0].get(x) for x in required):raise ValueError('Full 120 pre-close odds required')
 if a.mode=='live':
  now=dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
  if date!=now.date().isoformat():raise ValueError('Live event date must be today JST')
  for r in rows:
   if str(r.get('feature_verified','')).lower() not in ('true','1') or not r.get('feature_asof_jst'):raise ValueError('Missing verified current racer/motor features: SKIP')
   timestamp=dt.datetime.fromisoformat(r['feature_asof_jst']);close=dt.datetime.fromisoformat(r['cutoff_jst'])
   if not(timestamp.tzinfo and close.tzinfo and timestamp<=now<close):raise ValueError('Features timestamp/close invalid: SKIP')
  seen=dt.datetime.fromisoformat(odds[0]['observed_jst'])
  if not seen.tzinfo or not seen<=now<close:raise ValueError('Odds timestamp/close invalid: SKIP')
 model=HERE/'model'
 for name in ('with_motor_rank1.joblib','with_motor_rank2.joblib','with_motor_rank3.joblib','学習検証結果.json'):
  if not (model/name).is_file():raise FileNotFoundError('Missing trained model: '+name)
 prediction=out/'predictions_120.csv'
 subprocess.run([sys.executable,str(HERE/'predict_live.py'),'--input',a.entries,'--odds',a.odds,'--model-dir',str(model),'--model-name','with_motor','--output',str(prediction)],check=True)
 ledger=out/'paper_ledger.csv'
 subprocess.run([sys.executable,str(ROOT/'paper_trade.py'),'decide','--predictions',str(prediction),'--ledger',str(ledger),'--date',date],check=True)
 if a.results and a.mode=='historical-demo' and ledger.exists():
  subprocess.run([sys.executable,str(ROOT/'paper_trade.py'),'settle','--ledger',str(ledger),'--results',a.results],check=True)
 (out/'manifest.json').write_text(json.dumps({'mode':a.mode,'date':date,'venue':venue,'race':race,'real_bets':False},ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
