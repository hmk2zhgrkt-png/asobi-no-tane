#!/usr/bin/env python3
"""Explicitly synthetic data for a GitHub Actions INFRASTRUCTURE smoke test.
NOT historical data, NOT a valid prediction, NOT a betting recommendation.
"""
import csv,itertools,json
from pathlib import Path
BASE=Path(__file__).resolve().parent
model=json.loads((BASE/'model'/'学習検証結果.json').read_text(encoding='utf-8'))
features=model['with_motor']['features']
entries=[]
for boat in range(1,7):
 row={'date':'2026-10-31','venue':'SYNTHETIC_TEST','race':1,'boat':boat,
      'racer_id':str(9000+boat),'cutoff_jst':'2026-10-31T12:30:00+09:00'}
 for col in features:
  if 'win_rate' in col or 'top3_rate' in col or 'top2_mean' in col: value=0.2+boat/30
  elif 'exhibition_time' in col: value=6.7+boat/100
  elif 'entry_course' in col: value=boat
  elif 'exhibition_st' in col: value=0.12+boat/100
  elif 'prior_runs' in col: value=10+boat
  elif 'exh' in col: value=(boat-3)/100
  elif col=='motor_prior_valid':value=1
  else:value=1
  row[col]=value
 entries.append(row)
with open(BASE/'input'/'entries.csv','w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=list(entries[0]));w.writeheader();w.writerows(entries)
odds={'date':'2026-10-31','venue':'SYNTHETIC_TEST','race':1,'observed_jst':'2026-10-31T12:00:00+09:00'}
for i,comb in enumerate(itertools.permutations(range(1,7),3)):
 odds['3連単_'+'-'.join(map(str,comb))]=round(25+10*(i%12),1)
with open(BASE/'input'/'odds.csv','w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=list(odds));w.writeheader();w.writerow(odds)
print('Synthetic six-boat input and all 120 odds created. This is NOT real historical data.')
