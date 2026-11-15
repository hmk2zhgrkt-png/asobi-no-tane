#!/usr/bin/env python3
"""End-to-end screenshot transcription input checks; zero network dependencies."""
import datetime as dt
import itertools
import json
import tempfile
from pathlib import Path
from screenshot_input import read_screenshot, overlay_screenshot, odds_coverage
JST=dt.timezone(dt.timedelta(hours=9))
now=dt.datetime.now(JST)
date=now.date()
code=f'{date:%Y%m%d}2408'
obj={'date':date.isoformat(),'venue':24,'race':8,'source':'chat_screenshot',
     'transcribed_by':'assistant','observed_at_jst':now.isoformat(),'cutoff_jst':(now+dt.timedelta(minutes=15)).strftime('%H:%M'),
     'fields':{'wind_speed_m':3,'wave_cm':2,'exhibition_st':[.03,.11,.11,.17,.04,.04],
               'entry_course':[1,2,3,4,5,6],
               'odds':{'1-2-3':7.2,'1-3-2':9.1}}}
with tempfile.TemporaryDirectory() as d:
    p=Path(d)/'screenshot_input.json'
    p.write_text(json.dumps(obj),encoding='utf-8')
    read=read_screenshot(p,date,24,8)
    assert read['odds_count']==2 and not read['complete_odds']
    assert read_screenshot(p,date,24,7) is None
    close=now+dt.timedelta(minutes=15)
    odds=overlay_screenshot([],read,'previews/od3',code,close)[0]
    assert odds['3連単_1-3-2']=='9.1'
    assert odds_coverage(odds)==2
    weather=overlay_screenshot([],read,'previews/sui',code,close)[0]
    assert weather['風速(m)']=='3.0' and weather['波の高さ(cm)']=='2.0'
    st=overlay_screenshot([],read,'previews/stt',code,close)[0]
    assert st['艇6_コース']=='6' and st['艇6_スタート展示']=='0.04'
    allodds={'-'.join(map(str,z)):float(i+2) for i,z in enumerate(itertools.permutations(range(1,7),3))}
    obj['fields']['odds']=allodds
    p.write_text(json.dumps(obj),encoding='utf-8')
    allread=read_screenshot(p,date,24,8)
    assert allread['complete_odds'] and allread['odds_count']==120
    assert odds_coverage(overlay_screenshot([],allread,'previews/od3',code,close)[0])==120
    obj['fields']['entry_course']=[1,1,3,4,5,6]
    p.write_text(json.dumps(obj),encoding='utf-8')
    try:read_screenshot(p,date,24,8)
    except ValueError:pass
    else:raise AssertionError('Duplicate entry course must be blocked')
    obj['fields']['entry_course']=[1,2,3,4,5,6]
    obj['fields']['odds']={'1-1-2':8.0}
    p.write_text(json.dumps(obj),encoding='utf-8')
    try:read_screenshot(p,date,24,8)
    except ValueError:pass
    else:raise AssertionError('Invalid trifecta must be blocked')
print('PASS: screenshot data input, partial/120 odds, race matching, numeric validation')
